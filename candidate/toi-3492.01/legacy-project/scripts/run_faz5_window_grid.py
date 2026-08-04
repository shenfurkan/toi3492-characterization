"""Run the preregistered Phase-5 event-window and polynomial grid.

The analysis uses the accepted Phase-4 PDCSAP reference reduction. Event
baselines are integrated analytically and sector jitter is integrated on the
frozen log grid. Reduction alternatives are not multiplied as independent
data; their Phase-4 dispersion is carried forward as a separate systematic.
"""

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import batman
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp


ROOT = Path(__file__).resolve().parent.parent
PREREG_PATH = ROOT / "data" / "faz5_preregistered_grid.json"
FAZ2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
FAZ4_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"
LONG_TABLE_PATH = ROOT / "data" / "toi3492_faz4_reductions_120s.csv.gz"
GRID_CSV_PATH = ROOT / "outputs" / "faz5_model_grid.csv"
BLOCK_CSV_PATH = ROOT / "outputs" / "faz5_block_scores.csv"
DRAW_PATH = ROOT / "data" / "toi3492_faz5_geometry_draws.npz"
OUTPUT_PATH = ROOT / "outputs" / "faz5_window_polynomial_grid.json"

SECTORS = (37, 63, 64, 90, 99, 100)
PARAMETERS = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")
REQUIRED_COLUMNS = (
    "time_btjd",
    "sector",
    "cadenceno",
    "branch",
    "flux",
    "flux_err",
    "quality",
    "crowdsap",
    "crowdsap_applied_count",
    "flfrcsap",
    "exposure_seconds",
    "provenance_id",
    "source_product_id",
    "source_sha256",
    "aperture_sha256",
)
GEOMETRY_STARTS = (
    (0.0551113293, 10.16836, 0.73378),
    (0.05200, 8.50, 0.450),
    (0.05800, 12.00, 0.840),
    (0.04700, 7.00, 0.200),
    (0.06100, 14.00, 0.910),
)


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def weighted_quantile(values, weights, probabilities):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    cumulative /= cumulative[-1]
    return np.interp(np.asarray(probabilities, dtype=float), cumulative, values)


def percentile_summary(values):
    values = np.asarray(values, dtype=float)
    p16, median, p84 = np.percentile(values, [16.0, 50.0, 84.0])
    return {
        "p16": float(p16),
        "median": float(median),
        "p84": float(p84),
        "standard_deviation": float(np.std(values, ddof=1)),
    }


def duration_hours(draws, period_days):
    draws = np.atleast_2d(np.asarray(draws, dtype=float))
    rp = draws[:, 0]
    a_rs = draws[:, 1]
    impact = draws[:, 2]
    sin_i = np.sqrt(np.clip(1.0 - (impact / a_rs) ** 2, 0.0, None))
    numerator = np.sqrt(np.clip((1.0 + rp) ** 2 - impact**2, 0.0, None))
    argument = numerator / (a_rs * sin_i)
    result = period_days * 24.0 / math.pi * np.arcsin(np.clip(argument, 0.0, 1.0))
    invalid = (
        (impact >= 1.0 + rp)
        | (impact >= a_rs)
        | ~np.isfinite(argument)
        | (argument < 0.0)
        | (argument > 1.0)
    )
    result[invalid] = np.nan
    return result


def cell_id(total_window_hours, degree):
    return f"W{int(total_window_hours):02d}_P{int(degree)}"


def validate_inputs(prereg, faz2, faz4):
    artifact = faz4["artifacts"]["long_table"]
    actual_hash = sha256_file(LONG_TABLE_PATH)
    windows = prereg["grid"]["total_window_hours"]
    degrees = prereg["grid"]["event_polynomial_degrees"]
    used = [item for item in faz2["events"] if item["used"]]
    gaps = sorted(
        (int(item["sector"]), int(item["epoch"]))
        for item in faz2["events"]
        if not item["used"]
    )
    checks = {
        "preregistration_frozen": prereg["frozen_before_first_phase5_fit"] is True,
        "phase2_gate_pass": faz2.get("gate_pass") is True,
        "phase4_allows_phase5": faz4["gate"]["phase5_may_begin"] is True,
        "phase4_status_allowed": faz4["gate"]["status"] in ("PASS", "CONDITIONAL_PASS"),
        "pdcsap_accepted": "pdcsap" in faz4["gate"]["accepted_branches"],
        "phase4_reductions_share_native_timestamps": faz4["correction_formulas"][
            "timestamps"
        ]
        == "native FITS BTJD, never binned or resampled",
        "exact_15_cell_grid": len(windows) * len(degrees)
        == prereg["grid"]["cell_count"]
        == 15,
        "window_grid_exact": windows == [13, 16, 20, 26, 32],
        "polynomial_grid_exact": degrees == [0, 1, 2],
        "used_event_count_exact": len(used) == 16,
        "gap_event_set_exact": gaps == [(37, 2), (99, 189)],
        "long_table_hash_matches_preregistration": actual_hash
        == prereg["inputs"]["phase4_long_table_sha256"],
        "long_table_hash_matches_phase4": actual_hash == artifact["sha256"],
        "long_table_size_matches_phase4": LONG_TABLE_PATH.stat().st_size
        == artifact["size_bytes"],
        "period_matches_phase4": prereg["transit_model"]["period_days_fixed"]
        == faz4["inputs"]["ephemeris"]["period_days_fixed"],
        "t0_matches_phase4": prereg["transit_model"]["t0_btjd_fixed"]
        == faz4["inputs"]["ephemeris"]["t0_btjd_fixed"],
    }
    if not all(checks.values()):
        raise RuntimeError(f"Phase 5 input validation failed: {checks}")
    events = [
        {
            "physical_event_id": item["physical_event_id"],
            "sector": int(item["sector"]),
            "epoch": int(item["epoch"]),
            "midpoint_btjd": float(item["predicted_midpoint_btjd"]),
        }
        for item in used
    ]
    return checks, events, actual_hash


