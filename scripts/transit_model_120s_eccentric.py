import json
from pathlib import Path

import batman
import corner
import emcee
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import beta as beta_distribution

from science import eccentric_cosi, transit_duration_hours
from utils import load_config


ROOT = Path(__file__).parent.parent
OFFICIAL_PERIOD = 9.2224171
OFFICIAL_T0_BTJD = 2459314.5211550 - 2457000.0
BURNIN_STEPS = 1500
PRODUCTION_STEPS = 3000
FLAT_DISCARD_STEPS = 400
NWALKERS = 50


def load_reference():
    df = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    time = df["time"].to_numpy(float)
    flux = df["flux"].to_numpy(float)
    sector = df["sector"].to_numpy(int)
    finite = np.isfinite(time) & np.isfinite(flux)
    return time[finite], flux[finite], sector[finite]


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
    n = np.zeros_like(centers_days, dtype=int)
    for i in range(len(centers_days)):
        m = (hours >= bins[i]) & (hours < bins[i + 1])
        n[i] = int(m.sum())
        if m.sum() >= 4:
            med[i] = np.nanmedian(flux[m])
            err[i] = 1.253 * np.nanstd(flux[m]) / np.sqrt(m.sum())
    valid = np.isfinite(med) & np.isfinite(err) & (err > 0)
    return centers_days[valid], med[valid], err[valid], n[valid]


def model_flux(t_days, rp, ar, b, baseline, u1, u2, ecc, omega):
    if ar <= 0 or b < 0 or b >= 1.0 + rp:
        return None
    cosi = eccentric_cosi(ar, b, ecc, omega)
    if cosi < 0 or cosi > 1:
        return None
    inc = np.degrees(np.arccos(cosi))
    params = batman.TransitParams()
    params.t0 = 0.0
    params.per = OFFICIAL_PERIOD
    params.rp = rp
    params.a = ar
    params.inc = inc
    params.ecc = ecc
    params.w = omega
    params.u = [u1, u2]
    params.limb_dark = "quadratic"
    return baseline * batman.TransitModel(
        params,
        t_days,
        supersample_factor=7,
        exp_time=8.0 / 1440.0,
    ).light_curve(params)


def duration_hours(rp, ar, b, ecc, omega):
    return float(
        transit_duration_hours(OFFICIAL_PERIOD, rp, ar, b, ecc, omega)
    )


