import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter

import pytest

import build_lab_artifact_register as artifact_register
import build_recursive_release_manifest as recursive_manifest
import build_release_package as release_package
import generate_release_manifest
import stage3_quarantine as quarantine


EXPECTED_EVIDENCE_TREE = "d768fa036ea5e349792fcf3dcc16f9579438319f7394dcf6d36e647bb764e1b7"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest():
    return json.loads(
        quarantine.MANIFEST_PATH.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError("non-standard JSON constant: {}".format(value))
        ),
    )


def test_quarantine_manifest_is_strict_and_fail_closed():
    manifest = quarantine.verify()
    assert manifest["record_type"] == "QUARANTINED_EXECUTION_MANIFEST"
    assert manifest["execution_state"] == "INTERRUPTED"
    assert manifest["validity"] == "INVALID"
    assert manifest["disposition"] == "QUARANTINED"
    assert manifest["scientific_use"] == "NONE"
    assert manifest["publication_target"] == "PASP_OR_MNRAS_METHODOLOGY_PIPELINE_PAPER"
    permissions = manifest["permissions"]
    assert permissions["forensic_use_permitted"] is True
    assert permissions["resume_permitted"] is False
    assert permissions["formal_calibration_use_permitted"] is False
    assert permissions["threshold_derivation_permitted"] is False
    assert permissions["model_adoption_permitted"] is False
    assert permissions["real_data_authorization_permitted"] is False
    assert manifest["run_evidence_tree"]["record_count"] == 132
    assert manifest["run_evidence_tree"]["sha256"] == EXPECTED_EVIDENCE_TREE
    assert manifest["capture"]["git_ignore_fields_authoritative"] is False


def test_quarantine_snapshot_reproduces_forensic_counts():
    root = quarantine.QUARANTINE_DIR / "snapshot" / "outputs"
    detail_path = root / "stage3_synthetic_screening_detail.csv"
    decoded, canonical, first_misordered = quarantine._decode_detail_rows(detail_path)
    keys = [
        (
            int(row["class_index"]), int(row["realization_index"]),
            row["model_id"], int(row["held_sector"]),
        )
        for row in decoded
    ]
    counts = Counter(keys)
    assert len(decoded) == 2160
    assert canonical == 1008
    assert first_misordered == 146
    assert len(counts) == 2016
    assert sum(count - 1 for count in counts.values()) == 144
    assert {
        (key[0], key[1]) for key, count in counts.items() if count > 1
    } == {(0, 6)}
    assert sum(row["m1_success"].lower() != "true" for row in decoded) == 299

    with (root / "stage3_synthetic_calibration.csv").open(
            "r", encoding="utf-8", newline="") as stream:
        assert sum(1 for _ in csv.reader(stream)) - 1 == 14

    checkpoints = sorted(
        (root / "stage3_synthetic_screening_checkpoints").glob("*.json")
    )
    assert len(checkpoints) == 102
    checkpoint_rows = []
    for path in checkpoints:
        checkpoint_rows.extend(json.loads(path.read_text(encoding="utf-8"))["detail"])
    assert len(checkpoint_rows) == 612
    assert sum(not row["m1_success"] for row in checkpoint_rows) == 177
    assert not (root / "stage3_synthetic_joint_recovery.csv").exists()
    assert not (root / "stage3_synthetic_calibration_summary.json").exists()
    assert not (root / "stage3_threshold_calibration.json").exists()


def test_quarantine_capture_refuses_to_clobber():
    before = sha256(quarantine.MANIFEST_PATH)
    with pytest.raises(FileExistsError):
        quarantine.capture()
    assert sha256(quarantine.MANIFEST_PATH) == before


