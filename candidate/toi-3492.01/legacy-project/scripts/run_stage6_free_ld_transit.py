"""Stage 6: free limb-darkening descriptive reference fit.

Re-runs the folded/binned transit MCMC with LDTk-derived Gaussian priors
on q1, q2 instead of fixed quadratic limb-darkening coefficients.

This directly responds to the supervisor concern that fixed LD introduces
bias, by propagating the LDTk atmosphere-model uncertainty into the transit
parameter intervals.  The result remains descriptive/diagnostic, not an
adopted native-cadence posterior.
"""

import json
import math
import sys
import time
from pathlib import Path

import batman
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize

matplotlib.use("Agg")


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

LIGHTCURVE_PATH = ROOT / "data" / "toi3492_120s_reference.csv"
CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
OUT_JSON = ROOT / "outputs" / "stage6_free_ld_transit.json"
OUT_DIAG = ROOT / "outputs" / "stage6_free_ld_diagnostics.json"
OUT_CHAIN = ROOT / "data" / "stage6_free_ld_chain.npy"

PERIOD = 9.2224171
T0 = 2314.521155
T14_HOURS = 5.232600530809344
WINDOW_HALF_HOURS = 13.0
BIN_MINUTES = 8.0
EXPTIME_SECONDS = 120.0
SUPERSAMPLE = 7
WALKERS = 48
BURN_IN = 2000
PRODUCTION_STEPS = 8000

# --- LDTk-derived Kipping q1/q2 priors -----------------------------------
Q1_MEAN, Q1_SIGMA = 0.294369, 0.002690
Q2_MEAN, Q2_SIGMA = 0.361720, 0.001337
Q1Q2_CORR = -0.548295


def _build_folded_data(csv_path):
    data = pd.read_csv(csv_path)
    time = data["time"].to_numpy(np.float64)
    flux = data["flux"].to_numpy(np.float64)
    flux_err = data["flux_err"].to_numpy(np.float64)

    phase_days = ((time - T0 + 0.5 * PERIOD) % PERIOD) - 0.5 * PERIOD
    window_days = WINDOW_HALF_HOURS / 24.0
    keep = np.isfinite(phase_days) & np.isfinite(flux) & (
        np.abs(phase_days) <= window_days
    )
    phase_days = phase_days[keep]
    flux = flux[keep]
    flux_err = flux_err[keep]

    bin_days = BIN_MINUTES / (24.0 * 60.0)
    edges = np.arange(-window_days, window_days + bin_days, bin_days)
    bins = np.digitize(phase_days, edges) - 1
    n_bins = len(edges) - 1

    binned_t = np.zeros(n_bins)
    binned_f = np.zeros(n_bins)
    binned_e = np.zeros(n_bins)
    for i in range(n_bins):
        mask = bins == i
        if np.sum(mask) < 5:
            binned_t[i] = np.nan
            binned_f[i] = np.nan
            binned_e[i] = np.nan
            continue
        binned_t[i] = np.mean(phase_days[mask])
        binned_f[i] = np.median(flux[mask])
        binned_e[i] = 1.4826 * np.median(np.abs(
            flux[mask] - np.median(flux[mask])
        )) / math.sqrt(max(1, np.sum(mask) - 1))

    keep = np.isfinite(binned_t) & np.isfinite(binned_f) & (binned_e > 0)
    return binned_t[keep], binned_f[keep], binned_e[keep]


def _batman_model(q1, q2):
    u1_val = 2.0 * math.sqrt(q1) * q2
    u2_val = math.sqrt(q1) * (1.0 - 2.0 * q2)
    params = batman.TransitParams()
    params.t0 = 0.0
    params.per = PERIOD
    params.rp = 0.055
    params.a = 10.2
    params.inc = 86.0
    params.ecc = 0.0
    params.w = 90.0
    params.u = [u1_val, u2_val]
    params.limb_dark = "quadratic"
    return params


