import json
from pathlib import Path

import batman
import corner
import emcee
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from utils import load_config


ROOT = Path(__file__).parent.parent
OFFICIAL_PERIOD = 9.2224171
OFFICIAL_T0_BTJD = 2459314.5211550 - 2457000.0


def phase_bin(time, flux, period, t0, limit_hr=13.0, bin_minutes=8.0):
    phase_days = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    hours = phase_days * 24.0
    mask = np.abs(hours) < limit_hr
    hours = hours[mask]
    phase_days = phase_days[mask]
    flux = flux[mask]
    bins = np.arange(-limit_hr, limit_hr + bin_minutes / 60.0, bin_minutes / 60.0)
    centers_hr = 0.5 * (bins[:-1] + bins[1:])
    centers_days = centers_hr / 24.0
    med = np.full_like(centers_days, np.nan, dtype=float)
    err = np.full_like(centers_days, np.nan, dtype=float)
    for i in range(len(centers_days)):
        m = (hours >= bins[i]) & (hours < bins[i + 1])
        if m.sum() >= 4:
            med[i] = np.nanmedian(flux[m])
            err[i] = 1.253 * np.nanstd(flux[m]) / np.sqrt(m.sum())
    valid = np.isfinite(med) & np.isfinite(err) & (err > 0)
    return centers_days[valid], med[valid], err[valid]


def model_flux(t_days, rp, b, baseline, ar, u1, u2):
    if not (0 <= b < 1 + rp and b < ar):
        return None
    inc = np.degrees(np.arccos(np.clip(b / ar, 0, 1)))
    params = batman.TransitParams()
    params.t0 = 0.0
    params.per = OFFICIAL_PERIOD
    params.rp = rp
    params.a = ar
    params.inc = inc
    params.ecc = 0.0
    params.w = 90.0
    params.u = [u1, u2]
    params.limb_dark = "quadratic"
    return baseline * batman.TransitModel(params, t_days).light_curve(params)


def duration_hours(rp, ar, b):
    inc = np.degrees(np.arccos(np.clip(b / ar, 0, 1)))
    arg = np.sqrt(max((1 + rp) ** 2 - b**2, 0)) / (ar * np.sin(np.radians(inc)))
    return float((OFFICIAL_PERIOD / np.pi) * np.arcsin(np.clip(arg, -1, 1)) * 24.0)


