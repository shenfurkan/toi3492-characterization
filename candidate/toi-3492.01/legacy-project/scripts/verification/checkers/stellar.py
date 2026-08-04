"""Verification checks for stellar SED posterior and Gaia DR3 crosschecks."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd

from ..core import ROOT, Verification, _as_bool, _blackbody_magnitudes, _close, _load


def verify_stellar_sed(audit: Verification) -> None:
    chain = np.load(ROOT / "data" / "stellar_sed_chain.npy", allow_pickle=False)
    result = _load("outputs/stellar_sed_posterior.json")
    catalog = _load("data/stellar_photometry.json")
    tic = _load("data/tic_v8_target.json")
    config = _load("data/config_corrected_120s.json")
    audit.check("stellar_sed", "tic_config_crosscheck", all((
        _close(tic["stellar"]["teff_k"], config["stellar"]["teff"]),
        _close(tic["stellar"]["logg_cgs"], config["stellar"]["logg"]),
        _close(tic["stellar"]["radius_solar"], config["stellar"]["r_star"]),
    )), "TIC stellar inputs")
    audit.check("stellar_sed", "chain_shape_and_support", bool(
        chain.shape == (96000, 3) and np.isfinite(chain).all()
        and np.all((chain[:, 0] > 5000.0) & (chain[:, 0] < 7200.0))
        and np.all((chain[:, 2] > 0.0) & (chain[:, 2] < 0.3))
    ), f"shape={chain.shape}")
    quantiles = np.quantile(chain, [0.16, 0.50, 0.84], axis=0)
    posterior = result["single_star_posterior"]
    audit.check("stellar_sed", "teff_and_av_quantiles", bool(
        np.allclose(quantiles[:, 0], [posterior["teff_k"][key] for key in ("p16", "median", "p84")])
        and np.allclose(quantiles[:, 2], [posterior["av_mag"][key] for key in ("p16", "median", "p84")])
    ), f"Teff={quantiles[1, 0]:.2f} Av={quantiles[1, 2]:.4f}")
    parallax = catalog["gaia_dr3_photometry_from_frozen_crosscheck"]["parallax_mas"]
    parallax_error = catalog["gaia_dr3_photometry_from_frozen_crosscheck"]["parallax_error_mas"]
    rng = np.random.default_rng(81077799)
    distance = 1000.0 / rng.normal(parallax, parallax_error, len(chain))
    radius = np.exp(chain[:, 1]) * distance * 3.085677581491367e16 / 6.957e8
    luminosity = radius**2 * (chain[:, 0] / 5772.0)**4
    for name, values in (("distance_pc", distance), ("radius_solar", radius),
                         ("luminosity_solar", luminosity)):
        expected = [posterior[name][key] for key in ("p16", "median", "p84")]
        audit.check("stellar_sed", f"{name}_quantiles", bool(np.allclose(
            np.quantile(values, [0.16, 0.50, 0.84]), expected, rtol=0, atol=1e-10,
        )), f"median={float(np.median(values)):.8f}")
    bands = {
        "J": (1.235, 1594.0, 0.282), "H": (1.662, 1024.0, 0.190),
        "Ks": (2.159, 666.7, 0.114), "W1": (3.3526, 309.540, 0.067),
        "W2": (4.6028, 171.787, 0.054), "W3": (11.5608, 31.674, 0.024),
        "W4": (22.0883, 8.363, 0.015),
    }
    observations = []
    for name in ("J", "H", "Ks"):
        row = catalog["photometry"]["2MASS"][name]
        observations.append((name, row["mag"], row["error"]))
    for name in ("W1", "W2", "W3", "W4"):
        row = catalog["photometry"]["AllWISE"][name]
        observations.append((name, row["mag"], row["error"]))
    median = np.median(chain, axis=0)
    model = _blackbody_magnitudes(median[0], median[1], median[2],
                                  [(name, *bands[name]) for name, _, _ in observations])
    observed = np.asarray([value for _, value, _ in observations])
    errors = np.sqrt(np.asarray([value for _, _, value in observations])**2 + 0.05**2)
    chi_square = float(np.sum(((observed - model) / errors)**2))
    audit.check("stellar_sed", "photometric_likelihood_recomputed", bool(
        np.allclose(model, [row["model_mag_at_posterior_median"] for row in result["photometry"]])
        and _close(chi_square, result["fit_quality"]["chi_square_at_posterior_median"])
    ), f"chi2={chi_square:.8f}")
    audit.warning("stellar_sed", "scope_limit",
                  "The verified blackbody chain is a radius crosscheck, not an atmosphere-plus-isochrone posterior.")


def verify_gaia(audit: Verification) -> None:
    result = _load("outputs/gaia_contamination_check.json")
    neighbors = pd.read_csv(ROOT / "outputs" / "gaia_dr3_neighbors.csv")
    target = neighbors.loc[neighbors["is_target_match"].map(_as_bool)]
    audit.check("gaia", "unique_target_match", len(target) == 1,
                f"matches={len(target)}")
    target_row = target.iloc[0]
    ra0 = math.radians(float(result["target"]["ra_deg"]))
    dec0 = math.radians(float(result["target"]["dec_deg"]))
    ra = np.radians(neighbors["ra"].to_numpy(float))
    dec = np.radians(neighbors["dec"].to_numpy(float))
    cosine = np.sin(dec0) * np.sin(dec) + np.cos(dec0) * np.cos(dec) * np.cos(ra - ra0)
    separation = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))) * 3600.0
    audit.check("gaia", "spherical_separations", bool(np.allclose(
        separation, neighbors["separation_arcsec"].to_numpy(float), rtol=0, atol=2e-3,
    )), f"max_diff={float(np.max(np.abs(separation - neighbors['separation_arcsec'].to_numpy(float)))):.3g} arcsec")
    target_g = float(target_row["phot_g_mean_mag"])
    delta_g = neighbors["phot_g_mean_mag"].to_numpy(float) - target_g
    ratio = 10.0**(-0.4 * delta_g)
    full_depth = 1e6 * ratio / (1.0 + ratio)
    observed_depth = float(result["observed_transit"]["depth_ppm"])
    non_target = ~neighbors["is_target_match"].map(_as_bool).to_numpy()
    full_mimics = non_target & (full_depth >= observed_depth)
    half_mimics = non_target & (0.5 * full_depth >= observed_depth)
    summary = result["neighbor_summary"]
    audit.check("gaia", "flux_ratio_and_mimic_counts", bool(
        np.allclose(ratio, neighbors["flux_ratio_vs_target"].to_numpy(float), rtol=3e-6, atol=1e-10)
        and int(np.sum(full_mimics)) == summary["n_neighbors_that_could_mimic_if_fully_eclipsed"]
        and int(np.sum(half_mimics)) == summary["n_neighbors_that_could_mimic_if_50pct_eclipsed"]
    ), f"full={int(np.sum(full_mimics))} half={int(np.sum(half_mimics))}")
    within_42 = int(np.sum(non_target & (separation <= 42.0)))
    audit.check("gaia", "42_arcsec_neighbor_count", within_42 == 58,
                f"computed={within_42}")
    source_id = "5347362002981716992"
    mimic = neighbors.loc[neighbors["source_id"].astype(str) == source_id]
    audit.check("gaia", "known_mimic_candidate", bool(
        len(mimic) == 1 and bool(full_mimics[mimic.index[0]]) and not bool(half_mimics[mimic.index[0]])
    ), f"source_id={source_id}")
    audit.check("gaia", "target_astrometric_caution_retained", bool(
        _as_bool(target_row["duplicated_source"]) and float(target_row["ruwe"]) < 1.4
    ), f"duplicated_source={_as_bool(target_row['duplicated_source'])} RUWE={float(target_row['ruwe']):.3f}")
    audit.warning("gaia", "bandpass_limit",
                  "The recomputation verifies archived Gaia G-band screening only; it is not a TESS PRF/aperture contamination model.")
