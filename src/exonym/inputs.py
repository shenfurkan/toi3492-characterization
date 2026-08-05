"""Target-neutral input loading for scientific analysis modules.

Every loader probes candidate workspace files and metadata only. Ephemerides,
stellar parameters, photometry, light curves, and target pixel files are read
dynamically; generic demonstration values are used only when no candidate data
exists and are always labelled ``synthetic-demo``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .workspace import CandidateWorkspace

# Generic demonstration ephemeris used only when no candidate ephemeris source
# exists. These are placeholder values, never target data.
DEMO_PERIOD_DAYS = 3.5
DEMO_EPOCH_BTJD = 2.0
DEMO_DURATION_DAYS = 0.12
DEMO_DEPTH_PPM = 1200.0

# Generic demonstration stellar parameters (solar reference values).
DEMO_TEFF_K = 5772.0
DEMO_LOGG_CGS = 4.438
DEMO_FEH = 0.0
DEMO_MASS_SOLAR = 1.0
DEMO_RADIUS_SOLAR = 1.0
DEMO_PARALLAX_MAS = 10.0

EPHEMERIS_CONFIG_NAMES = (
    "transit_config.json",
    "ephemeris.json",
    "candidate_ephemeris.json",
)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _first_number(payload: Dict[str, Any], keys: Sequence[str]) -> Optional[float]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def load_transit_ephemeris(workspace: CandidateWorkspace) -> Dict[str, Any]:
    """Return the best-known transit ephemeris for a candidate workspace.

    Probes ``config/`` JSON files (``transit`` or top-level keys) first, then
    ``outputs/bls_search_results.json``. Falls back to a generic demonstration
    ephemeris labelled ``synthetic-demo`` when nothing readable exists.
    """
    result: Dict[str, Any] = {
        "period_days": DEMO_PERIOD_DAYS,
        "epoch_btjd": DEMO_EPOCH_BTJD,
        "duration_days": DEMO_DURATION_DAYS,
        "depth_ppm": DEMO_DEPTH_PPM,
        "source": "synthetic-demo",
    }

    for config_name in EPHEMERIS_CONFIG_NAMES:
        config_path = workspace.path / "config" / config_name
        payload = _read_json(config_path)
        if payload is None:
            continue
        transit = payload.get("transit")
        if not isinstance(transit, dict):
            transit = payload
        period_value = _first_number(transit, ("period", "period_days", "p"))
        epoch_value = _first_number(transit, ("t0", "epoch_btjd", "epoch", "t0_btjd"))
        duration_hours_value = _first_number(
            transit, ("duration_hrs", "duration_hours", "duration_h")
        )
        duration_days_value = _first_number(transit, ("duration_days",))
        depth_value = _first_number(transit, ("depth_ppm", "depth"))
        if period_value is not None and period_value > 0:
            result["period_days"] = period_value
            result["source"] = "candidate-config"
        if epoch_value is not None:
            result["epoch_btjd"] = epoch_value
            result["source"] = "candidate-config"
        if duration_hours_value is not None and duration_hours_value > 0:
            result["duration_days"] = duration_hours_value / 24.0
            result["source"] = "candidate-config"
        if duration_days_value is not None and duration_days_value > 0:
            result["duration_days"] = duration_days_value
            result["source"] = "candidate-config"
        if depth_value is not None and depth_value >= 0:
            result["depth_ppm"] = depth_value
            result["source"] = "candidate-config"
        if result["source"] == "candidate-config":
            break

    if result["source"] != "candidate-config":
        bls_path = workspace.path / "outputs" / "bls_search_results.json"
        payload = _read_json(bls_path)
        if payload is not None:
            period_value = _first_number(payload, ("best_period",))
            epoch_value = _first_number(payload, ("best_epoch",))
            duration_hours_value = _first_number(payload, ("best_duration_hours",))
            depth_value = _first_number(payload, ("best_depth_ppm",))
            if period_value is not None and period_value > 0:
                result["period_days"] = period_value
            if epoch_value is not None:
                result["epoch_btjd"] = epoch_value
            if duration_hours_value is not None and duration_hours_value > 0:
                result["duration_days"] = duration_hours_value / 24.0
            if depth_value is not None and depth_value >= 0:
                result["depth_ppm"] = depth_value
            if period_value is not None or epoch_value is not None:
                result["source"] = "bls-search"

    if result["period_days"] <= 0 or result["duration_days"] <= 0:
        result["period_days"] = DEMO_PERIOD_DAYS
        result["duration_days"] = DEMO_DURATION_DAYS
        result["source"] = "synthetic-demo"
    return result


def load_stellar_parameters(workspace: CandidateWorkspace) -> Dict[str, Any]:
    """Return stellar parameters read from ``data/external/stellar_params.json``.

    Falls back to generic solar demonstration values labelled ``synthetic-demo``.
    """
    result: Dict[str, Any] = {
        "teff_k": DEMO_TEFF_K,
        "logg_cgs": DEMO_LOGG_CGS,
        "feh": DEMO_FEH,
        "mass_solar": DEMO_MASS_SOLAR,
        "radius_solar": DEMO_RADIUS_SOLAR,
        "parallax_mas": DEMO_PARALLAX_MAS,
        "source": "synthetic-demo",
    }
    params_path = workspace.path / "data" / "external" / "stellar_params.json"
    payload = _read_json(params_path)
    if payload is None:
        return result
    values = {
        "teff_k": _first_number(payload, ("teff_k", "teff", "temperature_k")),
        "logg_cgs": _first_number(payload, ("logg_cgs", "logg", "log_g")),
        "feh": _first_number(payload, ("feh", "metallicity")),
        "mass_solar": _first_number(payload, ("mass_solar", "mass_msun", "mass")),
        "radius_solar": _first_number(
            payload, ("radius_solar", "radius_rsun", "radius")
        ),
        "parallax_mas": _first_number(
            payload, ("parallax_mas", "parallax", "plx")
        ),
    }
    if any(value is not None for value in values.values()):
        result["source"] = "candidate-data"
    for name, value in values.items():
        if value is not None:
            result[name] = value
    return result


def load_photometry(workspace: CandidateWorkspace) -> Optional[Dict[str, Any]]:
    """Return broadband photometry from ``data/external/stellar_photometry.json``.

    Expected generic shape: ``{"2MASS": {"J": {"mag":.., "error":..}, ...},
    "AllWISE": {"W1": ...}, "gaia": {"parallax_mas": .., "g_mag": ..}}``.
    Returns None when no readable photometry file exists.
    """
    path = workspace.path / "data" / "external" / "stellar_photometry.json"
    return _read_json(path)


def _mad_flux_error(flux: np.ndarray) -> float:
    median = float(np.median(flux))
    mad = float(np.median(np.abs(flux - median)))
    if not np.isfinite(mad) or mad <= 0:
        return 1.0
    return float(1.4826 * mad)


def _median_bin(
    time: np.ndarray,
    flux: np.ndarray,
    flux_err: np.ndarray,
    sector_values: np.ndarray,
    n_bins: int = 4000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Median-bin a time-sorted table down to at most n_bins rows."""
    if time.size <= n_bins:
        return time, flux, flux_err, sector_values
    order = np.argsort(time)
    time_sorted = time[order]
    flux_sorted = flux[order]
    err_sorted = flux_err[order]
    sector_sorted = sector_values[order]
    edges = np.linspace(0, time_sorted.size, n_bins + 1).astype(int)
    bin_times = np.empty(n_bins, dtype=float)
    bin_flux = np.empty(n_bins, dtype=float)
    bin_err = np.empty(n_bins, dtype=float)
    bin_sector = np.empty(n_bins, dtype=int)
    for index in range(n_bins):
        start, stop = edges[index], edges[index + 1]
        if stop <= start:
            bin_times[index] = np.nan
            bin_flux[index] = np.nan
            bin_err[index] = np.nan
            bin_sector[index] = 0
            continue
        bin_times[index] = float(np.mean(time_sorted[start:stop]))
        bin_flux[index] = float(np.median(flux_sorted[start:stop]))
        bin_err[index] = float(np.median(err_sorted[start:stop]))
        bin_sector[index] = int(
            np.median(sector_sorted[start:stop].astype(float))
        )
    valid = np.isfinite(bin_times) & np.isfinite(bin_flux)
    return (
        bin_times[valid],
        bin_flux[valid],
        bin_err[valid],
        bin_sector[valid],
    )


