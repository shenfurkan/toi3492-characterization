import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = (13, 16, 20, 26, 32)
DEGREES = (0, 1, 2)
PARAMETERS = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")
ORIGINAL_RETAINED = {
    "W13_P0",
    "W13_P1",
    "W13_P2",
    "W16_P0",
    "W16_P1",
    "W16_P2",
    "W20_P0",
    "W20_P1",
    "W20_P2",
    "W26_P1",
    "W26_P2",
}
REFERENCE_RETAINED = ORIGINAL_RETAINED | {"W26_P0", "W32_P2"}


def load_json(relative_path):
    with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weighted_quantile(values, weights, probabilities):
    order = np.argsort(values)
    values = np.asarray(values)[order]
    weights = np.asarray(weights)[order]
    cumulative = np.cumsum(weights)
    cumulative /= cumulative[-1]
    return np.interp(probabilities, cumulative, values)


@pytest.fixture(scope="module")
def report():
    return load_json("outputs/faz5b_remediation.json")


@pytest.fixture(scope="module")
def protocol():
    return load_json("data/faz5b_preregistered_handoff.json")


@pytest.fixture(scope="module")
def alternate_report():
    return load_json("outputs/faz5b_reference_included_grid.json")


@pytest.fixture(scope="module")
def alternate_grid():
    return pd.read_csv(ROOT / "outputs" / "faz5b_reference_included_model_grid.csv")


@pytest.fixture(scope="module")
def alternate_blocks():
    return pd.read_csv(
        ROOT / "outputs" / "faz5b_reference_included_block_scores.csv"
    )


@pytest.fixture(scope="module")
def lineage():
    return pd.read_csv(ROOT / "outputs" / "faz5b_cadence_lineage.csv")


@pytest.fixture(scope="module")
def folds():
    return pd.read_csv(ROOT / "outputs" / "faz5b_fold_audit.csv")


def test_original_phase5_failure_and_source_artifacts_are_immutable(report, protocol):
    original = load_json("outputs/faz5_window_polynomial_grid.json")
    assert original["status"] == report["original_phase5_status"] == "FAIL"
    assert original["gate"]["phase6_may_begin"] is False
    assert set(original["model_comparison"]["retained_cell_ids"]) == ORIGINAL_RETAINED
    assert protocol["disclosure"]["phase5_results_already_observed"] is True
    assert protocol["disclosure"]["preliminary_cadence_mask_audit_already_observed"] is True
    assert protocol["disclosure"]["not_claimed_as_blind_preregistration"] is True
    assert report["protocol"]["sha256"] == sha256_file(
        ROOT / report["protocol"]["relative_path"]
    )
    for item in protocol["immutable_phase5"]["source_artifacts"].values():
        assert sha256_file(ROOT / item["relative_path"]) == item["sha256"]
    for item in protocol["upstream_inputs"].values():
        assert sha256_file(ROOT / item["relative_path"]) == item["sha256"]


