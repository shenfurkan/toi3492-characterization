import json
import re
from pathlib import Path

import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astropy.timeseries import BoxLeastSquares


ROOT = Path(__file__).parent.parent
TARGET = "TIC 81077799"
SECTORS_20S = {90, 99, 100}

OFFICIAL_PERIOD = 9.2224171
OFFICIAL_T0_BTJD = 2459314.5211550 - 2457000.0
OFFICIAL_DURATION_HR = 5.2968580

OUT_REFERENCE = ROOT / "data" / "toi3492_20s_reference.csv"
OUT_DEPTHS = ROOT / "outputs" / "toi3492_20s_sector_depths.csv"
OUT_ALIAS = ROOT / "outputs" / "alias_20s_results.json"
OUT_CHECK = ROOT / "outputs" / "cadence_independent_depth_check.json"
FIG_FOLD = ROOT / "figures" / "toi3492_20s_reference_fold.png"
FIG_COMPARE = ROOT / "figures" / "toi3492_20s_vs_120s_depth.png"


def parse_sector(mission):
    match = re.search(r"Sector\s+(\d+)", str(mission))
    return int(match.group(1)) if match else -1


def robust_depth(time, flux, period=OFFICIAL_PERIOD, t0=OFFICIAL_T0_BTJD, duration_hr=OFFICIAL_DURATION_HR):
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    hours = phase * 24.0
    in_mask = np.abs(hours) < 0.5 * duration_hr
    out_mask = (np.abs(hours) > 1.2 * duration_hr) & (np.abs(hours) < 2.5 * duration_hr)
    if in_mask.sum() < 20 or out_mask.sum() < 20:
        return None
    in_flux = flux[in_mask]
    out_flux = flux[out_mask]
    depth = np.nanmedian(out_flux) - np.nanmedian(in_flux)
    err = np.sqrt(
        (1.253 * np.nanstd(in_flux) / np.sqrt(in_mask.sum())) ** 2
        + (1.253 * np.nanstd(out_flux) / np.sqrt(out_mask.sum())) ** 2
    )
    return {
        "depth_ppm": float(depth * 1e6),
        "depth_err_ppm": float(err * 1e6),
        "n_in": int(in_mask.sum()),
        "n_out": int(out_mask.sum()),
    }


def normalize_sector(time, flux, flux_err):
    phase = ((time - OFFICIAL_T0_BTJD + 0.5 * OFFICIAL_PERIOD) % OFFICIAL_PERIOD) - 0.5 * OFFICIAL_PERIOD
    hours = phase * 24.0
    oot = np.abs(hours) > 1.5 * OFFICIAL_DURATION_HR
    norm = np.nanmedian(flux[oot]) if oot.sum() > 50 else np.nanmedian(flux)
    return flux / norm, flux_err / norm


def bin_time_series(time, flux, bin_seconds=120.0):
    bin_days = bin_seconds / 86400.0
    order = np.argsort(time)
    time = time[order]
    flux = flux[order]
    bins = np.floor((time - time.min()) / bin_days).astype(int)
    df = pd.DataFrame({"time": time, "flux": flux, "bin": bins})
    grouped = df.groupby("bin", sort=True)
    out = grouped.agg(time=("time", "median"), flux=("flux", "median"), n=("flux", "size")).reset_index(drop=True)
    return out["time"].to_numpy(float), out["flux"].to_numpy(float), out["n"].to_numpy(int)


def run_bls(time, flux):
    periods = np.linspace(5.0, 22.0, 7000)
    durations = np.array([0.16, 0.20, 0.22, 0.26, 0.32])
    bls = BoxLeastSquares(time, flux)
    power = bls.power(periods, durations)
    best = int(np.nanargmax(power.power))
    official_idx = int(np.argmin(np.abs(power.period - OFFICIAL_PERIOD)))
    double_idx = int(np.argmin(np.abs(power.period - 2 * OFFICIAL_PERIOD)))
    return {
        "n_binned_points": int(len(time)),
        "best_period_days": float(power.period[best]),
        "best_t0_btjd": float(power.transit_time[best]),
        "best_duration_days": float(power.duration[best]),
        "best_depth_ppm": float(power.depth[best] * 1e6),
        "best_power": float(power.power[best]),
        "power_at_official_period": float(power.power[official_idx]),
        "power_at_double_period": float(power.power[double_idx]),
        "depth_at_official_period_ppm": float(power.depth[official_idx] * 1e6),
        "depth_at_double_period_ppm": float(power.depth[double_idx] * 1e6),
        "official_to_best_power_ratio": float(power.power[official_idx] / power.power[best]) if power.power[best] else None,
        "double_to_best_power_ratio": float(power.power[double_idx] / power.power[best]) if power.power[best] else None,
    }, power


