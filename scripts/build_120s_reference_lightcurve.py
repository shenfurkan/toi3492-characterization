"""Build the corrected 120-s SPOC reference light curve for TOI-3492.01.

Downloads all six 120-s cadence SPOC products from MAST via lightkurve,
normalises each sector independently, and concatenates them into a single
reference CSV.  The resulting product is the photometric basis for all
subsequent transit fits and false-positive tests.

Outputs
-------
data/toi3492_120s_reference.csv
    Columns: time (BTJD), flux, flux_err, sector, exptime.
outputs/toi3492_120s_sector_depths.csv
    Robust per-sector in/out window depths.
figures/toi3492_120s_reference_fold.png
    Phase-folded diagnostic plot.

Requires MAST network access.
"""

import re
from pathlib import Path

import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

TARGET = "TIC 81077799"
OFFICIAL_PERIOD = 9.2224171
OFFICIAL_T0_BTJD = 2459314.5211550 - 2457000.0  # BTJD = BJD - 2457000
OFFICIAL_DURATION_HR = 5.2968580


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_sector(mission):
    """Extract the TESS sector number from a MAST mission string.

    Example: ``"TESS Sector 37"`` -> ``37``.
    """
    match = re.search(r"Sector\s+(\d+)", str(mission))
    return int(match.group(1)) if match else -1


def robust_depth(time, flux, period, t0, duration_hr=OFFICIAL_DURATION_HR):
    """Compute a robust median in/out transit depth.

    Uses a simple box: the in-transit window is [-0.5*dur, +0.5*dur];
    the out-of-transit window is [1.2*dur, 2.5*dur] on each side.
    Errors are scaled by 1.253 (robust median estimator factor).

    Returns
    -------
    depth_ppm : float
    depth_err_ppm : float
    n_in : int
    n_out : int
    """
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    hours = phase * 24.0
    in_mask = np.abs(hours) < 0.5 * duration_hr
    out_mask = (np.abs(hours) > 1.2 * duration_hr) & (
        np.abs(hours) < 2.5 * duration_hr
    )
    depth = np.nanmedian(flux[out_mask]) - np.nanmedian(flux[in_mask])
    err = np.sqrt(
        (1.253 * np.nanstd(flux[in_mask]) / np.sqrt(in_mask.sum())) ** 2
        + (1.253 * np.nanstd(flux[out_mask]) / np.sqrt(out_mask.sum())) ** 2
    )
    return depth * 1e6, err * 1e6, int(in_mask.sum()), int(out_mask.sum())


