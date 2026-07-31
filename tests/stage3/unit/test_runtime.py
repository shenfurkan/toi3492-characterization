import hashlib
import json

import pytest

import toi3492.stage3.runtime as runtime_module
from toi3492.stage3.cli import main
from toi3492.stage3.contracts import BranchSpec, ContractError, RunSpec, TaskKey
from toi3492.stage3.jsonio import (
    canonical_json_bytes,
    create_immutable_json,
    load_strict_json,
)
from toi3492.stage3.runtime import (
    authorization_schema_valid,
    hash_bindings_match,
    readiness,
    require_execution_ready,
    review_approved,
    task_path,
    validate_task,
    verify_component,
    write_realization_metadata,
    write_task,
)


@pytest.mark.parametrize("revision", (1, 2, 3))
def test_historical_revisions_fail_all_execution_gates(root, revision):
    report = readiness(RunSpec.from_registry(root, revision))
    assert report["active_execution_revision"] is None
    assert report["active_revision_matches"] is False
    assert report["implementation_compatible"] is False
    assert report["authorization_schema_valid"] is False
    assert report["execution_ready"] is False


def test_require_execution_ready_rejects_superseded_revision(root):
    with pytest.raises(ContractError, match="not execution-ready"):
        require_execution_ready(RunSpec.from_registry(root, 3))


def test_artifact_producing_commands_refuse_revision_three(root, capsys):
    namespace = root / "outputs" / "stage3_v3"
    assert not namespace.exists()
    assert main(["run", "--revision", "3", "--confirm-full-run"]) == 1
    assert main(["reduce-only", "--revision", "3"]) == 1
    assert not namespace.exists()
    assert "not execution-ready" in capsys.readouterr().err


def test_status_reports_registry_without_scientific_imports(root, capsys):
    assert main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["active_execution_revision"] is None
    assert status["next_revision"] == 4


def _temporary_spec(tmp_path):
    placeholder = tmp_path / "placeholder.json"
    return RunSpec(
        protocol_revision=4,
        root=tmp_path,
        protocol_path=placeholder,
        architecture_path=placeholder,
        input_manifest_path=placeholder,
        authorization_path=placeholder,
        artifact_namespace=tmp_path / "outputs" / "stage3_v4",
        task_schema_version="stage3-task-record/2.0",
        seed_base=949204,
        status="DEVELOPMENT",
        scientific_use="DEVELOPMENT_ONLY",
    )


def _manifest(run_hash=None):
    payload = {
        "components": {
            "common": {"sha256": "b" * 64},
            "screening": {"sha256": "c" * 64},
            "recovery": {"sha256": "d" * 64},
        },
    }
    payload["sha256"] = run_hash or hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    return payload


def _initialize(spec, manifest):
    create_immutable_json(spec.artifact_namespace / "run_identity.json", manifest)


def _metadata(spec):
    return {
        "class_id": "C01",
        "class_name": "C01_white_jitter_transit",
        "class_ordinal": 0,
        "realization_index": 0,
        "realization_seed": spec.realization_seed(0, 0),
        "drawn_geometry": None,
        "sector_noise": {},
        "telemetry_systematic": None,
        "shared_baseline_draws": {},
        "event_ids": [],
        "latent_sha256": "d" * 64,
    }


def _screening_result():
    return {
        "model_id": "raw_valid::W13_P0",
        "mask_id": "raw_valid",
        "cell_id": "W13_P0",
        "joint_model_weight": 1.0 / 24.0,
        "held_sector": 37,
        "k0_score": 0.0,
        "m1_score": 1.0,
        "delta_elpd": 1.0,
        "k0_objective": 0.0,
        "m1_objective": 1.0,
        "k0_boundary_count": 0,
        "m1_boundary_count": 0,
        "gap_edge_coverage": {},
    }


