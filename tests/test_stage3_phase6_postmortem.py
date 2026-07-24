import ast
import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest


def load_json(root, relative_path):
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def as_bool(series):
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    return series.astype(str).str.lower().eq("true")


@pytest.fixture
def report(root):
    return load_json(root, "outputs/stage3_phase6_postmortem.json")


def test_s3_02_report_passes_without_opening_real_data(report):
    assert report["status"] == "PASS"
    assert all(report["gate"]["checks"].values())
    assert report["scope"] == {
        "analysis_mode": "EXISTING_ARTIFACTS_AND_FROZEN_ENDPOINT_DIAGNOSTICS_ONLY",
        "real_data_fit_executed": False,
        "optimizer_calls": 0,
        "new_random_draws": 0,
        "threshold_changes": 0,
        "phase_7_may_begin": False,
    }
    assert len(report["questions"]) == 10
    assert report["unsupported_explanations"]


def test_s3_02_boundary_map_is_complete_and_identifies_only_upper_timescales(root):
    frame = pd.read_csv(root / "outputs/stage3_phase6_boundary_map.csv")
    flagged = frame.loc[as_bool(frame["at_boundary"])]

    assert len(frame) == 6480
    assert not frame.duplicated(
        ["model_id", "kernel_id", "held_sector", "parameter_index"]
    ).any()
    assert flagged.groupby("kernel_id").size().to_dict() == {
        "K1_ou": 87,
        "K2_matern32": 37,
        "K3_sho": 20,
    }
    assert set(flagged["parameter_name"]) == {"log_timescale_minutes"}
    assert set(flagged["nearest_boundary"]) == {"upper"}
    assert frame["source_artifact"].eq("outputs/faz6_loso_scores.csv").all()
    assert frame["source_csv_row"].between(2, 577).all()


def test_s3_02_mask_influence_separates_sector_evidence_from_cadence_limits(root):
    frame = pd.read_csv(
        root / "outputs/stage3_phase6_mask_influence.csv", keep_default_na=False
    )
    sectors = frame.loc[frame["record_type"] == "sector_kernel_interaction"].copy()
    cadences = frame.loc[frame["record_type"] == "raw_only_cadence"].copy()

    assert len(sectors) == 18
    assert len(cadences) == 60
    assert (~as_bool(frame["cadence_effect_attribution_supported"])).all()
    expected = {
        "K1_ou": -1.1304441515962935,
        "K2_matern32": -1.0199785241841255,
        "K3_sho": -1.0319348624300346,
    }
    sectors["mask_interaction"] = pd.to_numeric(sectors["mask_interaction"])
    sectors["absolute_interaction_rank_within_kernel"] = pd.to_numeric(
        sectors["absolute_interaction_rank_within_kernel"]
    )
    sectors["held_sector"] = pd.to_numeric(sectors["held_sector"])
    observed = sectors.groupby("kernel_id")["mask_interaction"].sum().to_dict()
    assert observed == pytest.approx(expected, abs=2e-12)
    for kernel_id in expected:
        ordered = sectors.loc[sectors["kernel_id"] == kernel_id].sort_values(
            "absolute_interaction_rank_within_kernel"
        )
        assert ordered.iloc[0]["held_sector"] == 64
        assert list(ordered.iloc[:3]["held_sector"]) == [64, 100, 37]

    cadences["sector"] = pd.to_numeric(cadences["sector"])
    assert cadences.groupby("sector").size().to_dict() == {
        37: 20,
        63: 4,
        64: 13,
        90: 4,
        99: 9,
        100: 10,
    }
    assert set(cadences["quality"].astype(int)) == {0}
    assert as_bool(cadences["inside_inner_transit_mask"]).sum() == 4
    assert as_bool(cadences["screening_oot_eligible_w13"]).sum() == 4
    assert as_bool(cadences["screening_oot_eligible_w26"]).sum() == 17
    assert as_bool(cadences["screening_oot_eligible_w32"]).sum() == 19


