import hashlib
import json

import pytest

from toi3492.stage3.cli import main
from toi3492.stage3.contracts import ContractError, RunSpec, TaskKey
from toi3492.stage3.jsonio import canonical_json_bytes, create_immutable_json
from toi3492.stage3.runtime import (
    readiness,
    require_execution_ready,
    task_path,
    validate_task,
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
