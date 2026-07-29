"""Stage-3 v3 runtime configuration over isolated strict v2 helpers."""

from contextlib import contextmanager

import stage3_v2_runtime as _base


ROOT = _base.ROOT
PROTOCOL_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v3.json"
ARCHITECTURE_PATH = ROOT / "data" / "stage3_model_architecture_decision_v3.json"
INPUT_MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest_v3.json"
AUTHORIZATION_PATH = ROOT / "data" / "stage3_v3_execution_authorization.json"
NAMESPACE = "stage3_v3"
TASK_SCHEMA_VERSION = "stage3-v3-task-record/1.0"
CODE_PATHS = (
    "scripts/stage3_v3_runtime.py",
    "scripts/stage3_v2_runtime.py",
    "scripts/stage3_synthetic_calibration_core_v3.py",
    "scripts/stage3_synthetic_calibration_core_v2.py",
    "scripts/run_stage3_synthetic_calibration_v3.py",
    "scripts/run_stage3_synthetic_calibration_v2.py",
    "scripts/stage3_joint_model.py",
    "scripts/stage3_noise_core.py",
    "scripts/run_faz5b_remediation.py",
    "scripts/run_faz5_window_grid.py",
    "scripts/run_faz6_noise_models.py",
    "scripts/faz6_noise_core.py",
    "scripts/stage3_synthetic_calibration_core.py",
    "scripts/stage3_synthetic_generator.py",
)

TaskKey = _base.TaskKey
RuntimeContractError = _base.RuntimeContractError
TASK_TYPES = _base.TASK_TYPES
JOINT_HELD_SECTOR = _base.JOINT_HELD_SECTOR
SECTORS = _base.SECTORS


@contextmanager
def _configured():
    saved = {
        "PROTOCOL_PATH": _base.PROTOCOL_PATH,
        "ARCHITECTURE_PATH": _base.ARCHITECTURE_PATH,
        "INPUT_MANIFEST_PATH": _base.INPUT_MANIFEST_PATH,
        "AUTHORIZATION_PATH": _base.AUTHORIZATION_PATH,
        "NAMESPACE": _base.NAMESPACE,
        "TASK_SCHEMA_VERSION": _base.TASK_SCHEMA_VERSION,
        "CODE_PATHS": _base.CODE_PATHS,
        "VERIFY_INPUT_MANIFEST": _base.VERIFY_INPUT_MANIFEST,
    }
    _base.PROTOCOL_PATH = PROTOCOL_PATH
    _base.ARCHITECTURE_PATH = ARCHITECTURE_PATH
    _base.INPUT_MANIFEST_PATH = INPUT_MANIFEST_PATH
    _base.AUTHORIZATION_PATH = AUTHORIZATION_PATH
    _base.NAMESPACE = NAMESPACE
    _base.TASK_SCHEMA_VERSION = TASK_SCHEMA_VERSION
    _base.CODE_PATHS = CODE_PATHS
    _base.VERIFY_INPUT_MANIFEST = True
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(_base, name, value)


def build_identity(root=ROOT):
    with _configured():
        return _base.build_identity(root)


def preflight(root=ROOT):
    from stage3_quarantine import refuse_superseded_execution

    refuse_superseded_execution(
        "scripts/stage3_v3_runtime.py:preflight",
        3,
        "SUPERSEDED_IMPLEMENTATION_DEFECTS",
    )
    with _configured():
        return _base.preflight(root)


def validate_execution_authorization(root, identity):
    with _configured():
        return _base.validate_execution_authorization(root, identity)


def expected_task_keys(protocol, task_type):
    return _base.expected_task_keys(protocol, task_type)


def checkpoint_path(root, task_type, key):
    with _configured():
        return _base.checkpoint_path(root, task_type, key)


def make_task_record(identity, task_type, key, status, result=None, error=""):
    with _configured():
        return _base.make_task_record(identity, task_type, key, status, result, error)


def validate_task_record(path, identity, task_type, expected_key):
    with _configured():
        return _base.validate_task_record(path, identity, task_type, expected_key)


def verify_namespace(root, protocol, identity, allow_partial=False):
    with _configured():
        return _base.verify_namespace(root, protocol, identity, allow_partial)


load_strict_json = _base.load_strict_json
canonical_json_bytes = _base.canonical_json_bytes
write_immutable_json = _base.write_immutable_json
