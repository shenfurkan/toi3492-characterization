"""Corrected 120-s MCMC transit fit for TOI-3492.01.

Phase-folds the reference light curve on the official TOI ephemeris and
fits a circular analytic transit model (batman) with emcee.  Four free
parameters are sampled:

    * rp_rs           –  planet-to-star radius ratio
    * a_rs            –  scaled semi-major axis
    * impact_parameter
    * baseline

Orbital period, reference epoch, eccentricity (e=0), and quadratic
limb-darkening coefficients (LDTk / Claret 2017) are fixed.

A weak Gaussian prior centred on the TIC-density Keplerian a/Rs
prediction is included to penalise unphysical solutions.

Outputs
-------
data/config_corrected_120s.json   Adopted transit solution.
data/toi3492_chains_120s_corrected.npy   Flat MCMC chain (88 000, 4).
data/toi3492_raw_chain_120s_corrected.npy  Raw chain (2500, 40, 4).
outputs/mcmc_diagnostics_120s_corrected.json  Autocorrelation, acceptance.
figures/toi3492_corner_120s_corrected.png
figures/toi3492_transit_fit_120s_corrected.png

Runs offline after the reference CSV has been built.
"""

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

ROOT = Path(__file__).resolve().parent.parent

# ---- Constants --------------------------------------------------------------
OFFICIAL_PERIOD = 9.2224171          # d
OFFICIAL_PERIOD_ERR = 0.0000098      # d
OFFICIAL_T0_BTJD = 2459314.5211550 - 2457000.0  # BTJD = BJD - 2457000
OFFICIAL_T0_ERR = 0.000615           # d
OFFICIAL_DURATION_HR = 5.2968580     # h

# MCMC settings
BURNIN_STEPS = 1200
PRODUCTION_STEPS = 2500
FLAT_DISCARD_STEPS = 300
NWALKERS = 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_reference():
    """Load the corrected 120-s reference CSV.

    Returns
    -------
    time, flux, sector : ndarray
        Finite-cadence arrays only.
    """
    df = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    time = df["time"].to_numpy(float)
    flux = df["flux"].to_numpy(float)
    sector = df["sector"].to_numpy(int)
    finite = np.isfinite(time) & np.isfinite(flux)
    return time[finite], flux[finite], sector[finite]


def phase_bin(time, flux, period, t0, limit_hr=13.0, bin_minutes=8.0):
    """Phase-fold and median-bin the light curve.

    The 8-minute bin size keeps the ingress/egress resolved at 120-s
    cadence while delivering stable medians.

    Returns
    -------
    centers_days, med, err, n
        Binned arrays; only bins with >= 4 points are returned.
    """
    phase_days = ((time - t0 + 0.5 * period) % period) - 0.5 * period
    hours = phase_days * 24.0
    mask = np.abs(hours) < limit_hr
    hours = hours[mask]
    phase_days = phase_days[mask]
    flux = flux[mask]

    bins = np.arange(
        -limit_hr, limit_hr + bin_minutes / 60.0, bin_minutes / 60.0
    )
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


