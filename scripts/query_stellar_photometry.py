"""Freeze broadband catalog photometry used for stellar SED follow-up."""

import json
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
from astropy.coordinates import SkyCoord
from astroquery.vizier import Vizier


ROOT = Path(__file__).resolve().parent.parent
RA_DEG = 166.636671
DEC_DEG = -53.73198


def value(row, name):
    item = row[name]
    return None if getattr(item, "mask", False) else float(item)


def main():
    coordinate = SkyCoord(RA_DEG * u.deg, DEC_DEG * u.deg)
    tables = Vizier(columns=["*"], row_limit=5).query_region(
        coordinate,
        radius=3.0 * u.arcsec,
        catalog=["II/246/out", "II/328/allwise", "II/336/apass9"],
    )
    required = ["II/246/out", "II/328/allwise", "II/336/apass9"]
    missing = [catalog for catalog in required if catalog not in tables.keys()]
    if missing:
        raise RuntimeError(f"Missing VizieR catalog matches: {missing}")
    tmass = tables["II/246/out"][0]
    wise = tables["II/328/allwise"][0]
    apass = tables["II/336/apass9"][0]
    output = {
        "target": "TOI-3492 / TIC 81077799",
        "coordinates_icrs_deg": {"ra": RA_DEG, "dec": DEC_DEG},
        "query_radius_arcsec": 3.0,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "photometry": {
            "2MASS": {
                "catalog": "II/246/out",
                "identifier": str(tmass["2MASS"]),
                "J": {"mag": value(tmass, "Jmag"), "error": value(tmass, "e_Jmag")},
                "H": {"mag": value(tmass, "Hmag"), "error": value(tmass, "e_Hmag")},
                "Ks": {"mag": value(tmass, "Kmag"), "error": value(tmass, "e_Kmag")},
                "quality_flag": str(tmass["Qflg"]),
                "contamination_flag": str(tmass["Cflg"]),
            },
            "AllWISE": {
                "catalog": "II/328/allwise",
                "identifier": str(wise["AllWISE"]),
                **{
                    band: {
                        "mag": value(wise, f"{band}mag"),
                        "error": value(wise, f"e_{band}mag"),
                    }
                    for band in ("W1", "W2", "W3", "W4")
                },
                "quality_flag": str(wise["qph"]),
                "contamination_confusion_flag": str(wise["ccf"]),
                "extended_source_flag": int(wise["ex"]),
            },
            "APASS9": {
                "catalog": "II/336/apass9",
                "B": {"mag": value(apass, "Bmag"), "error": value(apass, "e_Bmag")},
                "g_prime": {"mag": value(apass, "g'mag"), "error": value(apass, "e_g'mag")},
                "V": {"mag": value(apass, "Vmag"), "error": value(apass, "e_Vmag")},
                "r_prime": {"mag": value(apass, "r'mag"), "error": value(apass, "e_r'mag")},
                "i_prime": {"mag": value(apass, "i'mag"), "error": value(apass, "e_i'mag")},
            },
        },
        "gaia_dr3_photometry_from_frozen_crosscheck": {
            "G": 8.83012866973877,
            "BP": 9.096477508544922,
            "RP": 8.400259971618652,
            "parallax_mas": 4.932393709472833,
            "parallax_error_mas": 0.013711396604776382,
        },
        "notes": [
            "Catalog magnitudes are frozen with their native quality flags.",
            "No isochrone or atmosphere-grid fit is performed by this query script.",
        ],
    }
    path = ROOT / "data" / "stellar_photometry.json"
    path.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))
    print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