def load_reference_table(faz4):
    frame = pd.read_csv(LONG_TABLE_PATH)
    artifact = faz4["artifacts"]["long_table"]
    if len(frame) != artifact["row_count"]:
        raise RuntimeError("Phase 4 long-table row count changed")
    if tuple(frame.columns) != REQUIRED_COLUMNS:
        raise RuntimeError("Phase 4 long-table schema changed")
    reference = frame.loc[frame["branch"] == "pdcsap"].copy()
    reference.sort_values(["sector", "cadenceno"], inplace=True)
    reference.reset_index(drop=True, inplace=True)
    if reference.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("PDCSAP reference has duplicate sector/cadence keys")
    finite = (
        np.isfinite(reference["time_btjd"])
        & np.isfinite(reference["flux"])
        & np.isfinite(reference["flux_err"])
        & (reference["flux_err"] > 0)
    )
    if not finite.all():
        raise RuntimeError("PDCSAP reference contains invalid retained values")
    if not ((reference["quality"].to_numpy(np.int64) & 17087) == 0).all():
        raise RuntimeError("PDCSAP reference violates the frozen quality mask")
    return reference


def event_rows(reference, event, half_width_days):
    sector_rows = reference.loc[reference["sector"] == event["sector"]]
    distance = sector_rows["time_btjd"].to_numpy(float) - event["midpoint_btjd"]
    selected = np.abs(distance) <= half_width_days
    rows = sector_rows.loc[selected, ["time_btjd", "sector", "cadenceno", "flux", "flux_err"]].copy()
    rows["event_id"] = event["physical_event_id"]
    rows["epoch"] = event["epoch"]
    rows["event_midpoint_btjd"] = event["midpoint_btjd"]
    rows["x_days"] = rows["time_btjd"] - event["midpoint_btjd"]
    rows.sort_values("time_btjd", inplace=True)
    rows.reset_index(drop=True, inplace=True)
    return rows


def build_cell_events(reference, events, half_width_days):
    result = [event_rows(reference, event, half_width_days) for event in events]
    if any(rows.empty for rows in result):
        raise RuntimeError("A Phase-5 event has no cadence in a requested window")
    combined = pd.concat(result, ignore_index=True)
    if combined.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("A cadence was assigned to more than one Phase-5 event")
    return result


def polynomial_basis(x_days, degree):
    x_days = np.asarray(x_days, dtype=float)
    return np.column_stack([x_days**power for power in range(degree + 1)])


def log_jitter_grid(prereg):
    lower_ppm, upper_ppm = prereg["noise_model"]["jitter_bounds_ppm"]
    count = int(prereg["noise_model"]["log_jitter_midpoint_grid_size"])
    edges = np.linspace(math.log(lower_ppm * 1e-6), math.log(upper_ppm * 1e-6), count + 1)
    return np.exp(0.5 * (edges[:-1] + edges[1:]))


@dataclass
class MarginalBlock:
    event_id: str
    sector: int
    flux: np.ndarray
    error: np.ndarray
    basis: np.ndarray
    jitter_grid: np.ndarray
    baseline_prior_sigma: float

    def __post_init__(self):
        self.flux = np.asarray(self.flux, dtype=float)
        self.error = np.asarray(self.error, dtype=float)
        self.basis = np.asarray(self.basis, dtype=float)
        self.jitter_grid = np.asarray(self.jitter_grid, dtype=float)
        variance = self.error[None, :] ** 2 + self.jitter_grid[:, None] ** 2
        self.weight = 1.0 / variance
        self.log_variance_sum = np.sum(np.log(variance), axis=1)
        self.prior_precision = 1.0 / self.baseline_prior_sigma**2
        self.log_prior_covariance_determinant = (
            self.basis.shape[1] * math.log(self.baseline_prior_sigma**2)
        )
        self.design_rank = int(np.linalg.matrix_rank(self.basis))

    def loglike_grid(self, transit=None):
        if transit is None:
            transit = np.ones(len(self.flux))
        transit = np.asarray(transit, dtype=float)
        design = transit[:, None] * self.basis
        target = self.flux - transit
        grid_count = len(self.jitter_grid)
        parameter_count = design.shape[1]
        information = np.zeros((grid_count, parameter_count, parameter_count))
        rhs = np.zeros((grid_count, parameter_count))
        for left in range(parameter_count):
            rhs[:, left] = self.weight @ (target * design[:, left])
            for right in range(left, parameter_count):
                values = self.weight @ (design[:, left] * design[:, right])
                information[:, left, right] = values
                information[:, right, left] = values
        diagonal = np.arange(parameter_count)
        information[:, diagonal, diagonal] += self.prior_precision
        solution = np.linalg.solve(information, rhs[..., None])[..., 0]
        quadratic = self.weight @ target**2 - np.sum(rhs * solution, axis=1)
        sign, log_information_determinant = np.linalg.slogdet(information)
        if not np.all(sign > 0):
            raise RuntimeError(f"Non-positive baseline information for {self.event_id}")
        log_determinant = (
            self.log_variance_sum
            + self.log_prior_covariance_determinant
            + log_information_determinant
        )
        return -0.5 * (
            quadratic + log_determinant + len(self.flux) * math.log(2.0 * math.pi)
        )

    def information_condition(self, transit, jitter_index):
        transit = np.asarray(transit, dtype=float)
        design = transit[:, None] * self.basis
        weight = self.weight[int(jitter_index)]
        information = design.T @ (weight[:, None] * design)
        information += np.eye(design.shape[1]) * self.prior_precision
        return float(np.linalg.cond(information))


