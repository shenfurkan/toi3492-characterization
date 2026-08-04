"""Phase-6 out-of-transit noise likelihood and predictive scoring core."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import OptimizeResult, minimize
from scipy.special import logsumexp

try:
    import celerite
    from celerite import terms
except ImportError as exc:  # pragma: no cover - depends on the runtime image
    raise ImportError("faz6_noise_core requires celerite 0.4.3") from exc


KERNEL_IDS = ("K0_white", "K1_ou", "K2_matern32", "K3_sho")
BASELINE_PRIOR_SIGMA = 0.01
OFFSET_PRIOR_SIGMA = 0.75
LOG_RATIO_BOUNDS = (-6.0, 2.0)
OFFSET_BOUNDS = (-3.0, 3.0)
TIMESCALE_MINUTES_BOUNDS = (4.0, 360.0)
BOUNDARY_FRACTION = 0.01
MINUTES_PER_DAY = 1440.0


class NoiseModelError(RuntimeError):
    """Raised when a covariance or likelihood calculation fails."""


def _require_float64(name: str, value: np.ndarray) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype != np.float64:
        raise TypeError("{} must have dtype float64".format(name))
    return array


@dataclass(frozen=True)
class SectorData:
    """One sector's sorted OOT/scoring vector and event-baseline design."""

    sector: int
    time: np.ndarray
    flux: np.ndarray
    flux_err: np.ndarray
    baseline_matrix: np.ndarray

    def __post_init__(self) -> None:
        time = _require_float64("time", self.time)
        flux = _require_float64("flux", self.flux)
        flux_err = _require_float64("flux_err", self.flux_err)
        design = _require_float64("baseline_matrix", self.baseline_matrix)
        if time.ndim != 1 or flux.ndim != 1 or flux_err.ndim != 1:
            raise ValueError("time, flux, and flux_err must be one-dimensional")
        if len(time) == 0 or len(flux) != len(time) or len(flux_err) != len(time):
            raise ValueError("sector vectors must be non-empty and have equal length")
        if design.ndim != 2 or design.shape[0] != len(time):
            raise ValueError("baseline_matrix must have shape (n_cadences, n_coefficients)")
        if not all(np.all(np.isfinite(x)) for x in (time, flux, flux_err, design)):
            raise ValueError("sector arrays must contain only finite values")
        if np.any(flux_err <= 0.0):
            raise ValueError("flux_err must be strictly positive")
        if np.any(np.diff(time) <= 0.0):
            raise ValueError("time must be strictly increasing")
        if not isinstance(self.sector, (int, np.integer)):
            raise TypeError("sector must be an integer")

    @property
    def error_scale(self) -> float:
        """Frozen hierarchy scale: median propagated sector uncertainty."""

        return float(np.median(self.flux_err))


@dataclass(frozen=True)
class MarginalLikelihood:
    """Gaussian baseline-marginal likelihood and coefficient posterior mean."""

    log_likelihood: float
    baseline_posterior_mean: np.ndarray


@dataclass(frozen=True)
class ConditionalComponents:
    """Posterior mean components and corrected residual at observed times."""

    baseline_mean: np.ndarray
    gp_mean: np.ndarray
    corrected_residual: np.ndarray


class _DiagonalCovariance:
    def __init__(self, variance: np.ndarray):
        if np.any(~np.isfinite(variance)) or np.any(variance <= 0.0):
            raise NoiseModelError("diagonal covariance is not positive and finite")
        self._variance = variance

    def apply_inverse(self, rhs: np.ndarray) -> np.ndarray:
        return rhs / self._variance[:, None]

    @property
    def log_determinant(self) -> float:
        return float(np.sum(np.log(self._variance)))