def bin_fold(time, flux, period, t0, limit_hr=14.0, bin_minutes=10.0):
    """Phase-fold and bin the light curve for plotting.

    Returns
    -------
    centers_hr : ndarray
        Bin centre positions (hours from mid-transit).
    med : ndarray
        Median flux per bin.
    err : ndarray
        Robust standard error per bin.
    """
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    hours = phase * 24.0
    mask = np.abs(hours) < limit_hr
    hours = hours[mask]
    flux = flux[mask]
    bins = np.arange(
        -limit_hr, limit_hr + bin_minutes / 60.0, bin_minutes / 60.0
    )
    centers = 0.5 * (bins[:-1] + bins[1:])
    med = np.full_like(centers, np.nan, dtype=float)
    err = np.full_like(centers, np.nan, dtype=float)
    for i in range(len(centers)):
        m = (hours >= bins[i]) & (hours < bins[i + 1])
        if m.sum() >= 3:
            med[i] = np.nanmedian(flux[m])
            err[i] = 1.253 * np.nanstd(flux[m]) / np.sqrt(m.sum())
    return centers, med, err


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ---- Download SPOC products --------------------------------------------
    search = lk.search_lightcurve(TARGET, author="SPOC")
    rows = []
    summary = []

    for i, row in enumerate(search.table):
        exptime = float(row.get("exptime", np.nan))
        # Keep only the 120-s cadence products
        if abs(exptime - 120.0) > 1.0:
            continue

        sector = parse_sector(row.get("mission", ""))
        print(f"Downloading 120s SPOC light curve: row={i}, sector={sector}")

        lc = (
            search[i]
            .download()
            .remove_nans()
            .normalize()
            .remove_outliers(sigma_upper=3, sigma_lower=10)
        )
        t = np.asarray(lc.time.value, dtype=float)
        f = np.asarray(lc.flux.value, dtype=float)
        if lc.flux_err is None:
            e = np.full_like(f, np.nan)
        else:
            e = np.asarray(lc.flux_err.value, dtype=float)
        finite = np.isfinite(t) & np.isfinite(f)
        t, f, e = t[finite], f[finite], e[finite]

        # Normalise each sector by its out-of-transit median
        phase = (
            (t - OFFICIAL_T0_BTJD + 0.5 * OFFICIAL_PERIOD)
            % OFFICIAL_PERIOD
        ) - 0.5 * OFFICIAL_PERIOD
        hours = phase * 24.0
        oot = np.abs(hours) > 1.5 * OFFICIAL_DURATION_HR
        norm = np.nanmedian(f[oot]) if oot.sum() > 20 else np.nanmedian(f)
        f = f / norm
        e = e / norm

        d, de, n_in, n_out = robust_depth(
            t, f, OFFICIAL_PERIOD, OFFICIAL_T0_BTJD
        )
        summary.append(
            {
                "sector": sector,
                "n_points": len(t),
                "depth_ppm": d,
                "depth_err_ppm": de,
                "n_in": n_in,
                "n_out": n_out,
            }
        )
        rows.append(
            pd.DataFrame(
                {
                    "time": t,
                    "flux": f,
                    "flux_err": e,
                    "sector": sector,
                    "exptime": exptime,
                }
            )
        )

    # ---- Concatenate and save -----------------------------------------------
    df = pd.concat(rows, ignore_index=True).sort_values("time")
    out_csv = ROOT / "data" / "toi3492_120s_reference.csv"
    df.to_csv(out_csv, index=False)
    pd.DataFrame(summary).to_csv(
        ROOT / "outputs" / "toi3492_120s_sector_depths.csv", index=False
    )

    # Global robust depth at the official ephemeris
    d_all, de_all, n_in, n_out = robust_depth(
        df["time"].to_numpy(float),
        df["flux"].to_numpy(float),
        OFFICIAL_PERIOD,
        OFFICIAL_T0_BTJD,
    )
    print(f"Wrote {out_csv}")
    print(f"Rows: {len(df):,}")
    print(
        f"Reference depth at official ephemeris: {d_all:.0f} +/- {de_all:.0f} ppm"
    )

    # ---- Plot ---------------------------------------------------------------
    hours, med, err = bin_fold(
        df["time"].to_numpy(float),
        df["flux"].to_numpy(float),
        OFFICIAL_PERIOD,
        OFFICIAL_T0_BTJD,
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.errorbar(
        hours,
        (med - 1.0) * 1e6,
        yerr=err * 1e6,
        fmt="o",
        ms=3,
        color="black",
        ecolor="gray",
    )
    ax.axhline(0, color="tab:gray", linestyle=":")
    ax.axvline(
        -OFFICIAL_DURATION_HR / 2.0,
        color="tab:red",
        linestyle="--",
        label="Official T14 window",
    )
    ax.axvline(OFFICIAL_DURATION_HR / 2.0, color="tab:red", linestyle="--")
    ax.set_xlabel("Hours from official mid-transit")
    ax.set_ylabel("Median normalized flux - 1 (ppm)")
    ax.set_title(
        f"TOI-3492.01 120s SPOC Reference Fold\n"
        f"P={OFFICIAL_PERIOD:.7f} d, depth={d_all:.0f}+/-{de_all:.0f} ppm"
    )
    ax.legend()
    ax.grid(alpha=0.25)
    plt.tight_layout()
    fig.savefig(ROOT / "figures" / "toi3492_120s_reference_fold.png", dpi=180)
    plt.close(fig)
    print("Wrote toi3492_120s_reference_fold.png")
    print("Wrote toi3492_120s_sector_depths.csv")


if __name__ == "__main__":
    main()
