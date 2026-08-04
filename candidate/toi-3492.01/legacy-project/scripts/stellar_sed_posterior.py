"""Approximate broadband SED angular-radius posterior with systematic floors.

This deliberately uses a reddened blackbody only as a radius cross-check. It
does not claim the fidelity of an atmosphere-grid plus isochrone analysis.
"""

import json
from pathlib import Path

import emcee
import numpy as np
from scipy.constants import c, h, k
from scipy.special import logsumexp

from science import percentile_summary


ROOT = Path(__file__).resolve().parent.parent
RSUN_M = 6.957e8
PC_M = 3.085677581491367e16
MAG_SYSTEMATIC_FLOOR = 0.05

BANDS = {
    "J": (1.235, 1594.0, 0.282),
    "H": (1.662, 1024.0, 0.190),
    "Ks": (2.159, 666.7, 0.114),
    "W1": (3.3526, 309.540, 0.067),
    "W2": (4.6028, 171.787, 0.054),
    "W3": (11.5608, 31.674, 0.024),
    "W4": (22.0883, 8.363, 0.015),
}


def blackbody_magnitudes(teff, log_r_over_d, av, band_data):
    """Evaluate monochromatic Vega magnitudes at catalog pivot wavelengths."""
    radius_distance = np.exp(log_r_over_d)
    model = []
    for _, wavelength_micron, zero_jy, extinction_ratio in band_data:
        wavelength = wavelength_micron * 1e-6
        frequency = c / wavelength
        intensity = 2.0 * h * frequency**3 / c**2 / np.expm1(
            h * frequency / (k * teff)
        )
        flux_jy = np.pi * intensity * radius_distance**2 / 1e-26
        magnitude = -2.5 * np.log10(flux_jy / zero_jy) + av * extinction_ratio
        model.append(magnitude)
    return np.asarray(model)