class _CeleriteCovariance:
    def __init__(self, time: np.ndarray, yerr: np.ndarray, term: terms.Term):
        self._gp = celerite.GP(term)
        try:
            self._gp.compute(time, yerr=yerr, check_sorted=True)
        except Exception as exc:
            raise NoiseModelError("celerite covariance factorization failed") from exc

    def apply_inverse(self, rhs: np.ndarray) -> np.ndarray:
        """Apply celerite's inverse once to a matrix RHS."""

        if rhs.ndim != 2:
            raise ValueError("celerite inverse RHS must be a matrix")
        try:
            result = np.asarray(self._gp.apply_inverse(rhs), dtype=np.float64)
        except Exception as exc:
            raise NoiseModelError("celerite matrix inverse application failed") from exc
        if result.shape != rhs.shape or np.any(~np.isfinite(result)):
            raise NoiseModelError("celerite returned an invalid matrix inverse result")
        return result

    @property
    def log_determinant(self) -> float:
        try:
            value = float(self._gp.solver.log_determinant())
        except Exception as exc:
            raise NoiseModelError("celerite log determinant failed") from exc
        if not np.isfinite(value):
            raise NoiseModelError("celerite returned a non-finite log determinant")
        return value


def build_kernel_term(kernel_id: str, amplitude: float, timescale_minutes: float):
    """Build a preregistered celerite term; K0 has no correlated term."""

    if kernel_id not in KERNEL_IDS:
        raise ValueError("unknown kernel_id: {}".format(kernel_id))
    if kernel_id == "K0_white":
        return None
    if not np.isfinite(amplitude) or amplitude <= 0.0:
        raise ValueError("amplitude must be positive and finite")
    if not np.isfinite(timescale_minutes) or timescale_minutes <= 0.0:
        raise ValueError("timescale_minutes must be positive and finite")
    timescale_days = timescale_minutes / MINUTES_PER_DAY
    if kernel_id == "K1_ou":
        return terms.RealTerm(log_a=2.0 * np.log(amplitude),
                              log_c=-np.log(timescale_days))
    if kernel_id == "K2_matern32":
        return terms.Matern32Term(log_sigma=np.log(amplitude),
                                  log_rho=np.log(timescale_days), eps=0.01)
    q = 1.0 / np.sqrt(2.0)
    omega0 = 1.0 / timescale_days
    # celerite's SHO has k(0) = S0 * omega0 * Q.
    s0 = amplitude * amplitude / (omega0 * q)
    return terms.SHOTerm(log_S0=np.log(s0), log_Q=np.log(q),
                         log_omega0=np.log(omega0))


def marginal_log_likelihood(
    data: SectorData,
    kernel_id: str,
    jitter: float,
    amplitude: Optional[float] = None,
    timescale_minutes: Optional[float] = None,
    baseline_prior_sigma: float = BASELINE_PRIOR_SIGMA,
) -> MarginalLikelihood:
    """Exactly marginalize the Gaussian event baseline with Woodbury."""

    if not np.isfinite(jitter) or jitter <= 0.0:
        raise ValueError("jitter must be positive and finite")
    if not np.isfinite(baseline_prior_sigma) or baseline_prior_sigma <= 0.0:
        raise ValueError("baseline_prior_sigma must be positive and finite")
    if kernel_id == "K0_white":
        covariance = _DiagonalCovariance(data.flux_err ** 2 + jitter ** 2)
    else:
        if amplitude is None or timescale_minutes is None:
            raise ValueError("complex kernels require amplitude and timescale_minutes")
        term = build_kernel_term(kernel_id, amplitude, timescale_minutes)
        total_error = np.sqrt(data.flux_err ** 2 + jitter ** 2)
        covariance = _CeleriteCovariance(data.time, total_error, term)

    design = data.baseline_matrix
    rhs = np.column_stack((data.flux, design))
    solved = covariance.apply_inverse(rhs)
    cinv_y = solved[:, 0]
    n_coeff = design.shape[1]
    y_quad = float(np.dot(data.flux, cinv_y))
    log_det = covariance.log_determinant

    if n_coeff:
        cinv_design = solved[:, 1:]
        precision = (design.T @ cinv_design)
        precision.flat[::n_coeff + 1] += baseline_prior_sigma ** -2
        linear = design.T @ cinv_y
        try:
            posterior_mean = np.linalg.solve(precision, linear)
            sign, log_det_precision = np.linalg.slogdet(precision)
        except np.linalg.LinAlgError as exc:
            raise NoiseModelError("baseline posterior precision is singular") from exc
        if sign <= 0 or np.any(~np.isfinite(posterior_mean)):
            raise NoiseModelError("baseline posterior precision is not positive definite")
        y_quad -= float(np.dot(linear, posterior_mean))
        log_det += log_det_precision + 2.0 * n_coeff * np.log(baseline_prior_sigma)
    else:
        posterior_mean = np.empty(0, dtype=np.float64)

    value = -0.5 * (y_quad + log_det + len(data.time) * np.log(2.0 * np.pi))
    if not np.isfinite(value):
        raise NoiseModelError("marginal log likelihood is non-finite")
    return MarginalLikelihood(float(value), posterior_mean)


