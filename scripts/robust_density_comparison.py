"""Compare robust transit densities with the systematic-floor SED cross-check."""

import json
from pathlib import Path

import numpy as np

from science import percentile_summary, photometric_density_solar


ROOT = Path(__file__).resolve().parent.parent
PERIOD = 9.2224171
PERIOD_ERR = 0.0000098


def comparison(transit_chain, radius_draw, rng):
    count = min(len(transit_chain), len(radius_draw), 100000)
    transit = transit_chain[rng.integers(0, len(transit_chain), count)]
    radius = radius_draw[rng.integers(0, len(radius_draw), count)]
    method = rng.random(count) < 0.5
    mass = np.empty(count)
    mass[method] = rng.normal(1.25, 0.186312, np.count_nonzero(method))
    gaia_sigma = np.hypot(0.0413, 0.10 * 1.5139)
    mass[~method] = rng.normal(1.5139, gaia_sigma, np.count_nonzero(~method))
    valid = (mass > 0.0) & (radius > 0.0)
    mass = mass[valid]
    radius = radius[valid]
    transit = transit[valid]
    period = PERIOD + transit[:, 2] * PERIOD_ERR
    rho_transit = photometric_density_solar(period, transit[:, 0])
    rho_star = mass / radius**3
    difference = rho_transit - rho_star
    return {
        "photometric_density_solar": percentile_summary(rho_transit),
        "stellar_density_solar": percentile_summary(rho_star),
        "difference_solar": percentile_summary(difference),
        "probability_photometric_density_greater": float(np.mean(difference > 0.0)),
        "mean_difference_over_quadrature_standard_deviation": float(
            (np.mean(rho_transit) - np.mean(rho_star))
            / np.sqrt(np.var(rho_transit) + np.var(rho_star))
        ),
        "n_draws": int(len(difference)),
    }


def main():
    sed_chain = np.load(ROOT / "data" / "stellar_sed_chain.npy")
    catalog = json.loads((ROOT / "data" / "stellar_photometry.json").read_text())
    rng = np.random.default_rng(20260712)
    parallax = rng.normal(
        catalog["gaia_dr3_photometry_from_frozen_crosscheck"]["parallax_mas"],
        catalog["gaia_dr3_photometry_from_frozen_crosscheck"]["parallax_error_mas"],
        len(sed_chain),
    )
    radius = (
        np.exp(sed_chain[:, 1])
        * (1000.0 / parallax)
        * 3.085677581491367e16
        / 6.957e8
    )
    result = {
        "status": "systematics_sensitivity_not_adopted_density_posterior",
        "stellar_model": "SED radius draws plus equal-weight TIC/Gaia mass-method mixture; 10% external floor added to Gaia FLAME mass",
        "mass_radius_covariance_available": False,
        "robust_120s": comparison(
            np.load(ROOT / "data" / "toi3492_chains_robust_120s.npy"),
            radius,
            rng,
        ),
        "robust_20s": comparison(
            np.load(ROOT / "data" / "toi3492_chains_robust_20s.npy"),
            radius,
            rng,
        ),
        "limitations": [
            "The robust transit chains fail the conservative 50-autocorrelation-time rule and are geometry checks, not adopted posteriors.",
            "The SED model is a monochromatic blackbody cross-check rather than a passband-integrated atmosphere/isochrone fit.",
            "Mass-radius covariance is unavailable; independent draws make the quoted standardized difference descriptive rather than a final significance.",
        ],
    }
    output = ROOT / "outputs" / "robust_density_comparison.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
