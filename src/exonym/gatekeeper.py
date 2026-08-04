"""Quality Verification Gate (QVG) engine.

``exonym advance`` promotes a candidate to the next workflow phase only after
every mandatory gate item is checked and any phase-specific gate passes.
Gate sign-offs are recorded in ``candidate/<id>/gates/`` and lifecycle events
are appended to ``candidate/<id>/lifecycle/events.jsonl``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .tracking import phase_document_path, parse_checklist
from .workspace import (
    CandidateWorkspace,
    METADATA_FILENAME,
    WORKFLOW_PHASES,
    load_candidate,
    validate_metadata,
)


class GateError(RuntimeError):
    """Raised when a phase gate blocks advancement."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_metadata(workspace: CandidateWorkspace, metadata: Dict) -> None:
    path = workspace.path / METADATA_FILENAME
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_event(workspace: CandidateWorkspace, event: Dict) -> None:
    directory = workspace.path / "lifecycle"
    directory.mkdir(parents=True, exist_ok=True)
    events = directory / "events.jsonl"
    with events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def next_phase(phase: str) -> Optional[str]:
    """Return the next workflow phase, or None for the terminal phase."""
    if phase not in WORKFLOW_PHASES:
        raise ValueError("unknown workflow phase: {0}".format(phase))
    index = WORKFLOW_PHASES.index(phase)
    if index + 1 >= len(WORKFLOW_PHASES):
        return None
    return WORKFLOW_PHASES[index + 1]


def _gate_provenance_ready(workspace: CandidateWorkspace) -> Tuple[bool, str]:
    """acquisition gate: every raw FITS product has a provenance sidecar."""
    raw_root = workspace.path / "data" / "raw"
    products = sorted(raw_root.rglob("*")) if raw_root.is_dir() else []
    fits_files = [p for p in products if p.is_file() and p.suffix.lower() in (".fits", ".fz")]
    if not fits_files:
        return False, "data/raw contains no FITS products; acquisition gate not met"
    missing = [
        p.name
        for p in fits_files
        if not p.with_name(p.stem + ".provenance.json").is_file()
    ]
    if missing:
        return False, "raw products missing provenance sidecars: {0}".format(", ".join(missing[:5]))
    return True, "{0} raw products with provenance sidecars".format(len(fits_files))


def _gate_fpp_claim(workspace: CandidateWorkspace, threshold: float = 0.01) -> Tuple[bool, str]:
    """analysis gate: an FPP claim below the preregistered threshold exists."""
    claims_root = workspace.path / "claims"
    if not claims_root.is_dir():
        return False, "no claims directory; FPP gate not met"
    for claim in sorted(claims_root.glob("*.json")):
        try:
            data = json.loads(claim.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("parameter") == "fpp" and isinstance(data.get("value"), (int, float)):
            value = float(data["value"])
            if value < threshold:
                return True, "FPP={0:.4f} < {1:.2f}".format(value, threshold)
    return False, "no FPP claim below threshold {0:.2f} found in claims/".format(threshold)


def gate_errors(workspace: CandidateWorkspace) -> List[str]:
    """Return a list of gate failures blocking the current phase."""
    metadata = workspace.metadata
    phase = metadata["workflow"]["phase"]
    errors: List[str] = []

    document = phase_document_path(workspace, phase)
    if document is not None:
        telemetry = parse_checklist(document)
        if not telemetry.exists:
            errors.append("missing gate document: {0}".format(document.relative_to(workspace.path)))
        else:
            for item in telemetry.items:
                if item.mandatory and not item.checked:
                    errors.append(
                        "unchecked mandatory item in {0}: {1}".format(
                            document.relative_to(workspace.path), item.text[:80]
                        )
                    )

    if phase == "acquisition":
        ok, detail = _gate_provenance_ready(workspace)
        if not ok:
            errors.append(detail)
    elif phase == "analysis":
        ok, detail = _gate_fpp_claim(workspace)
        if not ok:
            errors.append(detail)
    elif phase == "review":
        if metadata["lifecycle"]["state"] in ("published", "archived"):
            errors.append("candidate is already locked; no further advancement")

    return errors


def advance(workspace: CandidateWorkspace) -> Dict:
    """Validate the current gate and promote the candidate one phase.

    Advancing from ``review`` additionally locks the lifecycle to
    ``published`` when it is still ``active`` or ``paused``.

    The candidate record is re-read from disk so repeated advances always
    operate on the current state.
    """
    workspace = load_candidate(workspace.repository_root, workspace.candidate_id)
    metadata = dict(workspace.metadata)
    phase = metadata["workflow"]["phase"]
    errors = gate_errors(workspace)
    if errors:
        raise GateError("; ".join(errors))

    next_phase_name = next_phase(phase)
    if next_phase_name is None:
        raise GateError("terminal phase reached: {0}".format(phase))

    event: Dict = {
        "event": "advanced",
        "candidate_id": workspace.candidate_id,
        "from": phase,
        "to": next_phase_name,
        "timestamp": _now(),
    }
    if phase == "review":
        if metadata["lifecycle"]["state"] not in ("published", "archived"):
            metadata["lifecycle"]["state"] = "published"
            metadata["lifecycle"]["state_since"] = _now()
            metadata["lifecycle"]["reason"] = "Review gate passed; lifecycle locked"
        event["lifecycle"] = metadata["lifecycle"]["state"]
        event["to"] = "review (locked)"

    metadata["workflow"]["phase"] = next_phase_name if next_phase_name is not None else phase
    validate_metadata(metadata, workspace.candidate_id)
    _write_metadata(workspace, metadata)
    _append_event(workspace, event)

    gate_record = {
        "gate": phase,
        "candidate_id": workspace.candidate_id,
        "result": "PASS",
        "timestamp": _now(),
        "next_phase": next_phase_name,
        "event": event["event"],
    }
    gates_dir = workspace.path / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    index = len(list(gates_dir.glob("gate-*.json")))
    (gates_dir / "gate-{0:03d}-{1}.json".format(index, phase)).write_text(
        json.dumps(gate_record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return event
