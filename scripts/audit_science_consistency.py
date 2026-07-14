"""Offline, assertion-based scientific release audit."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from science import kepler_a_au, kepler_a_rs


ROOT = Path(__file__).resolve().parent.parent


def load_json(relative):
    return json.loads((ROOT / relative).read_text())


def main():
    config = load_json("data/config_corrected_120s.json")
    transit = config["transit_corrected_120s"]
    stellar = config["stellar"]
    reference = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    assert len(reference) == 102502
    assert set(reference["sector"]) == {37, 63, 64, 90, 99, 100}
    assert reference[["time", "flux", "flux_err"]].notna().all().all()

    chain = np.load(ROOT / "data" / "toi3492_chains_120s_corrected.npy")
    raw = np.load(ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy")
    diagnostics = load_json("outputs/mcmc_diagnostics_120s_corrected.json")
    assert tuple(chain.shape) == tuple(diagnostics["flat_chain_shape"])
    assert tuple(raw.shape) == tuple(diagnostics["raw_chain_shape"])
    assert diagnostics["autocorr_reliable_50tau_rule"]
    assert not transit["stellar_density_prior_used"]

    expected_a = float(kepler_a_au(transit["period"], stellar["m_star"]))
    expected_a_rs = float(
        kepler_a_rs(transit["period"], stellar["m_star"], stellar["r_star"])
    )
    assert np.isclose(transit["a_au"], expected_a, rtol=0.01)
    assert np.isclose(
        transit["derived_posterior"]["catalog_a_rs"]["median"],
        expected_a_rs,
        rtol=0.01,
    )

    vetting = load_json("outputs/statistical_validation_120s.json")
    assert vetting["formal_fpp"] is None
    assert not vetting["statistical_validation_claim_supported"]

    cadence = load_json("outputs/cadence_independent_depth_check.json")
    gaia_stellar = load_json("outputs/gaia_stellar_crosscheck.json")
    localization = load_json("outputs/tess_source_localization_120s.json")
    robust_120 = load_json("outputs/transit_fit_robust_120s.json")
    robust_20 = load_json("outputs/transit_fit_robust_20s.json")
    phase = load_json("outputs/phase_curve_search_120s.json")
    sed = load_json("outputs/stellar_sed_posterior.json")
    dilution = load_json("outputs/dilution_corrected_transit_params.json")
    source_specific = load_json("outputs/source_specific_aperture_check.json")
    release_status = load_json("outputs/release_status.json")
    window = load_json("outputs/transit_window_comparison.json")
    math_audit = load_json("outputs/manuscript_math_audit.json")
    sector_stats = load_json("outputs/sector_depth_statistics.json")
    tic = load_json("data/tic_v8_target.json")
    assert cadence["n_points_20s"] == 310533
    assert abs(cadence["delta_20s_minus_matched_120s_robust_sigma_formal"]) < 3
    assert np.isclose(
        gaia_stellar["derived_from_flame_medians"]["expected_circular_a_rs"],
        7.9558813800220705,
    )
    assert localization["summary"]["n_sectors"] == 6
    assert robust_120["status"] == "robustness_fit_not_adopted"
    assert robust_20["status"] == "robustness_fit_not_adopted"
    assert not robust_120["mcmc"]["reliable_50tau_rule"]
    assert not robust_20["mcmc"]["reliable_50tau_rule"]
    assert phase["status"] == "unphysical_phase_harmonic_detected_systematics_limited"
    assert phase["secondary_phase_scan_performed"] is False
    assert sed["status"] == "approximate_sed_radius_crosscheck_not_isochrone_posterior"
    assert not dilution["adopted_dilution_treatment"]["additional_correction_applied"]
    assert source_specific["status"] == "aperture_geometry_check_not_formal_prf_localization"
    assert release_status["strongest_supported_gate"] == "descriptive_candidate_preprint"
    assert not release_status["gates"]["central_density_or_eccentricity_claim_ready"]
    assert not release_status["gates"]["statistical_validation_ready"]
    assert not release_status["gates"]["planet_confirmation_ready"]
    assert window["status"] == "window_definition_sensitivity_not_adopted"
    assert window["adopted_window"]["half_width_hours"] == 13.0
    assert window["adopted_window"]["total_width_hours"] == 26.0
    assert window["alternative_window"]["mcmc"]["reliable_50tau_rule"]
    assert math_audit["status"] == "PASS"
    assert np.isclose(sector_stats["chi_square"], 29.849938162158445)
    assert tic["stellar"]["metallicity_dex"] is None
    assert "Assumed solar metallicity" in stellar["feh_source"]

    print("SCIENTIFIC CONSISTENCY AND CLAIM-BOUNDARY AUDIT: PASS")
    print(f"Reference rows: {len(reference)}")
    print(f"Posterior samples: {len(chain)}")
    print(f"Rp/Rs: {transit['rp_rs']:.6f} +/- {transit['rp_rs_err']:.6f}")
    print(f"Circular a/Rs: {transit['a_rs']:.3f} +/- {transit['a_rs_err']:.3f}")
    print(f"Keplerian a: {transit['a_au']:.5f} AU")
    print(
        "Circular reference/catalog density ratio: "
        f"{transit['derived_posterior']['photometric_density_solar']['median'] / transit['derived_posterior']['catalog_density_solar']['median']:.2f} (model conditional)"
    )
    print("Formal FPP: not reported")
    print(
        "20s vs matched 120s robust depth: "
        f"{cadence['delta_20s_minus_matched_120s_robust_sigma_formal']:.2f} sigma"
    )
    print(
        "Gaia FLAME expected circular a/Rs: "
        f"{gaia_stellar['derived_from_flame_medians']['expected_circular_a_rs']:.3f}"
    )
    print("Native-cadence chains: diagnostic and unconverged")
    print("Secondary eclipse coverage: phase 0.5 only; no eccentric-phase scan")
    print("Strongest supported gate: descriptive candidate preprint")
    print(
        "Total-width 13h window shift in Rp/Rs: "
        f"{window['alternative_minus_adopted']['rp_rs']['in_adopted_max_68pct_half_widths']:.2f} adopted posterior half-widths"
    )
    print(
        "Manuscript math inventory: "
        f"{math_audit['inventory']['math_expression_count']} expressions, "
        f"{math_audit['inventory']['numeric_token_count']} numeric tokens"
    )


if __name__ == "__main__":
    main()