def conditional_components(
    data: SectorData,
    kernel_id: str,
    jitter: float,
    amplitude: Optional[float] = None,
    timescale_minutes: Optional[float] = None,
    baseline_prior_sigma: float = BASELINE_PRIOR_SIGMA,
) -> ConditionalComponents:
    """Return baseline and GP posterior means for residual diagnostics."""

    marginal = marginal_log_likelihood(
        data,
        kernel_id,
        jitter,
        amplitude,
        timescale_minutes,
        baseline_prior_sigma,
    )
    baseline = data.baseline_matrix @ marginal.baseline_posterior_mean
    after_baseline = data.flux - baseline
    if kernel_id == "K0_white":
        gp_mean = np.zeros(len(data.time), dtype=np.float64)
    else:
        term = build_kernel_term(kernel_id, float(amplitude), float(timescale_minutes))
        gp = celerite.GP(term)
        total_error = np.sqrt(data.flux_err ** 2 + jitter ** 2)
        gp.compute(data.time, yerr=total_error, check_sorted=True)
        gp_mean = np.asarray(
            gp.predict(after_baseline, data.time, return_cov=False),
            dtype=np.float64,
        ).reshape(-1)
    corrected = after_baseline - gp_mean
    if np.any(~np.isfinite(corrected)):
        raise NoiseModelError("conditional residual is non-finite")
    return ConditionalComponents(baseline, gp_mean, corrected)


@dataclass(frozen=True)
class ParameterLayout:
    """Names and bounds for one five-sector pooled fit."""

    kernel_id: str
    sector_ids: Tuple[int, ...]
    names: Tuple[str, ...]
    bounds: Tuple[Tuple[float, float], ...]


def parameter_layout(kernel_id: str, sectors: Sequence[SectorData]) -> ParameterLayout:
    """Construct the protocol-fixed pooled parameter vector layout."""

    if kernel_id not in KERNEL_IDS:
        raise ValueError("unknown kernel_id: {}".format(kernel_id))
    if any(not isinstance(data, SectorData) for data in sectors):
        raise TypeError("sectors must contain only SectorData instances")
    sector_ids = tuple(int(data.sector) for data in sectors)
    if len(set(sector_ids)) != len(sector_ids):
        raise ValueError("training sector identifiers must be unique")
    names: List[str] = ["mu_jitter"]
    bounds: List[Tuple[float, float]] = [LOG_RATIO_BOUNDS]
    if kernel_id != "K0_white":
        names.extend(("mu_amplitude", "log_timescale_minutes"))
        bounds.extend((LOG_RATIO_BOUNDS,
                       tuple(np.log(TIMESCALE_MINUTES_BOUNDS))))
    names.extend("delta_jitter_s{}".format(s) for s in sector_ids)
    bounds.extend([OFFSET_BOUNDS] * len(sector_ids))
    if kernel_id != "K0_white":
        names.extend("delta_amplitude_s{}".format(s) for s in sector_ids)
        bounds.extend([OFFSET_BOUNDS] * len(sector_ids))
    return ParameterLayout(kernel_id, sector_ids, tuple(names), tuple(bounds))