def bin_fold(time, flux, limit_hr=14.0, bin_minutes=5.0):
    phase = ((time - OFFICIAL_T0_BTJD + 0.5 * OFFICIAL_PERIOD) % OFFICIAL_PERIOD) - 0.5 * OFFICIAL_PERIOD
    hours = phase * 24.0
    mask = np.abs(hours) < limit_hr
    hours = hours[mask]
    flux = flux[mask]
    bins = np.arange(-limit_hr, limit_hr + bin_minutes / 60.0, bin_minutes / 60.0)
    centers = 0.5 * (bins[:-1] + bins[1:])
    med = np.full(len(centers), np.nan)
    err = np.full(len(centers), np.nan)
    count = np.zeros(len(centers), dtype=int)
    for i in range(len(centers)):
        m = (hours >= bins[i]) & (hours < bins[i + 1])
        count[i] = int(m.sum())
        if m.sum() >= 10:
            med[i] = np.nanmedian(flux[m])
            err[i] = 1.253 * np.nanstd(flux[m]) / np.sqrt(m.sum())
    return centers, med, err, count


def main():
    try:
        search = lk.search_lightcurve(TARGET, author="SPOC")
    except Exception as exc:
        blocked = {
            "source": "20 s-only SPOC independent cadence check; not used in adopted transit fit",
            "status": "blocked_mast_query_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "interpretation": "No 20 s scientific result is available. MAST/STScI HTTPS is unreachable from this network (confirmed by urllib and PowerShell tests: mast.stsci.edu and archive.stsci.edu timeout/SSL error regardless of verify_ssl setting, while NASA Exoplanet Archive and other hosts work). This is a network-level firewall block, not a Python TLS configuration issue. Re-run when network access to STScI is restored.",
        }
        OUT_CHECK.write_text(json.dumps(blocked, indent=2))
        print(f"Wrote blocked status to {OUT_CHECK}")
        raise
    selected = []
    for i, row in enumerate(search.table):
        exptime = float(row.get("exptime", np.nan))
        sector = parse_sector(row.get("mission", ""))
        if abs(exptime - 20.0) > 1.0 or sector not in SECTORS_20S:
            continue
        selected.append({"idx": i, "sector": sector, "exptime": exptime})

    if not selected:
        raise RuntimeError("No 20 s SPOC products found for sectors 90, 99, and 100.")

    rows = []
    depths = []
    for item in selected:
        print(f"Downloading 20s SPOC light curve: row={item['idx']}, sector={item['sector']}")
        lc = search[item["idx"]].download().remove_nans().normalize().remove_outliers(sigma_upper=3, sigma_lower=10)
        time = np.asarray(lc.time.value, dtype=float)
        flux = np.asarray(lc.flux.value, dtype=float)
        if lc.flux_err is None:
            flux_err = np.full_like(flux, np.nan)
        else:
            flux_err = np.asarray(lc.flux_err.value, dtype=float)
        finite = np.isfinite(time) & np.isfinite(flux)
        time = time[finite]
        flux = flux[finite]
        flux_err = flux_err[finite]
        flux, flux_err = normalize_sector(time, flux, flux_err)

        depth = robust_depth(time, flux)
        depth_row = {
            "sector": item["sector"],
            "n_points": int(len(time)),
            "exptime": item["exptime"],
        }
        if depth:
            depth_row.update(depth)
        depths.append(depth_row)
        rows.append(pd.DataFrame({"time": time, "flux": flux, "flux_err": flux_err, "sector": item["sector"], "exptime": item["exptime"]}))

    df = pd.concat(rows, ignore_index=True).sort_values("time")
    df.to_csv(OUT_REFERENCE, index=False)
    depth_df = pd.DataFrame(depths).sort_values("sector")
    depth_df.to_csv(OUT_DEPTHS, index=False)

    time = df["time"].to_numpy(float)
    flux = df["flux"].to_numpy(float)
    combined_depth = robust_depth(time, flux)
    double_depth = robust_depth(time, flux, period=2.0 * OFFICIAL_PERIOD)
    binned_time, binned_flux, bin_counts = bin_time_series(time, flux, bin_seconds=120.0)
    bls_result, power = run_bls(binned_time, binned_flux)

    alias_results = {
        "source": "20 s SPOC products only; BLS run on 120 s median bins made from 20 s data",
        "products": selected,
        "median_cadence_seconds": float(np.nanmedian(np.diff(np.sort(time))) * 86400.0),
        "n_points": int(len(time)),
        "n_binned_points_for_bls": int(len(binned_time)),
        "official": {
            "period_days": OFFICIAL_PERIOD,
            "t0_btjd": OFFICIAL_T0_BTJD,
            "duration_hr": OFFICIAL_DURATION_HR,
        },
        "bls": bls_result,
        "official_period_depth": combined_depth,
        "double_period_depth": double_depth,
        "by_sector": depth_df.to_dict(orient="records"),
    }
    OUT_ALIAS.write_text(json.dumps(alias_results, indent=2))

    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    local_depth = float(config["transit"]["depth_ppm"])
    comparison = {
        "source": "20 s-only SPOC independent cadence check; not used in adopted transit fit",
        "sectors": sorted(SECTORS_20S),
        "n_points_20s": int(len(df)),
        "combined_20s_depth_ppm": combined_depth["depth_ppm"] if combined_depth else None,
        "combined_20s_depth_err_ppm": combined_depth["depth_err_ppm"] if combined_depth else None,
        "adopted_120s_model_depth_ppm": local_depth,
        "delta_20s_minus_120s_model_ppm": (combined_depth["depth_ppm"] - local_depth) if combined_depth else None,
        "delta_20s_minus_120s_model_sigma_formal": ((combined_depth["depth_ppm"] - local_depth) / combined_depth["depth_err_ppm"]) if combined_depth else None,
        "bls_best_period_days": bls_result["best_period_days"],
        "official_to_best_power_ratio": bls_result["official_to_best_power_ratio"],
        "double_to_best_power_ratio": bls_result["double_to_best_power_ratio"],
        "interpretation": "The 20 s data are an independent cadence check. They should support the several-thousand-ppm depth scale, but the adopted physical fit remains the six-sector 120 s analysis to avoid duplicate sector weighting.",
        "outputs": {
            "reference_csv": str(OUT_REFERENCE.relative_to(ROOT)),
            "sector_depths_csv": str(OUT_DEPTHS.relative_to(ROOT)),
            "alias_json": str(OUT_ALIAS.relative_to(ROOT)),
            "fold_figure": str(FIG_FOLD.relative_to(ROOT)),
            "comparison_figure": str(FIG_COMPARE.relative_to(ROOT)),
        },
    }
    OUT_CHECK.write_text(json.dumps(comparison, indent=2))

    hours, med, err, count = bin_fold(time, flux)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.errorbar(hours, (med - 1.0) * 1e6, yerr=err * 1e6, fmt="o", ms=3, color="black", ecolor="gray")
    ax.axhline(0, color="tab:gray", linestyle=":")
    ax.axvline(-OFFICIAL_DURATION_HR / 2.0, color="tab:red", linestyle="--", label="Official T14 window")
    ax.axvline(OFFICIAL_DURATION_HR / 2.0, color="tab:red", linestyle="--")
    ax.set_xlabel("Hours from official mid-transit")
    ax.set_ylabel("Median normalized flux - 1 (ppm)")
    ax.set_title(
        "TOI-3492.01 20s SPOC Independent Fold\n"
        f"Sectors 90/99/100, depth={combined_depth['depth_ppm']:.0f}+/-{combined_depth['depth_err_ppm']:.0f} ppm"
    )
    ax.legend()
    ax.grid(alpha=0.25)
    plt.tight_layout()
    fig.savefig(FIG_FOLD, dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(depth_df))
    ax.errorbar(x - 0.08, depth_df["depth_ppm"], yerr=depth_df["depth_err_ppm"], fmt="o", label="20 s", color="tab:blue")
    depth_120_path = ROOT / "outputs" / "toi3492_120s_sector_depths.csv"
    if depth_120_path.exists():
        d120 = pd.read_csv(depth_120_path)
        d120 = d120[d120["sector"].isin(depth_df["sector"])]
        d120 = d120.set_index("sector").loc[depth_df["sector"]].reset_index()
        ax.errorbar(x + 0.08, d120["depth_ppm"], yerr=d120["depth_err_ppm"], fmt="s", label="120 s", color="tab:orange")
    ax.axhline(local_depth, color="black", linestyle=":", label="120 s model depth")
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(s)) for s in depth_df["sector"]])
    ax.set_xlabel("Sector")
    ax.set_ylabel("Robust fixed-window depth (ppm)")
    ax.set_title("20 s vs 120 s independent sector-depth check")
    ax.grid(alpha=0.25)
    ax.legend()
    plt.tight_layout()
    fig.savefig(FIG_COMPARE, dpi=180)
    plt.close(fig)

    print(f"Wrote {OUT_REFERENCE}")
    print(f"Wrote {OUT_DEPTHS}")
    print(f"Wrote {OUT_ALIAS}")
    print(f"Wrote {OUT_CHECK}")
    print(f"Wrote {FIG_FOLD}")
    print(f"Wrote {FIG_COMPARE}")
    print(
        f"20s combined depth: {combined_depth['depth_ppm']:.0f}+/-{combined_depth['depth_err_ppm']:.0f} ppm; "
        f"BLS best period: {bls_result['best_period_days']:.6f} d"
    )


if __name__ == "__main__":
    main()
