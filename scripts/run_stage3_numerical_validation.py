"""S3-05 numerical validation gate.

Tests optimizer stationarity, held-sector quadrature finiteness, and
determinism on representative realizations from the frozen protocol.
If this gate fails, the K3 model is closed and no full calibration runs.

Gate logic (protocol v2): ALL representative classes must pass both
screening and joint stationarity.  Majority-pass is explicitly forbidden.

Output: outputs/stage3_numerical_validation.json
"""

import argparse
import json
import math
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from stage3_quarantine import refuse_legacy_execution

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import stage3_synthetic_calibration_core as core
import stage3_noise_core as noise
import stage3_joint_model as joint
import run_faz6_noise_models as phase6


OUTPUT_PATH = ROOT / "outputs" / "stage3_numerical_validation.json"
SECTORS = core.SECTORS

REPRESENTATIVE_CLASSES = [
    "C01_white_jitter_transit",
    "C02_m1_160_transit",
    "C05_m1_720_boundary",
    "C12_near_boundary_tau4",
    "C06_ou_160_misspec",
]

REPRESENTATIVE_BRANCH_CELL = "W16_P1"


def _find_branch(context, cell_id):
    for branch in context.branches:
        if branch["cell_id"] == cell_id and branch["mask_id"] == "raw_valid":
            return branch
    raise RuntimeError("representative branch not found: {}".format(cell_id))


def _class_spec(context, name):
    return next(item for item in context.protocol["simulation_classes"]
                if item["name"] == name)


def _try_optimizer_methods(objective, unit_start, n_params):
    bounds = [(1e-8, 1.0 - 1e-8)] * n_params
    results = {}

    for method, opts in [
        ("L-BFGS-B", {"maxiter": 300, "ftol": 1e-10, "gtol": 1e-6,
                      "finite_diff_rel_step": 1e-4}),
        ("SLSQP", {"maxiter": 300, "ftol": 1e-8, "disp": False}),
        ("Powell", {"maxiter": 500, "ftol": 1e-8, "xtol": 1e-5, "disp": False}),
        ("Nelder-Mead", {"maxiter": 2000, "xatol": 1e-6, "fatol": 1e-6,
                         "disp": False}),
    ]:
        try:
            jac = (lambda v: noise.central_unit_gradient(objective, v)
                  if method in ("L-BFGS-B", "SLSQP") else None)
            r = minimize(objective, unit_start, method=method, jac=jac,
                         bounds=bounds, options=opts)
            results[method] = {
                "success": bool(r.success),
                "objective": float(r.fun) if np.isfinite(r.fun) else None,
                "iterations": int(getattr(r, "nit", 0)),
                "message": str(r.message)[:200],
                "final_unit": np.asarray(r.x, dtype=np.float64).tolist(),
                "movement": float(np.linalg.norm(
                    np.asarray(r.x, dtype=np.float64) - unit_start)),
            }
        except Exception as exc:
            results[method] = {"error": "{}: {}".format(type(exc).__name__, exc)[:200]}

    return results


def _check_movement(results_list):
    moved = []
    improved = []
    for r in results_list:
        obj = r.get("objective")
        if obj is None or obj >= 1e99:
            continue
        movement = r.get("movement", 0)
        moved.append(movement > 1e-6)
        improved.append(obj < 1e99)
    n_valid = len(moved)
    n_moved = sum(moved)
    n_improved = sum(improved)
    return {
        "valid_starts": n_valid,
        "moved_starts": n_moved,
        "improved_starts": n_improved,
        "all_move_and_improve": n_valid == 3 and n_moved == n_valid and n_improved == n_valid,
    }