def model_flux(t_days, rp, ar, b, baseline, u1, u2):
    """Evaluate a quadratic-limb-darkened batman transit model.

    Returns None if the geometry is unphysical
    (ar <= 0, b outside [0, ar], or cos(i) out of [0, 1]).
    """
    if ar <= 0 or b < 0 or b >= ar:
        return None
    cosi = b / ar
    if cosi < 0 or cosi > 1:
        return None
    inc = np.degrees(np.arccos(cosi))

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
    """Compute the total transit duration (T14) from the geometry.

    Uses the standard equation:
        T14 = (P/pi) * arcsin(sqrt((1+rp)^2 - b^2) / (a sin i))
    """
    inc = np.degrees(np.arccos(np.clip(b / ar, 0, 1)))
    arg = np.sqrt(max((1 + rp) ** 2 - b ** 2, 0)) / (
        ar * np.sin(np.radians(inc))
    )
    arg = np.clip(arg, -1, 1)
    return float((OFFICIAL_PERIOD / np.pi) * np.arcsin(arg) * 24.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config = load_config()
    stellar = config["stellar"]
    u1 = config["limb_darkening"]["u1"]  # LDTk quadratic coefficients
    u2 = config["limb_darkening"]["u2"]

    time, flux, sector = load_reference()
    t_bin, f_bin, e_bin, n_bin = phase_bin(
        time, flux, OFFICIAL_PERIOD, OFFICIAL_T0_BTJD
    )

    # ---- Kepler III prior ---------------------------------------------------
    # G in (R_sun^3) / (M_sun * day^2)
    G_MSUN = 2942.2062

    # Predicted a/Rs from Kepler's Third Law for e=0
    ar_prior = (
        G_MSUN
        * stellar["m_star"]
        * OFFICIAL_PERIOD ** 2
        / (4 * np.pi ** 2)
    ) ** (1 / 3) / stellar["r_star"]

    # Uncertainty propagated from the TIC stellar density uncertainty
    ar_sigma = max(
        ar_prior * stellar["rho_star_err"] / (3 * stellar["rho_star"]), 0.5
    )

    # Initial guesses
    rp_guess = np.sqrt(0.0031)  # ~3110 ppm depth
    b_guess = 0.88
    jitter = 120e-6  # 120 ppm white-noise floor

    # ---- Negative log-posterior ---------------------------------------------
    def neg_log_post(theta):
        """Negative log-posterior: chi-squared + weak Kepler prior on a/Rs."""
        rp, ar, b, baseline = theta
        # Hard bounds
        if not (
            0.025 < rp < 0.09
            and 4.0 < ar < 13.0
            and 0.0 <= b < 1.0 + rp
            and 0.995 < baseline < 1.005
        ):
            return np.inf

        m = model_flux(t_bin, rp, ar, b, baseline, u1, u2)
        if m is None:
            return np.inf

        # Quadratic jitter added in quadrature with the bin error
        sigma = np.sqrt(e_bin ** 2 + jitter ** 2)
        chi2 = np.sum(((f_bin - m) / sigma) ** 2)

        # Weak Gaussian prior on a/Rs
        ar_prior_term = ((ar - ar_prior) / ar_sigma) ** 2

        return 0.5 * (chi2 + ar_prior_term)

    print(f"a/Rstar prior = {ar_prior:.3f} +/- {ar_sigma:.3f}")

    # ---- Optimise starting position -----------------------------------------
    opt = minimize(
        neg_log_post,
        [rp_guess, ar_prior, b_guess, 1.0],
        method="Nelder-Mead",
        options={"maxiter": 5000},
    )
    start = opt.x
    print("Optimization:", start, "objective", opt.fun)

    # ---- MCMC ---------------------------------------------------------------
    def log_prob(theta):
        val = neg_log_post(theta)
        return -val if np.isfinite(val) else -np.inf

    rng = np.random.default_rng(42)
    ndim = 4
    # Scatter walkers around the optimised position
    p0 = start + rng.normal(
        [0, 0, 0, 0], [0.002, 0.25, 0.04, 2e-4], size=(NWALKERS, ndim)
    )
    # Clip into physically plausible bounds
    p0[:, 0] = np.clip(p0[:, 0], 0.03, 0.08)
    p0[:, 1] = np.clip(p0[:, 1], 4.5, 12.0)
    p0[:, 2] = np.clip(p0[:, 2], 0.05, 1.0)
    p0[:, 3] = np.clip(p0[:, 3], 0.997, 1.003)

    sampler = emcee.EnsembleSampler(NWALKERS, ndim, log_prob)
    print(f"Burn-in {BURNIN_STEPS} steps")
    state = sampler.run_mcmc(p0, BURNIN_STEPS, progress=True)
    sampler.reset()
    print(f"Production {PRODUCTION_STEPS} steps")
    sampler.run_mcmc(state, PRODUCTION_STEPS, progress=True)

    raw_chain = sampler.get_chain()
    samples = sampler.get_chain(flat=True, discard=FLAT_DISCARD_STEPS)
    accept = float(np.mean(sampler.acceptance_fraction))

    # ---- Autocorrelation diagnostics ----------------------------------------
    try:
        tau = sampler.get_autocorr_time(tol=0)
        tau_list = [float(x) for x in tau]
        autocorr_error = None
    except Exception as exc:
        tau_list = None
        autocorr_error = str(exc)

    if tau_list is None:
        steps_per_tau = None
        autocorr_reliable = False
    else:
        steps_per_tau = [
            float(PRODUCTION_STEPS / x) if x > 0 else None for x in tau_list
        ]
        valid_steps_per_tau = [x for x in steps_per_tau if x is not None]
        autocorr_reliable = bool(
            valid_steps_per_tau and min(valid_steps_per_tau) >= 50.0
        )

    # ---- Posterior summaries ------------------------------------------------
    med = np.median(samples, axis=0)
    lo = np.percentile(samples, 16, axis=0)
    hi = np.percentile(samples, 84, axis=0)

    rp, ar, b, baseline = med
    inc = float(np.degrees(np.arccos(np.clip(b / ar, 0, 1))))

    # Symmetric error from 16-84 percentile half-width
    rp_err = max(rp - lo[0], hi[0] - rp)
    ar_err = max(ar - lo[1], hi[1] - ar)
    b_err = max(b - lo[2], hi[2] - b)
    inc_samples = np.degrees(
        np.arccos(np.clip(samples[:, 2] / samples[:, 1], 0, 1))
    )
    inc_err = max(
        inc - np.percentile(inc_samples, 16),
        np.percentile(inc_samples, 84) - inc,
    )

    # ---- Derived quantities -------------------------------------------------
    # Model depth:  delta = (Rp/Rs)^2
    depth_ppm = float(rp ** 2 * 1e6)

    # Physical radius:  R_p = (Rp/Rs) * R_s * (R_sun / R_earth)
    RE_PER_RSUN = 109.1
    rp_re = float(rp * stellar["r_star"] * RE_PER_RSUN)
    rp_re_err = float(
        rp_re
        * np.sqrt(
            (rp_err / rp) ** 2
            + (stellar["r_star_err"] / stellar["r_star"]) ** 2
        )
    )
    dur = duration_hours(rp, ar, b)

    R_SUN_AU = 0.00465047
    a_au = float(ar * stellar["r_star"] * R_SUN_AU)

    # Luminosity (solar units):  L = (R/R_sun)^2 (T/5772)^4
    lum = float(stellar["r_star"] ** 2 * (stellar["teff"] / 5772.0) ** 4)

    # Incident flux (Earth units):  S = L / a^2
    insol = float(lum / a_au ** 2)

    # Equilibrium temperature (zero albedo, full redistribution):
    #   T_eq = T_eff * sqrt(R_s / (2a))
    teq = float(
        stellar["teff"] * np.sqrt(stellar["r_star"] * R_SUN_AU / (2 * a_au))
    )

    # ---- Assemble result ----------------------------------------------------
    result = {
        "source": "Corrected 120s SPOC reference light curve; official ephemeris fixed; circular model",
        "period": OFFICIAL_PERIOD,
        "t0": OFFICIAL_T0_BTJD,
        "rp_rs": float(rp),
        "rp_rs_err": float(rp_err),
        "a_rs": float(ar),
        "a_rs_err": float(ar_err),
        "impact_parameter": float(b),
        "impact_parameter_err": float(b_err),
        "inc": inc,
        "inc_err": float(inc_err),
        "depth_ppm": depth_ppm,
        "duration_hrs": dur,
        "rp_earth": rp_re,
        "rp_earth_err": rp_re_err,
        "a_au": a_au,
        "luminosity_lsun": lum,
        "incident_flux_earth": insol,
        "teq_k": teq,
        "mcmc_samples": int(samples.shape[0]),
        "mcmc_acceptance_fraction": accept,
        "mcmc_raw_chain_shape": list(raw_chain.shape),
        "mcmc_burnin_steps": BURNIN_STEPS,
        "mcmc_production_steps": PRODUCTION_STEPS,
        "mcmc_flat_discard_steps": FLAT_DISCARD_STEPS,
        "mcmc_walkers": NWALKERS,
        "mcmc_autocorr_time_steps": tau_list,
        "mcmc_steps_per_autocorr_time": steps_per_tau,
        "mcmc_autocorr_reliable_50tau_rule": autocorr_reliable,
        "mcmc_autocorr_error": autocorr_error,
        "a_rs_prior": float(ar_prior),
        "a_rs_prior_sigma": float(ar_sigma),
        "jitter_ppm": float(jitter * 1e6),
    }

    diagnostics = {
        "source": "emcee diagnostics for corrected 120s transit fit",
        "parameters": ["rp_rs", "a_rs", "impact_parameter", "baseline"],
        "burnin_steps": BURNIN_STEPS,
        "production_steps": PRODUCTION_STEPS,
        "flat_discard_steps": FLAT_DISCARD_STEPS,
        "walkers": NWALKERS,
        "ndim": ndim,
        "raw_chain_shape": list(raw_chain.shape),
        "flat_chain_shape": list(samples.shape),
        "acceptance_fraction_mean": accept,
        "acceptance_fraction_min": float(
            np.min(sampler.acceptance_fraction)
        ),
        "acceptance_fraction_max": float(
            np.max(sampler.acceptance_fraction)
        ),
        "autocorr_time_steps": tau_list,
        "steps_per_autocorr_time": steps_per_tau,
        "autocorr_reliable_50tau_rule": autocorr_reliable,
        "autocorr_error": autocorr_error,
        "note": "The 50*tau rule is a conservative emcee heuristic; "
        "failing it does not by itself invalidate the fit, "
        "but it means autocorrelation reporting should be cautious.",
    }

    # ---- Update config ------------------------------------------------------
    corrected = dict(config)
    corrected["files"] = dict(corrected.get("files", {}))
    corrected["files"].pop("cleaned_csv", None)
    corrected["files"].pop("unflattened_csv", None)
    corrected["files"]["reference_120s_csv"] = "toi3492_120s_reference.csv"
    corrected["files"]["flat_chain_120s_npy"] = (
        "toi3492_chains_120s_corrected.npy"
    )
    corrected["files"]["raw_chain_120s_npy"] = (
        "toi3492_raw_chain_120s_corrected.npy"
    )
    corrected["files"]["mcmc_diagnostics_120s_json"] = (
        "mcmc_diagnostics_120s_corrected.json"
    )
    corrected["transit"] = {
        "status": "current_corrected_120s",
        "source": result["source"],
        "period": result["period"],
        "period_err": OFFICIAL_PERIOD_ERR,
        "t0": result["t0"],
        "t0_err": OFFICIAL_T0_ERR,
        "rp_rs": result["rp_rs"],
        "rp_rs_err": result["rp_rs_err"],
        "a_rs": result["a_rs"],
        "a_rs_err": result["a_rs_err"],
        "impact_parameter": result["impact_parameter"],
        "impact_parameter_err": result["impact_parameter_err"],
        "inc": result["inc"],
        "inc_err": result["inc_err"],
        "ecc": 0.0,
        "ecc_err": 0.0,
        "omega": 90.0,
        "omega_err": 0.0,
        "depth_ppm": result["depth_ppm"],
        "duration_hrs": result["duration_hrs"],
        "rp_earth": result["rp_earth"],
        "rp_earth_err": result["rp_earth_err"],
    }
    corrected["transit_corrected_120s"] = result

    (ROOT / "data" / "config_corrected_120s.json").write_text(
        json.dumps(corrected, indent=4)
    )

    # ---- Save chains --------------------------------------------------------
    np.save(
        ROOT / "data" / "toi3492_chains_120s_corrected.npy", samples
    )
    np.save(
        ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy", raw_chain
    )
    (ROOT / "outputs" / "mcmc_diagnostics_120s_corrected.json").write_text(
        json.dumps(diagnostics, indent=2)
    )

    # ---- Corner plot --------------------------------------------------------
    fig = plt.figure(figsize=(10, 10))
    fig = corner.corner(
        samples,
        fig=fig,
        labels=["Rp/Rs", "a/Rs", "b", "baseline"],
        show_titles=True,
        quantiles=[0.16, 0.5, 0.84],
        title_fmt=".5f",
        title_kwargs={"fontsize": 10},
        label_kwargs={"labelpad": 20, "fontsize": 11},
        max_n_ticks=3,
    )
    fig.subplots_adjust(top=0.95, bottom=0.1, left=0.1, right=0.95, hspace=0.1, wspace=0.1)
    fig.savefig(
        ROOT / "figures" / "toi3492_corner_120s_corrected.png", dpi=160
    )
    plt.close(fig)

    # ---- Best-fit transit plot ----------------------------------------------
    model = model_flux(t_bin, rp, ar, b, baseline, u1, u2)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    hours = t_bin * 24.0
    ax1.errorbar(
        hours,
        f_bin,
        yerr=np.sqrt(e_bin ** 2 + jitter ** 2),
        fmt="o",
        ms=3,
        color="black",
        ecolor="lightgray",
        alpha=0.8,
    )
    ax1.plot(hours, model, color="red", linewidth=2)
    ax1.set_ylabel("Normalized flux")
    ax1.set_title(
        f"TOI-3492.01 Corrected 120s Transit Fit\n"
        f"Rp/Rs={rp:.4f}, Rp={rp_re:.1f} Rearth, "
        f"b={b:.2f}, i={inc:.2f} deg"
    )
    ax2.errorbar(
        hours,
        (f_bin - model) * 1e6,
        yerr=np.sqrt(e_bin ** 2 + jitter ** 2) * 1e6,
        fmt="o",
        ms=3,
        color="black",
        ecolor="lightgray",
        alpha=0.8,
    )
    ax2.axhline(0, color="red", linestyle="--")
    ax2.set_xlabel("Hours from official mid-transit")
    ax2.set_ylabel("Residuals (ppm)")
    plt.tight_layout()
    fig.savefig(
        ROOT / "figures" / "toi3492_transit_fit_120s_corrected.png", dpi=180
    )
    plt.close(fig)

    print(json.dumps(result, indent=2))
    print("Wrote config_corrected_120s.json")
    print("Wrote mcmc_diagnostics_120s_corrected.json")
    print("Wrote toi3492_raw_chain_120s_corrected.npy")
    print("Wrote toi3492_transit_fit_120s_corrected.png")
    print("Wrote toi3492_corner_120s_corrected.png")


if __name__ == "__main__":
    main()
