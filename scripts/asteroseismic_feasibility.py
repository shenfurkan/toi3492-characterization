"""Calculate preregistered seismic expectations and TESS-ATL detectability."""

import json
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from atl.atl import calc_detection_probability


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "asteroseismic_feasibility.json"
T_MAG = 8.4504
COORDINATE = SkyCoord(166.636735 * u.deg, -53.731971 * u.deg)
NUMAX_SUN = 3090.0
DNU_SUN = 135.1
TEFF_SUN = 5772.0
LOGG_SUN = 4.438


def numax(mass, radius, teff):
    return NUMAX_SUN * mass * radius ** -2 * (teff / TEFF_SUN) ** -0.5


def dnu(density):
    return DNU_SUN * density ** 0.5


def logg(mass, radius):
    import math

    return LOGG_SUN + math.log10(mass / radius ** 2)


def atl_result(teff, radius, gravity, sectors, cadence):
    probability, snr, predicted_numax, predicted_dnu = calc_detection_probability(
        T_MAG,
        teff,
        radius,
        gravity,
        sectors,
        cadence,
        COORDINATE,
        fap=0.05,
    )
    return {
        "sectors": sectors,
        "cadence_seconds": cadence,
        "probability": float(probability),
        "global_snr": float(snr),
        "numax_uhz": float(predicted_numax),
        "dnu_uhz": float(predicted_dnu),
    }


def main():
    scenarios = {
        "tic_mass_radius": {
            "teff_k": 6332.0,
            "mass_solar": 1.25,
            "radius_solar": 2.59262,
            "density_solar": 0.07172877471177881,
        },
        "gaia_flame_mass_radius": {
            "teff_k": 6061.15087890625,
            "mass_solar": 1.5139343738555908,
            "radius_solar": 2.6710479259490967,
            "density_solar": 0.07944416562519523,
        },
        "circular_transit_density": {
            "density_solar": 0.18786598965600354,
            "density_p16_solar": 0.1677412278830344,
            "density_p84_solar": 0.21262451227213455,
        },
    }
    for scenario in ("tic_mass_radius", "gaia_flame_mass_radius"):
        values = scenarios[scenario]
        values["consistent_logg"] = logg(
            values["mass_solar"], values["radius_solar"]
        )
        values["numax_scaling_uhz"] = numax(
            values["mass_solar"], values["radius_solar"], values["teff_k"]
        )
        values["dnu_density_scaling_uhz"] = dnu(values["density_solar"])
    transit = scenarios["circular_transit_density"]
    transit["dnu_density_scaling_uhz"] = dnu(transit["density_solar"])
    transit["dnu_p16_uhz"] = dnu(transit["density_p16_solar"])
    transit["dnu_p84_uhz"] = dnu(transit["density_p84_solar"])

    gaia_gspphot = {
        "teff_k": 6061.15087890625,
        "radius_solar": 2.6735999584198,
        "logg": 3.850600004196167,
    }
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "solar_references": {
            "numax_uhz": NUMAX_SUN,
            "dnu_uhz": DNU_SUN,
            "teff_k": TEFF_SUN,
            "logg_cgs": LOGG_SUN,
        },
        "scenarios": scenarios,
        "gaia_gspphot_atl_input": gaia_gspphot,
        "revised_atl": [
            atl_result(
                gaia_gspphot["teff_k"],
                gaia_gspphot["radius_solar"],
                gaia_gspphot["logg"],
                sectors=6,
                cadence=120,
            ),
            atl_result(
                gaia_gspphot["teff_k"],
                gaia_gspphot["radius_solar"],
                gaia_gspphot["logg"],
                sectors=3,
                cadence=20,
            ),
        ],
        "interpretation": (
            "The revised ATL probability is a pre-data detectability estimate, "
            "not a measured significance. Its dnu prediction uses the ATL "
            "radius/temperature relation and is not the FLAME-density scaling."
        ),
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
