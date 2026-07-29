"""Superseded Stage-3 v2 runner retained only for provenance.

Execution cannot be restored by editing the historical authorization record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

if __name__ == "__main__":
    for _thread_var in (
        "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(_thread_var, "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from stage3_quarantine import (
    LegacyStage3QuarantineError,
    refuse_superseded_execution,
)

if __name__ == "__main__":
    try:
        refuse_superseded_execution(
            "scripts/run_stage3_synthetic_calibration_v2.py",
            2,
            "SUPERSEDED_REVIEW_FAILED",
        )
    except LegacyStage3QuarantineError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)

import numpy as np
import pandas as pd

import run_faz6_noise_models as phase6
import run_faz5_window_grid as phase5
import stage3_joint_model as joint
import stage3_v2_runtime as runtime
import stage3_synthetic_calibration_core_v2 as core
import stage3_noise_core as noise


def _finite(value):
    return float(value) if np.isfinite(value) else None


def _boundary_count(diagnostics):
    return int(sum(bool(item.at_boundary) for item in diagnostics))


def _latent_hash(frame):
    digest = hashlib.sha256()
    columns = ("sector", "cadenceno", "time_btjd", "flux", "flux_err")
    values = frame.loc[:, columns].sort_values(["sector", "cadenceno"])
    digest.update(pd.util.hash_pandas_object(values, index=False).to_numpy().tobytes())
    return digest.hexdigest()


def _class_spec(context, class_index):
    return next(
        item for item in context.protocol["simulation_classes"]
        if int(item["class_index"]) == int(class_index)
    )


def _screening_result(context, spec, key, latent, metadata, branch):
    branch_frame, baseline_draws = core.apply_branch_baseline(
        latent, context.events_for_class(spec), branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])
    events = context.events_for_class(spec)
    usable_events = []
    gap_flags = {}
    for event in events:
        event_rows = phase5.event_rows(mask, event, branch["window_hours"] / 48.0)
        if event_rows.empty:
            if event.get("used", True):
                raise RuntimeError(
                    "complete event has no screening cadence: {}".format(
                        event["physical_event_id"]
                    )
                )
            gap_flags[event["physical_event_id"]] = False
            continue
        usable_events.append(event)
        if not event.get("used", True):
            gap_flags[event["physical_event_id"]] = True
    events = tuple(usable_events)
    training, held = phase6.build_model_sector_data(
        mask, context.validation, events, context.phase2, branch,
    )
    sectors = tuple(training[sector] for sector in core.SECTORS if sector != key.held_sector)
    fit_k0 = noise.fit_pooled_map(sectors, "K0_white")
    fit_m1 = noise.fit_pooled_map(
        sectors, "K3_MATERN32_SECTOR", use_warm_start=True,
    )
    if not fit_k0.success or not fit_m1.success:
        raise RuntimeError("screening K0 or M1 pooled MAP failed")
    score_k0 = noise.held_sector_joint_log_predictive_density(
        held[key.held_sector], fit_k0,
    )
    score_m1 = noise.held_sector_joint_log_predictive_density(
        held[key.held_sector], fit_m1,
    )
    if not np.isfinite(score_k0) or not np.isfinite(score_m1):
        raise RuntimeError("screening score is non-finite")
    return {
        "class_name": spec["name"],
        "model_id": branch["model_id"],
        "mask_id": branch["mask_id"],
        "cell_id": branch["cell_id"],
        "held_sector": int(key.held_sector),
        "k0_score": float(score_k0),
        "m1_score": float(score_m1),
        "delta_elpd": float(score_m1 - score_k0),
        "k0_objective": float(fit_k0.objective),
        "m1_objective": float(fit_m1.objective),
        "k0_boundary_count": _boundary_count(fit_k0.boundary_diagnostics),
        "m1_boundary_count": _boundary_count(fit_m1.boundary_diagnostics),
        "baseline_draws": baseline_draws,
        "injected_geometry": metadata["drawn_geometry"],
        "sector_noise": metadata["sector_draws"],
        "gap_edge_event_recovery_flags": gap_flags,
    }


def _joint_result(context, spec, key, latent, metadata, branch, decision):
    branch_frame, baseline_draws = core.apply_branch_baseline(
        latent, context.events_for_class(spec), branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])
    events = context.events_for_class(spec)
    seed = metadata["realization_seed"] + 1000000 + int(branch["model_index"])
    fit_h1 = joint.fit_joint_map(
        branch, mask, events, context.phase2, decision, seed,
        require_stationarity=True, expected_event_count=len(events),
        use_v2_starts=True,
    )
    fit_h0 = joint.fit_joint_null_map(
        branch, mask, events, decision, expected_event_count=len(events),
        noise_parameters=fit_h1["noise_parameters"],
    )
    if not fit_h1.get("success") or not fit_h0.get("success"):
        raise RuntimeError("joint H0/H1 MAP fit failed")
    objective_h1 = float(fit_h1["objective"])
    objective_h0 = float(fit_h0["objective"])
    if not np.isfinite(objective_h1) or not np.isfinite(objective_h0):
        raise RuntimeError("joint H0/H1 objective is non-finite")
    event_coverage = fit_h1.get("event_coverage", {})
    gap_flags = {
        event["physical_event_id"]: bool(event_coverage.get(event["physical_event_id"], 0))
        for event in events if not event.get("used", True)
    }
    injected_geometry = metadata["drawn_geometry"]
    injected_t14_hours = None
    if injected_geometry is not None:
        injected_t14_hours = float(phase5.duration_hours([[
            injected_geometry["rp_rs"], injected_geometry["a_rs"],
            injected_geometry["impact_parameter"],
        ]], context.phase2["ephemeris_and_windows"]["period_days"])[0])
    return {
        "class_name": spec["name"],
        "model_id": branch["model_id"],
        "mask_id": branch["mask_id"],
        "cell_id": branch["cell_id"],
        "objective_h0": objective_h0,
        "objective_h1": objective_h1,
        "delta_map": objective_h0 - objective_h1,
        "h1_stationary": bool(fit_h1.get("stationary", False)),
        "h1_recovered_geometry": fit_h1["recovered_geometry"],
        "h1_intervals": fit_h1.get("intervals", {}),
        "h1_boundary_count": _boundary_count(
            fit_h1.get("boundary_diagnostics", ())
        ) if fit_h1.get("boundary_diagnostics") else None,
        "h0_boundary_count": _boundary_count(fit_h0["boundary_diagnostics"]),
        "gap_edge_event_recovery_flags": gap_flags,
        "injected_t14_hours": injected_t14_hours,
        "h1_attempts": fit_h1["attempts"],
        "h1_multistart_objective_spread": float(fit_h1["multistart_objective_spread"]),
        "h1_multistart_unit_parameter_spread": float(
            fit_h1["multistart_unit_parameter_spread"]
        ),
        **fit_h1["residual_diagnostics"],
        "baseline_draws": baseline_draws,
        "injected_geometry": metadata["drawn_geometry"],
        "sector_noise": metadata["sector_draws"],
    }


def run_one(context, identity, decision, task_type, key):
    refuse_superseded_execution(
        "scripts/run_stage3_synthetic_calibration_v2.py:run_one",
        2,
        "SUPERSEDED_REVIEW_FAILED",
    )
    spec = _class_spec(context, key.class_index)
    if key.branch_index < 0 or key.branch_index >= len(context.branches):
        raise RuntimeError("branch index is outside the frozen 24-branch universe")
    if task_type == "screening" and key.held_sector not in core.SECTORS:
        raise RuntimeError("screening task has an invalid held sector")
    if task_type == "joint" and key.held_sector != runtime.JOINT_HELD_SECTOR:
        raise RuntimeError("joint task must use the -1 held-sector sentinel")
    latent, metadata = core.generate_latent_realization(
        context, spec, key.realization_index,
    )
    branch = context.branches[key.branch_index]
    if task_type == "screening":
        result = _screening_result(context, spec, key, latent, metadata, branch)
    else:
        result = _joint_result(context, spec, key, latent, metadata, branch, decision)
    result.update({
        "realization_seed": int(metadata["realization_seed"]),
        "latent_sha256": _latent_hash(latent),
    })
    return runtime.make_task_record(identity, task_type, key, "completed", result=result)


def _selected_keys(protocol, task_type, class_indices, realization_indices):
    keys = runtime.expected_task_keys(protocol, task_type)
    classes = set(class_indices or [])
    realizations = set(realization_indices or [])
    return tuple(
        key for key in keys
        if (not classes or key.class_index in classes)
        and (not realizations or key.realization_index in realizations)
    )


def _write_records(root, records):
    refuse_superseded_execution(
        "scripts/run_stage3_synthetic_calibration_v2.py:_write_records",
        2,
        "SUPERSEDED_REVIEW_FAILED",
    )
    for task_type, key, record in records:
        path = runtime.checkpoint_path(root, task_type, key)
        runtime.write_immutable_json(path, record)


def _derive_metric_summary(screening_rows, joint_rows):
    screening = pd.DataFrame(screening_rows)
    joint = pd.DataFrame(joint_rows)
    delta = screening["delta_elpd"].to_numpy(float)
    positive = int(np.sum(delta > 0.0))
    negative = int(np.sum(delta < 0.0))
    zero = int(np.sum(delta == 0.0))
    sign_flip = 2.0 * min(positive, negative) / len(delta) if len(delta) else np.nan
    raw = screening.loc[screening["mask_id"] == "raw_valid"]
    reference = screening.loc[screening["mask_id"] == "reference_included"]
    paired = raw.merge(
        reference,
        on=["class_index", "realization_index", "cell_id", "held_sector"],
        suffixes=("_raw", "_reference"),
    )
    mask_interaction = float(
        np.median(np.abs(paired["delta_elpd_raw"] - paired["delta_elpd_reference"]))
    ) if len(paired) else np.nan

    bias = {name: [] for name in ("rp_rs", "a_rs", "impact_parameter", "t14_hours")}
    coverage = {name: {"68": [], "95": []} for name in bias}
    attenuation = []
    gap_flags = []
    for row in joint.to_dict("records"):
        injected = row.get("injected_geometry")
        recovered = row.get("h1_recovered_geometry")
        intervals = row.get("h1_intervals")
        if injected is None or recovered is None or not intervals:
            continue
        for name in ("rp_rs", "a_rs", "impact_parameter"):
            bias[name].append(float(recovered[name]) - float(injected[name]))
            interval = intervals[name]
            coverage[name]["68"].append(float(interval[1]) <= float(injected[name]) <= float(interval[2]))
            coverage[name]["95"].append(float(interval[0]) <= float(injected[name]) <= float(interval[3]))
        injected_t14 = float(row["injected_t14_hours"])
        recovered_t14 = float(phase5.duration_hours([[
            recovered["rp_rs"], recovered["a_rs"], recovered["impact_parameter"],
        ]], 9.2224171)[0])
        bias["t14_hours"].append(recovered_t14 - injected_t14)
        interval = intervals["t14_hours"]
        coverage["t14_hours"]["68"].append(float(interval[1]) <= injected_t14 <= float(interval[2]))
        coverage["t14_hours"]["95"].append(float(interval[0]) <= injected_t14 <= float(interval[3]))
        attenuation.append(
            (float(injected["rp_rs"]) ** 2 - float(recovered["rp_rs"]) ** 2)
            / float(injected["rp_rs"]) ** 2
        )
        gap_flags.extend(row.get("gap_edge_event_recovery_flags", {}).values())

    result = {
        "delta_elpd_m1_vs_k0": float(np.median(delta)),
        "sign_flip_p_value": float(sign_flip),
        "mask_interaction": mask_interaction,
        "k0_selected": float(negative / len(delta)) if len(delta) else np.nan,
        "m1_selected": float(positive / len(delta)) if len(delta) else np.nan,
        "neither_selected": float(zero / len(delta)) if len(delta) else np.nan,
        "any_parameter_at_boundary": float(np.mean(
            (screening["k0_boundary_count"] > 0)
            | (screening["m1_boundary_count"] > 0)
        )),
        "transit_depth_attenuation_fraction": float(np.median(attenuation)) if attenuation else np.nan,
        "optimizer_no_op_count": int(joint["optimizer_no_op_count"].sum()),
        "optimizer_local_mode_count": int(joint["optimizer_local_mode_count"].sum()),
        "weighted_residual_beta_max": float(joint["weighted_residual_beta_max"].max()),
        "ingress_egress_rms_residual_mm_s": float(
            np.sqrt(np.mean(np.square(joint["ingress_egress_rms_residual_mm_s"])))
        ),
        "gap_edge_event_recovery_flags": {
            "S037-E002": bool(gap_flags[0]) if len(gap_flags) >= 2 else False,
            "S099-E189": bool(gap_flags[1]) if len(gap_flags) >= 2 else False,
        },
    }
    for name, values in bias.items():
        result[name + "_bias"] = float(np.median(values)) if values else np.nan
        result[name + "_coverage_68"] = float(np.mean(coverage[name]["68"])) if values else np.nan
        result[name + "_coverage_95"] = float(np.mean(coverage[name]["95"])) if values else np.nan
    return result


def _evaluate_calibration_gates(protocol, screening_frame, joint_frame, class_summary, c11,
                                metric_summary):
    declared = sorted({
        quantity
        for spec in protocol["simulation_classes"]
        for quantity in spec["evaluation"]["measured_quantities"]
    })
    implemented = {
        "delta_elpd_m1_vs_k0", "k0_selected", "m1_selected", "neither_selected",
        "any_parameter_at_boundary", "gap_edge_event_recovery_flags",
        "rp_rs_bias", "a_rs_bias", "impact_parameter_bias", "t14_bias",
        "rp_rs_coverage_68", "rp_rs_coverage_95", "a_rs_coverage_68",
        "a_rs_coverage_95", "impact_parameter_coverage_68",
        "impact_parameter_coverage_95", "t14_coverage_68", "t14_coverage_95",
        "transit_depth_attenuation_fraction", "ingress_egress_rms_residual_mm_s",
        "optimizer_no_op_count", "optimizer_local_mode_count", "weighted_residual_beta_max",
    }
    missing_metrics = sorted(set(declared) - implemented)
    metric_values_finite = all(
        isinstance(value, (int, float)) and np.isfinite(value)
        for key, value in metric_summary.items()
        if key != "gap_edge_event_recovery_flags"
    )
    checks = {
        "all_classes_complete": all(item["complete"] for item in class_summary),
        "screening_record_count_exact": len(screening_frame) == 235 * 24 * 6,
        "joint_record_count_exact": len(joint_frame) == 235 * 24,
        "all_h1_stationary": bool(joint_frame["h1_stationary"].all()),
        "c11_finite": bool(len(c11) == 240 and np.isfinite(c11).all()),
        "strict_null_detection_zero": bool(np.sum(c11 > np.max(c11)) == 0),
        "declared_metric_coverage": not missing_metrics,
        "derived_metric_values_finite": metric_values_finite,
    }
    return {
        "status": "PASS" if all(checks.values()) else "INCOMPLETE",
        "checks": checks,
        "declared_metrics": declared,
        "implemented_metrics": sorted(implemented & set(declared)),
        "missing_metrics": missing_metrics,
        "metric_summary": metric_summary,
        "real_data_fit_authorized": False,
        "phase_7_authorized": False,
    }


def _reduce(root, protocol, identity):
    refuse_superseded_execution(
        "scripts/run_stage3_synthetic_calibration_v2.py:_reduce",
        2,
        "SUPERSEDED_REVIEW_FAILED",
    )
    summary = runtime.verify_namespace(root, protocol, identity, allow_partial=False)
    rows = {"screening": [], "joint": []}
    for task_type in runtime.TASK_TYPES:
        for key in runtime.expected_task_keys(protocol, task_type):
            record = runtime.validate_task_record(
                runtime.checkpoint_path(root, task_type, key), identity, task_type, key,
            )
            row = {
                **key.as_dict(),
                "task_type": task_type,
                **record["result"],
            }
            rows[task_type].append(row)
    stage3_root = root / "outputs" / runtime.NAMESPACE
    output_paths = {
        "screening": stage3_root / (runtime.NAMESPACE + "_screening_detail.csv"),
        "joint": stage3_root / (runtime.NAMESPACE + "_joint_recovery.csv"),
    }
    for task_type, path in output_paths.items():
        frame = pd.DataFrame(rows[task_type]).sort_values(
            ["class_index", "realization_index", "branch_index", "held_sector"],
        )
        temporary = path.with_suffix(path.suffix + ".tmp")
        frame.to_csv(temporary, index=False)
        os.replace(str(temporary), str(path))
    realization_rows = []
    for (class_index, realization_index), group in pd.DataFrame(
            rows["joint"]
    ).groupby(["class_index", "realization_index"], sort=True):
        realization_rows.append({
            "class_index": int(class_index),
            "realization_index": int(realization_index),
            "joint_branch_count": int(group["branch_index"].nunique()),
            "joint_complete": bool(len(group) == 24),
        })
    summary_path = stage3_root / (runtime.NAMESPACE + "_synthetic_calibration.csv")
    pd.DataFrame(realization_rows).to_csv(summary_path, index=False)
    class_summary = []
    joint_frame = pd.DataFrame(rows["joint"])
    for class_index, group in joint_frame.groupby("class_index", sort=True):
        requested = next(
            int(item["requested_count"])
            for item in protocol["simulation_classes"]
            if int(item["class_index"]) == int(class_index)
        )
        realization_count = int(group["realization_index"].nunique())
        class_summary.append({
            "class_index": int(class_index),
            "requested_realizations": requested,
            "completed_realizations": realization_count,
            "complete": realization_count == requested and bool(group["h1_stationary"].all()),
        })
    c11 = joint_frame.loc[joint_frame["class_index"] == 10, "delta_map"].to_numpy(float)
    if len(c11) == 0 or not np.isfinite(c11).all():
        raise RuntimeError("C11 null distribution is incomplete or non-finite")
    metric_summary = _derive_metric_summary(rows["screening"], rows["joint"])
    gate_evaluation = _evaluate_calibration_gates(
        protocol, pd.DataFrame(rows["screening"]), joint_frame, class_summary, c11,
        metric_summary,
    )
    calibration_summary = {
        "schema_version": protocol["schema_version"],
        "record_type": "STAGE3_V3_CALIBRATION_SUMMARY",
        "namespace": runtime.NAMESPACE,
        "complete": bool(summary["complete"]),
        "class_summary": class_summary,
        "screening_record_count": len(rows["screening"]),
        "joint_record_count": len(rows["joint"]),
        "gate_status": gate_evaluation["status"],
        "gate_evaluation": gate_evaluation,
        "real_data_fit_authorized": False,
        "phase_7_authorized": False,
    }
    summary_json = stage3_root / (runtime.NAMESPACE + "_calibration_summary.json")
    summary_json.write_text(
        json.dumps(calibration_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    delta_detect = float(np.max(c11))
    threshold = {
        "schema_version": protocol["schema_version"],
        "record_type": "STAGE3_V3_THRESHOLD_CALIBRATION",
        "namespace": runtime.NAMESPACE,
        "class_index": 10,
        "valid_c11_count": int(len(c11)),
        "delta_detect": delta_detect,
        "detection_rule": "delta_map > delta_detect",
        "null_detection_count": int(np.sum(c11 > delta_detect)),
        "gate_status": "PASS" if int(np.sum(c11 > delta_detect)) == 0 else "FAIL",
        "real_data_fit_authorized": False,
        "phase_7_authorized": False,
    }
    threshold_json = stage3_root / (runtime.NAMESPACE + "_threshold_calibration.json")
    threshold_json.write_text(
        json.dumps(threshold, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if gate_evaluation["status"] != "PASS":
        raise RuntimeError(
            "declared calibration gates are incomplete: {}".format(
                gate_evaluation["missing_metrics"]
            )
        )
    return summary


def run(args):
    try:
        refuse_superseded_execution(
            "scripts/run_stage3_synthetic_calibration_v2.py:run",
            2,
            "SUPERSEDED_REVIEW_FAILED",
        )
    except LegacyStage3QuarantineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    root = ROOT
    try:
        preflight = runtime.preflight(root)
    except Exception as exc:
        print("V2 preflight failed: {}".format(exc), file=sys.stderr)
        return 1
    protocol = preflight["protocol"]
    identity = preflight["identity"]
    if args.preflight:
        print(json.dumps({
            "execution_authorized": preflight["execution_authorized"],
            "authorization_status": preflight["authorization"]["status"],
            "expected_screening_records": preflight["expected_screening_records"],
            "expected_joint_records": preflight["expected_joint_records"],
            "expected_joint_fits": preflight["expected_joint_fits"],
            "identity": identity,
        }, indent=2, sort_keys=True))
        return 0
    if args.verify_only:
        try:
            result = runtime.verify_namespace(
                root, protocol, identity, allow_partial=args.allow_partial,
            )
        except Exception as exc:
            print("V2 verification failed: {}".format(exc), file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if not preflight["execution_authorized"]:
        print(
            "V2 execution refused: protocol and architecture execution_authorized are false; "
            "record the required independent review before running.",
            file=sys.stderr,
        )
        return 2
    context = core.load_context()
    decision = preflight["architecture"]
    task_types = args.task_type or list(runtime.TASK_TYPES)
    records = []
    for task_type in task_types:
        for key in _selected_keys(
                protocol, task_type, args.class_index, args.realization_index):
            path = runtime.checkpoint_path(root, task_type, key)
            if path.exists():
                runtime.validate_task_record(path, identity, task_type, key)
                continue
            try:
                record = run_one(context, identity, decision, task_type, key)
            except Exception as exc:
                record = runtime.make_task_record(
                    identity, task_type, key, "failed",
                    error="{}: {}".format(type(exc).__name__, exc),
                )
            _write_records(root, [(task_type, key, record)])
            records.append(record)
            if record["status"] == "failed":
                print("FAILED {} {}".format(task_type, key.as_dict()), file=sys.stderr)
                return 1
    if args.allow_partial:
        print("INCOMPLETE: partial execution is not an accepted calibration result", file=sys.stderr)
        return 3
    try:
        _reduce(root, protocol, identity)
    except Exception as exc:
        print("CALIBRATION GATE EVALUATION FAILED: {}".format(exc), file=sys.stderr)
        return 1
    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--class-index", type=int, action="append")
    parser.add_argument("--realization-index", type=int, action="append")
    parser.add_argument("--task-type", choices=runtime.TASK_TYPES, action="append")
    parser.add_argument("--workers", type=int, default=1,
                        help="Reserved for the deterministic parallel executor.")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
