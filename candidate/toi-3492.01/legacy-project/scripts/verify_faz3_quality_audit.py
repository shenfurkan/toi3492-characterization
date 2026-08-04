"""Faz 3: real quality, telemetry, CBV, and control-star audit.

This script consumes the Faz 1 cadence ledger and Faz 2 event inventory.  It
does not rebuild either phase.  The only external inputs are the six official
CBV FITS and six TIC 81400324 control-star LC FITS frozen by
``prepare_faz3_inputs.py``.
"""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import batman
import numpy as np
import pandas as pd
from astropy.io import fits
from scipy.optimize import least_squares
from scipy.stats import norm


ROOT = Path(__file__).resolve().parent.parent
FAZ1_PATH = ROOT / "outputs" / "faz1_product_inventory.json"
FAZ2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
INPUT_PATH = ROOT / "outputs" / "faz3_input_inventory.json"
LEDGER_PATH = ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz"
OUTPUT_PATH = ROOT / "outputs" / "faz3_quality_audit.json"
CBV_CSV_PATH = ROOT / "outputs" / "faz3_cbv_validation.csv"
CONTROL_CSV_PATH = ROOT / "outputs" / "faz3_control_event_depths.csv"
EVENT_CSV_PATH = ROOT / "outputs" / "faz3_event_telemetry.csv"
TARGET_DEPTH_PATH = ROOT / "outputs" / "toi3492_120s_event_depths.csv"

SECTORS = (37, 63, 64, 90, 99, 100)
PERIOD_DAYS = 9.2224171
T0_BTJD = 2314.5211550001986
T14_HOURS = 5.296858
HALF_WINDOW_HOURS = 13.0
EXPOSURE_SECONDS = 120.0
SUPERSAMPLE_FACTOR = 7
LD_U1 = 0.3546454910932521
LD_U2 = 0.15379449038160178
MAX_GEOMETRY_SHIFT_SIGMA = 0.5
MAX_POST_TELEMETRY_R = 0.10
CONTROL_SIGNAL_SIGMA = 3.0
CONTROL_BOOTSTRAPS = 256
CONTROL_BLOCK_CADENCES = 30

MASKS = {
    "strict_zero": {
        "numeric_bitmask": 0,
        "rule": "QUALITY == 0",
    },
    "lightkurve_default": {
        "numeric_bitmask": 17087,
        "rule": "(QUALITY & 17087) == 0",
    },
    "explicit_hard": {
        "numeric_bitmask": 24319,
        "rule": "(QUALITY & 24319) == 0",
    },
}