def pooled_map_objective(
    parameters: np.ndarray,
    training_sectors: Sequence[SectorData],
    layout: ParameterLayout,
) -> float:
    """Negative pooled marginal log likelihood plus fixed offset penalty."""

    values = np.asarray(parameters, dtype=np.float64)
    if values.shape != (len(layout.names),) or np.any(~np.isfinite(values)):
        raise ValueError("parameters have the wrong shape or contain non-finite values")
    if tuple(int(x.sector) for x in training_sectors) != layout.sector_ids:
        raise ValueError("training sectors do not match the parameter layout")

    complex_kernel = layout.kernel_id != "K0_white"
    cursor = 1
    mu_jitter = values[0]
    if complex_kernel:
        mu_amplitude = values[1]
        timescale_minutes = float(np.exp(values[2]))
        cursor = 3
    jitter_offsets = values[cursor:cursor + len(training_sectors)]
    cursor += len(training_sectors)
    amplitude_offsets = values[cursor:] if complex_kernel else np.empty(0)

    log_likelihood = 0.0
    for index, data in enumerate(training_sectors):
        jitter = data.error_scale * np.exp(mu_jitter + jitter_offsets[index])
        amplitude = None
        if complex_kernel:
            amplitude = data.error_scale * np.exp(
                mu_amplitude + amplitude_offsets[index])
        result = marginal_log_likelihood(
            data, layout.kernel_id, jitter, amplitude, timescale_minutes
            if complex_kernel else None)
        log_likelihood += result.log_likelihood
    offsets = np.concatenate((jitter_offsets, amplitude_offsets))
    penalty = 0.5 * float(np.dot(offsets, offsets)) / OFFSET_PRIOR_SIGMA ** 2
    return float(-log_likelihood + penalty)


def _registered_starts(layout: ParameterLayout) -> List[np.ndarray]:
    n_sector = len(layout.sector_ids)
    if layout.kernel_id == "K0_white":
        ratios = (0.1, 0.5, 1.5)
        return [np.concatenate(([np.log(ratio)], np.zeros(n_sector)))
                for ratio in ratios]
    settings = ((0.1, 0.3, 20.0), (0.5, 1.0, 60.0),
                (1.0, 2.0, 180.0))
    return [np.concatenate((np.log(setting), np.zeros(2 * n_sector)))
            for setting in settings]


@dataclass(frozen=True)
class BoundaryDiagnostic:
    name: str
    value: float
    lower: float
    upper: float
    distance_fraction: float
    at_boundary: bool


def parameter_boundary_diagnostics(
    parameters: np.ndarray,
    layout: ParameterLayout,
    boundary_fraction: float = BOUNDARY_FRACTION,
) -> Tuple[BoundaryDiagnostic, ...]:
    """Report each parameter's fractional distance from its nearest bound."""

    values = np.asarray(parameters, dtype=np.float64)
    if values.shape != (len(layout.names),):
        raise ValueError("parameters do not match layout")
    if not 0.0 <= boundary_fraction < 0.5:
        raise ValueError("boundary_fraction must be in [0, 0.5)")
    diagnostics = []
    for name, value, (lower, upper) in zip(layout.names, values, layout.bounds):
        fraction = min(value - lower, upper - value) / (upper - lower)
        diagnostics.append(BoundaryDiagnostic(
            name, float(value), float(lower), float(upper), float(fraction),
            bool(fraction <= boundary_fraction)))
    return tuple(diagnostics)


@dataclass(frozen=True)
class PooledMapFit:
    """Best protocol MAP fit and all optimizer attempts."""

    kernel_id: str
    parameters: np.ndarray
    objective: float
    layout: ParameterLayout
    optimizer_results: Tuple[OptimizeResult, ...]
    retried: bool
    boundary_diagnostics: Tuple[BoundaryDiagnostic, ...]

    @property
    def success(self) -> bool:
        return bool(np.isfinite(self.objective) and
                    any(result.success for result in self.optimizer_results))


