"""Capture and enforce the quarantine of the interrupted legacy S3-04B run."""

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN_ID = "stage3_s3-04b_20260725T222451Z_invalid"
QUARANTINE_ROOT = ROOT / "outputs" / "quarantine"
QUARANTINE_DIR = QUARANTINE_ROOT / RUN_ID
MANIFEST_PATH = QUARANTINE_DIR / "manifest.json"
RETROSPECTIVE_SOURCE_COMMIT = "983938587cfa1000f82028c0edb8482f69bb110e"

FIXED_EVIDENCE_PATHS = (
    "outputs/stage3_synthetic_calibration.csv",
    "outputs/stage3_synthetic_screening_detail.csv",
    "outputs/stage3_synthetic_screening_metadata.json",
    "outputs/stage3_publication_pipeline_status.json",
    "outputs/stage3_publication_pipeline.log",
    "outputs/stage3_publication_pipeline.err.log",
)

CONTEXT_PATHS = (
    "data/stage3_input_manifest.json",
    "data/stage3_model_architecture_decision.json",
    "data/stage3_synthetic_calibration_protocol.json",
    "outputs/stage3_numerical_validation.json",
    "outputs/release_status.json",
    "provenance/environment.json",
    "pyproject.toml",
    "requirements-lock.txt",
    "stage3.md",
)

RETROSPECTIVE_SOURCE_PATHS = (
    "scripts/launch_stage3_batch.py",
    "scripts/run_stage3_numerical_validation.py",
    "scripts/run_stage3_publication_pipeline.py",
    "scripts/run_stage3_synthetic_joint_recovery.py",
    "scripts/run_stage3_synthetic_screening.py",
    "scripts/stage3_joint_model.py",
    "scripts/stage3_noise_core.py",
    "scripts/stage3_synthetic_calibration_core.py",
    "scripts/stage3_synthetic_generator.py",
)

ABSENT_EXPECTED_ARTIFACTS = (
    "outputs/stage3_synthetic_joint_recovery.csv",
    "outputs/stage3_synthetic_joint_recovery_metadata.json",
    "outputs/stage3_synthetic_calibration_summary.json",
    "outputs/stage3_threshold_calibration.json",
)

INVALIDITY_FINDINGS = (
    {
        "id": "S3Q-001",
        "finding": "Checkpoint-resumed rows were appended in sorted-key order under a different CSV header order.",
    },
    {
        "id": "S3Q-002",
        "finding": "The detail artifact contains duplicate fold task keys.",
    },
    {
        "id": "S3Q-003",
        "finding": "Failed M1 fits were represented by non-finite values and could be skipped by aggregation.",
    },
    {
        "id": "S3Q-004",
        "finding": "Boundary counts recorded diagnostic entries rather than true at-boundary flags.",
    },
    {
        "id": "S3Q-005",
        "finding": "Legacy runners and verification paths failed open or relied on raw row counts.",
    },
    {
        "id": "S3Q-006",
        "finding": "Branches in the interrupted run used independently drawn synthetic baselines.",
    },
    {
        "id": "S3Q-007",
        "finding": "The null-transit gate had no explicit null-transit model while rp_rs was bounded above zero.",
    },
    {
        "id": "S3Q-008",
        "finding": "The frozen protocol contains class-count, coverage-language, partial-completion, and artifact-path contradictions.",
    },
    {
        "id": "S3Q-009",
        "finding": "The execution commit and exact execution environment were not bound into the run artifacts.",
    },
)

LEGACY_BLOCK_MESSAGE = (
    "The legacy S3-04B output namespace is permanently quarantined at "
    "outputs/quarantine/{}/manifest.json. This entry point must not resume, "
    "verify, or write those artifacts. A corrected run requires a versioned "
    "protocol amendment, a new runner/schema, and a fresh output namespace."
).format(RUN_ID)


class LegacyStage3QuarantineError(RuntimeError):
    """Raised when code attempts to use the quarantined Stage-3 namespace."""


def refuse_legacy_execution(entrypoint):
    """Fail closed before a legacy entry point reads or writes run artifacts."""
    raise LegacyStage3QuarantineError("{} Entry point: {}".format(
        LEGACY_BLOCK_MESSAGE, entrypoint,
    ))


