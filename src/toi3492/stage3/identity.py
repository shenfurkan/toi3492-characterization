"""Component-scoped identities that avoid invalidating unrelated checkpoints."""

from __future__ import annotations

import hashlib
import os
import platform
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Mapping, Tuple

from .contracts import ContractError, RunSpec
from .jsonio import canonical_json_bytes, load_strict_json


COMPONENT_PATHS = {
    "common": (
        "src/toi3492/stage3/contracts.py",
        "src/toi3492/stage3/errors.py",
        "src/toi3492/stage3/jsonio.py",
        "src/toi3492/stage3/identity.py",
        "src/toi3492/stage3/inputs.py",
        "src/toi3492/stage3/simulation.py",
        "src/toi3492/stage3/runtime.py",
        "scripts/run_faz5b_remediation.py",
        "scripts/run_faz5_window_grid.py",
        "scripts/faz6_noise_core.py",
    ),
    "screening": (
        "src/toi3492/stage3/screening.py",
        "scripts/stage3_noise_core.py",
        "scripts/faz6_noise_core.py",
        "scripts/run_faz5_window_grid.py",
        "scripts/run_faz5b_remediation.py",
        "scripts/run_faz6_noise_models.py",
    ),
    "recovery": (
        "src/toi3492/stage3/recovery.py",
        "scripts/stage3_joint_model.py",
        "scripts/stage3_noise_core.py",
        "scripts/faz6_noise_core.py",
        "scripts/run_faz5_window_grid.py",
    ),
    "reducer": (
        "src/toi3492/stage3/metrics.py",
        "src/toi3492/stage3/reducer.py",
    ),
    "scheduler": (
        "src/toi3492/stage3/executor.py",
        "src/toi3492/stage3/cli.py",
        "scripts/run_stage3.py",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name: str):
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


_THREAD_LIMIT_VARIABLES = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def normalize_thread_limits() -> None:
    """Ensure thread-limit variables are set to '1' if not already present.

    Call this before computing environment_identity() and at executor startup
    so the identity value is stable regardless of import order.
    """
    for name in _THREAD_LIMIT_VARIABLES:
        os.environ.setdefault(name, "1")


def environment_identity() -> Mapping:
    normalize_thread_limits()
    details = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": {
            name: _package_version(name)
            for name in ("numpy", "pandas", "scipy", "celerite", "batman-package")
        },
        "thread_limits": {
            name: os.environ.get(name)
            for name in _THREAD_LIMIT_VARIABLES
        },
    }
    return {"sha256": hashlib.sha256(canonical_json_bytes(details)).hexdigest(), **details}


def verify_input_manifest(spec: RunSpec) -> Tuple[str, ...]:
    manifest = load_strict_json(spec.input_manifest_path)
    records = []

    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, Mapping):
            if {"path", "size_bytes", "sha256"}.issubset(value):
                records.append(value)
            for item in value.values():
                visit(item)

    visit(manifest.get("input_groups", {}))
    seen = set()
    for record in records:
        relative = record["path"]
        if not isinstance(relative, str) or relative in seen:
            raise ContractError("input manifest contains an invalid or duplicate path")
        seen.add(relative)
        path = (spec.root / relative).resolve()
        if spec.root not in path.parents or not path.is_file():
            raise ContractError("input manifest file is missing: {}".format(relative))
        if path.stat().st_size != int(record["size_bytes"]):
            raise ContractError("input manifest size mismatch: {}".format(relative))
        if sha256_file(path) != record["sha256"]:
            raise ContractError("input manifest hash mismatch: {}".format(relative))
    if not records:
        raise ContractError("input manifest contains no files")
    return tuple(sorted(seen))


def component_identity(spec: RunSpec, component: str) -> Mapping:
    if component not in COMPONENT_PATHS:
        raise ContractError("unknown identity component: {}".format(component))
    records = []
    for relative in COMPONENT_PATHS[component]:
        path = spec.root / relative
        if not path.is_file():
            raise ContractError("identity source is missing: {}".format(relative))
        records.append({"path": relative, "sha256": sha256_file(path)})
    return {
        "component": component,
        "sha256": hashlib.sha256(canonical_json_bytes(records)).hexdigest(),
        "files": records,
    }


def code_identity_sha256(components: Mapping) -> str:
    payload = {
        name: components[name]["sha256"]
        for name in sorted(components)
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def run_identity(spec: RunSpec) -> Mapping:
    verify_input_manifest(spec)
    components = {
        name: component_identity(spec, name)
        for name in sorted(COMPONENT_PATHS)
    }
    payload = {
        "protocol_revision": spec.protocol_revision,
        "protocol_sha256": sha256_file(spec.protocol_path),
        "architecture_sha256": sha256_file(spec.architecture_path),
        "input_manifest_sha256": sha256_file(spec.input_manifest_path),
        "task_schema_version": spec.task_schema_version,
        "seed_base": spec.seed_base,
        "artifact_namespace": spec.artifact_namespace.relative_to(spec.root).as_posix(),
        "components": components,
        "code_identity_sha256": code_identity_sha256(components),
        "environment": environment_identity(),
    }
    return {"sha256": hashlib.sha256(canonical_json_bytes(payload)).hexdigest(), **payload}
