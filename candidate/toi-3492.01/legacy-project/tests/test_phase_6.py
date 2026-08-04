import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import faz6_noise_core as core
import faz6_residual_diagnostics as diagnostics
import run_faz6_joint_diagnostics as joint
import run_faz6_noise_models as phase6
import run_faz6r as remediation


def load_json(relative_path):
    with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def protocol():
    return load_json("data/faz6_preregistered_kernels.json")


def synthetic_sector(sector, seed=0, n=80, degree=1):
    rng = np.random.default_rng(seed + sector)
    time = np.arange(n, dtype=np.float64) * (2.0 / 1440.0) + sector
    x = np.linspace(-0.05, 0.05, n, dtype=np.float64)
    design = np.column_stack([x**power for power in range(degree + 1)]).astype(
        np.float64
    )
    error = np.full(n, 4e-4, dtype=np.float64)
    flux = design @ np.array([1e-4, -3e-4]) + rng.normal(0.0, error)
    return core.SectorData(
        sector=sector,
        time=time,
        flux=np.asarray(flux, dtype=np.float64),
        flux_err=error,
        baseline_matrix=design,
    )


def test_phase6_protocol_and_frozen_input_contract(protocol):
    assert protocol["protocol_revision"] == 1
    assert protocol["revision_before_any_kernel_fit"] is True
    assert protocol["disclosure"]["phase6_kernel_results_observed_before_freeze"] is False
    assert protocol["inputs"]["common_validation_keys"]["row_count"] == 2233
    assert protocol["branch_contract"]["model_count"] == 24
    assert set(protocol["kernel_family"]) == set(core.KERNEL_IDS)
    checks, report = phase6.verify_upstream(protocol)
    assert all(checks.values())
    models, branch_checks = phase6.load_branch_contract(protocol, report)
    assert len(models) == 24
    assert all(branch_checks.values())
    assert sum(item["mask_id"] == "raw_valid" for item in models) == 11
    assert sum(item["mask_id"] == "reference_included" for item in models) == 13
    assert sum(
        item["conditional_cell_weight"]
        for item in models
        if item["mask_id"] == "raw_valid"
    ) == pytest.approx(1.0)


def test_phase6_common_validation_and_mask_data_contract(protocol):
    masks, validation, events, phase2 = phase6.load_analysis_inputs(protocol)
    assert len(masks["raw_valid"]) == 102562
    assert len(masks["reference_included"]) == 102502
    assert len(validation) == 2233
    assert validation.groupby("sector").size().to_dict() == {
        37: 300,
        63: 419,
        64: 455,
        90: 453,
        99: 303,
        100: 303,
    }
    assert len(events) == 16
    model = {
        "window_hours": 13,
        "polynomial_degree": 1,
    }
    training, held = phase6.build_model_sector_data(
        masks["reference_included"], validation, events, phase2, model
    )
    assert set(training) == set(held) == set(phase6.protocol_sectors())
    assert sum(len(item.time) for item in held.values()) == 2233
    assert all(item.time.dtype == np.float64 for item in training.values())
    assert all(item.baseline_matrix.shape[1] in (4, 6) for item in held.values())


@pytest.mark.parametrize("kernel_id", core.KERNEL_IDS[1:])
def test_celerite_kernel_amplitude_and_woodbury_match_dense(kernel_id):
    data = synthetic_sector(1, n=45)
    jitter = 1.5e-4
    amplitude = 3e-4
    timescale = 45.0
    term = core.build_kernel_term(kernel_id, amplitude, timescale)
    assert float(np.asarray(term.get_value(np.array([0.0])))[0]) == pytest.approx(
        amplitude**2, rel=2e-3
    )
    result = core.marginal_log_likelihood(
        data, kernel_id, jitter, amplitude, timescale
    )
    lag = data.time[:, None] - data.time[None, :]
    kernel = np.asarray(term.get_value(lag), dtype=float)
    covariance = (
        kernel
        + np.diag(data.flux_err**2 + jitter**2)
        + core.BASELINE_PRIOR_SIGMA**2
        * (data.baseline_matrix @ data.baseline_matrix.T)
    )
    sign, logdet = np.linalg.slogdet(covariance)
    assert sign > 0
    dense = -0.5 * (
        data.flux @ np.linalg.solve(covariance, data.flux)
        + logdet
        + len(data.time) * np.log(2.0 * np.pi)
    )
    assert result.log_likelihood == pytest.approx(dense, rel=0, abs=2e-8)