def refuse_superseded_execution(entrypoint, revision, disposition):
    """Permanently disable a versioned runner retained only as evidence."""
    raise LegacyStage3QuarantineError(
        "Stage-3 revision {} is permanently superseded with disposition {}. "
        "Its versioned launcher is retained only for provenance and cannot be "
        "reactivated by editing an authorization file. Use scripts/run_stage3.py "
        "for registry status. Entry point: {}".format(
            revision, disposition, entrypoint,
        )
    )


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_mtime(path):
    return datetime.fromtimestamp(
        path.stat().st_mtime, timezone.utc,
    ).isoformat()


def _git_output(*args):
    return subprocess.check_output(
        ["git"] + list(args), cwd=str(ROOT), stderr=subprocess.DEVNULL,
    ).decode("utf-8", errors="strict").strip()


def _tracked_paths():
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=str(ROOT))
    return {
        item.decode("utf-8") for item in raw.split(b"\0") if item
    }


def _ignored_paths(relative_paths):
    ignored = set()
    for relative in relative_paths:
        process = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", relative],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        if process.returncode == 0:
            ignored.add(relative)
        elif process.returncode != 1:
            raise RuntimeError(process.stderr.strip() or "git check-ignore failed")
    return ignored


def _inventory_evidence():
    paths = [ROOT / relative for relative in FIXED_EVIDENCE_PATHS]
    paths.extend(sorted((ROOT / "outputs").glob("batch_c[0-9][0-9].log")))
    paths.extend(sorted((ROOT / "outputs").glob("batch_c[0-9][0-9].err.log")))
    paths.extend(sorted(
        (ROOT / "outputs" / "stage3_synthetic_screening_checkpoints").glob("*.json")
    ))
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing quarantine evidence: {}".format(missing[0]))
    relative = [path.relative_to(ROOT).as_posix() for path in paths]
    if len(relative) != len(set(relative)):
        raise RuntimeError("quarantine evidence inventory contains duplicate paths")
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def _source_record(path, tracked, ignored, category, role):
    relative = path.relative_to(ROOT).as_posix()
    return {
        "category": category,
        "role": role,
        "original_path": relative,
        "snapshot_path": "snapshot/{}".format(relative),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_path(path),
        "original_mtime_utc": _utc_mtime(path),
        "tracked_at_capture": relative in tracked,
        "ignored_by_rules_at_capture": relative in ignored,
        "formal_use_permitted": False,
    }


def _git_source_record(relative, data):
    snapshot = "snapshot/retrospective_source_{}/{}".format(
        RETROSPECTIVE_SOURCE_COMMIT[:7], relative,
    )
    return {
        "category": "retrospective_source",
        "role": "candidate_source_snapshot_not_execution_bound",
        "original_path": "git:{}:{}".format(RETROSPECTIVE_SOURCE_COMMIT, relative),
        "snapshot_path": snapshot,
        "size_bytes": len(data),
        "sha256": _sha256_bytes(data),
        "original_mtime_utc": None,
        "tracked_at_capture": True,
        "ignored_by_rules_at_capture": False,
        "formal_use_permitted": False,
    }


def _tree_digest(records, path_key="original_path"):
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item[path_key]):
        line = "{}\0{}\0{}\n".format(
            record[path_key], record["size_bytes"], record["sha256"],
        )
        digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def _decode_detail_rows(path):
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows:
        raise RuntimeError("screening detail CSV is empty")
    header = rows[0]
    sorted_header = sorted(header)
    decoded = []
    canonical = 0
    first_misordered = None
    for file_line, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            raise RuntimeError("detail CSV field count differs at line {}".format(file_line))
        try:
            int(row[0])
            row_header = header
            canonical += 1
        except ValueError:
            row_header = sorted_header
            if first_misordered is None:
                first_misordered = file_line
        decoded.append(dict(zip(row_header, row)))
    return decoded, canonical, first_misordered


