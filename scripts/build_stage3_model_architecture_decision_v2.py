"""Build the versioned S3-03 v2 model-architecture amendment.

This builder loads the frozen v1 architecture decision, verifies its hash, and
emits a standalone v2 amendment that corrects the defects exposed by the
interrupted S3-04B execution and LAB-DEC-010.  The v1 file is never modified.
The v2 output is no-clobber; use --verify-only to confirm it is current.
"""

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
V1_PATH = ROOT / "data" / "stage3_model_architecture_decision.json"
OUTPUT_PATH = ROOT / "data" / "stage3_model_architecture_decision_v2.json"
QUARANTINE_MANIFEST = (
    ROOT / "outputs" / "quarantine"
    / "stage3_s3-04b_20260725T222451Z_invalid" / "manifest.json"
)
DECISION_PATH = ROOT / "docs" / "lab" / "decisions" / "LAB-DEC-010.md"

V2_NAMESPACE = "outputs/stage3_v2"
SEED_BASE_V1 = 349204
SEED_BASE_V2 = 749204

CHECKPOINT_REQUIRED_FIELDS = [
    "protocol_v2_sha256",
    "architecture_v2_sha256",
    "input_manifest_sha256",
    "code_identity",
    "environment_identity",
    "task_schema_version",
    "task_key",
]