def fit_pooled_map(
    training_sectors: Sequence[SectorData],
    kernel_id: str,
    required_sector_count: int = 5,
) -> PooledMapFit:
    """Fit the registered pooled model with frozen three-start L-BFGS-B."""

    sectors = tuple(training_sectors)
    if len(sectors) != required_sector_count:
        raise ValueError(
            "Phase-6 pooled MAP requires exactly {} sectors".format(
                required_sector_count
            )
        )
    layout = parameter_layout(kernel_id, sectors)
    starts = _registered_starts(layout)
    options = {"maxiter": 300, "ftol": 1e-10, "gtol": 1e-6,
               "finite_diff_rel_step": 1e-4}

    def objective(x: np.ndarray) -> float:
        try:
            return pooled_map_objective(x, sectors, layout)
        except (NoiseModelError, FloatingPointError, OverflowError, ValueError):
            return 1e100

    results = [minimize(objective, start, method="L-BFGS-B", jac="2-point",
                        bounds=layout.bounds, options=options)
               for start in starts]
    finite_indices = [i for i, result in enumerate(results)
                      if np.isfinite(result.fun) and result.fun < 1e100]
    best_index = min(finite_indices, key=lambda i: results[i].fun) \
        if finite_indices else 0
    retried = not results[best_index].success
    if retried:
        retry_options = dict(options)
        retry_options["maxiter"] = 600
        retry = minimize(objective, starts[best_index], method="L-BFGS-B",
                         jac="2-point", bounds=layout.bounds,
                         options=retry_options)
        results.append(retry)

    valid_results = [result for result in results
                     if np.isfinite(result.fun) and result.fun < 1e100]
    if not valid_results:
        messages = "; ".join(str(result.message) for result in results)
        raise NoiseModelError("all pooled MAP attempts failed: {}".format(messages))
    converged_results = [result for result in valid_results if result.success]
    best = min(converged_results or valid_results, key=lambda result: result.fun)
    parameters = np.asarray(best.x, dtype=np.float64)
    return PooledMapFit(
        kernel_id, parameters, float(best.fun), layout, tuple(results), retried,
        parameter_boundary_diagnostics(parameters, layout))


def held_sector_joint_log_predictive_density(
    held_sector: SectorData,
    fit: PooledMapFit,
) -> float:
    """Integrate held jitter/amplitude offsets with fixed 5-node GH rules."""

    nodes, weights = np.polynomial.hermite.hermgauss(5)
    offsets = np.sqrt(2.0) * OFFSET_PRIOR_SIGMA * nodes
    log_weights = np.log(weights) - 0.5 * np.log(np.pi)
    values = fit.parameters
    mu_jitter = values[0]
    complex_kernel = fit.kernel_id != "K0_white"
    if complex_kernel:
        mu_amplitude = values[1]
        timescale_minutes = float(np.exp(values[2]))

    components = []
    for i, jitter_offset in enumerate(offsets):
        jitter = held_sector.error_scale * np.exp(mu_jitter + jitter_offset)
        if not complex_kernel:
            likelihood = marginal_log_likelihood(
                held_sector, fit.kernel_id, jitter).log_likelihood
            components.append(log_weights[i] + likelihood)
            continue
        for j, amplitude_offset in enumerate(offsets):
            amplitude = held_sector.error_scale * np.exp(
                mu_amplitude + amplitude_offset)
            likelihood = marginal_log_likelihood(
                held_sector, fit.kernel_id, jitter, amplitude,
                timescale_minutes).log_likelihood
            components.append(log_weights[i] + log_weights[j] + likelihood)
    result = float(logsumexp(components))
    if not np.isfinite(result):
        raise NoiseModelError("held-sector predictive density is non-finite")
    return result