def main():
    catalog = json.loads((ROOT / "data" / "stellar_photometry.json").read_text())
    observations = []
    for band in ("J", "H", "Ks"):
        row = catalog["photometry"]["2MASS"][band]
        observations.append((band, row["mag"], row["error"]))
    for band in ("W1", "W2", "W3", "W4"):
        row = catalog["photometry"]["AllWISE"][band]
        observations.append((band, row["mag"], row["error"]))
    band_data = [(name, *BANDS[name]) for name, _, _ in observations]
    magnitudes = np.array([row[1] for row in observations])
    errors = np.sqrt(
        np.array([row[2] for row in observations]) ** 2 + MAG_SYSTEMATIC_FLOOR**2
    )

    parallax = catalog["gaia_dr3_photometry_from_frozen_crosscheck"]["parallax_mas"]
    distance_pc = 1000.0 / parallax
    initial_scale = 2.65 * RSUN_M / (distance_pc * PC_M)

    def log_probability(theta):
        teff, log_scale, av = theta
        if not 5000.0 < teff < 7200.0 or not 0.0 < av < 0.3:
            return -np.inf
        if not np.log(initial_scale / 2.0) < log_scale < np.log(initial_scale * 2.0):
            return -np.inf
        model = blackbody_magnitudes(teff, log_scale, av, band_data)
        likelihood = -0.5 * np.sum(
            ((magnitudes - model) / errors) ** 2 + np.log(2.0 * np.pi * errors**2)
        )
        temperature_components = np.array(
            [
                -0.5 * ((teff - 6332.0) / 150.0) ** 2 - np.log(150.0),
                -0.5 * ((teff - 6061.15) / 150.0) ** 2 - np.log(150.0),
            ]
        )
        temperature_prior = logsumexp(temperature_components) - np.log(2.0)
        extinction_prior = -0.5 * (av / 0.05) ** 2
        return float(likelihood + temperature_prior + extinction_prior)

    rng = np.random.default_rng(3492)
    start = np.array([6200.0, np.log(initial_scale), 0.02])
    walkers = start + rng.normal(
        size=(48, 3)
    ) * np.array([80.0, 0.02, 0.01])
    walkers[:, 2] = np.clip(walkers[:, 2], 1e-4, 0.1)
    sampler = emcee.EnsembleSampler(48, 3, log_probability)
    state = sampler.run_mcmc(walkers, 500, progress=True)
    sampler.reset()
    sampler.run_mcmc(state, 2500, progress=True)
    samples = sampler.get_chain(discard=500, flat=True)

    draw_rng = np.random.default_rng(81077799)
    parallax_draw = draw_rng.normal(
        parallax,
        catalog["gaia_dr3_photometry_from_frozen_crosscheck"]["parallax_error_mas"],
        len(samples),
    )
    distance_draw = 1000.0 / parallax_draw
    radius_draw = np.exp(samples[:, 1]) * distance_draw * PC_M / RSUN_M
    luminosity_draw = radius_draw**2 * (samples[:, 0] / 5772.0) ** 4
    binary_component_radius = radius_draw / np.sqrt(2.0)

    median = np.median(samples, axis=0)
    model_magnitudes = blackbody_magnitudes(
        median[0], median[1], median[2], band_data
    )
    residuals = magnitudes - model_magnitudes
    try:
        tau = sampler.get_autocorr_time(tol=0)
        tau_values = [float(value) for value in tau]
    except Exception:
        tau_values = None
    result = {
        "status": "approximate_sed_radius_crosscheck_not_isochrone_posterior",
        "method": "reddened monochromatic blackbody fit to 2MASS and AllWISE photometry with a 0.05-mag model/passband systematic floor",
        "temperature_prior": "equal mixture of TIC 6332+/-150 K and Gaia GSP-Phot 6061+/-150 K external-error components",
        "extinction_prior": "half-normal Av=0+/-0.05 mag, truncated to [0, 0.3]",
        "photometry": [
            {
                "band": name,
                "observed_mag": float(observed),
                "catalog_error_mag": float(catalog_error),
                "total_error_mag": float(total_error),
                "model_mag_at_posterior_median": float(model),
                "residual_mag": float(residual),
            }
            for (name, observed, catalog_error), total_error, model, residual in zip(
                observations, errors, model_magnitudes, residuals
            )
        ],
        "single_star_posterior": {
            "teff_k": percentile_summary(samples[:, 0]),
            "av_mag": percentile_summary(samples[:, 2]),
            "distance_pc": percentile_summary(distance_draw),
            "radius_solar": percentile_summary(radius_draw),
            "luminosity_solar": percentile_summary(luminosity_draw),
        },
        "equal_brightness_unresolved_binary_geometric_branch": {
            "component_radius_solar": percentile_summary(binary_component_radius),
            "note": "At fixed temperature, splitting the observed SED equally reduces each component radius by sqrt(2). No component mass, density, or age is inferred without binary isochrones.",
        },
        "fit_quality": {
            "chi_square_at_posterior_median": float(np.sum((residuals / errors) ** 2)),
            "degrees_of_freedom": len(observations) - 3,
            "acceptance_fraction_mean": float(np.mean(sampler.acceptance_fraction)),
            "production_steps": int(sampler.get_chain().shape[0]),
            "retained_samples": int(len(samples)),
            "autocorrelation_time_steps": tau_values,
            "reliable_50tau_rule": bool(
                tau_values is not None
                and min(2500.0 / np.asarray(tau_values)) >= 50.0
            ),
        },
        "limitations": [
            "A blackbody at pivot wavelengths is not a substitute for passband-integrated stellar atmosphere models.",
            "The MIST grid was unavailable within the bounded offline attempt, so no isochrone mass, age, or coherent mass-radius covariance is claimed.",
            "WISE saturation and catalog calibration systematics may exceed formal magnitude errors; the common 0.05-mag floor is an approximation.",
        ],
    }
    output = ROOT / "outputs" / "stellar_sed_posterior.json"
    output.write_text(json.dumps(result, indent=2))
    np.save(ROOT / "data" / "stellar_sed_chain.npy", samples)
    print(json.dumps(result["single_star_posterior"], indent=2))
    print(json.dumps(result["fit_quality"], indent=2))
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