def main():
    config = load_config()
    s = config["stellar"]
    u1 = config["limb_darkening"]["u1"]
    u2 = config["limb_darkening"]["u2"]
    df = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    t = df["time"].to_numpy(float)
    f = df["flux"].to_numpy(float)
    finite = np.isfinite(t) & np.isfinite(f)
    t_bin, f_bin, e_bin = phase_bin(t[finite], f[finite], OFFICIAL_PERIOD, OFFICIAL_T0_BTJD)

    G_msun = 2942.2062
    ar = (G_msun * s["m_star"] * OFFICIAL_PERIOD**2 / (4 * np.pi**2)) ** (1 / 3) / s["r_star"]
    jitter = 120e-6

    def neg_log_post(theta):
        rp, b, baseline = theta
        if not (0.025 < rp < 0.09 and 0.0 <= b < 1.0 + rp and 0.995 < baseline < 1.005):
            return np.inf
        m = model_flux(t_bin, rp, b, baseline, ar, u1, u2)
        if m is None:
            return np.inf
        sigma = np.sqrt(e_bin**2 + jitter**2)
        return 0.5 * np.sum(((f_bin - m) / sigma) ** 2)

    opt = minimize(neg_log_post, [0.056, 0.88, 1.0], method="Nelder-Mead", options={"maxiter": 5000})
    start = opt.x
    print("Optimization:", start, "objective", opt.fun)

    def log_prob(theta):
        val = neg_log_post(theta)
        return -val if np.isfinite(val) else -np.inf

    rng = np.random.default_rng(123)
    nwalkers, ndim = 36, 3
    p0 = start + rng.normal([0, 0, 0], [0.0015, 0.025, 2e-4], size=(nwalkers, ndim))
    p0[:, 0] = np.clip(p0[:, 0], 0.03, 0.08)
    p0[:, 1] = np.clip(p0[:, 1], 0.05, 1.0)
    p0[:, 2] = np.clip(p0[:, 2], 0.997, 1.003)

    sampler = emcee.EnsembleSampler(nwalkers, ndim, log_prob)
    state = sampler.run_mcmc(p0, 1000, progress=True)
    sampler.reset()
    sampler.run_mcmc(state, 2200, progress=True)
    samples = sampler.get_chain(flat=True, discard=250)

    med = np.median(samples, axis=0)
    lo = np.percentile(samples, 16, axis=0)
    hi = np.percentile(samples, 84, axis=0)
    rp, b, baseline = med
    rp_err = max(rp - lo[0], hi[0] - rp)
    b_err = max(b - lo[1], hi[1] - b)
    inc = float(np.degrees(np.arccos(np.clip(b / ar, 0, 1))))
    inc_samples = np.degrees(np.arccos(np.clip(samples[:, 1] / ar, 0, 1)))
    inc_err = max(inc - np.percentile(inc_samples, 16), np.percentile(inc_samples, 84) - inc)
    rp_re = float(rp * s["r_star"] * 109.1)
    rp_re_err = float(rp_re * np.sqrt((rp_err / rp) ** 2 + (s["r_star_err"] / s["r_star"]) ** 2))
    R_sun_AU = 0.00465047
    a_au = float(ar * s["r_star"] * R_sun_AU)
    lum = float(s["r_star"] ** 2 * (s["teff"] / 5772.0) ** 4)
    result = {
        "source": "Corrected 120s reference light curve; official ephemeris fixed; a/Rstar fixed by TIC stellar density",
        "period": OFFICIAL_PERIOD,
        "t0": OFFICIAL_T0_BTJD,
        "rp_rs": float(rp),
        "rp_rs_err": float(rp_err),
        "a_rs": float(ar),
        "impact_parameter": float(b),
        "impact_parameter_err": float(b_err),
        "inc": inc,
        "inc_err": float(inc_err),
        "depth_ppm": float(rp**2 * 1e6),
        "duration_hrs": duration_hours(rp, ar, b),
        "rp_earth": rp_re,
        "rp_earth_err": rp_re_err,
        "a_au": a_au,
        "luminosity_lsun": lum,
        "incident_flux_earth": float(lum / a_au**2),
        "teq_k": float(s["teff"] * np.sqrt(s["r_star"] * R_sun_AU / (2 * a_au))),
        "mcmc_samples": int(samples.shape[0]),
        "mcmc_acceptance_fraction": float(np.mean(sampler.acceptance_fraction)),
        "jitter_ppm": float(jitter * 1e6),
    }

    (ROOT / "outputs" / "transit_fit_120s_density_locked.json").write_text(json.dumps(result, indent=2))
    np.save(ROOT / "outputs" / "toi3492_chains_120s_density_locked.npy", samples)

    fig = corner.corner(samples, labels=["Rp/Rs", "b", "baseline"], show_titles=True, quantiles=[0.16, 0.5, 0.84])
    fig.savefig(ROOT / "figures" / "toi3492_corner_120s_density_locked.png", dpi=160)
    plt.close(fig)

    model = model_flux(t_bin, rp, b, baseline, ar, u1, u2)
    hours = t_bin * 24
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    sigma = np.sqrt(e_bin**2 + jitter**2)
    ax1.errorbar(hours, f_bin, yerr=sigma, fmt="o", ms=3, color="black", ecolor="lightgray")
    ax1.plot(hours, model, color="red", linewidth=2)
    ax1.set_ylabel("Normalized flux")
    ax1.set_title(f"TOI-3492.01 Density-Locked 120s Fit\nRp={rp_re:.1f} Rearth, Rp/Rs={rp:.4f}, b={b:.2f}, a/Rs={ar:.2f}")
    ax2.errorbar(hours, (f_bin - model) * 1e6, yerr=sigma * 1e6, fmt="o", ms=3, color="black", ecolor="lightgray")
    ax2.axhline(0, color="red", linestyle="--")
    ax2.set_xlabel("Hours from official mid-transit")
    ax2.set_ylabel("Residuals (ppm)")
    plt.tight_layout()
    fig.savefig(ROOT / "figures" / "toi3492_transit_fit_120s_density_locked.png", dpi=180)
    plt.close(fig)

    print(json.dumps(result, indent=2))
    print("Wrote transit_fit_120s_density_locked.json")


if __name__ == "__main__":
    main()
