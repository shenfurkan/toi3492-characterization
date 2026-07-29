"""Run the reproducible, gate-controlled Stage-3 preparation pipeline.

This orchestrator deliberately stops before any real-data fit.  It runs the
full frozen synthetic universe with resumable checkpoints, verifies the
resulting artifact counts, and records the next approval gate.  Publication
packaging is only allowed after the scientific gates and final audits close.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
STATUS_PATH = ROOT / "outputs" / "stage3_publication_pipeline_status.json"


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_counts():
    protocol = _load_json(ROOT / "data" / "stage3_synthetic_calibration_protocol.json")
    classes = protocol["simulation_classes"]
    realizations = sum(int(item["requested_count"]) for item in classes)
    return {
        "realizations": realizations,
        "branches": 24,
        "sectors": 6,
        "screening_detail_rows": realizations * 24 * 6,
        "screening_realization_rows": realizations,
        "joint_rows": realizations * 24,
    }


def _artifact_rows(path):
    if not path.exists():
        return 0
    with path.open("rb") as stream:
        return max(0, sum(1 for _ in stream) - 1)


def _write_status(status):
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(STATUS_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(str(temporary), str(STATUS_PATH))


def _run(command):
    print("RUN:", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def _verify_upstream():
    path = ROOT / "outputs" / "stage3_numerical_validation.json"
    if not path.is_file():
        raise RuntimeError("S3-05 artifact is missing; run numerical validation first")
    artifact = _load_json(path)
    if artifact.get("status") != "PASS":
        raise RuntimeError("S3-05 gate is not PASS; full S3-04B run is blocked")


def _verify_synthetic_artifacts(expected):
    paths = {
        "screening_detail_rows": ROOT / "outputs" / "stage3_synthetic_screening_detail.csv",
        "screening_realization_rows": ROOT / "outputs" / "stage3_synthetic_calibration.csv",
        "joint_rows": ROOT / "outputs" / "stage3_synthetic_joint_recovery.csv",
    }
    actual = {key: _artifact_rows(path) for key, path in paths.items()}
    complete = all(actual[key] >= expected[key] for key in paths)
    return complete, actual


def main(args):
    expected = _expected_counts()
    _verify_upstream()
    status = {
        "schema_version": "1.0",
        "pipeline": "stage3_publication_preparation",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "real_data_fit_authorized": False,
        "workers": min(args.workers, os.cpu_count() or 1),
        "expected": expected,
        "stages": {
            "s3_05_numerical_validation": "PASS",
            "s3_04b_screening": "PENDING",
            "s3_04b_joint_recovery": "PENDING",
            "s3_04b_artifact_completeness": "PENDING",
        },
        "next_gate": "S3-04B formal synthetic calibration summary and threshold gate",
    }
    _write_status(status)

    screening = [
        sys.executable, "-B", str(SCRIPTS / "run_stage3_synthetic_screening.py"),
        "--workers", str(status["workers"]), "--fold-workers", "1",
    ]
    joint = [
        sys.executable, "-B", str(SCRIPTS / "run_stage3_synthetic_joint_recovery.py"),
        "--workers", str(status["workers"]),
    ]
    if args.dry_run:
        print("DRY RUN: S3-05 PASS verified")
        print("DRY RUN:", " ".join(screening))
        print("DRY RUN:", " ".join(joint))
        return 0

    _run(screening)
    status["stages"]["s3_04b_screening"] = "COMPLETED"
    _write_status(status)

    _run(joint)
    status["stages"]["s3_04b_joint_recovery"] = "COMPLETED"
    complete, actual = _verify_synthetic_artifacts(expected)
    status["actual"] = actual
    status["stages"]["s3_04b_artifact_completeness"] = "PASS" if complete else "FAIL"
    status["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_status(status)
    if not complete:
        raise RuntimeError("synthetic artifacts are incomplete: {}".format(actual))
    print("S3-04B execution complete; formal calibration summary is still required.")
    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main(parse_args()))
