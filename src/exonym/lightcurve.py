"""Target-independent helpers for phase-folded transit light curves."""

from __future__ import annotations

import re
from typing import Optional, Sequence, Tuple

import numpy as np


def parse_tess_sector(mission: object) -> Optional[int]:
    """Return the TESS sector number in a MAST mission label, if present."""
    match = re.search(r"\bSector\s+(\d+)\b", str(mission), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def phase_hours(
    time_btjd: Sequence[float], period_days: float, epoch_btjd: float
) -> np.ndarray:
    """Return signed hours from the nearest transit center for each BTJD time."""
    if period_days <= 0:
        raise ValueError("period_days must be positive")
    time = np.asarray(time_btjd, dtype=float)
    return (
        (time - float(epoch_btjd) + 0.5 * float(period_days)) % float(period_days)
        - 0.5 * float(period_days)
    ) * 24.0


def robust_transit_depth(
    time_btjd: Sequence[float],
    flux: Sequence[float],
    period_days: float,
    epoch_btjd: float,
    duration_hours: float,
) -> Tuple[float, float, int, int]:
    """Estimate median in/out transit depth and uncertainty in ppm.

    The in-transit window spans one catalog duration. Symmetric out-of-transit
    windows span 1.2 to 2.5 durations from transit center. Invalid samples are
    excluded before both the depth and its robust standard-error estimate.
    """
    if duration_hours <= 0:
        raise ValueError("duration_hours must be positive")

    time = np.asarray(time_btjd, dtype=float)
    values = np.asarray(flux, dtype=float)
    if time.shape != values.shape:
        raise ValueError("time_btjd and flux must have identical shapes")

    hours = phase_hours(time, period_days, epoch_btjd)
    finite = np.isfinite(hours) & np.isfinite(values)
    in_transit = finite & (np.abs(hours) < 0.5 * duration_hours)
    out_of_transit = finite & (np.abs(hours) > 1.2 * duration_hours) & (
        np.abs(hours) < 2.5 * duration_hours
    )
    in_values = values[in_transit]
    out_values = values[out_of_transit]
    if not in_values.size or not out_values.size:
        raise ValueError("insufficient finite in-transit or out-of-transit coverage")

    depth = float(np.median(out_values) - np.median(in_values))
    uncertainty = float(
        np.sqrt(
            (1.253 * np.std(in_values) / np.sqrt(in_values.size)) ** 2
            + (1.253 * np.std(out_values) / np.sqrt(out_values.size)) ** 2
        )
    )
    return depth * 1e6, uncertainty * 1e6, int(in_values.size), int(out_values.size)


def bin_phase_folded_flux(
    time_btjd: Sequence[float],
    flux: Sequence[float],
    period_days: float,
    epoch_btjd: float,
    limit_hours: float = 14.0,
    bin_minutes: float = 8.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Phase-fold and median-bin a light curve for a diagnostic plot."""
    if limit_hours <= 0:
        raise ValueError("limit_hours must be positive")
    if bin_minutes <= 0:
        raise ValueError("bin_minutes must be positive")

    time = np.asarray(time_btjd, dtype=float)
    values = np.asarray(flux, dtype=float)
    if time.shape != values.shape:
        raise ValueError("time_btjd and flux must have identical shapes")

    hours = phase_hours(time, period_days, epoch_btjd)
    valid = np.isfinite(hours) & np.isfinite(values) & (np.abs(hours) <= limit_hours)
    width_hours = bin_minutes / 60.0
    bin_count = int(np.ceil(2.0 * limit_hours / width_hours))
    edges = np.linspace(-limit_hours, limit_hours, bin_count + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    median = np.full(bin_count, np.nan, dtype=float)
    error = np.full(bin_count, np.nan, dtype=float)

    for index in range(bin_count):
        if index == bin_count - 1:
            mask = valid & (hours >= edges[index]) & (hours <= edges[index + 1])
        else:
            mask = valid & (hours >= edges[index]) & (hours < edges[index + 1])
        samples = values[mask]
        if samples.size >= 3:
            median[index] = np.median(samples)
            error[index] = 1.253 * np.std(samples) / np.sqrt(samples.size)

    return centers, median, error
