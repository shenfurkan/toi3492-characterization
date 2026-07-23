"""Pure residual diagnostics for the preregistered Phase-6 noise-model gate.

All times are BTJD days and all residual calculations use float64.  The
functions in this module perform no file I/O and do not inspect model results.
"""

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from astropy.timeseries import LombScargle


REQUIRED_COLUMNS = ("time_btjd", "cadenceno", "residual", "sector")
CADENCE_MINUTES = 2.0
ACF_MAX_LAG_MINUTES = 360.0
BETA_TIMESCALES_MINUTES = (20, 40, 80, 160, 320, 360)
BETA_MINIMUM_FILLED_BINS = 3
BETA_MINIMUM_ELIGIBLE_SECTORS = 4
BETA_MAX = 1.2
PERIODOGRAM_PERIOD_MINUTES = (20.0, 360.0)
PERIODOGRAM_SAMPLES_PER_PEAK = 5
_MINUTES_PER_DAY = 1440.0
_AGGREGATE_SECTOR = "__equal_sector__"


def validate_residual_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and return a sorted, float64 residual frame copy.

    Non-finite times or residuals are rejected rather than silently removed.
    Times must be unique and strictly increasing within each sector.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas DataFrame")
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError("Missing residual-frame columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("Residual frame is empty")

    result = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    result["time_btjd"] = np.asarray(result["time_btjd"], dtype=np.float64)
    result["residual"] = np.asarray(result["residual"], dtype=np.float64)
    if not np.all(np.isfinite(result[["time_btjd", "residual"]].to_numpy())):
        raise ValueError("time_btjd and residual must contain only finite values")
    if result[["sector", "cadenceno"]].isna().any().any():
        raise ValueError("sector and cadenceno must not contain missing values")
    result["cadenceno"] = np.asarray(result["cadenceno"], dtype=np.int64)

    result.sort_values(["sector", "time_btjd"], kind="mergesort", inplace=True)
    result.reset_index(drop=True, inplace=True)
    for sector, group in result.groupby("sector", sort=False):
        if np.any(np.diff(group["time_btjd"].to_numpy()) <= 0.0):
            raise ValueError(
                "time_btjd must be unique and increasing within sector "
                + str(sector)
            )
        if np.any(np.diff(group["cadenceno"].to_numpy(np.int64)) <= 0):
            raise ValueError("cadenceno must be unique and increasing within sector")
    return result


def gap_aware_residual_acf(
    frame: pd.DataFrame,
    cadence_minutes: float = CADENCE_MINUTES,
    max_lag_minutes: float = ACF_MAX_LAG_MINUTES,
    grid_tolerance: float = 0.2,
) -> pd.DataFrame:
    """Calculate a cadence-index ACF without compressing gaps.

    A pair contributes at lag ``k`` only when its observed cadence indices
    differ by exactly ``k``.  Missing cadences therefore remain missing rather
    than becoming adjacent samples.  Residuals are centered per sector.  The
    aggregate row at each lag is an equal-sector mean of finite sector ACFs.
    """
    if cadence_minutes <= 0.0 or max_lag_minutes < 0.0:
        raise ValueError("cadence_minutes must be positive and max lag non-negative")
    if not 0.0 <= grid_tolerance < 0.5:
        raise ValueError("grid_tolerance must be in [0, 0.5)")
    lag_ratio = max_lag_minutes / cadence_minutes
    if not np.isclose(lag_ratio, round(lag_ratio), rtol=0.0, atol=1e-12):
        raise ValueError("max_lag_minutes must be an integer number of cadences")

    clean = validate_residual_frame(frame)
    max_lag = int(round(lag_ratio))
    rows: List[Dict[str, Any]] = []
    for sector, group in clean.groupby("sector", sort=False):
        time = group["time_btjd"].to_numpy(dtype=np.float64)
        residual = group["residual"].to_numpy(dtype=np.float64)
        residual = residual - np.mean(residual, dtype=np.float64)
        variance = np.mean(residual * residual, dtype=np.float64)
        indices = group["cadenceno"].to_numpy(dtype=np.int64)
        positions = {int(index): position for position, index in enumerate(indices)}

        for lag in range(max_lag + 1):
            left = []
            right = []
            for position, index in enumerate(indices):
                partner = positions.get(int(index) + lag)
                if partner is not None:
                    left.append(position)
                    right.append(partner)
            pair_count = len(left)
            acf = np.nan
            if pair_count and variance > 0.0:
                covariance = np.mean(
                    residual[np.asarray(left)] * residual[np.asarray(right)],
                    dtype=np.float64,
                )
                acf = float(covariance / variance)
            rows.append(
                {
                    "sector": sector,
                    "lag_cadences": lag,
                    "lag_minutes": float(lag * cadence_minutes),
                    "pair_count": pair_count,
                    "acf": acf,
                }
            )

    per_sector = pd.DataFrame.from_records(rows)
    aggregate_rows = []
    for lag, group in per_sector.groupby("lag_cadences", sort=True):
        finite = np.isfinite(group["acf"].to_numpy(dtype=np.float64))
        aggregate_rows.append(
            {
                "sector": _AGGREGATE_SECTOR,
                "lag_cadences": int(lag),
                "lag_minutes": float(lag * cadence_minutes),
                "pair_count": int(group.loc[finite, "pair_count"].sum()),
                "acf": (
                    float(group.loc[finite, "acf"].mean()) if finite.any() else np.nan
                ),
            }
        )
    return pd.concat(
        [per_sector, pd.DataFrame.from_records(aggregate_rows)], ignore_index=True
    )


def _contiguous_segments(
    time_btjd: np.ndarray,
    cadenceno: np.ndarray,
    cadence_minutes: float,
    gap_tolerance: float,
) -> List[np.ndarray]:
    del time_btjd, cadence_minutes, gap_tolerance
    split_at = np.flatnonzero(np.diff(cadenceno) != 1)
    return list(np.split(np.arange(cadenceno.size), split_at + 1))


def _sector_binned_means(
    time_btjd: np.ndarray,
    cadenceno: np.ndarray,
    residual: np.ndarray,
    timescale_minutes: float,
    cadence_minutes: float,
    gap_tolerance: float,
) -> Tuple[np.ndarray, np.ndarray]:
    means = []
    counts = []
    for segment in _contiguous_segments(
        time_btjd, cadenceno, cadence_minutes, gap_tolerance
    ):
        segment_time = time_btjd[segment]
        bin_index = np.floor(
            (segment_time - segment_time[0])
            * _MINUTES_PER_DAY
            / timescale_minutes
            + 1e-10
        ).astype(np.int64)
        for value in np.unique(bin_index):
            members = segment[bin_index == value]
            means.append(float(np.mean(residual[members], dtype=np.float64)))
            counts.append(int(members.size))
    return np.asarray(means, dtype=np.float64), np.asarray(counts, dtype=np.int64)


def binned_rms_beta(
    frame: pd.DataFrame,
    timescales_minutes: Tuple[int, ...] = BETA_TIMESCALES_MINUTES,
    cadence_minutes: float = CADENCE_MINUTES,
    minimum_filled_bins: int = BETA_MINIMUM_FILLED_BINS,
    minimum_eligible_sectors: int = BETA_MINIMUM_ELIGIBLE_SECTORS,
    gap_tolerance: float = 0.2,
) -> Dict[str, Any]:
    """Compute preregistered sector RMS-beta values and their strict aggregate.

    Bins restart after every missing cadence, so no bin spans a gap or sector.
    The white-noise expectation uses the actual occupancy of every filled bin:
    ``rms_1 * sqrt(mean(1 / n_i)) * sqrt(M / (M - 1))``.  The last factor is
    the finite-bin correction. A scale aggregate is defined when at least the
    registered number of sectors have ``minimum_filled_bins`` bins.
    """
    if cadence_minutes <= 0.0:
        raise ValueError("cadence_minutes must be positive")
    if minimum_filled_bins < 2:
        raise ValueError("minimum_filled_bins must be at least two")
    if minimum_eligible_sectors < 1:
        raise ValueError("minimum_eligible_sectors must be positive")
    if not 0.0 <= gap_tolerance < 0.5:
        raise ValueError("gap_tolerance must be in [0, 0.5)")
    scales = tuple(float(value) for value in timescales_minutes)
    if not scales or any(value <= 0.0 for value in scales):
        raise ValueError("timescales_minutes must contain positive values")

    clean = validate_residual_frame(frame)
    sectors = list(clean["sector"].drop_duplicates())
    rows = []
    for sector, group in clean.groupby("sector", sort=False):
        time = group["time_btjd"].to_numpy(dtype=np.float64)
        cadenceno = group["cadenceno"].to_numpy(dtype=np.int64)
        residual = group["residual"].to_numpy(dtype=np.float64)
        residual = residual - np.mean(residual, dtype=np.float64)
        unbinned_rms = float(np.sqrt(np.mean(residual * residual)))
        for scale in scales:
            means, counts = _sector_binned_means(
                time,
                cadenceno,
                residual,
                scale,
                cadence_minutes,
                gap_tolerance,
            )
            filled_bins = int(means.size)
            eligible = filled_bins >= minimum_filled_bins and unbinned_rms > 0.0
            binned_rms = np.nan
            finite_correction = np.nan
            effective_cadences = np.nan
            white_rms = np.nan
            beta = np.nan
            if filled_bins > 1:
                binned_rms = float(np.sqrt(np.mean((means - np.mean(means)) ** 2)))
                finite_correction = float(np.sqrt(filled_bins / (filled_bins - 1.0)))
                effective_cadences = float(1.0 / np.mean(1.0 / counts))
                white_rms = float(
                    unbinned_rms
                    * np.sqrt(np.mean(1.0 / counts))
                    * finite_correction
                )
                if eligible and white_rms > 0.0:
                    beta = float(binned_rms / white_rms)
            rows.append(
                {
                    "sector": sector,
                    "timescale_minutes": scale,
                    "filled_bins": filled_bins,
                    "eligible": bool(eligible),
                    "unbinned_rms": unbinned_rms,
                    "binned_rms": binned_rms,
                    "effective_cadences_per_bin": effective_cadences,
                    "finite_bin_correction": finite_correction,
                    "white_noise_rms": white_rms,
                    "beta": beta,
                }
            )

    per_sector = pd.DataFrame.from_records(rows)
    aggregate_rows = []
    for scale in scales:
        selected = per_sector.loc[per_sector["timescale_minutes"] == scale]
        usable = selected.loc[
            selected["eligible"] & np.isfinite(selected["beta"])
        ]
        complete = len(usable) >= minimum_eligible_sectors
        aggregate_rows.append(
            {
                "timescale_minutes": scale,
                "eligible_sector_count": int(selected["eligible"].sum()),
                "sector_count": len(sectors),
                "all_sectors_eligible": bool(complete),
                "equal_sector_beta": (
                    float(usable["beta"].mean()) if complete else np.nan
                ),
            }
        )
    aggregate = pd.DataFrame.from_records(aggregate_rows)
    complete = bool(aggregate["all_sectors_eligible"].all())
    max_beta = (
        float(aggregate["equal_sector_beta"].max()) if complete else None
    )
    return {
        "per_sector": per_sector,
        "aggregate": aggregate,
        "summary": {
            "all_scales_and_sectors_eligible": complete,
            "max_equal_sector_beta": max_beta,
            "minimum_filled_bins_per_sector": int(minimum_filled_bins),
            "minimum_eligible_sectors_per_timescale": int(minimum_eligible_sectors),
            "beta_maximum_allowed": BETA_MAX,
            "passes_beta_gate": bool(complete and max_beta <= BETA_MAX),
        },
    }


def lomb_scargle_diagnostics(
    frame: pd.DataFrame,
    period_minutes: Tuple[float, float] = PERIODOGRAM_PERIOD_MINUTES,
    samples_per_peak: int = PERIODOGRAM_SAMPLES_PER_PEAK,
    peak_count: int = 5,
) -> Dict[str, Any]:
    """Return a diagnostic Lomb-Scargle periodogram and ranked local peaks.

    Residuals are centered separately in each sector before the irregular-time
    periodogram.  Peak ranks are descriptive and are not detection claims.
    """
    if len(period_minutes) != 2:
        raise ValueError("period_minutes must contain (minimum, maximum)")
    minimum_period, maximum_period = (float(value) for value in period_minutes)
    if minimum_period <= 0.0 or maximum_period <= minimum_period:
        raise ValueError("period bounds must satisfy 0 < minimum < maximum")
    if samples_per_peak < 1 or peak_count < 1:
        raise ValueError("samples_per_peak and peak_count must be positive integers")

    clean = validate_residual_frame(frame)
    minimum_frequency = _MINUTES_PER_DAY / maximum_period
    maximum_frequency = _MINUTES_PER_DAY / minimum_period
    groups = list(clean.groupby("sector", sort=False))
    baselines = [np.ptp(group["time_btjd"].to_numpy(float)) for _, group in groups]
    longest = max(baselines)
    if longest <= 0.0:
        raise ValueError("Each residual sector requires a positive time baseline")
    frequency_step = 1.0 / (float(samples_per_peak) * longest)
    frequency = np.arange(
        minimum_frequency, maximum_frequency, frequency_step, dtype=np.float64
    )
    if frequency.size == 0 or frequency[-1] < maximum_frequency:
        frequency = np.r_[frequency, maximum_frequency]
    sector_power = []
    for _, group in groups:
        time = group["time_btjd"].to_numpy(dtype=np.float64)
        centered = group["residual"].to_numpy(dtype=np.float64)
        centered -= np.mean(centered, dtype=np.float64)
        if time.size < 3 or np.all(centered == 0.0):
            raise ValueError("Each sector requires three non-constant residuals")
        sector_power.append(
            LombScargle(
                time,
                centered,
                center_data=False,
                fit_mean=True,
                normalization="standard",
            ).power(frequency)
        )
    power = np.mean(np.asarray(sector_power, dtype=np.float64), axis=0)
    period = _MINUTES_PER_DAY / frequency
    periodogram = pd.DataFrame(
        {
            "frequency_per_day": frequency,
            "period_minutes": period,
            "power": power,
        }
    )

    if power.size == 1:
        candidates = np.array([0], dtype=np.int64)
    else:
        candidates = np.flatnonzero(
            (power >= np.r_[-np.inf, power[:-1]])
            & (power >= np.r_[power[1:], -np.inf])
        )
    ranked = candidates[np.argsort(power[candidates])[::-1]][:peak_count]
    peaks = periodogram.iloc[ranked].copy().reset_index(drop=True)
    peaks.insert(0, "rank", np.arange(1, len(peaks) + 1, dtype=np.int64))
    highest = peaks.iloc[0]
    summary = {
        "diagnostic_only": True,
        "samples_per_peak": int(samples_per_peak),
        "period_min_minutes": minimum_period,
        "period_max_minutes": maximum_period,
        "frequency_count": int(frequency.size),
        "sector_count": len(groups),
        "sector_aggregation": "equal-sector mean on a common frequency grid",
        "highest_peak_period_minutes": float(highest["period_minutes"]),
        "highest_peak_frequency_per_day": float(highest["frequency_per_day"]),
        "highest_peak_power": float(highest["power"]),
    }
    return {"periodogram": periodogram, "peaks": peaks, "summary": summary}


def _json_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _json_records(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    return [
        {key: _json_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def residual_diagnostics(frame: pd.DataFrame) -> Dict[str, Any]:
    """Run all frozen diagnostics and return a fully JSON-serializable dict."""
    clean = validate_residual_frame(frame)
    acf = gap_aware_residual_acf(clean)
    beta = binned_rms_beta(clean)
    periodogram = lomb_scargle_diagnostics(clean)
    return {
        "protocol": {
            "cadence_minutes": CADENCE_MINUTES,
            "acf_max_lag_minutes": ACF_MAX_LAG_MINUTES,
            "beta_timescales_minutes": list(BETA_TIMESCALES_MINUTES),
            "beta_minimum_filled_bins_per_sector": BETA_MINIMUM_FILLED_BINS,
            "beta_minimum_eligible_sectors_per_timescale": BETA_MINIMUM_ELIGIBLE_SECTORS,
            "beta_aggregation": "equal-sector mean at scale, then maximum",
            "beta_maximum_allowed": BETA_MAX,
            "periodogram_period_minutes": list(PERIODOGRAM_PERIOD_MINUTES),
            "periodogram_samples_per_peak": PERIODOGRAM_SAMPLES_PER_PEAK,
            "periodogram_diagnostic_only": True,
        },
        "input": {
            "row_count": int(len(clean)),
            "sector_count": int(clean["sector"].nunique()),
        },
        "acf": _json_records(acf),
        "beta": {
            "per_sector": _json_records(beta["per_sector"]),
            "aggregate": _json_records(beta["aggregate"]),
            "summary": beta["summary"],
        },
        "lomb_scargle": {
            "periodogram": _json_records(periodogram["periodogram"]),
            "peaks": _json_records(periodogram["peaks"]),
            "summary": periodogram["summary"],
        },
    }
