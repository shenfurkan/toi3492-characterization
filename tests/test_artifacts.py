import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_json(relative):
    return json.loads((ROOT / relative).read_text())


def test_reference_lightcurve_integrity():
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    assert list(data.columns) == ["time", "flux", "flux_err", "sector", "exptime"]
    assert len(data) == 102502
    assert data.notna().all().all()
    assert (data["flux_err"] > 0).all()
    assert data["time"].is_monotonic_increasing
    assert set(data["sector"]) == {37, 63, 64, 90, 99, 100}
    assert set(data["exptime"]) == {120.0}


def test_chain_and_config_are_one_run():
    config = load_json("data/config_corrected_120s.json")
    diagnostics = load_json("outputs/mcmc_diagnostics_120s_corrected.json")
    raw = np.load(ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy", allow_pickle=False)
    flat = np.load(ROOT / "data" / "toi3492_chains_120s_corrected.npy", allow_pickle=False)
    discard = diagnostics["flat_discard_steps"]
    assert tuple(raw.shape) == tuple(diagnostics["raw_chain_shape"])
    assert tuple(flat.shape) == tuple(diagnostics["flat_chain_shape"])
    assert np.array_equal(flat, raw[discard:].reshape(-1, raw.shape[-1]))
    medians = np.median(flat, axis=0)
    transit = config["transit"]
    assert np.allclose(
        medians[:3],
        [transit["rp_rs"], transit["a_rs"], transit["impact_parameter"]],
        atol=1e-12,
    )
    assert config["transit_corrected_120s"]["stellar_density_prior_used"] is False
    assert diagnostics["autocorr_reliable_50tau_rule"] is True


def test_vetting_is_not_misrepresented_as_validation():
    summary = load_json("outputs/statistical_validation_120s.json")
    assert summary["formal_fpp"] is None
    assert summary["formal_fpp_available"] is False
    assert summary["statistical_validation_claim_supported"] is False
    assert summary["gaia_42arcsec"]["n_full_eclipse_mimics"] == 0


def test_required_machine_readable_outputs_exist():
    paths = [
        "data/official_toi_metadata.json",
        "outputs/mcmc_diagnostics_120s_corrected.json",
        "outputs/alias_120s_results.json",
        "outputs/spectroscopic_archives.json",
        "outputs/false_positive_tests_120s.json",
        "outputs/gaia_contamination_check.json",
        "outputs/gaia_stellar_crosscheck.json",
        "outputs/gaia_dr3_neighbors.csv",
        "outputs/spoc_dv_summary.json",
        "outputs/spoc_vs_local_comparison.json",
        "outputs/statistical_validation_120s.json",
        "outputs/transit_fit_120s_eccentric.json",
        "outputs/transit_stability_checks.json",
        "outputs/toi3492_120s_sector_depths.csv",
        "outputs/cadence_independent_depth_check.json",
        "outputs/toi3492_20s_sector_depths.csv",
        "outputs/tess_source_localization_120s.json",
        "outputs/transit_fit_robust_120s.json",
        "outputs/transit_fit_robust_20s.json",
        "outputs/robust_density_comparison.json",
        "outputs/phase_curve_search_120s.json",
        "outputs/source_specific_aperture_check.json",
        "outputs/stellar_sed_posterior.json",
        "outputs/dilution_corrected_transit_params.json",
        "outputs/release_status.json",
        "data/stellar_photometry.json",
        "EXOPLANET_RELEASE_ROADMAP.md",
        "toi3492_characterization.tex",
        "toi3492_characterization.pdf",
    ]
    assert all((ROOT / path).is_file() for path in paths)


def test_new_public_data_crosschecks():
    cadence = load_json("outputs/cadence_independent_depth_check.json")
    gaia = load_json("outputs/gaia_stellar_crosscheck.json")
    localization = load_json("outputs/tess_source_localization_120s.json")
    assert cadence["n_points_20s"] == 310533
    assert abs(cadence["delta_20s_minus_matched_120s_robust_sigma_formal"]) < 3
    assert np.isclose(
        gaia["derived_from_flame_medians"]["stellar_density_solar"],
        0.07944416562519523,
    )
    assert np.isclose(
        gaia["derived_from_flame_medians"]["expected_circular_a_rs"],
        7.9558813800220705,
    )
    assert localization["summary"]["n_sectors"] == 6
    assert localization["summary"]["max_difference_centroid_offset_pix"] < 1.1


def test_new_robustness_outputs_are_not_overclaimed():
    robust_120 = load_json("outputs/transit_fit_robust_120s.json")
    robust_20 = load_json("outputs/transit_fit_robust_20s.json")
    phase = load_json("outputs/phase_curve_search_120s.json")
    dilution = load_json("outputs/dilution_corrected_transit_params.json")
    source = load_json("outputs/source_specific_aperture_check.json")
    release = load_json("outputs/release_status.json")
    assert robust_120["status"] == "robustness_fit_not_adopted"
    assert robust_20["status"] == "robustness_fit_not_adopted"
    assert robust_120["mcmc"]["reliable_50tau_rule"] is False
    assert robust_20["mcmc"]["reliable_50tau_rule"] is False
    assert phase["status"] == "unphysical_phase_harmonic_detected_systematics_limited"
    assert phase["secondary_phase_scan_performed"] is False
    assert dilution["adopted_dilution_treatment"]["additional_correction_applied"] is False
    assert source["nearest_mimic_candidate_summary"]["inside_pipeline_aperture_sector_count"] == 0
    assert release["strongest_supported_gate"] == "descriptive_candidate_preprint"
    assert release["gates"]["central_density_or_eccentricity_claim_ready"] is False
    assert release["gates"]["statistical_validation_ready"] is False
    assert release["gates"]["planet_confirmation_ready"] is False
    config = load_json("data/config_corrected_120s.json")
    assert config["pipeline_status"]["ttv_analysis"] is False
    assert config["pipeline_status"]["stellar_activity"] is False


def test_release_hash_manifest():
    manifest = load_json("provenance/SHA256SUMS.json")
    assert "scripts/transit_model_120s_corrected.py" in manifest
    assert "scripts/asteroseismic_search.py" in manifest
    assert "tests/test_science.py" in manifest
    assert "tests/test_asteroseismology.py" in manifest
    assert "EXOPLANET_RELEASE_ROADMAP.md" in manifest
    assert "outputs/gaia_dr3_neighbors.csv" in manifest
    assert "outputs/release_status.json" in manifest
    assert "outputs/alias_120s_results.json" in manifest
    assert "outputs/spectroscopic_archives.json" in manifest
    assert "provenance/environment.json" in manifest
    for relative, expected in manifest.items():
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert digest == expected, relative
