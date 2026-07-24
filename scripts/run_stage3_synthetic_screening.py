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
from pathlib import Path

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
SECTORS = core.SECTORS

_CONTEXT = None


def _init_worker():
    global _CONTEXT
    _CONTEXT = core.load_context()


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
    rows = []
    for held_sector in SECTORS:
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
        if not k0_ok and not m1_ok:
            raise RuntimeError("both K0 and M1 held-sector fit failed")

        rows.append({
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
        })
    return rows


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
        for branch in branches:
            detail.extend(_score_branch(latent, metadata, branch))
        return {
            "ok": True,
            "class_index": class_index,
            "realization_index": realization_index,
            "metadata": metadata,
            "detail": detail,
            "elapsed_seconds": time.time() - started,
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
    frame = pd.DataFrame(rows)
    frame.to_csv(path, mode="a", header=not path.exists(), index=False)


def _realization_summary(result):
    detail = pd.DataFrame(result["detail"])
    branch = detail.groupby(
        ["mask_id", "model_id", "joint_model_weight"], as_index=False,
    )[["k0_score", "m1_score"]].sum()
    log_weights = np.log(branch["joint_model_weight"].to_numpy(np.float64))
    k0 = float(np.logaddexp.reduce(log_weights + branch["k0_score"].to_numpy(np.float64)))
    m1 = float(np.logaddexp.reduce(log_weights + branch["m1_score"].to_numpy(np.float64)))
    metadata = result["metadata"]
    return {
        "protocol_sha256": _CONTEXT.protocol_sha256,
        "class_index": metadata["class_index"],
        "class_name": metadata["class_name"],
        "realization_index": metadata["realization_index"],
        "realization_seed": metadata["realization_seed"],
        "screening_complete": bool(
            detail["model_id"].nunique() == len(_CONTEXT.branches) and
            len(detail) == len(_CONTEXT.branches) * len(SECTORS)
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
    }
    if args.verify_only:
        print("S3-04B synthetic-screening checkpoint is structurally valid")
        return 0
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    if not tasks:
        print("No incomplete realizations selected.")
        return 0

    workers = min(args.workers, cpu_count(), len(tasks))
    print("S3-04B screening: {} realizations, {} workers, {} branches each".format(
        len(tasks), workers, args.branch_limit or len(context.branches),
    ), flush=True)
    with Pool(workers, initializer=_init_worker) as pool:
        for result in pool.imap_unordered(
                _run_realization,
                [(index, realization, args.branch_limit) for index, realization in tasks]):
            if not result["ok"]:
                print("FAILED C{} r{}: {}".format(
                    result["class_index"], result["realization_index"], result["error"],
                ), flush=True)
                continue
            _append_csv(DETAIL_PATH, result["detail"])
            _append_csv(REALIZATION_PATH, [_realization_summary(result)])
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
    parser.add_argument("--branch-limit", type=int,
                        help="Development-only limit; formal runs omit this option.")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
