"""Run the minimal Phase-6R K0 remediation on all frozen Phase-5B branches."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

import faz6_noise_core as noise
import faz6_residual_diagnostics as residuals
import run_faz5_window_grid as phase5
import run_faz6_joint_diagnostics as phase6


ROOT = Path(__file__).resolve().parent.parent
FIT_PATH = ROOT / "outputs" / "faz6r_joint_fits.csv"
RESULT_PATH = ROOT / "outputs" / "faz6r_result.json"
DRAW_PATH = ROOT / "data" / "faz6r_geometry_draws.npz"

EPSILON = 1e-8
OBJECTIVE_SPREAD_MAX = 1e-3
PARAMETER_SPREAD_MAX = 1e-3
GRADIENT_MAX = 5e-2
GRADIENT_STEP_DIFFERENCE_MAX = 5e-2
BOUND_DISTANCE_MIN = 1e-4
VALIDATOR_OBJECTIVE_DIFFERENCE_MAX = 1e-3
VALIDATOR_PARAMETER_DIFFERENCE_MAX = 1e-3


def compact(value):
    return json.dumps(phase6.json_ready(value), separators=(",", ":"), ensure_ascii=True)


def atomic_csv(path, frame):
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n", float_format="%.17g")
    temporary.replace(path)


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(phase6.json_ready(value), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def central_gradient(function, point, step):
    point = np.asarray(point, np.float64)
    gradient = np.empty_like(point)
    for index in range(len(point)):
        delta = np.zeros_like(point)
        delta[index] = step
        gradient[index] = (function(point + delta) - function(point - delta)) / (2.0 * step)
    return gradient


def projected_gradient(point, gradient):
    point = np.asarray(point, np.float64)
    return point - np.clip(point - np.asarray(gradient, np.float64), EPSILON, 1.0 - EPSILON)


def fit_branch(branch, mask, events, phase2, prereg):
    row = {
        "model_index": branch["model_index"],
        "model_id": branch["model_id"],
        "mask_id": branch["mask_id"],
        "cell_id": branch["cell_id"],
        "joint_model_weight": branch["joint_model_weight"],
        "cadence_count": 0,
        "all_starts_finite": False,
        "all_starts_moved": False,
        "all_starts_improved": False,
        "objective_spread": np.nan,
        "unit_parameter_spread": np.nan,
        "maximum_projected_gradient": np.nan,
        "maximum_gradient_step_difference": np.nan,
        "minimum_bound_distance": np.nan,
        "validator_objective_difference": np.nan,
        "validator_unit_parameter_difference": np.nan,
        "scipy_success_count": 0,
        "stationarity_valid": False,
        "selected_start_index": -1,
        "parameter_names_json": "[]",
        "parameters_json": "[]",
        "attempts_json": "[]",
        "error": "",
    }
    try:
        model = phase6.build_joint_model(branch, mask, events, prereg)
        row["cadence_count"] = sum(len(item.time) for item in model.sectors)
        oot = phase6.build_oot_data(branch, mask, events, phase2)
        noise_start = noise.fit_pooled_map(oot, "K0_white", required_sector_count=6)
        if not noise_start.success:
            raise RuntimeError("OOT K0 initializer failed")

        lower = np.asarray([item[0] for item in model.bounds], np.float64)
        upper = np.asarray([item[1] for item in model.bounds], np.float64)
        span = upper - lower
        physical_starts = [
            np.concatenate((geometry, noise_start.parameters))
            for geometry in phase6.geometry_starts(
                branch["geometry_initializer"], model.geometry_bounds
            )
        ]
        offset = float(model.objective(physical_starts[0]))

        def objective(unit):
            unit = np.asarray(unit, np.float64)
            if np.any(unit < EPSILON) or np.any(unit > 1.0 - EPSILON):
                return 1e100
            return float(model.objective(lower + unit * span) - offset)

        attempts = []
        endpoints = []
        final_objectives = []
        gradients = []
        for start_index, physical_start in enumerate(physical_starts):
            unit_start = (physical_start - lower) / span
            initial_objective = float(objective(unit_start))
            result = minimize(
                objective,
                unit_start,
                method="L-BFGS-B",
                jac="3-point",
                bounds=[(EPSILON, 1.0 - EPSILON)] * len(unit_start),
                options={
                    "maxiter": 2000,
                    "maxls": 100,
                    "maxfun": 200000,
                    "ftol": 1e-12,
                    "gtol": 1e-7,
                    "finite_diff_rel_step": 1e-4,
                },
            )
            endpoint = np.asarray(result.x, np.float64)
            final_objective = float(objective(endpoint))
            gradient_1 = central_gradient(objective, endpoint, 1e-4)
            gradient_2 = central_gradient(objective, endpoint, 3e-5)
            projected_1 = projected_gradient(endpoint, gradient_1)
            projected_2 = projected_gradient(endpoint, gradient_2)
            gradient_max = float(max(np.max(np.abs(projected_1)), np.max(np.abs(projected_2))))
            gradient_difference = float(np.max(np.abs(projected_1 - projected_2)))
            movement = float(np.linalg.norm(endpoint - unit_start))
            improvement = float(initial_objective - final_objective)
            endpoints.append(endpoint)
            final_objectives.append(final_objective)
            gradients.append((gradient_max, gradient_difference))
            attempts.append({
                "start_index": start_index,
                "scipy_success": bool(result.success),
                "status": int(result.status),
                "message": str(result.message),
                "iterations": int(result.nit),
                "function_evaluations": int(result.nfev),
                "initial_objective": initial_objective + offset,
                "final_objective": final_objective + offset,
                "unit_movement": movement,
                "objective_improvement": improvement,
                "projected_gradient_max": gradient_max,
                "gradient_step_difference": gradient_difference,
            })

        endpoint_array = np.asarray(endpoints, np.float64)
        objective_array = np.asarray(final_objectives, np.float64)
        finite = bool(np.all(np.isfinite(endpoint_array)) and np.all(np.isfinite(objective_array)) and np.all(objective_array < 1e99))
        moved = all(item["unit_movement"] > 1e-8 for item in attempts)
        improved = all(item["objective_improvement"] > 1e-8 for item in attempts)
        objective_spread = float(np.ptp(objective_array))
        parameter_spread = float(np.max(np.ptp(endpoint_array, axis=0)))
        minimum_distance = float(np.min(np.minimum(endpoint_array, 1.0 - endpoint_array)))
        maximum_gradient = float(max(item[0] for item in gradients))
        gradient_difference = float(max(item[1] for item in gradients))
        selected = int(np.argmin(objective_array))

        validator = minimize(
            objective,
            endpoint_array[selected],
            method="Powell",
            bounds=[(EPSILON, 1.0 - EPSILON)] * endpoint_array.shape[1],
            options={"maxiter": 1000, "maxfev": 50000, "xtol": 1e-8, "ftol": 1e-10},
        )
        validator_endpoint = np.asarray(validator.x, np.float64)
        validator_objective = float(objective(validator_endpoint))
        validator_objective_difference = abs(validator_objective - objective_array[selected])
        validator_parameter_difference = float(np.max(np.abs(validator_endpoint - endpoint_array[selected])))
        stationarity = bool(
            finite and moved and improved
            and objective_spread <= OBJECTIVE_SPREAD_MAX
            and parameter_spread <= PARAMETER_SPREAD_MAX
            and maximum_gradient <= GRADIENT_MAX
            and gradient_difference <= GRADIENT_STEP_DIFFERENCE_MAX
            and minimum_distance >= BOUND_DISTANCE_MIN
            and validator_objective_difference <= VALIDATOR_OBJECTIVE_DIFFERENCE_MAX
            and validator_parameter_difference <= VALIDATOR_PARAMETER_DIFFERENCE_MAX
        )
        parameters = lower + endpoint_array[selected] * span
        row.update({
            "all_starts_finite": finite,
            "all_starts_moved": moved,
            "all_starts_improved": improved,
            "objective_spread": objective_spread,
            "unit_parameter_spread": parameter_spread,
            "maximum_projected_gradient": maximum_gradient,
            "maximum_gradient_step_difference": gradient_difference,
            "minimum_bound_distance": minimum_distance,
            "validator_objective_difference": validator_objective_difference,
            "validator_unit_parameter_difference": validator_parameter_difference,
            "scipy_success_count": sum(item["scipy_success"] for item in attempts),
            "stationarity_valid": stationarity,
            "selected_start_index": selected,
            "parameter_names_json": compact(model.parameter_names),
            "parameters_json": compact(parameters),
            "attempts_json": compact(attempts),
        })
    except Exception as exc:
        row["error"] = "{}: {}".format(type(exc).__name__, str(exc).replace("\n", " "))
    return row


def geometry_and_residuals(branches, fits, masks, events, prereg):
    draw_stack = []
    beta_rows = []
    geometry_checks = []
    indexed = {row.model_id: row for row in fits.itertuples(index=False)}
    for branch in branches:
        row = indexed[branch["model_id"]]
        parameters = np.asarray(json.loads(row.parameters_json), np.float64)
        model = phase6.build_joint_model(branch, masks[branch["mask_id"]], events, prereg)
        fixed_noise = parameters[3:].copy()

        def geometry_objective(geometry):
            return model.objective(np.concatenate((geometry, fixed_noise)))

        try:
            _, covariance, attempts = phase5.finite_difference_hessian(
                geometry_objective, parameters[:3]
            )
            draws, _ = phase5.draw_laplace(
                parameters[:3], covariance, model.geometry_bounds, 4096,
                649260 + branch["model_index"], model.period_days,
            )
            beta = residuals.binned_rms_beta(model.residual_frame(parameters))
            aggregate = beta["aggregate"].copy()
            aggregate.insert(0, "model_id", branch["model_id"])
            aggregate.insert(1, "joint_model_weight", branch["joint_model_weight"])
            beta_rows.append(aggregate)
            draw_stack.append(draws)
            geometry_checks.append({
                "model_id": branch["model_id"], "valid": True,
                "hessian_attempts": attempts,
            })
        except Exception as exc:
            geometry_checks.append({
                "model_id": branch["model_id"], "valid": False,
                "error": "{}: {}".format(type(exc).__name__, exc),
            })
    if not all(item["valid"] for item in geometry_checks):
        return geometry_checks, None, None, None
    draws = np.stack(draw_stack)
    beta_frame = pd.concat(beta_rows, ignore_index=True)
    mixture_rows = []
    for scale in residuals.BETA_TIMESCALES_MINUTES:
        selected = beta_frame.loc[beta_frame["timescale_minutes"] == float(scale)]
        eligible = bool(len(selected) == 24 and selected["all_sectors_eligible"].astype(bool).all() and np.isfinite(selected["equal_sector_beta"]).all())
        weighted = None
        if eligible:
            weighted = float(np.sum(selected["joint_model_weight"] * selected["equal_sector_beta"]))
        mixture_rows.append({
            "timescale_minutes": float(scale),
            "all_branches_eligible": eligible,
            "weighted_equal_sector_beta": weighted,
        })
    complete = all(item["all_branches_eligible"] for item in mixture_rows)
    maximum = max(item["weighted_equal_sector_beta"] for item in mixture_rows) if complete else None
    np.savez_compressed(
        DRAW_PATH,
        model_ids=np.asarray([item["model_id"] for item in branches], dtype="U40"),
        weights=np.asarray([item["joint_model_weight"] for item in branches], np.float64),
        parameter_names=np.asarray(phase6.DRAW_NAMES, dtype="U32"),
        draws=draws,
    )
    return geometry_checks, mixture_rows, complete, maximum


def run(workers):
    if RESULT_PATH.exists():
        raise FileExistsError("Faz 6R result already exists")
    protocol = phase6.load_json(phase6.PROTOCOL_PATH)
    parent = phase6.load_json(phase6.PARENT_PATH)
    checks, _, phase5b_report = phase6.verify_inputs(protocol, parent)
    branches, branch_checks = phase6.load_branches(protocol, phase5b_report)
    masks, events, phase2, prereg = phase6.load_masks_and_model(protocol, parent)

    if FIT_PATH.exists():
        fits = pd.read_csv(FIT_PATH, keep_default_na=False)
    else:
        fits = pd.DataFrame()
    completed = set(fits["model_id"]) if len(fits) else set()
    pending = [item for item in branches if item["model_id"] not in completed]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(
            fit_branch, branch, masks[branch["mask_id"]], events, phase2, prereg
        ) for branch in pending]
        for branch, future in zip(pending, futures):
            row = future.result()
            fits = pd.concat([fits, pd.DataFrame([row])], ignore_index=True)
            fits.sort_values("model_index", inplace=True)
            atomic_csv(FIT_PATH, fits)
            print("{} stationarity={}".format(branch["model_id"], row["stationarity_valid"]))

    all_stationary = bool(len(fits) == 24 and fits["stationarity_valid"].astype(bool).all())
    geometry_checks = []
    beta_rows = None
    beta_complete = False
    maximum_beta = None
    if all_stationary:
        geometry_checks, beta_rows, beta_complete, maximum_beta = geometry_and_residuals(
            branches, fits, masks, events, prereg
        )
    geometry_pass = bool(all_stationary and geometry_checks and all(item["valid"] for item in geometry_checks))
    beta_pass = bool(geometry_pass and beta_complete and maximum_beta is not None and maximum_beta <= residuals.BETA_MAX)
    if not all_stationary:
        status = "FAIL_STATIONARITY"
    elif not geometry_pass:
        status = "FAIL_GEOMETRY_HESSIAN"
    elif not beta_complete:
        status = "FAIL_BETA_SUPPORT"
    elif not beta_pass:
        status = "FAIL_RESIDUAL_CORRELATION"
    else:
        status = "PASS_K0_WHITE"
    result = {
        "phase": "6R",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "workers": workers,
        "model": "unchanged Phase-6 V2 K0 white+jitter joint model",
        "branch_count": len(fits),
        "stationary_branch_count": int(fits["stationarity_valid"].astype(bool).sum()),
        "failed_stationarity_branches": fits.loc[~fits["stationarity_valid"].astype(bool), "model_id"].tolist(),
        "scipy_success_is_not_a_gate": True,
        "thresholds": {
            "objective_spread_max": OBJECTIVE_SPREAD_MAX,
            "unit_parameter_spread_max": PARAMETER_SPREAD_MAX,
            "projected_gradient_max": GRADIENT_MAX,
            "gradient_step_difference_max": GRADIENT_STEP_DIFFERENCE_MAX,
            "minimum_bound_distance": BOUND_DISTANCE_MIN,
            "powell_objective_difference_max": VALIDATOR_OBJECTIVE_DIFFERENCE_MAX,
            "powell_unit_parameter_difference_max": VALIDATOR_PARAMETER_DIFFERENCE_MAX,
            "beta_max": residuals.BETA_MAX,
        },
        "upstream_checks_pass": bool(all(checks.values()) and all(branch_checks.values())),
        "geometry_checks": geometry_checks,
        "beta_mixture": beta_rows,
        "maximum_weighted_beta": maximum_beta,
        "phase7_may_begin": status == "PASS_K0_WHITE",
    }
    atomic_json(RESULT_PATH, result)
    print("Faz 6R complete: {}".format(status))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")
    run(args.workers)


if __name__ == "__main__":
    main()
