"""S3-05 numerical validation gate.

Tests optimizer stationarity, held-sector quadrature finiteness, and
determinism on representative realizations from the frozen protocol.
If this gate fails, the K3 model is closed and no full calibration runs.

Output: outputs/stage3_numerical_validation.json
"""

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

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
                movement = _check_movement(
                    [start_result["methods"][method_name]
                     for start_result in all_results
                     if method_name in start_result["methods"]]
                )

    screening_ok = (best_spread < 1e-3 if best_method == "SLSQP"
                    else (best_movement is not None and best_movement["all_move_and_improve"]))
    return {
        "class_name": class_name,
        "branch_cell": branch["cell_id"],
        "held_sector": int(SECTORS[0]),
        "best_method": best_method,
        "best_objective_spread": best_spread,
        "screening_ok": screening_ok,
        "movement": best_movement,
        "start_results": all_results,
    }


def _joint_stationarity(context, class_name, branch, decision):
    spec = _class_spec(context, class_name)
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    branch_frame, baseline_draws = core.apply_branch_baseline(
        latent, context.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])

    try:
        fit = joint.fit_joint_map(
            branch, mask, context.events, context.phase2, decision,
            metadata["realization_seed"] + 1000000,
            require_stationarity=False,
        )
        return {
            "class_name": class_name,
            "joint_stationary": bool(fit["stationary"]),
            "joint_objective_spread": float(fit["multistart_objective_spread"]),
            "joint_parameter_spread": float(fit["multistart_unit_parameter_spread"]),
            "recovered_geometry": fit["recovered_geometry"],
            "attempts": fit["attempts"],
        }
    except Exception as exc:
        return {
            "class_name": class_name,
            "joint_stationary": False,
            "error": "{}: {}".format(type(exc).__name__, str(exc)[:300]),
        }


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


def run():
    context = core.load_context()
    decision = json.loads(
        (ROOT / "data" / "stage3_model_architecture_decision.json").read_text(
            encoding="utf-8",
        )
    )
    branch = _find_branch(context, REPRESENTATIVE_BRANCH_CELL)

    report = {
        "work_package": "S3-05_NUMERICAL_VALIDATION",
        "generated_utc": "2026-07-24T12:00:00+00:00",
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
        print("  joint {} ...".format(class_name), end=" ", flush=True)
        joint_result = _joint_stationarity(context, class_name, branch, decision)
        if joint_result.get("joint_stationary", False):
            joint_ok_count += 1
        print("stationary={} ({:.0f}s)".format(
            joint_result.get("joint_stationary", False),
            time.time() - t0,
        ), flush=True)
        report["checks"][class_name]["joint"] = joint_result

    screening_ok_count = sum(1 for cls in REPRESENTATIVE_CLASSES
                              if report["checks"][cls]["screening"]["screening_ok"])
    report["summary"] = {
        "all_quadrature_finite": bool(quad_ok),
        "all_determinism_ok": bool(det_ok),
        "screening_ok_count": screening_ok_count,
        "screening_total_count": len(REPRESENTATIVE_CLASSES),
        "joint_stationary_count": joint_ok_count,
        "joint_total_count": len(REPRESENTATIVE_CLASSES),
    }

    if (screening_ok_count >= 3 and joint_ok_count >= 3
            and quad_ok and det_ok):
        report["status"] = "PASS"
    else:
        report["status"] = "FAIL"

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
        print("  {}: {}".format(key, val), flush=True)
    print("  status: {}".format(report["status"]), flush=True)
    print("  decision: {}".format(report["gate_decision"]), flush=True)
    print("Saved {}".format(OUTPUT_PATH), flush=True)
    return report


if __name__ == "__main__":
    run()