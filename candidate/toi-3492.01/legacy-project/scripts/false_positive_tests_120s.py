"""Corrected 120-s false-positive diagnostics for TOI-3492.01.

Performs two classic transit-vetting checks on the corrected reference
light curve:

    1. Odd/even transit depth comparison
       Measures the robust median depth of odd- and even-numbered transits
       separately.  A significant difference indicates an eclipsing binary
       with unequal primary and secondary depths.

    2. Secondary eclipse search at phase 0.5
       Measures the robust median depth in a transit-duration window
       centred at the expected secondary-eclipse phase.  A significant
       detection indicates a blended eclipsing binary.

Outputs
-------
outputs/false_positive_tests_120s.json    Summary of both tests.
outputs/toi3492_120s_event_depths.csv     Per-event depth measurements.
figures/toi3492_false_positive_120s.png    Diagnostic plot.

These checks reduce obvious eclipsing-binary concerns but do not replace
Gaia, centroid, imaging, or RV validation.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
REFERENCE_PATH = ROOT / "data" / "toi3492_120s_reference.csv"
OUT_JSON = ROOT / "outputs" / "false_positive_tests_120s.json"
OUT_EVENTS = ROOT / "outputs" / "toi3492_120s_event_depths.csv"
OUT_FIG = ROOT / "figures" / "toi3492_false_positive_120s.png"


# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------

def _json_clean(value):
    """Recursively convert numpy/Pandas types to native Python for JSON."""
    if isinstance(value, dict):
        return {str(k): _json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if pd.isna(value):
        return None
    return value


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------

def _phase_days(time, t0, period):
    """Return orbital phase (days) relative to mid-transit.

    Phase is in [-0.5*period, 0.5*period).
    """
    return ((time - t0 + 0.5 * period) % period) - 0.5 * period


# ---------------------------------------------------------------------------
# Robust depth measurement
# ---------------------------------------------------------------------------

def _robust_depth(hours, flux, duration_hr):
    """Measure a robust median in/out transit depth.

    In-transit window:  [-0.5*dur, +0.5*dur]
    Out-of-transit:     [1.2*dur, 2.5*dur] on each side.

    Returns None if fewer than 10 cadences fall in either window.
    """
    in_mask = np.abs(hours) < 0.5 * duration_hr
    out_mask = (np.abs(hours) > 1.2 * duration_hr) & (
        np.abs(hours) < 2.5 * duration_hr
    )
    if in_mask.sum() < 10 or out_mask.sum() < 10:
        return None
    in_flux = flux[in_mask]
    out_flux = flux[out_mask]
    depth = np.nanmedian(out_flux) - np.nanmedian(in_flux)
    # 1.253 = sqrt(pi/2) robust-to-Gaussian conversion factor
    in_err = 1.253 * np.nanstd(in_flux) / np.sqrt(in_mask.sum())
    out_err = 1.253 * np.nanstd(out_flux) / np.sqrt(out_mask.sum())
    return {
        "depth_ppm": depth * 1e6,
        "depth_err_ppm": np.sqrt(in_err ** 2 + out_err ** 2) * 1e6,
        "n_in": int(in_mask.sum()),
        "n_out": int(out_mask.sum()),
    }


def _weighted_mean(values, errors):
    """Inverse-variance weighted mean of per-event measurements."""
    values = np.asarray(values, dtype=float)
    errors = np.asarray(errors, dtype=float)
    valid = np.isfinite(values) & np.isfinite(errors) & (errors > 0)
    if valid.sum() == 0:
        return {"depth_ppm": np.nan, "depth_err_ppm": np.nan, "n": 0}
    weights = 1.0 / errors[valid] ** 2
    mean = np.sum(weights * values[valid]) / np.sum(weights)
    err = np.sqrt(1.0 / np.sum(weights))
    return {"depth_ppm": mean, "depth_err_ppm": err, "n": int(valid.sum())}


# ---------------------------------------------------------------------------
# Binning for plotting
# ---------------------------------------------------------------------------

def _bin_series(hours, flux, limit_hr, bin_minutes=12.0):
    """Median-bin a time series for visualisation.

    Returns (centres, median, error, count) for bins with >= 4 points.
    """
    bins = np.arange(
        -limit_hr, limit_hr + bin_minutes / 60.0, bin_minutes / 60.0
    )
    centers = 0.5 * (bins[:-1] + bins[1:])
    med = np.full_like(centers, np.nan, dtype=float)
    err = np.full_like(centers, np.nan, dtype=float)
    count = np.zeros_like(centers, dtype=int)
    for i in range(len(centers)):
        mask = (hours >= bins[i]) & (hours < bins[i + 1])
        count[i] = int(mask.sum())
        if mask.sum() >= 4:
            med[i] = np.nanmedian(flux[mask])
            err[i] = 1.253 * np.nanstd(flux[mask]) / np.sqrt(mask.sum())
    valid = np.isfinite(med) & np.isfinite(err)
    return centers[valid], med[valid], err[valid], count[valid]


# ---------------------------------------------------------------------------
# Per-event depth extraction
# ---------------------------------------------------------------------------

def _event_depths(time, flux, sector, period, t0, duration_hr):
    """Measure robust depths for every individual transit epoch.

    Returns a DataFrame with columns:
    epoch, t_mid_btjd, parity, sector, n_points_window, depth_ppm,
    depth_err_ppm, n_in, n_out.
    """
    rows = []
    n_min = int(np.floor((np.nanmin(time) - t0) / period))
    n_max = int(np.ceil((np.nanmax(time) - t0) / period))
    window_hr = 2.5 * duration_hr
    for epoch in range(n_min, n_max + 1):
        mid = t0 + epoch * period
        hours = (time - mid) * 24.0
        mask = np.abs(hours) < window_hr
        if mask.sum() < 30:
            continue
        depth = _robust_depth(hours[mask], flux[mask], duration_hr)
        if depth is None:
            continue
        sectors, counts = np.unique(sector[mask], return_counts=True)
        dominant_sector = int(sectors[np.argmax(counts)])
        rows.append(
            {
                "epoch": int(epoch),
                "t_mid_btjd": float(mid),
                "parity": "even" if epoch % 2 == 0 else "odd",
                "sector": dominant_sector,
                "n_points_window": int(mask.sum()),
                **depth,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def _plot(time, flux, period, t0, duration_hr):
    """Draw the odd/even and secondary-eclipse diagnostic figure."""
    window_hr = 2.5 * duration_hr

    epoch = np.rint((time - t0) / period).astype(int)
    transit_hours = (time - (t0 + epoch * period)) * 24.0
    transit_mask = np.abs(transit_hours) < window_hr
    odd_mask = transit_mask & (epoch % 2 != 0)
    even_mask = transit_mask & (epoch % 2 == 0)

    secondary_hours = _phase_days(time, t0 + 0.5 * period, period) * 24.0
    secondary_mask = np.abs(secondary_hours) < window_hr

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # ---- Odd / Even ---------------------------------------------------------
    for mask, label, color in [
        (odd_mask, "odd epochs", "tab:red"),
        (even_mask, "even epochs", "tab:blue"),
    ]:
        x, y, yerr, _ = _bin_series(
            transit_hours[mask], flux[mask], window_hr
        )
        ax1.errorbar(
            x,
            (y - 1.0) * 1e6,
            yerr=yerr * 1e6,
            fmt="o",
            ms=3,
            capsize=2,
            color=color,
            label=label,
        )
    ax1.axvline(
        -0.5 * duration_hr, color="tab:gray", linestyle="--", linewidth=1
    )
    ax1.axvline(
        0.5 * duration_hr, color="tab:gray", linestyle="--", linewidth=1
    )
    ax1.axhline(0, color="black", linestyle=":", linewidth=1)
    ax1.set_xlabel("Hours from transit midpoint")
    ax1.set_ylabel("Median normalized flux - 1 (ppm)")
    ax1.set_title("Corrected 120s Odd/Even Test")
    ax1.grid(alpha=0.25)
    ax1.legend()

    # ---- Secondary eclipse --------------------------------------------------
    x, y, yerr, _ = _bin_series(
        secondary_hours[secondary_mask], flux[secondary_mask], window_hr
    )
    ax2.errorbar(
        x,
        (y - 1.0) * 1e6,
        yerr=yerr * 1e6,
        fmt="o",
        ms=3,
        capsize=2,
        color="black",
    )
    ax2.axvline(
        -0.5 * duration_hr, color="tab:gray", linestyle="--", linewidth=1
    )
    ax2.axvline(
        0.5 * duration_hr, color="tab:gray", linestyle="--", linewidth=1
    )
    ax2.axhline(0, color="black", linestyle=":", linewidth=1)
    ax2.set_xlabel("Hours from phase 0.5")
    ax2.set_ylabel("Median normalized flux - 1 (ppm)")
    ax2.set_title("Corrected 120s Secondary-Eclipse Search")
    ax2.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=180)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config = json.loads(CONFIG_PATH.read_text())
    transit = config["transit_corrected_120s"]
    period = float(transit["period"])
    t0 = float(transit["t0"])
    duration_hr = float(transit["duration_hrs"])
    model_depth_ppm = float(transit["depth_ppm"])

    df = pd.read_csv(REFERENCE_PATH)
    finite = (
        np.isfinite(df["time"])
        & np.isfinite(df["flux"])
        & np.isfinite(df["sector"])
    )
    if "flux_err" in df.columns:
        finite = finite & np.isfinite(df["flux_err"])
    df = df.loc[finite].copy()
    time = df["time"].to_numpy(float)
    flux = df["flux"].to_numpy(float)
    sector = df["sector"].to_numpy(int)

    # ---- Per-event depths ---------------------------------------------------
    events = _event_depths(time, flux, sector, period, t0, duration_hr)
    events.to_csv(OUT_EVENTS, index=False)

    # ---- Odd / Even comparison ----------------------------------------------
    odd = events[events["parity"] == "odd"]
    even = events[events["parity"] == "even"]
    odd_mean = _weighted_mean(odd["depth_ppm"], odd["depth_err_ppm"])
    even_mean = _weighted_mean(even["depth_ppm"], even["depth_err_ppm"])
    diff = abs(odd_mean["depth_ppm"] - even_mean["depth_ppm"])
    diff_err = np.sqrt(
        odd_mean["depth_err_ppm"] ** 2 + even_mean["depth_err_ppm"] ** 2
    )
    diff_sigma = diff / diff_err if diff_err > 0 else np.nan

    # ---- Secondary eclipse at phase 0.5 -------------------------------------
    secondary_hours = (
        _phase_days(time, t0 + 0.5 * period, period) * 24.0
    )
    secondary = _robust_depth(secondary_hours, flux, duration_hr)
    secondary_sigma = (
        secondary["depth_ppm"] / secondary["depth_err_ppm"]
        if secondary and secondary["depth_err_ppm"] > 0
        else np.nan
    )
    secondary_upper_3sigma = max(0.0, secondary["depth_ppm"]) + 3.0 * secondary[
        "depth_err_ppm"
    ]

    _plot(time, flux, period, t0, duration_hr)

    # ---- Assemble result ----------------------------------------------------
    result = {
        "source": "Corrected 120s SPOC reference light curve",
        "inputs": {
            "config": CONFIG_PATH.name,
            "reference_csv": REFERENCE_PATH.name,
            "period_days": period,
            "t0_btjd": t0,
            "duration_hours": duration_hr,
            "model_depth_ppm": model_depth_ppm,
        },
        "event_depths": {
            "n_events_used": int(len(events)),
            "n_odd_events": int(len(odd)),
            "n_even_events": int(len(even)),
            "event_depth_csv": OUT_EVENTS.name,
        },
        "odd_even": {
            "odd_depth_ppm": odd_mean["depth_ppm"],
            "odd_depth_err_ppm": odd_mean["depth_err_ppm"],
            "even_depth_ppm": even_mean["depth_ppm"],
            "even_depth_err_ppm": even_mean["depth_err_ppm"],
            "absolute_difference_ppm": diff,
            "difference_sigma": diff_sigma,
            "passes_3sigma_check": bool(
                np.isfinite(diff_sigma) and diff_sigma < 3.0
            ),
        },
        "secondary_eclipse": {
            "phase_checked": 0.5,
            "depth_ppm": secondary["depth_ppm"],
            "depth_err_ppm": secondary["depth_err_ppm"],
            "significance_sigma": secondary_sigma,
            "three_sigma_upper_limit_ppm": secondary_upper_3sigma,
            "passes_no_secondary_3sigma_check": bool(
                np.isfinite(secondary_sigma) and abs(secondary_sigma) < 3.0
            ),
            "n_in": secondary["n_in"],
            "n_out": secondary["n_out"],
        },
        "outputs": {
            "summary_json": OUT_JSON.name,
            "event_depth_csv": OUT_EVENTS.name,
            "plot": OUT_FIG.name,
        },
        "notes": [
            "Odd/even means are weighted means of per-event robust median depths.",
            "The secondary-eclipse check measures a transit-duration window "
            "centered at phase 0.5.",
            "These tests reduce obvious eclipsing-binary concerns but do not "
            "replace Gaia, centroid, imaging, or RV validation.",
        ],
    }

    OUT_JSON.write_text(json.dumps(_json_clean(result), indent=2))
    print(f"Wrote {OUT_JSON.name}")
    print(f"Wrote {OUT_EVENTS.name}")
    print(f"Wrote {OUT_FIG.name}")
    print(
        "Odd/even depths: "
        f"{odd_mean['depth_ppm']:.0f} +/- {odd_mean['depth_err_ppm']:.0f} ppm vs "
        f"{even_mean['depth_ppm']:.0f} +/- {even_mean['depth_err_ppm']:.0f} ppm "
        f"({diff_sigma:.2f} sigma)"
    )
    print(
        "Secondary depth: "
        f"{secondary['depth_ppm']:.0f} +/- {secondary['depth_err_ppm']:.0f} ppm "
        f"({secondary_sigma:.2f} sigma); "
        f"3sigma upper limit {secondary_upper_3sigma:.0f} ppm"
    )


if __name__ == "__main__":
    main()