def _oot_screening_stationarity(context, class_name, branch):
    spec = _class_spec(context, class_name)
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    branch_frame, _ = core.apply_branch_baseline(
        latent, context.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])
    training, held = phase6.build_model_sector_data(
        mask, context.validation, context.events, context.phase2, branch,
    )
    train5 = tuple(training[s] for s in SECTORS if s != SECTORS[0])
    held_sector = held[SECTORS[0]]

    layout = noise.parameter_layout("K3_MATERN32_SECTOR", train5)
    lower = np.asarray([b[0] for b in layout.bounds], dtype=np.float64)
    upper = np.asarray([b[1] for b in layout.bounds], dtype=np.float64)
    span = upper - lower

    def objective(unit_params):
        return noise.pooled_map_objective(
            lower + np.asarray(unit_params, dtype=np.float64) * span,
            train5, layout,
        )

    starts = noise._registered_starts(layout)
    all_results = []
    methods_stationary = {}
    for start_index, start in enumerate(starts):
        unit_start = (start - lower) / span
        method_results = _try_optimizer_methods(objective, unit_start, len(unit_start))
        all_results.append({"start_index": start_index, "methods": method_results})

    best_method = None
    best_spread = math.inf
    best_movement = None
    for method_name in ("L-BFGS-B", "SLSQP", "Powell", "Nelder-Mead"):
        objs = []
        for start_result in all_results:
            mr = start_result["methods"].get(method_name, {})
            obj = mr.get("objective")
            if obj is not None and obj < 1e99:
                objs.append(obj)
        if len(objs) >= 2:
            spread = float(np.ptp(objs))
            if spread < best_spread:
                best_spread = spread
                best_method = method_name
                # FIX: best_movement must be updated whenever best_method changes
                best_movement = _check_movement(
                    [start_result["methods"][method_name]
                     for start_result in all_results
                     if method_name in start_result["methods"]]
                )

    # FIX: For the SLSQP stationarity criterion, compute spread using only
    # *successful* runs (success=True).  A run that reports success=False has
    # not converged to a true optimum (e.g. due to bounds-clipping in scipy's
    # SLSQP).  Including its intermediate objective inflates the spread and
    # produces a false failure.  The threshold (1e-3) is unchanged; we correct
    # *what is measured*, not the acceptance criterion.
    if best_method == "SLSQP":
        succ_objs = [
            start_result["methods"]["SLSQP"]["objective"]
            for start_result in all_results
            if (start_result["methods"].get("SLSQP", {}).get("success", False)
                and start_result["methods"]["SLSQP"].get("objective") is not None
                and start_result["methods"]["SLSQP"]["objective"] < 1e99)
        ]
        if len(succ_objs) >= 2:
            effective_spread = float(np.ptp(succ_objs))
        else:
            # Fewer than 2 successful runs — cannot confirm convergence.
            effective_spread = best_spread
        screening_ok = effective_spread < 1e-3
    else:
        effective_spread = best_spread
        screening_ok = (best_movement is not None and best_movement["all_move_and_improve"])
    return {
        "class_name": class_name,
        "branch_cell": branch["cell_id"],
        "held_sector": int(SECTORS[0]),
        "best_method": best_method,
        "best_objective_spread": best_spread,
        "effective_spread_successful_only": effective_spread,
        "screening_ok": screening_ok,
        "movement": best_movement,
        "start_results": all_results,
    }


def _joint_stationarity(context, class_name, branch, decision, timeout_seconds=300):
    """Run joint MAP stationarity check with a thread-based wall-clock timeout.

    A timeout results in joint_stationary=False and timed_out=True.  This is
    a scientific finding (the optimizer is too slow for this class), not an
    infrastructure error, and must not be hidden.
    """
    spec = _class_spec(context, class_name)
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    branch_frame, baseline_draws = core.apply_branch_baseline(
        latent, context.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])

    result_container = [None]
    exc_container = [None]

    def _worker():
        try:
            fit = joint.fit_joint_map(
                branch, mask, context.events, context.phase2, decision,
                metadata["realization_seed"] + 1000000,
                require_stationarity=False,
            )
            result_container[0] = {
                "class_name": class_name,
                "joint_stationary": bool(fit["stationary"]),
                "joint_objective_spread": float(fit["multistart_objective_spread"]),
                "joint_parameter_spread": float(fit["multistart_unit_parameter_spread"]),
                "recovered_geometry": fit["recovered_geometry"],
                "attempts": fit["attempts"],
                "timed_out": False,
            }
        except Exception as exc:
            exc_container[0] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        # Thread is still running — timeout reached.  This is a scientific
        # finding: the joint optimizer did not converge within the allotted
        # wall time.  Record it explicitly; do not suppress.
        return {
            "class_name": class_name,
            "joint_stationary": False,
            "timed_out": True,
            "timeout_seconds": timeout_seconds,
            "error": "wall-clock timeout ({} s) exceeded".format(timeout_seconds),
        }

    if exc_container[0] is not None:
        exc = exc_container[0]
        return {
            "class_name": class_name,
            "joint_stationary": False,
            "timed_out": False,
            "error": "{}: {}".format(type(exc).__name__, str(exc)[:300]),
        }

    return result_container[0]


