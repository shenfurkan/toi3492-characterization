"""Stage-3 Matérn-3/2 noise core with sector-partially-pooled timescales.

Extends the Phase-6 noise core. Only four functions change:
  parameter_layout  — adds delta_timescale_sXX and mu_timescale
  pooled_map_objective — adds timescale offset penalty
  _registered_starts — adds timescale starts
  held_sector_joint_log_predictive_density — 3D quadrature (jitter+amp+timescale)
"""

import math
from typing import List, Sequence, Tuple, Optional

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from faz6_noise_core import (
    KERNEL_IDS as BASE_KERNEL_IDS,
    BASELINE_PRIOR_SIGMA,
    OFFSET_PRIOR_SIGMA,
    LOG_RATIO_BOUNDS,
    OFFSET_BOUNDS,
    TIMESCALE_MINUTES_BOUNDS,
    BOUNDARY_FRACTION,
    MINUTES_PER_DAY,
    NoiseModelError,
    SectorData,
    MarginalLikelihood,
    ConditionalComponents,
    _DiagonalCovariance,
    _CeleriteCovariance,
    build_kernel_term,
    marginal_log_likelihood,
    conditional_components,
    ParameterLayout,
    BoundaryDiagnostic,
    PooledMapFit,
    parameter_boundary_diagnostics,
    fit_pooled_map as _original_fit_pooled_map,
    held_sector_joint_log_predictive_density as _original_held_prediction,
)

KERNEL_IDS = BASE_KERNEL_IDS + ("K3_MATERN32_SECTOR",)
TIMESCALE_UPPER_MINUTES = 780.0
LOG_TIMESCALE_MINUTES_MIN = math.log(TIMESCALE_MINUTES_BOUNDS[0])
LOG_TIMESCALE_MINUTES_MAX = math.log(TIMESCALE_UPPER_MINUTES)


def _valid_timescale_offset_bounds(mu_timescale: float) -> Tuple[float, float]:
    """Return supported held-sector timescale offsets for a fitted mean."""
    return (
        max(OFFSET_BOUNDS[0], LOG_TIMESCALE_MINUTES_MIN - mu_timescale),
        min(OFFSET_BOUNDS[1], LOG_TIMESCALE_MINUTES_MAX - mu_timescale),
    )


def central_unit_gradient(objective, values, relative_step=1e-4):
    """Bounded central finite difference in unit-hypercube coordinates."""
    point = np.asarray(values, dtype=np.float64)
    gradient = np.empty_like(point)
    lower, upper = 1e-8, 1.0 - 1e-8
    for index, value in enumerate(point):
        step = relative_step * max(abs(value), 1.0)
        plus_value = min(upper, value + step)
        minus_value = max(lower, value - step)
        if plus_value <= minus_value:
            gradient[index] = 0.0
            continue
        plus = point.copy()
        minus = point.copy()
        plus[index] = plus_value
        minus[index] = minus_value
        gradient[index] = ((objective(plus) - objective(minus)) /
                           (plus_value - minus_value))
    return gradient


def parameter_layout(kernel_id: str, sectors: Sequence[SectorData]) -> ParameterLayout:
    if kernel_id not in KERNEL_IDS:
        raise ValueError("unknown kernel_id: {}".format(kernel_id))

    sector_ids = tuple(int(data.sector) for data in sectors)
    if len(set(sector_ids)) != len(sector_ids):
        raise ValueError("training sector identifiers must be unique")

    names: List[str] = ["mu_jitter"]
    bounds: List[Tuple[float, float]] = [LOG_RATIO_BOUNDS]

    is_complex = kernel_id != "K0_white"
    if is_complex:
        names.extend(("mu_amplitude", "mu_timescale"))
        bounds.extend((LOG_RATIO_BOUNDS,
                       (math.log(TIMESCALE_MINUTES_BOUNDS[0]),
                        math.log(TIMESCALE_UPPER_MINUTES))))

    names.extend("delta_jitter_s{}".format(s) for s in sector_ids)
    bounds.extend([OFFSET_BOUNDS] * len(sector_ids))

    if is_complex:
        names.extend("delta_amplitude_s{}".format(s) for s in sector_ids)
        bounds.extend([OFFSET_BOUNDS] * len(sector_ids))

    if kernel_id == "K3_MATERN32_SECTOR":
        names.extend("delta_timescale_s{}".format(s) for s in sector_ids)
        bounds.extend([OFFSET_BOUNDS] * len(sector_ids))

    return ParameterLayout(kernel_id, sector_ids, tuple(names), tuple(bounds))