def test_legacy_stage3_entrypoints_fail_before_touching_outputs(root):
    manifest = load_manifest()
    evidence = [
        record for record in manifest["artifacts"]
        if record["category"] == "run_evidence"
    ]
    before = {
        record["original_path"]: (
            (root / record["original_path"]).stat().st_mtime_ns,
            sha256(root / record["original_path"]),
        )
        for record in evidence
    }
    assert all(
        before[record["original_path"]][1] == record["sha256"]
        for record in evidence
    )
    commands = (
        [sys.executable, "-B", "scripts/run_stage3_synthetic_screening.py", "--verify-only"],
        [sys.executable, "-B", "scripts/run_stage3_synthetic_joint_recovery.py", "--verify-only"],
        [sys.executable, "-B", "scripts/run_stage3_publication_pipeline.py", "--dry-run"],
        [sys.executable, "-B", "scripts/launch_stage3_batch.py", "--screening-only"],
    )
    for command in commands:
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False, timeout=30,
        )
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert quarantine.RUN_ID in output
        assert "fresh output namespace" in output

    after = {
        record["original_path"]: (
            (root / record["original_path"]).stat().st_mtime_ns,
            sha256(root / record["original_path"]),
        )
        for record in evidence
    }
    assert after == before


def test_quarantine_is_visible_to_git_and_bytes_are_not_normalized(root):
    relative = quarantine.MANIFEST_PATH.relative_to(root).as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--", relative], cwd=root, check=False,
    )
    assert ignored.returncode == 1
    snapshot = next(
        record["snapshot_path"] for record in load_manifest()["artifacts"]
        if record["category"] == "run_evidence"
    )
    snapshot_relative = (
        quarantine.QUARANTINE_DIR.relative_to(root) / snapshot
    ).as_posix()
    attributes = subprocess.check_output(
        ["git", "check-attr", "text", "diff", "--", snapshot_relative],
        cwd=root, text=True,
    )
    assert "text: unset" in attributes
    assert "diff: unset" in attributes


def test_release_tooling_isolates_quarantined_and_legacy_paths():
    quarantine_path = "outputs/quarantine/{}/manifest.json".format(quarantine.RUN_ID)
    legacy_path = "outputs/stage3_synthetic_screening_detail.csv"
    policy = json.loads(
        (quarantine.ROOT / "data" / "release_manifest_policy.json").read_text(
            encoding="utf-8"
        )
    )
    assert recursive_manifest.status_for(quarantine_path, policy) == "historical"
    assert recursive_manifest.status_for(legacy_path, policy) == "historical"
    assert quarantine_path not in generate_release_manifest.recursive_policy_paths()
    assert legacy_path not in generate_release_manifest.recursive_policy_paths()
    assert "LEGACY_ARCHIVE.md" not in generate_release_manifest.REQUIRED
    assert quarantine_path not in generate_release_manifest.REQUIRED
    assert legacy_path not in generate_release_manifest.REQUIRED
    assert release_package.historical_manifest_paths([quarantine_path, legacy_path]) == [
        quarantine_path, legacy_path,
    ]
    assert artifact_register.classification(quarantine_path) == (
        "quarantined_execution_evidence", "provenance_only", False,
    )


def test_methodology_charter_and_release_status_agree(root):
    charter = json.loads(
        (root / "data" / "methodology_publication_charter.json").read_text(
            encoding="utf-8"
        )
    )
    release = json.loads(
        (root / "outputs" / "release_status.json").read_text(encoding="utf-8")
    )
    method = release["methodology_publication"]
    assert charter["decision_id"] == "LAB-DEC-010"
    assert charter["primary_publication_object"] == method["primary_publication_object"]
    assert charter["stage3_current_state"] == method["stage3_current_state"]
    assert charter["current_code_protocol_consistency"] == (
        "UNRESOLVED_REVISION_4_NOT_FROZEN"
    )
    assert charter["active_execution_revision"] is None
    assert charter["next_revision"] == 4
    assert charter["real_data_fit_authorized"] is False
    assert charter["claim_register"]["explicit_null_transit_calibration"] == (
        "DEVELOPMENT_CODE_NOT_CALIBRATED"
    )
    assert charter["claim_register"]["stage3_injection_recovery_validation"] == (
        "NOT_SUPPORTED"
    )
    assert release["gates"]["methodology_paper_ready"] is False
    assert release["gates"]["local_release_package_ready"] is False
    assert release["stage4_candidate_publication"]["candidate_paper_ready"] is False
    verification = release["current_verification"]
    assert verification["canonical_stage3_focused_passed"] == 22
    assert verification["canonical_stage3_focused_failed"] == 0
    assert verification["full_suite_green"] is False