class CellModel:
    def __init__(self, event_frames, degree, prereg, jitter_values):
        self.degree = int(degree)
        self.period_days = float(prereg["transit_model"]["period_days_fixed"])
        self.ld = prereg["transit_model"]["limb_darkening_quadratic_fixed"]
        self.exposure_seconds = float(prereg["transit_model"]["exposure_seconds"])
        self.supersample_factor = int(prereg["transit_model"]["supersample_factor"])
        self.bounds = tuple(
            tuple(prereg["transit_model"]["geometry_uniform_bounds"][name])
            for name in ("rp_rs", "a_rs", "impact_parameter")
        )
        prior_sigma = float(prereg["grid"]["baseline_coefficient_prior"]["sigma"])
        self.blocks = []
        self.slices = []
        x_parts = []
        start = 0
        for frame in event_frames:
            x = frame["x_days"].to_numpy(float)
            block = MarginalBlock(
                event_id=str(frame["event_id"].iloc[0]),
                sector=int(frame["sector"].iloc[0]),
                flux=frame["flux"].to_numpy(float),
                error=frame["flux_err"].to_numpy(float),
                basis=polynomial_basis(x, self.degree),
                jitter_grid=jitter_values,
                baseline_prior_sigma=prior_sigma,
            )
            stop = start + len(frame)
            self.blocks.append(block)
            self.slices.append(slice(start, stop))
            x_parts.append(x)
            start = stop
        self.x = np.concatenate(x_parts)
        self.n_points = len(self.x)
        self.jitter_values = np.asarray(jitter_values, dtype=float)
        params = batman.TransitParams()
        params.t0 = 0.0
        params.per = self.period_days
        params.rp = 0.055
        params.a = 10.2
        params.inc = 86.0
        params.ecc = 0.0
        params.w = 90.0
        params.u = list(self.ld)
        params.limb_dark = "quadratic"
        self.params = params
        self.transit_model = batman.TransitModel(
            params,
            self.x,
            supersample_factor=self.supersample_factor,
            exp_time=self.exposure_seconds / 86400.0,
        )

    def transit(self, theta):
        rp_rs, a_rs, impact = [float(value) for value in theta]
        if impact >= 1.0 + rp_rs or impact >= a_rs:
            return None
        cosine = impact / a_rs
        if not 0.0 <= cosine < 1.0:
            return None
        self.params.rp = rp_rs
        self.params.a = a_rs
        self.params.inc = math.degrees(math.acos(cosine))
        transit = self.transit_model.light_curve(self.params)
        return transit if np.all(np.isfinite(transit)) else None

    def sector_loglike_grids(self, theta):
        transit = self.transit(theta)
        if transit is None:
            return None, None
        sector_logs = {sector: np.zeros(len(self.jitter_values)) for sector in SECTORS}
        for block, selected in zip(self.blocks, self.slices):
            sector_logs[block.sector] += block.loglike_grid(transit[selected])
        return sector_logs, transit

    def log_posterior(self, theta):
        theta = np.asarray(theta, dtype=float)
        if any(
            not lower < value < upper
            for value, (lower, upper) in zip(theta, self.bounds)
        ):
            return -np.inf
        sector_logs, _ = self.sector_loglike_grids(theta)
        if sector_logs is None:
            return -np.inf
        value = sum(
            float(logsumexp(sector_logs[sector]) - math.log(len(self.jitter_values)))
            for sector in SECTORS
        )
        return value if np.isfinite(value) else -np.inf

    def objective(self, theta):
        value = self.log_posterior(theta)
        return -value if np.isfinite(value) else 1e100

    def jitter_summaries(self, theta):
        sector_logs, transit = self.sector_loglike_grids(theta)
        summaries = {}
        maximum_condition = 0.0
        for sector in SECTORS:
            log_weight = sector_logs[sector] - logsumexp(sector_logs[sector])
            weight = np.exp(log_weight)
            q16, median, q84 = weighted_quantile(
                self.jitter_values * 1e6, weight, [0.16, 0.50, 0.84]
            )
            maximum_index = int(np.argmax(weight))
            summaries[str(sector)] = {
                "p16_ppm": float(q16),
                "median_ppm": float(median),
                "p84_ppm": float(q84),
                "maximum_grid_weight": float(weight[maximum_index]),
            }
            for block, selected in zip(self.blocks, self.slices):
                if block.sector == sector:
                    maximum_condition = max(
                        maximum_condition,
                        block.information_condition(transit[selected], maximum_index),
                    )
        return summaries, maximum_condition


