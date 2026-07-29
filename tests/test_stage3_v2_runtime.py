"""Contract tests for the Stage-3 v2 task/checkpoint runtime."""

import pytest

import stage3_v2_runtime as runtime


def load_protocol(root):
    return runtime.load_strict_json(
        root / "data" / "stage3_synthetic_calibration_protocol_v2.json"
    )


def valid_result(task_type):
    if task_type == "screening":
        return {
            "class_name": "C01",
            "model_id": "raw_valid::W13_P0",
            "mask_id": "raw_valid",
            "cell_id": "W13_P0",
            "held_sector": 37,
            "k0_score": 0.0,
            "m1_score": 0.0,
            "delta_elpd": 0.0,
            "k0_objective": 0.0,
            "m1_objective": 0.0,
            "k0_boundary_count": 0,
            "m1_boundary_count": 0,
            "baseline_draws": {},
            "injected_geometry": None,
            "sector_noise": {},
            "gap_edge_event_recovery_flags": {},
            "latent_sha256": "0" * 64,
            "realization_seed": 749204,
        }
    return {
        "class_name": "C01",
        "model_id": "raw_valid::W13_P0",
        "mask_id": "raw_valid",
        "cell_id": "W13_P0",
        "objective_h0": 0.0,
        "objective_h1": 0.0,
        "delta_map": 0.0,
        "h1_stationary": True,
        "h1_recovered_geometry": {"rp_rs": 0.05, "a_rs": 10.0, "impact_parameter": 0.5},
        "h1_intervals": {
            "rp_rs": [0.04, 0.05, 0.06, 0.07],
            "a_rs": [9.0, 9.5, 10.5, 11.0],
            "impact_parameter": [0.3, 0.4, 0.6, 0.7],
            "t14_hours": [4.0, 4.5, 5.0, 5.5],
        },
        "h1_boundary_count": 0,
        "h0_boundary_count": 0,
        "baseline_draws": {},
        "injected_geometry": None,
        "sector_noise": {},
        "gap_edge_event_recovery_flags": {},
        "latent_sha256": "0" * 64,
        "realization_seed": 749204,
    }


def test_v2_expected_task_universe_has_frozen_counts(root):
    protocol = load_protocol(root)
    assert len(runtime.expected_task_keys(protocol, "screening")) == 33840
    assert len(runtime.expected_task_keys(protocol, "joint")) == 5640
    assert runtime.expected_task_keys(protocol, "joint")[0].held_sector == -1


def test_v2_identity_contains_all_required_bindings(root):
    identity = runtime.build_identity(root)
    assert set(identity) == {
        "protocol_v2_sha256", "architecture_v2_sha256", "input_manifest_sha256",
        "code_identity", "environment_identity", "task_schema_version",
    }
    assert identity["code_identity"]["files"]
    assert identity["environment_identity"]["sha256"]


def test_historical_execution_request_is_pending_and_revision_is_superseded(root):
    identity = runtime.build_identity(root)
    authorization, approved = runtime.validate_execution_authorization(root, identity)
    assert authorization["status"] == "PENDING_INDEPENDENT_REVIEW"
    assert approved is False
    registry = runtime.load_strict_json(root / "protocols" / "stage3" / "index.json")
    assert registry["revisions"]["2"]["status"] == "SUPERSEDED_REVIEW_FAILED"
    assert registry["active_execution_revision"] is None


def test_execution_authorization_requires_matching_review_and_code(root, tmp_path):
    identity = runtime.build_identity(root)
    source = runtime.load_strict_json(
        root / "data" / "stage3_v2_execution_authorization.json"
    )
    source["status"] = "APPROVED"
    source["code_identity_sha256"] = identity["code_identity"]["sha256"]
    source["review"] = {
        "independent_second_party": True,
        "reviewer_id": "reviewer-example",
        "reviewed_utc": "2026-07-29T00:00:00Z",
        "decision": "APPROVED",
        "notes": "Independent review completed.",
    }
    path = tmp_path / "data" / "stage3_v2_execution_authorization.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(runtime.canonical_json_bytes(source))
    authorization, approved = runtime.validate_execution_authorization(tmp_path, identity)
    assert authorization["status"] == "APPROVED"
    assert approved is True
    source["protocol_v2_sha256"] = "0" * 64
    path.write_bytes(runtime.canonical_json_bytes(source))
    with pytest.raises(runtime.RuntimeContractError, match="hash mismatch"):
        runtime.validate_execution_authorization(tmp_path, identity)


def test_immutable_json_allows_identical_retry_and_rejects_clobber(tmp_path):
    path = tmp_path / "record.json"
    payload = {"ok": True, "value": 3}
    assert runtime.write_immutable_json(path, payload) is True
    assert runtime.write_immutable_json(path, payload) is False
    with pytest.raises(FileExistsError):
        runtime.write_immutable_json(path, {"ok": True, "value": 4})


def test_strict_json_rejects_duplicate_keys_and_nonfinite(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a": 1, "a": 2}\n', encoding="utf-8")
    with pytest.raises(runtime.RuntimeContractError, match="duplicate"):
        runtime.load_strict_json(duplicate)
    with pytest.raises(runtime.RuntimeContractError, match="non-finite"):
        runtime.canonical_json_bytes({"value": float("nan")})


def test_partial_namespace_verification_is_explicit(root, tmp_path):
    protocol = load_protocol(root)
    identity = runtime.build_identity(root)
    key = runtime.expected_task_keys(protocol, "screening")[0]
    record = runtime.make_task_record(
        identity, "screening", key, "completed", valid_result("screening")
    )
    runtime.write_immutable_json(
        runtime.checkpoint_path(tmp_path, "screening", key), record,
    )
    with pytest.raises(runtime.RuntimeContractError, match="incomplete"):
        runtime.verify_namespace(tmp_path, protocol, identity)
    result = runtime.verify_namespace(tmp_path, protocol, identity, allow_partial=True)
    assert result["verified_records"] == 1
    assert result["missing_records"] == 39479
    assert result["complete"] is False


def test_namespace_verification_rejects_unknown_checkpoint_paths(root, tmp_path):
    protocol = load_protocol(root)
    identity = runtime.build_identity(root)
    unknown = tmp_path / "outputs" / "stage3_v2" / "checkpoints" / "legacy.json"
    unknown.parent.mkdir(parents=True)
    unknown.write_text("{}\n", encoding="utf-8")
    with pytest.raises(runtime.RuntimeContractError, match="unexpected checkpoint"):
        runtime.verify_namespace(tmp_path, protocol, identity, allow_partial=True)


def test_failed_task_is_not_silently_accepted(root, tmp_path):
    protocol = load_protocol(root)
    identity = runtime.build_identity(root)
    key = runtime.expected_task_keys(protocol, "joint")[0]
    record = runtime.make_task_record(
        identity, "joint", key, "failed", error="fit failed",
    )
    runtime.write_immutable_json(
        runtime.checkpoint_path(tmp_path, "joint", key), record,
    )
    with pytest.raises(runtime.RuntimeContractError, match="failed task"):
        runtime.verify_namespace(tmp_path, protocol, identity, allow_partial=True)