def test_white_woodbury_and_pooled_predictive_are_finite():
    data = synthetic_sector(1, n=40)
    jitter = 2e-4
    result = core.marginal_log_likelihood(data, "K0_white", jitter)
    covariance = (
        np.diag(data.flux_err**2 + jitter**2)
        + core.BASELINE_PRIOR_SIGMA**2
        * (data.baseline_matrix @ data.baseline_matrix.T)
    )
    sign, logdet = np.linalg.slogdet(covariance)
    dense = -0.5 * (
        data.flux @ np.linalg.solve(covariance, data.flux)
        + logdet
        + len(data.time) * np.log(2.0 * np.pi)
    )
    assert sign > 0
    assert result.log_likelihood == pytest.approx(dense, rel=0, abs=2e-8)
    training = tuple(synthetic_sector(sector, n=35) for sector in range(1, 6))
    fit = core.fit_pooled_map(training, "K0_white")
    held = synthetic_sector(6, n=35)
    score = core.held_sector_joint_log_predictive_density(held, fit)
    assert fit.success
    assert np.isfinite(score)


def test_residual_diagnostics_are_gap_aware_and_json_ready():
    rng = np.random.default_rng(6)
    frames = []
    for sector in phase6.protocol_sectors():
        n = 720
        time = sector * 100.0 + np.arange(n, dtype=float) * (2.0 / 1440.0)
        residual = rng.normal(0.0, 1.0, n)
        frames.append(
            pd.DataFrame(
                {
                    "time_btjd": time,
                    "cadenceno": np.arange(n, dtype=np.int64),
                    "residual": residual,
                    "sector": sector,
                }
            )
        )
    frame = pd.concat(frames, ignore_index=True)
    result = diagnostics.residual_diagnostics(frame)
    assert result["input"] == {"row_count": 4320, "sector_count": 6}
    assert result["beta"]["summary"]["all_scales_and_sectors_eligible"] is True
    assert result["beta"]["summary"]["minimum_filled_bins_per_sector"] == 3
    assert result["beta"]["summary"][
        "minimum_eligible_sectors_per_timescale"
    ] == 4
    assert result["lomb_scargle"]["summary"]["diagnostic_only"] is True
    periods = [
        row["period_minutes"]
        for row in result["lomb_scargle"]["periodogram"]
    ]
    assert min(periods) >= 20.0
    assert max(periods) <= 360.0
    json.dumps(result, allow_nan=False)


def test_phase6r_gradient_is_diagnostic_not_a_stationarity_gate():
    values = {
        "all_starts_finite": True,
        "all_starts_moved": True,
        "all_starts_improved": True,
        "objective_spread": remediation.OBJECTIVE_SPREAD_MAX,
        "unit_parameter_spread": remediation.PARAMETER_SPREAD_MAX,
        "minimum_bound_distance": remediation.BOUND_DISTANCE_MIN,
        "validator_objective_difference": remediation.VALIDATOR_OBJECTIVE_DIFFERENCE_MAX,
        "validator_unit_parameter_difference": remediation.VALIDATOR_PARAMETER_DIFFERENCE_MAX,
        "maximum_projected_gradient": 1e6,
        "maximum_gradient_step_difference": 1e6,
    }
    assert remediation.stationarity_gate(values)
    values["validator_objective_difference"] = 2.0 * remediation.VALIDATOR_OBJECTIVE_DIFFERENCE_MAX
    assert not remediation.stationarity_gate(values)


def test_predictive_mixture_uses_log_density_mixture_and_sector_only_se(protocol):
    checks, report = phase6.verify_upstream(protocol)
    models, _ = phase6.load_branch_contract(protocol, report)
    rows = []
    improvements = {
        "K0_white": 0.0,
        "K1_ou": 1.0,
        "K2_matern32": 0.0,
        "K3_sho": -1.0,
    }
    for model in models:
        branch_offset = 0.1 * model["polynomial_degree"]
        for kernel_id in core.KERNEL_IDS:
            for sector in phase6.protocol_sectors():
                rows.append(
                    {
                        "model_id": model["model_id"],
                        "kernel_id": kernel_id,
                        "held_sector": sector,
                        "valid": True,
                        "branch_log_predictive_density": -100.0
                        + branch_offset
                        + improvements[kernel_id],
                        "any_parameter_at_boundary": False,
                    }
                )
    scores = pd.DataFrame(rows)
    mixture = phase6.aggregate_mixtures(scores, models, "synthetic")
    assert len(mixture) == 24
    k1 = mixture.loc[mixture["kernel_id"] == "K1_ou"]
    k0 = mixture.loc[mixture["kernel_id"] == "K0_white"]
    assert np.allclose(
        k1["combined_log_predictive_density"].to_numpy()
        - k0["combined_log_predictive_density"].to_numpy(),
        1.0,
    )
    delta, standard_error, p_value = phase6.paired_summary(np.ones(6))
    assert delta == 6.0
    assert standard_error == 0.0
    assert p_value == 1.0 / 64.0
    comparisons = phase6.comparison_rows(mixture, scores, protocol)
    ou = next(item for item in comparisons if item["kernel_id"] == "K1_ou")
    assert ou["strict_delta_elpd_gt_2se"] is True
    assert ou["exact_sign_flip_p_at_most_0p05"] is True
    assert ou["predictive_and_physical_gates_pass"] is True


