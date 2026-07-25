"""Execute the frozen Stage-4 C01/C02 synthetic selector pilot.

The runner is intentionally limited to one Phase-5B branch.  It reports
K0-versus-K3 held-sector selection diagnostics, not a joint transit/noise
recovery or a Stage-3 adoption decision.
"""

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import sys
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_distribution


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_faz6_noise_models as phase6
import stage3_noise_core as noise
import stage3_synthetic_calibration_core as core


PROTOCOL_PATH = ROOT / "data" / "stage4_fast_calibration_protocol.json"
CONTEXT = None
PROTOCOL = None
PROTOCOL_SHA256 = None
BRANCH = None


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_protocol():
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN":
        raise RuntimeError("Stage-4 protocol is not frozen")
    for relative_path, expected in protocol["inputs"].items():
        path = ROOT / relative_path
        actual = {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
        if actual != expected:
            raise RuntimeError("frozen protocol source changed: {}".format(relative_path))
    return protocol


def _find_branch(context, model_id):
    for branch in context.branches:
        if branch["model_id"] == model_id:
            return branch
    raise RuntimeError("fixed Stage-4 branch is unavailable: {}".format(model_id))


def _init_worker():
    global CONTEXT, PROTOCOL, PROTOCOL_SHA256, BRANCH
    PROTOCOL = _load_protocol()
    PROTOCOL_SHA256 = _sha256(PROTOCOL_PATH)
    CONTEXT = core.load_context()
    BRANCH = _find_branch(CONTEXT, PROTOCOL["fixed_branch"]["model_id"])


def _class_spec(class_index):
    for spec in CONTEXT.protocol["simulation_classes"]:
        if int(spec["class_index"]) == int(class_index):
            return spec
    raise RuntimeError("unknown Stage-4 class index: {}".format(class_index))


def _fit_diagnostics(fit, require_timescale_boundary):
    starts = tuple(fit.optimizer_results[:3])
    finite = [result for result in starts if np.isfinite(result.fun) and result.fun < 1e100]
    successes = [result for result in finite if result.success]
    all_starts_success = len(starts) == 3 and len(successes) == 3
    objective_spread = (float(np.ptp([result.fun for result in successes]))
                        if len(successes) == 3 else None)
    parameter_boundary = any(item.at_boundary for item in fit.boundary_diagnostics)
    effective_timescale_boundary = False
    effective_timescale = {}
    if require_timescale_boundary:
        names = fit.layout.names
        mu = float(fit.parameters[names.index("mu_timescale")])
        low = noise.LOG_TIMESCALE_MINUTES_MIN
        high = noise.LOG_TIMESCALE_MINUTES_MAX
        fraction = float(PROTOCOL["screening"]["effective_timescale_boundary_fraction"])
        for sector in fit.layout.sector_ids:
            delta = float(fit.parameters[names.index("delta_timescale_s{}".format(sector))])
            log_tau = mu + delta
            distance = min(log_tau - low, high - log_tau) / (high - low)
            effective_timescale[str(sector)] = {
                "minutes": float(math.exp(log_tau)),
                "distance_fraction": float(distance),
            }
            effective_timescale_boundary |= distance <= fraction
    eligible = bool(
        fit.success and all_starts_success and not parameter_boundary and
        not effective_timescale_boundary
    )
    return {
        "eligible": eligible,
        "fit_success": bool(fit.success),
        "all_registered_starts_success": all_starts_success,
        "objective_spread": objective_spread,
        "parameter_boundary": parameter_boundary,
        "effective_timescale_boundary": effective_timescale_boundary,
        "effective_timescale": effective_timescale,
        "optimizer_messages": [str(result.message) for result in starts],
    }


def exact_one_sided_sign_flip_pvalue(deltas):
    values = np.asarray(deltas, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or np.any(~np.isfinite(values)):
        return None
    observed = float(np.sum(values))
    totals = np.fromiter(
        (float(np.dot(signs, values)) for signs in itertools.product((-1.0, 1.0), repeat=len(values))),
        dtype=np.float64,
    )
    return float(np.mean(totals >= observed - 1e-12))


def select_m1(folds):
    if len(folds) != 6 or not all(fold["eligible"] for fold in folds):
        return {"status": "INELIGIBLE", "m1_selected": False, "delta_elpd": None,
                "standard_error": None, "sign_flip_p_value": None}
    deltas = np.asarray([fold["delta_elpd"] for fold in folds], dtype=np.float64)
    if np.any(~np.isfinite(deltas)):
        return {"status": "INELIGIBLE", "m1_selected": False, "delta_elpd": None,
                "standard_error": None, "sign_flip_p_value": None}
    total = float(np.sum(deltas))
    standard_error = float(math.sqrt(len(deltas) * np.var(deltas, ddof=1)))
    p_value = exact_one_sided_sign_flip_pvalue(deltas)
    rule = PROTOCOL["screening"]["selection_rule"]
    selected = bool(
        total > max(float(rule["minimum_total_delta_elpd"]), 2.0 * standard_error) and
        p_value <= 0.05
    )
    return {
        "status": "ELIGIBLE",
        "m1_selected": selected,
        "delta_elpd": total,
        "standard_error": standard_error,
        "sign_flip_p_value": p_value,
    }


def _run_realization(task):
    class_index, realization_index = task
    started = time.time()
    try:
        spec = _class_spec(class_index)
        latent, metadata = core.generate_latent_realization(CONTEXT, spec, realization_index)
        branch_frame, baseline_draws = core.apply_branch_baseline(
            latent, CONTEXT.events, BRANCH, metadata["realization_seed"],
        )
        mask = core.derive_mask(branch_frame, CONTEXT, BRANCH["mask_id"])
        training, held = phase6.build_model_sector_data(
            mask, CONTEXT.validation, CONTEXT.events, CONTEXT.phase2, BRANCH,
        )
        folds = []
        for held_sector in core.SECTORS:
            sectors = tuple(training[sector] for sector in core.SECTORS if sector != held_sector)
            fold = {"held_sector": int(held_sector), "eligible": False}
            try:
                k0_fit = noise.fit_pooled_map(sectors, "K0_white")
                k0 = _fit_diagnostics(k0_fit, require_timescale_boundary=False)
                fold["k0"] = k0
                if k0["eligible"]:
                    fold["k0_score"] = float(noise.held_sector_joint_log_predictive_density(
                        held[held_sector], k0_fit,
                    ))
            except Exception as exc:
                fold["k0_error"] = "{}: {}".format(type(exc).__name__, exc)
            try:
                k3_fit = noise.fit_pooled_map(sectors, "K3_MATERN32_SECTOR")
                k3 = _fit_diagnostics(k3_fit, require_timescale_boundary=True)
                fold["k3"] = k3
                if k3["eligible"]:
                    fold["k3_score"] = float(noise.held_sector_joint_log_predictive_density(
                        held[held_sector], k3_fit, nodes=PROTOCOL["screening"]["quadrature_nodes"],
                    ))
            except Exception as exc:
                fold["k3_error"] = "{}: {}".format(type(exc).__name__, exc)
            fold["eligible"] = bool(
                fold.get("k0", {}).get("eligible") and fold.get("k3", {}).get("eligible") and
                np.isfinite(fold.get("k0_score", np.nan)) and np.isfinite(fold.get("k3_score", np.nan))
            )
            if fold["eligible"]:
                fold["delta_elpd"] = float(fold["k3_score"] - fold["k0_score"])
            folds.append(fold)
        selection = select_m1(folds)
        return {
            "schema_version": "1.0",
            "protocol_sha256": PROTOCOL_SHA256,
            "status": "COMPLETE",
            "class_index": int(class_index),
            "class_name": metadata["class_name"],
            "realization_index": int(realization_index),
            "realization_seed": int(metadata["realization_seed"]),
            "branch": BRANCH["model_id"],
            "injected_geometry": metadata["drawn_geometry"],
            "sector_noise": metadata["sector_draws"],
            "baseline_draws": baseline_draws,
            "folds": folds,
            "selection": selection,
            "elapsed_seconds": time.time() - started,
        }
    except Exception as exc:
        return {
            "schema_version": "1.0",
            "protocol_sha256": PROTOCOL_SHA256,
            "status": "FAILED",
            "class_index": int(class_index),
            "realization_index": int(realization_index),
            "error": "{}: {}".format(type(exc).__name__, exc),
            "elapsed_seconds": time.time() - started,
        }


def _record_path(run_dir, class_index, realization_index):
    return run_dir / "records" / "C{:02d}_r{:03d}.json".format(class_index + 1, realization_index)


def _read_record(path, protocol_sha256):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("protocol_sha256") != protocol_sha256:
        raise RuntimeError("record belongs to another protocol: {}".format(path))
    return record


def _atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _clopper_pearson(successes, trials, alpha=0.05):
    if trials == 0:
        return None, None
    lower = 0.0 if successes == 0 else float(beta_distribution.ppf(alpha, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta_distribution.ppf(1.0 - alpha, successes + 1, trials - successes))
    return lower, upper


def _class_summary(records, class_index):
    selected = [record for record in records if record["class_index"] == class_index]
    complete = [record for record in selected if record["status"] == "COMPLETE"]
    eligible = [record for record in complete if record.get("selection", {}).get("status") == "ELIGIBLE"]
    successes = sum(record["selection"]["m1_selected"] for record in eligible)
    lower, upper = _clopper_pearson(successes, len(eligible))
    return {
        "requested_records": 30,
        "records_present": len(selected),
        "completed_records": len(complete),
        "eligible_records": len(eligible),
        "ineligible_or_failed_records": len(selected) - len(eligible),
        "m1_selected_records": int(successes),
        "m1_selection_rate": float(successes / len(eligible)) if eligible else None,
        "one_sided_95_clopper_pearson": {"lower": lower, "upper": upper},
    }


def _write_aggregation(run_dir, protocol_sha256):
    records = []
    for path in sorted((run_dir / "records").glob("C*_r*.json")):
        records.append(_read_record(path, protocol_sha256))
    records.sort(key=lambda item: (item["class_index"], item["realization_index"]))
    c01 = _class_summary(records, 0)
    c02 = _class_summary(records, 1)
    complete = len(records) == 60 and all(record["status"] == "COMPLETE" for record in records)
    report = {
        "schema_version": "1.0",
        "work_package": "S4-01_LIMITED_SYNTHETIC_SELECTOR_PILOT",
        "protocol_sha256": protocol_sha256,
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "scientific_use": "DIAGNOSTIC_ONLY",
        "does_not_authorize_real_data": True,
        "records_present": len(records),
        "required_records": 60,
        "classes": {
            "C01_white_jitter_transit": c01,
            "C02_m1_160_transit": c02,
        },
        "interpretation": {
            "c01": "M1 selection rate is the limited pilot false-selection estimate.",
            "c02": "M1 selection rate is the limited pilot nominal-model selection estimate.",
            "not_estimated": [
                "joint geometry bias or coverage",
                "24-branch mixture behavior",
                "mask interaction",
                "null-transit behavior",
                "misspecification and boundary classes",
                "real-data suitability",
            ],
        },
    }
    _atomic_write_json(run_dir / "stage4_fast_calibration_summary.json", report)
    rows = []
    for record in records:
        selection = record.get("selection", {})
        rows.append({
            "class_index": record["class_index"],
            "class_name": record.get("class_name", ""),
            "realization_index": record["realization_index"],
            "status": record["status"],
            "selection_status": selection.get("status", ""),
            "m1_selected": selection.get("m1_selected", False),
            "delta_elpd": selection.get("delta_elpd"),
            "standard_error": selection.get("standard_error"),
            "sign_flip_p_value": selection.get("sign_flip_p_value"),
            "elapsed_seconds": record.get("elapsed_seconds"),
        })
    with (run_dir / "stage4_fast_calibration_records.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["class_index"])
        writer.writeheader()
        writer.writerows(rows)
    return report


def _tasks(protocol, selected_classes, start, count, run_dir, protocol_sha256):
    selected = set(selected_classes or [0, 1])
    permitted = {item["class_index"] for item in protocol["selected_classes"]}
    if not selected.issubset(permitted):
        raise ValueError("Stage-4 protocol permits only C01 and C02")
    tasks = []
    for class_index in sorted(selected):
        stop = 30 if count is None else min(30, start + count)
        for realization_index in range(start, stop):
            path = _record_path(run_dir, class_index, realization_index)
            if path.exists():
                _read_record(path, protocol_sha256)
            else:
                tasks.append((class_index, realization_index))
    return tasks


def run(args):
    protocol = _load_protocol()
    protocol_sha256 = _sha256(PROTOCOL_PATH)
    run_dir = Path(args.run_dir).resolve()
    if args.count is not None and not args.allow_partial:
        raise ValueError("partial execution requires --allow-partial")
    if args.workers < 1 or args.workers > protocol["execution"]["maximum_workers"]:
        raise ValueError("workers must be between 1 and {}".format(protocol["execution"]["maximum_workers"]))
    if args.verify_only:
        report = _write_aggregation(run_dir, protocol_sha256)
        print("Stage-4 fast calibration: {}".format(report["status"]))
        return report
    tasks = _tasks(protocol, args.class_index, args.start, args.count, run_dir, protocol_sha256)
    if tasks:
        print("Stage-4 C01/C02 selector pilot: {} records, {} workers".format(
            len(tasks), min(args.workers, cpu_count(), len(tasks)),
        ), flush=True)
    if args.workers == 1:
        _init_worker()
        results = map(_run_realization, tasks)
    else:
        workers = min(args.workers, cpu_count(), len(tasks))
        pool = Pool(workers, initializer=_init_worker)
        results = pool.imap_unordered(_run_realization, tasks)
    try:
        for result in results:
            path = _record_path(run_dir, result["class_index"], result["realization_index"])
            _atomic_write_json(path, result)
            print("{} C{:02d} r{:02d} ({:.0f}s)".format(
                result["status"], result["class_index"] + 1,
                result["realization_index"], result["elapsed_seconds"],
            ), flush=True)
    finally:
        if args.workers > 1 and tasks:
            pool.close()
            pool.join()
    report = _write_aggregation(run_dir, protocol_sha256)
    print("Stage-4 aggregation: {} ({}/{})".format(
        report["status"], report["records_present"], report["required_records"],
    ), flush=True)
    return report


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default=str(ROOT / "outputs" / "stage4_fast_calibration"))
    parser.add_argument("--class-index", type=int, action="append")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
