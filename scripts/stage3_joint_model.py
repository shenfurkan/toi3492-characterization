"""Joint transit plus sector-timescale Matérn-3/2 MAP model for S3-04B."""

import math
from dataclasses import dataclass

import batman
import numpy as np
import pandas as pd
from scipy.optimize import minimize

import faz6_noise_core as base_noise
import run_faz5_window_grid as phase5
import stage3_noise_core as noise


SECTORS = (37, 63, 64, 90, 99, 100)
GEOMETRY_NAMES = ("rp_rs", "a_rs", "impact_parameter")


@dataclass(frozen=True)
class JointSector:
    sector: int
    cadenceno: np.ndarray
    time: np.ndarray
    flux: np.ndarray
    flux_err: np.ndarray
    x_days: np.ndarray
    base_design: np.ndarray


class Stage3JointModel:
    def __init__(self, branch, event_frames, decision):
        transit = decision["candidate"]["transit_model"]
        self.branch = branch
        self.period_days = float(transit["period_days_fixed"])
        self.ld = list(transit["limb_darkening_quadratic_fixed"])
        self.exposure_seconds = float(transit["exposure_seconds"])
        self.supersample_factor = int(transit["supersample_factor"])
        self.geometry_bounds = tuple(
            tuple(float(value) for value in transit["geometry_uniform_bounds"][name])
            for name in GEOMETRY_NAMES
        )
        self.sectors = self._build_sectors(event_frames)
        layout_sectors = tuple(self._empty_noise_sector(item) for item in self.sectors)
        self.noise_layout = noise.parameter_layout(
            "K3_MATERN32_SECTOR", layout_sectors,
        )
        self.bounds = self.geometry_bounds + self.noise_layout.bounds
        self.parameter_names = GEOMETRY_NAMES + self.noise_layout.names
        self.params = batman.TransitParams()
        self.params.t0 = 0.0
        self.params.per = self.period_days
        self.params.rp = 0.055
        self.params.a = 10.2
        self.params.inc = 86.0
        self.params.ecc = 0.0
        self.params.w = 90.0
        self.params.u = self.ld
        self.params.limb_dark = "quadratic"
        self.transit_models = [
            batman.TransitModel(
                self.params, item.x_days,
                supersample_factor=self.supersample_factor,
                exp_time=self.exposure_seconds / 86400.0,
            )
            for item in self.sectors
        ]

    def _build_sectors(self, event_frames):
        degree = int(self.branch["polynomial_degree"])
        combined = pd.concat(event_frames, ignore_index=True)
        if combined.duplicated(["sector", "cadenceno"]).any():
            raise RuntimeError("a full-frame cadence belongs to multiple events")
        result = []
        for sector in SECTORS:
            frame = combined.loc[combined["sector"] == sector].copy()
            frame.sort_values("time_btjd", inplace=True)
            frame.reset_index(drop=True, inplace=True)
            if frame.empty:
                raise RuntimeError("joint model has no cadences in sector {}".format(sector))
            event_ids = sorted(frame["event_id"].unique())
            design = np.zeros(
                (len(frame), len(event_ids) * (degree + 1)), dtype=np.float64,
            )
            for event_index, event_id in enumerate(event_ids):
                selected = frame["event_id"].eq(event_id).to_numpy()
                basis = phase5.polynomial_basis(
                    frame.loc[selected, "x_days"].to_numpy(np.float64), degree,
                ).astype(np.float64)
                start = event_index * (degree + 1)
                design[selected, start:start + degree + 1] = basis
            if np.linalg.matrix_rank(design) != design.shape[1]:
                raise RuntimeError("joint baseline design is rank deficient")
            item = JointSector(
                int(sector),
                frame["cadenceno"].to_numpy(np.int64),
                frame["time_btjd"].to_numpy(np.float64),
                frame["flux"].to_numpy(np.float64),
                frame["flux_err"].to_numpy(np.float64),
                frame["x_days"].to_numpy(np.float64),
                design,
            )
            if (not np.all(np.isfinite(np.column_stack((item.time, item.flux,
                                                        item.flux_err)))) or
                    np.any(item.flux_err <= 0.0) or np.any(np.diff(item.time) <= 0.0)):
                raise RuntimeError("joint sector arrays are invalid")
            result.append(item)
        if len(event_frames) != 16 or sum(len(item.time) for item in result) != len(combined):
            raise RuntimeError("joint model does not contain exactly 16 complete events")
        return tuple(result)

    @staticmethod
    def _empty_noise_sector(item):
        return base_noise.SectorData(
            item.sector, item.time, item.flux - 1.0, item.flux_err,
            np.empty((len(item.time), 0), dtype=np.float64),
        )

    def transit(self, geometry):
        rp_rs, a_rs, impact = np.asarray(geometry, dtype=np.float64)
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
            data.append(base_noise.SectorData(
                item.sector, item.time, item.flux - transit, item.flux_err,
                transit[:, None] * item.base_design,
            ))
        return tuple(data), transits

    def objective(self, parameters):
        values = np.asarray(parameters, dtype=np.float64)
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

    def recovered_geometry(self, parameters):
        return {
            name: float(value)
            for name, value in zip(GEOMETRY_NAMES, np.asarray(parameters, dtype=np.float64)[:3])
        }


