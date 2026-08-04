"""Compare the adopted +/-13 h fit with a total-width 13 h fit.

The adopted result is loaded from its frozen chain. The alternative fit uses
the same likelihood, priors, exposure integration, sampler settings, and seed,
but selects +/-6.5 h around transit. It never updates the adopted config.
"""

import json
from pathlib import Path

import emcee
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from science import percentile_summary, photometric_density_solar, transit_duration_hours
from transit_model_120s_corrected import (
    BURNIN_STEPS,
    FLAT_DISCARD_STEPS,
    NWALKERS,
    OFFICIAL_PERIOD,
    OFFICIAL_T0_BTJD,
    PRODUCTION_STEPS,
    model_flux,
    phase_bin,
)


ROOT = Path(__file__).resolve().parent.parent
ALTERNATIVE_HALF_WIDTH_HOURS = 6.5
ADOPTED_HALF_WIDTH_HOURS = 13.0
BIN_MINUTES = 8.0
SEED = 42


def summarize_samples(samples, u1, u2):
    """Return draw-wise summaries needed for the window comparison."""
    rp = samples[:, 0]
    a_rs = samples[:, 1]
    impact = samples[:, 2]
    inclination = np.degrees(np.arccos(np.clip(impact / a_rs, 0.0, 1.0)))
    duration = transit_duration_hours(OFFICIAL_PERIOD, rp, a_rs, impact)
    density = photometric_density_solar(OFFICIAL_PERIOD, a_rs)
    medians = np.median(samples, axis=0)
    midpoint = model_flux(
        np.array([0.0]),
        medians[0],
        medians[1],
        medians[2],
        1.0,
        u1,
        u2,
        exp_minutes=BIN_MINUTES,
    )
    return {
        "rp_rs": percentile_summary(rp),
        "a_rs": percentile_summary(a_rs),
        "impact_parameter": percentile_summary(impact),
        "inclination_deg": percentile_summary(inclination),
        "duration_hours": percentile_summary(duration),
        "circular_density_solar": percentile_summary(density),
        "baseline": percentile_summary(samples[:, 3]),
        "jitter_ppm": percentile_summary(np.exp(samples[:, 4]) * 1e6),
        "area_ratio_ppm": percentile_summary(rp**2 * 1e6),
        "midtransit_model_depth_at_parameter_medians_ppm": float(
            (1.0 - midpoint[0]) * 1e6
        ),
    }


def finite_walker_cloud(center, log_probability, rng):
    """Draw the same-scale initial cloud while requiring finite probability."""
    scales = np.array([0.002, 0.25, 0.04, 2e-4, 0.15])
    cloud = np.empty((NWALKERS, len(center)))
    for index in range(NWALKERS):
        for _ in range(10000):
            candidate = center + rng.normal(size=len(center)) * scales
            if np.isfinite(log_probability(candidate)):
                cloud[index] = candidate
                break
        else:
            raise RuntimeError("Could not initialize a finite walker cloud")
    return cloud


