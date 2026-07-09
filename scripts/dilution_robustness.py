import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
ARCHIVE_PATH = ROOT / "outputs" / "archive_enrichment.json"
GAIA_PATH = ROOT / "outputs" / "gaia_contamination_check.json"

OUT_CSV = ROOT / "outputs" / "dilution_summary_120s.csv"
OUT_JSON = ROOT / "outputs" / "dilution_corrected_transit_params.json"
OUT_WORST = ROOT / "outputs" / "dilution_worst_case_scenarios.json"
OUT_MD = ROOT / "outputs" / "dilution_robustness_summary.md"
OUT_FIG = ROOT / "figures" / "toi3492_dilution_robustness.png"


def load_json(path):
    return json.loads(path.read_text())


def corrected_from_target_fraction(depth_ppm, rp_rs, rp_earth, rp_earth_err, target_fraction):
    depth = depth_ppm / target_fraction
    factor = 1.0 / np.sqrt(target_fraction)
    return {
        "target_fraction": float(target_fraction),
        "contamination_fraction_total_flux": float(1.0 - target_fraction),
        "contamination_ratio_vs_target": float((1.0 - target_fraction) / target_fraction),
        "depth_correction_factor": float(1.0 / target_fraction),
        "radius_correction_factor": float(factor),
        "corrected_depth_ppm": float(depth),
        "corrected_rp_rs": float(rp_rs * factor),
        "corrected_rp_earth": float(rp_earth * factor),
        "corrected_rp_earth_err": float(rp_earth_err * factor),
    }


def corrected_from_ratio(depth_ppm, rp_rs, rp_earth, rp_earth_err, ratio_vs_target):
    target_fraction = 1.0 / (1.0 + ratio_vs_target)
    return corrected_from_target_fraction(depth_ppm, rp_rs, rp_earth, rp_earth_err, target_fraction)