def build_joint_model(branch, mask, events, decision):
    half_width = float(branch["window_hours"]) / 48.0
    frames = [phase5.event_rows(mask, event, half_width) for event in events]
    if any(frame.empty for frame in frames):
        raise RuntimeError("registered event window is empty")
    return Stage3JointModel(branch, frames, decision)


def _oot_data(branch, mask, events, phase2):
    inner_days = 0.75 * float(
        phase2["ephemeris_and_windows"]["t14_hours"]
    ) / 24.0
    parts = []
    for event in events:
        frame = phase5.event_rows(mask, event, float(branch["window_hours"]) / 48.0)
        frame = frame.loc[np.abs(frame["x_days"]) >= inner_days].copy()
        if frame.empty:
            raise RuntimeError("registered event has no OOT cadence")
        parts.append(frame)
    combined = pd.concat(parts, ignore_index=True)
    result = []
    degree = int(branch["polynomial_degree"])
    for sector in SECTORS:
        selected = combined.loc[combined["sector"] == sector].copy()
        selected.sort_values("time_btjd", inplace=True)
        selected.reset_index(drop=True, inplace=True)
        event_ids = sorted(selected["event_id"].unique())
        design = np.zeros((len(selected), len(event_ids) * (degree + 1)), dtype=np.float64)
        for event_index, event_id in enumerate(event_ids):
            rows = selected["event_id"].eq(event_id).to_numpy()
            basis = phase5.polynomial_basis(
                selected.loc[rows, "x_days"].to_numpy(np.float64), degree,
            ).astype(np.float64)
            start = event_index * (degree + 1)
            design[rows, start:start + degree + 1] = basis
        result.append(base_noise.SectorData(
            sector, selected["time_btjd"].to_numpy(np.float64),
            selected["flux"].to_numpy(np.float64) - 1.0,
            selected["flux_err"].to_numpy(np.float64), design,
        ))
    return tuple(result)


def _geometry_starts(bounds):
    center = np.array([0.055, 10.2, 0.73], dtype=np.float64)
    perturbation = np.array([0.02 * center[0], 0.02 * center[1], 0.02], dtype=np.float64)
    lower = np.asarray([item[0] for item in bounds], dtype=np.float64)
    upper = np.asarray([item[1] for item in bounds], dtype=np.float64)
    epsilon = np.maximum((upper - lower) * 1e-8, 1e-12)
    return [np.clip(value, lower + epsilon, upper - epsilon)
            for value in (center, center - perturbation, center + perturbation)]