def test_validation_key_producer_verifies_and_refuses_to_clobber():
    verify = subprocess.run(
        [sys.executable, "-B", "scripts/prepare_faz6_validation.py", "--verify-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stderr
    assert "rows=2233" in verify.stdout
    no_clobber = subprocess.run(
        [sys.executable, "-B", "scripts/prepare_faz6_validation.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_clobber.returncode != 0
    assert "no-clobber" in no_clobber.stderr


def test_completed_screening_is_frozen_and_complex_kernels_are_not_promoted(protocol):
    checks, phase5b_report = phase6.verify_upstream(protocol)
    phase6.verify_existing(protocol, checks, phase5b_report)
    report = load_json("outputs/faz6_kernel_comparison.json")
    assert report["status"] == "screening_complete_final_diagnostics_pending"
    assert report["screening"]["completed_score_rows"] == 576
    assert report["screening"]["invalid_score_rows"] == 0
    assert report["screening"]["predictive_candidates_pending_joint_diagnostics"] == []
    assert report["gate"]["phase7_may_begin"] is False
    for comparison in report["screening"]["comparisons_against_k0"]:
        assert comparison["strict_delta_elpd_gt_2se"] is True
        assert comparison["exact_sign_flip_p_at_most_0p05"] is True
        assert comparison["predictive_and_physical_gates_pass"] is False


def test_joint_stage_contract_and_objective_are_valid_before_fit():
    protocol = load_json("data/faz6_joint_diagnostics_protocol.json")
    parent = load_json("data/faz6_preregistered_kernels.json")
    checks, screening_report, phase5b_report = joint.verify_inputs(protocol, parent)
    assert all(checks.values())
    assert screening_report["screening"][
        "predictive_candidates_pending_joint_diagnostics"
    ] == []
    branches, branch_checks = joint.load_branches(protocol, phase5b_report)
    assert len(branches) == 24
    assert all(branch_checks.values())
    masks, events, _, prereg = joint.load_masks_and_model(protocol, parent)
    branch = branches[0]
    model = joint.build_joint_model(
        branch, masks[branch["mask_id"]], events, prereg
    )
    parameters = np.concatenate(
        [branch["geometry_initializer"], np.array([-1.0] + [0.0] * 6)]
    )
    assert len(model.sectors) == 6
    assert len(model.parameter_names) == 10
    assert np.isfinite(model.objective(parameters))


def test_joint_v1_is_quarantined_and_v2_fails_only_stationarity():
    v1 = pd.read_csv(ROOT / "outputs" / "faz6_k0_joint_fits.csv")
    for value in v1["optimizer_attempts_json"]:
        attempts = json.loads(value)
        assert all(
            np.array_equal(np.asarray(item["initial"]), np.asarray(item["final"]))
            for item in attempts
        )
    protocol = load_json("data/faz6_joint_diagnostics_protocol_v2.json")
    parent = load_json("data/faz6_preregistered_kernels.json")
    checks, _, phase5b_report = joint.verify_inputs(protocol, parent)
    joint.verify_existing(protocol, parent, checks, phase5b_report)
    v2 = pd.read_csv(ROOT / "outputs" / "faz6_k0_joint_fits_v2.csv")
    assert len(v2) == 24
    assert np.all(v2["objective_improvement"] > 0.0)
    assert np.all(v2["parameter_movement_norm"] > 0.0)
    assert np.all(v2["multistart_objective_spread"] < 1e-3)
    assert np.all(v2["multistart_unit_parameter_spread"] < 1e-3)
    failed = set(v2.loc[~v2["valid"].astype(bool), "model_id"])
    assert failed == {"raw_valid::W20_P0", "reference_included::W32_P2"}
    for value in v2.loc[~v2["valid"].astype(bool), "optimizer_attempts_json"]:
        attempts = json.loads(value)
        assert sum(item["success"] for item in attempts) == 2
    report = load_json("outputs/faz6_final_noise_model_v2.json")
    assert report["joint_fit"]["valid_branch_count"] == 22
    assert report["gate"]["phase6_pass"] is False
    assert report["gate"]["phase7_may_begin"] is False
    assert report["residual_diagnostics"]["weighted_max_beta"] is None
