"""Verification checks for transit geometry and sector depths statistics."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2_distribution

from ..core import ROOT, Verification, _close, _duration_hours, _load


def verify_transit_geometry(audit: Verification) -> None:
    config = _load("data/config_corrected_120s.json")
    raw = np.load(ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy", allow_pickle=False)
    diagnostics = _load("outputs/mcmc_diagnostics_120s_corrected.json")
    flat = raw[int(diagnostics["flat_discard_steps"]):].reshape(-1, raw.shape[-1])
    transit = config["transit"]
    corrected = config["transit_corrected_120s"]
    duplicate_fields = (
        "period", "t0", "rp_rs", "rp_rs_err", "a_rs", "a_rs_err",
        "impact_parameter", "impact_parameter_err", "inc", "inc_err",
        "depth_ppm", "duration_hrs", "rp_earth", "rp_earth_err",
    )
    audit.check("transit_geometry", "duplicated_config_fields_agree", all(
        _close(transit[name], corrected[name], rel=0, abs_tol=1e-12)
        for name in duplicate_fields
    ), f"{len(duplicate_fields)} shared fields")
    rp, a_rs, impact = flat[:, 0], flat[:, 1], flat[:, 2]
    duration = _duration_hours(rp, a_rs, impact, transit["period"])
    inclination = np.degrees(np.arccos(impact / a_rs))
    density_solar = (4.0 * math.pi**2 * a_rs**3
                     / (2942.2062 * transit["period"]**2))
    derived = corrected["derived_posterior"]
    audit.check("transit_geometry", "duration_posterior", _close(
        np.median(duration), derived["duration_hours"]["median"], rel=0, abs_tol=1e-10,
    ), f"median={float(np.median(duration)):.8f}h")
    inclination_from_marginals = math.degrees(math.acos(
        transit["impact_parameter"] / transit["a_rs"]
    ))
    audit.check("transit_geometry", "inclination_from_marginal_medians", _close(
        inclination_from_marginals, transit["inc"], rel=0, abs_tol=1e-10,
    ), f"median-of-draws={float(np.median(inclination)):.8f}; stored={inclination_from_marginals:.8f}")
    audit.check("transit_geometry", "photometric_density", _close(
        np.median(density_solar), derived["photometric_density_solar"]["median"],
        rel=0, abs_tol=1e-10,
    ), f"median={float(np.median(density_solar)):.8f} rho_sun")
    area_ppm = rp**2 * 1e6
    audit.check("transit_geometry", "area_ratio_quantiles", bool(np.allclose(
        np.quantile(area_ppm, [0.16, 0.50, 0.84]),
        [corrected["area_ratio_ppm_p16"], corrected["area_ratio_ppm"],
         corrected["area_ratio_ppm_p84"]],
        rtol=0, atol=1e-9,
    )), f"median={float(np.median(area_ppm)):.6f} ppm")
    draw_rng = np.random.default_rng(3492)
    stellar = config["stellar"]
    r_draw = draw_rng.normal(stellar["r_star"], stellar["r_star_err"], len(flat))
    m_draw = draw_rng.normal(stellar["m_star"], stellar["m_star_err"], len(flat))
    teff_draw = draw_rng.normal(stellar["teff"], stellar["teff_err"], len(flat))
    valid_stellar = (r_draw > 0) & (m_draw > 0) & (teff_draw > 0)
    rp_earth = flat[valid_stellar, 0] * r_draw[valid_stellar] * 109.076
    audit.check("transit_geometry", "conditional_planet_radius", bool(np.allclose(
        np.quantile(rp_earth, [0.16, 0.50, 0.84]),
        [corrected["rp_earth_p16"], transit["rp_earth"], corrected["rp_earth_p84"]],
        rtol=0, atol=1e-10,
    )), f"median={float(np.median(rp_earth)):.8f} R_earth")


def verify_sector_depths(audit: Verification) -> None:
    frame = pd.read_csv(ROOT / "outputs" / "toi3492_120s_sector_depths.csv")
    values = frame["depth_ppm"].to_numpy(float)
    errors = frame["depth_err_ppm"].to_numpy(float)
    weights = 1.0 / errors**2
    mean = float(np.sum(weights * values) / np.sum(weights))
    formal_error = float(math.sqrt(1.0 / np.sum(weights)))
    chi_square = float(np.sum((values - mean)**2 / errors**2))
    dof = len(values) - 1
    p_value = float(chi2_distribution.sf(chi_square, dof))
    scale = float(math.sqrt(chi_square / dof))
    statistics = _load("outputs/sector_depth_statistics.json")
    formal = _load("outputs/wp09a_formal_sector_audit.json")["statistics"]
    audit.check("sector_depths", "statistics_from_csv", all((
        _close(mean, statistics["weighted_mean_depth_ppm"]),
        _close(formal_error, statistics["weighted_mean_formal_error_ppm"]),
        _close(chi_square, statistics["chi_square"]),
        _close(p_value, statistics["p_value"], rel=1e-8, abs_tol=1e-14),
        _close(scale, statistics["unit_reduced_chi_square_error_scale"]),
        _close(mean, formal["weighted_mean_depth_ppm"]),
        _close(chi_square, formal["chi_square"]),
    )), f"mean={mean:.6f} chi2={chi_square:.6f} p={p_value:.3e}")
    audit.check("sector_depths", "formal_heterogeneity_gate", bool(
        chi_square > 0 and p_value < 0.001 and dof == 5
    ), f"dof={dof} p={p_value:.3e}")
