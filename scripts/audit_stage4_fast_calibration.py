"""Independently close the Stage-4 limited selector pilot."""

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUN_DIR = ROOT / "outputs" / "stage4_fast_calibration"
SUMMARY_PATH = RUN_DIR / "stage4_fast_calibration_summary.json"
OUTPUT_PATH = ROOT / "outputs" / "stage4_fast_calibration_gate.json"


def _records():
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((RUN_DIR / "records").glob("C*_r*.json"))
    ]


def _failure_counts(records, class_index):
    counts = Counter()
    for record in records:
        if record["class_index"] != class_index:
            continue
        if record["status"] != "COMPLETE":
            counts["realization_failure"] += 1
            continue
        for fold in record["folds"]:
            if fold["eligible"]:
                continue
            k0 = fold.get("k0", {})
            k3 = fold.get("k3", {})
            if not k0.get("eligible", False):
                counts["k0_ineligible_fold"] += 1
            if "k3_error" in fold:
                counts["k3_exception_fold"] += 1
            elif not k3.get("all_registered_starts_success", False):
                counts["k3_multistart_failure_fold"] += 1
            if k3.get("parameter_boundary", False):
                counts["k3_parameter_boundary_fold"] += 1
            if k3.get("effective_timescale_boundary", False):
                counts["k3_timescale_boundary_fold"] += 1
    return dict(sorted(counts.items()))


def main():
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    records = _records()
    c01 = summary["classes"]["C01_white_jitter_transit"]
    c02 = summary["classes"]["C02_m1_160_transit"]
    checks = {
        "all_60_records_complete": summary["status"] == "COMPLETE" and len(records) == 60,
        "c01_all_records_selector_eligible": c01["eligible_records"] == 30,
        "c02_all_records_selector_eligible": c02["eligible_records"] == 30,
        "c01_false_selection_rate_estimable": c01["eligible_records"] == 30,
        "c02_true_selection_rate_at_least_70_percent": (
            c02["m1_selection_rate"] is not None and c02["m1_selection_rate"] >= 0.70
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL_CLAIM_REMOVED"
    report = {
        "schema_version": "1.0",
        "work_package": "S4-01_LIMITED_SYNTHETIC_SELECTOR_PILOT_AUDIT",
        "protocol_sha256": summary["protocol_sha256"],
        "status": status,
        "checks": checks,
        "class_results": {
            "C01_white_jitter_transit": {
                **c01,
                "fold_ineligibility_reasons": _failure_counts(records, 0),
            },
            "C02_m1_160_transit": {
                **c02,
                "fold_ineligibility_reasons": _failure_counts(records, 1),
            },
        },
        "decision": (
            "The frozen C01/C02 selector pilot completed, but K3 is not eligible "
            "for Stage-3 real-data adoption. The K3-dependent native-cadence "
            "claim is removed; real-data authorization and Phase 7 remain closed."
        ),
        "allowed_use": "The completed pilot may be retained as a numerical diagnostic only.",
        "forbidden_use": [
            "K3 adoption for TOI-3492.01 real data",
            "full Stage-3 calibration pass",
            "joint transit/noise geometry calibration",
            "native-cadence physical-parameter adoption",
        ],
    }
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Stage-4 fast-calibration audit: {}".format(status))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