def _registered_starts(layout: ParameterLayout) -> List[np.ndarray]:
    n_sector = len(layout.sector_ids)
    if layout.kernel_id == "K0_white":
        return [np.concatenate(([math.log(ratio)], np.zeros(n_sector)))
                for ratio in (0.1, 0.5, 1.5)]

    if layout.kernel_id == "K3_MATERN32_SECTOR":
        settings = (
            (0.5, 1.0, math.log(160.0)),
            (1.0, 0.5, math.log(80.0)),
            (0.5, 0.5, math.log(320.0)),
        )
        starts = []
        for j_ratio, a_ratio, mu_tau in settings:
            vec = [math.log(j_ratio), math.log(a_ratio), mu_tau]
            vec.extend(np.zeros(3 * n_sector))
            starts.append(np.asarray(vec, dtype=np.float64))
        return starts

    return [np.concatenate((np.log(setting), np.zeros(2 * n_sector)))
            for setting in ((0.1, 0.3, 20.0), (0.5, 1.0, 60.0), (1.0, 2.0, 180.0))]


def pooled_map_objective(
    parameters: np.ndarray,
    training_sectors: Sequence[SectorData],
    layout: ParameterLayout,
) -> float:
    values = np.asarray(parameters, dtype=np.float64)
    if values.shape != (len(layout.names),) or np.any(~np.isfinite(values)):
        return 1e100

    for idx, (lo, hi) in enumerate(layout.bounds):
        if not lo < values[idx] < hi:
            return 1e100

    n_sec = len(training_sectors)
    mu_jitter = values[0]
    cursor = 1

    if layout.kernel_id != "K0_white":
        mu_amplitude = values[cursor]
        mu_timescale = values[cursor + 1]
        cursor += 2

    jitter_offsets = values[cursor:cursor + n_sec]
    cursor += n_sec

    if layout.kernel_id != "K0_white":
        amp_offsets = values[cursor:cursor + n_sec]
        cursor += n_sec
    else:
        amp_offsets = np.empty(0)

    if layout.kernel_id == "K3_MATERN32_SECTOR":
        tau_offsets = values[cursor:cursor + n_sec]
    else:
        tau_offsets = np.empty(0)

    log_likelihood = 0.0
    for idx, data in enumerate(training_sectors):
        jitter = data.error_scale * math.exp(mu_jitter + jitter_offsets[idx])
        amplitude = None
        timescale = None
        if layout.kernel_id != "K0_white":
            amplitude = data.error_scale * math.exp(mu_amplitude + amp_offsets[idx])
            log_tau = mu_timescale + (tau_offsets[idx]
                                       if len(tau_offsets) else 0.0)
            if not LOG_TIMESCALE_MINUTES_MIN <= log_tau <= LOG_TIMESCALE_MINUTES_MAX:
                return 1e100
            timescale = math.exp(log_tau)
        result = marginal_log_likelihood(
            data, "K2_matern32" if layout.kernel_id == "K3_MATERN32_SECTOR"
            else layout.kernel_id,
            jitter, amplitude, timescale,
        )
        log_likelihood += result.log_likelihood

    offsets = np.concatenate((jitter_offsets, amp_offsets, tau_offsets))
    if len(offsets):
        penalty = 0.5 * float(np.dot(offsets, offsets)) / OFFSET_PRIOR_SIGMA ** 2
    else:
        penalty = 0.0
    return float(-log_likelihood + penalty)


