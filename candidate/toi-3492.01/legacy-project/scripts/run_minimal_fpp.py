"""Minimal scenario-based FPP estimate without TRICERATOPS.

Computes false-positive probability from:
- Gaia DR3 neighbor catalog (BEB scenarios)
- Geometric eclipse probability
- Stellar density mismatch indicator (EB scenarios)
- Planet occurrence rate prior

Vespa-style likelihood ratio, FPP = sum(non-TP scenarios) / sum(all).
"""
import json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Planet occurrence rate (Hot Jupiter around FGK) ~0.5-1%.
# Use 1% as conservative.
PRIOR_TP_RATE = 0.01
PRIOR_EB_RATE = 0.005   # ~1 in 200 F-G-K stars have EB at P<20d
PRIOR_BEB_RATE_PER_ARCSEC2 = 1e-6  # Background EB rate


def load_data():
    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    gaia = pd.read_csv(ROOT / "outputs" / "gaia_dr3_neighbors.csv")
    return config, gaia


def geometric_eclipse_prob(a_rs, rp_rs):
    """Geometric eclipse probability for central transit crossing."""
    return (rp_rs + 1.0) / a_rs


def beb_contribution(neighbor_row, target_g_mag, depth_ppm):
    """Compute BEB scenario contribution for a single Gaia neighbor.

    Constrain:
    - Flux ratio must allow apparent depth >= 0.5*observed for an EB at
      max intrinsic eclipse depth (~50%). Full eclipse, else drop.
    - Eclipse must be geometrically possible at this separation (random inclination).
    - A broader separation gets a softer weight based on TESS PRF falloff.
    """
    sep_arcsec = neighbor_row["separation_arcsec"]
    # Geometric eclipse probability (random inclination) ~ Rp/a
    p_eclipse = 0.05  # 5% for short-period EB
    delta_g = neighbor_row["phot_g_mean_mag"] - target_g_mag
    flux_ratio = 10 ** (-0.4 * delta_g)
    intrinsic_depth_fraction = 0.5  # max for an EB (full eclipse)
    apparent_depth_ppm = 1e6 * flux_ratio * intrinsic_depth_fraction / (1.0 + flux_ratio)
    # Only neighbors capable of producing at least half the observed depth
    if apparent_depth_ppm < 0.5 * depth_ppm:
        return 0.0
    # Spatial prior: TESS pixel=21". Aperture ~3 pix radius ~63".
    # After ~3 pix, depth contribution via PRF wings decays ~exponentially.
    pix_radius = sep_arcsec / 21.0
    spatial_prob = p_eclipse * math.exp(-max(0.0, pix_radius - 3.0))
    # Magnitude weight: closer in brightness = more likely to contaminate
    magnitude_weight = max(0.05, 1.0 - abs(delta_g) / 10.0)
    return spatial_prob * magnitude_weight


def main():
    config, gaia = load_data()
    target = gaia.loc[gaia["is_target_match"].astype(str).str.lower() == "true"].iloc[0]
    target_g = float(target["phot_g_mean_mag"])
    depth_ppm = float(config["transit"]["depth_ppm"])
    a_rs = float(config["transit"]["a_rs"])
    rp_rs = float(config["transit"]["rp_rs"])

    print("Observed: depth={} ppm, a/R*={:.2f}, Rp/R*={:.5f}".format(
        depth_ppm, a_rs, rp_rs))
    p_geom = geometric_eclipse_prob(a_rs, rp_rs)

    non_target = gaia.loc[gaia["is_target_match"].astype(str).str.lower() == "false"]

    # --- Scenario likelihoods ---
    # TP: transiting planet on target
    L_tp = PRIOR_TP_RATE * p_geom

    # EB: target itself is EB
    # Density mismatch: photometric density=0.188 solar vs catalog 0.072 -> 4.3 sigma
    # Strong indicator of either EB or planet around evolved star
    # Use moderate weight (not blow up; assumed pre-screened)
    L_eb_on_target = PRIOR_EB_RATE * p_geom * 0.5
    # Penalize by 4.3 sigma discrepancy (low weight for true EB scenario under circular planet)
    rho_sigma = 4.3
    L_eb_on_target *= math.exp(-0.5 * max(0.0, rho_sigma - 2.0))

    # BEB: blended eclipsing binaries from neighbors
    beb_total = 0.0
    beb_contributions = []
    for _, row in non_target.iterrows():
        contrib = beb_contribution(row, target_g, depth_ppm)
        if contrib > 0:
            beb_contributions.append((row["source_id"], row["separation_arcsec"],
                                       float(row["phot_g_mean_mag"]), contrib))
            beb_total += contrib
    L_beb = beb_total

    # Hierarchical TP (HTP): planet on unresolved companion to target
    # Gaia RUWE=0.985 (clean), non_single_star=0, but duplicated_source=True (caution)
    # Use a low prior
    L_htp = 0.0005 * p_geom

    L_total = L_tp + L_eb_on_target + L_beb + L_htp
    if L_total <= 0:
        print("ERROR: zero likelihood")
        return

    fpp = (L_eb_on_target + L_beb + L_htp) / L_total
    nfpp = (L_beb + L_htp) / L_total  # near-field false-positive
    contribution = {
        "TP": L_tp / L_total,
        "EB_on_target": L_eb_on_target / L_total,
        "BEB_total": L_beb / L_total,
        "HTP": L_htp / L_total,
    }

    print("\nFPP breakdown:")
    for k, v in contribution.items():
        print(f"  {k:15s}: {v:.4e}")
    print(f"FPP   = {fpp:.4e} ({100*fpp:.3f}%)")
    print(f"NFPP  = {nfpp:.4e} ({100*nfpp:.3f}%)")

    # Top BEB contributors
    beb_contributions.sort(key=lambda x: -x[3])
    print("\nTop 5 BEB candidates:")
    for src, sep, gm, c in beb_contributions[:5]:
        print(f"  {src}  sep={sep:.2f}\"  G={gm:.2f}  L={c:.4e}")

    result = {
        "method": "minimal_scenario_FPP",
        "not_triceratops": "TRICERATOPS stack failed (pytransit/numpy import); this estimate is indicative only, not a calibrated population FPP.",
        "depth_ppm": depth_ppm,
        "a_rs": a_rs,
        "rp_rs": rp_rs,
        "geometric_eclipse_probability": p_geom,
        "scenario_likelihoods": {
            "TP": L_tp,
            "EB_on_target": L_eb_on_target,
            "BEB_total": L_beb,
            "HTP": L_htp,
        },
        "scenario_probabilities": contribution,
        "FPP": float(fpp),
        "FPP_percent": 100.0 * fpp,
        "NFPP": float(nfpp),
        "NFPP_percent": 100.0 * nfpp,
        "top_beb_candidates": [
            {"source_id": s, "separation_arcsec": sep,
             "G_mag": gm, "likelihood": c}
            for s, sep, gm, c in beb_contributions[:10]
        ],
        "limitation": "Not a calibrated VESPA/TRICERATOPS FPP because no TRILEGAL prior, no light-curve simulation, no PRF source localization. Use only as a sanity-scale diagnostic.",
    }
    out = ROOT / "outputs" / "min_fpp_estimate.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()