def _observed_state(evidence_paths):
    detail_path = ROOT / "outputs" / "stage3_synthetic_screening_detail.csv"
    detail, canonical_count, first_misordered = _decode_detail_rows(detail_path)
    keys = [
        (
            int(row["class_index"]),
            int(row["realization_index"]),
            row["model_id"],
            int(row["held_sector"]),
        )
        for row in detail
    ]
    key_counts = Counter(keys)
    failed_m1 = sum(row["m1_success"].strip().lower() != "true" for row in detail)

    summary_path = ROOT / "outputs" / "stage3_synthetic_calibration.csv"
    with summary_path.open("r", encoding="utf-8", newline="") as stream:
        summary_rows = sum(1 for _ in csv.reader(stream)) - 1

    checkpoint_paths = [
        path for path in evidence_paths
        if path.parent.name == "stage3_synthetic_screening_checkpoints"
    ]
    checkpoint_rows = 0
    checkpoint_failed_m1 = 0
    for path in checkpoint_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload["detail"]
        checkpoint_rows += len(rows)
        checkpoint_failed_m1 += sum(not bool(row.get("m1_success")) for row in rows)

    return {
        "expected_realizations": 210,
        "expected_detail_rows": 30240,
        "expected_joint_rows": 5040,
        "summary_rows": summary_rows,
        "detail_rows": len(detail),
        "canonical_detail_rows": canonical_count,
        "misordered_detail_rows": len(detail) - canonical_count,
        "first_misordered_file_line": first_misordered,
        "unique_fold_keys": len(key_counts),
        "duplicate_fold_keys": sum(count - 1 for count in key_counts.values()),
        "duplicated_realizations": sorted({
            "C{}-r{}".format(key[0], key[1])
            for key, count in key_counts.items() if count > 1
        }),
        "failed_m1_detail_rows": failed_m1,
        "checkpoint_files": len(checkpoint_paths),
        "checkpoint_fold_rows": checkpoint_rows,
        "failed_m1_checkpoint_rows": checkpoint_failed_m1,
        "joint_recovery_rows": 0,
        "formal_summary_present": False,
        "threshold_artifact_present": False,
    }


def _copy_and_verify(source, destination, expected_sha256):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(destination))
    actual = _sha256_path(destination)
    if actual != expected_sha256:
        raise RuntimeError("copied artifact hash mismatch: {}".format(destination))


def _notice_text(manifest):
    state = manifest["observed_state"]
    return """# Quarantined S3-04B Execution

Run ID: `{run_id}`

This directory is a byte-preserving forensic capture of the interrupted legacy
S3-04B execution. It is invalid for formal calibration, threshold derivation,
model adoption, real-data authorization, or resume.

Observed at capture:

- {summary_rows}/210 realization summaries
- {detail_rows} detail rows, including {misordered_rows} rows in the wrong field order
- {duplicate_rows} duplicate fold keys
- {failed_rows} failed M1 detail fits
- {checkpoint_files} partial branch checkpoints
- no joint recovery, formal summary, or threshold artifact

The PASP/MNRAS methodology-paper program requires a versioned protocol
amendment and a fresh execution namespace. The files here may be used only for
forensic review of the interrupted run. Verify them with:

```text
python scripts/stage3_quarantine.py verify
```
""".format(
        run_id=manifest["run_id"],
        summary_rows=state["summary_rows"],
        detail_rows=state["detail_rows"],
        misordered_rows=state["misordered_detail_rows"],
        duplicate_rows=state["duplicate_fold_keys"],
        failed_rows=state["failed_m1_detail_rows"],
        checkpoint_files=state["checkpoint_files"],
    )


