"""Checkpointed S3-04B joint transit-recovery calibration runner."""

import argparse
import json
import sys
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import stage3_joint_model as joint
import stage3_synthetic_calibration_core as core


OUTPUT_PATH = ROOT / "outputs" / "stage3_synthetic_joint_recovery.csv"
METADATA_PATH = ROOT / "outputs" / "stage3_synthetic_joint_recovery_metadata.json"
DECISION_PATH = ROOT / "data" / "stage3_model_architecture_decision.json"

_CONTEXT = None
_DECISION = None


def _init_worker():
    global _CONTEXT, _DECISION
    _CONTEXT = core.load_context()
    _DECISION = json.loads(DECISION_PATH.read_text(encoding="utf-8"))


def _class_spec(class_index):
    return next(
        item for item in _CONTEXT.protocol["simulation_classes"]
        if int(item["class_index"]) == int(class_index)
    )


def _run_realization(task):
    class_index, realization_index = task
    started = time.time()
    try:
        spec = _class_spec(class_index)
        latent, metadata = core.generate_latent_realization(
            _CONTEXT, spec, realization_index,
        )
        rows = []
        for branch in _CONTEXT.branches:
            branch_frame, baseline_draws = core.apply_branch_baseline(
                latent, _CONTEXT.events, branch, metadata["realization_seed"],
            )
            mask = core.derive_mask(branch_frame, _CONTEXT, branch["mask_id"])
            try:
                fit = joint.fit_joint_map(
                    branch, mask, _CONTEXT.events, _CONTEXT.phase2, _DECISION,
                    metadata["realization_seed"] + 1000000 + int(branch["model_index"]),
                    require_stationarity=False,
                )
                row = {
                    "protocol_sha256": _CONTEXT.protocol_sha256,
                    "class_index": metadata["class_index"],
                    "class_name": metadata["class_name"],
                    "realization_index": metadata["realization_index"],
                    "realization_seed": metadata["realization_seed"],
                    "model_id": branch["model_id"],
                    "mask_id": branch["mask_id"],
                    "cell_id": branch["cell_id"],
                    "joint_model_weight": branch["joint_model_weight"],
                    "valid": bool(fit["stationary"]),
                    "objective": fit["objective"],
                    "parameters_json": json.dumps(fit["parameters"].tolist()),
                    "recovered_geometry_json": json.dumps(fit["recovered_geometry"], sort_keys=True),
                    "intervals_json": json.dumps(fit.get("intervals", {}), sort_keys=True),
                    "geometry_covariance_json": json.dumps(
                        fit.get("geometry_covariance", []).tolist()
                        if hasattr(fit.get("geometry_covariance", []), "tolist")
                        else fit.get("geometry_covariance", [])
                    ),
                    "multistart_objective_spread": fit["multistart_objective_spread"],
                    "multistart_unit_parameter_spread": fit["multistart_unit_parameter_spread"],
                    "attempts_json": json.dumps(fit["attempts"], sort_keys=True),
                    "hessian_attempts_json": json.dumps(fit.get("hessian_attempts", []), sort_keys=True),
                    "laplace_draw_diagnostics_json": json.dumps(
                        fit.get("laplace_draw_diagnostics", {}), sort_keys=True,
                    ),
                    "injected_geometry_json": json.dumps(metadata["drawn_geometry"], sort_keys=True),
                    "baseline_draws_json": json.dumps(baseline_draws, sort_keys=True),
                    "sector_noise_json": json.dumps(metadata["sector_draws"], sort_keys=True),
                    "error": "" if fit["stationary"] else "joint MAP failed stationarity",
                }
            except Exception as exc:
                row = {
                    "protocol_sha256": _CONTEXT.protocol_sha256,
                    "class_index": metadata["class_index"],
                    "class_name": metadata["class_name"],
                    "realization_index": metadata["realization_index"],
                    "realization_seed": metadata["realization_seed"],
                    "model_id": branch["model_id"],
                    "mask_id": branch["mask_id"],
                    "cell_id": branch["cell_id"],
                    "joint_model_weight": branch["joint_model_weight"],
                    "valid": False,
                    "objective": None,
                    "parameters_json": "[]",
                    "recovered_geometry_json": "{}",
                    "intervals_json": "{}",
                    "geometry_covariance_json": "[]",
                    "multistart_objective_spread": None,
                    "multistart_unit_parameter_spread": None,
                    "attempts_json": "[]",
                    "hessian_attempts_json": "[]",
                    "laplace_draw_diagnostics_json": "{}",
                    "injected_geometry_json": json.dumps(metadata["drawn_geometry"], sort_keys=True),
                    "baseline_draws_json": json.dumps(baseline_draws, sort_keys=True),
                    "sector_noise_json": json.dumps(metadata["sector_draws"], sort_keys=True),
                    "error": "{}: {}".format(type(exc).__name__, exc).replace("\n", " "),
                }
            rows.append(row)
        return {"ok": True, "rows": rows, "elapsed_seconds": time.time() - started,
                "class_index": class_index, "realization_index": realization_index}
    except Exception as exc:
        return {"ok": False, "class_index": class_index,
                "realization_index": realization_index,
                "error": "{}: {}".format(type(exc).__name__, exc),
                "elapsed_seconds": time.time() - started}