def main():
    config = load_config()
    stellar = config["stellar"]
    u1 = config["limb_darkening"]["u1"]
    u2 = config["limb_darkening"]["u2"]

    time, flux, sector = load_reference()
    t_bin, f_bin, e_bin, n_bin = phase_bin(time, flux, OFFICIAL_PERIOD, OFFICIAL_T0_BTJD)

    G_msun = 2942.2062
    ar_prior = (G_msun * stellar["m_star"] * OFFICIAL_PERIOD**2 / (4 * np.pi**2)) ** (1 / 3) / stellar["r_star"]
    ar_sigma = max(ar_prior * stellar["rho_star_err"] / (3 * stellar["rho_star"]), 0.5)
    jitter = 120e-6

    rp_guess = 0.056
    ar_guess = ar_prior
    b_guess = 0.80
    ecc_guess = 0.0
    omega_guess = 90.0
    baseline_guess = 1.0

    def neg_log_post(theta):
        rp, ar, b, log_baseline, esinw, ecosw = theta
        baseline = np.exp(log_baseline)
        ecc = esinw**2 + ecosw**2
        if not (
            0.025 < rp < 0.09
            and 4.0 < ar < 13.0
            and 0.0 <= b < 1.0 + rp
            and 0.0 <= ecc < 0.8
            and 0.995 < baseline < 1.005
        ):
            return np.inf
        omega = np.degrees(np.arctan2(esinw, ecosw)) % 360
        if ar * (1.0 - ecc) <= 1.0 + rp:
            return np.inf
        m = model_flux(t_bin, rp, ar, b, baseline, u1, u2, ecc, omega)
        if m is None:
            return np.inf
        sigma = np.sqrt(e_bin**2 + jitter**2)
        chi2 = np.sum(((f_bin - m) / sigma) ** 2)
        ar_prior_term = ((ar - ar_prior) / ar_sigma) ** 2
        ecc_log_prior = beta_distribution.logpdf(max(ecc, 1e-6), 0.867, 3.03)
        return 0.5 * (chi2 + ar_prior_term) - ecc_log_prior

    def log_prob(theta):
        val = neg_log_post(theta)
        return -val if np.isfinite(val) else -np.inf

    print(f"a/Rstar prior = {ar_prior:.3f} +/- {ar_sigma:.3f}")
    print("Running stellar-density-informed eccentric sensitivity fit")
    print("Parameters are sqrt(e) sin(w) and sqrt(e) cos(w)")

    esinw0 = np.sqrt(ecc_guess) * np.sin(np.radians(omega_guess))
    ecosw0 = np.sqrt(ecc_guess) * np.cos(np.radians(omega_guess))
    log_baseline0 = np.log(baseline_guess)
    x0 = [rp_guess, ar_guess, b_guess, log_baseline0, esinw0, ecosw0]

    opt = minimize(neg_log_post, x0, method="Nelder-Mead", options={"maxiter": 10000})
    start = opt.x
    print("Optimization:", start, "objective", opt.fun)

    ndim = 6
    rng = np.random.default_rng(123)
    p0 = start + rng.normal(np.zeros(ndim), [0.002, 0.25, 0.04, 0.0002, 0.05, 0.05], size=(NWALKERS, ndim))
    p0[:, 0] = np.clip(p0[:, 0], 0.03, 0.08)
    p0[:, 1] = np.clip(p0[:, 1], 4.5, 12.0)
    p0[:, 2] = np.clip(p0[:, 2], 0.05, 1.0)

    sampler = emcee.EnsembleSampler(NWALKERS, ndim, log_prob)
    print(f"Burn-in {BURNIN_STEPS} steps")
    state = sampler.run_mcmc(p0, BURNIN_STEPS, progress=True)
    sampler.reset()
    print(f"Production {PRODUCTION_STEPS} steps")
    sampler.run_mcmc(state, PRODUCTION_STEPS, progress=True)
    samples_raw = sampler.get_chain(flat=True, discard=FLAT_DISCARD_STEPS)
    accept = float(np.mean(sampler.acceptance_fraction))

    rp_samples = samples_raw[:, 0]
    ar_samples = samples_raw[:, 1]
    b_samples = samples_raw[:, 2]
    baseline_samples = np.exp(samples_raw[:, 3])
    e_samples = samples_raw[:, 4]**2 + samples_raw[:, 5]**2
    omega_samples = np.degrees(np.arctan2(samples_raw[:, 4], samples_raw[:, 5])) % 360

    samples = np.column_stack([rp_samples, ar_samples, b_samples, baseline_samples, e_samples, omega_samples])
    labels = ["Rp/Rs", "a/Rs", "b", "baseline", "e", "omega"]

    med = np.median(samples, axis=0)
    lo = np.percentile(samples, 16, axis=0)
    hi = np.percentile(samples, 84, axis=0)
    rp, ar, b, baseline, ecc, omega = med
    inc = float(
        np.degrees(
            np.arccos(np.clip(eccentric_cosi(ar, b, ecc, omega), 0, 1))
        )
    )

    print("\n" + "=" * 60)
    print("ECCENTRIC FIT RESULTS")
    print("=" * 60)
    print(f"Rp/Rstar  = {rp:.6f} +{hi[0]-rp:.6f} -{rp-lo[0]:.6f}")
    print(f"a/Rstar   = {ar:.3f} +{hi[1]-ar:.3f} -{ar-lo[1]:.3f}")
    print(f"b         = {b:.4f} +{hi[2]-b:.4f} -{b-lo[2]:.4f}")
    print(f"baseline  = {baseline:.6f} +{hi[3]-baseline:.6f} -{baseline-lo[3]:.6f}")
    print(f"e         = {ecc:.4f} +{hi[4]-ecc:.4f} -{ecc-lo[4]:.4f}")
    print(f"omega     = {omega:.1f} deg +{hi[5]-omega:.1f} -{omega-lo[5]:.1f}")
    print(f"Incl      = {inc:.2f} deg")
    print(f"Depth     = {rp**2 * 1e6:.0f} ppm")
    print(f"Duration  = {duration_hours(rp, ar, b, ecc, omega):.2f} h")
    ar_diff = ar - ar_prior
    ar_sigma_tot = np.sqrt(np.std(ar_samples)**2 + ar_sigma**2)
    print(f"\na/Rstar tension: {ar:.2f} (fit) vs {ar_prior:.2f} (density) = {ar_diff/ar_sigma_tot:.1f} sigma")

    rp_re = float(rp * stellar["r_star"] * 109.1)
    print(f"Rp        = {rp_re:.2f} Rearth")

    try:
        tau = sampler.get_autocorr_time(tol=0)
        print(f"Autocorr times: {tau}")
    except Exception as exc:
        print(f"Autocorr error: {exc}")

    result = {
        "fit_type": "eccentric_stellar_density_informed",
        "interpretation": "eccentric sensitivity fit, not the adopted solution",
        "period": OFFICIAL_PERIOD,
        "t0": OFFICIAL_T0_BTJD,
        "rp_rs": float(rp),
        "rp_rs_p16": float(lo[0]),
        "rp_rs_p84": float(hi[0]),
        "a_rs": float(ar),
        "a_rs_p16": float(lo[1]),
        "a_rs_p84": float(hi[1]),
        "impact_parameter": float(b),
        "impact_parameter_p16": float(lo[2]),
        "impact_parameter_p84": float(hi[2]),
        "eccentricity": float(ecc),
        "eccentricity_p16": float(lo[4]),
        "eccentricity_p84": float(hi[4]),
        "omega_deg": float(omega),
        "omega_deg_p16": float(lo[5]),
        "omega_deg_p84": float(hi[5]),
        "inclination_deg": inc,
        "depth_ppm": float(rp**2 * 1e6),
        "duration_hrs": duration_hours(rp, ar, b, ecc, omega),
        "rp_earth": rp_re,
        "ar_prior": float(ar_prior),
        "ar_prior_sigma": float(ar_sigma),
        "ar_tension_sigma": float(ar_diff / ar_sigma_tot),
        "mcmc_acceptance": accept,
        "mcmc_burnin": BURNIN_STEPS,
        "mcmc_production": PRODUCTION_STEPS,
        "eccentric_parameterization": "sqrt(e) sin(omega), sqrt(e) cos(omega)",
        "eccentricity_prior": "Beta(0.867, 3.03)",
    }

    (ROOT / "outputs" / "transit_fit_120s_eccentric.json").write_text(json.dumps(result, indent=2))
    np.save(ROOT / "outputs" / "toi3492_raw_chain_120s_eccentric.npy", sampler.get_chain())

    fig = corner.corner(samples, labels=labels, show_titles=True, quantiles=[0.16, 0.5, 0.84])
    fig.savefig(ROOT / "figures" / "toi3492_corner_120s_eccentric.png", dpi=160)
    plt.close(fig)

    m = model_flux(t_bin, rp, ar, b, baseline, u1, u2, ecc, omega)
    if m is not None:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        hours = t_bin * 24
        sigma = np.sqrt(e_bin**2 + jitter**2)
        ax1.errorbar(hours, f_bin, yerr=sigma, fmt="o", ms=3, color="black", ecolor="lightgray", alpha=0.8)
        ax1.plot(hours, m, color="red", linewidth=2)
        ax1.set_ylabel("Normalized flux")
        ax1.set_title(f"TOI-3492.01 Eccentric 120s Fit\ne={ecc:.3f}, omega={omega:.1f} deg, a/Rs={ar:.2f}")
        ax2.errorbar(hours, (f_bin - m) * 1e6, yerr=sigma * 1e6, fmt="o", ms=3, color="black", ecolor="lightgray", alpha=0.8)
        ax2.axhline(0, color="red", linestyle="--")
        ax2.set_xlabel("Hours from official mid-transit")
        ax2.set_ylabel("Residuals (ppm)")
        plt.tight_layout()
        fig.savefig(ROOT / "figures" / "toi3492_transit_fit_120s_eccentric.png", dpi=180)
        plt.close(fig)

    print("\nWrote transit_fit_120s_eccentric.json, corner and fit PNGs")


if __name__ == "__main__":
    main()