def test_task_writer_rejects_bad_result_before_creating_record(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    key = TaskKey(0, 0, 0, 37)
    result = _screening_result()
    result["held_sector"] = 63
    with pytest.raises(ContractError, match="held sector mismatch"):
        write_task(spec, manifest, "screening", key, metadata, result)
    assert not task_path(spec, "screening", key).exists()


def test_task_validation_rejects_a_different_run_identity(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    key = TaskKey(0, 0, 0, 37)
    write_task(spec, manifest, "screening", key, metadata, _screening_result())
    with pytest.raises(ContractError, match="run identity mismatch"):
        validate_task(spec, _manifest("e" * 64), "screening", key)


def test_realization_writer_rejects_extra_fields_before_creation(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    metadata = _metadata(spec)
    metadata["unexpected"] = True
    with pytest.raises(ContractError, match="wrong schema"):
        write_realization_metadata(spec, manifest, metadata)
    assert not (spec.artifact_namespace / "realizations").exists()


def test_task_writers_require_an_initialized_namespace(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    with pytest.raises(ContractError, match="not initialized"):
        write_realization_metadata(spec, manifest, _metadata(spec))
    assert not (spec.artifact_namespace / "realizations").exists()


def _identity():
    return {
        "protocol_sha256": "a" * 64,
        "architecture_sha256": "b" * 64,
        "input_manifest_sha256": "c" * 64,
        "code_identity_sha256": "d" * 64,
    }


def _authorization(identity):
    return {
        "schema_version": "1.0",
        "record_type": "STAGE3_EXECUTION_AUTHORIZATION",
        "protocol_revision": 4,
        "status": "APPROVED",
        "scope": "SYNTHETIC_CALIBRATION_ONLY",
        "protocol_sha256": identity["protocol_sha256"],
        "architecture_sha256": identity["architecture_sha256"],
        "input_manifest_sha256": identity["input_manifest_sha256"],
        "code_identity_sha256": identity["code_identity_sha256"],
        "review": {
            "independent_second_party": True,
            "reviewer_id": "REVIEWER_001",
            "reviewed_utc": "2026-08-01T12:00:00Z",
            "decision": "APPROVED",
            "notes": "independent second-party approval",
        },
        "real_data_fit_authorized": False,
        "phase_7_authorized": False,
    }


def test_review_approved_accepts_a_minimal_valid_review():
    assert review_approved(_authorization(_identity())) is True


@pytest.mark.parametrize("mutate", [
    lambda a: a.update(status="PENDING"),
    lambda a: a["review"].update(independent_second_party=False),
    lambda a: a["review"].update(decision="REJECTED"),
    lambda a: a["review"].update(reviewer_id="   "),
    lambda a: a["review"].update(reviewed_utc="2026-08-01 12:00:00"),
    lambda a: a.update(real_data_fit_authorized=True),
    lambda a: a.update(phase_7_authorized=True),
    lambda a: a.update(review="not-a-mapping"),
])
def test_review_approved_rejects_each_violation(mutate):
    authorization = _authorization(_identity())
    mutate(authorization)
    assert review_approved(authorization) is False


def test_minimal_revision4_authorization_passes_the_schema(tmp_path):
    spec = _temporary_spec(tmp_path)
    assert authorization_schema_valid(_authorization(_identity()), spec) is True


def test_legacy_v2_v3_authorization_shape_is_rejected(tmp_path):
    spec = _temporary_spec(tmp_path)
    legacy = _authorization(_identity())
    legacy["record_type"] = "STAGE3_V2_EXECUTION_AUTHORIZATION"
    legacy.pop("protocol_revision")
    assert authorization_schema_valid(legacy, spec) is False


@pytest.mark.parametrize("mutate", [
    lambda a: a.pop("scope"),
    lambda a: a.update(extra=True),
    lambda a: a.update(schema_version="2.0"),
    lambda a: a.update(scope="REAL_DATA"),
    lambda a: a["review"].pop("notes"),
    lambda a: a.update(review={}),
])
def test_authorization_schema_rejects_field_set_deviations(tmp_path, mutate):
    spec = _temporary_spec(tmp_path)
    authorization = _authorization(_identity())
    mutate(authorization)
    assert authorization_schema_valid(authorization, spec) is False


def test_hash_bindings_match_accepts_exact_bindings():
    identity = _identity()
    assert hash_bindings_match(_authorization(identity), identity) is True


@pytest.mark.parametrize("field", [
    "protocol_sha256",
    "architecture_sha256",
    "input_manifest_sha256",
    "code_identity_sha256",
])
def test_hash_bindings_match_rejects_each_mismatched_hash(field):
    identity = _identity()
    authorization = _authorization(identity)
    authorization[field] = "f" * 64
    assert hash_bindings_match(authorization, identity) is False


def test_hash_bindings_match_short_circuits_on_none_identity():
    assert hash_bindings_match(_authorization(_identity()), None) is False


def _branch():
    return BranchSpec(
        ordinal=0,
        model_id="raw_valid::W13_P0",
        mask_id="raw_valid",
        cell_id="W13_P0",
        window_hours=13,
        polynomial_degree=0,
        joint_model_weight=1.0 / 24.0,
    )


def _write_screening_task(spec, manifest, key):
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    return write_task(
        spec, manifest, "screening", key, metadata, _screening_result(),
        expected_branch=_branch(),
    )


def test_write_task_rejects_a_result_for_the_wrong_branch(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    key = TaskKey(0, 0, 0, 37)
    result = _screening_result()
    result["model_id"] = "reference_included::OTHER"
    with pytest.raises(ContractError, match="does not match its branch"):
        write_task(spec, manifest, "screening", key, metadata, result, _branch())
    assert not task_path(spec, "screening", key).exists()


def test_write_task_rejects_a_branch_weight_mismatch(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    key = TaskKey(0, 0, 0, 37)
    result = _screening_result()
    result["joint_model_weight"] = 0.5
    with pytest.raises(ContractError, match="branch weight mismatch"):
        write_task(spec, manifest, "screening", key, metadata, result, _branch())
    assert not task_path(spec, "screening", key).exists()


def test_validate_task_rejects_a_tampered_result_sha256(tmp_path):
    spec = _temporary_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    key = TaskKey(0, 0, 0, 37)
    _write_screening_task(spec, manifest, key)
    path = task_path(spec, "screening", key)
    record = load_strict_json(path)
    record["result"]["m1_score"] = 99.0
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ContractError, match="task result hash mismatch"):
        validate_task(spec, manifest, "screening", key)


def _recovery_spec(tmp_path):
    placeholder = tmp_path / "placeholder.json"
    architecture = tmp_path / "architecture.json"
    architecture.write_text(json.dumps({
        "candidate": {
            "transit_model": {
                "geometry_uniform_bounds": {
                    "rp_rs": [0.03, 0.09],
                    "a_rs": [5.0, 16.0],
                    "impact_parameter": [0.0, 0.98],
                },
            },
        },
    }), encoding="utf-8")
    return RunSpec(
        protocol_revision=4,
        root=tmp_path,
        protocol_path=placeholder,
        architecture_path=architecture,
        input_manifest_path=placeholder,
        authorization_path=placeholder,
        artifact_namespace=tmp_path / "outputs" / "stage3_v4",
        task_schema_version="stage3-task-record/2.0",
        seed_base=949204,
        status="DEVELOPMENT",
        scientific_use="DEVELOPMENT_ONLY",
    )


def _recovery_result():
    return {
        "model_id": "raw_valid::W13_P0",
        "mask_id": "raw_valid",
        "cell_id": "W13_P0",
        "joint_model_weight": 1.0 / 24.0,
        "objective_h0": 1.0,
        "objective_h1": 0.5,
        "delta_map": 0.5,
        "recovery_mode": "conditional_geometry_with_fixed_oot_noise",
        "recovered_geometry": {
            "rp_rs": 0.05,
            "a_rs": 10.0,
            "impact_parameter": 0.5,
            "t14_hours": 5.0,
        },
        "injected_geometry": None,
        "intervals": {
            "rp_rs": [0.03, 0.04, 0.06, 0.09],
            "a_rs": [6.0, 8.0, 12.0, 15.0],
            "impact_parameter": [0.1, 0.3, 0.7, 0.9],
            "t14_hours": [3.0, 4.0, 6.0, 7.0],
        },
        "noise_boundary_count": 0,
        "geometry_boundary_count": 0,
        "gap_edge_coverage": {},
        "optimizer_no_op_count": 0,
        "optimizer_local_mode_count": 0,
        "max_abs_standardized_residual": 0.0,
        "ingress_egress_rms_relative_flux": 0.0,
    }


def _write_recovery_task(spec, manifest, key):
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    return write_task(
        spec, manifest, "recovery", key, metadata, _recovery_result(),
        expected_branch=_branch(),
    )


@pytest.mark.parametrize("mutate, match", [
    (lambda r: r["recovered_geometry"].update(rp_rs=0.02), "outside the frozen uniform bounds"),
    (lambda r: r["recovered_geometry"].update(a_rs=20.0), "outside the frozen uniform bounds"),
    (lambda r: r["recovered_geometry"].update(impact_parameter=-0.1), "outside the frozen uniform bounds"),
    (lambda r: r["recovered_geometry"].update(t14_hours=0.0), "t14_hours must be positive"),
    (lambda r: r["recovered_geometry"].pop("rp_rs"), "geometry schema mismatch"),
    (lambda r: r["recovered_geometry"].update(extra=1.0), "geometry schema mismatch"),
    (lambda r: r.update(injected_geometry={"rp_rs": 0.05, "a_rs": 10.0}), "injected geometry schema mismatch"),
    (lambda r: r["intervals"]["rp_rs"].append(0.1), "does not have four quantiles"),
    (lambda r: r["intervals"]["rp_rs"].pop(2), "does not have four quantiles"),
    (lambda r: r["intervals"].update(a_rs=[9.0, 8.0, 7.0, 6.0]), "quantiles are not ordered"),
    (lambda r: r["intervals"].pop("t14_hours"), "intervals schema mismatch"),
    (lambda r: r["gap_edge_coverage"].update(event="yes"), "gap_edge_coverage must map event ids to booleans"),
    (lambda r: r.update(noise_boundary_count=-1), "must be a non-negative integer"),
    (lambda r: r.update(geometry_boundary_count=True), "must be a non-negative integer"),
    (lambda r: r.update(optimizer_no_op_count=1.5), "must be a non-negative integer"),
    (lambda r: r.update(optimizer_local_mode_count=-2), "must be a non-negative integer"),
])
def test_recovery_result_rejects_nested_content_violations(tmp_path, mutate, match):
    spec = _recovery_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    metadata = write_realization_metadata(spec, manifest, _metadata(spec))
    key = TaskKey(0, 0, 0, -1)
    result = _recovery_result()
    mutate(result)
    with pytest.raises(ContractError, match=match):
        write_task(spec, manifest, "recovery", key, metadata, result, _branch())
    assert not task_path(spec, "recovery", key).exists()


def test_recovery_result_accepts_a_valid_payload(tmp_path):
    spec = _recovery_spec(tmp_path)
    manifest = _manifest()
    _initialize(spec, manifest)
    key = TaskKey(0, 0, 0, -1)
    _write_recovery_task(spec, manifest, key)
    record = validate_task(spec, manifest, "recovery", key)
    assert record["status"] == "COMPLETED"


def test_verify_component_rejects_a_stale_run_identity(tmp_path, monkeypatch):
    spec = _temporary_spec(tmp_path)
    monkeypatch.setattr(RunSpec, "has_canonical_implementation_contract", lambda self: True)
    monkeypatch.setattr(
        RunSpec, "expected_task_keys", lambda self, component: (TaskKey(0, 0, 0, 37),),
    )
    manifest = _manifest()
    _initialize(spec, manifest)
    monkeypatch.setattr(runtime_module, "run_identity", lambda spec: _manifest("f" * 64))
    with pytest.raises(ContractError, match="stored run identity does not match"):
        verify_component(spec, "screening")


def test_verify_component_rejects_an_unexpected_task_file(tmp_path, monkeypatch):
    spec = _temporary_spec(tmp_path)
    monkeypatch.setattr(RunSpec, "has_canonical_implementation_contract", lambda self: True)
    monkeypatch.setattr(RunSpec, "expected_task_keys", lambda self, component: ())
    manifest = _manifest()
    _initialize(spec, manifest)
    monkeypatch.setattr(runtime_module, "run_identity", lambda spec: manifest)
    stray = spec.artifact_namespace / "tasks" / "screening" / "stray.json"
    stray.parent.mkdir(parents=True)
    stray.write_text("{}", encoding="utf-8")
    with pytest.raises(ContractError, match="unexpected task record"):
        verify_component(spec, "screening")


def test_verify_component_reports_partial_task_sets_without_rerun(tmp_path, monkeypatch):
    spec = _temporary_spec(tmp_path)
    monkeypatch.setattr(RunSpec, "has_canonical_implementation_contract", lambda self: True)
    expected = (TaskKey(0, 0, 0, 37), TaskKey(0, 0, 1, 37))
    monkeypatch.setattr(RunSpec, "expected_task_keys", lambda self, component: expected)
    manifest = _manifest()
    _initialize(spec, manifest)
    monkeypatch.setattr(runtime_module, "run_identity", lambda spec: manifest)
    _write_screening_task(spec, manifest, TaskKey(0, 0, 0, 37))
    report = verify_component(spec, "screening", require_complete=False)
    assert report == {"component": "screening", "expected": 2, "present": 1, "missing": 1}
    with pytest.raises(ContractError, match="missing records"):
        verify_component(spec, "screening", require_complete=True)
