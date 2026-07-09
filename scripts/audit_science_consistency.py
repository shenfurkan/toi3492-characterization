"""Comprehensive numerical audit for TOI-3492.01.

Independently recomputes all key physical parameters from local CSV/NPY/JSON
outputs and compares them against the config_corrected_120s.json transit
solution.  Produces a terminal report covering:

    * Reference light curve integrity (rows, sectors, finite fluxes)
    * MCMC chain shapes and median parameter consistency
    * Derived quantities: depth, Rp, a, luminosity, incident flux, Teq
    * Kepler's Third Law consistency check (a/Rs tension)
    * Sector-by-sector robust depths and weighted-mean statistics
    * Odd/even and secondary-eclipse false-positive diagnostics
    * Simplified Morton-style FPP
    * TRICERATOPS screening summary
    * Gaia DR3 neighbor census by aperture
    * SPOC DV machine-readable and dashboard consistency
    * TTV analysis, difference-image centroids, dilution corrections

Run from the project root::

    python scripts/audit_science_consistency.py

This script requires no network access; all inputs are local.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path):
    """Read a JSON file and return its parsed contents."""
    return json.loads(path.read_text())


def print_kv(key, value):
    """Print a key-value pair for the audit report."""
    print(f"{key}: {value}")


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def main():
    # ---- Load the adopted transit solution ---------------------------------
    config = load_json(ROOT / "data" / "config_corrected_120s.json")
    stellar = config["stellar"]
    transit = config["transit_corrected_120s"]

    print("NUMERICAL AUDIT")
    print("=" * 60)

    # ---- Reference light curve ---------------------------------------------
    # The reference CSV is the foundation of all downstream analysis.
    # It must have 102 502 rows covering six 120-s sectors.
    ref = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    print_kv("reference_rows", len(ref))
    print_kv("finite_flux_rows", int(np.isfinite(ref["flux"]).sum()))
    print_kv("sectors", sorted(int(x) for x in ref["sector"].unique()))

    # ---- MCMC chains -------------------------------------------------------
    # Flat chain:  (n_samples, 4)   Raw chain: (n_steps, n_walkers, 4)
    # Parameters:  rp_rs, a_rs, impact_parameter, baseline
    chain = np.load(ROOT / "data" / "toi3492_chains_120s_corrected.npy")
    raw = np.load(ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy")
    med = np.median(chain, axis=0)
    print_kv("flat_chain_shape", tuple(chain.shape))
    print_kv("raw_chain_shape", tuple(raw.shape))
    print_kv("chain_median_rp_ar_b_baseline", [float(x) for x in med])
    print_kv(
        "config_rp_ar_b",
        [transit["rp_rs"], transit["a_rs"], transit["impact_parameter"]],
    )

    # ---- Derived quantities from the transit fit ---------------------------
    rp = transit["rp_rs"]
    rp_err = transit["rp_rs_err"]
    r_star = stellar["r_star"]

    # Model transit depth:  depth = (Rp / Rs)^2  (fractional)
    depth = rp ** 2 * 1e6  # ppm

    # Physical radius:  R_p = (Rp/Rs) * R_s * (R_sun / R_earth)
    # R_sun / R_earth = 109.1
    rp_re = rp * r_star * 109.1  # R_earth
    rp_re_err = rp_re * math.sqrt(
        (rp_err / rp) ** 2 + (stellar["r_star_err"] / r_star) ** 2
    )

    # Orbital semi-major axis:  a = (a/Rs) * R_s * (R_sun / AU)
    R_SUN_AU = 0.00465047
    a_au = transit["a_rs"] * r_star * R_SUN_AU

    # Luminosity (Stefan-Boltzmann, solar units):
    #   L = (R/R_sun)^2 * (Teff / 5772)^4
    lum = r_star ** 2 * (stellar["teff"] / 5772.0) ** 4

    # Incident flux (Earth units):
    #   S = L / a^2
    insol = lum / a_au ** 2

    # Equilibrium temperature (zero-albedo, full redistribution):
    #   T_eq = Teff * sqrt(R_sun / (2 a))
    teq = stellar["teff"] * math.sqrt(r_star * R_SUN_AU / (2 * a_au))

    print_kv("derived_depth_ppm_vs_config", [depth, transit["depth_ppm"]])
    print_kv("derived_rp_re_vs_config", [rp_re, transit["rp_earth"]])
    print_kv("derived_rp_re_err_vs_config", [rp_re_err, transit["rp_earth_err"]])
    print_kv("derived_a_lum_insol_teq", [a_au, lum, insol, teq])

    # ---- Kepler's Third Law consistency (a/Rs tension) ---------------------
    # Gravitational constant in (R_sun^3) / (M_sun * day^2)
    G_MSUN = 2942.2062

    # Predicted a/Rs from Kepler III for a circular orbit:
    #   a/Rs = (G M P^2 / (4 pi^2))^(1/3) / R
    ar_pred = (
        G_MSUN * stellar["m_star"] * transit["period"] ** 2 / (4 * math.pi ** 2)
    ) ** (1 / 3) / r_star

    # Uncertainty on the Kepler prediction (propagated from rho_star_err)
    ar_sigma = max(
        ar_pred * stellar["rho_star_err"] / (3 * stellar["rho_star"]), 0.5
    )

    tension = abs(transit["a_rs"] - ar_pred) / math.sqrt(
        transit["a_rs_err"] ** 2 + ar_sigma ** 2
    )

    print_kv("kepler_a_rs_sigma_tension", [ar_pred, ar_sigma, tension])

    # Stellar density ratio implied by the free fit:
    #   rho_free / rho_TIC = (a/Rs_free / a/Rs_TIC)^3
    print_kv(
        "density_ratio_free_to_tic", (transit["a_rs"] / ar_pred) ** 3
    )

    # ---- Sector depths ------------------------------------------------------
    sector = (
        pd.read_csv(ROOT / "outputs" / "toi3492_120s_sector_depths.csv")
        .sort_values("sector")
    )
    print("sector_depths:")
    for _, row in sector.iterrows():
        print(
            f"  S{int(row['sector'])}: "
            f"{row['depth_ppm']:.1f} +/- {row['depth_err_ppm']:.1f} ppm "
            f"(n_in={int(row['n_in'])}, n_out={int(row['n_out'])})"
        )

    # Weighted mean and scaled error (accounts for sector-to-sector scatter)
    weights = 1.0 / sector["depth_err_ppm"].to_numpy(float) ** 2
    values = sector["depth_ppm"].to_numpy(float)
    weighted_mean = float(np.sum(weights * values) / np.sum(weights))
    formal_err = float(math.sqrt(1.0 / np.sum(weights)))

    # Reduced-chi2 style scaled error when scatter exceeds formal uncertainties
    scaled_err = formal_err * math.sqrt(
        float(np.sum(weights * (values - weighted_mean) ** 2) / (len(values) - 1))
    )

    print_kv(
        "sector_weighted_mean_formal_scaled",
        [weighted_mean, formal_err, scaled_err],
    )

    # ---- False-positive diagnostics -----------------------------------------
    fp = load_json(ROOT / "outputs" / "false_positive_tests_120s.json")
    print_kv("odd_even", fp["odd_even"])
    print_kv("secondary_eclipse", fp["secondary_eclipse"])

    # ---- Statistical validation (simplified Morton-style FPP) ---------------
    stat = load_json(ROOT / "outputs" / "statistical_validation_120s.json")
    print_kv(
        "statistical_validation",
        {
            "FPP_percent": stat["FPP_percent"],
            "aRstar_tension_sigma": stat["aRstar_tension_sigma"],
            "n_full_eclipse_mimics_42arcsec": stat["n_full_eclipse_mimics_42arcsec"],
            "caveat": stat["caveat"],
        },
    )

    # ---- TRICERATOPS screening ----------------------------------------------
    tri = load_json(ROOT / "outputs" / "triceratops_validation_120s.json")
    print_kv(
        "triceratops",
        {
            "FPP": tri["FPP"],
            "PTP": tri["scenario_probabilities"]["PTP"],
            "scenario_sum": float(
                sum(tri["scenario_probabilities"].values())
            ),
        },
    )

    # ---- Gaia DR3 neighbor census -------------------------------------------
    gaia = load_json(ROOT / "outputs" / "gaia_contamination_check.json")
    print("gaia_apertures:")
    for ap in gaia["aperture_flux_summary_gband"]:
        print(
            f"  {ap['radius_arcsec']:.0f} arcsec: n={ap['n_neighbors']}, "
            f"flux_ratio={ap['neighbor_flux_ratio_sum_gband']:.8f}"
        )
    nearest = gaia["neighbor_summary"]["nearest_neighbor"]
    print_kv(
        "gaia_nearest_sep_delta_g",
        [nearest["separation_arcsec"], nearest["delta_g_mag"]],
    )
    print_kv(
        "gaia_mimics_120arcsec_full_half",
        [
            gaia["neighbor_summary"][
                "n_neighbors_that_could_mimic_if_fully_eclipsed"
            ],
            gaia["neighbor_summary"][
                "n_neighbors_that_could_mimic_if_50pct_eclipsed"
            ],
        ],
    )

    # ---- SPOC Data Validation products --------------------------------------
    spoc = load_json(ROOT / "outputs" / "spoc_vs_local_comparison.json")
    best = spoc["spoc_dv_best_machine_readable"]
    dash = spoc["spoc_dv_best_pdf_dashboard"]
    print_kv(
        "spoc_best_machine",
        [
            best["period_days"],
            best["depth_ppm"],
            best["rp_earth"],
            best["max_mes"],
        ],
    )
    print_kv(
        "spoc_dashboard",
        [
            dash["depth_ppm_rounded"],
            dash["depth_ppm_rounded_err"],
            dash["planet_radius_rearth_rounded"],
            dash["max_mes_pdf"],
            dash["joint_offset_distance_sigma"],
        ],
    )

    # ---- TTV analysis -------------------------------------------------------
    ttv = load_json(ROOT / "outputs" / "ttv_analysis_120s.json")
    print_kv("ttv", ttv)

    # ---- First-pass TESS difference images ----------------------------------
    loc = load_json(ROOT / "outputs" / "tess_source_localization_120s.json")
    print_kv(
        "difference_image_median_max_arcsec",
        [
            loc["summary"]["median_difference_centroid_offset_arcsec"],
            loc["summary"]["max_difference_centroid_offset_arcsec"],
        ],
    )

    # ---- Dilution robustness ------------------------------------------------
    dilution = load_json(
        ROOT / "outputs" / "dilution_corrected_transit_params.json"
    )
    print_kv(
        "dilution_crowdsap_mean",
        dilution["preferred_small_dilution_corrections"]["spoc_crowdsap_mean"],
    )


if __name__ == "__main__":
    main()