def _fit_pooled_map(
    training_sectors: Sequence[SectorData],
    kernel_id: str,
    required_sector_count: int = 5,
) -> PooledMapFit:
    sectors = tuple(training_sectors)
    if len(sectors) != required_sector_count:
        raise ValueError("expected {} training sectors".format(required_sector_count))
    layout = parameter_layout(kernel_id, sectors)

    starts = _registered_starts(layout)

    options = {"maxiter": 300, "ftol": 1e-8, "disp": False}

    def objective(x):
        try:
            return pooled_map_objective(x, sectors, layout)
        except (NoiseModelError, FloatingPointError, OverflowError, ValueError):
            return 1e100

    lower = np.asarray([bound[0] for bound in layout.bounds], dtype=np.float64)
    upper = np.asarray([bound[1] for bound in layout.bounds], dtype=np.float64)
    span = upper - lower
    objective_offset = float(objective(starts[0]))

    def optimize_start(start):
        unit_start = (np.asarray(start, dtype=np.float64) - lower) / span

        def scaled_objective(unit_parameters):
            physical = lower + np.asarray(unit_parameters, dtype=np.float64) * span
            return objective(physical) - objective_offset

        result = minimize(
            scaled_objective, unit_start, method="SLSQP",
            jac=lambda value: central_unit_gradient(scaled_objective, value),
            bounds=[(1e-8, 1.0 - 1e-8)] * len(unit_start), options=options,
        )
        result.x = lower + np.asarray(result.x, dtype=np.float64) * span
        result.fun = float(result.fun + objective_offset)
        return result

    results = [optimize_start(start) for start in starts]
    finite = [i for i, r in enumerate(results)
              if np.isfinite(r.fun) and r.fun < 1e100]
    best_index = min(finite, key=lambda i: results[i].fun) if finite else 0
    retried = not results[best_index].success
    if retried:
        retry_options = dict(options)
        retry_options["maxiter"] = 600
        retry_start = starts[best_index]
        unit_start = (np.asarray(retry_start, dtype=np.float64) - lower) / span

        def scaled_retry(unit_parameters):
            physical = lower + np.asarray(unit_parameters, dtype=np.float64) * span
            return objective(physical) - objective_offset

        retry = minimize(
            scaled_retry, unit_start, method="SLSQP",
            jac=lambda value: central_unit_gradient(scaled_retry, value),
            bounds=[(1e-8, 1.0 - 1e-8)] * len(unit_start),
            options=retry_options,
        )
        retry.x = lower + np.asarray(retry.x, dtype=np.float64) * span
        retry.fun = float(retry.fun + objective_offset)
        results.append(retry)

    valid = [r for r in results if np.isfinite(r.fun) and r.fun < 1e100]
    if not valid:
        messages = "; ".join(str(r.message) for r in results)
        raise NoiseModelError("all pooled MAP starts failed: {}".format(messages))
    converged = [r for r in valid if r.success]
    best = min(converged or valid, key=lambda r: r.fun)
    best_params = np.asarray(best.x, dtype=np.float64)
    best_obj = float(best.fun)

    boundary = parameter_boundary_diagnostics(best_params, layout)
    return PooledMapFit(
        kernel_id, best_params, best_obj, layout, tuple(results), retried, boundary,
    )


def fit_pooled_map(
    training_sectors: Sequence[SectorData],
    kernel_id: str,
    required_sector_count: int = 5,
) -> PooledMapFit:
    if kernel_id in ("K0_white", "K1_ou", "K2_matern32", "K3_sho"):
        return _original_fit_pooled_map(
            training_sectors, kernel_id, required_sector_count,
        )
    return _fit_pooled_map(training_sectors, kernel_id, required_sector_count)


def _accumulate(max_val, weight, log_val):
    if not np.isfinite(log_val):
        return max_val
    if max_val is None:
        return (log_val, weight)
    prev_max, prev_sum = max_val
    if log_val > prev_max:
        return (log_val, prev_sum * math.exp(prev_max - log_val) + weight)
    return (prev_max, prev_sum + weight * math.exp(log_val - prev_max))


def _finalize(total):
    if total is None:
        return -np.inf
    max_val, weighted_sum = total
    if weighted_sum <= 0.0:
        return -np.inf
    return float(max_val + math.log(weighted_sum))


def held_sector_joint_log_predictive_density(
    held_sector: SectorData,
    fit: PooledMapFit,
    nodes: int = 5,
) -> float:
    if fit.layout.kernel_id != "K3_MATERN32_SECTOR":
        return _original_held_prediction(held_sector, fit)

    gh_nodes, gh_weights = np.polynomial.hermite.hermgauss(nodes)
    offsets = np.sqrt(2.0) * OFFSET_PRIOR_SIGMA * gh_nodes
    log_weights = np.log(gh_weights) - 0.5 * np.log(math.pi)

    mu_jitter = fit.parameters[0]
    mu_amplitude = fit.parameters[1]
    mu_timescale = fit.parameters[2]
    tau_offset_lo, tau_offset_hi = _valid_timescale_offset_bounds(mu_timescale)
    valid_tau = (offsets >= tau_offset_lo) & (offsets <= tau_offset_hi)
    if not np.any(valid_tau):
        raise NoiseModelError("no valid held-sector timescale quadrature nodes")
    tau_offsets = offsets[valid_tau]
    tau_log_weights = log_weights[valid_tau]
    tau_log_weights -= logsumexp(tau_log_weights)

    components = []
    for i, j_off in enumerate(offsets):
        jitter = held_sector.error_scale * math.exp(mu_jitter + j_off)
        for j, a_off in enumerate(offsets):
            amplitude = held_sector.error_scale * math.exp(mu_amplitude + a_off)
            for k, t_off in enumerate(tau_offsets):
                timescale = math.exp(mu_timescale + t_off)
                ll = marginal_log_likelihood(
                    held_sector, "K2_matern32",
                    jitter, amplitude, timescale,
                ).log_likelihood
                components.append(
                    log_weights[i] + log_weights[j] + tau_log_weights[k] + ll
                )
    return float(logsumexp(components))