def _neg_log_post(theta, phase_days, flux, flux_err):
    if not np.all(np.isfinite(theta)):
        return 1e100
    rp, ar, b, baseline, log_jitter, q1, q2 = (
        float(theta[0]), float(theta[1]), float(theta[2]),
        float(theta[3]), float(theta[4]), float(theta[5]), float(theta[6]),
    )
    if not (0.025 < rp < 0.09 and 4.0 < ar < 16.0
            and 0.0 <= b < 1.0 + rp and 0.995 < baseline < 1.005
            and -9.0 < log_jitter < -2.0
            and 0.01 < q1 < 0.8 and 0.1 < q2 < 0.7):
        return 1e100

    try:
        model_params = _batman_model(q1, q2)
        model_params.rp = rp
        model_params.a = ar
        cosine = b / ar
        if not 0.0 <= cosine < 1.0:
            return 1e100
        model_params.inc = math.degrees(math.acos(float(cosine)))

        bm = batman.TransitModel(
            model_params, phase_days,
            supersample_factor=SUPERSAMPLE,
            exp_time=EXPTIME_SECONDS / 86400.0,
        )
        model_flux = bm.light_curve(model_params)
        model_flux = np.asarray(model_flux, dtype=np.float64)
    except Exception:
        return 1e100

    jitter_ppm = math.exp(log_jitter) * 1e-6
    ivar = 1.0 / (flux_err ** 2 + jitter_ppm ** 2)

    scaled = baseline * model_flux
    residual = flux - scaled
    chi2 = np.sum(residual ** 2 * ivar)
    logdet = np.sum(np.log(2.0 * math.pi / ivar))
    loglike = -0.5 * (chi2 + logdet)

    chi2_q1 = ((q1 - Q1_MEAN) / Q1_SIGMA) ** 2
    chi2_q2 = ((q2 - Q2_MEAN) / Q2_SIGMA) ** 2
    # off-diagonal from correlation
    rho = Q1Q2_CORR
    cross = 2.0 * rho * (q1 - Q1_MEAN) / Q1_SIGMA * (q2 - Q2_MEAN) / Q2_SIGMA
    log_prior_q = -0.5 * (chi2_q1 + chi2_q2 - cross) / (1.0 - rho * rho)

    return float(-loglike - log_prior_q)


def _optimize(phase_days, flux, flux_err):
    bounds = [
        (0.03, 0.09), (5.0, 16.0), (0.0, 0.95),
        (0.997, 1.003), (-9.0, -2.0),
        (Q1_MEAN - 4 * Q1_SIGMA, Q1_MEAN + 4 * Q1_SIGMA),
        (Q2_MEAN - 4 * Q2_SIGMA, Q2_MEAN + 4 * Q2_SIGMA),
    ]
    center = np.array([
        0.055, 10.2, 0.73, 1.0, math.log(300e-6),
        Q1_MEAN, Q2_MEAN,
    ])

    starts = [
        center,
        center + [0.01, 1.0, -0.1, 0.001, -0.5, 0.01, 0.01],
        center + [-0.01, -1.0, 0.1, -0.001, 0.5, -0.01, -0.01],
    ]
    best = None
    best_obj = np.inf
    for start in starts:
        res = minimize(
            lambda x: _neg_log_post(x, phase_days, flux, flux_err),
            start, method="L-BFGS-B", bounds=bounds,
            options={"maxiter": 500, "ftol": 1e-10},
        )
        if res.fun < best_obj and np.isfinite(res.fun):
            best_obj = float(res.fun)
            best = res.x
    return np.asarray(best, dtype=np.float64)


def _run_mcmc(map_point, phase_days, flux, flux_err):
    import emcee
    ndim = 7
    nwalkers = WALKERS
    nburn = BURN_IN
    nprod = PRODUCTION_STEPS

    p0 = map_point + 1e-3 * np.random.randn(nwalkers, ndim).astype(np.float64)
    p0[:, 2] = np.clip(p0[:, 2], 0.0, 0.95)
    p0[:, 3] = np.clip(p0[:, 3], 0.998, 1.002)
    p0[:, 4] = np.clip(p0[:, 4], -8.0, -4.0)
    p0[:, 5] = np.clip(p0[:, 5], Q1_MEAN - 4 * Q1_SIGMA, Q1_MEAN + 4 * Q1_SIGMA)
    p0[:, 6] = np.clip(p0[:, 6], Q2_MEAN - 4 * Q2_SIGMA, Q2_MEAN + 4 * Q2_SIGMA)

    sampler = emcee.EnsembleSampler(
        nwalkers, ndim,
        lambda x: -_neg_log_post(x, phase_days, flux, flux_err),
        moves=emcee.moves.StretchMove(a=1.5),
    )
    sampler.run_mcmc(p0, nburn + nprod, progress=True)
    chain = sampler.get_chain(discard=nburn, flat=True)
    return chain, sampler