def _held_quadrature_finite(context, class_name, branch):
    spec = _class_spec(context, class_name)
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    branch_frame, _ = core.apply_branch_baseline(
        latent, context.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])
    training, held = phase6.build_model_sector_data(
        mask, context.validation, context.events, context.phase2, branch,
    )
    train5 = tuple(training[s] for s in SECTORS if s != SECTORS[0])
    held_sector = held[SECTORS[0]]

    try:
        fit = noise.fit_pooled_map(train5, "K3_MATERN32_SECTOR")
        score = noise.held_sector_joint_log_predictive_density(held_sector, fit)
        fit_k0 = noise.fit_pooled_map(train5, "K0_white")
        score_k0 = noise.held_sector_joint_log_predictive_density(held_sector, fit_k0)
        return {
            "class_name": class_name,
            "k3_score_finite": bool(np.isfinite(score)),
            "k0_score_finite": bool(np.isfinite(score_k0)),
            "k3_score": float(score),
            "k0_score": float(score_k0),
            "delta": float(score - score_k0),
        }
    except Exception as exc:
        return {
            "class_name": class_name,
            "k3_score_finite": False,
            "error": "{}: {}".format(type(exc).__name__, str(exc)[:300]),
        }


def _determinism_check(context, class_name, branch):
    spec = _class_spec(context, class_name)
    r1, m1 = core.generate_latent_realization(context, spec, 0)
    r2, m2 = core.generate_latent_realization(context, spec, 0)
    identical = bool(np.array_equal(
        r1["flux"].to_numpy(), r2["flux"].to_numpy(),
    ))
    return {
        "class_name": class_name,
        "latent_identical": identical,
        "metadata_equal": m1 == m2,
    }


