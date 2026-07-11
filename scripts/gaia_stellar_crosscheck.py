"""Fetch and freeze Gaia DR3 stellar and RVS summary information."""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astroquery.gaia import Gaia

from science import R_EARTH_PER_RSUN, kepler_a_rs


ROOT = Path(__file__).resolve().parent.parent
SOURCE_ID = 5347362071701193344
OUTPUT = ROOT / "outputs" / "gaia_stellar_crosscheck.json"

ASTROPHYSICAL_COLUMNS = [
    "teff_gspphot", "teff_gspphot_lower", "teff_gspphot_upper",
    "logg_gspphot", "logg_gspphot_lower", "logg_gspphot_upper",
    "mh_gspphot", "mh_gspphot_lower", "mh_gspphot_upper",
    "azero_gspphot", "radius_gspphot", "radius_gspphot_lower",
    "radius_gspphot_upper", "radius_flame", "radius_flame_lower",
    "radius_flame_upper", "lum_flame", "lum_flame_lower",
    "lum_flame_upper", "mass_flame", "mass_flame_lower",
    "mass_flame_upper", "age_flame", "age_flame_lower",
    "age_flame_upper", "teff_gspspec", "logg_gspspec", "mh_gspspec",
    "flags_gspspec",
]

RVS_COLUMNS = [
    "parallax", "parallax_error", "radial_velocity",
    "radial_velocity_error", "rv_nb_transits", "rv_time_duration",
    "rv_amplitude_robust", "rv_chisq_pvalue", "rv_renormalised_gof",
    "grvs_mag", "rv_expected_sig_to_noise", "non_single_star", "ruwe",
    "ipd_frac_multi_peak", "ipd_gof_harmonic_amplitude",
]


def native(value):
    if np.ma.is_masked(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def fetch(table, columns):
    query = (
        f"SELECT {','.join(columns)} FROM {table} "
        f"WHERE source_id={SOURCE_ID}"
    )
    result = Gaia.launch_job(query).get_results()
    if len(result) != 1:
        raise RuntimeError(f"Expected one Gaia row, received {len(result)}")
    return {column: native(result[column][0]) for column in result.colnames}


def main():
    astrophysical = fetch("gaiadr3.astrophysical_parameters", ASTROPHYSICAL_COLUMNS)
    rvs = fetch("gaiadr3.gaia_source", RVS_COLUMNS)
    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    period = config["transit"]["period"]
    rp_rs = config["transit"]["rp_rs"]

    radius = astrophysical["radius_flame"]
    mass = astrophysical["mass_flame"]
    density = mass / radius**3
    expected_a_rs = float(kepler_a_rs(period, mass, radius))
    radius_planet = rp_rs * radius * R_EARTH_PER_RSUN

    output = {
        "source": "Gaia DR3 gaia_source and astrophysical_parameters",
        "source_id": SOURCE_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "gsp_phot_and_flame": astrophysical,
        "rvs_summary": rvs,
        "derived_from_flame_medians": {
            "stellar_density_solar": density,
            "expected_circular_a_rs": expected_a_rs,
            "planet_radius_earth_using_adopted_rp_rs": radius_planet,
        },
        "interpretation": {
            "stellar": (
                "Gaia GSP-Phot/FLAME independently supports a roughly "
                "2.67-Rsun evolved host. Its expected circular a/Rstar remains "
                "well below the photometry-only circular transit result."
            ),
            "rvs": (
                "Gaia reports only summary RVS statistics, not public epoch "
                "velocities. The 2.08-km/s robust range and p=0.046 constancy "
                "statistic motivate dedicated RV follow-up but cannot yield an "
                "orbit or companion mass."
            ),
            "gsp_spec": (
                "The GSP-Spec atmospheric solution is retained for provenance "
                "but not adopted because its flag string is non-clean and it "
                "conflicts with GSP-Phot/FLAME and TIC."
            ),
        },
        "limitations": [
            "GSP-Phot and FLAME are model-dependent and not independent of each other.",
            "The very small quoted Gaia percentile intervals are internal formal intervals and do not represent full external systematics.",
            "non_single_star=0 means no published Gaia NSS solution; it does not prove the star is single.",
            "Gaia field-of-view RVS transits are spacecraft visits, not planetary transits.",
        ],
    }
    OUTPUT.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
    print(f"Wrote {OUTPUT.name}")


if __name__ == "__main__":
    main()