def _completed(context):
    if not OUTPUT_PATH.exists():
        return set()
    frame = pd.read_csv(OUTPUT_PATH, keep_default_na=False)
    required = {"protocol_sha256", "class_index", "realization_index", "model_id"}
    if not required.issubset(frame.columns):
        raise RuntimeError("joint-recovery checkpoint schema mismatch")
    if not frame["protocol_sha256"].eq(context.protocol_sha256).all():
        raise RuntimeError("joint-recovery checkpoint protocol mismatch")
    expected = {branch["model_id"] for branch in context.branches}
    completed = set()
    for key, group in frame.groupby(["class_index", "realization_index"]):
        if set(group["model_id"]) == expected and len(group) == len(expected):
            completed.add((int(key[0]), int(key[1])))
    return completed


def _append(rows):
    if rows:
        pd.DataFrame(rows).to_csv(
            OUTPUT_PATH, mode="a", header=not OUTPUT_PATH.exists(), index=False,
        )


def _tasks(context, selected, start, count, completed):
    tasks = []
    for spec in context.protocol["simulation_classes"]:
        class_index = int(spec["class_index"])
        if selected and class_index not in selected:
            continue
        stop = int(spec["requested_count"])
        if count is not None:
            stop = min(stop, start + count)
        for realization_index in range(start, stop):
            if (class_index, realization_index) not in completed:
                tasks.append((class_index, realization_index))
    return tasks


def run(args):
    context = core.load_context()
    if args.verify_only:
        _completed(context)
        print("S3-04B joint-recovery checkpoint is structurally valid")
        return 0
    tasks = _tasks(context, set(args.class_index or []), args.start, args.count,
                   _completed(context))
    metadata = {
        **core.source_metadata(context),
        "runner": "scripts/run_stage3_synthetic_joint_recovery.py",
        "joint_parameter_count": 24,
        "registered_starts": 3,
        "laplace_draw_count": 4096,
        "formal_gate_emitted": False,
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    if not tasks:
        print("No incomplete realizations selected.")
        return 0
    workers = min(int(args.workers), cpu_count(), len(tasks))
    print("S3-04B joint recovery: {} realizations, {} workers".format(
        len(tasks), workers,
    ), flush=True)
    with Pool(workers, initializer=_init_worker) as pool:
        for result in pool.imap_unordered(_run_realization, tasks):
            if not result["ok"]:
                print("FAILED C{} r{}: {}".format(
                    result["class_index"], result["realization_index"], result["error"],
                ), flush=True)
                continue
            _append(result["rows"])
            print("DONE C{} r{} ({:.0f}s)".format(
                result["class_index"], result["realization_index"],
                result["elapsed_seconds"],
            ), flush=True)
    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--class-index", type=int, action="append")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