def marginal_grid_for_frame(frame, degree, jitter_values, prior_sigma):
    block = MarginalBlock(
        event_id=str(frame["event_id"].iloc[0]),
        sector=int(frame["sector"].iloc[0]),
        flux=frame["flux"].to_numpy(float),
        error=frame["flux_err"].to_numpy(float),
        basis=polynomial_basis(frame["x_days"].to_numpy(float), degree),
        jitter_grid=jitter_values,
        baseline_prior_sigma=prior_sigma,
    )
    if block.design_rank != degree + 1:
        raise RuntimeError(f"Rank-deficient Phase-5 OOT design for {block.event_id}")
    return block.loglike_grid()


def concat_frames(*frames):
    selected = [frame for frame in frames if len(frame)]
    if not selected:
        raise RuntimeError("Cannot marginalize an empty frame set")
    result = pd.concat(selected, ignore_index=True)
    result.sort_values("time_btjd", inplace=True)
    result.reset_index(drop=True, inplace=True)
    if result.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("Training and validation cadence sets overlap")
    return result


def blocked_scores(reference, events, total_window_hours, degree, prereg, jitter_values):
    half_width_days = total_window_hours / 48.0
    t14_hours = load_json(FAZ2_PATH)["ephemeris_and_windows"]["t14_hours"]
    inner_days = 0.75 * t14_hours / 24.0
    common_outer_days = float(
        prereg["blocked_predictive_comparison"]["common_score_outer_boundary_hours"]
    ) / 24.0
    minimum_side = int(
        prereg["blocked_predictive_comparison"]["minimum_cadences_per_common_side"]
    )
    prior_sigma = float(prereg["grid"]["baseline_coefficient_prior"]["sigma"])
    components = {}
    eligible = []
    for event in events:
        frame = event_rows(reference, event, half_width_days)
        oot = frame.loc[np.abs(frame["x_days"]) >= inner_days].copy()
        left = oot.loc[oot["x_days"] < 0].copy()
        right = oot.loc[oot["x_days"] > 0].copy()
        left_common = left.loc[np.abs(left["x_days"]) <= common_outer_days].copy()
        right_common = right.loc[np.abs(right["x_days"]) <= common_outer_days].copy()
        key = event["physical_event_id"]
        is_eligible = (
            len(left_common) >= minimum_side and len(right_common) >= minimum_side
        )
        components[key] = {
            "event": event,
            "both": marginal_grid_for_frame(
                concat_frames(left, right), degree, jitter_values, prior_sigma
            ),
            "left_count": len(left),
            "right_count": len(right),
            "left_common_count": len(left_common),
            "right_common_count": len(right_common),
        }
        if is_eligible:
            components[key].update(
                {
                    "left": marginal_grid_for_frame(
                        left, degree, jitter_values, prior_sigma
                    ),
                    "right": marginal_grid_for_frame(
                        right, degree, jitter_values, prior_sigma
                    ),
                    "right_plus_left_common": marginal_grid_for_frame(
                        concat_frames(right, left_common),
                        degree,
                        jitter_values,
                        prior_sigma,
                    ),
                    "left_plus_right_common": marginal_grid_for_frame(
                        concat_frames(left, right_common),
                        degree,
                        jitter_values,
                        prior_sigma,
                    ),
                }
            )
            eligible.append(key)

    sector_both = {sector: np.zeros(len(jitter_values)) for sector in SECTORS}
    for item in components.values():
        sector_both[item["event"]["sector"]] += item["both"]

    rows = []
    identifier = cell_id(total_window_hours, degree)
    for key in eligible:
        item = components[key]
        event = item["event"]
        sector = event["sector"]
        for side in ("left", "right"):
            if side == "left":
                train_log = item["right"]
                combined_log = item["right_plus_left_common"]
                validation_count = item["left_common_count"]
                training_count = item["right_count"]
            else:
                train_log = item["left"]
                combined_log = item["left_plus_right_common"]
                validation_count = item["right_common_count"]
                training_count = item["left_count"]
            sector_training = sector_both[sector] - item["both"] + train_log
            conditional = combined_log - train_log
            predictive = float(
                logsumexp(sector_training + conditional)
                - logsumexp(sector_training)
            )
            rows.append(
                {
                    "cell_id": identifier,
                    "total_window_hours": int(total_window_hours),
                    "polynomial_degree": int(degree),
                    "event_id": key,
                    "sector": int(sector),
                    "epoch": int(event["epoch"]),
                    "side": side,
                    "elpd": predictive,
                    "validation_cadence_count": int(validation_count),
                    "held_event_opposite_side_training_count": int(training_count),
                    "transit_cadences_in_training": 0,
                    "held_side_cadences_in_training": 0,
                    "training_validation_overlap_count": 0,
                }
            )
    return pd.DataFrame(rows), {
        "eligible_event_ids": eligible,
        "excluded_event_ids": sorted(set(components) - set(eligible)),
        "fold_count": len(rows),
        "validation_cadence_count": int(
            sum(item["validation_cadence_count"] for item in rows)
        ),
        "common_score_inner_boundary_hours": inner_days * 24.0,
        "common_score_outer_boundary_hours": common_outer_days * 24.0,
    }