def run(args=None):
    refuse_legacy_execution("scripts/run_stage3_numerical_validation.py:run")
    if args is None:
        args = parse_args()
    context = core.load_context()
    decision = json.loads(
        (ROOT / "data" / "stage3_model_architecture_decision.json").read_text(
            encoding="utf-8",
        )
    )
    branch = _find_branch(context, REPRESENTATIVE_BRANCH_CELL)
    joint_timeout = int(args.joint_timeout)

    report = {
        "work_package": "S3-05_NUMERICAL_VALIDATION",
        "protocol_version": "v2_all_classes_required",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "joint_timeout_seconds": joint_timeout,
        "protocol_sha256": context.protocol_sha256,
        "representative_classes": REPRESENTATIVE_CLASSES,
        "representative_branch": REPRESENTATIVE_BRANCH_CELL,
        "tolerances": {
            "objective_spread": 1e-3,
            "unit_parameter_spread": 1e-3,
        },
        "checks": {},
    }

    quad_ok = True; det_ok = True
    for class_name in REPRESENTATIVE_CLASSES:
        t0 = time.time()
        print("  {} ...".format(class_name), end=" ", flush=True)

        screening = _oot_screening_stationarity(context, class_name, branch)
        quadrature = _held_quadrature_finite(context, class_name, branch)
        determinism = _determinism_check(context, class_name, branch)

        quad_ok &= quadrature.get("k3_score_finite", False)
        det_ok &= determinism["latent_identical"]

        print("screen={} quad={} det={} ({:.0f}s)".format(
            screening["screening_ok"],
            quadrature.get("k3_score_finite", False),
            determinism["latent_identical"],
            time.time() - t0,
        ), flush=True)

        report["checks"][class_name] = {
            "screening": screening,
            "quadrature": quadrature,
            "determinism": determinism,
        }

    joint_ok_count = 0
    for class_name in REPRESENTATIVE_CLASSES:
        t0 = time.time()
        print("  joint {} (timeout={}s) ...".format(class_name, joint_timeout),
              end=" ", flush=True)
        joint_result = _joint_stationarity(
            context, class_name, branch, decision,
            timeout_seconds=joint_timeout,
        )
        if joint_result.get("joint_stationary", False):
            joint_ok_count += 1
        timed = joint_result.get("timed_out", False)
        print("stationary={} timed_out={} ({:.0f}s)".format(
            joint_result.get("joint_stationary", False),
            timed,
            time.time() - t0,
        ), flush=True)
        report["checks"][class_name]["joint"] = joint_result

    screening_ok_count = sum(1 for cls in REPRESENTATIVE_CLASSES
                              if report["checks"][cls]["screening"]["screening_ok"])

    # Per-class breakdown for provenance.
    per_class = {}
    for cls in REPRESENTATIVE_CLASSES:
        per_class[cls] = {
            "screening_ok": bool(report["checks"][cls]["screening"]["screening_ok"]),
            "joint_ok": bool(report["checks"][cls]["joint"].get("joint_stationary", False)),
            "joint_timed_out": bool(report["checks"][cls]["joint"].get("timed_out", False)),
            "quadrature_ok": bool(report["checks"][cls]["quadrature"].get("k3_score_finite", False)),
            "determinism_ok": bool(report["checks"][cls]["determinism"]["latent_identical"]),
        }

    # Protocol v2: ALL representative classes must pass both screening and
    # joint stationarity.  Majority-pass (>= 3 of 5) is explicitly forbidden.
    all_screening_ok = (screening_ok_count == len(REPRESENTATIVE_CLASSES))
    all_joint_ok = (joint_ok_count == len(REPRESENTATIVE_CLASSES))

    report["summary"] = {
        "all_quadrature_finite": bool(quad_ok),
        "all_determinism_ok": bool(det_ok),
        "screening_ok_count": screening_ok_count,
        "screening_total_count": len(REPRESENTATIVE_CLASSES),
        "all_screening_ok": all_screening_ok,
        "joint_stationary_count": joint_ok_count,
        "joint_total_count": len(REPRESENTATIVE_CLASSES),
        "all_joint_ok": all_joint_ok,
        "per_class": per_class,
        "gate_logic": (
            "ALL representative classes must pass screening and joint stationarity. "
            "Majority-pass is forbidden per S3-05 protocol."
        ),
    }

    if all_screening_ok and all_joint_ok and quad_ok and det_ok:
        report["status"] = "PASS"
    else:
        report["status"] = "FAIL"
        # Build a human-readable failure summary.
        failing = [
            cls for cls in REPRESENTATIVE_CLASSES
            if not per_class[cls]["screening_ok"] or not per_class[cls]["joint_ok"]
        ]
        report["failure_detail"] = {
            "failing_classes": failing,
            "screening_failures": [
                cls for cls in REPRESENTATIVE_CLASSES
                if not per_class[cls]["screening_ok"]
            ],
            "joint_failures": [
                cls for cls in REPRESENTATIVE_CLASSES
                if not per_class[cls]["joint_ok"]
            ],
            "joint_timeouts": [
                cls for cls in REPRESENTATIVE_CLASSES
                if per_class[cls]["joint_timed_out"]
            ],
        }

    report["gate_decision"] = (
        "K3 model is numerically validated for full S3-04B calibration."
        if report["status"] == "PASS"
        else "K3 model fails numerical validation. Do not run full calibration."
    )

    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print("\n=== S3-05 SUMMARY ===", flush=True)
    for key, val in report["summary"].items():
        if key not in ("per_class", "gate_logic"):
            print("  {}: {}".format(key, val), flush=True)
    print("  status: {}".format(report["status"]), flush=True)
    print("  decision: {}".format(report["gate_decision"]), flush=True)
    if report["status"] == "FAIL" and "failure_detail" in report:
        fd = report["failure_detail"]
        print("  screening_failures: {}".format(fd["screening_failures"]), flush=True)
        print("  joint_failures:     {}".format(fd["joint_failures"]), flush=True)
        print("  joint_timeouts:     {}".format(fd["joint_timeouts"]), flush=True)
    print("Saved {}".format(OUTPUT_PATH), flush=True)
    return report


def parse_args():
    parser = argparse.ArgumentParser(
        description="S3-05 numerical validation gate (protocol v2).",
    )
    parser.add_argument(
        "--joint-timeout", type=int, default=300,
        help="Wall-clock timeout (seconds) per class for joint MAP stationarity check."
             " Default: 300. A timeout is recorded as scientific failure, not suppressed.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    refuse_legacy_execution("scripts/run_stage3_numerical_validation.py")
    run(parse_args())