def main():
    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    transit = config["transit_corrected_120s"]
    u1 = config["limb_darkening"]["u1"]
    u2 = config["limb_darkening"]["u2"]
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    time = data["time"].to_numpy(float)
    flux = data["flux"].to_numpy(float)
    phase = (
        (time - OFFICIAL_T0_BTJD + 0.5 * OFFICIAL_PERIOD) % OFFICIAL_PERIOD
    ) - 0.5 * OFFICIAL_PERIOD

    t_bin, f_bin, e_bin, n_bin = phase_bin(
        time,
        flux,
        OFFICIAL_PERIOD,
        OFFICIAL_T0_BTJD,
        half_width_hr=ALTERNATIVE_HALF_WIDTH_HOURS,
        bin_minutes=BIN_MINUTES,
    )

    def negative_log_probability(theta):
        rp, a_rs, impact, baseline, log_jitter = theta
        if not (
            0.025 < rp < 0.09
            and 4.0 < a_rs < 13.0
            and 0.0 <= impact < 1.0 + rp
            and 0.995 < baseline < 1.005
            and np.log(10e-6) < log_jitter < np.log(2000e-6)
        ):
            return np.inf
        model = model_flux(
            t_bin,
            rp,
            a_rs,
            impact,
            baseline,
            u1,
            u2,
            exp_minutes=BIN_MINUTES,
        )
        if model is None:
            return np.inf
        sigma = np.sqrt(e_bin**2 + np.exp(log_jitter) ** 2)
        residual = (f_bin - model) / sigma
        return 0.5 * np.sum(residual**2 + np.log(2.0 * np.pi * sigma**2))

    def log_probability(theta):
        value = negative_log_probability(theta)
        return -value if np.isfinite(value) else -np.inf

    initial = np.array(
        [
            transit["rp_rs"],
            transit["a_rs"],
            transit["impact_parameter"],
            1.0,
            np.log(transit["jitter_ppm"] * 1e-6),
        ]
    )
    optimum = minimize(
        negative_log_probability,
        initial,
        method="Nelder-Mead",
        options={"maxiter": 10000, "xatol": 1e-9, "fatol": 1e-6},
    )
    if not optimum.success:
        raise RuntimeError(f"Alternative-window optimization failed: {optimum.message}")

    rng = np.random.default_rng(SEED)
    walkers = finite_walker_cloud(optimum.x, log_probability, rng)
    np.random.seed(SEED)
    sampler = emcee.EnsembleSampler(NWALKERS, 5, log_probability)
    state = sampler.run_mcmc(walkers, BURNIN_STEPS, progress=True)
    sampler.reset()
    sampler.run_mcmc(state, PRODUCTION_STEPS, progress=True)
    raw_chain = sampler.get_chain()
    alternative_samples = sampler.get_chain(flat=True, discard=FLAT_DISCARD_STEPS)
    adopted_samples = np.load(
        ROOT / "data" / "toi3492_chains_120s_corrected.npy", allow_pickle=False
    )

    tau = [float(value) for value in sampler.get_autocorr_time(tol=0)]
    adopted_summary = summarize_samples(adopted_samples, u1, u2)
    alternative_summary = summarize_samples(alternative_samples, u1, u2)
    comparison = {}
    for key in (
        "rp_rs",
        "a_rs",
        "impact_parameter",
        "duration_hours",
        "circular_density_solar",
    ):
        adopted_value = adopted_summary[key]["median"]
        alternative_value = alternative_summary[key]["median"]
        lower = adopted_value - adopted_summary[key]["p16"]
        upper = adopted_summary[key]["p84"] - adopted_value
        comparison[key] = {
            "alternative_minus_adopted": alternative_value - adopted_value,
            "in_adopted_max_68pct_half_widths": (
                alternative_value - adopted_value
            )
            / max(lower, upper),
        }

    result = {
        "status": "window_definition_sensitivity_not_adopted",
        "question": "Compare total-width 13 h (+/-6.5 h) with the adopted +/-13 h selection",
        "shared_model": "Same folded 8-minute circular likelihood, priors, exposure integration, MCMC settings, and seed",
        "adopted_window": {
            "half_width_hours": ADOPTED_HALF_WIDTH_HOURS,
            "total_width_hours": 2.0 * ADOPTED_HALF_WIDTH_HOURS,
            "n_selected_native_points": int(
                np.count_nonzero(
                    np.abs(phase) < ADOPTED_HALF_WIDTH_HOURS / 24.0
                )
            ),
            "n_bins": 195,
            "posterior": adopted_summary,
        },
        "alternative_window": {
            "half_width_hours": ALTERNATIVE_HALF_WIDTH_HOURS,
            "total_width_hours": 2.0 * ALTERNATIVE_HALF_WIDTH_HOURS,
            "n_selected_native_points": int(
                np.count_nonzero(
                    np.abs(phase) < ALTERNATIVE_HALF_WIDTH_HOURS / 24.0
                )
            ),
            "n_binned_points_used": int(np.sum(n_bin)),
            "n_bins": int(len(t_bin)),
            "optimizer": {
                "parameters": [float(value) for value in optimum.x],
                "negative_log_likelihood": float(optimum.fun),
            },
            "posterior": alternative_summary,
            "mcmc": {
                "walkers": NWALKERS,
                "burnin_steps": BURNIN_STEPS,
                "production_steps": PRODUCTION_STEPS,
                "flat_discard_steps": FLAT_DISCARD_STEPS,
                "retained_samples": int(len(alternative_samples)),
                "acceptance_fraction_mean": float(
                    np.mean(sampler.acceptance_fraction)
                ),
                "autocorrelation_time_steps": tau,
                "production_steps_per_tau": [
                    PRODUCTION_STEPS / value for value in tau
                ],
                "reliable_50tau_rule": bool(
                    min(PRODUCTION_STEPS / np.asarray(tau)) >= 50.0
                ),
                "seed": SEED,
            },
        },
        "alternative_minus_adopted": comparison,
        "interpretation_rule": "This comparison diagnoses window sensitivity; it does not replace the adopted result unless explicitly selected after review.",
    }

    chain_path = ROOT / "data" / "toi3492_raw_chain_window_total13h.npy"
    output_path = ROOT / "outputs" / "transit_window_comparison.json"
    np.save(chain_path, raw_chain)
    output_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    print(f"Wrote {chain_path}")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