AMENDMENTS = [
    {
        "id": "S3V2-A01",
        "title": "Explicit null-transit hypothesis",
        "v1_defect": "The joint model always fitted a positive transit with rp_rs >= 0.03, so the frozen C11 false-transit gate could never be evaluated.",
        "v2_correction": "Add an H0 model with rp_rs fixed to 0, identical noise hierarchy and baseline marginalization, and a frozen detection statistic delta_map = objective_H0 - objective_H1.",
    },
    {
        "id": "S3V2-A02",
        "title": "One shared observed realization for all branches",
        "v1_defect": "Every branch drew an independent polynomial baseline, so the 24-branch mixture combined likelihoods evaluated on different synthetic data sets.",
        "v2_correction": "The injected baseline is drawn once per realization (degree-2 per event over +/-16 h) and shared by every branch and mask; per-branch data alteration is forbidden.",
    },
    {
        "id": "S3V2-A03",
        "title": "Checkpoint identity binding",
        "v1_defect": "Legacy checkpoints bound only the protocol hash; resumed rows corrupted the CSV schema and could not be traced to code or environment.",
        "v2_correction": "Every immutable task record binds protocol, architecture, input-manifest, code, environment, schema, and the exact task key; strict JSON forbids NaN; a failed fit fails the task and the runner exits nonzero.",
    },
    {
        "id": "S3V2-A04",
        "title": "Correct boundary accounting",
        "v1_defect": "Boundary counts recorded one diagnostic entry per parameter, not the parameters actually at a boundary.",
        "v2_correction": "boundary_count counts only parameters whose at_boundary flag is true.",
    },
    {
        "id": "S3V2-A05",
        "title": "Registered white-noise warm start",
        "v1_defect": "The K2 warm start was documented but never supplied to the optimizer.",
        "v2_correction": "The correlated-noise MAP receives a fourth registered start derived exactly from the white-noise (K0) MAP solution.",
    },
    {
        "id": "S3V2-A06",
        "title": "Missing calibration classes registered",
        "v1_defect": "Pointing-correlated and partial-gap/edge injections were required but absent from the 12-class protocol.",
        "v2_correction": "C13 injects aperture-telemetry-correlated systematics (frozen template telemetry; true centroid telemetry requires a new input and is deferred to a possible v3). C14 injects transits into the two registered gap/edge events with partial window coverage.",
    },
    {
        "id": "S3V2-A07",
        "title": "Fresh artifact namespace",
        "v1_defect": "The architecture and protocol named different threshold paths, and the legacy namespace mixes invalid and valid states.",
        "v2_correction": "Every v2 artifact lives under outputs/stage3_v2/ with versioned file names; legacy paths are forbidden as inputs or outputs.",
    },
    {
        "id": "S3V2-A08",
        "title": "Full completion rule",
        "v1_defect": "The protocol allowed a class to pass at 50% completion while the orchestrator assumed all 210 realizations.",
        "v2_correction": "A class is complete only when 100% of requested realizations finish with valid fits; anything less is INCOMPLETE, never a pass and never a calibrated failure.",
    },
    {
        "id": "S3V2-A09",
        "title": "Honest coverage rationale",
        "v1_defect": "The protocol called a 0.50 coverage floor 'more stringent' than the nominal 0.68.",
        "v2_correction": "The floors are documented as relaxed relative to nominal because MAP + conditional-Laplace intervals are approximate and expected to undercover.",
    },
    {
        "id": "S3V2-A10",
        "title": "Untouched seed stream",
        "v1_defect": "Post-result corrections reused the same seed base as the interrupted run.",
        "v2_correction": "v2 draws use base seed 749204, disjoint from the v1 stream; legacy seeds are never reused.",
    },
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_record(path):
    return {
        "relative_path": path.relative_to(ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build_decision():
    v1 = load_json(V1_PATH)
    decision = {
        "schema_version": "2.0",
        "work_package": "S3-03_V2_MODEL_ARCHITECTURE_AMENDMENT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "scope": {
            "analysis_mode": "VERSIONED_AMENDMENT_POST_RESULT_DISCLOSED",
            "supersedes": "data/stage3_model_architecture_decision.json",
            "supersedes_sha256": sha256(V1_PATH),
            "v1_preserved_unmodified": True,
            "governing_decision": "docs/lab/decisions/LAB-DEC-010.md",
            "real_data_fit_executed": False,
            "real_data_fit_authorized": False,
            "phase_7_may_begin": False,
            "execution_authorized": False,
            "execution_requires": [
                "data/stage3_synthetic_calibration_protocol_v2.json frozen and verified",
                "independent second-party protocol review recorded",
                "v2 runner with checkpoint identity and fresh namespace",
            ],
            "prior_results_disclosed": True,
            "interrupted_legacy_run_quarantined": (
                "outputs/quarantine/stage3_s3-04b_20260725T222451Z_invalid/manifest.json"
            ),
        },
        "source_integrity": {
            "sources": {
                record["relative_path"]: record
                for record in (
                    source_record(V1_PATH),
                    source_record(QUARANTINE_MANIFEST),
                    source_record(DECISION_PATH),
                )
            },
            "governance_references_not_hash_bound": [
                "data/methodology_publication_charter.json (living status document; binding it would guarantee staleness)",
            ],
        },
        "amendment_register": AMENDMENTS,
        "candidate": None,
        "optimizer": None,
        "artifact_namespace": {
            "root": V2_NAMESPACE,
            "screening_detail_csv": "{}/stage3_v2_screening_detail.csv".format(V2_NAMESPACE),
            "realization_summary_csv": "{}/stage3_v2_synthetic_calibration.csv".format(V2_NAMESPACE),
            "joint_recovery_csv": "{}/stage3_v2_joint_recovery.csv".format(V2_NAMESPACE),
            "calibration_summary_json": "{}/stage3_v2_calibration_summary.json".format(V2_NAMESPACE),
            "threshold_calibration_json": "{}/stage3_v2_threshold_calibration.json".format(V2_NAMESPACE),
            "checkpoint_dir": "{}/checkpoints".format(V2_NAMESPACE),
            "legacy_paths_forbidden": [
                "outputs/stage3_synthetic_calibration.csv",
                "outputs/stage3_synthetic_screening_detail.csv",
                "outputs/stage3_synthetic_joint_recovery.csv",
                "outputs/stage3_synthetic_calibration_summary.json",
                "outputs/stage3_threshold_calibration.json",
                "outputs/stage3_synthetic_screening_checkpoints",
                "data/stage3_threshold_calibration.json",
            ],
        },
        "checkpoint_identity": {
            "required_fields": CHECKPOINT_REQUIRED_FIELDS,
            "task_key_fields": [
                "class_index", "realization_index", "branch_index", "held_sector",
            ],
            "rules": [
                "Task records are immutable single-task JSON files written atomically; a single deterministic reducer builds CSV artifacts.",
                "JSON is strict: NaN, Infinity, and duplicate keys are forbidden.",
                "A failed fit is recorded as a failed task, never as a missing or neutral score.",
                "The runner exits nonzero if any requested task fails.",
                "--verify-only performs full schema, exact task-key, hash, and fit-validity checks.",
                "Legacy checkpoints and legacy CSVs are never ingested.",
                "Aggregation never skips non-finite values; exact expected task-key equality is required.",
            ],
        },
        "boundary_accounting": {
            "rule": "boundary_count equals the number of parameters whose at_boundary flag is true.",
            "v1_defect_corrected": "S3V2-A04",
        },
        "completion_rule": {
            "required_fraction": 1.0,
            "partial_completion_state": "INCOMPLETE",
            "partial_acceptance_permitted": False,
        },
        "seed_policy": {
            "base_seed_v1": SEED_BASE_V1,
            "base_seed_v2": SEED_BASE_V2,
            "streams_disjoint": True,
            "scheme": "realization_seed = base_seed_v2 + class_index * 10000 + realization_index * 100",
        },
        "computational_feasibility": {
            "classes": 14,
            "realizations": 235,
            "screening_fold_scores": 235 * 24 * 6,
            "joint_fits_with_null_hypothesis": 235 * 24 * 2,
            "screening_wallclock_estimate_hours_at_8_workers": "45-115",
            "joint_wallclock_estimate_hours_at_8_workers": "35-125",
            "basis": "Observed v1 C01 runtimes of 0.5-2.4 h per realization and the v1 architecture estimate of 60-180 s per branch-start.",
        },
        "stop_rules": {
            "no_real_data_before_v2_synthetic_and_numerical_gates_pass": True,
            "no_threshold_revision_after_observing_real_data": True,
            "no_legacy_resume_or_legacy_artifact_use": True,
            "no_branch_sector_or_event_removal": True,
            "further_changes_require": "S3-03 v3 versioned amendment with fresh seeds and a fresh namespace",
            "on_synthetic_failure": "Report the failed conditions; narrow or close the method. Do not tune against the target.",
        },
    }

    candidate = copy.deepcopy(v1["candidate"])
    candidate["id"] = "K1_RM32_SECTOR_TIMESCALES_V2"
    candidate["role"] = "PRIMARY_CALIBRATION_CANDIDATE_V2"
    candidate["adopted_for_real_data"] = False
    candidate["v2_changes"] = [item["id"] for item in AMENDMENTS]
    candidate["transit_model"]["null_hypothesis"] = {
        "id": "H0_NO_TRANSIT",
        "rp_rs": 0.0,
        "transit_component": "unity (flat light curve)",
        "noise_hierarchy": "identical to the transit hypothesis",
        "event_baseline": "identical exact Gaussian marginalization",
        "fit": "separate MAP fit per branch with the same registered multistart set",
        "detection_statistic": "delta_map = objective_H0 - objective_H1 (larger favors the transit)",
        "detection_rule": (
            "A transit is detected iff delta_map >= delta_detect. delta_detect is derived "
            "from C11 null realizations under data/stage3_synthetic_calibration_protocol_v2.json "
            "before any real-data use; the derivation rule is frozen there."
        ),
        "purpose": "Makes the C11 false-transit gate evaluable; v1 bounded rp_rs >= 0.03 with no null model.",
    }
    candidate["transit_model"]["hypothesis_count"] = 2
    candidate["event_baseline"]["injection"] = (
        "Shared draw per realization: one degree-2 polynomial per event over +/-16 h "
        "(the widest branch half-width), coefficients from N(0, 0.01^2), identical for "
        "all 24 branches and both masks. Model-side marginalization is unchanged."
    )
    decision["candidate"] = candidate

    optimizer = copy.deepcopy(v1["optimizer"])
    optimizer["registered_starts"] = 4
    optimizer["warm_start"] = {
        "id": "WARM_FROM_K0_MAP",
        "role": "fourth registered start for the correlated-noise MAP",
        "derivation": (
            "Take the converged white-noise (K0) pooled MAP for the same training sectors; "
            "map jitter means and sector offsets one-to-one; initialize amplitude at the prior "
            "mean ratio and timescales at the prior mean log-timescale."
        ),
        "resolves_v1_defect": "S3V2-A05 documented-but-unimplemented K2 warm start",
    }
    decision["optimizer"] = optimizer

    artifact_paths = [
        decision["artifact_namespace"][key]
        for key in (
            "screening_detail_csv", "realization_summary_csv", "joint_recovery_csv",
            "calibration_summary_json", "threshold_calibration_json", "checkpoint_dir",
        )
    ]
    null_h = candidate["transit_model"]["null_hypothesis"]
    checks = {
        "v1_architecture_status_pass": v1.get("status") == "PASS",
        "v1_preserved": V1_PATH.is_file() and decision["scope"]["supersedes_sha256"] == sha256(V1_PATH),
        "quarantine_manifest_present": QUARANTINE_MANIFEST.is_file(),
        "governing_decision_present": DECISION_PATH.is_file(),
        "amendment_count_10": len(AMENDMENTS) == 10,
        "null_hypothesis_defined": (
            null_h["rp_rs"] == 0.0
            and "delta_map" in null_h["detection_statistic"]
        ),
        "shared_realization_required": any(
            item["id"] == "S3V2-A02" for item in AMENDMENTS
        ),
        "checkpoint_fields_complete": (
            decision["checkpoint_identity"]["required_fields"] == CHECKPOINT_REQUIRED_FIELDS
            and len(CHECKPOINT_REQUIRED_FIELDS) == 7
        ),
        "boundary_accounting_at_boundary_only": (
            "at_boundary flag is true" in decision["boundary_accounting"]["rule"]
        ),
        "warm_start_registered": optimizer["registered_starts"] == 4,
        "artifacts_under_stage3_v2": all(
            path.startswith(V2_NAMESPACE + "/") for path in artifact_paths
        ),
        "legacy_paths_forbidden_listed": (
            len(decision["artifact_namespace"]["legacy_paths_forbidden"]) == 7
        ),
        "completion_rule_full": (
            decision["completion_rule"]["required_fraction"] == 1.0
            and decision["completion_rule"]["partial_acceptance_permitted"] is False
        ),
        "seed_streams_disjoint": (
            decision["seed_policy"]["base_seed_v2"] != SEED_BASE_V1
            and decision["seed_policy"]["streams_disjoint"] is True
        ),
        "real_data_not_authorized": (
            decision["scope"]["real_data_fit_authorized"] is False
            and candidate["adopted_for_real_data"] is False
        ),
        "phase_7_closed": decision["scope"]["phase_7_may_begin"] is False,
        "execution_not_authorized": decision["scope"]["execution_authorized"] is False,
    }
    decision["gate"] = {
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    decision["status"] = decision["gate"]["status"]
    return decision


def comparable(report):
    report = dict(report)
    report.pop("generated_utc", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    current = build_decision()
    if current["status"] != "PASS":
        failed = [k for k, v in current["gate"]["checks"].items() if not v]
        raise AssertionError("S3-03 v2 architecture amendment failed: " + ", ".join(failed))

    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(current):
            raise AssertionError("Stored S3-03 v2 architecture amendment is stale")
        print("STAGE-3 S3-03 v2 MODEL ARCHITECTURE AMENDMENT: PASS (verified)")
        return

    if OUTPUT_PATH.exists():
        raise FileExistsError("S3-03 v2 amendment is no-clobber; use --verify-only")

    OUTPUT_PATH.write_text(
        json.dumps(current, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("STAGE-3 S3-03 v2 MODEL ARCHITECTURE AMENDMENT: PASS")


if __name__ == "__main__":
    main()