def test_cadence_masks_and_sixty_row_lineage_are_independently_reproduced(
    report, protocol, lineage
):
    ledger = pd.read_csv(ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz")
    long_table = pd.read_csv(
        ROOT / "data" / "toi3492_faz4_reductions_120s.csv.gz",
        usecols=["sector", "cadenceno", "branch"],
    )
    raw = long_table.loc[long_table["branch"] == "pdcsap", ["sector", "cadenceno"]]
    if pd.api.types.is_bool_dtype(ledger["in_current_reference"]):
        included_mask = ledger["in_current_reference"]
    else:
        included_mask = ledger["in_current_reference"].astype(str).str.lower().eq("true")
    quality = ledger["quality"].fillna(0).to_numpy(np.int64)
    valid = (
        np.isfinite(ledger["time_btjd"])
        & np.isfinite(ledger["pdcsap_flux"])
        & np.isfinite(ledger["pdcsap_flux_err"])
        & (ledger["pdcsap_flux"] > 0)
        & (ledger["pdcsap_flux_err"] > 0)
        & ((quality & 17087) == 0)
    )
    ledger_raw = ledger.loc[valid, ["sector", "cadenceno"]]
    ledger_included = ledger.loc[valid & included_mask, ["sector", "cadenceno"]]
    raw_keys = set(map(tuple, raw.to_numpy()))
    ledger_raw_keys = set(map(tuple, ledger_raw.to_numpy()))
    included_keys = set(map(tuple, ledger_included.to_numpy()))
    lineage_keys = set(map(tuple, lineage[["sector", "cadenceno"]].to_numpy()))
    assert raw_keys == ledger_raw_keys
    assert included_keys < raw_keys
    assert lineage_keys == raw_keys - included_keys
    assert len(raw_keys) == 102562
    assert len(included_keys) == 102502
    assert len(lineage) == protocol["cadence_policies"]["expected_raw_only_count"] == 60
    assert set(lineage["exclusion_reason"]) == {"post_quality_clip_or_filter"}
    assert not lineage["in_current_reference"].any()
    expected_window_counts = {13: 8, 16: 12, 20: 16, 26: 21, 32: 23}
    assert {
        window: int(lineage[f"inside_w{window:02d}"].sum()) for window in WINDOWS
    } == expected_window_counts
    assert report["cadence_lineage"]["raw_only_inside_window_counts"] == {
        str(key): value for key, value in expected_window_counts.items()
    }
    assert all(report["cadence_lineage"]["checks"].values())


def test_reference_mask_grid_recomputes_selection_without_cherry_picking(
    report, alternate_report, alternate_grid, alternate_blocks
):
    expected_ids = {
        f"W{window:02d}_P{degree}" for window in WINDOWS for degree in DEGREES
    }
    expected_counts = {13: 6073, 16: 7418, 20: 9257, 26: 11938, 32: 14617}
    assert len(alternate_grid) == 15
    assert set(alternate_grid["cell_id"]) == expected_ids
    assert all(
        row.n_points == expected_counts[row.total_window_hours]
        for row in alternate_grid.itertuples()
    )
    totals = alternate_blocks.groupby("cell_id")["elpd"].sum()
    best = totals.idxmax()
    assert best == alternate_report["model_comparison"]["best_raw_elpd_cell"] == "W16_P1"
    retained = {best}
    stored = {
        item["cell_id"]: item
        for item in alternate_report["model_comparison"]["pairwise_against_best"]
    }
    for identifier in totals.index:
        if identifier == best:
            continue
        selected = alternate_blocks.loc[
            alternate_blocks["cell_id"].isin([best, identifier])
        ]
        event = selected.groupby(["cell_id", "event_id"])["elpd"].sum().unstack(0)
        sector = selected.groupby(["cell_id", "sector"])["elpd"].sum().unstack(0)
        event_delta = event[best] - event[identifier]
        sector_delta = sector[best] - sector[identifier]
        delta = float(event_delta.sum())
        se_event = math.sqrt(len(event_delta) * np.var(event_delta, ddof=1))
        se_sector = math.sqrt(len(sector_delta) * np.var(sector_delta, ddof=1))
        adopted = max(se_event, se_sector)
        assert stored[identifier]["delta_elpd_best_minus_cell"] == pytest.approx(delta)
        assert stored[identifier]["adopted_standard_error"] == pytest.approx(adopted)
        if not delta > 2.0 * adopted:
            retained.add(identifier)
    assert retained == REFERENCE_RETAINED
    assert set(alternate_report["model_comparison"]["retained_cell_ids"]) == retained
    assert set(report["branches"]["reference_included"]["retained_cell_ids"]) == retained
    assert alternate_report["model_comparison"]["retained_model_count"] == 13
    assert all(alternate_report["gate"].values())


def test_real_fold_key_audit_has_zero_leakage_and_common_support(
    report, folds, alternate_blocks
):
    assert len(folds) == 2 * 15 * 30
    assert set(folds.groupby("mask_id").size()) == {450}
    for column in (
        "transit_cadences_in_training",
        "held_side_cadences_in_training",
        "training_validation_overlap_count",
    ):
        assert np.all(folds[column] == 0)
        assert np.all(alternate_blocks[column] == 0)
        assert report["fold_audit"]["actual_overlap_maxima"][column] == 0
    common = folds.groupby(["mask_id", "event_id", "side"])[
        "validation_key_sha256"
    ].nunique()
    assert np.all(common == 1)
    support = folds.groupby(["mask_id", "cell_id"])[
        "validation_cadence_count"
    ].sum()
    assert set(support.loc["raw_valid"]) == {2236}
    assert set(support.loc["reference_included"]) == {2233}
    assert report["fold_audit"]["common_validation_key_hash_within_each_mask"] is True


def test_hierarchical_weights_preserve_both_masks_without_double_counting(report):
    handoff = report["handoff"]
    weights = handoff["joint_model_weights"]
    assert handoff["model_count"] == len(weights) == 24
    assert set(report["branches"]["raw_valid"]["retained_cell_ids"]) == ORIGINAL_RETAINED
    assert set(report["branches"]["reference_included"]["retained_cell_ids"]) == REFERENCE_RETAINED
    assert sum(weights.values()) == pytest.approx(1.0)
    assert handoff["mask_weight_sums"]["raw_valid"] == pytest.approx(0.5)
    assert handoff["mask_weight_sums"]["reference_included"] == pytest.approx(0.5)
    assert all(
        value == pytest.approx(0.5 / 11.0)
        for key, value in weights.items()
        if key.startswith("raw_valid::")
    )
    assert all(
        value == pytest.approx(0.5 / 13.0)
        for key, value in weights.items()
        if key.startswith("reference_included::")
    )
    assert handoff["phase5_between_cell_padding_added"] is False
    assert handoff["phase4_systematic_in_handoff_draws"] is False
    assert handoff["dependent_reduction_likelihoods_multiplied"] is False
    for summary in report["model_averaged_geometry"][
        "with_phase4_reduction_systematic_once"
    ].values():
        assert summary["phase5_between_cell_padding_added"] is False


def test_handoff_draws_reproduce_weighted_mixture_and_artifact_hashes(report):
    artifact = report["artifacts"]["handoff_draws"]
    path = ROOT / artifact["relative_path"]
    assert path.stat().st_size == artifact["size_bytes"]
    assert sha256_file(path) == artifact["sha256"]
    with np.load(path, allow_pickle=False) as payload:
        model_ids = [str(item) for item in payload["model_ids"]]
        mask_ids = np.asarray(payload["mask_ids"])
        cell_ids = np.asarray(payload["cell_ids"])
        names = [str(item) for item in payload["parameter_names"]]
        model_weights = np.asarray(payload["joint_model_weights"], dtype=float)
        draws = np.asarray(payload["draws"], dtype=float)
    assert names == list(PARAMETERS)
    assert model_ids == report["handoff"]["model_ids"]
    assert len(set(model_ids)) == 24
    assert draws.shape == (24, 8192, 4)
    assert mask_ids.shape == cell_ids.shape == model_weights.shape == (24,)
    assert all(
        model_id == f"{mask_id}::{cell_id}"
        for model_id, mask_id, cell_id in zip(model_ids, mask_ids, cell_ids)
    )
    assert np.all(np.isfinite(draws))
    assert model_weights.sum() == pytest.approx(1.0)
    source_draws = {}
    for mask_id, relative_path in (
        ("raw_valid", "data/toi3492_faz5_geometry_draws.npz"),
        (
            "reference_included",
            "data/toi3492_faz5b_reference_included_geometry_draws.npz",
        ),
    ):
        with np.load(ROOT / relative_path, allow_pickle=False) as payload:
            source_draws[mask_id] = {
                str(identifier): array
                for identifier, array in zip(payload["cell_ids"], payload["draws"])
            }
    assert all(
        np.array_equal(draw, source_draws[str(mask_id)][str(cell_id)])
        for mask_id, cell_id, draw in zip(mask_ids, cell_ids, draws)
    )
    flattened = draws.reshape(-1, 4)
    draw_weights = np.repeat(model_weights / draws.shape[1], draws.shape[1])
    stored = report["model_averaged_geometry"]["hierarchical_specification_mixture"]
    for index, name in enumerate(PARAMETERS):
        values = weighted_quantile(
            flattened[:, index], draw_weights, [0.025, 0.16, 0.50, 0.84, 0.975]
        )
        assert values == pytest.approx(
            [
                stored[name]["p025"],
                stored[name]["p16"],
                stored[name]["median"],
                stored[name]["p84"],
                stored[name]["p975"],
            ]
        )
    mean = np.sum(draw_weights[:, None] * flattened, axis=0)
    centered = flattened - mean
    covariance = (centered * draw_weights[:, None]).T @ centered
    stored_covariance = np.asarray(
        report["model_averaged_geometry"]["hierarchical_mixture_covariance"]
    )
    assert covariance == pytest.approx(stored_covariance)
    assert np.all(np.linalg.eigvalsh(stored_covariance) > 0)
    for artifact in report["artifacts"].values():
        assert sha256_file(ROOT / artifact["relative_path"]) == artifact["sha256"]


def test_phase5b_is_conditional_continuation_not_retroactive_pass(report):
    assert report["status"] == report["gate"]["status"] == "CONDITIONAL_CONTINUE"
    assert all(report["gate"]["checks"].values())
    assert report["gate"]["gate_pass"] is False
    assert report["gate"]["conditional_continue"] is True
    assert report["gate"]["phase6_may_begin"] is True
    assert report["gate"]["phase6_started"] is False
    assert report["original_phase5_status"] == "FAIL"
    assert "original preregistered Phase-5 status remains FAIL" in report["limitations"][0]


def test_phase5b_producer_verifies_frozen_outputs_and_refuses_to_clobber():
    verify = subprocess.run(
        [sys.executable, "-B", "scripts/run_faz5b_remediation.py", "--verify-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stderr
    assert "Verified outputs/faz5b_remediation.json" in verify.stdout
    no_clobber = subprocess.run(
        [sys.executable, "-B", "scripts/run_faz5b_remediation.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert no_clobber.returncode != 0
    assert "Phase-5B is no-clobber" in no_clobber.stderr
