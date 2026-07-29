"""Checkpointed full-universe S3-04B synthetic LOSO screening.

This runner executes the frozen 12-class, 210-realization, 24-branch,
two-mask, six-held-sector screening universe. It is intentionally separate
from transit recovery: no S3-04B calibration gate is emitted until the joint
recovery component is available and merged with this checkpoint.
"""

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool, cpu_count
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from stage3_quarantine import refuse_legacy_execution

if __name__ == "__main__":
    refuse_legacy_execution("scripts/run_stage3_synthetic_screening.py")

# Each realization is already a separate process. Keep numerical libraries
# single-threaded so --workers scales across realizations instead of oversubscribing.
for _thread_var in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_var, "1")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_faz6_noise_models as phase6
import stage3_noise_core as noise
import stage3_synthetic_calibration_core as core


DETAIL_PATH = ROOT / "outputs" / "stage3_synthetic_screening_detail.csv"
REALIZATION_PATH = ROOT / "outputs" / "stage3_synthetic_calibration.csv"
METADATA_PATH = ROOT / "outputs" / "stage3_synthetic_screening_metadata.json"
CHECKPOINT_DIR = ROOT / "outputs" / "stage3_synthetic_screening_checkpoints"
SECTORS = core.SECTORS

DETAIL_COLUMNS = [
    "class_index", "class_name", "realization_index", "realization_seed",
    "protocol_sha256", "model_id", "mask_id", "cell_id", "window_hours",
    "polynomial_degree", "joint_model_weight", "held_sector",
    "k0_score", "m1_score", "delta_elpd", "k0_objective", "m1_objective",
    "k0_boundary_count", "m1_boundary_count", "m1_success",
    "baseline_draws_json", "injected_geometry_json", "sector_noise_json",
]

_CONTEXT = None
_FOLD_WORKERS = 1


def _init_worker(fold_workers=1):
    global _CONTEXT, _FOLD_WORKERS
    _CONTEXT = core.load_context()
    _FOLD_WORKERS = max(1, int(fold_workers))


def _class_spec(class_index):
    return next(
        item for item in _CONTEXT.protocol["simulation_classes"]
        if int(item["class_index"]) == int(class_index)
    )


def _score_branch(latent, metadata, branch):
    branch_frame, baseline_draws = core.apply_branch_baseline(
        latent, _CONTEXT.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, _CONTEXT, branch["mask_id"])
    training, held = phase6.build_model_sector_data(
        mask, _CONTEXT.validation, _CONTEXT.events, _CONTEXT.phase2, branch,
    )
    def score_fold(held_sector):
        sectors = tuple(
            training[sector] for sector in SECTORS if sector != held_sector
        )
        fit_k0 = noise.fit_pooled_map(sectors, "K0_white")
        score_k0 = noise.held_sector_joint_log_predictive_density(
            held[held_sector], fit_k0,
        )
        fit_m1 = noise.fit_pooled_map(sectors, "K3_MATERN32_SECTOR")
        if fit_m1.success:
            score_m1 = noise.held_sector_joint_log_predictive_density(
                held[held_sector], fit_m1,
            )
        else:
            score_m1 = float("nan")

        k0_ok = fit_k0.success and np.isfinite(score_k0)
        m1_ok = fit_m1.success and np.isfinite(score_m1)
        if not k0_ok or not m1_ok:
            raise RuntimeError("K0 or M1 held-sector fit failed")

        return {
            "class_index": metadata["class_index"],
            "class_name": metadata["class_name"],
            "realization_index": metadata["realization_index"],
            "realization_seed": metadata["realization_seed"],
            "protocol_sha256": _CONTEXT.protocol_sha256,
            "model_id": branch["model_id"],
            "mask_id": branch["mask_id"],
            "cell_id": branch["cell_id"],
            "window_hours": branch["window_hours"],
            "polynomial_degree": branch["polynomial_degree"],
            "joint_model_weight": branch["joint_model_weight"],
            "held_sector": held_sector,
            "k0_score": float(score_k0) if np.isfinite(score_k0) else float("nan"),
            "m1_score": float(score_m1) if np.isfinite(score_m1) else float("nan"),
            "delta_elpd": float(score_m1 - score_k0) if m1_ok else float("nan"),
            "k0_objective": float(fit_k0.objective),
            "m1_objective": float(fit_m1.objective) if fit_m1.success else float("nan"),
            "k0_boundary_count": len(fit_k0.boundary_diagnostics),
            "m1_boundary_count": len(fit_m1.boundary_diagnostics) if fit_m1.success else -1,
            "m1_success": fit_m1.success,
            "baseline_draws_json": json.dumps(baseline_draws, sort_keys=True),
            "injected_geometry_json": json.dumps(metadata["drawn_geometry"], sort_keys=True),
            "sector_noise_json": json.dumps(metadata["sector_draws"], sort_keys=True),
        }

    if _FOLD_WORKERS == 1:
        return [score_fold(held_sector) for held_sector in SECTORS]
    with ThreadPoolExecutor(max_workers=min(_FOLD_WORKERS, len(SECTORS))) as executor:
        return list(executor.map(score_fold, SECTORS))


