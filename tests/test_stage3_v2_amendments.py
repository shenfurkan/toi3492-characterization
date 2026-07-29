"""Regression tests for the S3-03 v2 / S3-04A v2 versioned amendments."""

import hashlib
import json
import subprocess
import sys

import numpy as np
import pytest

import stage3_synthetic_calibration_core as core


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(root, relative):
    return json.loads((root / relative).read_text(encoding="utf-8"))


@pytest.fixture
def arch(root):
    return load(root, "data/stage3_model_architecture_decision_v2.json")


@pytest.fixture
def protocol(root):
    return load(root, "data/stage3_synthetic_calibration_protocol_v2.json")


def test_architecture_v2_is_frozen_pass_and_supersedes_v1(root, arch):
    assert arch["schema_version"] == "2.0"
    assert arch["status"] == "PASS"
    assert all(arch["gate"]["checks"].values())
    assert arch["scope"]["supersedes"] == "data/stage3_model_architecture_decision.json"
    assert arch["scope"]["supersedes_sha256"] == sha256(
        root / "data/stage3_model_architecture_decision.json"
    )
    assert arch["scope"]["v1_preserved_unmodified"] is True
    assert arch["scope"]["real_data_fit_authorized"] is False
    assert arch["scope"]["execution_authorized"] is False
    assert arch["scope"]["phase_7_may_begin"] is False
    registry = load(root, "protocols/stage3/index.json")
    assert registry["revisions"]["2"]["status"] == "SUPERSEDED_REVIEW_FAILED"
    assert registry["revisions"]["2"]["scientific_use"] == "NONE"


def test_architecture_v2_defines_the_null_transit_hypothesis(arch):
    null = arch["candidate"]["transit_model"]["null_hypothesis"]
    assert null["rp_rs"] == 0.0
    assert "delta_map" in null["detection_statistic"]
    assert "delta_detect" in null["detection_rule"]
    assert arch["candidate"]["transit_model"]["hypothesis_count"] == 2
    assert arch["candidate"]["transit_model"]["geometry_uniform_bounds"]["rp_rs"] == [0.03, 0.09]


def test_architecture_v2_binds_checkpoint_identity_and_completion(arch):
    assert arch["checkpoint_identity"]["required_fields"] == [
        "protocol_v2_sha256", "architecture_v2_sha256", "input_manifest_sha256",
        "code_identity", "environment_identity", "task_schema_version", "task_key",
    ]
    assert arch["completion_rule"]["required_fraction"] == 1.0
    assert arch["completion_rule"]["partial_acceptance_permitted"] is False
    assert "at_boundary flag is true" in arch["boundary_accounting"]["rule"]
    assert arch["optimizer"]["registered_starts"] == 4
    assert arch["seed_policy"]["base_seed_v2"] == 749204
    assert arch["seed_policy"]["base_seed_v2"] != arch["seed_policy"]["base_seed_v1"]


def test_architecture_v2_namespace_is_fresh_and_legacy_is_forbidden(arch):
    namespace = arch["artifact_namespace"]
    assert namespace["root"] == "outputs/stage3_v2"
    for key in ("screening_detail_csv", "realization_summary_csv", "joint_recovery_csv",
                "calibration_summary_json", "threshold_calibration_json", "checkpoint_dir"):
        assert namespace[key].startswith("outputs/stage3_v2/")
    assert "outputs/stage3_synthetic_screening_detail.csv" in namespace["legacy_paths_forbidden"]
    assert "data/stage3_threshold_calibration.json" in namespace["legacy_paths_forbidden"]


def test_protocol_v2_is_frozen_pass_and_binds_architecture(root, protocol, arch):
    assert protocol["schema_version"] == "2.0"
    assert protocol["status"] == "PASS"
    assert all(protocol["gate"]["checks"].values())
    assert protocol["scope"]["supersedes_sha256"] == sha256(
        root / "data/stage3_synthetic_calibration_protocol.json"
    )
    assert protocol["scope"]["architecture_amendment_sha256"] == sha256(
        root / "data/stage3_model_architecture_decision_v2.json"
    )
    assert protocol["scope"]["interrupted_v1_results_observed_and_quarantined"] is True
    assert protocol["scope"]["real_data_fit_authorized"] is False
    assert protocol["scope"]["execution_authorized"] is False