def fit_joint_map(branch, mask, events, phase2, decision, laplace_seed,
                   require_stationarity=True):
    """Fit geometry MAP conditional on six-sector K3 OOT noise MAP."""
    model = build_joint_model(branch, mask, events, decision)
    oot = _oot_data(branch, mask, events, phase2)
    noise_map = noise.fit_pooled_map(
        oot, "K3_MATERN32_SECTOR", required_sector_count=6,
    )
    noise_obj = float(noise_map.objective) if noise_map.success else None
    if not noise_map.success:
        k0_map = noise.fit_pooled_map(oot, "K0_white", required_sector_count=6)
        if not k0_map.success:
            raise noise.NoiseModelError("both K3 and K0 OOT noise init failed")
        k3_params = np.zeros(21, dtype=np.float64)
        k3_params[0] = k0_map.parameters[0]
        k3_params[3:3 + 6] = k0_map.parameters[1:7]
        noise_params = k3_params
        noise_obj = float(k0_map.objective)
    else:
        noise_params = noise_map.parameters.copy()

    fixed_noise = noise_params
    geometry_bounds = model.geometry_bounds
    lower = np.asarray([l for l, _ in geometry_bounds], dtype=np.float64)
    upper = np.asarray([h for _, h in geometry_bounds], dtype=np.float64)
    span = upper - lower

    def conditional_objective(unit_geometry):
        geometry = lower + np.asarray(unit_geometry, dtype=np.float64) * span
        return model.objective(np.concatenate((geometry, fixed_noise)))

    starts = _geometry_starts(geometry_bounds)
    options = {"maxiter": 500, "ftol": 1e-12, "gtol": 1e-7,
               "finite_diff_rel_step": 1e-4}
    results = []
    for start in starts:
        unit_start = (start - lower) / span
        result = minimize(
            conditional_objective, unit_start, method="L-BFGS-B", jac="3-point",
            bounds=[(1e-8, 1.0 - 1e-8)] * len(unit_start), options=options,
        )
        final = lower + result.x * span
        actual = float(result.fun)
        results.append((result, final, actual, start))

    finite = [item for item in results if np.isfinite(item[2]) and item[2] < 1e100]
    successful = [item for item in finite if item[0].success]
    if not (successful or finite):
        raise noise.NoiseModelError("all registered geometry starts failed")

    best = min(successful or finite, key=lambda item: item[2])
    result, geometry, objective, initial = best
    parameters = np.concatenate((geometry, fixed_noise))
    converged = [item for item in results if item[0].success]
    objective_spread = (float(np.ptp([item[2] for item in converged]))
                        if len(converged) >= 2 else np.inf)
    unit_spread = (float(np.max(np.ptp(
        np.asarray([(item[1] - lower) / span for item in converged], dtype=np.float64),
        axis=0,
    ))) if len(converged) >= 2 else np.inf)
    stationary = bool(
        result.success and len(converged) == 3 and
        objective_spread < 1e-3 and unit_spread < 1e-3
    )
    attempts = [{
        "success": bool(item[0].success),
        "message": str(item[0].message),
        "iterations": int(item[0].nit),
        "objective": float(item[2]),
        "movement_norm": float(np.linalg.norm(item[1] - item[3])),
    } for item in results]

    if not stationary and require_stationarity:
        raise noise.NoiseModelError(
            "geometry MAP failed stationarity: successes={}, spread={}/{}, attempts={}".format(
                len(converged), objective_spread, unit_spread, attempts,
            )
        )
    if not stationary:
        return {
            "parameters": parameters,
            "parameter_names": model.parameter_names,
            "objective": objective,
            "success": bool(result.success),
            "stationary": False,
            "recovered_geometry": model.recovered_geometry(parameters),
            "attempts": attempts,
            "multistart_objective_spread": objective_spread,
            "multistart_unit_parameter_spread": unit_spread,
            "noise_start_objective": float(noise_obj),
            "noise_start_parameters": noise_params,
        }
        return model.objective(np.concatenate((geo, fixed_noise)))

    hessian = covariance = None
    hessian_attempts = []
    draw_diagnostics = {}
    intervals = {}
    try:
        hessian, covariance, hessian_attempts = phase5.finite_difference_hessian(
            geo_objective, geometry,
        )
        draws, draw_diagnostics = phase5.draw_laplace(
            geometry, covariance, geometry_bounds, 4096,
            int(laplace_seed), model.period_days,
        )
        intervals = {
            name: [float(v) for v in np.quantile(draws[:, i], [0.025, 0.16, 0.84, 0.975])]
            for i, name in enumerate(("rp_rs", "a_rs", "impact_parameter", "t14_hours"))
        }
    except Exception:
        pass
    return {
        "parameters": parameters,
        "parameter_names": model.parameter_names,
        "objective": objective,
        "success": bool(result.success),
        "stationary": True,
        "recovered_geometry": model.recovered_geometry(parameters),
        "intervals": intervals,
        "geometry_covariance": covariance,
        "hessian_attempts": hessian_attempts,
        "laplace_draw_diagnostics": draw_diagnostics,
        "multistart_objective_spread": objective_spread,
        "multistart_unit_parameter_spread": unit_spread,
        "noise_start_objective": float(noise_obj),
        "noise_start_parameters": noise_params,
        "attempts": attempts,
    }

