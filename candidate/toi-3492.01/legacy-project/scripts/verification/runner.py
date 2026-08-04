"""Main runner entrypoint for verification suite."""

from __future__ import annotations

import subprocess
import sys
import time

from .checkers import ALL_GROUPS
from .core import ROOT, Verification
from .report import REPORT_PATH, write_verification_report
from .snapshot import capture_snapshot


def _run_suite_commands(audit: Verification) -> None:
    audit.run_command("compileall", [sys.executable, "-m", "compileall", "-q", "scripts", "tests"])
    audit.run_command(
        "pytest_calculation_only",
        [
            sys.executable, "-m", "pytest", "-q", "--tb=short",
            "-m", "not integration",
            "--deselect", "tests/test_artifacts.py::test_manuscript_math_audit_is_current_and_passes",
        ],
    )


def run_all_verifications() -> int:
    started = time.monotonic()
    print("=== FINAL CALCULATION VERIFICATION ===", flush=True)
    print("Scope: numerical artifacts and independent recomputations only", flush=True)
    snapshot_before = capture_snapshot()
    git_before = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout

    audit = Verification()
    _run_suite_commands(audit)

    for name, function in ALL_GROUPS:
        audit.run_group(name, function)

    snapshot_after = capture_snapshot()
    git_after = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout

    report = write_verification_report(
        audit, started, snapshot_before, snapshot_after, git_before, git_after
    )

    print(f"=== FINAL CALCULATION VERIFICATION: {report['status']} ===", flush=True)
    print(
        f"{report['summary']['checks_passed']}/{report['summary']['checks_total']} checks passed; report: {REPORT_PATH}",
        flush=True,
    )

    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run_all_verifications())
