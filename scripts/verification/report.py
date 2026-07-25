"""JSON report generation and log file formatting."""

from __future__ import annotations

import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import ROOT, Verification

REPORT_PATH = ROOT / "outputs" / "final_calculation_verification_report.json"
LOG_PATH = ROOT / "outputs" / "final_calculation_verification.log"


def write_verification_report(
    audit: Verification,
    started: float,
    snapshot_before: tuple[dict[str, str], str],
    snapshot_after: tuple[dict[str, str], str],
    git_before: str,
    git_after: str,
) -> dict[str, Any]:
    """Compile verification results, verify file mutations, and write JSON report + log."""
    changed = sorted({
        *set(snapshot_before[0]).symmetric_difference(snapshot_after[0]),
        *(path for path in set(snapshot_before[0]).intersection(snapshot_after[0])
          if snapshot_before[0][path] != snapshot_after[0][path]),
    })
    mutation_ok = not changed
    if not mutation_ok:
        audit.check(
            "provenance",
            "no_calculation_artifact_mutation_during_suite",
            False,
            ", ".join(changed[:20]),
        )

    n_ok = sum(c["ok"] for c in audit.checks)
    n_fail = len(audit.checks) - n_ok
    groups: dict[str, dict[str, int]] = {}
    for check in audit.checks:
        group = groups.setdefault(check["group"], {"total": 0, "passed": 0, "failed": 0})
        group["total"] += 1
        group["passed" if check["ok"] else "failed"] += 1

    status = "PASS" if n_fail == 0 else "FAIL"

    command_log = []
    for command in audit.commands:
        command_log.append("$ " + " ".join(command["command"]))
        command_log.append(command["stdout"])
        if command["stderr"]:
            command_log.append(command["stderr"])
    LOG_PATH.write_text("\n".join(command_log), encoding="utf-8")

    report = {
        "schema_version": "2.0",
        "work_package": "FINAL_CALCULATION_VERIFICATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Calculation-only verification; manuscript, PDF, and writing-quality audit excluded.",
        "status": status,
        "verification_interpretation": (
            "Frozen calculation artifacts are internally consistent with independently recomputed quantities. "
            "Expected scientific gates remain closed."
            if status == "PASS" else
            "At least one calculation, test, or frozen-artifact consistency check failed."
        ),
        "publication_ready": False,
        "expected_closed_gates": [
            "native-cadence geometry adoption", "calibrated PRF localization",
            "formal population false-positive probability", "statistical validation",
            "planet confirmation", "Stage-3 K3 real-data adoption",
        ],
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
        },
        "source_snapshot": {
            "before_digest": snapshot_before[1],
            "after_digest": snapshot_after[1],
            "file_count": len(snapshot_before[0]),
            "unchanged_during_run": mutation_ok,
            "changed_paths": changed,
            "git_status_before": git_before,
            "git_status_after": git_after,
        },
        "summary": {
            "checks_total": len(audit.checks),
            "checks_passed": n_ok,
            "checks_failed": n_fail,
            "groups": groups,
        },
        "commands": [
            {k: v for k, v in cmd.items() if k not in {"stdout", "stderr"}}
            for cmd in audit.commands
        ],
        "command_log": str(LOG_PATH.relative_to(ROOT)),
        "checks": audit.checks,
        "limitations": audit.warnings,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