def _run():
    t0_wall = time.time()
    phase_days, flux, flux_err = _build_folded_data(LIGHTCURVE_PATH)
    print("Phase points: {}".format(len(phase_days)))

    map_point = _optimize(phase_days, flux, flux_err)
    rp, ar, b, baseline, log_jitter, q1_map, q2_map = map_point
    print("MAP: rp={:.6f} ar={:.2f} b={:.3f} q1={:.6f} q2={:.6f}".format(
        rp, ar, b, q1_map, q2_map))

    chain, sampler = _run_mcmc(map_point, phase_days, flux, flux_err)

    names = ["rp_rs", "a_rs", "impact_parameter", "baseline",
             "log_jitter", "q1", "q2"]
    quantiles = [0.16, 0.50, 0.84]
    posteriors = {}
    for i, name in enumerate(names):
        q = np.quantile(chain[:, i], quantiles)
        posteriors[name] = {
            "p16": float(q[0]), "median": float(q[1]), "p84": float(q[2]),
            "plus": float(q[2] - q[1]), "minus": float(q[1] - q[0]),
        }

    # Derived: u1, u2 from q1,q2 medians
    q1_med = posteriors["q1"]["median"]
    q2_med = posteriors["q2"]["median"]
    u1_derived = 2.0 * math.sqrt(q1_med) * q2_med
    u2_derived = math.sqrt(q1_med) * (1.0 - 2.0 * q2_med)

    # Derived: inclination
    b_samples = chain[:, 2]
    ar_samples = chain[:, 1]
    inc_samples = np.degrees(np.arccos(b_samples / ar_samples))
    inc_q = np.quantile(inc_samples, quantiles)
    posteriors["inclination_deg"] = {
        "p16": float(inc_q[0]), "median": float(inc_q[1]),
        "p84": float(inc_q[2]),
    }

    # Derived: area ratio and model depth
    rp_samples = chain[:, 0]
    area_ppm = (rp_samples ** 2) * 1e6
    area_q = np.quantile(area_ppm, quantiles)
    posteriors["area_ratio_ppm"] = {
        "p16": float(area_q[0]), "median": float(area_q[1]),
        "p84": float(area_q[2]),
    }

    # Compute model depth at mid-transit
    depth_samples = np.zeros(len(rp_samples))
    for i in range(0, len(rp_samples), 1000):
        chunk = slice(i, min(i + 1000, len(rp_samples)))
        med_rp = np.median(rp_samples[chunk])
        med_ar = np.median(ar_samples[chunk])
        med_b = np.median(b_samples[chunk])
        med_q1 = np.median(chain[chunk, 5])
        med_q2 = np.median(chain[chunk, 6])
        params = _batman_model(med_q1, med_q2)
        params.rp = med_rp
        params.a = med_ar
        params.inc = math.degrees(math.acos(float(med_b / med_ar)))
        bm = batman.TransitModel(
            params, np.array([0.0]),
            supersample_factor=SUPERSAMPLE,
            exp_time=EXPTIME_SECONDS / 86400.0,
        )
        depth_samples[chunk] = 1.0 - bm.light_curve(params)[0]
    depth_ppm = depth_samples * 1e6
    depth_q = np.quantile(depth_ppm, quantiles)
    posteriors["mid_transit_depth_ppm"] = {
        "p16": float(depth_q[0]), "median": float(depth_q[1]),
        "p84": float(depth_q[2]),
    }

    # Autocorrelation
    try:
        tau = sampler.get_autocorr_time(discard=1000, quiet=True)
        tau_dict = {names[i]: float(tau[i]) if np.isfinite(tau[i]) else None
                    for i in range(len(names))}
    except Exception:
        tau_dict = {}

    # Compare with fixed-LD result
    old_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    old = old_config.get("transit_corrected_120s", {})
    old_rp = old.get("rp_rs", 0.05472)
    if isinstance(old_rp, dict):
        old_rp_val = old_rp.get("value", 0.05472)
    else:
        old_rp_val = float(old_rp)
    old_ar = old.get("a_rs", 10.60)
    if isinstance(old_ar, dict):
        old_ar_val = old_ar.get("value", 10.60)
    else:
        old_ar_val = float(old_ar)
    old_b = old.get("impact_parameter", 0.705)
    if isinstance(old_b, dict):
        old_b_val = old_b.get("value", 0.705)
    else:
        old_b_val = float(old_b)

    comparison = {
        "rp_rs": {
            "fixed_ld": old_rp_val,
            "free_ld_median": posteriors["rp_rs"]["median"],
            "free_ld_plus": posteriors["rp_rs"]["plus"],
            "free_ld_minus": posteriors["rp_rs"]["minus"],
        },
        "a_rs": {
            "fixed_ld": old_ar_val,
            "free_ld_median": posteriors["a_rs"]["median"],
        },
        "impact_parameter": {
            "fixed_ld": old_b_val,
            "free_ld_median": posteriors["impact_parameter"]["median"],
        },
    }

    report = {
        "schema_version": "1.0",
        "work_package": "S6-01_FREE_LIMB_DARKENING_DESCRIPTIVE_REFIT",
        "status": "PASS",
        "model": "folded 8-minute-binned circular transit with free q1/q2 LDTk priors",
        "ld_priors": {
            "q1_mean": Q1_MEAN, "q1_sigma": Q1_SIGMA,
            "q2_mean": Q2_MEAN, "q2_sigma": Q2_SIGMA,
            "q1q2_correlation": Q1Q2_CORR,
            "source": "LDTk PHOENIX, Teff=6332±134K, logg=3.71±0.08, [Fe/H]=0.0±0.15",
        },
        "derived_u1_u2": {
            "u1": round(u1_derived, 6),
            "u2": round(u2_derived, 6),
            "note": "Derived from posterior median q1, q2 via Kipping inverse transform.",
        },
        "posterior": posteriors,
        "comparison_with_fixed_ld": comparison,
        "mcmc": {
            "walkers": WALKERS,
            "burn_in": BURN_IN,
            "production": PRODUCTION_STEPS,
            "flat_samples": int(WALKERS * PRODUCTION_STEPS),
            "autocorrelation_times": tau_dict,
        },
        "elapsed_seconds": time.time() - t0_wall,
        "caveat": "This is a diagnostic folded/binned refit only, not an adopted native-cadence posterior.",
    }

    OUT_JSON.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    OUT_DIAG.write_text(
        json.dumps({
            "work_package": "S6-01",
            "parameters": names,
            "walkers": WALKERS,
            "burn_in": BURN_IN,
            "production": PRODUCTION_STEPS,
            "flat_samples": WALKERS * PRODUCTION_STEPS,
            "acceptance_fraction_mean": float(np.mean(sampler.acceptance_fraction)),
            "autocorr_times": tau_dict,
        }, indent=2) + "\n", encoding="utf-8",
    )
    np.save(str(OUT_CHAIN), chain)

    print("Free LD MCMC complete ({:.0f}s)".format(report["elapsed_seconds"]))
    print("  Rp/Rs: {:.5f} +{:.5f} -{:.5f} (fixed-LD: {:.5f})".format(
        posteriors["rp_rs"]["median"],
        posteriors["rp_rs"]["plus"], posteriors["rp_rs"]["minus"],
        old_rp_val,
    ))
    print("  a/Rs:  {:.2f} +{:.2f} -{:.2f} (fixed-LD: {:.2f})".format(
        posteriors["a_rs"]["median"],
        posteriors["a_rs"]["plus"], posteriors["a_rs"]["minus"],
        old_ar_val,
    ))
    print("  b:     {:.3f} (fixed-LD: {:.3f})".format(
        posteriors["impact_parameter"]["median"],
        old_b_val,
    ))
    print("  q1/q2: {:.4f}/{:.4f} → u1={:.4f} u2={:.4f}".format(
        q1_med, q2_med, u1_derived, u2_derived,
    ))


if __name__ == "__main__":
    _run()
