"""Regression tests for the S3-03/S3-04A v3 amendment."""

import hashlib
import json
import subprocess
import sys

import stage3_v2_runtime as v2_runtime
import stage3_v3_runtime as v3_runtime


def load(root, relative):
    return json.loads((root / relative).read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v3_amendments_are_fresh_and_hash_bound(root):
    architecture = load(root, "data/stage3_model_architecture_decision_v3.json")
    protocol = load(root, "data/stage3_synthetic_calibration_protocol_v3.json")
    assert architecture["schema_version"] == "3.0"
    assert protocol["schema_version"] == "3.0"
    assert architecture["status"] == "PASS"
    assert protocol["status"] == "PASS"
    assert architecture["seed_policy"]["base_seed_v3"] == 849204
    assert protocol["deterministic_seeds"]["base_seed"] == 849204
    assert architecture["artifact_namespace"]["root"] == "outputs/stage3_v3"
    assert protocol["artifacts"]["root"] == "outputs/stage3_v3"
    assert protocol["scope"]["architecture_amendment_sha256"] == sha256(
        root / "data/stage3_model_architecture_decision_v3.json"
    )
    assert "delta_map > delta_detect" in protocol["threshold_derivation_rules"]["null_transit"]


def test_v3_authorization_request_is_historical_and_revision_is_superseded(root):
    authorization = load(root, "data/stage3_v3_execution_authorization.json")
    assert authorization["status"] == "PENDING_INDEPENDENT_REVIEW"
    registry = load(root, "protocols/stage3/index.json")
    assert registry["revisions"]["3"]["status"] == "SUPERSEDED_IMPLEMENTATION_DEFECTS"
    assert registry["revisions"]["3"]["scientific_use"] == "NONE"
    assert registry["active_execution_revision"] is None
    try:
        v3_runtime.build_identity(root)
    except v3_runtime.RuntimeContractError as exc:
        assert "input manifest" in str(exc)
    else:
        raise AssertionError("superseded v3 identity unexpectedly remained current")


def test_v3_launcher_is_a_permanent_tombstone(root):
    before = v2_runtime.build_identity(root)["protocol_v2_sha256"]
    result = subprocess.run(
        [sys.executable, "-B", "scripts/run_stage3_synthetic_calibration_v3.py", "--preflight"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    after = v2_runtime.build_identity(root)["protocol_v2_sha256"]
    assert before == after
    assert result.returncode == 2
    assert "SUPERSEDED_IMPLEMENTATION_DEFECTS" in result.stderr
