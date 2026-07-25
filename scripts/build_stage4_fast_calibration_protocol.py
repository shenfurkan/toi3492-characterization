"""Freeze the limited C01/C02 selector pilot used by Stage 4.

This is deliberately a new protocol.  It does not amend the frozen S3-04A
12-class universe and cannot authorize a real-data fit.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "stage4_fast_calibration_protocol.json"
SOURCE_PATHS = (
    "data/stage3_synthetic_calibration_protocol.json",
    "data/stage3_model_architecture_decision.json",
    "scripts/stage3_synthetic_calibration_core.py",
    "scripts/stage3_noise_core.py",
    "scripts/run_stage4_fast_calibration.py",
    "scripts/build_stage4_fast_calibration_protocol.py",
)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_inventory():
    result = {}
    for relative_path in SOURCE_PATHS:
        path = ROOT / relative_path
        result[relative_path] = {
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
    return result


def build_protocol():
    stage3 = json.loads((ROOT / SOURCE_PATHS[0]).read_text(encoding="utf-8"))
    classes = [
        item for item in stage3["simulation_classes"]
        if item["name"] in ("C01_white_jitter_transit", "C02_m1_160_transit")
    ]
    if [item["class_index"] for item in classes] != [0, 1]:
        raise RuntimeError("the Stage-3 C01/C02 class identity changed")
    if any(item["requested_count"] != 30 for item in classes):
        raise RuntimeError("the Stage-3 C01/C02 count is no longer 30")

    return {
        "schema_version": "1.0",
        "work_package": "S4-01_LIMITED_SYNTHETIC_SELECTOR_PILOT",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FROZEN",
        "scope": {
            "purpose": "Bounded operational and selector diagnostic for the C01/C02 simulations.",
            "does_not_amend": "S3-04A 12-class, 210-realization calibration protocol.",
            "real_data_fit_authorized": False,
            "phase_7_may_begin": False,
            "scientific_use": "DIAGNOSTIC_ONLY",
            "forbidden_claims": [
                "full Stage-3 calibration passed",
                "K3 is adopted for TOI-3492.01 real data",
                "joint transit-noise geometry is calibrated",
                "any native-cadence physical parameter is adopted",
            ],
        },
        "inputs": source_inventory(),
        "selected_classes": [
            {
                "class_index": item["class_index"],
                "name": item["name"],
                "requested_count": item["requested_count"],
                "noise_family": item["noise_family"],
            }
            for item in classes
        ],
        "fixed_branch": {
            "model_id": "raw_valid::W16_P1",
            "reason": "One fixed branch avoids invalid likelihood mixing across separately generated branch baselines.",
        },
        "screening": {
            "models": ["K0_white", "K3_MATERN32_SECTOR"],
            "held_out_sectors": [37, 63, 64, 90, 99, 100],
            "training_sectors_per_fold": 5,
            "registered_starts_required": 3,
            "optimizer": "Frozen Stage-3 pooled-MAP implementation",
            "require_all_starts_success": True,
            "require_no_parameter_boundary": True,
            "effective_timescale_boundary_fraction": 0.01,
            "quadrature_nodes": 5,
            "selection_rule": {
                "require_all_six_folds_eligible": True,
                "delta_elpd_rule": "sum(delta_elpd) > 2 * sqrt(n * sample_variance(delta_elpd))",
                "sign_flip_rule": "exact one-sided sign-flip p <= 0.05",
                "minimum_total_delta_elpd": 0.0,
            },
        },
        "execution": {
            "run_directory": "outputs/stage4_fast_calibration",
            "record_format": "one atomic JSON record per class/realization",
            "aggregation": "single parent process writes deterministic summary JSON and CSV after worker results return",
            "maximum_workers": 2,
            "parallel_reproducibility": "semantic equality of deterministic records; records are ordered by class and realization during aggregation",
        },
        "reporting": {
            "required_records": 60,
            "report_false_m1_selection_rate_for": "C01_white_jitter_transit",
            "report_true_m1_selection_rate_for": "C02_m1_160_transit",
            "intervals": "one-sided 95% Clopper-Pearson intervals computed with scipy.stats.beta",
            "completion_rule": "All 60 records must be present; otherwise status is INCOMPLETE.",
        },
        "failure_closure": "Any missing fold, numerical failure, optimizer disagreement, or boundary event is recorded as ineligible. It never becomes a neutral score or a K0-derived K3 fallback.",
    }


def verify_protocol():
    protocol = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    if protocol["status"] != "FROZEN":
        raise RuntimeError("Stage-4 protocol is not frozen")
    if protocol["inputs"] != source_inventory():
        raise RuntimeError("Stage-4 protocol source inventory is stale")
    if protocol["fixed_branch"]["model_id"] != "raw_valid::W16_P1":
        raise RuntimeError("Stage-4 protocol branch changed")
    if protocol["reporting"]["required_records"] != 60:
        raise RuntimeError("Stage-4 protocol record count changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify_protocol()
        print("Stage-4 fast-calibration protocol is structurally valid")
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError("refusing to overwrite frozen protocol: {}".format(OUTPUT_PATH))
    OUTPUT_PATH.write_text(
        json.dumps(build_protocol(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("Wrote {}".format(OUTPUT_PATH))


if __name__ == "__main__":
    main()
