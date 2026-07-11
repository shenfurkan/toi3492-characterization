"""Run the preregistered preliminary TOI-3492 asteroseismic search.

This script provides reduction and cross-method diagnostics. Its local peak
scores are not calibrated detection probabilities; publication claims require
the null simulations and injection/recovery gates in REVIEW_NOTES.md.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits
from astropy.timeseries import LombScargle
from scipy.ndimage import binary_dilation, gaussian_filter1d, median_filter
from scipy.signal import savgol_filter


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "asteroseismology" / "raw"
OUT_JSON = ROOT / "outputs" / "asteroseismic_preliminary_search.json"
OUT_FIG = ROOT / "figures" / "toi3492_asteroseismic_preliminary.png"

PERIOD_DAYS = 9.2224171
T0_BTJD = 2459314.5211550 - 2457000.0
DURATION_DAYS = 5.232600530809344 / 24.0
SEARCH_MIN_UHZ = 400.0
SEARCH_MAX_UHZ = 1600.0
DNU_MIN_UHZ = 30.0
DNU_MAX_UHZ = 70.0
PSD_MIN_UHZ = 100.0
PSD_MAX_UHZ = 2000.0
BLOCKS = {
    "S37": (37,),
    "S63+64": (63, 64),
    "S90": (90,),
    "S99+100": (99, 100),
}


def parse_product(path):
    match = re.search(r"-s(\d{4})-.*?-(a_fast-lc|s_lc)\.fits$", path.name)
    if not match:
        raise ValueError(f"Unrecognized SPOC filename: {path.name}")
    return int(match.group(1)), 20 if match.group(2) == "a_fast-lc" else 120


def transit_mask(time):
    phase = ((time - T0_BTJD + 0.5 * PERIOD_DAYS) % PERIOD_DAYS) - 0.5 * PERIOD_DAYS
    return np.abs(phase) >= 0.75 * DURATION_DAYS


def symmetric_clip(flux, sigma=7.0):
    median = np.nanmedian(flux)
    mad = 1.4826 * np.nanmedian(np.abs(flux - median))
    if not np.isfinite(mad) or mad <= 0:
        return np.isfinite(flux)
    return np.isfinite(flux) & (np.abs(flux - median) < sigma * mad)


def highpass_segments(time, flux, cadence_seconds, window_days=1.0):
    order = np.argsort(time)
    time = np.asarray(time, dtype=float)[order]
    flux = np.asarray(flux, dtype=float)[order]
    residual = np.full_like(flux, np.nan)
    gaps = np.flatnonzero(np.diff(time) > 5.0 * cadence_seconds / 86400.0) + 1
    edges = np.r_[0, gaps, len(time)]
    nominal_window = int(round(window_days * 86400.0 / cadence_seconds))
    if nominal_window % 2 == 0:
        nominal_window += 1

    for start, stop in zip(edges[:-1], edges[1:]):
        count = stop - start
        window = min(nominal_window, count if count % 2 else count - 1)
        if window < 11:
            continue
        trend = savgol_filter(flux[start:stop], window, 2, mode="interp")
        good = np.isfinite(trend) & (trend != 0)
        segment = np.full(count, np.nan)
        segment[good] = (flux[start:stop][good] / trend[good] - 1.0) * 1e6
        residual[start:stop] = segment
    finite = np.isfinite(residual)
    return time[finite], residual[finite]


def read_lc(path, flux_column):
    sector, cadence = parse_product(path)
    with fits.open(path, memmap=True) as hdul:
        data = hdul[1].data
        time = np.asarray(data["TIME"], dtype=float)
        flux = np.asarray(data[flux_column], dtype=float)
        quality = np.asarray(data["QUALITY"], dtype=np.int64)
    mask = (
        np.isfinite(time)
        & np.isfinite(flux)
        & (flux > 0)
        & (quality == 0)
        & transit_mask(time)
        & symmetric_clip(flux)
    )
    time, residual = highpass_segments(time[mask], flux[mask], cadence)
    return sector, cadence, time, residual


def read_custom_tpf(path):
    name = re.sub(r"([_-])tp\.fits$", r"\1lc.fits", path.name)
    sector, cadence = parse_product(Path(name))
    with fits.open(path, memmap=True) as hdul:
        data = hdul[1].data
        aperture = np.asarray(hdul[2].data)
        optimal = (aperture & 2) != 0
        if optimal.sum() == 0:
            raise RuntimeError(f"No optimal aperture pixels in {path.name}")
        expanded = binary_dilation(optimal, iterations=1)
        time = np.asarray(data["TIME"], dtype=float)
        quality = np.asarray(data["QUALITY"], dtype=np.int64)
        pixel_flux = np.asarray(data["FLUX"], dtype=float)
        flux = np.nansum(pixel_flux[:, expanded], axis=1)
    mask = (
        np.isfinite(time)
        & np.isfinite(flux)
        & (flux > 0)
        & (quality == 0)
        & transit_mask(time)
        & symmetric_clip(flux)
    )
    time, residual = highpass_segments(time[mask], flux[mask], cadence)
    return sector, cadence, time, residual


def power_spectrum(time, flux):
    frequency_day, power = LombScargle(
        time,
        flux - np.nanmean(flux),
        normalization="psd",
    ).autopower(
        minimum_frequency=PSD_MIN_UHZ * 0.0864,
        maximum_frequency=PSD_MAX_UHZ * 0.0864,
        samples_per_peak=1,
        method="fast",
    )
    frequency_uhz = frequency_day / 0.0864
    spacing = float(np.nanmedian(np.diff(frequency_uhz)))
    background_bins = odd_bins(200.0 / spacing)
    smooth_sigma = max(1.0, 20.0 / spacing)
    background = median_filter(power, size=background_bins, mode="nearest")
    background = np.maximum(background, np.finfo(float).tiny)
    whitened = power / background
    envelope = gaussian_filter1d(whitened, smooth_sigma, mode="nearest")
    return frequency_uhz, power, whitened, envelope


def odd_bins(value):
    bins = max(3, int(round(value)))
    return bins if bins % 2 else bins + 1


def spacing_score(frequency, whitened, numax):
    envelope_half_width = 0.66 * numax ** 0.88
    use = np.abs(frequency - numax) <= envelope_half_width
    local_frequency = frequency[use]
    local = whitened[use] - 1.0
    if len(local) < 20:
        return None, None, None
    lags = np.linspace(DNU_MIN_UHZ, DNU_MAX_UHZ, 801)
    scores = np.empty_like(lags)
    for index, lag in enumerate(lags):
        shifted = np.interp(
            local_frequency + lag,
            local_frequency,
            local,
            left=np.nan,
            right=np.nan,
        )
        valid = np.isfinite(shifted)
        if valid.sum() < 10:
            scores[index] = np.nan
            continue
        x = local[valid]
        y = shifted[valid]
        denominator = np.sqrt(np.sum(x * x) * np.sum(y * y))
        scores[index] = np.sum(x * y) / denominator if denominator else np.nan
    best = int(np.nanargmax(scores))
    return float(lags[best]), float(scores[best]), (lags, scores)


def analyze_series(time, flux):
    frequency, power, whitened, envelope = power_spectrum(time, flux)
    search = (frequency >= SEARCH_MIN_UHZ) & (frequency <= SEARCH_MAX_UHZ)
    peak_index = np.flatnonzero(search)[np.nanargmax(envelope[search])]
    numax = float(frequency[peak_index])
    dnu, dnu_score, spacing = spacing_score(frequency, whitened, numax)
    return {
        "n_points": int(len(time)),
        "start_btjd": float(np.min(time)),
        "end_btjd": float(np.max(time)),
        "baseline_days": float(np.max(time) - np.min(time)),
        "rayleigh_uhz": float(1e6 / ((np.max(time) - np.min(time)) * 86400.0)),
        "numax_candidate_uhz": numax,
        "envelope_peak_ratio": float(envelope[peak_index]),
        "dnu_candidate_uhz": dnu,
        "dnu_correlation": dnu_score,
    }, (frequency, power, whitened, envelope, spacing)


def collect(method, cadence):
    per_sector = {}
    if method in {"SAP_FLUX", "PDCSAP_FLUX"}:
        paths = sorted(RAW_DIR.glob("*lc.fits"))
        reader = lambda path: read_lc(path, method)
    else:
        paths = sorted(RAW_DIR.glob("*tp.fits"))
        reader = read_custom_tpf

    for path in paths:
        sector, product_cadence, time, flux = reader(path)
        if product_cadence == cadence:
            per_sector[sector] = (time, flux)
    return per_sector


def main():
    methods = ("SAP_FLUX", "PDCSAP_FLUX", "TPF_EXPANDED_APERTURE")
    results = []
    plot_payload = {}
    for cadence in (120, 20):
        for method in methods:
            per_sector = collect(method, cadence)
            for block, sectors in BLOCKS.items():
                if not all(sector in per_sector for sector in sectors):
                    continue
                time = np.concatenate([per_sector[sector][0] for sector in sectors])
                flux = np.concatenate([per_sector[sector][1] for sector in sectors])
                summary, diagnostic = analyze_series(time, flux)
                row = {
                    "cadence_seconds": cadence,
                    "method": method,
                    "block": block,
                    "sectors": list(sectors),
                    **summary,
                }
                results.append(row)
                plot_payload[(cadence, method, block)] = diagnostic
                print(
                    f"{cadence:3d}s {method:23s} {block:8s}: "
                    f"numax={row['numax_candidate_uhz']:.1f}, "
                    f"dnu={row['dnu_candidate_uhz']:.1f}"
                )

    payload = {
        "status": "preliminary_uncalibrated_diagnostic_not_a_detection",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "preregistered_search": {
            "numax_uhz": [SEARCH_MIN_UHZ, SEARCH_MAX_UHZ],
            "dnu_uhz": [DNU_MIN_UHZ, DNU_MAX_UHZ],
            "quality_mask": "QUALITY == 0",
            "transit_mask_half_width_duration": 0.75,
            "symmetric_clip_sigma_mad": 7.0,
            "highpass_window_days": 1.0,
        },
        "warning": (
            "Candidate maxima and spacing correlations have no calibrated "
            "global false-alarm probability and must not be quoted as seismic results."
        ),
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    make_figure(plot_payload)
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_FIG}")


def make_figure(plot_payload):
    fig, axes = plt.subplots(4, 2, figsize=(12, 13), sharex="col")
    for row_index, block in enumerate(BLOCKS):
        ax_psd, ax_dnu = axes[row_index]
        for method, color in (("SAP_FLUX", "tab:orange"), ("PDCSAP_FLUX", "black")):
            key = (120, method, block)
            if key not in plot_payload:
                continue
            frequency, _, _, envelope, spacing = plot_payload[key]
            ax_psd.plot(frequency, envelope, color=color, lw=0.9, label=method)
            if spacing is not None:
                ax_dnu.plot(spacing[0], spacing[1], color=color, lw=0.9)
        ax_psd.axvspan(400, 1600, color="tab:blue", alpha=0.05)
        ax_psd.set_xlim(100, 2000)
        ax_psd.set_ylabel(f"{block}\nsmoothed P/B")
        ax_dnu.set_xlim(30, 70)
        ax_dnu.axvspan(34, 41, color="tab:green", alpha=0.08)
        ax_dnu.axvspan(55, 63, color="tab:red", alpha=0.06)
        ax_dnu.set_ylabel("spacing corr.")
    axes[0, 0].legend(loc="upper right", fontsize=8)
    axes[-1, 0].set_xlabel("Frequency (microHz)")
    axes[-1, 1].set_xlabel("Trial Delta nu (microHz)")
    fig.suptitle("TOI-3492 preliminary blind seismic diagnostics (not a detection)")
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
