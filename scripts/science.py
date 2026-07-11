"""Shared astrophysical calculations for the TOI-3492.01 analysis."""

import numpy as np


G_RSUN3_MSUN_DAY2 = 2942.2062
R_SUN_AU = 0.00465047
R_EARTH_PER_RSUN = 109.076
T_SUN_K = 5772.0


def kepler_a_rs(period_days, mass_solar, radius_solar):
    """Scaled semimajor axis implied by period, stellar mass, and radius."""
    return (
        G_RSUN3_MSUN_DAY2 * np.asarray(mass_solar) * np.asarray(period_days) ** 2
        / (4.0 * np.pi**2)
    ) ** (1.0 / 3.0) / np.asarray(radius_solar)


def kepler_a_au(period_days, mass_solar):
    """Physical semimajor axis from Kepler's third law."""
    a_rsun = (
        G_RSUN3_MSUN_DAY2 * np.asarray(mass_solar) * np.asarray(period_days) ** 2
        / (4.0 * np.pi**2)
    ) ** (1.0 / 3.0)
    return a_rsun * R_SUN_AU


def luminosity_solar(radius_solar, teff_k):
    """Stefan-Boltzmann luminosity in solar units."""
    return np.asarray(radius_solar) ** 2 * (np.asarray(teff_k) / T_SUN_K) ** 4


def incident_flux_earth(luminosity_lsun, semimajor_axis_au):
    """Incident flux relative to Earth at the semimajor axis."""
    return np.asarray(luminosity_lsun) / np.asarray(semimajor_axis_au) ** 2


def equilibrium_temperature_k(teff_k, radius_solar, semimajor_axis_au):
    """Equilibrium temperature for zero albedo and full redistribution."""
    return np.asarray(teff_k) * np.sqrt(
        np.asarray(radius_solar) * R_SUN_AU
        / (2.0 * np.asarray(semimajor_axis_au))
    )


def photometric_density_solar(period_days, a_rs):
    """Circular transit density in units of the Sun's mean density."""
    return (
        4.0 * np.pi**2 * np.asarray(a_rs) ** 3
        / (G_RSUN3_MSUN_DAY2 * np.asarray(period_days) ** 2)
    )


def eccentric_cosi(a_rs, impact_parameter, eccentricity, omega_deg):
    """cos(i) for a physical eccentric-orbit transit impact parameter."""
    omega = np.radians(omega_deg)
    return (
        np.asarray(impact_parameter)
        / np.asarray(a_rs)
        * (1.0 + np.asarray(eccentricity) * np.sin(omega))
        / (1.0 - np.asarray(eccentricity) ** 2)
    )


def transit_duration_hours(
    period_days,
    rp_rs,
    a_rs,
    impact_parameter,
    eccentricity=0.0,
    omega_deg=90.0,
):
    """Approximate first-to-fourth-contact duration for a transiting orbit."""
    cosi = eccentric_cosi(a_rs, impact_parameter, eccentricity, omega_deg)
    if np.any((cosi < 0.0) | (cosi > 1.0)):
        return np.nan
    sini = np.sqrt(1.0 - cosi**2)
    chord = np.sqrt(np.maximum((1.0 + np.asarray(rp_rs)) ** 2 - np.asarray(impact_parameter) ** 2, 0.0))
    argument = np.clip(chord / (np.asarray(a_rs) * sini), -1.0, 1.0)
    speed_factor = np.sqrt(1.0 - np.asarray(eccentricity) ** 2) / (
        1.0 + np.asarray(eccentricity) * np.sin(np.radians(omega_deg))
    )
    return np.asarray(period_days) / np.pi * np.arcsin(argument) * speed_factor * 24.0


def percentile_summary(values):
    """Return JSON-ready 16th, 50th, and 84th percentiles."""
    p16, p50, p84 = np.percentile(np.asarray(values), [16.0, 50.0, 84.0])
    return {"p16": float(p16), "median": float(p50), "p84": float(p84)}
