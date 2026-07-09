import json
import re
from pathlib import Path

import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np
from astropy.timeseries import BoxLeastSquares


ROOT = Path(__file__).parent.parent
TARGET = "TIC 81077799"

# NASA Exoplanet Archive / ExoFOP values queried on 2026-07-08.
OFFICIAL_PERIOD = 9.2224171
OFFICIAL_T0_BTJD = 2459314.5211550 - 2457000.0
OFFICIAL_DURATION_HR = 5.2968580
OFFICIAL_DEPTH_PPM = 3109.7617072
OFFICIAL_RADIUS_REARTH = 15.6527771


def parse_sector(mission):
    match = re.search(r"Sector\s+(\d+)", str(mission))
    return int(match.group(1)) if match else -1


def robust_depth(time, flux, period, t0, duration_hr=OFFICIAL_DURATION_HR):
    phase = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    hours = phase * 24.0
    in_mask = np.abs(hours) < 0.5 * duration_hr
    out_mask = (np.abs(hours) > 1.2 * duration_hr) & (np.abs(hours) < 2.5 * duration_hr)
    if in_mask.sum() < 10 or out_mask.sum() < 10:
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


def flatten_lc(lc, mode):
    lc = lc.remove_nans().normalize().remove_outliers(sigma_upper=3, sigma_lower=10)
    if mode == "none":
        return lc
    if mode == "fixed_1001":
        return lc.flatten(window_length=1001)
    if mode == "two_day":
        cadence_days = np.nanmedian(np.diff(np.sort(lc.time.value)))
        window_length = int(round(2.0 / cadence_days))
        if window_length % 2 == 0:
            window_length += 1
        return lc.flatten(window_length=max(window_length, 1001))
    raise ValueError(mode)


def run_bls(time, flux):
    periods = np.linspace(5.0, 22.0, 9000)
    durations = np.array([0.16, 0.20, 0.22, 0.26, 0.32])
    bls = BoxLeastSquares(time, flux)
    power = bls.power(periods, durations)
    best = int(np.nanargmax(power.power))
    official_idx = int(np.argmin(np.abs(power.period - OFFICIAL_PERIOD)))
    double_idx = int(np.argmin(np.abs(power.period - 2 * OFFICIAL_PERIOD)))
    return {
        "best_period_days": float(power.period[best]),
        "best_t0_btjd": float(power.transit_time[best]),
        "best_duration_days": float(power.duration[best]),
        "best_depth_ppm": float(power.depth[best] * 1e6),
        "best_power": float(power.power[best]),
        "power_at_official_period": float(power.power[official_idx]),
        "power_at_double_period": float(power.power[double_idx]),
        "depth_at_official_period_ppm": float(power.depth[official_idx] * 1e6),
        "depth_at_double_period_ppm": float(power.depth[double_idx] * 1e6),
    }, power


def combine(lcs, mode):
    times = []
    fluxes = []
    sectors = []
    for item in lcs:
        lc = flatten_lc(item["lc"], mode)
        t = np.asarray(lc.time.value, dtype=float)
        f = np.asarray(lc.flux.value, dtype=float)
        mask = np.isfinite(t) & np.isfinite(f)
        times.append(t[mask])
        fluxes.append(f[mask])
        sectors.append(np.full(mask.sum(), item["sector"], dtype=int))
    return np.concatenate(times), np.concatenate(fluxes), np.concatenate(sectors)


