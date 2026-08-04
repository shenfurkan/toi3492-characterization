import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = (13, 16, 20, 26, 32)
DEGREES = (0, 1, 2)
PARAMETERS = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")
EXPECTED_COUNTS = {13: 6081, 16: 7430, 20: 9273, 26: 11959, 32: 14640}


def load_json(relative_path):
    with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def duration_hours(draws, period_days):
    rp = draws[:, 0]
    a_rs = draws[:, 1]
    impact = draws[:, 2]
    sin_i = np.sqrt(1.0 - (impact / a_rs) ** 2)
    numerator = np.sqrt((1.0 + rp) ** 2 - impact**2)
    return period_days * 24.0 / math.pi * np.arcsin(numerator / (a_rs * sin_i))


@pytest.fixture(scope="module")
def report():
    return load_json("outputs/faz5_window_polynomial_grid.json")


@pytest.fixture(scope="module")
def prereg():
    return load_json("data/faz5_preregistered_grid.json")


@pytest.fixture(scope="module")
def grid():
    return pd.read_csv(ROOT / "outputs" / "faz5_model_grid.csv")


@pytest.fixture(scope="module")
def blocks():
    return pd.read_csv(ROOT / "outputs" / "faz5_block_scores.csv")


def test_preregistration_input_provenance_and_failure_boundary(report, prereg):
    assert report["phase"] == 5
    assert report["status"] == "FAIL"
    assert report["input_policy"] == {
        "active_phase4_products_only": True,
        "legacy_zip_inspected": False,
        "network_used": False,
        "git_used": False,
        "phase6_started": False,
    }
    assert prereg["frozen_before_first_phase5_fit"] is True
    assert prereg["grid"]["total_window_hours"] == list(WINDOWS)
    assert prereg["grid"]["event_polynomial_degrees"] == list(DEGREES)
    assert prereg["grid"]["cell_count"] == 15
    assert prereg["inputs"]["reference_branch"] == "pdcsap"
    assert prereg["systematic_handoff"]["dependent_reduction_likelihoods_multiplied"] is False
    assert report["preregistration"]["sha256"] == sha256_file(
        ROOT / report["preregistration"]["relative_path"]
    )
    phase4_input = report["inputs"]["phase4_long_table"]
    assert phase4_input["sha256"] == prereg["inputs"]["phase4_long_table_sha256"]
    assert phase4_input["sha256"] == sha256_file(ROOT / phase4_input["relative_path"])
    assert all(report["inputs"]["input_validation"].values())
    assert len(report["inputs"]["used_events"]) == 16
    assert report["model"]["reductions_combined_as_independent_likelihoods"] is False
    assert report["model"]["posterior_approximation"]["mcmc_used"] is False


def test_complete_native_cadence_grid_and_laplace_outputs(report, grid):
    expected_ids = {f"W{window:02d}_P{degree}" for window in WINDOWS for degree in DEGREES}
    assert len(report["cells"]) == len(grid) == 15
    assert {item["cell_id"] for item in report["cells"]} == expected_ids
    assert set(grid["cell_id"]) == expected_ids
    for cell in report["cells"]:
        assert cell["n_points"] == EXPECTED_COUNTS[cell["total_window_hours"]]
        assert cell["n_events"] == 16
        assert sum(cell["n_points_by_sector"].values()) == cell["n_points"]
        assert cell["optimizer"]["multiple_start_count"] == 5
        assert cell["optimizer"]["selected_success"] is True
        assert len(cell["optimizer"]["attempts"]) == 5
        assert sum(item["success"] for item in cell["optimizer"]["attempts"]) >= 4
        objectives = np.asarray(
            [item["negative_log_marginal_posterior"] for item in cell["optimizer"]["attempts"]]
        )
        assert np.ptp(objectives) < 1e-3
        baseline = cell["baseline_marginalization"]
        assert baseline["event_specific"] is True
        assert baseline["minimum_design_rank"] == baseline["required_design_rank"]
        laplace = cell["laplace"]
        assert laplace["valid"] is True
        covariance = np.asarray(laplace["covariance"])
        assert covariance.shape == (3, 3)
        assert np.all(np.linalg.eigvalsh(covariance) > 0)
        assert any(item["valid"] for item in laplace["hessian_attempts"])
        for name in PARAMETERS:
            summary = cell["posterior"][name]
            assert np.isfinite(list(summary.values())).all()
            assert summary["p16"] < summary["median"] < summary["p84"]


def test_geometry_draw_artifact_is_physical_and_reproducible(report):
    artifact = report["artifacts"]["geometry_draws_npz"]
    path = ROOT / artifact["relative_path"]
    assert path.stat().st_size == artifact["size_bytes"]
    assert sha256_file(path) == artifact["sha256"]
    with np.load(path, allow_pickle=False) as payload:
        cell_ids = payload["cell_ids"]
        names = payload["parameter_names"]
        draws = payload["draws"]
    assert list(names) == list(PARAMETERS)
    assert draws.shape == (15, 8192, 4)
    assert len(set(cell_ids)) == 15
    assert np.all(np.isfinite(draws))
    assert np.all((draws[:, :, 0] > 0.03) & (draws[:, :, 0] < 0.09))
    assert np.all((draws[:, :, 1] > 5.0) & (draws[:, :, 1] < 16.0))
    assert np.all((draws[:, :, 2] > 0.0) & (draws[:, :, 2] < 0.98))
    recomputed = duration_hours(draws[:, ::127, :3].reshape(-1, 3), 9.2224171)
    stored = draws[:, ::127, 3].reshape(-1)
    assert np.allclose(recomputed, stored, rtol=0, atol=2e-14)