def main():
    config = load_json(CONFIG_PATH)
    archive = load_json(ARCHIVE_PATH)
    gaia = load_json(GAIA_PATH)

    transit = config["transit"]
    depth_ppm = float(transit["depth_ppm"])
    rp_rs = float(transit["rp_rs"])
    rp_earth = float(transit["rp_earth"])
    rp_earth_err = float(transit["rp_earth_err"])

    rows = []
    for item in archive["tess_spoc_contamination"].get("crowdsap_per_sector", []):
        corrected = corrected_from_target_fraction(depth_ppm, rp_rs, rp_earth, rp_earth_err, float(item["CROWDSAP"]))
        rows.append(
            {
                "source": "SPOC_CROWDSAP",
                "label": f"Sector {int(item['sector'])}",
                "sector": int(item["sector"]),
                "CROWDSAP": float(item["CROWDSAP"]),
                "FLFRCSAP": float(item["FLFRCSAP"]) if item.get("FLFRCSAP") is not None else np.nan,
                **corrected,
            }
        )

    crowdsap_values = [float(x["CROWDSAP"]) for x in archive["tess_spoc_contamination"].get("crowdsap_per_sector", [])]
    scenarios = []
    if crowdsap_values:
        scenarios.extend(
            [
                ("SPOC CROWDSAP mean", corrected_from_target_fraction(depth_ppm, rp_rs, rp_earth, rp_earth_err, float(np.mean(crowdsap_values)))),
                ("SPOC CROWDSAP minimum", corrected_from_target_fraction(depth_ppm, rp_rs, rp_earth, rp_earth_err, float(np.min(crowdsap_values)))),
                ("SPOC CROWDSAP maximum", corrected_from_target_fraction(depth_ppm, rp_rs, rp_earth, rp_earth_err, float(np.max(crowdsap_values)))),
            ]
        )

    exofop_ratio = archive["tess_spoc_contamination"].get("exofop_contamination_ratio")
    if exofop_ratio is not None:
        scenarios.append(("ExoFOP TIC contamination ratio", corrected_from_ratio(depth_ppm, rp_rs, rp_earth, rp_earth_err, float(exofop_ratio))))

    for aperture in gaia.get("aperture_flux_summary_gband", []):
        radius = float(aperture["radius_arcsec"])
        ratio = float(aperture["neighbor_flux_ratio_sum_gband"])
        scenarios.append((f"Gaia G-band neighbors within {radius:.0f} arcsec", corrected_from_ratio(depth_ppm, rp_rs, rp_earth, rp_earth_err, ratio)))

    for ratio in [0.05, 0.10, 0.25]:
        scenarios.append((f"Conservative contamination ratio {ratio:.0%} vs target", corrected_from_ratio(depth_ppm, rp_rs, rp_earth, rp_earth_err, ratio)))

    scenario_rows = []
    for label, values in scenarios:
        scenario_rows.append({"label": label, **values})

    df = pd.DataFrame(rows).sort_values("sector") if rows else pd.DataFrame()
    df.to_csv(OUT_CSV, index=False)

    scenario_df = pd.DataFrame(scenario_rows)
    scenario_df.to_json(OUT_WORST, orient="records", indent=2)

    mean_row = next((row for row in scenario_rows if row["label"] == "SPOC CROWDSAP mean"), None)
    exofop_row = next((row for row in scenario_rows if row["label"] == "ExoFOP TIC contamination ratio"), None)
    gaia_42 = next((row for row in scenario_rows if row["label"] == "Gaia G-band neighbors within 42 arcsec"), None)

    summary = {
        "source": "Dilution robustness from corrected 120 s transit parameters, SPOC CROWDSAP, ExoFOP contamination ratio, and Gaia DR3 G-band flux ratios",
        "observed": {
            "depth_ppm": depth_ppm,
            "rp_rs": rp_rs,
            "rp_earth": rp_earth,
            "rp_earth_err": rp_earth_err,
        },
        "crowdsap": {
            "n_sectors": len(crowdsap_values),
            "mean": float(np.mean(crowdsap_values)) if crowdsap_values else None,
            "min": float(np.min(crowdsap_values)) if crowdsap_values else None,
            "max": float(np.max(crowdsap_values)) if crowdsap_values else None,
        },
        "preferred_small_dilution_corrections": {
            "spoc_crowdsap_mean": mean_row,
            "exofop_tic_ratio": exofop_row,
            "gaia_42arcsec_gband": gaia_42,
        },
        "interpretation": "The nominal SPOC/ExoFOP dilution corrections change the inferred radius by about 1 percent, so the candidate remains firmly giant-planet-size. Gaia 120 arcsec is an intentionally over-wide G-band scenario and should not be treated as the adopted TESS aperture correction.",
        "outputs": {
            "sector_csv": OUT_CSV.name,
            "scenario_json": OUT_WORST.name,
            "figure": str(OUT_FIG.relative_to(ROOT)),
        },
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2))

    lines = []
    lines.append("# Dilution Robustness Summary")
    lines.append("")
    lines.append(f"Observed corrected 120 s depth: {depth_ppm:.1f} ppm")
    lines.append(f"Observed candidate radius: {rp_earth:.2f} +/- {rp_earth_err:.2f} Rearth")
    lines.append("")
    if mean_row:
        lines.append(
            "SPOC CROWDSAP mean correction: "
            f"target fraction={mean_row['target_fraction']:.4f}, "
            f"depth={mean_row['corrected_depth_ppm']:.1f} ppm, "
            f"Rp={mean_row['corrected_rp_earth']:.2f} Rearth."
        )
    if exofop_row:
        lines.append(
            "ExoFOP contamination-ratio correction: "
            f"depth={exofop_row['corrected_depth_ppm']:.1f} ppm, "
            f"Rp={exofop_row['corrected_rp_earth']:.2f} Rearth."
        )
    if gaia_42:
        lines.append(
            "Gaia 42 arcsec G-band summed-flux scenario: "
            f"depth={gaia_42['corrected_depth_ppm']:.1f} ppm, "
            f"Rp={gaia_42['corrected_rp_earth']:.2f} Rearth."
        )
    lines.append("")
    lines.append("The nominal correction is small and does not affect the giant-planet-size interpretation. This does not replace high-resolution imaging or a TESS-band PRF aperture model.")
    OUT_MD.write_text("\n".join(lines) + "\n")

    ratios = np.linspace(0.0, 0.25, 300)
    radius = rp_earth * np.sqrt(1.0 + ratios)
    depth = depth_ppm * (1.0 + ratios)
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(ratios * 100.0, radius, color="tab:blue", label="Corrected radius")
    ax1.axhline(rp_earth, color="tab:blue", linestyle=":", alpha=0.7)
    ax1.set_xlabel("Contaminating flux / target flux (%)")
    ax1.set_ylabel("Rp (Rearth)", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(ratios * 100.0, depth, color="tab:orange", label="Corrected depth")
    ax2.axhline(depth_ppm, color="tab:orange", linestyle=":", alpha=0.7)
    ax2.set_ylabel("Depth (ppm)", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    markers = []
    if mean_row:
        markers.append((mean_row["contamination_ratio_vs_target"], "CROWDSAP mean"))
    if exofop_row:
        markers.append((exofop_row["contamination_ratio_vs_target"], "ExoFOP"))
    if gaia_42:
        markers.append((gaia_42["contamination_ratio_vs_target"], "Gaia 42 arcsec"))
    for ratio, label in markers:
        ax1.axvline(ratio * 100.0, color="gray", linestyle="--", alpha=0.6)
        ax1.text(ratio * 100.0, ax1.get_ylim()[1], label, rotation=90, va="top", ha="right", fontsize=8)

    ax1.set_title("TOI-3492.01 dilution robustness")
    ax1.grid(alpha=0.25)
    plt.tight_layout()
    fig.savefig(OUT_FIG, dpi=180)
    plt.close(fig)

    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_WORST}")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_FIG}")
    if mean_row:
        print(f"CROWDSAP mean corrected Rp={mean_row['corrected_rp_earth']:.2f} Rearth")


if __name__ == "__main__":
    main()