def main():
    search = lk.search_lightcurve(TARGET, author="SPOC")
    selected = []
    for i, row in enumerate(search.table):
        exptime = float(row.get("exptime", np.nan))
        if abs(exptime - 120.0) > 1.0:
            continue
        sector = parse_sector(row.get("mission", ""))
        print(f"Downloading 120s product: row={i}, sector={sector}")
        selected.append({"idx": i, "sector": sector, "exptime": exptime, "lc": search[i].download()})

    results = {
        "official": {
            "period_days": OFFICIAL_PERIOD,
            "t0_btjd": OFFICIAL_T0_BTJD,
            "duration_hr": OFFICIAL_DURATION_HR,
            "depth_ppm": OFFICIAL_DEPTH_PPM,
            "radius_rearth": OFFICIAL_RADIUS_REARTH,
        },
        "products": [{"idx": x["idx"], "sector": x["sector"], "exptime": x["exptime"]} for x in selected],
        "modes": {},
    }

    fig, axes = plt.subplots(3, 2, figsize=(12, 11))
    for row_idx, mode in enumerate(["none", "fixed_1001", "two_day"]):
        time, flux, sector_labels = combine(selected, mode)
        bls_result, power = run_bls(time, flux)
        depth_official = robust_depth(time, flux, OFFICIAL_PERIOD, OFFICIAL_T0_BTJD)
        depth_double = robust_depth(time, flux, 2 * OFFICIAL_PERIOD, OFFICIAL_T0_BTJD)

        by_sector = {}
        for sector in sorted(set(sector_labels)):
            m = sector_labels == sector
            by_sector[str(sector)] = {
                "n_points": int(m.sum()),
                "official_period_depth": robust_depth(time[m], flux[m], OFFICIAL_PERIOD, OFFICIAL_T0_BTJD),
                "double_period_depth": robust_depth(time[m], flux[m], 2 * OFFICIAL_PERIOD, OFFICIAL_T0_BTJD),
            }

        results["modes"][mode] = {
            "n_points": int(len(time)),
            "median_cadence_min": float(np.nanmedian(np.diff(np.sort(time))) * 24 * 60),
            "bls": bls_result,
            "official_period_depth": depth_official,
            "double_period_depth": depth_double,
            "by_sector": by_sector,
        }

        ax = axes[row_idx, 0]
        ax.plot(power.period, power.power, color="black", linewidth=0.7)
        ax.axvline(OFFICIAL_PERIOD, color="tab:blue", linestyle="--", label="official P")
        ax.axvline(2 * OFFICIAL_PERIOD, color="tab:red", linestyle="--", label="2P")
        ax.set_xlim(5, 22)
        ax.set_ylabel("BLS power")
        ax.set_title(f"120s only, mode={mode}\nBLS best={bls_result['best_period_days']:.4f} d")
        if row_idx == 0:
            ax.legend(fontsize=8)
        if row_idx == 2:
            ax.set_xlabel("Period (d)")

        phase = ((time - OFFICIAL_T0_BTJD + 0.5 * OFFICIAL_PERIOD) % OFFICIAL_PERIOD) - 0.5 * OFFICIAL_PERIOD
        hours = phase * 24.0
        bins = np.linspace(-12, 12, 241)
        centers = 0.5 * (bins[:-1] + bins[1:])
        vals = np.full(len(centers), np.nan)
        for j in range(len(centers)):
            bm = (hours >= bins[j]) & (hours < bins[j + 1])
            if bm.sum() > 5:
                vals[j] = np.nanmedian(flux[bm])
        ax2 = axes[row_idx, 1]
        ax2.scatter(centers, (vals - 1.0) * 1e6, s=8, color="tab:blue")
        ax2.axhline(0, color="gray", linestyle=":")
        ax2.axvline(-OFFICIAL_DURATION_HR / 2, color="tab:red", linestyle=":")
        ax2.axvline(OFFICIAL_DURATION_HR / 2, color="tab:red", linestyle=":")
        ax2.set_ylabel("Median flux - 1 (ppm)")
        ax2.set_title(f"Folded at official P\nrobust depth={depth_official['depth_ppm']:.0f} ppm")
        if row_idx == 2:
            ax2.set_xlabel("Hours from official T0")

        print(
            f"mode={mode}: BLS best={bls_result['best_period_days']:.6f} d; "
            f"depth@official={depth_official['depth_ppm']:.0f} ppm; "
            f"depth@2P={depth_double['depth_ppm']:.0f} ppm"
        )

    plt.tight_layout()
    fig.savefig(ROOT / "figures" / "toi3492_120s_alias_analysis.png", dpi=180)
    plt.close(fig)

    out = ROOT / "outputs" / "alias_120s_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out}")
    print("Wrote toi3492_120s_alias_analysis.png")


if __name__ == "__main__":
    main()