def test_protocol_v2_defines_14_classes_and_235_realizations(protocol):
    classes = protocol["simulation_classes"]
    assert len(classes) == 14
    assert [item["class_index"] for item in classes] == list(range(14))
    assert protocol["requested_total"] == 235
    assert sum(item["requested_count"] for item in classes) == 235
    names = {item["name"] for item in classes}
    assert "C13_aperture_telemetry_correlated" in names
    assert "C14_partial_gap_edge_transit" in names
    c14 = next(item for item in classes if item["name"] == "C14_partial_gap_edge_transit")
    assert c14["event_coverage"]["gap_edge_events"] == 2
    assert c14["event_coverage"]["complete_events"] == 16
    assert all(item["noise_parameters"] for item in classes)


def test_protocol_v2_uses_untouched_seeds(protocol):
    seeds = protocol["deterministic_seeds"]
    assert seeds["base_seed"] == 749204
    assert seeds["v1_base_seed_retired"] == 349204
    assert seeds["streams_disjoint_from_v1"] is True


def test_protocol_v2_fixes_the_contradictions(protocol):
    rules = protocol["threshold_derivation_rules"]
    assert "more stringent" not in rules["coverage_acceptance"]
    assert "delta_detect" in rules["null_transit"]
    assert "delta_map" in rules["null_transit"]
    failure = protocol["calibration_failure"]
    assert failure["partial_acceptance_permitted"] is False
    assert "100%" in failure["incomplete_rule"]
    artifacts = protocol["artifacts"]
    for key in ("screening_detail_csv", "realization_summary_csv", "joint_recovery_csv",
                "calibration_summary_json", "threshold_calibration_json", "checkpoint_dir"):
        assert artifacts[key].startswith("outputs/stage3_v2/")
    assert "partial_completion" not in failure


def test_protocol_v2_requires_checkpoint_bound_execution(protocol):
    requirements = protocol["execution_requirements"]
    fields = requirements["checkpoint_identity"]["required_fields"]
    assert len(fields) == 7
    assert "task_key" in fields
    runner_rules = " ".join(requirements["runner"])
    assert "outputs/stage3_v2/" in runner_rules
    assert "exits nonzero" in runner_rules
    assert "worker count" in runner_rules


def test_v2_builders_verify_and_refuse_to_clobber(root):
    for builder in (
        "scripts/build_stage3_model_architecture_decision_v2.py",
        "scripts/build_stage3_synthetic_calibration_protocol_v2.py",
    ):
        verify = subprocess.run(
            [sys.executable, "-B", builder, "--verify-only"],
            cwd=root, capture_output=True, text=True, check=False, timeout=120,
        )
        assert verify.returncode == 0, verify.stderr
        assert "PASS (verified)" in verify.stdout
        clobber = subprocess.run(
            [sys.executable, "-B", builder],
            cwd=root, capture_output=True, text=True, check=False, timeout=120,
        )
        assert clobber.returncode != 0
        assert "no-clobber" in (clobber.stdout + clobber.stderr)


@pytest.fixture(scope="module")
def context():
    return core.load_context()


def test_shared_baseline_spans_the_widest_branch_window(context):
    """S3V2-A02: the shared draw covers +/-16 h, not the v1-era narrow window."""
    spec = next(item for item in context.protocol["simulation_classes"]
                if item["name"] == "C02_m1_160_transit")
    latent, _ = core.generate_latent_realization(context, spec, 2)
    baseline = latent["shared_baseline"].to_numpy()
    time = latent["time_btjd"].to_numpy()
    sectors = latent["sector"].to_numpy()
    half_width = 32.0 / 48.0
    outer_support_seen = False
    for event in context.events:
        delta = np.abs(time - float(event["midpoint_btjd"]))
        selected = (sectors == int(event["sector"])) & (delta <= half_width)
        outer = selected & (delta > 10.0 / 48.0)
        if np.any(outer) and np.any(np.abs(baseline[outer]) > 1e-12):
            outer_support_seen = True
            break
    assert outer_support_seen