def load_light_curve_table(
    workspace: CandidateWorkspace, max_points: int = 4000
) -> Optional[Dict[str, np.ndarray]]:
    """Return a light curve table from candidate FITS products, or None.

    The returned dict has ``time``, ``flux`` (normalized), ``flux_err`` and
    ``sector`` (int array). Products are read from ``data/processed/`` first,
    then ``data/raw/``. Returns None when no readable light curve exists.
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
    fits_files = [path for path in fits_files if "tp" not in path.stem.lower()]
    fits_files.sort()
    if not fits_files:
        return None

    try:
        import lightkurve as lk
    except ImportError:  # pragma: no cover - optional dependency
        return None

    tables: List[Dict[str, np.ndarray]] = []
    for path in fits_files:
        try:
            light_curve = lk.read(path).remove_nans().normalize()
            time = np.asarray(light_curve.time.value, dtype=float)
            flux = np.asarray(light_curve.flux.value, dtype=float)
            if time.size < 50 or time.size != flux.size:
                continue
            flux_err = None
            try:
                flux_err = np.asarray(light_curve.flux_err.value, dtype=float)
                if flux_err.shape != flux.shape:
                    flux_err = None
            except Exception:
                flux_err = None
            if flux_err is None:
                flux_err = np.full_like(flux, _mad_flux_error(flux))
            sector_value = None
            try:
                sector_value = int(light_curve.meta.get("SECTOR", 0))
            except (TypeError, ValueError):
                sector_value = None
            if not sector_value or sector_value <= 0:
                sector_value = len(tables) + 1
            sector_values = np.full(time.size, sector_value, dtype=int)
            binned = _median_bin(time, flux, flux_err, sector_values, n_bins=max_points)
            if binned[0].size >= 50:
                tables.append(
                    {
                        "time": binned[0],
                        "flux": binned[1],
                        "flux_err": binned[2],
                        "sector": binned[3],
                    }
                )
        except Exception:
            continue
    if not tables:
        return None

    time = np.concatenate([table["time"] for table in tables])
    flux = np.concatenate([table["flux"] for table in tables])
    flux_err = np.concatenate([table["flux_err"] for table in tables])
    sector_values = np.concatenate([table["sector"] for table in tables])
    if time.size > max_points:
        time, flux, flux_err, sector_values = _median_bin(
            time, flux, flux_err, sector_values, n_bins=max_points
        )
    return {
        "time": time,
        "flux": flux,
        "flux_err": flux_err,
        "sector": sector_values.astype(int),
    }


def load_tpf_cubes(workspace: CandidateWorkspace) -> List[Dict[str, Any]]:
    """Return TPF pixel cubes from candidate data, or an empty list.

    Each entry has ``path``, ``sector``, ``time``, ``quality``, ``flux``
    (n_time x n_y x n_x), ``aperture`` and ``header`` (primary header dict).
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
    fits_files = [path for path in fits_files if "tp" in path.stem.lower()]
    fits_files.sort()
    if not fits_files:
        return []

    try:
        from astropy.io import fits
    except ImportError:  # pragma: no cover - optional dependency
        return []

    cubes: List[Dict[str, Any]] = []
    for path in fits_files:
        try:
            with fits.open(path, memmap=False) as hdul:
                if len(hdul) < 3:
                    continue
                pix_hdu, ap_hdu = hdul[1], hdul[2]
                time = np.asarray(pix_hdu.data["TIME"], dtype=float)
                quality = np.asarray(pix_hdu.data["QUALITY"], dtype=np.int64)
                flux = np.asarray(pix_hdu.data["FLUX"], dtype=float)
                aperture = np.asarray(ap_hdu.data)
                header = dict(hdul[0].header)
                sector_value = None
                for key in ("SECTOR", "SECTOR_NUM"):
                    if key in header:
                        try:
                            sector_value = int(header[key])
                        except (TypeError, ValueError):
                            sector_value = None
                        if sector_value:
                            break
                if not sector_value or sector_value <= 0:
                    sector_value = len(cubes) + 1
                if flux.shape[0] == time.size and time.size >= 50:
                    cubes.append(
                        {
                            "path": path,
                            "sector": int(sector_value),
                            "time": time,
                            "quality": quality,
                            "flux": flux,
                            "aperture": aperture,
                            "header": header,
                        }
                    )
        except Exception:
            continue
    return cubes