def capture():
    """Capture the legacy run once without modifying any source artifact."""
    if QUARANTINE_DIR.exists():
        raise FileExistsError("refusing to overwrite {}".format(QUARANTINE_DIR))
    if not QUARANTINE_ROOT.is_dir():
        raise FileNotFoundError(QUARANTINE_ROOT)

    evidence_paths = _inventory_evidence()
    context_paths = [ROOT / relative for relative in CONTEXT_PATHS]
    missing_context = [path for path in context_paths if not path.is_file()]
    if missing_context:
        raise FileNotFoundError("missing capture context: {}".format(missing_context[0]))

    all_relative = [
        path.relative_to(ROOT).as_posix() for path in evidence_paths + context_paths
    ]
    tracked = _tracked_paths()
    ignored = _ignored_paths(all_relative)
    evidence = [
        _source_record(path, tracked, ignored, "run_evidence", "interrupted_execution")
        for path in evidence_paths
    ]
    context = [
        _source_record(path, tracked, ignored, "capture_context", "retrospective_context")
        for path in context_paths
    ]
    git_sources = []
    git_source_bytes = {}
    for relative in RETROSPECTIVE_SOURCE_PATHS:
        data = subprocess.check_output(
            ["git", "show", "{}:{}".format(RETROSPECTIVE_SOURCE_COMMIT, relative)],
            cwd=str(ROOT),
        )
        git_source_bytes[relative] = data
        git_sources.append(_git_source_record(relative, data))

    capture_head = _git_output("rev-parse", "HEAD")
    dirty_paths = _git_output("status", "--porcelain").splitlines()
    started = datetime.now(timezone.utc).isoformat()
    temporary = Path(tempfile.mkdtemp(prefix=".{}-".format(RUN_ID), dir=str(QUARANTINE_ROOT)))
    try:
        for record, source in zip(evidence, evidence_paths):
            _copy_and_verify(source, temporary / record["snapshot_path"], record["sha256"])
        for record, source in zip(context, context_paths):
            _copy_and_verify(source, temporary / record["snapshot_path"], record["sha256"])
        for record in git_sources:
            relative = record["original_path"].split(":", 2)[2]
            destination = temporary / record["snapshot_path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(git_source_bytes[relative])
            if _sha256_path(destination) != record["sha256"]:
                raise RuntimeError("retrospective source copy hash mismatch")

        for record, source in zip(evidence + context, evidence_paths + context_paths):
            if source.stat().st_size != record["size_bytes"]:
                raise RuntimeError("source size changed during capture: {}".format(source))
            if _sha256_path(source) != record["sha256"]:
                raise RuntimeError("source hash changed during capture: {}".format(source))
        if [path.relative_to(ROOT).as_posix() for path in _inventory_evidence()] != [
                path.relative_to(ROOT).as_posix() for path in evidence_paths]:
            raise RuntimeError("evidence path set changed during capture")

        artifacts = evidence + context + git_sources
        manifest = {
            "schema_version": "1.0",
            "record_type": "QUARANTINED_EXECUTION_MANIFEST",
            "run_id": RUN_ID,
            "work_package": "S3-04B",
            "execution_state": "INTERRUPTED",
            "validity": "INVALID",
            "disposition": "QUARANTINED",
            "scientific_use": "NONE",
            "publication_target": "PASP_OR_MNRAS_METHODOLOGY_PIPELINE_PAPER",
            "permissions": {
                "resume_permitted": False,
                "formal_calibration_use_permitted": False,
                "threshold_derivation_permitted": False,
                "model_adoption_permitted": False,
                "real_data_authorization_permitted": False,
                "forensic_use_permitted": True,
            },
            "execution": {
                "started_utc": "2026-07-25T22:24:51.599307+00:00",
                "ended_utc": None,
                "exit_code": None,
                "termination_reason": "UNKNOWN_INTERRUPTED",
                "workers": 8,
                "fold_workers": 1,
                "execution_git_commit": None,
                "retrospective_source_snapshot_commit": RETROSPECTIVE_SOURCE_COMMIT,
                "retrospective_source_limitation": (
                    "The source snapshot is the last recorded repository state associated "
                    "with the interrupted artifacts; the execution did not bind its commit."
                ),
            },
            "capture": {
                "started_utc": started,
                "finished_utc": datetime.now(timezone.utc).isoformat(),
                "git_head": capture_head,
                "dirty_status_at_capture": dirty_paths,
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "capture_tool": "scripts/stage3_quarantine.py",
            },
            "observed_state": _observed_state(evidence_paths),
            "invalidity_findings": list(INVALIDITY_FINDINGS),
            "absent_expected_artifacts": list(ABSENT_EXPECTED_ARTIFACTS),
            "run_evidence_tree": {
                "algorithm": "sha256(sorted(original_path + NUL + size + NUL + sha256 + LF))",
                "record_count": len(evidence),
                "size_bytes": sum(record["size_bytes"] for record in evidence),
                "sha256": _tree_digest(evidence),
            },
            "snapshot_tree": {
                "algorithm": "sha256(sorted(snapshot_path + NUL + size + NUL + sha256 + LF))",
                "record_count": len(artifacts),
                "size_bytes": sum(record["size_bytes"] for record in artifacts),
                "sha256": _tree_digest(artifacts, path_key="snapshot_path"),
            },
            "artifacts": artifacts,
            "environment_binding": {
                "status": "RETROSPECTIVE_NOT_EXECUTION_BOUND",
                "limitations": [
                    "No execution-time Git commit was embedded in the legacy outputs.",
                    "The available environment record is contextual and not bound to each task.",
                    "Legacy checkpoints bind only the frozen protocol hash.",
                ],
            },
            "replacement_requirement": (
                "Versioned protocol and architecture amendment, new runner/schema, "
                "fresh namespace, and independent gate audit."
            ),
        }
        manifest_path = temporary / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        (temporary / "NOTICE.md").write_text(_notice_text(manifest), encoding="utf-8")
        os.replace(str(temporary), str(QUARANTINE_DIR))
    except Exception:
        shutil.rmtree(str(temporary), ignore_errors=True)
        raise
    return verify()


def _reject_json_constant(value):
    raise ValueError("non-standard JSON constant: {}".format(value))


def verify():
    """Verify every captured byte and all fail-closed manifest permissions."""
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(MANIFEST_PATH)
    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8"),
        parse_constant=_reject_json_constant,
    )
    if manifest.get("run_id") != RUN_ID:
        raise RuntimeError("quarantine run ID mismatch")
    permissions = manifest.get("permissions", {})
    forbidden = (
        "resume_permitted",
        "formal_calibration_use_permitted",
        "threshold_derivation_permitted",
        "model_adoption_permitted",
        "real_data_authorization_permitted",
    )
    if any(permissions.get(name) is not False for name in forbidden):
        raise RuntimeError("quarantine permissions are not fail-closed")
    if permissions.get("forensic_use_permitted") is not True:
        raise RuntimeError("forensic-use permission is missing")

    artifacts = manifest.get("artifacts", [])
    seen = set()
    for record in artifacts:
        relative = record["snapshot_path"]
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise RuntimeError("unsafe or duplicate snapshot path: {}".format(relative))
        seen.add(relative)
        captured = QUARANTINE_DIR / path
        if not captured.is_file():
            raise FileNotFoundError(captured)
        if captured.stat().st_size != record["size_bytes"]:
            raise RuntimeError("captured size mismatch: {}".format(relative))
        if _sha256_path(captured) != record["sha256"]:
            raise RuntimeError("captured hash mismatch: {}".format(relative))

    evidence = [record for record in artifacts if record["category"] == "run_evidence"]
    evidence_tree = manifest["run_evidence_tree"]
    if len(evidence) != evidence_tree["record_count"]:
        raise RuntimeError("run-evidence record count mismatch")
    if sum(record["size_bytes"] for record in evidence) != evidence_tree["size_bytes"]:
        raise RuntimeError("run-evidence size mismatch")
    if _tree_digest(evidence) != evidence_tree["sha256"]:
        raise RuntimeError("run-evidence tree hash mismatch")

    snapshot_tree = manifest["snapshot_tree"]
    if len(artifacts) != snapshot_tree["record_count"]:
        raise RuntimeError("snapshot record count mismatch")
    if sum(record["size_bytes"] for record in artifacts) != snapshot_tree["size_bytes"]:
        raise RuntimeError("snapshot size mismatch")
    if _tree_digest(artifacts, path_key="snapshot_path") != snapshot_tree["sha256"]:
        raise RuntimeError("snapshot tree hash mismatch")
    return manifest


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("capture", "verify"))
    return parser.parse_args()


def main(args):
    manifest = capture() if args.command == "capture" else verify()
    print("Verified quarantine {}: {} files, {} bytes".format(
        manifest["run_id"],
        manifest["snapshot_tree"]["record_count"],
        manifest["snapshot_tree"]["size_bytes"],
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main(parse_args()))
