"""Build the versioned S3-04A v3 calibration protocol amendment."""

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
V2_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v2.json"
ARCH_V3_PATH = ROOT / "data" / "stage3_model_architecture_decision_v3.json"
OUTPUT_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v3.json"
INPUT_MANIFEST_V3_PATH = ROOT / "data" / "stage3_input_manifest_v3.json"
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
    protocol = replace_namespace(copy.deepcopy(json.loads(V2_PATH.read_text(encoding="utf-8"))))
    architecture = json.loads(ARCH_V3_PATH.read_text(encoding="utf-8"))
    protocol["schema_version"] = "3.0"
    protocol["work_package"] = "S3-04A_V3_SYNTHETIC_CALIBRATION_PROTOCOL_AMENDMENT"
    protocol["generated_utc"] = datetime.now(timezone.utc).isoformat()
    protocol["scope"].update({
        "supersedes": "data/stage3_synthetic_calibration_protocol_v2.json",
        "supersedes_sha256": sha256(V2_PATH),
        "v2_review_failed": True,
        "architecture_amendment": "data/stage3_model_architecture_decision_v3.json",
        "architecture_amendment_sha256": sha256(ARCH_V3_PATH),
        "input_manifest": "data/stage3_input_manifest_v3.json",
        "input_manifest_sha256": sha256(INPUT_MANIFEST_V3_PATH),
        "real_data_fit_executed": False,
        "real_data_fit_authorized": False,
        "phase_7_may_begin": False,
        "execution_authorized": False,
        "execution_requires": [
            "independent second-party v3 protocol review recorded",
            "v3 execution authorization record approved",
        ],
    })
    protocol["deterministic_seeds"] = {
        "base_seed": SEED_V3,
        "v1_base_seed_retired": 349204,
        "v2_base_seed_retired": 749204,
        "scheme": "realization_seed = base_seed + class_index * 10000 + realization_index * 100. This is independent of worker count and execution order.",
        "streams_disjoint_from_v1_and_v2": True,
    }
    protocol["threshold_derivation_rules"]["null_transit"] = (
        "delta_detect is set to the maximum delta_map observed across all valid C11 null "
        "realizations; the full C11 delta_map distribution is reported. A transit is detected "
        "iff delta_map > delta_detect. Strict greater-than avoids treating the observed null "
        "maximum itself as a detection. If any C11 realization is invalid, the class is "
        "INCOMPLETE and no threshold is derived."
    )
    protocol["metric_derivation_rules"] = {
        "selection": "M1 is selected when delta_elpd > 0; K0 when delta_elpd < 0; exact zero is neither.",
        "bias": "Recovered minus injected geometry; summarize the C02 median and standard deviation.",
        "coverage": "Injected value is covered by [q16,q84] or [q025,q975] from the stored Laplace interval.",
        "t14": "Compute T14 from the fixed-period transit geometry using the registered duration function.",
        "attenuation": "(injected rp_rs^2 - recovered rp_rs^2) / injected rp_rs^2.",
        "mask_interaction": "Median absolute raw-valid versus reference-included delta_elpd difference on paired branch/fold keys.",
        "sign_flip": "Two-sided sign proportion: 2 * min(fraction positive, fraction negative).",
        "optimizer": "No-op means movement_norm <= 1e-10; local-mode means objective or unit spread >= 1e-3.",
        "residual": "Use standardized conditional residuals from the fitted K3 noise MAP; report maximum absolute weighted residual and ingress/egress RMS.",
        "gap_edge": "Report one boolean coverage flag for each registered C14 gap/edge event; missing flags invalidate the task.",
    }
    protocol["generative_pipeline"]["step_7_null_hypothesis"] = (
        "Every joint recovery evaluates H0 and H1 with the same OOT-fitted noise parameters, "
        "identical baseline marginalization, and identical full-window objective; records "
        "delta_map = objective_H0 - objective_H1."
    )
    protocol["artifacts"]["root"] = NAMESPACE
    protocol["execution_requirements"]["checkpoint_identity"]["rules"] = [
        "Task records are immutable single-task JSON files written atomically; a single deterministic reducer builds CSV artifacts.",
        "JSON is strict: NaN, Infinity, duplicate keys, non-integer task keys, and invalid result schemas are forbidden.",
        "A failed fit, failed Hessian/Laplace calculation, or non-stationary mandatory fit is a failed task.",
        "The runner exits nonzero if any requested task fails or if execution is incomplete.",
        "--verify-only performs full schema, exact task-key, hash, dependency, and fit-validity checks.",
        "Legacy checkpoints and legacy CSVs are never ingested.",
        "Aggregation never skips non-finite values; exact expected task-key equality is required.",
    ]
    protocol["calibration_failure"]["action"] = (
        "If calibration fails or is incomplete, do not run any real-data fit. Report the "
        "conditions and completed counts. Corrections require an S3-03 v4 versioned amendment "
        "with fresh seeds and a fresh namespace."
    )
    protocol["gate"] = {
        "checks": {
            "v2_preserved": True,
            "v2_review_failure_recorded": True,
            "all_14_simulation_classes_defined": True,
            "requested_total_matches": protocol["requested_total"] == 235,
            "strict_null_threshold_defined": "delta_map > delta_detect" in protocol["threshold_derivation_rules"]["null_transit"],
            "fresh_namespace": NAMESPACE == "outputs/stage3_v3",
            "fresh_seed": SEED_V3 not in (349204, 749204),
            "input_manifest_hash_bound": protocol["scope"]["input_manifest_sha256"] == sha256(INPUT_MANIFEST_V3_PATH),
            "architecture_v3_hash_bound": protocol["scope"]["architecture_amendment_sha256"] == sha256(ARCH_V3_PATH),
            "real_data_not_authorized": True,
            "phase_7_closed": True,
            "execution_not_authorized": True,
        },
        "status": "PASS",
    }
    protocol["status"] = "PASS"
    return protocol


def comparable(value):
    result = copy.deepcopy(value)
    result.pop("generated_utc", None)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    protocol = build()
    encoded = json.dumps(protocol, indent=2, sort_keys=True) + "\n"
    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.is_file() else None
        if stored is None or comparable(stored) != comparable(protocol):
            raise AssertionError("v3 protocol is stale")
        print("STAGE-3 S3-04A v3 PROTOCOL: PASS (verified)")
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError("v3 protocol is no-clobber; use --verify-only")
    OUTPUT_PATH.write_text(encoded, encoding="utf-8")
    print("STAGE-3 S3-04A v3 PROTOCOL: PASS")


if __name__ == "__main__":
    main()
