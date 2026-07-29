"""Version-neutral Stage-3 readiness and checkpoint runtime."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .contracts import (
    CANONICAL_TASK_SCHEMA_VERSION,
    EXECUTABLE_REGISTRY_STATUS,
    FORMAL_SCIENTIFIC_USE,
    ContractError,
    RunSpec,
    TaskKey,
    load_registry,
)
from .identity import run_identity, sha256_file
from .jsonio import canonical_json_bytes, create_immutable_json, load_strict_json


AUTHORIZATION_FIELDS = {
    "schema_version", "record_type", "protocol_revision", "status", "scope",
    "protocol_sha256", "architecture_sha256", "input_manifest_sha256",
    "code_identity_sha256", "review", "real_data_fit_authorized",
    "phase_7_authorized",
}
REVIEW_FIELDS = {
    "independent_second_party", "reviewer_id", "reviewed_utc", "decision", "notes",
}
RESULT_FIELDS = {
    "screening": {
        "model_id", "mask_id", "cell_id", "joint_model_weight", "held_sector",
        "k0_score", "m1_score", "delta_elpd", "k0_objective", "m1_objective",
        "k0_boundary_count", "m1_boundary_count", "gap_edge_coverage",
    },
    "recovery": {
        "model_id", "mask_id", "cell_id", "joint_model_weight", "objective_h0",
        "objective_h1", "delta_map", "recovery_mode", "recovered_geometry",
        "injected_geometry", "intervals", "noise_boundary_count", "gap_edge_coverage",
        "optimizer_no_op_count", "optimizer_local_mode_count",
        "max_abs_standardized_residual", "ingress_egress_rms_relative_flux",
    },
}
METADATA_FIELDS = {
    "schema_version", "run_identity_sha256", "class_id", "class_name",
    "class_ordinal", "realization_index", "realization_seed", "drawn_geometry",
    "sector_noise", "telemetry_systematic", "shared_baseline_draws", "event_ids",
    "latent_sha256", "sha256",
}
RAW_METADATA_FIELDS = METADATA_FIELDS - {
    "schema_version", "run_identity_sha256", "sha256",
}


def _valid_review_timestamp(value) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _validate_result_payload(component: str, key: TaskKey, result: Mapping, path) -> None:
    if not isinstance(result, Mapping) or set(result) != RESULT_FIELDS[component]:
        raise ContractError("task result schema mismatch: {}".format(path))
    if component == "screening" and result["held_sector"] != key.held_sector:
        raise ContractError("screening result held sector mismatch: {}".format(path))
    if float(result["joint_model_weight"]) <= 0.0:
        raise ContractError("task branch weight is not positive: {}".format(path))


def _validate_realization_record(
    spec: RunSpec,
    run_manifest: Mapping,
    key: TaskKey,
    metadata: Mapping,
    path,
) -> None:
    if not isinstance(metadata, Mapping) or set(metadata) != METADATA_FIELDS:
        raise ContractError("realization metadata schema mismatch: {}".format(path))
    metadata_payload = dict(metadata)
    recorded_metadata_hash = metadata_payload.pop("sha256")
    computed_metadata_hash = hashlib.sha256(canonical_json_bytes(metadata_payload)).hexdigest()
    if recorded_metadata_hash != computed_metadata_hash:
        raise ContractError("realization metadata self-hash mismatch: {}".format(path))
    if metadata["run_identity_sha256"] != run_manifest["sha256"]:
        raise ContractError("realization run identity mismatch: {}".format(path))
    if (
        type(metadata["class_ordinal"]) is not int
        or type(metadata["realization_index"]) is not int
        or metadata["class_ordinal"] != key.class_ordinal
        or metadata["realization_index"] != key.realization_index
    ):
        raise ContractError("realization coordinates mismatch: {}".format(path))
    if metadata["realization_seed"] != spec.realization_seed(
        key.class_ordinal, key.realization_index,
    ):
        raise ContractError("realization seed mismatch: {}".format(path))


def readiness(spec: RunSpec) -> Mapping:
    identity = None
    identity_error = None
    try:
        identity = run_identity(spec)
    except (ContractError, OSError, KeyError, ValueError) as exc:
        identity_error = "{}: {}".format(type(exc).__name__, exc)
    authorization = load_strict_json(spec.authorization_path)
    if not isinstance(authorization, Mapping):
        raise ContractError("Stage-3 authorization record must be a JSON object")
    review = authorization.get("review", {})
    authorization_schema_valid = (
        set(authorization) == AUTHORIZATION_FIELDS
        and isinstance(review, Mapping)
        and set(review) == REVIEW_FIELDS
        and authorization.get("schema_version") == "1.0"
        and authorization.get("record_type") == "STAGE3_EXECUTION_AUTHORIZATION"
        and authorization.get("protocol_revision") == spec.protocol_revision
        and authorization.get("scope") == "SYNTHETIC_CALIBRATION_ONLY"
    )
    approved_review = (
        authorization.get("status") == "APPROVED"
        and review.get("independent_second_party") is True
        and review.get("decision") == "APPROVED"
        and isinstance(review.get("reviewer_id"), str)
        and bool(review.get("reviewer_id", "").strip())
        and _valid_review_timestamp(review.get("reviewed_utc"))
        and authorization.get("real_data_fit_authorized") is False
        and authorization.get("phase_7_authorized") is False
    )
    hash_bindings_match = (
        identity is not None
        and authorization.get("protocol_sha256") == identity["protocol_sha256"]
        and authorization.get("architecture_sha256") == identity["architecture_sha256"]
        and authorization.get("input_manifest_sha256") == identity["input_manifest_sha256"]
        and authorization.get("code_identity_sha256") == identity["code_identity_sha256"]
    )
    registry = load_registry(spec.root)
    active_revision_matches = registry["active_execution_revision"] == spec.protocol_revision
    executable_registry = (
        registry["execution_state"] == EXECUTABLE_REGISTRY_STATUS
        and spec.status == EXECUTABLE_REGISTRY_STATUS
        and spec.scientific_use == FORMAL_SCIENTIFIC_USE
    )
    implementation_compatible = spec.has_canonical_implementation_contract()
    execution_ready = all((
        active_revision_matches,
        executable_registry,
        implementation_compatible,
        identity is not None,
        authorization_schema_valid,
        approved_review,
        hash_bindings_match,
    ))
    return {
        "protocol_revision": spec.protocol_revision,
        "active_execution_revision": registry["active_execution_revision"],
        "active_revision_matches": active_revision_matches,
        "registry_execution_state": registry["execution_state"],
        "registry_status": spec.status,
        "scientific_use": spec.scientific_use,
        "implementation_compatible": implementation_compatible,
        "identity_valid": identity is not None,
        "identity_error": identity_error,
        "authorization_status": authorization.get("status"),
        "authorization_schema_valid": authorization_schema_valid,
        "independent_review_complete": bool(approved_review),
        "authorization_hash_bindings_match": bool(hash_bindings_match),
        "authorization_sha256": sha256_file(spec.authorization_path),
        "execution_ready": execution_ready,
        "real_data_fit_authorized": False,
        "phase_7_authorized": False,
        "run_identity": identity,
    }


def require_execution_ready(spec: RunSpec) -> Mapping:
    report = readiness(spec)
    if not report["execution_ready"]:
        raise ContractError(
            "Stage-3 revision {} is not execution-ready: active={}, registry={}, "
            "authorization={}, review={}, bindings={}, implementation={}".format(
                spec.protocol_revision,
                report["active_execution_revision"],
                report["registry_status"],
                report["authorization_status"],
                report["independent_review_complete"],
                report["authorization_hash_bindings_match"],
                report["implementation_compatible"],
            )
        )
    return report


def require_development_ready(spec: RunSpec) -> None:
    if not (
        spec.status == "DEVELOPMENT"
        and spec.scientific_use == "DEVELOPMENT_ONLY"
        and spec.has_canonical_implementation_contract()
    ):
        raise ContractError(
            "diagnostic generation requires a registered canonical DEVELOPMENT revision"
        )


def initialize_namespace(spec: RunSpec) -> Mapping:
    report = require_execution_ready(spec)
    manifest = report["run_identity"]
    create_immutable_json(spec.artifact_namespace / "run_identity.json", manifest)
    return manifest


def realization_metadata_path(spec: RunSpec, class_ordinal: int, realization_index: int):
    return (
        spec.artifact_namespace
        / "realizations"
        / "c{:02d}_r{:03d}.json".format(class_ordinal, realization_index)
    )


def task_path(spec: RunSpec, component: str, key: TaskKey):
    return (
        spec.artifact_namespace
        / "tasks"
        / component
        / "c{:02d}_r{:03d}_b{:02d}_h{:03d}.json".format(
            key.class_ordinal,
            key.realization_index,
            key.branch_index,
            key.held_sector,
        )
    )


def _require_initialized_namespace(spec: RunSpec, run_manifest: Mapping) -> None:
    """Writers may only append to a namespace created by initialize_namespace."""
    path = spec.artifact_namespace / "run_identity.json"
    if not path.is_file():
        raise ContractError(
            "Stage-3 namespace is not initialized; task writers require "
            "initialize_namespace, which is execution-readiness gated"
        )
    stored = load_strict_json(path)
    if stored != dict(run_manifest):
        raise ContractError("passed run identity does not match the initialized namespace")
    payload = {key: value for key, value in stored.items() if key != "sha256"}
    expected = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    if stored.get("sha256") != expected:
        raise ContractError("stored run identity self-hash mismatch")


def write_realization_metadata(spec: RunSpec, run_manifest: Mapping, metadata: Mapping):
    _require_initialized_namespace(spec, run_manifest)
    class_ordinal = int(metadata["class_ordinal"])
    realization_index = int(metadata["realization_index"])
    expected_seed = spec.realization_seed(class_ordinal, realization_index)
    if int(metadata["realization_seed"]) != expected_seed:
        raise ContractError("realization metadata seed does not match RunSpec")
    protected = {"schema_version", "run_identity_sha256", "sha256"}
    if protected.intersection(metadata):
        raise ContractError("realization metadata attempts to replace protected fields")
    if set(metadata) != RAW_METADATA_FIELDS:
        raise ContractError("realization metadata payload has the wrong schema")
    payload = dict(metadata)
    payload.update({
        "schema_version": "stage3-realization/1.0",
        "run_identity_sha256": run_manifest["sha256"],
    })
    payload["sha256"] = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    create_immutable_json(
        realization_metadata_path(spec, class_ordinal, realization_index), payload,
    )
    return payload


def write_task(
    spec: RunSpec,
    run_manifest: Mapping,
    component: str,
    key: TaskKey,
    realization_metadata: Mapping,
    result: Mapping,
):
    if component not in ("screening", "recovery"):
        raise ContractError("invalid task component: {}".format(component))
    _require_initialized_namespace(spec, run_manifest)
    path = task_path(spec, component, key)
    _validate_realization_record(spec, run_manifest, key, realization_metadata, path)
    _validate_result_payload(component, key, result, path)
    payload = {
        "schema_version": spec.task_schema_version,
        "component": component,
        "component_identity_sha256": run_manifest["components"][component]["sha256"],
        "common_identity_sha256": run_manifest["components"]["common"]["sha256"],
        "run_identity_sha256": run_manifest["sha256"],
        "realization_metadata_sha256": realization_metadata["sha256"],
        "task_key": key.as_dict(),
        "status": "COMPLETED",
        "result": dict(result),
    }
    create_immutable_json(path, payload)
    return payload


def validate_task(
    spec: RunSpec,
    run_manifest: Mapping,
    component: str,
    key: TaskKey,
):
    path = task_path(spec, component, key)
    record = load_strict_json(path)
    expected_fields = {
        "schema_version", "component", "component_identity_sha256",
        "common_identity_sha256", "run_identity_sha256",
        "realization_metadata_sha256", "task_key", "status", "result",
    }
    if set(record) != expected_fields:
        raise ContractError("task record envelope schema mismatch: {}".format(path))
    if record["schema_version"] != spec.task_schema_version:
        raise ContractError("task schema version mismatch: {}".format(path))
    if record["component"] != component or record["status"] != "COMPLETED":
        raise ContractError("task component or status mismatch: {}".format(path))
    if record["task_key"] != key.as_dict():
        raise ContractError("task key mismatch: {}".format(path))
    if record["run_identity_sha256"] != run_manifest["sha256"]:
        raise ContractError("run identity mismatch: {}".format(path))
    if record["common_identity_sha256"] != run_manifest["components"]["common"]["sha256"]:
        raise ContractError("common producer identity mismatch: {}".format(path))
    if record["component_identity_sha256"] != run_manifest["components"][component]["sha256"]:
        raise ContractError("component producer identity mismatch: {}".format(path))
    metadata_path = realization_metadata_path(spec, key.class_ordinal, key.realization_index)
    metadata = load_strict_json(metadata_path)
    _validate_realization_record(spec, run_manifest, key, metadata, metadata_path)
    if record["realization_metadata_sha256"] != metadata.get("sha256"):
        raise ContractError("realization metadata identity mismatch: {}".format(path))
    result = record["result"]
    _validate_result_payload(component, key, result, path)
    return record


def verify_component(spec: RunSpec, component: str, require_complete=True):
    if not spec.has_canonical_implementation_contract():
        raise ContractError(
            "revision {} does not use canonical task schema {}".format(
                spec.protocol_revision, CANONICAL_TASK_SCHEMA_VERSION,
            )
        )
    manifest = load_strict_json(spec.artifact_namespace / "run_identity.json")
    current_manifest = run_identity(spec)
    if manifest != current_manifest:
        raise ContractError("stored run identity does not match the current frozen inputs and code")
    expected = spec.expected_task_keys(component)
    expected_paths = {task_path(spec, component, key).resolve() for key in expected}
    component_root = spec.artifact_namespace / "tasks" / component
    present_paths = {
        path.resolve() for path in component_root.rglob("*") if path.is_file()
    } if component_root.is_dir() else set()
    unexpected = sorted(str(path) for path in present_paths - expected_paths)
    if unexpected:
        raise ContractError("unexpected task record: {}".format(unexpected[0]))
    present = 0
    for key in expected:
        path = task_path(spec, component, key)
        if not path.is_file():
            continue
        validate_task(spec, manifest, component, key)
        present += 1
    missing = len(expected) - present
    if missing and require_complete:
        raise ContractError("{} task universe has {} missing records".format(component, missing))
    return {"component": component, "expected": len(expected), "present": present, "missing": missing}