def _branch_checkpoint_path(class_index, realization_index, branch_index):
    return CHECKPOINT_DIR / "c{:03d}_r{:03d}_b{:03d}.json".format(
        class_index, realization_index, branch_index,
    )


def _load_branch_checkpoint(path):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if payload.get("protocol_sha256") != _CONTEXT.protocol_sha256:
        raise RuntimeError("branch checkpoint belongs to a different frozen protocol")
    return payload["detail"]


def _write_branch_checkpoint(path, detail):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp-{}".format(os.getpid()))
    payload = {
        "protocol_sha256": _CONTEXT.protocol_sha256,
        "detail": detail,
    }
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def _run_realization(task):
    class_index, realization_index, branch_limit = task
    started = time.time()
    try:
        spec = _class_spec(class_index)
        latent, metadata = core.generate_latent_realization(
            _CONTEXT, spec, realization_index,
        )
        branches = _CONTEXT.branches[:branch_limit] if branch_limit else _CONTEXT.branches
        detail = []
        resumed = 0
        for b_idx, branch in enumerate(branches):
            b_start = time.time()
            checkpoint_path = _branch_checkpoint_path(
                class_index, realization_index, b_idx,
            )
            res = _load_branch_checkpoint(checkpoint_path)
            branch_resumed = res is not None
            if branch_resumed:
                resumed += 1
            else:
                res = _score_branch(latent, metadata, branch)
                _write_branch_checkpoint(checkpoint_path, res)
            detail.extend(res)
            print("  [C{} r{}] Branch {}/{} ({}) {} in {:.1f}s".format(
                class_index, realization_index, b_idx + 1, len(branches),
                branch["model_id"], "resumed" if branch_resumed
                else "done", time.time() - b_start,
            ), flush=True)
        return {
            "ok": True,
            "class_index": class_index,
            "realization_index": realization_index,
            "metadata": metadata,
            "detail": detail,
            "elapsed_seconds": time.time() - started,
            "resumed_branches": resumed,
        }
    except Exception as exc:
        return {
            "ok": False,
            "class_index": class_index,
            "realization_index": realization_index,
            "error": "{}: {}".format(type(exc).__name__, exc),
            "elapsed_seconds": time.time() - started,
        }


def _load_completed(path, protocol_sha256):
    if not path.exists():
        return set()
    frame = pd.read_csv(path)
    required = {"protocol_sha256", "class_index", "realization_index"}
    if not required.issubset(frame.columns):
        raise RuntimeError("existing checkpoint lacks its required key columns")
    hashes = set(frame["protocol_sha256"].dropna().astype(str))
    if hashes and hashes != {protocol_sha256}:
        raise RuntimeError("existing checkpoint belongs to a different frozen protocol")
    return {
        (int(row.class_index), int(row.realization_index))
        for row in frame.itertuples(index=False)
    }


def _append_csv(path, rows):
    if not rows:
        return
    frame = pd.DataFrame(rows, columns=DETAIL_COLUMNS)
    frame.to_csv(path, mode="a", header=not path.exists(), index=False)