def test_common_blocked_support_and_no_training_leakage(report, blocks):
    assert len(blocks) == 15 * 30
    assert report["blocked_predictive_design"]["excluded_event_ids"] == ["S100-E193"]
    assert report["blocked_predictive_design"]["same_score_cadences_for_all_cells"] is True
    grouped = blocks.groupby("cell_id")
    assert set(grouped.size()) == {30}
    assert set(grouped["validation_cadence_count"].sum()) == {2236}
    assert set(grouped["event_id"].nunique()) == {15}
    assert set(grouped["sector"].nunique()) == {6}
    assert set(blocks["side"]) == {"left", "right"}
    assert "S100-E193" not in set(blocks["event_id"])
    assert np.all(blocks["validation_cadence_count"] >= 40)
    assert np.all(blocks["held_event_opposite_side_training_count"] >= 40)
    for column in (
        "transit_cadences_in_training",
        "held_side_cadences_in_training",
        "training_validation_overlap_count",
    ):
        assert np.all(blocks[column] == 0)
    support = blocks.pivot_table(
        index=["event_id", "side"],
        columns="cell_id",
        values="validation_cadence_count",
    )
    assert not support.isna().any().any()
    assert np.all(support.nunique(axis=1) == 1)


def test_recompute_elpd_pairwise_se_selection_and_equal_weights(report, grid, blocks):
    comparison = report["model_comparison"]
    totals = blocks.groupby("cell_id")["elpd"].sum()
    best = totals.idxmax()
    assert best == comparison["best_raw_elpd_cell"] == "W16_P1"
    assert totals[best] == pytest.approx(comparison["best_raw_elpd"])
    assert np.allclose(
        grid.set_index("cell_id").loc[totals.index, "elpd"], totals.loc[totals.index]
    )
    stored = {item["cell_id"]: item for item in comparison["pairwise_against_best"]}
    retained = []
    for identifier in totals.index:
        if identifier == best:
            retained.append(identifier)
            continue
        selected = blocks.loc[blocks["cell_id"].isin([best, identifier])]
        event = selected.groupby(["cell_id", "event_id"])["elpd"].sum().unstack(0)
        event_delta = event[best] - event[identifier]
        sector = selected.groupby(["cell_id", "sector"])["elpd"].sum().unstack(0)
        sector_delta = sector[best] - sector[identifier]
        se_event = math.sqrt(len(event_delta) * np.var(event_delta, ddof=1))
        se_sector = math.sqrt(len(sector_delta) * np.var(sector_delta, ddof=1))
        delta = float(event_delta.sum())
        adopted = max(se_event, se_sector)
        assert stored[identifier]["delta_elpd_best_minus_cell"] == pytest.approx(delta)
        assert stored[identifier]["event_cluster_standard_error"] == pytest.approx(se_event)
        assert stored[identifier]["sector_cluster_standard_error"] == pytest.approx(se_sector)
        assert stored[identifier]["adopted_standard_error"] == pytest.approx(adopted)
        assert stored[identifier]["strictly_distinguished"] is (delta > 2.0 * adopted)
        if not delta > 2.0 * adopted:
            retained.append(identifier)
    assert set(retained) == set(comparison["retained_cell_ids"])
    assert len(retained) == comparison["retained_model_count"] == 11
    assert comparison["single_model_selected"] is False
    assert set(comparison["weights"]) == set(retained)
    assert all(
        value == pytest.approx(1.0 / 11.0)
        for value in comparison["weights"].values()
    )
    assert sum(comparison["weights"].values()) == pytest.approx(1.0)


def test_failure_is_only_the_preregistered_median_coverage_gate(report):
    checks = report["gate"]["checks"]
    failed = {name for name, value in checks.items() if not value}
    assert failed == {"retained_cell_medians_inside_final_68pct"}
    assert report["gate"]["status"] == "FAIL"
    assert report["gate"]["gate_pass"] is False
    assert report["gate"]["phase6_may_begin"] is False
    median_checks = report["model_averaged_geometry"]["retained_cell_median_checks"]
    failures = {
        (cell_id, parameter)
        for cell_id, values in median_checks.items()
        for parameter, passed in values.items()
        if not passed
    }
    assert failures == {("W26_P1", "rp_rs"), ("W26_P1", "t14_hours")}
    cells = {item["cell_id"]: item for item in report["cells"]}
    final = report["model_averaged_geometry"][
        "cumulative_with_phase4_reduction_systematic"
    ]
    assert cells["W26_P1"]["posterior"]["rp_rs"]["median"] < final["rp_rs"]["cumulative_p16"]
    assert cells["W26_P1"]["posterior"]["t14_hours"]["median"] < final["t14_hours"]["cumulative_p16"]
    assert all(
        median_checks[cell_id][parameter]
        for cell_id in median_checks
        for parameter in PARAMETERS
        if (cell_id, parameter) not in failures
    )