def test_s3_02_beta_rows_reproduce_phase6r_and_expose_sector_drivers(root, report):
    frame = pd.read_csv(root / "outputs/stage3_phase6_beta_by_sector.csv")
    assert len(frame) == 24 * 6 * 6
    assert not frame.duplicated(
        ["model_id", "sector", "timescale_minutes"]
    ).any()
    assert as_bool(frame["eligible"]).all()
    assert set(frame["sector"]) == {37, 63, 64, 90, 99, 100}
    assert set(frame["timescale_minutes"]) == {20, 40, 80, 160, 320, 360}
    assert frame.groupby(["sector", "timescale_minutes"]).size().eq(24).all()
    assert frame.groupby(["sector", "timescale_minutes"])[
        "joint_model_weight"
    ].sum().to_numpy() == pytest.approx(1.0, abs=1e-12)

    sector_mixture = frame.groupby(
        ["sector", "timescale_minutes"]
    )["weighted_beta_contribution"].sum()
    reconstructed = sector_mixture.groupby("timescale_minutes").mean().to_dict()
    frozen = {
        item["timescale_minutes"]: item["weighted_equal_sector_beta"]
        for item in load_json(root, "outputs/faz6r_result.json")["beta_mixture"]
    }
    assert reconstructed == pytest.approx(frozen, abs=2e-12)
    assert max(reconstructed, key=reconstructed.get) == 80.0
    assert max(reconstructed.values()) == pytest.approx(
        1.2936064512125263, abs=2e-12
    )
    at_80 = sector_mixture.xs(80.0, level="timescale_minutes")
    assert int(at_80.idxmax()) == 37
    assert report["phase6r_residual_analysis"]["maximum_weighted_beta"] == pytest.approx(
        max(reconstructed.values()), abs=2e-12
    )


def test_s3_02_residual_summary_covers_every_branch_sector_and_is_descriptive(root):
    frame = pd.read_csv(root / "outputs/stage3_phase6_residual_summary.csv")
    assert len(frame) == 24 * 6
    assert not frame.duplicated(["model_id", "sector"]).any()
    assert frame.groupby("model_id")["event_count"].sum().eq(16).all()
    assert np.isfinite(
        frame[
            [
                "centered_rms",
                "frozen_sector_jitter",
                "maximum_beta",
                "maximum_absolute_acf_nonzero_lag",
                "branch_periodogram_peak_power",
            ]
        ].to_numpy(float)
    ).all()
    assert (frame["centered_rms"] > 0.0).all()
    assert as_bool(frame["telemetry_association_diagnostic_only"]).all()
    assert frame["source_artifact"].eq("outputs/faz6r_joint_fits.csv").all()


def test_s3_02_preserves_v1_quarantine_and_v2_empty_artifacts(report):
    versions = {
        item["version"]: item for item in report["residual_artifact_validity"]["versions"]
    }
    assert versions["v1"]["status"] == "QUARANTINED_INVALID_NUMERICAL_RESULT"
    assert versions["v2"]["status"] == "EMPTY_AFTER_STATIONARITY_FAILURE"
    assert [item["row_count"] for item in versions["v1"]["artifacts"]] == [
        30408,
        1008,
        156997,
        120,
    ]
    assert [item["row_count"] for item in versions["v2"]["artifacts"]] == [0, 0, 0, 0]
    assert all(
        item["scientifically_usable"] is False
        for version in versions.values()
        for item in version["artifacts"]
    )


def test_s3_02_runner_has_no_direct_fit_or_optimizer_call(root):
    source = (root / "scripts/run_stage3_phase6_postmortem.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    called_names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            called_names.add(node.func.attr)

    assert "scipy.optimize" not in imported_modules
    assert "run_faz6r" not in imported_modules
    assert called_names.isdisjoint(
        {
            "minimize",
            "fit_pooled_map",
            "fit_branch",
            "fit_cell",
            "finite_difference_hessian",
            "draw_laplace",
            "geometry_and_residuals",
        }
    )


def test_s3_02_runner_verifies_and_refuses_to_clobber(root):
    verify = subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/run_stage3_phase6_postmortem.py",
            "--verify-only",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert verify.returncode == 0, verify.stderr
    assert "PASS (verified)" in verify.stdout

    no_clobber = subprocess.run(
        [sys.executable, "-B", "scripts/run_stage3_phase6_postmortem.py"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert no_clobber.returncode != 0
    assert "no-clobber" in no_clobber.stderr
