"""Target-neutral Box Least Squares (BLS) transit search engine.

Search routines evaluate transit candidate periodograms across light curves without
hardcoding target designations or ephemerides.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .lightcurve import phase_hours
from .workspace import CandidateWorkspace


@dataclass
class BLSSearchResult:
    best_period: float
    best_epoch: float
    best_depth_ppm: float
    best_duration_hours: float
    snr: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_period": float(self.best_period),
            "best_epoch": float(self.best_epoch),
            "best_depth_ppm": float(self.best_depth_ppm),
            "best_duration_hours": float(self.best_duration_hours),
            "snr": float(self.snr),
        }


def find_transits(
    time_btjd: Sequence[float],
    flux: Sequence[float],
    period_min: float = 0.5,
    period_max: float = 15.0,
    n_periods: int = 2000,
    duration_hours: float = 3.0,
) -> BLSSearchResult:
    """Run a target-neutral BLS periodogram search over a light curve.

    Returns the optimal (period, epoch, depth_ppm, duration_hours, snr).
    """
    time = np.asarray(time_btjd, dtype=float)
    values = np.asarray(flux, dtype=float)

    finite = np.isfinite(time) & np.isfinite(values)
    time = time[finite]
    values = values[finite]

    if time.size < 50:
        raise ValueError("insufficient data points for BLS transit search")
    if period_min <= 0 or period_max <= period_min:
        raise ValueError("invalid period search bounds")

    periods = np.linspace(period_min, period_max, n_periods)
    best_snr = -1.0
    best_period = float(periods[0])
    best_epoch = float(time[0])
    best_depth_ppm = 0.0

    t_min, t_max = np.min(time), np.max(time)

    for p in periods:
        # Epoch trial spacing must be at most half the transit duration so a
        # signal is never completely missed between trial epochs. Capped to
        # keep long-period searches tractable.
        n_epochs = max(8, min(int(np.ceil(p / (duration_hours / 48.0))), 40))
        for trial_epoch in np.linspace(t_min, t_min + p, n_epochs):
            ph = phase_hours(time, p, trial_epoch)
            in_transit = np.abs(ph) <= 0.5 * duration_hours
            out_transit = (np.abs(ph) > 1.0 * duration_hours) & (np.abs(ph) < 3.0 * duration_hours)

            in_vals = values[in_transit]
            out_vals = values[out_transit]

            if in_vals.size >= 1 and out_vals.size >= 3:
                depth = float(np.median(out_vals) - np.median(in_vals))
                std_out = np.std(out_vals) if np.std(out_vals) > 1e-8 else 1e-4
                snr = (depth * np.sqrt(in_vals.size)) / std_out

                if snr > best_snr:
                    best_snr = float(snr)
                    best_period = float(p)
                    best_epoch = float(trial_epoch)
                    best_depth_ppm = float(depth * 1e6)

    return BLSSearchResult(
        best_period=round(best_period, 5),
        best_epoch=round(best_epoch, 5),
        best_depth_ppm=round(best_depth_ppm, 2),
        best_duration_hours=round(duration_hours, 2),
        snr=round(max(best_snr, 0.0), 2),
    )


def _median_bin(time: np.ndarray, flux: np.ndarray, n_bins: int = 4000) -> Tuple[np.ndarray, np.ndarray]:
    """Median-bin a time-sorted light curve down to at most n_bins samples."""
    if time.size <= n_bins:
        return time, flux
    order = np.argsort(time)
    time_sorted = time[order]
    flux_sorted = flux[order]
    edges = np.linspace(0, time_sorted.size, n_bins + 1).astype(int)
    bin_times = np.empty(n_bins, dtype=float)
    bin_flux = np.empty(n_bins, dtype=float)
    for index in range(n_bins):
        start, stop = edges[index], edges[index + 1]
        if stop > start:
            bin_times[index] = np.mean(time_sorted[start:stop])
            bin_flux[index] = np.median(flux_sorted[start:stop])
    return bin_times, bin_flux


def load_candidate_light_curve(
    workspace: CandidateWorkspace, max_points: int = 4000
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Return (time_btjd, normalized_flux) from candidate FITS data, or None.

    Products are read from ``data/processed/`` first, then ``data/raw/``.
    Returns None when no readable FITS light curve with at least 50 points
    exists, so callers can fall back to a synthetic demonstration grid.
    """
    roots = (
        workspace.path / "data" / "processed",
        workspace.path / "data" / "raw",
    )
    fits_files: List[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for suffix in (".fits", ".fits.fz", ".fz"):
            fits_files.extend(root.rglob("*" + suffix))
    fits_files.sort()
    if not fits_files:
        return None

    try:
        import lightkurve as lk
    except ImportError:  # pragma: no cover - optional dependency
        return None

    for path in fits_files:
        try:
            light_curve = lk.read(path).remove_nans().normalize()
            time = np.asarray(light_curve.time.value, dtype=float)
            flux = np.asarray(light_curve.flux.value, dtype=float)
            if time.size < 50 or time.size != flux.size:
                continue
            return _median_bin(time, flux, n_bins=max_points)
        except Exception:
            continue
    return None


def run_bls_on_candidate(
    workspace: CandidateWorkspace,
    period_min: float = 0.5,
    period_max: float = 15.0,
) -> Path:
    """Run BLS transit search on candidate data and save JSON summary to outputs/.

    Real candidate light curves are used when present; otherwise a synthetic
    demonstration grid is analyzed and the payload is marked ``source``.
    """
    outputs_dir = workspace.path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    loaded = load_candidate_light_curve(workspace)
    if loaded is None:
        time = np.linspace(0, 30, 1000)
        flux = 1.0 - 0.001 * (np.abs((time - 2.0) % 3.5) < 0.05).astype(float)
        source = "synthetic-demo"
    else:
        time, flux = loaded
        source = "candidate-data"

    result = find_transits(time, flux, period_min=period_min, period_max=period_max)
    payload = result.to_dict()
    payload["source"] = source
    payload["n_points"] = int(time.size)

    output_path = outputs_dir / "bls_search_results.json"
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output_path