def _write_metadata(metadata):
    temporary = METADATA_PATH.with_suffix(METADATA_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(str(temporary), str(METADATA_PATH))


def _remove_branch_checkpoints(class_index, realization_index, branch_count):
    for branch_index in range(branch_count):
        _branch_checkpoint_path(
            class_index, realization_index, branch_index,
        ).unlink(missing_ok=True)


def _realization_summary(result, context):
    detail = pd.DataFrame(result["detail"])
    branch = detail.groupby(
        ["mask_id", "model_id", "joint_model_weight"], as_index=False,
    )[["k0_score", "m1_score"]].sum()
    log_weights = np.log(branch["joint_model_weight"].to_numpy(np.float64))
    k0 = float(np.logaddexp.reduce(log_weights + branch["k0_score"].to_numpy(np.float64)))
    m1 = float(np.logaddexp.reduce(log_weights + branch["m1_score"].to_numpy(np.float64)))
    metadata = result["metadata"]
    return {
        "protocol_sha256": context.protocol_sha256,
        "class_index": metadata["class_index"],
        "class_name": metadata["class_name"],
        "realization_index": metadata["realization_index"],
        "realization_seed": metadata["realization_seed"],
        "screening_complete": bool(
            detail["model_id"].nunique() == len(context.branches) and
            len(detail) == len(context.branches) * len(SECTORS)
        ),
        "screening_branch_count": int(detail["model_id"].nunique()),
        "screening_fold_count": int(len(detail)),
        "k0_mixture_score": k0,
        "m1_mixture_score": m1,
        "delta_elpd": m1 - k0,
        "injected_geometry_json": json.dumps(metadata["drawn_geometry"], sort_keys=True),
        "sector_noise_json": json.dumps(metadata["sector_draws"], sort_keys=True),
        "telemetry_systematic_json": json.dumps(metadata["telemetry_systematic"], sort_keys=True),
        "elapsed_seconds": result["elapsed_seconds"],
    }


def _tasks(context, class_indices, start, count, completed):
    result = []
    for spec in context.protocol["simulation_classes"]:
        class_index = int(spec["class_index"])
        if class_indices and class_index not in class_indices:
            continue
        stop = int(spec["requested_count"])
        if count is not None:
            stop = min(stop, int(start) + int(count))
        for realization_index in range(int(start), stop):
            key = (class_index, realization_index)
            if key not in completed:
                result.append(key)
    return result


def run(args):
    refuse_legacy_execution("scripts/run_stage3_synthetic_screening.py:run")
    context = core.load_context()
    if args.branch_limit is not None:
        raise ValueError("branch-limited execution cannot write formal calibration artifacts")
    completed = _load_completed(REALIZATION_PATH, context.protocol_sha256)
    class_indices = set(args.class_index) if args.class_index else set()
    tasks = _tasks(context, class_indices, args.start, args.count, completed)
    expected_folds = (args.branch_limit or len(context.branches)) * len(SECTORS)
    metadata = {
        **core.source_metadata(context),
        "runner": "scripts/run_stage3_synthetic_screening.py",
        "screening_only": True,
        "formal_gate_emitted": False,
        "expected_folds_per_realization": expected_folds,
        "workers": min(args.workers, cpu_count()),
        "fold_workers": args.fold_workers,
        "checkpoint_dir": str(CHECKPOINT_DIR.relative_to(ROOT)),
        "total_selected_realizations": len(tasks),
        "completed_realizations": 0,
        "progress_percent": 0.0,
    }
    if args.verify_only:
        if not DETAIL_PATH.exists():
            print("S3-04B synthetic-screening missing detail CSV")
            return 1
        frame = pd.read_csv(DETAIL_PATH)
        if frame["m1_score"].isna().any():
            print("S3-04B verification failed: Found NaN m1_scores in detail CSV")
            return 1
        if list(frame.columns) != DETAIL_COLUMNS:
            print("S3-04B verification failed: Schema mismatch in detail CSV")
            return 1
        print("S3-04B synthetic-screening checkpoint is structurally valid")
        return 0
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    _write_metadata(metadata)
    if not tasks:
        print("No incomplete realizations selected.")
        return 0

    workers = min(args.workers, cpu_count(), len(tasks))
    print("S3-04B screening: {} realizations, {} workers, {} branches each".format(
        len(tasks), workers, args.branch_limit or len(context.branches),
    ), flush=True)
    with Pool(workers, initializer=_init_worker, initargs=(args.fold_workers,)) as pool:
        finished = 0
        for result in pool.imap_unordered(
                _run_realization,
                [(index, realization, args.branch_limit) for index, realization in tasks]):
            if not result["ok"]:
                print("FAILED C{} r{}: {}".format(
                    result["class_index"], result["realization_index"], result["error"],
                ), flush=True)
                continue
            _append_csv(DETAIL_PATH, result["detail"])
            _append_csv(REALIZATION_PATH, [_realization_summary(result, context)])
            _remove_branch_checkpoints(
                result["class_index"], result["realization_index"],
                args.branch_limit or len(context.branches),
            )
            finished += 1
            metadata["completed_realizations"] = finished
            metadata["progress_percent"] = round(100.0 * finished / len(tasks), 2)
            metadata["last_completed"] = "C{} r{}".format(
                result["class_index"], result["realization_index"],
            )
            _write_metadata(metadata)
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
    parser.add_argument(
        "--workers", type=int, default=cpu_count(),
        help="Realization processes (default: all logical CPU cores).",
    )
    parser.add_argument(
        "--fold-workers", type=int, default=1,
        help="Parallel held-sector fits per realization branch; use with care on small hosts.",
    )
    parser.add_argument("--branch-limit", type=int,
                        help="Development-only limit; formal runs omit this option.")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
