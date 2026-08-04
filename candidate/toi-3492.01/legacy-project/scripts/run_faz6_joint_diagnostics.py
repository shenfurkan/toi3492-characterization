"""Run the frozen Phase-6 K0 joint fits and residual diagnostics.

The screening result is immutable.  This runner evaluates only K0_white and
writes the final Phase-6 gate after every frozen Phase-5B branch is complete.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re

import batman
import numpy as np
import pandas as pd
from scipy.optimize import minimize

import faz6_noise_core as noise
import faz6_residual_diagnostics as residuals
import run_faz5_window_grid as phase5
import run_faz5b_remediation as phase5b
import run_faz6_noise_models as screening


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "data" / "faz6_joint_diagnostics_protocol_v2.json"
PARENT_PATH = ROOT / "data" / "faz6_preregistered_kernels.json"
FIT_PATH = ROOT / "outputs" / "faz6_k0_joint_fits_v2.csv"
DRAW_PATH = ROOT / "data" / "toi3492_faz6_k0_geometry_draws_v2.npz"
ACF_PATH = ROOT / "outputs" / "faz6_residual_acf_v2.csv"
BETA_PATH = ROOT / "outputs" / "faz6_residual_beta_v2.csv"
PERIODOGRAM_PATH = ROOT / "outputs" / "faz6_residual_periodogram_v2.csv"
PEAK_PATH = ROOT / "outputs" / "faz6_residual_peaks_v2.csv"
OUTPUT_PATH = ROOT / "outputs" / "faz6_final_noise_model_v2.json"

SECTORS = (37, 63, 64, 90, 99, 100)
GEOMETRY_NAMES = ("rp_rs", "a_rs", "impact_parameter")
DRAW_NAMES = GEOMETRY_NAMES + ("t14_hours",)
MODEL_PATTERN = re.compile(r"^(raw_valid|reference_included)::W(\d{2})_P([012])$")
FIT_COLUMNS = (
    "protocol_sha256", "model_index", "model_id", "mask_id", "cell_id",
    "window_hours", "polynomial_degree", "joint_model_weight",
    "cadence_count", "event_count", "valid", "noise_start_success",
    "noise_start_objective", "noise_start_parameters_json", "initial_objective",
    "map_objective", "objective_improvement", "parameter_movement_norm",
    "unit_gradient_max_abs", "multistart_objective_spread",
    "multistart_unit_parameter_spread", "stationarity_valid", "optimizer_success",
    "selected_start_index", "optimizer_attempts_json",
    "parameter_names_json", "parameters_json", "geometry_hessian_valid",
    "geometry_hessian_json", "geometry_covariance_json",
    "hessian_attempts_json", "draw_diagnostics_json", "error_type",
    "error_message",
)
FINAL_ARTIFACTS = (FIT_PATH, DRAW_PATH, ACF_PATH, BETA_PATH,
                   PERIODOGRAM_PATH, PEAK_PATH)


def load_json(path):
    return phase5b.load_json(path)


def sha256_file(path):
    return phase5b.sha256_file(path)


def relative(path):
    return phase5b.relative(path)


def json_ready(value):
    return phase5.json_ready(value)


def compact_json(value):
    return json.dumps(json_ready(value), separators=(",", ":"), ensure_ascii=True)


def atomic_json(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_csv(path, frame, columns=None):
    output = frame if columns is None else frame.loc[:, list(columns)]
    temporary = path.with_name(path.name + ".tmp")
    output.to_csv(temporary, index=False, lineterminator="\n",
                  float_format="%.17g")
    temporary.replace(path)


def atomic_npz(path, **arrays):
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def artifact_record(path, **extra):
    result = {
        "relative_path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    result.update(extra)
    return result


def bool_value(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() == "true"


def verify_declared_hashes(items, prefix, checks):
    for name, item in items.items():
        if "relative_path" not in item or "sha256" not in item:
            continue
        path = ROOT / item["relative_path"]
        checks[prefix + name] = bool(
            path.is_file() and sha256_file(path) == item["sha256"]
        )


def verify_inputs(protocol, parent):
    checks = {}
    verify_declared_hashes(protocol["inputs"], "joint_", checks)
    verify_declared_hashes(parent["inputs"], "parent_", checks)
    checks["parent_protocol_path"] = (
        ROOT / protocol["inputs"]["parent_protocol"]["relative_path"]
    ).resolve() == PARENT_PATH.resolve()
    screening_item = protocol["inputs"]["screening_report"]
    report = load_json(ROOT / screening_item["relative_path"])
    candidates = report.get("screening", {}).get(
        "predictive_candidates_pending_joint_diagnostics", [])
    checks["screening_status"] = report.get("status") == screening_item[
        "required_status"]
    checks["screening_candidate_count"] = (
        len(candidates) == screening_item["required_predictive_candidate_count"] == 0
    )
    checks["screening_all_scores_valid"] = bool(
        report.get("gate", {}).get("all_576_rows_valid") is True
    )
    checks["screening_phase7_closed"] = bool(
        report.get("gate", {}).get("phase7_may_begin") is False
    )
    checks["loso_row_count"] = len(pd.read_csv(
        ROOT / protocol["inputs"]["loso_scores"]["relative_path"]
    )) == int(protocol["inputs"]["loso_scores"]["row_count"])
    phase5b_report = load_json(
        ROOT / parent["inputs"]["phase5b_report"]["relative_path"]
    )
    checks["phase5b_status"] = phase5b_report.get("status") == parent[
        "inputs"]["phase5b_report"]["required_status"]
    if not all(checks.values()):
        raise RuntimeError("Phase-6 joint input contract failed: {}".format(checks))
    return checks, report, phase5b_report


def parse_model_id(model_id):
    match = MODEL_PATTERN.fullmatch(str(model_id))
    if match is None:
        raise RuntimeError("Invalid Phase-5B model id: {}".format(model_id))
    mask_id, window, degree = match.groups()
    return mask_id, "W{}_P{}".format(window, degree), int(window), int(degree)


def load_branches(protocol, phase5b_report):
    path = ROOT / protocol["inputs"]["phase5b_handoff_draws"]["relative_path"]
    with np.load(path, allow_pickle=False) as payload:
        required = {
            "model_ids", "mask_ids", "cell_ids", "parameter_names",
            "conditional_cell_weights", "joint_model_weights", "draws",
        }
        if not required.issubset(payload.files):
            raise RuntimeError("Phase-5B handoff initializer schema is incomplete")
        model_ids = [str(value) for value in payload["model_ids"]]
        mask_ids = [str(value) for value in payload["mask_ids"]]
        cell_ids = [str(value) for value in payload["cell_ids"]]
        parameter_names = [str(value) for value in payload["parameter_names"]]
        conditional = np.asarray(payload["conditional_cell_weights"], np.float64)
        weights = np.asarray(payload["joint_model_weights"], np.float64)
        draws = np.asarray(payload["draws"], np.float64)
    expected = int(protocol["model"]["branch_count"])
    checks = {
        "model_count_exact": len(model_ids) == expected == draws.shape[0],
        "model_ids_unique": len(set(model_ids)) == expected,
        "parameter_order": parameter_names == list(phase5.PARAMETERS),
        "draw_shape": draws.ndim == 3 and draws.shape[2] == len(phase5.PARAMETERS),
        "draws_finite": bool(np.all(np.isfinite(draws))),
        "conditional_weights_positive_finite": bool(
            np.all(np.isfinite(conditional)) and np.all(conditional > 0.0)
        ),
        "weights_positive_finite": bool(np.all(np.isfinite(weights)) and
                                          np.all(weights > 0.0)),
        "weights_sum_one": math.isclose(float(weights.sum()), 1.0,
                                         rel_tol=0.0, abs_tol=1e-12),
        "report_ids": model_ids == phase5b_report["handoff"]["model_ids"],
    }
    branches = []
    for index, (model_id, mask_id, cell_id, conditional_weight, weight) in enumerate(
        zip(model_ids, mask_ids, cell_ids, conditional, weights)
    ):
        parsed_mask, parsed_cell, window, degree = parse_model_id(model_id)
        checks["branch_{}_identity".format(index)] = (
            parsed_mask == mask_id and parsed_cell == cell_id
        )
        report_weight = phase5b_report["handoff"]["joint_model_weights"][model_id]
        checks["branch_{}_weight".format(index)] = float(weight) == float(report_weight)
        geometry = np.median(draws[index, :, :3], axis=0).astype(np.float64)
        branches.append({
            "model_index": index,
            "model_id": model_id,
            "mask_id": mask_id,
            "cell_id": cell_id,
            "window_hours": window,
            "polynomial_degree": degree,
            "conditional_cell_weight": float(conditional_weight),
            "joint_model_weight": float(weight),
            "geometry_initializer": geometry,
        })
    if not all(checks.values()):
        raise RuntimeError("Phase-5B branch initializer contract failed: {}".format(checks))
    return branches, checks


def load_masks_and_model(protocol, parent):
    prereg = load_json(ROOT / parent["inputs"]["phase5_preregistration"]["relative_path"])
    phase2 = load_json(ROOT / parent["inputs"]["phase2_report"]["relative_path"])
    phase4 = load_json(ROOT / "outputs" / "faz4_reduction_comparison.json")
    raw, reference, _, mask_checks, _, events = phase5b.load_cadence_masks(
        load_json(phase5b.PROTOCOL_PATH), phase2, phase4
    )
    masks = {"raw_valid": raw, "reference_included": reference}
    screening.verify_mask_contract(parent, masks)
    if not all(mask_checks.values()) or len(events) != 16:
        raise RuntimeError("Frozen mask/event contract failed")
    return masks, events, phase2, prereg


@dataclass
class JointSector:
    sector: int
    cadenceno: np.ndarray
    time: np.ndarray
    flux: np.ndarray
    flux_err: np.ndarray
    x_days: np.ndarray
    base_design: np.ndarray


class JointModel:
    def __init__(self, branch, event_frames, prereg):
        self.branch = branch
        self.period_days = float(prereg["transit_model"]["period_days_fixed"])
        self.t0_btjd = float(prereg["transit_model"]["t0_btjd_fixed"])
        self.ld = list(prereg["transit_model"]["limb_darkening_quadratic_fixed"])
        self.exposure_seconds = float(prereg["transit_model"]["exposure_seconds"])
        self.supersample_factor = int(prereg["transit_model"]["supersample_factor"])
        self.geometry_bounds = tuple(
            tuple(float(value) for value in
                  prereg["transit_model"]["geometry_uniform_bounds"][name])
            for name in GEOMETRY_NAMES
        )
        self.sectors = self._build_sectors(event_frames)
        layout_sectors = tuple(self._empty_noise_sector(item) for item in self.sectors)
        self.noise_layout = noise.parameter_layout("K0_white", layout_sectors)
        self.bounds = self.geometry_bounds + self.noise_layout.bounds
        self.parameter_names = GEOMETRY_NAMES + self.noise_layout.names
        params = batman.TransitParams()
        params.t0 = 0.0
        params.per = self.period_days
        params.rp = 0.055
        params.a = 10.2
        params.inc = 86.0
        params.ecc = 0.0
        params.w = 90.0
        params.u = self.ld
        params.limb_dark = "quadratic"
        self.params = params
        self.transit_models = [
            batman.TransitModel(
                params, item.x_days,
                supersample_factor=self.supersample_factor,
                exp_time=self.exposure_seconds / 86400.0,
            )
            for item in self.sectors
        ]

    def _build_sectors(self, event_frames):
        degree = self.branch["polynomial_degree"]
        combined = pd.concat(event_frames, ignore_index=True)
        if combined.duplicated(["sector", "cadenceno"]).any():
            raise RuntimeError("A full-frame cadence belongs to multiple events")
        result = []
        for sector in SECTORS:
            frame = combined.loc[combined["sector"] == sector].copy()
            frame.sort_values("time_btjd", inplace=True)
            frame.reset_index(drop=True, inplace=True)
            event_ids = sorted(frame["event_id"].unique())
            design = np.zeros((len(frame), len(event_ids) * (degree + 1)),
                              dtype=np.float64)
            for event_index, event_id in enumerate(event_ids):
                selected = frame["event_id"].eq(event_id).to_numpy()
                basis = phase5.polynomial_basis(
                    frame.loc[selected, "x_days"].to_numpy(np.float64), degree
                ).astype(np.float64)
                start = event_index * (degree + 1)
                design[selected, start:start + degree + 1] = basis
            if frame.empty or np.linalg.matrix_rank(design) != design.shape[1]:
                raise RuntimeError("Invalid full-frame event design in sector {}".format(sector))
            item = JointSector(
                sector, frame["cadenceno"].to_numpy(np.int64),
                frame["time_btjd"].to_numpy(np.float64),
                frame["flux"].to_numpy(np.float64),
                frame["flux_err"].to_numpy(np.float64),
                frame["x_days"].to_numpy(np.float64), design,
            )
            if (not np.all(np.isfinite(np.column_stack((item.time, item.flux,
                                                        item.flux_err)))) or
                    np.any(item.flux_err <= 0.0) or np.any(np.diff(item.time) <= 0.0)):
                raise RuntimeError("Invalid natural-cadence full frame")
            result.append(item)
        if len(event_frames) != 16 or sum(len(item.time) for item in result) != len(combined):
            raise RuntimeError("Joint model does not contain exactly 16 complete events")
        return tuple(result)

    @staticmethod
    def _empty_noise_sector(item):
        return noise.SectorData(item.sector, item.time, item.flux - 1.0,
                                item.flux_err,
                                np.empty((len(item.time), 0), np.float64))

    def transit(self, geometry):
        rp_rs, a_rs, impact = np.asarray(geometry, np.float64)
        if impact >= 1.0 + rp_rs or impact >= a_rs:
            return None
        cosine = impact / a_rs
        if not 0.0 <= cosine < 1.0:
            return None
        self.params.rp = float(rp_rs)
        self.params.a = float(a_rs)
        self.params.inc = math.degrees(math.acos(float(cosine)))
        values = [model.light_curve(self.params).astype(np.float64)
                  for model in self.transit_models]
        return values if all(np.all(np.isfinite(value)) for value in values) else None

    def sector_data(self, geometry):
        transits = self.transit(geometry)
        if transits is None:
            return None, None
        data = []
        for item, transit in zip(self.sectors, transits):
            data.append(noise.SectorData(
                item.sector, item.time, item.flux - transit, item.flux_err,
                transit[:, None] * item.base_design,
            ))
        return tuple(data), transits

    def objective(self, parameters):
        values = np.asarray(parameters, np.float64)
        if values.shape != (len(self.bounds),) or np.any(~np.isfinite(values)):
            return 1e100
        if any(not lower < value < upper
               for value, (lower, upper) in zip(values[:3], self.geometry_bounds)):
            return 1e100
        data, _ = self.sector_data(values[:3])
        if data is None:
            return 1e100
        try:
            return noise.pooled_map_objective(values[3:], data, self.noise_layout)
        except (ValueError, noise.NoiseModelError, FloatingPointError, OverflowError):
            return 1e100

    def residual_frame(self, parameters):
        values = np.asarray(parameters, np.float64)
        data, _ = self.sector_data(values[:3])
        if data is None:
            raise RuntimeError("Invalid MAP geometry for residuals")
        mu = values[3]
        offsets = values[4:]
        frames = []
        for index, (source, item) in enumerate(zip(self.sectors, data)):
            jitter = item.error_scale * math.exp(mu + offsets[index])
            components = noise.conditional_components(item, "K0_white", jitter)
            frames.append(pd.DataFrame({
                "time_btjd": item.time,
                "cadenceno": source.cadenceno,
                "residual": components.corrected_residual,
                "sector": item.sector,
            }))
        return pd.concat(frames, ignore_index=True)


def build_joint_model(branch, mask, events, prereg):
    half_width = branch["window_hours"] / 48.0
    frames = [phase5.event_rows(mask, event, half_width) for event in events]
    if any(frame.empty for frame in frames):
        raise RuntimeError("A registered event has an empty full frame")
    return JointModel(branch, frames, prereg)


def build_oot_data(branch, mask, events, phase2):
    inner_days = 0.75 * float(
        phase2["ephemeris_and_windows"]["t14_hours"]
    ) / 24.0
    parts = []
    for event in events:
        frame = phase5.event_rows(mask, event, branch["window_hours"] / 48.0)
        frame = frame.loc[np.abs(frame["x_days"]) >= inner_days].copy()
        if frame.empty:
            raise RuntimeError("An event has no OOT cadence")
        parts.append(frame)
    combined = pd.concat(parts, ignore_index=True)
    return tuple(screening.event_block_sector_data(
        combined, sector, branch["polynomial_degree"]
    ) for sector in SECTORS)


def geometry_starts(center, bounds):
    center = np.asarray(center, np.float64)
    perturbation = np.array([0.02 * center[0], 0.02 * center[1], 0.02],
                            dtype=np.float64)
    lower = np.asarray([item[0] for item in bounds], np.float64)
    upper = np.asarray([item[1] for item in bounds], np.float64)
    epsilon = np.maximum((upper - lower) * 1e-8, 1e-12)
    return [np.clip(value, lower + epsilon, upper - epsilon)
            for value in (center, center - perturbation, center + perturbation)]


def empty_fit_row(branch, protocol_hash):
    return {
        "protocol_sha256": protocol_hash,
        "model_index": branch["model_index"], "model_id": branch["model_id"],
        "mask_id": branch["mask_id"], "cell_id": branch["cell_id"],
        "window_hours": branch["window_hours"],
        "polynomial_degree": branch["polynomial_degree"],
        "joint_model_weight": branch["joint_model_weight"],
        "cadence_count": 0, "event_count": 16, "valid": False,
        "noise_start_success": False, "noise_start_objective": np.nan,
        "noise_start_parameters_json": "[]", "initial_objective": np.nan,
        "map_objective": np.nan, "objective_improvement": np.nan,
        "parameter_movement_norm": np.nan, "unit_gradient_max_abs": np.nan,
        "multistart_objective_spread": np.nan,
        "multistart_unit_parameter_spread": np.nan,
        "stationarity_valid": False, "optimizer_success": False,
        "selected_start_index": -1,
        "optimizer_attempts_json": "[]", "parameter_names_json": "[]",
        "parameters_json": "[]", "geometry_hessian_valid": False,
        "geometry_hessian_json": "[]", "geometry_covariance_json": "[]",
        "hessian_attempts_json": "[]", "draw_diagnostics_json": "{}",
        "error_type": "", "error_message": "",
    }


def fit_branch(branch, mask, events, phase2, prereg, protocol_hash):
    row = empty_fit_row(branch, protocol_hash)
    try:
        model = build_joint_model(branch, mask, events, prereg)
        row["cadence_count"] = sum(len(item.time) for item in model.sectors)
        oot = build_oot_data(branch, mask, events, phase2)
        noise_start = noise.fit_pooled_map(oot, "K0_white", required_sector_count=6)
        row.update({
            "noise_start_success": noise_start.success,
            "noise_start_objective": noise_start.objective,
            "noise_start_parameters_json": compact_json(noise_start.parameters),
        })
        if not noise_start.success:
            raise noise.NoiseModelError("Six-sector OOT K0 start did not converge")
        attempts = []
        results = []
        options = {"maxiter": 500, "ftol": 1e-10, "gtol": 1e-6,
                   "finite_diff_rel_step": 1e-4}
        physical_starts = [
            np.concatenate((geometry, noise_start.parameters))
            for geometry in geometry_starts(
                branch["geometry_initializer"], model.geometry_bounds
            )
        ]
        lower = np.asarray([item[0] for item in model.bounds], np.float64)
        upper = np.asarray([item[1] for item in model.bounds], np.float64)
        span = upper - lower
        objective_offset = float(model.objective(physical_starts[0]))

        def scaled_objective(unit_parameters):
            physical = lower + np.asarray(unit_parameters, np.float64) * span
            return model.objective(physical) - objective_offset

        for index, initial in enumerate(physical_starts):
            unit_initial = (initial - lower) / span
            result = minimize(
                scaled_objective,
                unit_initial,
                method="L-BFGS-B",
                jac="3-point",
                bounds=[(1e-8, 1.0 - 1e-8)] * len(unit_initial),
                options=options,
            )
            final = lower + np.asarray(result.x, np.float64) * span
            actual = float(result.fun + objective_offset)
            movement = float(np.linalg.norm(final - initial))
            gradient_max = float(np.max(np.abs(np.asarray(result.jac, np.float64))))
            results.append((result, final, actual, initial, movement, gradient_max))
            attempts.append({
                "start_index": index, "initial": initial.tolist(),
                "final": final.tolist(),
                "negative_log_marginal_posterior": actual,
                "success": bool(result.success), "status": int(result.status),
                "message": str(result.message), "iterations": int(result.nit),
                "function_evaluations": int(result.nfev),
                "parameter_movement_norm": movement,
                "unit_gradient_max_abs": gradient_max,
            })
        finite = [index for index, item in enumerate(results)
                  if np.isfinite(item[2]) and item[2] < 1e100]
        successful = [index for index in finite if results[index][0].success]
        candidates = successful or finite
        if not candidates:
            raise noise.NoiseModelError("All fixed joint starts were invalid")
        selected = min(candidates, key=lambda index: results[index][2])
        best, parameters, best_objective, selected_initial, movement, gradient_max = (
            results[selected]
        )
        converged = [item for item in results if item[0].success]
        objective_spread = float(np.ptp([item[2] for item in converged]))
        unit_finals = np.asarray(
            [(item[1] - lower) / span for item in converged], np.float64
        )
        parameter_spread = float(np.max(np.ptp(unit_finals, axis=0)))
        stationarity = bool(
            best.success
            and len(converged) == 3
            and objective_spread < 1e-3
            and parameter_spread < 1e-3
        )
        row.update({
            "initial_objective": objective_offset,
            "map_objective": best_objective,
            "objective_improvement": objective_offset - best_objective,
            "parameter_movement_norm": movement,
            "unit_gradient_max_abs": gradient_max,
            "multistart_objective_spread": objective_spread,
            "multistart_unit_parameter_spread": parameter_spread,
            "stationarity_valid": stationarity,
            "optimizer_success": stationarity,
            "selected_start_index": selected,
            "optimizer_attempts_json": compact_json(attempts),
            "parameter_names_json": compact_json(model.parameter_names),
            "parameters_json": compact_json(parameters),
        })
        if not stationarity:
            raise noise.NoiseModelError(
                "Selected joint MAP failed stationarity: success={}, objective_spread={}, parameter_spread={}".format(
                    best.success, objective_spread, parameter_spread
                )
            )
        fixed_noise = parameters[3:].copy()

        def conditional_geometry_objective(geometry):
            return model.objective(np.concatenate((geometry, fixed_noise)))

        hessian, covariance, hessian_attempts = phase5.finite_difference_hessian(
            conditional_geometry_objective, parameters[:3]
        )
        draws, draw_diagnostics = phase5.draw_laplace(
            parameters[:3], covariance, model.geometry_bounds,
            4096, 349260 + branch["model_index"], model.period_days,
        )
        row.update({
            "valid": True,
            "geometry_hessian_valid": True,
            "geometry_hessian_json": compact_json(hessian),
            "geometry_covariance_json": compact_json(covariance),
            "hessian_attempts_json": compact_json(hessian_attempts),
            "draw_diagnostics_json": compact_json(draw_diagnostics),
        })
        return row, draws
    except Exception as exc:
        row["valid"] = False
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc).replace("\r", " ").replace("\n", " ")
        return row, None


def load_checkpoint(protocol_hash, branches):
    if not FIT_PATH.exists():
        return pd.DataFrame(columns=FIT_COLUMNS)
    frame = pd.read_csv(FIT_PATH, keep_default_na=False)
    if tuple(frame.columns) != FIT_COLUMNS:
        raise RuntimeError("Joint-fit checkpoint schema mismatch")
    if len(frame) and not frame["protocol_sha256"].eq(protocol_hash).all():
        raise RuntimeError("Joint-fit checkpoint protocol mismatch")
    if frame.duplicated("model_id").any():
        raise RuntimeError("Joint-fit checkpoint has duplicate model ids")
    expected = {item["model_id"] for item in branches}
    if not set(frame["model_id"]).issubset(expected):
        raise RuntimeError("Joint-fit checkpoint contains an unknown model")
    return frame


def append_checkpoint(frame, row):
    result = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
    result.sort_values("model_index", inplace=True)
    result.reset_index(drop=True, inplace=True)
    atomic_csv(FIT_PATH, result, FIT_COLUMNS)
    return result


def reconstruct_branch_products(branch, row, mask, events, prereg):
    if not bool_value(row.valid) or not bool_value(row.geometry_hessian_valid):
        return None
    parameters = np.asarray(json.loads(row.parameters_json), np.float64)
    covariance = np.asarray(json.loads(row.geometry_covariance_json), np.float64)
    model = build_joint_model(branch, mask, events, prereg)
    draws, diagnostics = phase5.draw_laplace(
        parameters[:3], covariance, model.geometry_bounds, 4096,
        349260 + branch["model_index"], model.period_days,
    )
    stored = json.loads(row.draw_diagnostics_json)
    if diagnostics != stored:
        raise RuntimeError("Deterministic Laplace draw reconstruction changed")
    frame = model.residual_frame(parameters)
    diagnostics = residuals.residual_diagnostics(frame)
    return draws, diagnostics


def diagnostics_frames(products):
    acf_frames = []
    beta_frames = []
    periodogram_frames = []
    peak_frames = []
    for branch, (_, diagnostic) in products:
        prefix = {"model_id": branch["model_id"],
                  "joint_model_weight": branch["joint_model_weight"]}
        acf = pd.DataFrame(diagnostic["acf"])
        acf.insert(0, "joint_model_weight", prefix["joint_model_weight"])
        acf.insert(0, "model_id", prefix["model_id"])
        acf_frames.append(acf)
        per_sector = pd.DataFrame(diagnostic["beta"]["per_sector"])
        per_sector.insert(0, "aggregation", "per_sector")
        aggregate = pd.DataFrame(diagnostic["beta"]["aggregate"])
        aggregate.insert(0, "aggregation", "aggregate")
        aggregate["sector"] = "__equal_sector__"
        beta = pd.concat([per_sector, aggregate], ignore_index=True, sort=False)
        beta.insert(0, "joint_model_weight", prefix["joint_model_weight"])
        beta.insert(0, "model_id", prefix["model_id"])
        beta_frames.append(beta)
        periodogram = pd.DataFrame(diagnostic["lomb_scargle"]["periodogram"])
        periodogram.insert(0, "joint_model_weight", prefix["joint_model_weight"])
        periodogram.insert(0, "model_id", prefix["model_id"])
        periodogram_frames.append(periodogram)
        peaks = pd.DataFrame(diagnostic["lomb_scargle"]["peaks"])
        peaks.insert(0, "joint_model_weight", prefix["joint_model_weight"])
        peaks.insert(0, "model_id", prefix["model_id"])
        peak_frames.append(peaks)
    return tuple(pd.concat(items, ignore_index=True) for items in
                 (acf_frames, beta_frames, periodogram_frames, peak_frames))


def weighted_geometry_summary(draw_stack, weights):
    count = draw_stack.shape[1]
    flattened = draw_stack.reshape(-1, draw_stack.shape[-1])
    draw_weights = np.repeat(np.asarray(weights, np.float64) / count, count)
    summary = {}
    for index, name in enumerate(DRAW_NAMES):
        quantiles = phase5.weighted_quantile(
            flattened[:, index], draw_weights,
            [0.025, 0.16, 0.50, 0.84, 0.975],
        )
        summary[name] = dict(zip(
            ("p025", "p16", "median", "p84", "p975"),
            [float(value) for value in quantiles],
        ))
    mean = np.sum(flattened * draw_weights[:, None], axis=0)
    centered = flattened - mean
    covariance = (centered * draw_weights[:, None]).T @ centered
    return summary, covariance


def beta_mixture(beta_frame, branches):
    aggregate = beta_frame.loc[beta_frame["aggregation"] == "aggregate"].copy()
    rows = []
    for timescale in residuals.BETA_TIMESCALES_MINUTES:
        selected = aggregate.loc[aggregate["timescale_minutes"] == float(timescale)]
        lookup = {str(row.model_id): row for row in selected.itertuples(index=False)}

        def finite_beta(row):
            try:
                return np.isfinite(float(row.equal_sector_beta))
            except (TypeError, ValueError):
                return False

        eligible = len(lookup) == len(branches) and all(
            bool_value(lookup[item["model_id"]].all_sectors_eligible) and
            finite_beta(lookup[item["model_id"]])
            for item in branches
        )
        value = None
        if eligible:
            value = float(sum(
                item["joint_model_weight"] *
                float(lookup[item["model_id"]].equal_sector_beta)
                for item in branches
            ))
        rows.append({"timescale_minutes": float(timescale),
                     "all_branches_eligible": eligible,
                     "weighted_equal_sector_beta": value})
    finite = [item["weighted_equal_sector_beta"] for item in rows
              if item["weighted_equal_sector_beta"] is not None]
    complete = all(item["all_branches_eligible"] for item in rows)
    maximum = max(finite) if complete else None
    return rows, complete, maximum


def finalize(protocol, parent, input_checks, branch_checks, branches, fits,
             masks, events, prereg):
    indexed = {str(row.model_id): row for row in fits.itertuples(index=False)}
    products = []
    for branch in branches:
        product = reconstruct_branch_products(
            branch, indexed[branch["model_id"]], masks[branch["mask_id"]],
            events, prereg,
        )
        if product is not None:
            products.append((branch, product))
    all_valid = len(products) == len(branches) == 24
    if all_valid:
        draw_stack = np.stack([product[0] for _, product in products])
        acf, beta, periodogram, peaks = diagnostics_frames(products)
    else:
        draw_stack = np.empty((0, 4096, 4), np.float64)
        acf = pd.DataFrame(columns=("model_id", "joint_model_weight"))
        beta = pd.DataFrame(columns=("model_id", "joint_model_weight", "aggregation"))
        periodogram = pd.DataFrame(columns=("model_id", "joint_model_weight"))
        peaks = pd.DataFrame(columns=("model_id", "joint_model_weight"))
    atomic_csv(ACF_PATH, acf)
    atomic_csv(BETA_PATH, beta)
    atomic_csv(PERIODOGRAM_PATH, periodogram)
    atomic_csv(PEAK_PATH, peaks)
    atomic_npz(
        DRAW_PATH,
        model_ids=np.asarray([item["model_id"] for item in branches], dtype="U40"),
        weights=np.asarray([item["joint_model_weight"] for item in branches], np.float64),
        params=np.asarray(DRAW_NAMES, dtype="U32"),
        draws=draw_stack,
    )
    mixture_summary = None
    mixture_covariance = None
    beta_rows, beta_eligible, weighted_max = [], False, None
    if all_valid:
        mixture_summary, mixture_covariance = weighted_geometry_summary(
            draw_stack, [item["joint_model_weight"] for item in branches]
        )
        beta_rows, beta_eligible, weighted_max = beta_mixture(beta, branches)
    beta_pass = bool(beta_eligible and weighted_max is not None and
                     weighted_max <= float(protocol["residuals"][
                         "beta_maximum_allowed"]))
    passed = all_valid and beta_pass
    status = protocol["gate"]["pass_status"] if passed else protocol["gate"][
        "failure_status"]
    result = {
        "phase": "6-joint-diagnostics", "generated_utc": datetime.now(
            timezone.utc).isoformat(), "status": status,
        "protocol": {"relative_path": relative(PROTOCOL_PATH),
                     "sha256": sha256_file(PROTOCOL_PATH),
                     "frozen_utc": protocol["frozen_utc"]},
        "source_integrity": {"checks": input_checks},
        "screening_outcome": {
            "predictive_candidate_count": 0,
            "retained_kernel": "K0_white",
            "complex_kernels_rejected_by_registered_screen": True,
            "parent_screening_results_modified": False,
            "supersedes_invalid_v1_joint_attempt": True,
        },
        "model": {
            "period_days_fixed": prereg["transit_model"]["period_days_fixed"],
            "t0_btjd_fixed": prereg["transit_model"]["t0_btjd_fixed"],
            "limb_darkening_quadratic_fixed": prereg["transit_model"][
                "limb_darkening_quadratic_fixed"
            ],
            "exposure_seconds": prereg["transit_model"]["exposure_seconds"],
            "supersample_factor": prereg["transit_model"]["supersample_factor"],
            "baseline_prior_sigma": noise.BASELINE_PRIOR_SIGMA,
            "event_baseline": "transit times one-day polynomial basis",
            "target": "observed flux minus exposure-integrated transit",
            "jitter": "global log ratio plus six sector offsets",
            "offset_prior_sigma_natural_log": noise.OFFSET_PRIOR_SIGMA,
        },
        "branch_contract": {"checks": branch_checks, "model_count": len(branches),
                            "joint_weights": {item["model_id"]:
                                item["joint_model_weight"] for item in branches}},
        "joint_fit": {
            "kernel_id": "K0_white", "valid_branch_count": len(products),
            "all_24_valid": all_valid,
            "all_geometry_hessians_valid": all_valid,
            "geometry_hessian_conditioning": "conditional on fixed joint noise MAP",
            "noise_start": "six-sector OOT fit_pooled_map(required_sector_count=6)",
            "optimizer": "three fixed geometry starts, unit-hypercube scaling, objective offset, L-BFGS-B three-point gradient",
            "stationarity_rule": "all three starts converge with objective spread below 1e-3 and maximum unit-parameter spread below 1e-3",
        },
        "residual_diagnostics": {
            "definition": protocol["residuals"]["definition"],
            "branch_beta_mixture": beta_rows,
            "all_timescales_and_branches_eligible": beta_eligible,
            "weighted_max_beta": weighted_max,
            "beta_maximum_allowed": protocol["residuals"]["beta_maximum_allowed"],
            "periodogram_diagnostic_only": True,
        },
        "geometry_mixture": {
            "parameter_order": list(DRAW_NAMES), "summary": mixture_summary,
            "covariance": None if mixture_covariance is None else mixture_covariance.tolist(),
            "branch_weights_exact_phase5b": True,
            "phase5_between_cell_padding_added": False,
            "phase4_reduction_systematic_in_draws": False,
        },
        "gate": {
            "checks": {"all_24_joint_fits_valid": all_valid,
                        "all_24_stationarity_checks_valid": all_valid,
                        "all_24_geometry_hessians_valid": all_valid,
                       "all_beta_timescales_eligible": beta_eligible,
                       "weighted_max_beta_at_most_1p2": beta_pass},
            "status": status, "phase6_pass": passed,
            "phase7_may_begin": bool(passed),
        },
        "limitations": [
            "Geometry draws are conditional Laplace diagnostics at fixed joint-noise MAP values, not final MCMC.",
            "K0 has zero correlated GP posterior mean.",
            "The periodogram is diagnostic only and is not a detection statistic.",
        ],
    }
    result["artifacts"] = {
        "joint_fits": artifact_record(FIT_PATH, row_count=len(fits)),
        "geometry_draws": artifact_record(DRAW_PATH, model_count=len(branches),
                                           draws_per_model=4096 if all_valid else 0),
        "residual_acf": artifact_record(ACF_PATH, row_count=len(acf)),
        "residual_beta": artifact_record(BETA_PATH, row_count=len(beta)),
        "residual_periodogram": artifact_record(PERIODOGRAM_PATH,
                                                 row_count=len(periodogram)),
        "residual_peaks": artifact_record(PEAK_PATH, row_count=len(peaks)),
    }
    atomic_json(OUTPUT_PATH, result)
    return result


def run(protocol, parent, input_checks, phase5b_report, workers):
    if OUTPUT_PATH.exists():
        raise FileExistsError("Final Phase-6 JSON is no-clobber; use --verify-only")
    for path in FINAL_ARTIFACTS[1:]:
        if path.exists():
            raise FileExistsError("Non-checkpoint output already exists: {}".format(relative(path)))
    branches, branch_checks = load_branches(protocol, phase5b_report)
    masks, events, phase2, prereg = load_masks_and_model(protocol, parent)
    protocol_hash = sha256_file(PROTOCOL_PATH)
    fits = load_checkpoint(protocol_hash, branches)
    completed = set(fits["model_id"])
    pending = [item for item in branches if item["model_id"] not in completed]
    if workers == 1:
        generated = (fit_branch(item, masks[item["mask_id"]], events, phase2,
                                prereg, protocol_hash) for item in pending)
        for branch, (row, _) in zip(pending, generated):
            fits = append_checkpoint(fits, row)
            print("Checkpointed {} valid={}".format(branch["model_id"], row["valid"]))
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(
                fit_branch, item, masks[item["mask_id"]], events, phase2,
                prereg, protocol_hash,
            ) for item in pending]
            for branch, future in zip(pending, futures):
                row, _ = future.result()
                fits = append_checkpoint(fits, row)
                print("Checkpointed {} valid={}".format(branch["model_id"], row["valid"]))
    if len(fits) != 24:
        raise RuntimeError("Joint-fit checkpoint is incomplete")
    result = finalize(protocol, parent, input_checks, branch_checks, branches,
                      fits, masks, events, prereg)
    print("Wrote {}: status={}, phase7_may_begin={}".format(
        relative(OUTPUT_PATH), result["status"],
        str(result["gate"]["phase7_may_begin"]).lower()))


def verify_existing(protocol, parent, input_checks, phase5b_report):
    if not OUTPUT_PATH.is_file():
        raise FileNotFoundError(OUTPUT_PATH)
    branches, branch_checks = load_branches(protocol, phase5b_report)
    report = load_json(OUTPUT_PATH)
    checks = {
        "protocol_hash": report["protocol"]["sha256"] == sha256_file(PROTOCOL_PATH),
        "input_checks": all(input_checks.values()),
        "branch_checks": all(branch_checks.values()),
        "model_count": report["branch_contract"]["model_count"] == 24,
        "status": report["status"] in (protocol["gate"]["pass_status"],
                                        protocol["gate"]["failure_status"]),
    }
    for name, artifact in report["artifacts"].items():
        path = ROOT / artifact["relative_path"]
        checks["artifact_{}".format(name)] = bool(
            path.is_file() and sha256_file(path) == artifact["sha256"]
        )
    fits = pd.read_csv(FIT_PATH, keep_default_na=False)
    checks["fit_grid"] = (
        tuple(fits.columns) == FIT_COLUMNS and len(fits) == 24 and
        list(fits.sort_values("model_index")["model_id"]) ==
        [item["model_id"] for item in branches]
    )
    with np.load(DRAW_PATH, allow_pickle=False) as payload:
        checks["draw_schema"] = set(("model_ids", "weights", "params", "draws")) \
            .issubset(payload.files)
        checks["draw_model_ids"] = [str(value) for value in payload["model_ids"]] == [
            item["model_id"] for item in branches]
        checks["draw_weights"] = np.array_equal(
            np.asarray(payload["weights"], np.float64),
            np.asarray([item["joint_model_weight"] for item in branches], np.float64))
    if not all(checks.values()):
        raise RuntimeError("Phase-6 final artifact verification failed: {}".format(checks))
    print("Verified {} and all upstream/artifact hashes".format(relative(OUTPUT_PATH)))


def smoke_test():
    rng = np.random.default_rng(123)
    frames = []
    for sector in SECTORS:
        time = sector * 100.0 + np.arange(240, dtype=np.float64) / 720.0
        frames.append(pd.DataFrame({
            "time_btjd": time,
            "cadenceno": np.arange(len(time), dtype=np.int64),
            "residual": rng.normal(0.0, 2e-4, len(time)).astype(np.float64),
            "sector": sector,
        }))
    diagnostic = residuals.residual_diagnostics(pd.concat(frames, ignore_index=True))
    data = tuple(noise.SectorData(
        sector, frame["time_btjd"].to_numpy(np.float64),
        frame["residual"].to_numpy(np.float64),
        np.full(len(frame), 2e-4, np.float64),
        np.ones((len(frame), 1), np.float64),
    ) for sector, frame in zip(SECTORS, frames))
    fit = noise.fit_pooled_map(data, "K0_white", required_sector_count=6)
    params = batman.TransitParams()
    params.t0 = 0.0
    params.per = 6.7365
    params.rp = 0.055
    params.a = 10.2
    params.inc = 86.0
    params.ecc = 0.0
    params.w = 90.0
    params.u = [0.3, 0.2]
    params.limb_dark = "quadratic"
    transit = batman.TransitModel(params, np.linspace(-0.2, 0.2, 121),
                                  supersample_factor=7,
                                  exp_time=120.0 / 86400.0).light_curve(params)
    if (not fit.success or not np.all(np.isfinite(transit)) or
            diagnostic["input"]["sector_count"] != 6):
        raise RuntimeError("Synthetic smoke test failed")
    print("Synthetic smoke test passed; no TOI data or outputs were touched")


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least one")
    if args.smoke_test:
        smoke_test()
        return
    protocol = load_json(PROTOCOL_PATH)
    parent = load_json(PARENT_PATH)
    input_checks, _, phase5b_report = verify_inputs(protocol, parent)
    if args.verify_only:
        verify_existing(protocol, parent, input_checks, phase5b_report)
        return
    run(protocol, parent, input_checks, phase5b_report, args.workers)


if __name__ == "__main__":
    main()
