"""Deterministic, independently rerunnable Stage-3 reduction."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from .contracts import ContractError, RunSpec
from .identity import component_identity
from .jsonio import create_immutable_json, load_strict_json
from .metrics import (
    derive_null_threshold,
    evaluate_development_gates,
    nominal_geometry_metrics,
    realization_selection_scores,
    selection_metrics,
)
from .runtime import require_execution_ready, task_path, verify_component


def _load_task_rows(spec: RunSpec, component: str):
    rows = []
    for key in spec.expected_task_keys(component):
        record = load_strict_json(task_path(spec, component, key))
        rows.append({
            **record["result"],
            **key.as_dict(),
        })
    return pd.DataFrame(rows)


def _normalize_recovery(frame: pd.DataFrame):
    rows = []
    for record in frame.to_dict("records"):
        injected = record.pop("injected_geometry")
        recovered = record.pop("recovered_geometry")
        intervals = record.pop("intervals")
        row = record
        for parameter in ("rp_rs", "a_rs", "impact_parameter", "t14_hours"):
            row["injected_{}".format(parameter)] = (
                None if injected is None else injected[parameter]
            )
            row["recovered_{}".format(parameter)] = recovered[parameter]
            values = intervals[parameter]
            for suffix, value in zip(("q025", "q16", "q84", "q975"), values):
                row["{}_{}".format(parameter, suffix)] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _immutable_csv(path: Path, frame: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise FileExistsError("immutable derived artifact differs: {}".format(path))
        return False
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return True


def reduce_completed_run(spec: RunSpec):
    readiness = require_execution_ready(spec)
    screening_status = verify_component(spec, "screening", require_complete=True)
    recovery_status = verify_component(spec, "recovery", require_complete=True)
    screening = _load_task_rows(spec, "screening").sort_values(
        ["class_ordinal", "realization_index", "branch_index", "held_sector"]
    )
    recovery = _normalize_recovery(_load_task_rows(spec, "recovery")).sort_values(
        ["class_ordinal", "realization_index", "branch_index"]
    )
    selection_rows = realization_selection_scores(screening)
    selection_summary = selection_metrics(selection_rows)
    geometry_rows, geometry_summary = nominal_geometry_metrics(recovery)
    null_summary = derive_null_threshold(recovery)
    protocol = spec.load_protocol()
    gate = evaluate_development_gates(
        selection_summary,
        geometry_summary,
        null_summary,
        protocol["provisional_gate_thresholds"],
    )
    reducer_identity = component_identity(spec, "reducer")
    summary = {
        "schema_version": "stage3-calibration-summary/1.0",
        "protocol_revision": spec.protocol_revision,
        "run_identity_sha256": readiness["run_identity"]["sha256"],
        "authorization_sha256": readiness["authorization_sha256"],
        "registry_status": spec.status,
        "scientific_use": spec.scientific_use,
        "reducer_identity": reducer_identity,
        "screening_status": screening_status,
        "recovery_status": recovery_status,
        "gate_status": gate.status,
        "gate_checks": dict(gate.checks),
        "metrics": dict(gate.metrics),
        "real_data_fit_authorized": False,
        "phase_7_authorized": False,
    }
    root = spec.artifact_namespace / "derived"
    _immutable_csv(root / "screening_detail.csv", screening)
    _immutable_csv(root / "recovery_detail.csv", recovery)
    _immutable_csv(root / "realization_selection.csv", selection_rows)
    _immutable_csv(root / "nominal_geometry.csv", geometry_rows)
    create_immutable_json(root / "threshold_calibration.json", null_summary)
    create_immutable_json(root / "calibration_summary.json", summary)
    return summary