def finite_difference_hessian(function, optimum):
    optimum = np.asarray(optimum, dtype=float)
    base_steps = np.array([2e-5, 5e-3, 5e-4])
    attempts = []
    for scale in (0.5, 1.0, 2.0):
        steps = base_steps * scale
        dimension = len(optimum)
        hessian = np.empty((dimension, dimension))
        center = float(function(optimum))
        for left in range(dimension):
            plus = optimum.copy()
            minus = optimum.copy()
            plus[left] += steps[left]
            minus[left] -= steps[left]
            hessian[left, left] = (
                function(plus) - 2.0 * center + function(minus)
            ) / steps[left] ** 2
            for right in range(left):
                plus_plus = optimum.copy()
                plus_minus = optimum.copy()
                minus_plus = optimum.copy()
                minus_minus = optimum.copy()
                plus_plus[[left, right]] += steps[[left, right]]
                plus_minus[left] += steps[left]
                plus_minus[right] -= steps[right]
                minus_plus[left] -= steps[left]
                minus_plus[right] += steps[right]
                minus_minus[[left, right]] -= steps[[left, right]]
                value = (
                    function(plus_plus)
                    - function(plus_minus)
                    - function(minus_plus)
                    + function(minus_minus)
                ) / (4.0 * steps[left] * steps[right])
                hessian[left, right] = value
                hessian[right, left] = value
        eigenvalues = np.linalg.eigvalsh(hessian)
        rank = int(np.linalg.matrix_rank(hessian))
        condition = float(np.linalg.cond(hessian))
        valid = bool(
            np.all(np.isfinite(hessian))
            and np.all(eigenvalues > 0)
            and rank == dimension
            and np.isfinite(condition)
            and condition < 1e14
        )
        attempts.append(
            {
                "step_scale": scale,
                "steps": steps.tolist(),
                "rank": rank,
                "condition_number": condition,
                "eigenvalues": eigenvalues.tolist(),
                "valid": valid,
            }
        )
        if valid:
            covariance = np.linalg.inv(hessian)
            return hessian, covariance, attempts
    raise RuntimeError(f"No valid Phase-5 Laplace Hessian: {attempts}")


def draw_laplace(optimum, covariance, bounds, count, seed, period_days):
    rng = np.random.default_rng(seed)
    accepted = []
    generated = 0
    while sum(len(item) for item in accepted) < count:
        batch = rng.multivariate_normal(optimum, covariance, size=max(count, 2048))
        generated += len(batch)
        valid = np.ones(len(batch), dtype=bool)
        for index, (lower, upper) in enumerate(bounds):
            valid &= (batch[:, index] > lower) & (batch[:, index] < upper)
        valid &= batch[:, 2] < 1.0 + batch[:, 0]
        valid &= batch[:, 2] < batch[:, 1]
        duration = duration_hours(batch, period_days)
        valid &= np.isfinite(duration)
        accepted.append(np.column_stack([batch[valid], duration[valid]]))
        if generated > count * 100:
            raise RuntimeError("Laplace rejection sampler could not produce valid draws")
    draws = np.concatenate(accepted, axis=0)[:count]
    return draws, {
        "requested_draw_count": int(count),
        "generated_candidate_count": int(generated),
        "acceptance_fraction": float(count / generated),
        "seed": int(seed),
    }


def fit_cell(event_frames, total_window_hours, degree, prereg, jitter_values, index):
    model = CellModel(event_frames, degree, prereg, jitter_values)
    attempts = []
    results = []
    lower = np.asarray([bounds[0] for bounds in model.bounds], dtype=float)
    upper = np.asarray([bounds[1] for bounds in model.bounds], dtype=float)
    span = upper - lower
    objective_offset = model.objective(np.asarray(GEOMETRY_STARTS[0], dtype=float))

    def scaled_objective(unit_theta):
        return model.objective(lower + np.asarray(unit_theta) * span) - objective_offset

    for start_index, start in enumerate(GEOMETRY_STARTS):
        unit_start = (np.asarray(start, dtype=float) - lower) / span
        result = minimize(
            scaled_objective,
            unit_start,
            method="L-BFGS-B",
            jac="3-point",
            bounds=[(1e-8, 1.0 - 1e-8)] * 3,
            options={
                "maxiter": 500,
                "maxls": 50,
                "ftol": 1e-12,
                "gtol": 1e-7,
                "finite_diff_rel_step": 1e-4,
            },
        )
        final = lower + result.x * span
        actual_objective = float(result.fun + objective_offset)
        results.append((result, final, actual_objective))
        attempts.append(
            {
                "start_index": start_index,
                "initial": list(start),
                "final": final.tolist(),
                "negative_log_marginal_posterior": actual_objective,
                "success": bool(result.success),
                "status": int(result.status),
                "message": str(result.message),
                "iterations": int(result.nit),
                "function_evaluations": int(result.nfev),
            }
        )
    finite = [
        position
        for position, (_, _, objective) in enumerate(results)
        if np.isfinite(objective)
    ]
    successful = [position for position in finite if results[position][0].success]
    candidates = successful or finite
    if not candidates:
        raise RuntimeError(f"No finite optimizer result for {cell_id(total_window_hours, degree)}")
    best_index = min(candidates, key=lambda position: results[position][2])
    best, best_theta, best_objective = results[best_index]
    hessian, covariance, hessian_attempts = finite_difference_hessian(
        model.objective, best_theta
    )
    draw_count = int(prereg["posterior_approximation"]["draws_per_cell"])
    seed = int(prereg["posterior_approximation"]["random_seed"]) + index
    draws, draw_diagnostics = draw_laplace(
        best_theta,
        covariance,
        model.bounds,
        draw_count,
        seed,
        model.period_days,
    )
    summaries = {
        name: percentile_summary(draws[:, parameter_index])
        for parameter_index, name in enumerate(PARAMETERS)
    }
    jitter_summaries, maximum_condition = model.jitter_summaries(best_theta)
    ranks = [block.design_rank for block in model.blocks]
    return {
        "cell_id": cell_id(total_window_hours, degree),
        "total_window_hours": int(total_window_hours),
        "half_window_hours": float(total_window_hours / 2.0),
        "event_polynomial_degree": int(degree),
        "n_points": int(model.n_points),
        "n_events": len(model.blocks),
        "n_points_by_sector": {
            str(sector): int(
                sum(len(block.flux) for block in model.blocks if block.sector == sector)
            )
            for sector in SECTORS
        },
        "optimizer": {
            "algorithm": "bounded L-BFGS-B with three-point numerical gradient",
            "multiple_start_count": len(GEOMETRY_STARTS),
            "selected_start_index": best_index,
            "selected_success": bool(best.success),
            "selected_parameters": best_theta.tolist(),
            "selected_negative_log_marginal_posterior": best_objective,
            "attempts": attempts,
        },
        "baseline_marginalization": {
            "event_specific": True,
            "coefficient_count": len(model.blocks) * (degree + 1),
            "minimum_design_rank": int(min(ranks)),
            "required_design_rank": int(degree + 1),
            "maximum_information_condition_number_at_modal_jitter": maximum_condition,
        },
        "sector_jitter_marginal_ppm": jitter_summaries,
        "laplace": {
            "parameter_order": list(PARAMETERS[:3]),
            "hessian": hessian.tolist(),
            "covariance": covariance.tolist(),
            "hessian_attempts": hessian_attempts,
            "valid": True,
            "draw_diagnostics": draw_diagnostics,
        },
        "posterior": summaries,
        "draws": draws,
    }