TELEMETRY = {
    "SAP_BKG": "sap_bkg",
    "POS_CORR1": "pos_corr1",
    "POS_CORR2": "pos_corr2",
    "MOM_CENTR1": "mom_centr1",
    "MOM_CENTR2": "mom_centr2",
}
PSF_COLUMNS = ("PSF_CENTR1", "PSF_CENTR2")
QUALITY_BIT_LABELS = {
    1: "attitude_tweak",
    2: "safe_mode",
    4: "coarse_point",
    8: "earth_point",
    16: "argabrightening",
    32: "desaturation_event",
    64: "cosmic_ray_optimal_aperture",
    128: "manual_exclude",
    256: "discontinuity_corrected",
    512: "impulsive_outlier",
    1024: "cosmic_ray_collateral",
    2048: "straylight",
    4096: "straylight2",
    8192: "planet_search_exclude",
    16384: "bad_calibration_exclude",
    32768: "insufficient_targets_for_error_correction",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def phase_days(time):
    return ((np.asarray(time, dtype=float) - T0_BTJD + 0.5 * PERIOD_DAYS) % PERIOD_DAYS) - (
        0.5 * PERIOD_DAYS
    )


def mask_pass(quality, mask_name):
    quality = np.asarray(quality, dtype=np.int64)
    if mask_name == "strict_zero":
        return quality == 0
    return (quality & MASKS[mask_name]["numeric_bitmask"]) == 0


def finite_float(value):
    value = float(value)
    return value if np.isfinite(value) else None


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return finite_float(value)
    if isinstance(value, float):
        return finite_float(value)
    return value


def pearson_r(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    good = np.isfinite(x) & np.isfinite(y)
    if good.sum() < 3:
        return None
    x = x[good] - np.mean(x[good])
    y = y[good] - np.mean(y[good])
    denominator = np.sqrt(np.dot(x, x) * np.dot(y, y))
    if denominator <= 0:
        return None
    return float(np.dot(x, y) / denominator)


def robust_scale(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return None
    median = np.median(values)
    scale = 1.4826 * np.median(np.abs(values - median))
    if not np.isfinite(scale) or scale <= 0:
        scale = np.std(values, ddof=1)
    return float(scale) if np.isfinite(scale) and scale > 0 else None


def range_summary(values):
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {
            "row_count": int(len(values)),
            "finite_count": 0,
            "minimum": None,
            "maximum": None,
            "median": None,
        }
    return {
        "row_count": int(len(values)),
        "finite_count": int(len(finite)),
        "minimum": float(np.min(finite)),
        "maximum": float(np.max(finite)),
        "median": float(np.median(finite)),
    }


def set_bit_counts(quality, selected=None):
    quality = np.asarray(quality, dtype=np.int64)
    if selected is not None:
        quality = quality[np.asarray(selected, dtype=bool)]
    records = []
    for bit_index in range(32):
        bit_value = 1 << bit_index
        count = int(np.count_nonzero(quality & bit_value))
        if count:
            records.append(
                {
                    "bit_index": bit_index,
                    "bit_value": bit_value,
                    "label": QUALITY_BIT_LABELS.get(bit_value, "unlabelled"),
                    "cadence_count": count,
                }
            )
    return records


def quality_audit(ledger):
    phase = phase_days(ledger["time_btjd"].to_numpy(float))
    finite_science = (
        np.isfinite(ledger["time_btjd"])
        & np.isfinite(ledger["pdcsap_flux"])
        & np.isfinite(ledger["pdcsap_flux_err"])
        & (ledger["pdcsap_flux_err"] > 0)
    ).to_numpy(bool)
    in_window = np.abs(phase) <= HALF_WINDOW_HOURS / 24.0
    output = {
        "definitions": MASKS,
        "accepted_count_definition": (
            "quality predicate evaluated on every raw 120-s ledger row; model counts "
            "add finite TIME/PDCSAP_FLUX/positive PDCSAP_FLUX_ERR and +/-13 h"
        ),
        "per_sector": {},
    }
    for sector in SECTORS:
        sector_rows = ledger["sector"].to_numpy(int) == sector
        quality = ledger.loc[sector_rows, "quality"].to_numpy(np.int64)
        sector_result = {
            "raw_row_count": int(sector_rows.sum()),
            "quality_zero_count": int(np.count_nonzero(quality == 0)),
            "quality_nonzero_count": int(np.count_nonzero(quality != 0)),
            "quality_or": int(np.bitwise_or.reduce(quality)) if len(quality) else 0,
            "all_set_bits": set_bit_counts(quality),
            "masks": {},
        }
        for name, definition in MASKS.items():
            accepted = mask_pass(quality, name)
            global_accepted = np.zeros(len(ledger), dtype=bool)
            global_accepted[sector_rows] = accepted
            rejected = ~accepted
            rejected_bits = set_bit_counts(quality, rejected)
            if name != "strict_zero":
                bitmask = definition["numeric_bitmask"]
                rejected_bits = [
                    item for item in rejected_bits if item["bit_value"] & bitmask
                ]
            sector_result["masks"][name] = {
                "numeric_bitmask": definition["numeric_bitmask"],
                "rule": definition["rule"],
                "accepted_count": int(accepted.sum()),
                "rejected_count": int(rejected.sum()),
                "finite_science_accepted_count": int(
                    np.count_nonzero(global_accepted & finite_science)
                ),
                "model_window_accepted_count": int(
                    np.count_nonzero(global_accepted & finite_science & in_window)
                ),
                "bits_causing_rejection": rejected_bits,
            }
        output["per_sector"][str(sector)] = sector_result
    return output


def duration_hours(theta):
    rp, a_rs, impact = [float(item) for item in theta]
    if impact >= 1.0 + rp or impact >= a_rs:
        return float("nan")
    sin_i = math.sqrt(max(0.0, 1.0 - (impact / a_rs) ** 2))
    numerator = math.sqrt(max(0.0, (1.0 + rp) ** 2 - impact**2))
    argument = numerator / (a_rs * sin_i)
    if not 0.0 <= argument <= 1.0:
        return float("nan")
    return PERIOD_DAYS * 24.0 / math.pi * math.asin(argument)


def geometry_context(ledger):
    context = ledger.copy()
    context["_phase"] = phase_days(context["time_btjd"].to_numpy(float))
    base = (
        np.isfinite(context["time_btjd"])
        & np.isfinite(context["pdcsap_flux"])
        & np.isfinite(context["pdcsap_flux_err"])
        & (context["pdcsap_flux"] > 0)
        & (context["pdcsap_flux_err"] > 0)
        & (np.abs(context["_phase"]) <= HALF_WINDOW_HOURS / 24.0)
    )
    for column in TELEMETRY.values():
        base &= np.isfinite(context[column])
    context["_geometry_base"] = base
    standards = {}
    for sector in SECTORS:
        rows = base & (context["sector"] == sector)
        if rows.sum() < 100:
            raise RuntimeError(f"Too few finite geometry cadences in sector {sector}")
        oot = rows & (np.abs(context["_phase"] * 24.0) > 0.5 * T14_HOURS)
        norm_value = float(np.median(context.loc[oot, "pdcsap_flux"]))
        context.loc[context["sector"] == sector, "_flux"] = (
            context.loc[context["sector"] == sector, "pdcsap_flux"] / norm_value
        )
        context.loc[context["sector"] == sector, "_flux_err"] = (
            context.loc[context["sector"] == sector, "pdcsap_flux_err"] / norm_value
        )
        time_values = context.loc[rows, "time_btjd"].to_numpy(float)
        time_mean = float(np.mean(time_values))
        time_std = float(np.std(time_values))
        context.loc[context["sector"] == sector, "_time_z"] = (
            context.loc[context["sector"] == sector, "time_btjd"] - time_mean
        ) / time_std
        telemetry_standards = {}
        for public_name, column in TELEMETRY.items():
            values = context.loc[rows, column].to_numpy(float)
            mean = float(np.mean(values))
            std = float(np.std(values))
            if not np.isfinite(std) or std <= 0:
                raise RuntimeError(f"{public_name} has zero scale in sector {sector}")
            context.loc[context["sector"] == sector, f"_{column}_z"] = (
                context.loc[context["sector"] == sector, column] - mean
            ) / std
            telemetry_standards[public_name] = {"mean": mean, "standard_deviation": std}
        ordered_oot = context.loc[oot].sort_values("time_btjd")["_flux"].to_numpy(float)
        diff_scale = robust_scale(np.diff(ordered_oot))
        if diff_scale is not None:
            diff_scale /= math.sqrt(2.0)
        formal_floor = float(np.median(context.loc[rows, "_flux_err"]))
        noise_scale = max(diff_scale or 0.0, formal_floor, 1e-6)
        context.loc[context["sector"] == sector, "_noise_scale"] = noise_scale
        standards[str(sector)] = {
            "pdcsap_normalization": norm_value,
            "time_mean_btjd": time_mean,
            "time_standard_deviation_days": time_std,
            "telemetry": telemetry_standards,
            "fixed_robust_noise_scale_fraction": noise_scale,
        }
    return context, standards


class TransitProfiler:
    def __init__(self, frame):
        self.frame = frame
        self.phase = frame["_phase"].to_numpy(float)
        self.y = frame["_flux"].to_numpy(float)
        self.sector = frame["sector"].to_numpy(int)
        self.noise = frame["_noise_scale"].to_numpy(float)
        self.design_columns = [
            "sector_offset",
            "sector_linear_time",
            *TELEMETRY.keys(),
        ]
        self.sector_indices = {}
        self.design = {}
        for sector in SECTORS:
            index = np.flatnonzero(self.sector == sector)
            self.sector_indices[sector] = index
            sector_frame = frame.iloc[index]
            self.design[sector] = np.column_stack(
                [
                    np.ones(len(index)),
                    sector_frame["_time_z"].to_numpy(float),
                    *[
                        sector_frame[f"_{column}_z"].to_numpy(float)
                        for column in TELEMETRY.values()
                    ],
                ]
            )
        params = batman.TransitParams()
        params.t0 = 0.0
        params.per = PERIOD_DAYS
        params.rp = 0.055
        params.a = 10.4
        params.inc = 86.0
        params.ecc = 0.0
        params.w = 90.0
        params.u = [LD_U1, LD_U2]
        params.limb_dark = "quadratic"
        self.params = params
        self.model = batman.TransitModel(
            params,
            self.phase,
            supersample_factor=SUPERSAMPLE_FACTOR,
            exp_time=EXPOSURE_SECONDS / 86400.0,
        )

    def transit(self, theta):
        rp, a_rs, impact = [float(item) for item in theta]
        if impact >= 1.0 + rp or impact >= a_rs:
            return None
        cosine = impact / a_rs
        if not 0.0 <= cosine < 1.0:
            return None
        self.params.rp = rp
        self.params.a = a_rs
        self.params.inc = math.degrees(math.acos(cosine))
        return self.model.light_curve(self.params)

    def profile(self, theta):
        transit = self.transit(theta)
        if transit is None or not np.all(np.isfinite(transit)):
            return None
        residual = np.empty_like(self.y)
        coefficients = {}
        ranks = {}
        for sector in SECTORS:
            index = self.sector_indices[sector]
            design = self.design[sector]
            beta, _, rank, _ = np.linalg.lstsq(
                design, self.y[index] - transit[index], rcond=None
            )
            residual[index] = self.y[index] - transit[index] - design @ beta
            coefficients[sector] = beta
            ranks[sector] = int(rank)
        return residual, transit, coefficients, ranks

    def residual(self, theta):
        profile = self.profile(theta)
        if profile is None:
            return np.full(len(self.y), 1e6, dtype=float)
        return profile[0] / self.noise


def robust_objective(residual):
    residual = np.asarray(residual, dtype=float)
    return float(np.sum(np.sqrt(1.0 + residual**2) - 1.0))


def fit_geometry(frame, mask_name):
    profiler = TransitProfiler(frame)
    lower = np.array([0.03, 5.0, 0.0])
    upper = np.array([0.09, 16.0, 0.98])
    starts = [
        np.array([0.05466, 10.44, 0.715]),
        np.array([0.052, 8.5, 0.45]),
        np.array([0.058, 12.0, 0.84]),
        np.array([0.047, 7.0, 0.20]),
        np.array([0.061, 14.0, 0.91]),
    ]
    attempts = []
    results = []
    for index, start in enumerate(starts):
        initial_residual = profiler.residual(start)
        result = least_squares(
            profiler.residual,
            start,
            bounds=(lower, upper),
            method="trf",
            loss="soft_l1",
            f_scale=1.0,
            x_scale="jac",
            max_nfev=500,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        results.append(result)
        movement = result.x - start
        attempts.append(
            {
                "start_index": index,
                "initial": {
                    "rp_rs": float(start[0]),
                    "a_rs": float(start[1]),
                    "impact_parameter": float(start[2]),
                },
                "final": {
                    "rp_rs": float(result.x[0]),
                    "a_rs": float(result.x[1]),
                    "impact_parameter": float(result.x[2]),
                },
                "movement": {
                    "rp_rs": float(movement[0]),
                    "a_rs": float(movement[1]),
                    "impact_parameter": float(movement[2]),
                    "scaled_euclidean": float(
                        np.linalg.norm(movement / (upper - lower))
                    ),
                },
                "initial_robust_objective": robust_objective(initial_residual),
                "final_robust_objective": float(result.cost),
                "success": bool(result.success),
                "status": int(result.status),
                "message": str(result.message),
                "n_function_evaluations": int(result.nfev),
                "optimality": float(result.optimality),
            }
        )
    finite = [
        index for index, result in enumerate(results) if np.isfinite(result.cost)
    ]
    if not finite:
        raise RuntimeError(f"No finite optimizer result for mask {mask_name}")
    successful = [index for index in finite if results[index].success]
    candidates = successful or finite
    best_index = min(candidates, key=lambda index: results[index].cost)
    result = results[best_index]
    profile = profiler.profile(result.x)
    if profile is None:
        raise RuntimeError(f"Invalid best geometry for mask {mask_name}")
    residual, transit, coefficients, ranks = profile
    nuisance_count = int(sum(ranks.values()))
    dof = max(1, len(frame) - len(result.x) - nuisance_count)
    jacobian = np.asarray(result.jac, dtype=float)
    information = jacobian.T @ jacobian
    jacobian_rank = int(np.linalg.matrix_rank(jacobian))
    condition = float(np.linalg.cond(information))
    residual_scale = float(2.0 * result.cost / dof)
    covariance = np.linalg.pinv(information) * residual_scale
    errors = np.sqrt(np.clip(np.diag(covariance), 0.0, np.inf))
    covariance_valid = bool(
        jacobian_rank == 3
        and np.all(np.isfinite(covariance))
        and np.all(np.diag(covariance) > 0)
        and np.isfinite(condition)
        and condition < 1e14
    )
    t14 = duration_hours(result.x)
    gradient = np.empty(3)
    steps = np.array([1e-6, 1e-4, 1e-5])
    for index, step in enumerate(steps):
        plus = result.x.copy()
        minus = result.x.copy()
        plus[index] += step
        minus[index] -= step
        gradient[index] = (duration_hours(plus) - duration_hours(minus)) / (2 * step)
    t14_variance = float(gradient @ covariance @ gradient)
    t14_error = math.sqrt(max(0.0, t14_variance))
    if not np.isfinite(t14_error) or t14_error <= 0:
        covariance_valid = False
    parameters = {
        "rp_rs": {"value": float(result.x[0]), "error": float(errors[0])},
        "a_rs": {"value": float(result.x[1]), "error": float(errors[1])},
        "impact_parameter": {
            "value": float(result.x[2]),
            "error": float(errors[2]),
        },
        "t14_hours": {"value": float(t14), "error": float(t14_error)},
    }
    coefficients_output = {}
    for sector in SECTORS:
        coefficients_output[str(sector)] = {
            name: float(value)
            for name, value in zip(profiler.design_columns, coefficients[sector])
        }
    output = {
        "mask": mask_name,
        "numeric_bitmask": MASKS[mask_name]["numeric_bitmask"],
        "n_points": int(len(frame)),
        "n_points_by_sector": {
            str(sector): int(np.count_nonzero(frame["sector"].to_numpy(int) == sector))
            for sector in SECTORS
        },
        "model": {
            "flux": "PDCSAP_FLUX normalized by sector out-of-transit median",
            "timestamps": "native 120-s BTJD within +/-13 h of fixed official ephemeris",
            "period_days_fixed": PERIOD_DAYS,
            "t0_btjd_fixed": T0_BTJD,
            "limb_darkening_fixed": [LD_U1, LD_U2],
            "exposure_seconds": EXPOSURE_SECONDS,
            "supersample_factor": SUPERSAMPLE_FACTOR,
            "shared_parameters": ["rp_rs", "a_rs", "impact_parameter"],
            "profiled_per_sector": profiler.design_columns,
        },
        "optimizer": {
            "algorithm": "scipy least_squares TRF, bounds, soft_l1 loss",
            "multiple_start_count": len(starts),
            "selected_start_index": best_index,
            "selected_success": bool(result.success),
            "selected_status": int(result.status),
            "selected_message": str(result.message),
            "selected_n_function_evaluations": int(result.nfev),
            "selected_cost": float(result.cost),
            "attempts": attempts,
        },
        "covariance": {
            "method": (
                "Gauss-Newton inverse information from the profiled soft_l1 "
                "least-squares Jacobian, scaled by robust residual cost per dof"
            ),
            "matrix_parameter_order": ["rp_rs", "a_rs", "impact_parameter"],
            "matrix": covariance.tolist(),
            "jacobian_shape": list(jacobian.shape),
            "jacobian_rank": jacobian_rank,
            "information_condition_number": condition,
            "residual_degrees_of_freedom": dof,
            "nuisance_parameter_rank": nuisance_count,
            "valid": covariance_valid,
        },
        "parameters": parameters,
        "profiled_coefficients": coefficients_output,
        "pass_optimizer_and_covariance": bool(result.success and covariance_valid),
    }
    internal = {
        "profiler": profiler,
        "theta": result.x,
        "residual": residual,
        "transit": transit,
        "coefficients": coefficients,
    }
    return output, internal


def geometry_analysis(context):
    fits_output = {}
    internals = {}
    for mask_name in MASKS:
        selected = context["_geometry_base"].to_numpy(bool) & mask_pass(
            context["quality"].to_numpy(np.int64), mask_name
        )
        frame = context.loc[selected].copy().reset_index(drop=True)
        fit_output, internal = fit_geometry(frame, mask_name)
        fits_output[mask_name] = fit_output
        internals[mask_name] = internal
        values = fit_output["parameters"]
        print(
            f"{mask_name}: rp/Rs={values['rp_rs']['value']:.7f}+/-"
            f"{values['rp_rs']['error']:.7f}, a/Rs={values['a_rs']['value']:.4f}, "
            f"b={values['impact_parameter']['value']:.4f}"
        )
    names = list(MASKS)
    parameter_names = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")
    pairwise = []
    maxima = {name: 0.0 for name in parameter_names}
    for left_index in range(len(names)):
        for right_index in range(left_index + 1, len(names)):
            left = names[left_index]
            right = names[right_index]
            shifts = {}
            for parameter in parameter_names:
                left_value = fits_output[left]["parameters"][parameter]
                right_value = fits_output[right]["parameters"][parameter]
                combined = math.hypot(left_value["error"], right_value["error"])
                absolute = abs(left_value["value"] - right_value["value"])
                sigma = absolute / combined if combined > 0 else float("inf")
                maxima[parameter] = max(maxima[parameter], sigma)
                shifts[parameter] = {
                    "absolute_shift": absolute,
                    "combined_error": combined,
                    "combined_sigma_shift": sigma,
                    "threshold_combined_sigma": MAX_GEOMETRY_SHIFT_SIGMA,
                    "pass": bool(sigma <= MAX_GEOMETRY_SHIFT_SIGMA),
                }
            pairwise.append({"left_mask": left, "right_mask": right, "shifts": shifts})
    optimizer_covariance_pass = all(
        item["pass_optimizer_and_covariance"] for item in fits_output.values()
    )
    shifts_pass = all(value <= MAX_GEOMETRY_SHIFT_SIGMA for value in maxima.values())
    systematic = {}
    for parameter in parameter_names:
        values = np.asarray(
            [fits_output[name]["parameters"][parameter]["value"] for name in names]
        )
        systematic[parameter] = {
            "between_mask_standard_deviation": float(np.std(values, ddof=1)),
            "half_range": float(0.5 * np.ptp(values)),
            "adopted_systematic": float(max(np.std(values, ddof=1), 0.5 * np.ptp(values))),
        }
    systematic_propagated = bool(not shifts_pass and optimizer_covariance_pass)
    return (
        {
            "gate_definition": (
                "For rp/rs, a/rs, impact parameter, and T14, every pairwise "
                "absolute shift divided by the quadrature-combined 1-sigma errors "
                "must be <= 0.5."
            ),
            "fits": fits_output,
            "pairwise_shifts": pairwise,
            "maximum_combined_sigma_shift": maxima,
            "between_mask_systematic": {
                "values": systematic,
                "propagated": systematic_propagated,
                "propagation_rule": (
                    "If the 0.5-sigma gate is exceeded, add the larger of the "
                    "between-mask sample SD and half-range in quadrature to the "
                    "corresponding geometry uncertainty."
                ),
            },
            "optimizer_covariance_pass": optimizer_covariance_pass,
            "shift_gate_pass": shifts_pass,
            "gate_pass": bool(optimizer_covariance_pass and shifts_pass),
        },
        internals,
    )


def telemetry_analysis(internal, standards):
    profiler = internal["profiler"]
    transit = internal["transit"]
    coefficients = internal["coefficients"]
    by_sector = {}
    global_before = {name: [] for name in TELEMETRY}
    global_after = {name: [] for name in TELEMETRY}
    global_z = {name: [] for name in TELEMETRY}
    all_post = []
    for sector in SECTORS:
        index = profiler.sector_indices[sector]
        design = profiler.design[sector]
        beta = coefficients[sector]
        baseline = design[:, :2] @ beta[:2]
        correction = design[:, 2:] @ beta[2:]
        before = profiler.y[index] - transit[index] - baseline
        after = before - correction
        correlations = {}
        for telemetry_index, name in enumerate(TELEMETRY):
            standardized = design[:, telemetry_index + 2]
            before_r = pearson_r(before, standardized)
            after_r = pearson_r(after, standardized)
            passed = after_r is not None and abs(after_r) < MAX_POST_TELEMETRY_R
            correlations[name] = {
                "n_cadences": int(len(index)),
                "before_correction_r": before_r,
                "after_correction_r": after_r,
                "threshold_absolute_r": MAX_POST_TELEMETRY_R,
                "pass": passed,
            }
            global_before[name].append(before)
            global_after[name].append(after)
            global_z[name].append(standardized)
            if after_r is not None:
                all_post.append(abs(after_r))
        by_sector[str(sector)] = {
            "standardization": standards[str(sector)]["telemetry"],
            "correlations": correlations,
        }
    global_result = {}
    for name in TELEMETRY:
        before = np.concatenate(global_before[name])
        after = np.concatenate(global_after[name])
        standardized = np.concatenate(global_z[name])
        before_r = pearson_r(before, standardized)
        after_r = pearson_r(after, standardized)
        passed = after_r is not None and abs(after_r) < MAX_POST_TELEMETRY_R
        global_result[name] = {
            "n_cadences": int(len(after)),
            "before_correction_r": before_r,
            "after_correction_r": after_r,
            "threshold_absolute_r": MAX_POST_TELEMETRY_R,
            "pass": passed,
        }
        if after_r is not None:
            all_post.append(abs(after_r))
    psf = {
        name: {
            "available": False,
            "finite_count_in_raw_120s_ledger": 0,
            "reason": "column is present but all values are NaN",
        }
        for name in PSF_COLUMNS
    }
    gate_pass = bool(all_post and max(all_post) < MAX_POST_TELEMETRY_R)
    return {
        "reference_mask": "lightkurve_default",
        "residual_definition": (
            "before: normalized PDCSAP minus exposure-integrated transit and "
            "per-sector offset/slope; after: additionally minus all five jointly "
            "fitted standardized telemetry regressors"
        ),
        "available_variables": list(TELEMETRY),
        "standardization": "mean zero and unit population standard deviation per sector",
        "by_sector": by_sector,
        "global": global_result,
        "psf_centroids": psf,
        "maximum_available_post_correction_absolute_r": max(all_post) if all_post else None,
        "threshold_absolute_r": MAX_POST_TELEMETRY_R,
        "gate_pass": gate_pass,
    }


def make_time_blocks(time, maximum_duration_days=1.0, gap_days=0.25):
    time = np.asarray(time, dtype=float)
    block = np.zeros(len(time), dtype=int)
    if len(time) == 0:
        return block
    block_id = 0
    start = time[0]
    previous = time[0]
    for index in range(1, len(time)):
        if time[index] - previous > gap_days or time[index] - start >= maximum_duration_days:
            block_id += 1
            start = time[index]
        block[index] = block_id
        previous = time[index]
    return block


def cv_linear_cbv(y, vectors, errors, blocks, n_cbv):
    squared_errors = []
    log_score_sum = 0.0
    validation_count = 0
    fold_count = 0
    for block_id in np.unique(blocks):
        validation = blocks == block_id
        training = ~validation
        if validation.sum() < 20 or training.sum() < max(100, n_cbv + 5):
            continue
        if n_cbv:
            mean = np.mean(vectors[training, :n_cbv], axis=0)
            scale = np.std(vectors[training, :n_cbv], axis=0)
            if np.any(~np.isfinite(scale)) or np.any(scale <= 0):
                continue
            train_vectors = (vectors[training, :n_cbv] - mean) / scale
            validation_vectors = (vectors[validation, :n_cbv] - mean) / scale
            train_design = np.column_stack([np.ones(training.sum()), train_vectors])
            validation_design = np.column_stack(
                [np.ones(validation.sum()), validation_vectors]
            )
        else:
            train_design = np.ones((training.sum(), 1))
            validation_design = np.ones((validation.sum(), 1))
        beta, _, rank, _ = np.linalg.lstsq(train_design, y[training], rcond=None)
        if rank != train_design.shape[1]:
            continue
        train_residual = y[training] - train_design @ beta
        validation_residual = y[validation] - validation_design @ beta
        sigma = max(
            float(np.sqrt(np.mean(train_residual**2))),
            float(np.median(errors[training])),
            1e-8,
        )
        squared_errors.append(validation_residual**2)
        log_score_sum += float(
            np.sum(
                -0.5 * (validation_residual / sigma) ** 2
                - math.log(sigma * math.sqrt(2.0 * math.pi))
            )
        )
        validation_count += int(validation.sum())
        fold_count += 1
    if validation_count == 0:
        return None
    squared_errors = np.concatenate(squared_errors)
    return {
        "n_cbv": n_cbv,
        "predictive_rmse_fraction": float(np.sqrt(np.mean(squared_errors))),
        "predictive_rmse_ppm": float(np.sqrt(np.mean(squared_errors)) * 1e6),
        "mean_predictive_log_score": float(log_score_sum / validation_count),
        "fold_count": fold_count,
        "validation_point_count": validation_count,
    }


def cbv_analysis(ledger, input_inventory):
    by_sector = {}
    csv_rows = []
    all_valid = True
    products = {int(item["sector"]): item for item in input_inventory["cbv_products"]}
    for sector in SECTORS:
        product = products.get(sector)
        if product is None:
            all_valid = False
            by_sector[str(sector)] = {"valid": False, "reason": "missing CBV product"}
            continue
        path = ROOT / product["relative_path"]
        hash_valid = path.is_file() and sha256_file(path) == product["sha256"]
        if not hash_valid:
            all_valid = False
            by_sector[str(sector)] = {"valid": False, "reason": "CBV hash mismatch"}
            continue
        with fits.open(path, mode="readonly", memmap=True) as hdul:
            hdu_index = int(product["fits"]["single_scale_hdu_index"])
            hdu = hdul[hdu_index]
            cbv = pd.DataFrame(
                {
                    "cadenceno": np.asarray(hdu.data["CADENCENO"], dtype=np.int64),
                    "cbv_time": np.asarray(hdu.data["TIME"], dtype=float),
                    "cbv_gap": np.asarray(hdu.data["GAP"], dtype=bool),
                    **{
                        f"vector_{index}": np.asarray(
                            hdu.data[f"VECTOR_{index}"], dtype=float
                        )
                        for index in range(1, 9)
                    },
                }
            )
        target = ledger.loc[ledger["sector"] == sector].copy()
        raw_count = len(target)
        merged = target.merge(cbv, on="cadenceno", how="inner", validate="one_to_one")
        vector_columns = [f"vector_{index}" for index in range(1, 9)]
        quality_ok = mask_pass(merged["quality"].to_numpy(np.int64), "lightkurve_default")
        phase = phase_days(merged["time_btjd"].to_numpy(float))
        out_of_transit = np.abs(phase * 24.0) > 0.5 * T14_HOURS
        finite = (
            np.isfinite(merged["time_btjd"])
            & np.isfinite(merged["sap_flux"])
            & np.isfinite(merged["sap_flux_err"])
            & (merged["sap_flux"] > 0)
            & (merged["sap_flux_err"] > 0)
            & np.all(np.isfinite(merged[vector_columns]), axis=1)
            & ~merged["cbv_gap"]
        )
        eligible = np.asarray(finite & quality_ok & out_of_transit, dtype=bool)
        validation_frame = merged.loc[eligible].sort_values("time_btjd").reset_index(drop=True)
        norm_value = float(np.median(validation_frame["sap_flux"]))
        y = validation_frame["sap_flux"].to_numpy(float) / norm_value - 1.0
        errors = validation_frame["sap_flux_err"].to_numpy(float) / norm_value
        vectors = validation_frame[vector_columns].to_numpy(float)
        blocks = make_time_blocks(validation_frame["time_btjd"].to_numpy(float))
        block_records = []
        for block_id in np.unique(blocks):
            selected = blocks == block_id
            block_records.append(
                {
                    "block_id": int(block_id),
                    "start_btjd": float(validation_frame.loc[selected, "time_btjd"].min()),
                    "stop_btjd": float(validation_frame.loc[selected, "time_btjd"].max()),
                    "cadence_count": int(selected.sum()),
                }
            )
        candidates = []
        for n_cbv in range(9):
            candidate = cv_linear_cbv(y, vectors, errors, blocks, n_cbv)
            if candidate is not None:
                candidates.append(candidate)
                csv_rows.append({"sector": sector, **candidate})
        selected = (
            min(candidates, key=lambda item: (item["predictive_rmse_fraction"], item["n_cbv"]))
            if candidates
            else None
        )
        valid = bool(
            len(merged) == raw_count
            and len(validation_frame) > 100
            and len(block_records) >= 3
            and len(candidates) == 9
            and selected is not None
            and np.isfinite(selected["predictive_rmse_fraction"])
        )
        all_valid &= valid
        by_sector[str(sector)] = {
            "valid": valid,
            "source": {
                "relative_path": product["relative_path"],
                "sha256": product["sha256"],
                "hash_valid": hash_valid,
                "url": product["url"],
                "single_scale_extension": product["fits"]["single_scale_extension"],
            },
            "alignment": {
                "key": "CADENCENO",
                "target_raw_row_count": raw_count,
                "cbv_row_count": len(cbv),
                "aligned_row_count": len(merged),
                "exact_full_alignment": len(merged) == raw_count == len(cbv),
            },
            "selection_data": {
                "flux": "SAP_FLUX",
                "quality_mask": "lightkurve_default (17087)",
                "transit_points_used": False,
                "out_of_transit_rule": f"abs(phase_hours) > {0.5 * T14_HOURS:.6f}",
                "out_of_transit_aligned_cadence_count": len(validation_frame),
            },
            "blocked_validation": {
                "method": "leave-one-contiguous-time-block-out predictive validation",
                "block_definition": (
                    "sorted out-of-transit cadences; start a block at a gap >0.25 d "
                    "or when elapsed block duration reaches 1.0 d"
                ),
                "block_count": len(block_records),
                "blocks": block_records,
            },
            "vectors_tested": list(range(9)),
            "candidate_scores": candidates,
            "selected_n_cbv": selected["n_cbv"] if selected else None,
            "selected_predictive_rmse_ppm": (
                selected["predictive_rmse_ppm"] if selected else None
            ),
            "selected_mean_predictive_log_score": (
                selected["mean_predictive_log_score"] if selected else None
            ),
            "selection_metric": "minimum blocked predictive RMSE; lower n breaks exact ties",
        }
        if selected:
            print(
                f"S{sector:03d} CBV selection: n={selected['n_cbv']}, "
                f"RMSE={selected['predictive_rmse_ppm']:.2f} ppm"
            )
    pd.DataFrame(csv_rows).to_csv(CBV_CSV_PATH, index=False)
    return {
        "method": (
            "Official SingleScale CBVs aligned by CADENCENO; n=0..8 selected "
            "using SAP out-of-transit leave-one-time-block-out prediction only"
        ),
        "transit_depth_used_for_selection": False,
        "by_sector": by_sector,
        "all_six_sectors_valid": bool(all_valid and len(by_sector) == 6),
        "gate_pass": bool(all_valid and len(by_sector) == 6),
        "compact_csv": relative(CBV_CSV_PATH),
    }


def load_control_frames(input_inventory):
    frames = {}
    products = {}
    for item in input_inventory["control_products"]:
        sector = int(item["sector"])
        path = ROOT / item["relative_path"]
        hash_valid = path.is_file() and sha256_file(path) == item["sha256"]
        if not hash_valid:
            raise RuntimeError(f"Control LC hash mismatch in sector {sector}")
        with fits.open(path, mode="readonly", memmap=True) as hdul:
            primary = hdul[0].header
            data = hdul[1].data
            frame = pd.DataFrame(
                {
                    "time": np.asarray(data["TIME"], dtype=float),
                    "cadenceno": np.asarray(data["CADENCENO"], dtype=np.int64),
                    "flux": np.asarray(data["PDCSAP_FLUX"], dtype=float),
                    "flux_err": np.asarray(data["PDCSAP_FLUX_ERR"], dtype=float),
                    "quality": np.asarray(data["QUALITY"], dtype=np.int64),
                    **{
                        public_name: np.asarray(data[public_name], dtype=float)
                        for public_name in TELEMETRY
                    },
                }
            )
            if (
                int(primary.get("TICID", -1)) != 81400324
                or int(primary.get("SECTOR", -1)) != sector
                or int(primary.get("CAMERA", -1)) != int(item["camera"])
                or int(primary.get("CCD", -1)) != int(item["ccd"])
            ):
                raise RuntimeError(f"Control header mismatch in sector {sector}")
        phase = phase_days(frame["time"].to_numpy(float))
        normalization_rows = (
            np.isfinite(frame["time"])
            & np.isfinite(frame["flux"])
            & np.isfinite(frame["flux_err"])
            & (frame["flux"] > 0)
            & (frame["flux_err"] > 0)
            & mask_pass(frame["quality"].to_numpy(np.int64), "lightkurve_default")
            & (np.abs(phase * 24.0) > 0.5 * T14_HOURS)
        )
        normalization = float(np.median(frame.loc[normalization_rows, "flux"]))
        frame["normalized_flux"] = frame["flux"] / normalization
        frame["normalized_flux_err"] = frame["flux_err"] / normalization
        frames[sector] = frame
        products[str(sector)] = {
            "relative_path": item["relative_path"],
            "sha256": item["sha256"],
            "hash_valid": hash_valid,
            "dataURI": item["dataURI"],
            "url": item["url"],
            "camera": int(item["camera"]),
            "ccd": int(item["ccd"]),
            "cadence_seconds": int(item["cadence_seconds"]),
            "normalization": normalization,
        }
    if tuple(sorted(frames)) != SECTORS:
        raise RuntimeError(f"Expected six control sectors, found {sorted(frames)}")
    return frames, products


def control_event_fit(frame, midpoint, seed):
    time = frame["time"].to_numpy(float)
    y = frame["normalized_flux"].to_numpy(float)
    dt = time - midpoint
    dt_scale = float(np.std(dt))
    columns = [np.ones(len(frame)), dt / dt_scale]
    telemetry_standards = {}
    for name in TELEMETRY:
        values = frame[name].to_numpy(float)
        mean = float(np.mean(values))
        std = float(np.std(values))
        columns.append((values - mean) / std)
        telemetry_standards[name] = {"mean": mean, "standard_deviation": std}
    in_transit = np.abs(dt * 24.0) <= 0.5 * T14_HOURS
    columns.append(in_transit.astype(float))
    design = np.column_stack(columns)
    beta, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    prediction = design @ beta
    residual = y - prediction
    dof = len(y) - int(rank)
    if rank != design.shape[1] or dof <= 0:
        return None
    residual_variance = float(np.dot(residual, residual) / dof)
    covariance = np.linalg.pinv(design.T @ design) * residual_variance
    analytic_error = float(math.sqrt(max(0.0, covariance[-1, -1])) * 1e6)
    rng = np.random.default_rng(seed)
    centered_residual = residual - np.mean(residual)
    bootstrap_depths = np.empty(CONTROL_BOOTSTRAPS)
    n = len(frame)
    for bootstrap_index in range(CONTROL_BOOTSTRAPS):
        sampled = []
        while sum(len(item) for item in sampled) < n:
            start = int(rng.integers(0, n))
            sampled.append((start + np.arange(CONTROL_BLOCK_CADENCES)) % n)
        indices = np.concatenate(sampled)[:n]
        bootstrap_y = prediction + centered_residual[indices]
        bootstrap_beta, _, _, _ = np.linalg.lstsq(design, bootstrap_y, rcond=None)
        bootstrap_depths[bootstrap_index] = -bootstrap_beta[-1] * 1e6
    bootstrap_error = float(np.std(bootstrap_depths, ddof=1))
    error = max(analytic_error, bootstrap_error)
    depth = float(-beta[-1] * 1e6)
    return {
        "depth_ppm": depth,
        "depth_error_ppm": error,
        "raw_significance_sigma": depth / error,
        "analytic_error_ppm": analytic_error,
        "moving_block_bootstrap_error_ppm": bootstrap_error,
        "bootstrap_replicates": CONTROL_BOOTSTRAPS,
        "bootstrap_block_cadences": CONTROL_BLOCK_CADENCES,
        "bootstrap_block_hours": CONTROL_BLOCK_CADENCES * EXPOSURE_SECONDS / 3600.0,
        "n_window": int(len(frame)),
        "n_in_transit": int(in_transit.sum()),
        "n_out_of_transit": int((~in_transit).sum()),
        "design_rank": int(rank),
        "telemetry_standardization": telemetry_standards,
    }


def control_analysis(input_inventory, faz2):
    frames, products = load_control_frames(input_inventory)
    event_results = []
    used_keys = {
        (int(event["sector"]), int(event["epoch"]))
        for event in faz2["events"]
        if event["used"]
    }
    for event in faz2["events"]:
        sector = int(event["sector"])
        epoch = int(event["epoch"])
        start = float(event["analysis_window_start_btjd"])
        stop = float(event["analysis_window_stop_btjd"])
        midpoint = float(event["predicted_midpoint_btjd"])
        source = frames[sector]
        raw_window = np.isfinite(source["time"]) & (source["time"] >= start) & (
            source["time"] <= stop
        )
        for mask_name in MASKS:
            accepted = raw_window & mask_pass(
                source["quality"].to_numpy(np.int64), mask_name
            )
            accepted &= (
                np.isfinite(source["normalized_flux"])
                & np.isfinite(source["normalized_flux_err"])
                & (source["normalized_flux_err"] > 0)
            )
            for telemetry_name in TELEMETRY:
                accepted &= np.isfinite(source[telemetry_name])
            selected = source.loc[accepted].sort_values("time").reset_index(drop=True)
            in_count = int(
                np.count_nonzero(
                    np.abs((selected["time"].to_numpy(float) - midpoint) * 24.0)
                    <= 0.5 * T14_HOURS
                )
            )
            record = {
                "physical_event_id": event["physical_event_id"],
                "sector": sector,
                "epoch": epoch,
                "phase2_classification": event["classification"],
                "phase2_used": bool(event["used"]),
                "mask": mask_name,
                "numeric_bitmask": MASKS[mask_name]["numeric_bitmask"],
                "window_start_btjd": start,
                "window_stop_btjd": stop,
                "predicted_midpoint_btjd": midpoint,
                "raw_finite_time_window_count": int(raw_window.sum()),
                "accepted_finite_window_count": int(len(selected)),
            }
            if len(selected) < 100 or in_count < 20 or len(selected) - in_count < 40:
                record.update(
                    {
                        "evaluable": False,
                        "reason": "insufficient in-transit or baseline control cadences",
                        "depth_ppm": None,
                        "depth_error_ppm": None,
                        "raw_significance_sigma": None,
                    }
                )
            else:
                seed = sector * 100000 + epoch * 10
                result = control_event_fit(selected, midpoint, seed)
                if result is None:
                    record.update(
                        {
                            "evaluable": False,
                            "reason": "rank-deficient event regression",
                            "depth_ppm": None,
                            "depth_error_ppm": None,
                            "raw_significance_sigma": None,
                        }
                    )
                else:
                    record.update({"evaluable": True, "reason": None, **result})
            event_results.append(record)

    trial_count = int(sum(item["evaluable"] for item in event_results))
    for item in event_results:
        if not item["evaluable"]:
            item["two_sided_normal_p_value"] = None
            item["bonferroni_adjusted_p_value"] = None
            item["trial_adjusted_absolute_sigma"] = None
            continue
        raw_sigma = abs(float(item["raw_significance_sigma"]))
        raw_p = float(2.0 * norm.sf(raw_sigma))
        adjusted_p = min(1.0, raw_p * trial_count)
        adjusted_sigma = float(norm.isf(adjusted_p / 2.0)) if adjusted_p < 1.0 else 0.0
        item["two_sided_normal_p_value"] = raw_p
        item["bonferroni_adjusted_p_value"] = adjusted_p
        item["trial_adjusted_absolute_sigma"] = adjusted_sigma

    global_by_mask = {}
    required_coverage = True
    for mask_name in MASKS:
        selected = [
            item
            for item in event_results
            if item["mask"] == mask_name and item["evaluable"]
        ]
        selected_keys = {(item["sector"], item["epoch"]) for item in selected}
        required_coverage &= used_keys.issubset(selected_keys)
        depths = np.asarray([item["depth_ppm"] for item in selected], dtype=float)
        errors = np.asarray([item["depth_error_ppm"] for item in selected], dtype=float)
        weights = 1.0 / errors**2
        mean_depth = float(np.sum(weights * depths) / np.sum(weights))
        formal_error = float(1.0 / math.sqrt(np.sum(weights)))
        chi2 = float(np.sum(((depths - mean_depth) / errors) ** 2))
        dof = max(1, len(depths) - 1)
        scatter_inflation = math.sqrt(max(1.0, chi2 / dof))
        error = formal_error * scatter_inflation
        global_by_mask[mask_name] = {
            "evaluable_event_count": len(selected),
            "required_phase2_used_events_all_evaluable": used_keys.issubset(selected_keys),
            "weighted_mean_depth_ppm": mean_depth,
            "formal_weighted_mean_error_ppm": formal_error,
            "event_scatter_inflation": scatter_inflation,
            "adopted_weighted_mean_error_ppm": error,
            "weighted_mean_significance_sigma": mean_depth / error,
            "maximum_raw_event_absolute_sigma": max(
                abs(item["raw_significance_sigma"]) for item in selected
            ),
            "maximum_trial_adjusted_event_absolute_sigma": max(
                item["trial_adjusted_absolute_sigma"] for item in selected
            ),
        }

    target_depths = pd.read_csv(TARGET_DEPTH_PATH)
    correlations = {}
    for mask_name in MASKS:
        control = pd.DataFrame(
            [
                {
                    "sector": item["sector"],
                    "epoch": item["epoch"],
                    "control_depth_ppm": item["depth_ppm"],
                }
                for item in event_results
                if item["mask"] == mask_name and item["evaluable"]
            ]
        )
        pairs = target_depths.merge(control, on=["sector", "epoch"], how="inner")
        correlations[mask_name] = {
            "paired_event_count": int(len(pairs)),
            "pearson_r": pearson_r(pairs["depth_ppm"], pairs["control_depth_ppm"]),
            "target_depth_source": relative(TARGET_DEPTH_PATH),
        }

    maximum_global = max(
        abs(item["weighted_mean_significance_sigma"]) for item in global_by_mask.values()
    )
    maximum_adjusted_event = max(
        item["trial_adjusted_absolute_sigma"]
        for item in event_results
        if item["evaluable"]
    )
    gate_pass = bool(
        required_coverage
        and maximum_global < CONTROL_SIGNAL_SIGMA
        and maximum_adjusted_event < CONTROL_SIGNAL_SIGMA
    )
    csv_columns = [
        "physical_event_id",
        "sector",
        "epoch",
        "phase2_classification",
        "phase2_used",
        "mask",
        "numeric_bitmask",
        "evaluable",
        "accepted_finite_window_count",
        "depth_ppm",
        "depth_error_ppm",
        "raw_significance_sigma",
        "bonferroni_adjusted_p_value",
        "trial_adjusted_absolute_sigma",
        "reason",
    ]
    pd.DataFrame(event_results)[csv_columns].to_csv(CONTROL_CSV_PATH, index=False)
    return {
        "criteria_frozen_before_values": {
            "control_tic_id": 81400324,
            "mask_family": list(MASKS),
            "event_windows": "all 18 Faz 2 target-ephemeris +/-13 h windows",
            "event_model": (
                "local offset/slope plus all five standardized telemetry variables "
                "and a fixed official-T14 box at the target midpoint"
            ),
            "event_error": (
                "maximum of regression covariance and 256-replicate circular "
                "moving-block residual bootstrap error (1 h blocks)"
            ),
            "trial_treatment": (
                "two-sided normal event p-values multiplied by the total number "
                "of evaluable event-mask trials (Bonferroni)"
            ),
            "gate": (
                "for every mask, abs(scatter-inflated global weighted-mean "
                "significance) < 3 and every Bonferroni-adjusted event significance < 3"
            ),
            "threshold_sigma": CONTROL_SIGNAL_SIGMA,
        },
        "identity": {
            **input_inventory["control"],
            "product_count": len(products),
            "target_data_substituted": False,
        },
        "products": products,
        "trial_count": trial_count,
        "event_results": event_results,
        "global_by_mask": global_by_mask,
        "target_control_event_depth_correlations": correlations,
        "maximum_global_absolute_sigma": maximum_global,
        "maximum_trial_adjusted_event_absolute_sigma": maximum_adjusted_event,
        "required_phase2_used_event_coverage": required_coverage,
        "gate_pass": gate_pass,
        "compact_csv": relative(CONTROL_CSV_PATH),
    }


def event_telemetry_analysis(ledger, faz2):
    sector_reference = {}
    for sector in SECTORS:
        rows = ledger["sector"] == sector
        sector_reference[sector] = {}
        for name, column in TELEMETRY.items():
            values = ledger.loc[rows, column].to_numpy(float)
            finite = values[np.isfinite(values)]
            median = float(np.median(finite)) if len(finite) else None
            scale = robust_scale(finite)
            sector_reference[sector][name] = {"median": median, "robust_scale": scale}
    records = []
    csv_rows = []
    for event_index, event in enumerate(faz2["events"]):
        sector = int(event["sector"])
        start = float(event["analysis_window_start_btjd"])
        stop = float(event["analysis_window_stop_btjd"])
        window = (
            (ledger["sector"] == sector)
            & np.isfinite(ledger["time_btjd"])
            & (ledger["time_btjd"] >= start)
            & (ledger["time_btjd"] <= stop)
        )
        frame = ledger.loc[window]
        quality = frame["quality"].to_numpy(np.int64)
        telemetry_ranges = {
            name: range_summary(frame[column].to_numpy(float))
            for name, column in TELEMETRY.items()
        }
        excursion_counts = {}
        for name, column in TELEMETRY.items():
            reference = sector_reference[sector][name]
            values = frame[column].to_numpy(float)
            if reference["robust_scale"] is None or reference["robust_scale"] <= 0:
                count = 0
            else:
                count = int(
                    np.count_nonzero(
                        np.isfinite(values)
                        & (
                            np.abs(values - reference["median"])
                            > 8.0 * reference["robust_scale"]
                        )
                    )
                )
            excursion_counts[name] = count
        gap = event["coverage_120s"]["nearest_gap_distances"]
        flags = []
        if event["classification"] == "GAP":
            flags.append("NO_IN_TRANSIT_DATA")
        if int(gap["significant_gap_count_in_analysis_window"]) > 0:
            flags.append("CADENCE_GAP_IN_WINDOW")
        if (gap["maximum_gap_duration_days"] or 0.0) > 0.25:
            flags.append("LARGE_GAP_OR_SECTOR_BOUNDARY")
        if np.any(quality != 0):
            flags.append("NONZERO_QUALITY_IN_WINDOW")
        if np.any(quality & 32):
            flags.append("DESATURATION_OR_MOMENTUM_DUMP_BIT")
        if excursion_counts["SAP_BKG"]:
            flags.append("BACKGROUND_8_MAD_EXCURSION")
        if any(excursion_counts[name] for name in TELEMETRY if name != "SAP_BKG"):
            flags.append("POINTING_OR_CENTROID_8_MAD_EXCURSION")
        flags.append("PSF_CENTROIDS_UNAVAILABLE_ALL_NAN")
        mask_counts = {
            name: int(mask_pass(quality, name).sum()) for name in MASKS
        }
        record = {
            "physical_event_id": event["physical_event_id"],
            "sector": sector,
            "epoch": int(event["epoch"]),
            "phase2_link": {
                "source": relative(FAZ2_PATH),
                "event_index": event_index,
                "classification": event["classification"],
                "used": bool(event["used"]),
                "target_product_sha256": event["coverage_120s"]["source"][
                    "product_sha256"
                ],
            },
            "analysis_window": {
                "start_btjd": start,
                "stop_btjd": stop,
                "raw_finite_time_cadence_count": int(len(frame)),
            },
            "telemetry_ranges": telemetry_ranges,
            "telemetry_8_mad_excursion_counts": excursion_counts,
            "quality": {
                "quality_zero_count": int(np.count_nonzero(quality == 0)),
                "quality_nonzero_count": int(np.count_nonzero(quality != 0)),
                "quality_or": int(np.bitwise_or.reduce(quality)) if len(quality) else 0,
                "set_bit_counts": set_bit_counts(quality),
                "accepted_counts_by_mask": mask_counts,
                "desaturation_bit_32_count": int(np.count_nonzero(quality & 32)),
            },
            "gaps": gap,
            "psf_centroids": {
                name: {"available": False, "finite_count": 0} for name in PSF_COLUMNS
            },
            "flags": flags,
        }
        records.append(record)
        csv_rows.append(
            {
                "physical_event_id": event["physical_event_id"],
                "sector": sector,
                "epoch": int(event["epoch"]),
                "classification": event["classification"],
                "used": bool(event["used"]),
                "window_cadences": len(frame),
                "sap_bkg_min": telemetry_ranges["SAP_BKG"]["minimum"],
                "sap_bkg_max": telemetry_ranges["SAP_BKG"]["maximum"],
                "pos_corr1_min": telemetry_ranges["POS_CORR1"]["minimum"],
                "pos_corr1_max": telemetry_ranges["POS_CORR1"]["maximum"],
                "pos_corr2_min": telemetry_ranges["POS_CORR2"]["minimum"],
                "pos_corr2_max": telemetry_ranges["POS_CORR2"]["maximum"],
                "quality_or": record["quality"]["quality_or"],
                "desaturation_bit_32_count": record["quality"][
                    "desaturation_bit_32_count"
                ],
                "significant_gap_count": gap["significant_gap_count_in_analysis_window"],
                "maximum_gap_days": gap["maximum_gap_duration_days"],
                "flags": ";".join(flags),
            }
        )
    pd.DataFrame(csv_rows).to_csv(EVENT_CSV_PATH, index=False)
    return {
        "event_count": len(records),
        "phase2_event_ids_exactly_linked": [item["physical_event_id"] for item in records]
        == [item["physical_event_id"] for item in faz2["events"]],
        "raw_target_columns": list(TELEMETRY),
        "summary_definition": (
            "direct raw cadence ranges and quality/gap flags; no epoch-correlation "
            "surrogate is used for background or pointing"
        ),
        "events": records,
        "compact_csv": relative(EVENT_CSV_PATH),
    }


def validate_inputs(faz1, faz2, input_inventory):
    ledger_hash = sha256_file(LEDGER_PATH)
    checks = {
        "faz1_gate_pass": faz1.get("gate_pass") is True,
        "faz2_gate_pass": faz2.get("gate_pass") is True,
        "faz3_input_gate_pass": input_inventory.get("gate_pass") is True,
        "faz2_has_18_events": len(faz2.get("events", [])) == 18,
        "ledger_hash_matches_faz2": ledger_hash
        == faz2["provenance"]["cadence_ledgers"]["120"]["sha256"],
        "legacy_zip_not_inspected_in_inputs": all(
            item.get("input_policy", {}).get("legacy_zip_inspected") is False
            for item in (faz1, faz2, input_inventory)
        ),
        "control_is_real_not_target_substitution": input_inventory["control"]["tic_id"]
        == 81400324
        and input_inventory["input_policy"]["target_data_substituted_for_control"]
        is False,
    }
    return {
        "checks": checks,
        "all_required_inputs_valid": all(checks.values()),
        "ledger": {
            "relative_path": relative(LEDGER_PATH),
            "size_bytes": LEDGER_PATH.stat().st_size,
            "sha256": ledger_hash,
            "faz2_hash_match": checks["ledger_hash_matches_faz2"],
        },
        "consumed": [
            relative(FAZ1_PATH),
            relative(FAZ2_PATH),
            relative(LEDGER_PATH),
            relative(INPUT_PATH),
        ],
    }


def main():
    print("=" * 78)
    print("FAZ 3: REAL QUALITY / TELEMETRY / CBV / CONTROL-STAR AUDIT")
    print("=" * 78)
    faz1 = json.loads(FAZ1_PATH.read_text(encoding="utf-8"))
    faz2 = json.loads(FAZ2_PATH.read_text(encoding="utf-8"))
    input_inventory = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    inputs = validate_inputs(faz1, faz2, input_inventory)
    if not inputs["all_required_inputs_valid"]:
        raise RuntimeError(f"Required Faz 3 inputs failed validation: {inputs['checks']}")
    ledger = pd.read_csv(LEDGER_PATH)
    if len(ledger) != faz2["provenance"]["cadence_ledgers"]["120"]["row_count"]:
        raise RuntimeError("120-s ledger row count does not match Faz 2 provenance")

    quality = quality_audit(ledger)
    context, standards = geometry_context(ledger)
    geometry, geometry_internals = geometry_analysis(context)
    telemetry = telemetry_analysis(
        geometry_internals["lightkurve_default"], standards
    )
    cbv = cbv_analysis(ledger, input_inventory)
    control = control_analysis(input_inventory, faz2)
    event_telemetry = event_telemetry_analysis(ledger, faz2)

    required_non_geometry = bool(
        inputs["all_required_inputs_valid"]
        and telemetry["gate_pass"]
        and cbv["gate_pass"]
        and control["gate_pass"]
        and event_telemetry["event_count"] == 18
        and event_telemetry["phase2_event_ids_exactly_linked"]
    )
    if required_non_geometry and geometry["gate_pass"]:
        status = "PASS"
    elif (
        required_non_geometry
        and geometry["optimizer_covariance_pass"]
        and not geometry["shift_gate_pass"]
        and geometry["between_mask_systematic"]["propagated"]
    ):
        status = "CONDITIONAL_PASS"
    else:
        status = "FAIL"
    gate_checks = {
        "phase1_gate_true": faz1.get("gate_pass") is True,
        "phase2_gate_true": faz2.get("gate_pass") is True,
        "all_required_inputs_valid": inputs["all_required_inputs_valid"],
        "real_mask_geometry_at_most_0_5_combined_sigma": geometry["gate_pass"],
        "all_available_post_correction_telemetry_abs_r_below_0_10": telemetry[
            "gate_pass"
        ],
        "cbv_blocked_validation_complete_six_sectors": cbv["gate_pass"],
        "real_control_star_gate_pass": control["gate_pass"],
        "all_18_phase2_events_linked_to_raw_telemetry": bool(
            event_telemetry["event_count"] == 18
            and event_telemetry["phase2_event_ids_exactly_linked"]
        ),
    }
    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 3,
        "input_policy": {
            "phase1_and_phase2_logic_rewritten": False,
            "legacy_zip_inspected": False,
            "current_active_local_data_only": True,
        },
        "inputs": inputs,
        "quality_masks": quality,
        "mask_geometry": geometry,
        "telemetry_correlations": telemetry,
        "cbv_selection": cbv,
        "control_star": control,
        "event_telemetry": event_telemetry,
        "gate": {
            "semantics": {
                "PASS": (
                    "Phase 1/2 gates true, real mask geometry <=0.5 combined sigma, "
                    "all available post-correction telemetry |r|<0.10, six valid CBV "
                    "selections, real control gate pass, and 18 event links"
                ),
                "CONDITIONAL_PASS": (
                    "only the mask-shift gate exceeds 0.5 combined sigma and the "
                    "quantified between-mask systematic is propagated"
                ),
                "FAIL": "any other required input or analysis is missing or fails",
            },
            "checks": gate_checks,
            "status": status,
            "gate_pass": status == "PASS",
            "phase4_may_begin": status == "PASS",
            "phase4_closed": status != "PASS",
        },
        "gate_status": status,
        "gate_pass": status == "PASS",
    }
    OUTPUT_PATH.write_text(
        json.dumps(json_ready(payload), indent=2) + "\n", encoding="ascii"
    )
    print("-" * 78)
    print(
        "Telemetry max post-correction |r| = "
        f"{telemetry['maximum_available_post_correction_absolute_r']:.6g}"
    )
    print(
        "Control max global |sigma| = "
        f"{control['maximum_global_absolute_sigma']:.3f}; "
        "max trial-adjusted event |sigma| = "
        f"{control['maximum_trial_adjusted_event_absolute_sigma']:.3f}"
    )
    print(f"FAZ 3 DECISION GATE: {status}")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
