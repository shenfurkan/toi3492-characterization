"""Strict checkpoint and identity helpers for the Stage-3 v2 runner.

The runtime is deliberately independent of the quarantined v1 CSV/checkpoint
format.  Task records are immutable JSON objects; aggregate CSV files are
derived only after the complete task-key universe has been verified.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v2.json"
ARCHITECTURE_PATH = ROOT / "data" / "stage3_model_architecture_decision_v2.json"
INPUT_MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest.json"
AUTHORIZATION_PATH = ROOT / "data" / "stage3_v2_execution_authorization.json"
V2_ROOT = ROOT / "outputs" / "stage3_v2"
CHECKPOINT_ROOT = V2_ROOT / "checkpoints"
NAMESPACE = "stage3_v2"
VERIFY_INPUT_MANIFEST = False
TASK_SCHEMA_VERSION = "stage3-v2-task-record/1.0"
TASK_TYPES = ("screening", "joint")
JOINT_HELD_SECTOR = -1
SECTORS = (37, 63, 64, 90, 99, 100)

CODE_PATHS = (
    "scripts/stage3_v2_runtime.py",
    "scripts/stage3_synthetic_calibration_core_v2.py",
    "scripts/stage3_joint_model.py",
    "scripts/stage3_noise_core.py",
    "scripts/run_stage3_synthetic_calibration_v2.py",
    "scripts/run_faz5b_remediation.py",
    "scripts/run_faz5_window_grid.py",
    "scripts/run_faz6_noise_models.py",
    "scripts/faz6_noise_core.py",
    "scripts/stage3_synthetic_calibration_core.py",
    "scripts/stage3_synthetic_generator.py",
)

TASK_RESULT_REQUIRED_FIELDS = {
    "screening": {
        "class_name", "model_id", "mask_id", "cell_id", "held_sector",
        "k0_score", "m1_score", "delta_elpd", "k0_objective", "m1_objective",
        "k0_boundary_count", "m1_boundary_count", "baseline_draws",
        "injected_geometry", "sector_noise", "gap_edge_event_recovery_flags",
        "latent_sha256", "realization_seed",
    },
    "joint": {
        "class_name", "model_id", "mask_id", "cell_id",
        "objective_h0", "objective_h1", "delta_map", "h1_stationary",
        "h1_recovered_geometry", "h1_intervals", "h1_boundary_count",
        "h0_boundary_count", "baseline_draws", "injected_geometry", "sector_noise",
        "gap_edge_event_recovery_flags", "injected_t14_hours", "h1_attempts",
        "h1_multistart_objective_spread", "h1_multistart_unit_parameter_spread",
        "ingress_egress_rms_residual_mm_s", "weighted_residual_beta_max",
        "optimizer_no_op_count", "optimizer_local_mode_count",
        "latent_sha256", "realization_seed",
    },
}


class RuntimeContractError(RuntimeError):
    """Raised when a v2 identity, task, or checkpoint contract is invalid."""


@dataclass(frozen=True)
class TaskKey:
    class_index: int
    realization_index: int
    branch_index: int
    held_sector: int

    def as_dict(self) -> dict[str, int]:
        return {
            "class_index": int(self.class_index),
            "realization_index": int(self.realization_index),
            "branch_index": int(self.branch_index),
            "held_sector": int(self.held_sector),
        }


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_records(value):
    if isinstance(value, list):
        for item in value:
            yield from _manifest_records(item)
    elif isinstance(value, Mapping):
        if {"path", "size_bytes", "sha256"}.issubset(value):
            yield value
        for item in value.values():
            yield from _manifest_records(item)


def verify_input_manifest(root: Path, manifest_path: Path):
    manifest = load_strict_json(manifest_path)
    records = list(_manifest_records(manifest.get("input_groups", {})))
    seen = set()
    for record in records:
        relative = record["path"]
        if not isinstance(relative, str) or relative in seen:
            raise RuntimeContractError("input manifest path is invalid or duplicated")
        seen.add(relative)
        path = (root / relative).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise RuntimeContractError("input manifest file is missing: {}".format(relative))
        if int(record["size_bytes"]) != path.stat().st_size:
            raise RuntimeContractError("input manifest size mismatch: {}".format(relative))
        if record["sha256"] != sha256_file(path):
            raise RuntimeContractError("input manifest hash mismatch: {}".format(relative))
    if not records:
        raise RuntimeContractError("input manifest contains no input records")
    return {record["path"] for record in records}


def _reject_constant(value: str):
    raise RuntimeContractError("non-standard JSON constant: {}".format(value))


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeContractError("duplicate JSON key: {}".format(key))
        result[key] = value
    return result


def _strict_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeContractError("non-finite JSON number: {}".format(value))
    return result


def load_strict_json(path: Path):
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
        parse_float=_strict_float,
    )


def _finite(value, location="$", seen=None):
    """Reject non-finite values before they can enter a task record."""
    if seen is None:
        seen = set()
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise RuntimeContractError("non-finite value at {}".format(location))
        return
    if isinstance(value, Mapping):
        marker = id(value)
        if marker in seen:
            raise RuntimeContractError("cyclic mapping at {}".format(location))
        seen.add(marker)
        for key, item in value.items():
            _finite(item, "{}[{}]".format(location, repr(key)), seen)
        seen.remove(marker)
        return
    if isinstance(value, (list, tuple)):
        marker = id(value)
        if marker in seen:
            raise RuntimeContractError("cyclic sequence at {}".format(location))
        seen.add(marker)
        for index, item in enumerate(value):
            _finite(item, "{}[{}]".format(location, index), seen)
        seen.remove(marker)


def canonical_json_bytes(payload) -> bytes:
    _finite(payload)
    try:
        text = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeContractError("payload is not strict JSON: {}".format(exc)) from exc
    return (text + "\n").encode("utf-8")


def write_immutable_json(path: Path, payload) -> bool:
    """Atomically create a record, allowing only an identical retry.

    Returns True when a new file was created and False when the exact same
    bytes already existed.
    """
    encoded = canonical_json_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise FileExistsError("immutable checkpoint already differs: {}".format(path))
        return False
    temporary = path.with_name(".{}-{}.tmp".format(path.name, os.getpid()))
    try:
        temporary.write_bytes(encoded)
        try:
            os.replace(str(temporary), str(path))
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise FileExistsError(
                    "concurrent checkpoint differs: {}".format(path)
                )
            return False
    finally:
        temporary.unlink(missing_ok=True)
    return True


def _package_version(name: str):
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def environment_identity() -> dict:
    details = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": {
            name: _package_version(name)
            for name in ("numpy", "pandas", "scipy", "celerite", "batman-package")
        },
    }
    encoded = canonical_json_bytes(details)
    return {"sha256": sha256_bytes(encoded), **details}


def code_identity(root: Path = ROOT) -> dict:
    files = []
    for relative in CODE_PATHS:
        path = root / relative
        if not path.is_file():
            raise RuntimeContractError("required code identity file is missing: {}".format(relative))
        files.append({"path": relative, "sha256": sha256_file(path)})
    encoded = canonical_json_bytes(files)
    return {"sha256": sha256_bytes(encoded), "files": files}


def build_identity(root: Path = ROOT) -> dict:
    protocol = root / PROTOCOL_PATH.relative_to(ROOT)
    architecture = root / ARCHITECTURE_PATH.relative_to(ROOT)
    input_manifest = root / INPUT_MANIFEST_PATH.relative_to(ROOT)
    for path in (protocol, architecture, input_manifest):
        if not path.is_file():
            raise RuntimeContractError("required identity input is missing: {}".format(path))
    if VERIFY_INPUT_MANIFEST:
        verify_input_manifest(root, input_manifest)
    return {
        "protocol_v2_sha256": sha256_file(protocol),
        "architecture_v2_sha256": sha256_file(architecture),
        "input_manifest_sha256": sha256_file(input_manifest),
        "code_identity": code_identity(root),
        "environment_identity": environment_identity(),
        "task_schema_version": TASK_SCHEMA_VERSION,
    }


def validate_execution_authorization(root: Path, identity: Mapping) -> tuple[dict, bool]:
    """Validate the separate review record without changing frozen v2 files."""
    path = root / "data" / AUTHORIZATION_PATH.name
    authorization = load_strict_json(path)
    required = {
        "schema_version", "record_type", "status", "scope",
        "protocol_v2_sha256", "architecture_v2_sha256", "input_manifest_sha256",
        "code_identity_sha256", "review", "real_data_fit_authorized", "phase_7_authorized",
    }
    if set(authorization) != required:
        raise RuntimeContractError("execution authorization schema mismatch")
    if authorization["schema_version"] != "1.0":
        raise RuntimeContractError("unsupported execution authorization schema")
    expected_record_type = "STAGE3_{}_EXECUTION_AUTHORIZATION".format(
        NAMESPACE.rsplit("_", 1)[-1].upper()
    )
    if authorization["record_type"] != expected_record_type:
        raise RuntimeContractError("invalid execution authorization record type")
    for field in ("protocol_v2_sha256", "architecture_v2_sha256", "input_manifest_sha256"):
        if authorization[field] != identity[field]:
            raise RuntimeContractError("execution authorization hash mismatch: {}".format(field))
    review = authorization["review"]
    if not isinstance(review, Mapping):
        raise RuntimeContractError("execution authorization review is not an object")
    review_required = {
        "independent_second_party", "reviewer_id", "reviewed_utc", "decision", "notes",
    }
    if set(review) != review_required:
        raise RuntimeContractError("execution authorization review schema mismatch")
    if authorization["scope"] != "SYNTHETIC_CALIBRATION_ONLY":
        raise RuntimeContractError("execution authorization scope is not synthetic-only")
    if authorization["real_data_fit_authorized"] is not False:
        raise RuntimeContractError("execution authorization cannot authorize real data")
    if authorization["phase_7_authorized"] is not False:
        raise RuntimeContractError("execution authorization cannot authorize Phase 7")
    approved = (
        authorization["status"] == "APPROVED"
        and review["independent_second_party"] is True
        and isinstance(review["reviewer_id"], str)
        and bool(review["reviewer_id"].strip())
        and isinstance(review["reviewed_utc"], str)
        and bool(review["reviewed_utc"].strip())
        and review["decision"] == "APPROVED"
    )
    if authorization["status"] not in ("PENDING_INDEPENDENT_REVIEW", "APPROVED"):
        raise RuntimeContractError("unknown execution authorization status")
    if approved:
        authorized_code = authorization.get("code_identity_sha256")
        if authorized_code != identity["code_identity"]["sha256"]:
            raise RuntimeContractError("execution authorization code identity mismatch")
    return authorization, approved


def _class_specs(protocol: Mapping) -> tuple[Mapping, ...]:
    classes = tuple(protocol.get("simulation_classes", ()))
    if len(classes) != 14 or sum(int(item["requested_count"]) for item in classes) != 235:
        raise RuntimeContractError("v2 protocol class universe is not 14/235")
    if [int(item["class_index"]) for item in classes] != list(range(14)):
        raise RuntimeContractError("v2 class indices are not contiguous")
    return classes


def expected_task_keys(protocol: Mapping, task_type: str) -> tuple[TaskKey, ...]:
    if task_type not in TASK_TYPES:
        raise ValueError("unknown v2 task type: {}".format(task_type))
    held = SECTORS if task_type == "screening" else (JOINT_HELD_SECTOR,)
    keys = []
    for spec in _class_specs(protocol):
        for realization_index in range(int(spec["requested_count"])):
            for branch_index in range(24):
                for held_sector in held:
                    keys.append(TaskKey(
                        int(spec["class_index"]), realization_index,
                        branch_index, held_sector,
                    ))
    return tuple(keys)


def checkpoint_path(root: Path, task_type: str, key: TaskKey) -> Path:
    if task_type not in TASK_TYPES:
        raise ValueError("unknown v2 task type: {}".format(task_type))
    return (
        root / "outputs" / NAMESPACE / "checkpoints" / task_type
        / "c{:02d}_r{:03d}_b{:02d}_h{:03d}.json".format(
            key.class_index, key.realization_index, key.branch_index,
            key.held_sector,
        )
    )


def _same_identity(record: Mapping, identity: Mapping) -> bool:
    return all(record.get(field) == value for field, value in identity.items())


def make_task_record(identity: Mapping, task_type: str, key: TaskKey,
                     status: str, result=None, error: str = "") -> dict:
    if status not in ("completed", "failed"):
        raise ValueError("invalid task status: {}".format(status))
    if status == "completed" and not isinstance(result, Mapping):
        raise ValueError("completed task requires a mapping result")
    if status == "failed" and (not error or result is not None):
        raise ValueError("failed task requires an error and no result")
    record = {
        **dict(identity),
        "record_type": "STAGE3_{}_TASK_RECORD".format(
            NAMESPACE.rsplit("_", 1)[-1].upper()
        ),
        "task_type": task_type,
        "task_key": key.as_dict(),
        "status": status,
        "result": dict(result) if result is not None else None,
        "error": str(error) if status == "failed" else "",
    }
    canonical_json_bytes(record)
    return record


def _validate_task_key(value) -> TaskKey:
    if not isinstance(value, Mapping):
        raise RuntimeContractError("task_key is not an object")
    expected = {"class_index", "realization_index", "branch_index", "held_sector"}
    if set(value) != expected:
        raise RuntimeContractError("task_key fields do not match the v2 schema")
    names = ("class_index", "realization_index", "branch_index", "held_sector")
    if any(type(value[name]) is not int for name in names):
        raise RuntimeContractError("task_key contains a non-integer")
    return TaskKey(*(value[name] for name in names))


def validate_task_record(path: Path, identity: Mapping, task_type: str,
                         expected_key: TaskKey) -> dict:
    record = load_strict_json(path)
    required = set(identity) | {
        "record_type", "task_type", "task_key", "status", "result", "error",
    }
    if set(record) != required:
        raise RuntimeContractError("record schema mismatch: {}".format(path))
    if not _same_identity(record, identity):
        raise RuntimeContractError("checkpoint identity mismatch: {}".format(path))
    expected_record_type = "STAGE3_{}_TASK_RECORD".format(
        NAMESPACE.rsplit("_", 1)[-1].upper()
    )
    if record["record_type"] != expected_record_type:
        raise RuntimeContractError("invalid record type: {}".format(path))
    if record["task_type"] != task_type:
        raise RuntimeContractError("task type mismatch: {}".format(path))
    if _validate_task_key(record["task_key"]) != expected_key:
        raise RuntimeContractError("task key mismatch: {}".format(path))
    if record["status"] == "completed":
        if not isinstance(record["result"], Mapping) or record["error"] != "":
            raise RuntimeContractError("completed record payload is invalid: {}".format(path))
        result = record["result"]
        expected_fields = TASK_RESULT_REQUIRED_FIELDS[task_type]
        if set(result) != expected_fields:
            missing = expected_fields - set(result)
            extra = set(result) - expected_fields
            raise RuntimeContractError(
                "completed result schema mismatch; missing={}, extra={}: {}".format(
                    sorted(missing), sorted(extra), path,
                )
            )
        def finite_number(value):
            return type(value) in (int, float) and math.isfinite(float(value))

        numeric_fields = (
            ("k0_score", "m1_score", "delta_elpd", "k0_objective", "m1_objective")
            if task_type == "screening" else
            ("objective_h0", "objective_h1", "delta_map",
             "h1_multistart_objective_spread", "h1_multistart_unit_parameter_spread",
             "ingress_egress_rms_residual_mm_s", "weighted_residual_beta_max")
        )
        for field in numeric_fields:
            if type(result[field]) not in (int, float) or not math.isfinite(float(result[field])):
                raise RuntimeContractError("result field is not finite numeric: {}".format(path))
        for field in ("realization_seed", "k0_boundary_count", "m1_boundary_count"):
            if field in result and type(result[field]) is not int:
                raise RuntimeContractError("result field is not an integer: {}".format(path))
        string_fields = (
            ("class_name", "model_id", "mask_id", "cell_id", "latent_sha256")
        )
        for field in string_fields:
            if type(result[field]) is not str or not result[field]:
                raise RuntimeContractError("result field is not a non-empty string: {}".format(path))
        integer_fields = (
            ("held_sector", "realization_seed", "k0_boundary_count", "m1_boundary_count")
            if task_type == "screening" else
            ("realization_seed", "h1_boundary_count", "h0_boundary_count",
             "optimizer_no_op_count", "optimizer_local_mode_count")
        )
        if any(type(result[field]) is not int or result[field] < 0 for field in integer_fields):
            raise RuntimeContractError("result integer field is invalid: {}".format(path))
        mapping_fields = (
            ("baseline_draws", "sector_noise", "gap_edge_event_recovery_flags")
            if task_type == "screening" else
            ("h1_recovered_geometry", "h1_intervals", "baseline_draws", "sector_noise",
             "gap_edge_event_recovery_flags")
        )
        for field in mapping_fields:
            if not isinstance(result[field], Mapping):
                raise RuntimeContractError("result field is not a mapping: {}".format(path))
            if any(type(key) is not str for key in result[field]):
                raise RuntimeContractError("result mapping key is not a string: {}".format(path))
        if result["injected_geometry"] is not None and not isinstance(
                result["injected_geometry"], Mapping):
            raise RuntimeContractError("injected geometry is not a mapping or null: {}".format(path))
        if task_type == "joint":
            if result["injected_t14_hours"] is not None and not finite_number(
                    result["injected_t14_hours"]):
                raise RuntimeContractError("injected T14 is invalid: {}".format(path))
            if (type(result["h1_attempts"]) is not list or
                    len(result["h1_attempts"]) != 3):
                raise RuntimeContractError("optimizer attempts schema mismatch: {}".format(path))
            for attempt in result["h1_attempts"]:
                if (not isinstance(attempt, Mapping)
                        or set(attempt) != {"success", "message", "iterations", "objective", "movement_norm"}
                        or type(attempt["success"]) is not bool
                        or type(attempt["message"]) is not str
                        or type(attempt["iterations"]) is not int
                        or not finite_number(attempt["objective"])
                        or not finite_number(attempt["movement_norm"])):
                    raise RuntimeContractError("optimizer attempt is invalid: {}".format(path))
        if len(result["latent_sha256"]) != 64:
            raise RuntimeContractError("latent hash has the wrong length: {}".format(path))
        try:
            int(result["latent_sha256"], 16)
        except ValueError as exc:
            raise RuntimeContractError("latent hash is not hexadecimal: {}".format(path)) from exc

        def validate_geometry(value, field):
            if value is None:
                return
            if set(value) != {"rp_rs", "a_rs", "impact_parameter"}:
                raise RuntimeContractError("{} geometry schema mismatch: {}".format(field, path))
            if not all(finite_number(value[name]) for name in value):
                raise RuntimeContractError("{} geometry is non-finite: {}".format(field, path))

        validate_geometry(result["injected_geometry"], "injected")
        if task_type == "joint":
            validate_geometry(result["h1_recovered_geometry"], "recovered")
            if set(result["h1_intervals"]) != {
                    "rp_rs", "a_rs", "impact_parameter", "t14_hours"}:
                raise RuntimeContractError("joint interval schema mismatch: {}".format(path))
            if any(
                    type(values) is not list or len(values) != 4
                    or not all(finite_number(value) for value in values)
                    for values in result["h1_intervals"].values()
            ):
                raise RuntimeContractError("joint intervals are invalid: {}".format(path))
        baseline = result["baseline_draws"]
        if any(
                type(values) is not list or len(values) != 3
                or not all(finite_number(value) for value in values)
                for values in baseline.values()
        ):
            raise RuntimeContractError("baseline draw schema is invalid: {}".format(path))
        for sector_draw in result["sector_noise"].values():
            if not isinstance(sector_draw, Mapping) or any(
                    not isinstance(name, str) or not finite_number(value)
                    for name, value in sector_draw.items()
            ):
                raise RuntimeContractError("sector noise schema is invalid: {}".format(path))
        if task_type == "joint" and result.get("h1_stationary") is not True:
            raise RuntimeContractError("joint task is not stationary: {}".format(path))
        flags = result["gap_edge_event_recovery_flags"]
        if any(type(value) is not bool for value in flags.values()):
            raise RuntimeContractError("gap/edge recovery flags are not boolean: {}".format(path))
        if expected_key.class_index == 13 and set(flags) != {"S037-E002", "S099-E189"}:
            raise RuntimeContractError("C14 gap/edge flags are incomplete: {}".format(path))
        if expected_key.class_index != 13 and flags:
            raise RuntimeContractError("non-C14 task contains gap/edge flags: {}".format(path))
        _finite(result, "$.result")
    elif record["status"] == "failed":
        if record["result"] is not None or not record["error"]:
            raise RuntimeContractError("failed record payload is invalid: {}".format(path))
    else:
        raise RuntimeContractError("unknown task status: {}".format(path))
    return record


def verify_namespace(root: Path, protocol: Mapping, identity: Mapping,
                     allow_partial: bool = False) -> dict:
    records = {}
    checkpoint_root = root / "outputs" / NAMESPACE / "checkpoints"
    expected_paths = set()
    for task_type in TASK_TYPES:
        expected_paths.update(
            checkpoint_path(root, task_type, key)
            for key in expected_task_keys(protocol, task_type)
        )
    actual_paths = set(checkpoint_root.rglob("*.json")) if checkpoint_root.exists() else set()
    unexpected_paths = actual_paths - expected_paths
    if unexpected_paths:
        raise RuntimeContractError(
            "unexpected checkpoint file(s): {}".format(
                sorted(str(path) for path in unexpected_paths)
            )
        )
    failures = []
    for task_type in TASK_TYPES:
        expected = {
            key: checkpoint_path(root, task_type, key)
            for key in expected_task_keys(protocol, task_type)
        }
        for key, path in expected.items():
            if not path.is_file():
                continue
            record = validate_task_record(path, identity, task_type, key)
            if key in records:
                raise RuntimeContractError("duplicate task key: {}".format(key))
            records[(task_type, key)] = record
            if record["status"] == "failed":
                failures.append((task_type, key))
    expected_count = sum(len(expected_task_keys(protocol, item)) for item in TASK_TYPES)
    missing = expected_count - len(records)
    if missing and not allow_partial:
        raise RuntimeContractError("v2 checkpoint universe is incomplete: {} missing".format(missing))
    if failures:
        raise RuntimeContractError("v2 checkpoint universe contains {} failed task(s)".format(len(failures)))
    return {
        "expected_records": expected_count,
        "verified_records": len(records),
        "missing_records": missing,
        "complete": missing == 0,
    }


def preflight(root: Path = ROOT) -> dict:
    from stage3_quarantine import refuse_superseded_execution

    refuse_superseded_execution(
        "scripts/stage3_v2_runtime.py:preflight",
        2,
        "SUPERSEDED_REVIEW_FAILED",
    )
    protocol = load_strict_json(root / PROTOCOL_PATH.relative_to(ROOT))
    architecture = load_strict_json(root / ARCHITECTURE_PATH.relative_to(ROOT))
    if protocol.get("status") != "PASS" or architecture.get("status") != "PASS":
        raise RuntimeContractError("v2 protocol or architecture is not PASS")
    identity = build_identity(root)
    authorization, execution_authorized = validate_execution_authorization(root, identity)
    return {
        "protocol": protocol,
        "architecture": architecture,
        "identity": identity,
        "authorization": authorization,
        "expected_screening_records": len(expected_task_keys(protocol, "screening")),
        "expected_joint_records": len(expected_task_keys(protocol, "joint")),
        "expected_joint_fits": 2 * len(expected_task_keys(protocol, "joint")),
        "execution_authorized": execution_authorized,
    }