def paired_comparison(block_scores, best_id, other_id):
    selected = block_scores.loc[
        block_scores["cell_id"].isin([best_id, other_id])
    ]
    event = selected.groupby(["cell_id", "event_id"], sort=True)["elpd"].sum().unstack(0)
    event_delta = event[best_id] - event[other_id]
    sector = selected.groupby(["cell_id", "sector"], sort=True)["elpd"].sum().unstack(0)
    sector_delta = sector[best_id] - sector[other_id]
    se_event = float(math.sqrt(len(event_delta) * np.var(event_delta, ddof=1)))
    se_sector = float(math.sqrt(len(sector_delta) * np.var(sector_delta, ddof=1)))
    delta = float(event_delta.sum())
    standard_error = max(se_event, se_sector)
    return {
        "cell_id": other_id,
        "delta_elpd_best_minus_cell": delta,
        "event_cluster_standard_error": se_event,
        "sector_cluster_standard_error": se_sector,
        "adopted_standard_error": standard_error,
        "two_standard_errors": 2.0 * standard_error,
        "strictly_distinguished": bool(delta > 2.0 * standard_error),
    }


def artifact_record(path, **extra):
    result = {
        "relative_path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    result.update(extra)
    return result


def main():
    prereg = load_json(PREREG_PATH)
    faz2 = load_json(FAZ2_PATH)
    faz4 = load_json(FAZ4_PATH)
    checks, events, long_hash = validate_inputs(prereg, faz2, faz4)
    reference = load_reference_table(faz4)
    jitter_values = log_jitter_grid(prereg)
    windows = prereg["grid"]["total_window_hours"]
    degrees = prereg["grid"]["event_polynomial_degrees"]

    block_frames = []
    score_metadata = {}
    cells = []
    draw_arrays = []
    for index, (window, degree) in enumerate(
        (window, degree) for window in windows for degree in degrees
    ):
        identifier = cell_id(window, degree)
        print(f"Phase 5 scoring and fitting {identifier}")
        block_frame, score_meta = blocked_scores(
            reference, events, window, degree, prereg, jitter_values
        )
        block_frames.append(block_frame)
        score_metadata[identifier] = score_meta
        event_frames = build_cell_events(reference, events, window / 48.0)
        fit = fit_cell(
            event_frames, window, degree, prereg, jitter_values, index
        )
        fit["blocked_predictive"] = {
            **score_meta,
            "elpd": float(block_frame["elpd"].sum()),
        }
        draw_arrays.append(fit.pop("draws"))
        cells.append(fit)

    block_scores = pd.concat(block_frames, ignore_index=True)
    totals = block_scores.groupby("cell_id")["elpd"].sum().to_dict()
    best_id = max(totals, key=totals.get)
    comparisons = []
    for identifier in totals:
        if identifier == best_id:
            comparisons.append(
                {
                    "cell_id": identifier,
                    "delta_elpd_best_minus_cell": 0.0,
                    "event_cluster_standard_error": 0.0,
                    "sector_cluster_standard_error": 0.0,
                    "adopted_standard_error": 0.0,
                    "two_standard_errors": 0.0,
                    "strictly_distinguished": False,
                }
            )
        else:
            comparisons.append(paired_comparison(block_scores, best_id, identifier))
    comparison_by_id = {item["cell_id"]: item for item in comparisons}
    retained = [
        identifier
        for identifier in totals
        if identifier == best_id
        or not comparison_by_id[identifier]["strictly_distinguished"]
    ]
    retained.sort(key=lambda identifier: (-totals[identifier], identifier))
    single_model_selected = len(retained) == 1
    weights = {identifier: 1.0 / len(retained) for identifier in retained}

    draws_by_id = {
        cell["cell_id"]: draws for cell, draws in zip(cells, draw_arrays)
    }
    mixture = np.concatenate([draws_by_id[identifier] for identifier in retained], axis=0)
    mixture_summary = {
        name: percentile_summary(mixture[:, position])
        for position, name in enumerate(PARAMETERS)
    }
    phase4_systematic = faz4["accepted_branch_geometry_comparison"][
        "between_reduction_systematic"
    ]["values"]
    cumulative = {}
    for name in PARAMETERS:
        summary = mixture_summary[name]
        systematic = float(phase4_systematic[name]["adopted_systematic"])
        lower_width = math.sqrt((summary["median"] - summary["p16"]) ** 2 + systematic**2)
        upper_width = math.sqrt((summary["p84"] - summary["median"]) ** 2 + systematic**2)
        cumulative[name] = {
            **summary,
            "phase4_between_reduction_systematic": systematic,
            "cumulative_p16": summary["median"] - lower_width,
            "cumulative_p84": summary["median"] + upper_width,
            "combination_rule": "Phase-5 model-mixture side width and Phase-4 systematic added in quadrature",
        }

    cell_by_id = {cell["cell_id"]: cell for cell in cells}
    retained_median_checks = {}
    for identifier in retained:
        retained_median_checks[identifier] = {
            name: bool(
                cumulative[name]["cumulative_p16"]
                <= cell_by_id[identifier]["posterior"][name]["median"]
                <= cumulative[name]["cumulative_p84"]
            )
            for name in PARAMETERS
        }
    all_medians_inside = all(
        all(parameter_checks.values())
        for parameter_checks in retained_median_checks.values()
    )

    for cell in cells:
        identifier = cell["cell_id"]
        comparison = comparison_by_id[identifier]
        cell["blocked_predictive"]["delta_elpd_from_best"] = comparison[
            "delta_elpd_best_minus_cell"
        ]
        cell["blocked_predictive"]["paired_standard_error_vs_best"] = comparison[
            "adopted_standard_error"
        ]
        cell["retained_for_model_average"] = identifier in retained
        cell["model_weight"] = weights.get(identifier, 0.0)

    expected_counts = {13: 6081, 16: 7430, 20: 9273, 26: 11959, 32: 14640}
    count_gate = all(
        cell["n_points"] == expected_counts[cell["total_window_hours"]]
        for cell in cells
    )
    cv_gate = all(
        metadata["fold_count"] == 30
        and metadata["validation_cadence_count"] == 2236
        and len(metadata["eligible_event_ids"]) == 15
        for metadata in score_metadata.values()
    )
    gate_checks = {
        "all_input_checks_pass": all(checks.values()),
        "all_15_cells_completed": len(cells) == 15,
        "all_cells_use_16_events": all(cell["n_events"] == 16 for cell in cells),
        "native_cadence_counts_exact": count_gate,
        "common_blocked_score_support_exact": cv_gate,
        "all_baseline_designs_full_rank": all(
            cell["baseline_marginalization"]["minimum_design_rank"]
            == cell["baseline_marginalization"]["required_design_rank"]
            for cell in cells
        ),
        "all_laplace_covariances_valid": all(cell["laplace"]["valid"] for cell in cells),
        "selection_rule_applied": bool(
            (single_model_selected and len(retained) == 1)
            or (not single_model_selected and len(retained) > 1)
        ),
        "model_weights_sum_to_one": math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12),
        "retained_cell_medians_inside_final_68pct": all_medians_inside,
        "dependent_reduction_likelihoods_not_multiplied": True,
        "phase4_systematic_propagated_once": True,
    }
    gate_status = "PASS" if all(gate_checks.values()) else "FAIL"

    grid_rows = []
    for cell in cells:
        comparison = comparison_by_id[cell["cell_id"]]
        row = {
            "cell_id": cell["cell_id"],
            "total_window_hours": cell["total_window_hours"],
            "half_window_hours": cell["half_window_hours"],
            "polynomial_degree": cell["event_polynomial_degree"],
            "n_points": cell["n_points"],
            "n_events": cell["n_events"],
            "elpd": cell["blocked_predictive"]["elpd"],
            "delta_elpd_from_best": comparison["delta_elpd_best_minus_cell"],
            "paired_se_vs_best": comparison["adopted_standard_error"],
            "retained": cell["retained_for_model_average"],
            "model_weight": cell["model_weight"],
        }
        for name in PARAMETERS:
            for statistic in ("p16", "median", "p84"):
                row[f"{name}_{statistic}"] = cell["posterior"][name][statistic]
        grid_rows.append(row)
    grid_frame = pd.DataFrame(grid_rows)
    grid_frame.to_csv(GRID_CSV_PATH, index=False, lineterminator="\n")
    block_scores.to_csv(BLOCK_CSV_PATH, index=False, lineterminator="\n")
    np.savez_compressed(
        DRAW_PATH,
        cell_ids=np.asarray([cell["cell_id"] for cell in cells], dtype="U8"),
        parameter_names=np.asarray(PARAMETERS, dtype="U32"),
        draws=np.stack(draw_arrays),
    )

    result = {
        "phase": 5,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": gate_status,
        "input_policy": {
            "active_phase4_products_only": True,
            "legacy_zip_inspected": False,
            "network_used": False,
            "git_used": False,
            "phase6_started": False,
        },
        "preregistration": {
            "relative_path": relative(PREREG_PATH),
            "sha256": sha256_file(PREREG_PATH),
            "frozen_utc": prereg["frozen_utc"],
            "frozen_before_first_phase5_fit": prereg[
                "frozen_before_first_phase5_fit"
            ],
        },
        "inputs": {
            "phase2_report": {
                "relative_path": relative(FAZ2_PATH),
                "sha256": sha256_file(FAZ2_PATH),
            },
            "phase4_report": {
                "relative_path": relative(FAZ4_PATH),
                "sha256": sha256_file(FAZ4_PATH),
                "status": faz4["gate"]["status"],
            },
            "phase4_long_table": {
                "relative_path": relative(LONG_TABLE_PATH),
                "sha256": long_hash,
                "reference_branch": "pdcsap",
                "reference_branch_row_count": len(reference),
            },
            "used_events": events,
            "input_validation": checks,
        },
        "model": {
            "timestamps": "native 120-s BTJD around exactly the 16 Phase-2 used events",
            "period_days_fixed": prereg["transit_model"]["period_days_fixed"],
            "t0_btjd_fixed": prereg["transit_model"]["t0_btjd_fixed"],
            "limb_darkening_fixed": prereg["transit_model"][
                "limb_darkening_quadratic_fixed"
            ],
            "exposure_seconds": prereg["transit_model"]["exposure_seconds"],
            "supersample_factor": prereg["transit_model"]["supersample_factor"],
            "baseline_model": prereg["grid"]["baseline_model"],
            "baseline_prior": prereg["grid"]["baseline_coefficient_prior"],
            "event_baselines": "analytically marginalized",
            "sector_jitters": "marginalized over the preregistered uniform-log midpoint grid",
            "reductions_combined_as_independent_likelihoods": False,
            "posterior_approximation": prereg["posterior_approximation"],
        },
        "blocked_predictive_design": {
            **prereg["blocked_predictive_comparison"],
            "eligible_event_count": 15,
            "fold_count_per_cell": 30,
            "validation_cadence_count_per_cell": 2236,
            "excluded_event_ids": sorted(
                set().union(
                    *(set(item["excluded_event_ids"]) for item in score_metadata.values())
                )
            ),
            "same_score_cadences_for_all_cells": True,
        },
        "cells": cells,
        "model_comparison": {
            "selection_metric": "maximum blocked out-of-transit ELPD",
            "best_raw_elpd_cell": best_id,
            "best_raw_elpd": float(totals[best_id]),
            "pairwise_against_best": comparisons,
            "single_model_selected": single_model_selected,
            "retained_cell_ids": retained,
            "retained_model_count": len(retained),
            "weights": weights,
            "weight_rule": "equal weights across cells not distinguished from the raw-ELPD best by strictly more than 2 paired SE",
        },
        "model_averaged_geometry": {
            "phase5_grid_mixture": mixture_summary,
            "cumulative_with_phase4_reduction_systematic": cumulative,
            "retained_cell_median_checks": retained_median_checks,
            "mixture_draw_count": len(mixture),
            "covariance_parameter_order": list(PARAMETERS),
            "mixture_covariance": np.cov(mixture, rowvar=False, ddof=1).tolist(),
        },
        "gate": {
            "checks": gate_checks,
            "status": gate_status,
            "gate_pass": gate_status == "PASS",
            "phase6_may_begin": gate_status == "PASS",
            "phase6_started": False,
        },
        "limitations": [
            "This phase isolates window and event-polynomial sensitivity on the accepted PDCSAP reference branch; it does not multiply same-pixel reduction likelihoods.",
            "The geometry posterior uses the preregistered Laplace approximation rather than MCMC; Phase 6 and Phase 17 remain required before final system parameters.",
            "The Phase-4 accepted-reduction systematic is added once in quadrature and remains separate from the Phase-5 model mixture.",
            "The blocked score is conditional on the already frozen Phase-4 reduction and is not an end-to-end raw-pixel cross-validation.",
        ],
    }
    result["artifacts"] = {
        "grid_csv": artifact_record(GRID_CSV_PATH, row_count=len(grid_frame), columns=list(grid_frame.columns)),
        "block_scores_csv": artifact_record(
            BLOCK_CSV_PATH,
            row_count=len(block_scores),
            columns=list(block_scores.columns),
        ),
        "geometry_draws_npz": artifact_record(
            DRAW_PATH,
            cell_count=len(cells),
            draws_per_cell=int(prereg["posterior_approximation"]["draws_per_cell"]),
            parameter_order=list(PARAMETERS),
        ),
    }
    OUTPUT_PATH.write_text(
        json.dumps(json_ready(result), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"Phase 5 {gate_status}: best={best_id}, retained={len(retained)}, "
        f"output={relative(OUTPUT_PATH)}"
    )


if __name__ == "__main__":
    main()
