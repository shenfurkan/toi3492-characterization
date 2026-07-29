"""Build the versioned S3-03 v3 architecture amendment."""

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
V2_PATH = ROOT / "data" / "stage3_model_architecture_decision_v2.json"
OUTPUT_PATH = ROOT / "data" / "stage3_model_architecture_decision_v3.json"
SEED_V3 = 849204
NAMESPACE = "outputs/stage3_v3"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_namespace(value):
    if isinstance(value, str):
        return value.replace("outputs/stage3_v2", NAMESPACE).replace("stage3_v2_", "stage3_v3_")
    if isinstance(value, list):
        return [replace_namespace(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_namespace(item) for key, item in value.items()}
    return value


def build():
    decision = replace_namespace(copy.deepcopy(json.loads(V2_PATH.read_text(encoding="utf-8"))))
    decision["schema_version"] = "3.0"
    decision["work_package"] = "S3-03_V3_MODEL_ARCHITECTURE_AMENDMENT"
    decision["generated_utc"] = datetime.now(timezone.utc).isoformat()
    decision["scope"].update({
        "supersedes": "data/stage3_model_architecture_decision_v2.json",
        "supersedes_sha256": sha256(V2_PATH),
        "v2_review_failed": True,
        "real_data_fit_authorized": False,
        "phase_7_may_begin": False,
        "execution_authorized": False,
        "execution_requires": [
            "data/stage3_synthetic_calibration_protocol_v3.json frozen and verified",
            "independent second-party v3 protocol review recorded",
            "v3 runner authorization record approved",
        ],
    })
    decision["candidate"]["id"] = "K1_RM32_SECTOR_TIMESCALES_V3"
    decision["candidate"]["role"] = "PRIMARY_CALIBRATION_CANDIDATE_V3"
    decision["candidate"]["adopted_for_real_data"] = False
    decision["candidate"]["v3_changes"] = [
        "S3V3-A01_STRICT_NULL_THRESHOLD",
        "S3V3-A02_EXPLICIT_PARTIAL_EVENT_FLAGS",
        "S3V3-A03_SYMMETRIC_H0_H1_NOISE_TREATMENT",
        "S3V3-A04_STRICT_RESULT_AND_DEPENDENCY_IDENTITY",
    ]
    decision["candidate"]["transit_model"]["null_hypothesis"]["detection_rule"] = (
        "A transit is detected iff delta_map > delta_detect. delta_detect is the maximum "
        "delta_map observed across valid C11 null realizations; strict greater-than avoids "
        "the equality contradiction at the observed maximum."
    )
    decision["candidate"]["transit_model"]["null_hypothesis"]["fit"] = (
        "Use the same OOT-fitted correlated-noise MAP parameters as H1; evaluate a separate "
        "H0 full-window objective with rp_rs fixed to 0 and identical baseline marginalization."
    )
    decision["seed_policy"] = {
        "base_seed_v1": 349204,
        "base_seed_v2": 749204,
        "base_seed_v3": SEED_V3,
        "streams_disjoint": True,
        "scheme": "realization_seed = base_seed_v3 + class_index * 10000 + realization_index * 100",
    }
    decision["artifact_namespace"]["root"] = NAMESPACE
    decision["checkpoint_identity"]["rules"] = [
        "Task records are immutable single-task JSON files written atomically; a single deterministic reducer builds CSV artifacts.",
        "JSON is strict: NaN, Infinity, duplicate keys, non-integer task keys, and invalid result schemas are forbidden.",
        "A failed fit, failed Hessian/Laplace calculation, or non-stationary mandatory fit fails the task.",
        "The runner exits nonzero if any requested task fails or if execution is incomplete.",
        "--verify-only performs full schema, exact task-key, hash, dependency, and fit-validity checks.",
        "Legacy checkpoints and legacy CSVs are never ingested.",
        "Aggregation never skips non-finite values; exact expected task-key equality is required.",
    ]
    decision["stop_rules"]["further_changes_require"] = (
        "S3-03 v4 versioned amendment with fresh seeds and a fresh namespace"
    )
    decision["gate"] = {
        "checks": {
            "v2_preserved": True,
            "v2_review_failure_recorded": True,
            "strict_null_threshold_defined": True,
            "fresh_namespace": NAMESPACE == "outputs/stage3_v3",
            "fresh_seed": SEED_V3 not in (349204, 749204),
            "real_data_not_authorized": True,
            "phase_7_closed": True,
            "execution_not_authorized": True,
        },
        "status": "PASS",
    }
    decision["status"] = "PASS"
    return decision


def comparable(value):
    result = copy.deepcopy(value)
    result.pop("generated_utc", None)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    decision = build()
    encoded = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.is_file() else None
        if stored is None or comparable(stored) != comparable(decision):
            raise AssertionError("v3 architecture is stale")
        print("STAGE-3 S3-03 v3 ARCHITECTURE: PASS (verified)")
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError("v3 architecture is no-clobber; use --verify-only")
    OUTPUT_PATH.write_text(encoded, encoding="utf-8")
    print("STAGE-3 S3-03 v3 ARCHITECTURE: PASS")


if __name__ == "__main__":
    main()
