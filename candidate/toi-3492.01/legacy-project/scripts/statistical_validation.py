"""Assemble measured false-positive diagnostics without inventing an FPP.

The previous implementation normalized arbitrary EB/BEB prior weights and
reported the result as a Morton-style false-positive probability.  That is
not a calibrated population calculation.  This script now records only the
measured diagnostics and explicitly leaves the formal FPP undefined.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _load(path):
    return json.loads(path.read_text())


def main():
    config = _load(ROOT / "data" / "config_corrected_120s.json")
    gaia = _load(ROOT / "outputs" / "gaia_contamination_check.json")
    fp = _load(ROOT / "outputs" / "false_positive_tests_120s.json")

    aperture_42 = next(
        item
        for item in gaia["aperture_flux_summary_gband"]
        if item["radius_arcsec"] == 42.0
    )
    mimics_42 = [
        item
        for item in gaia["neighbor_summary"]["full_eclipse_mimic_candidates"]
        if item["separation_arcsec"] <= 42.0
    ]
    density = config["transit_corrected_120s"]["derived_posterior"]

    result = {
        "method": "Measured false-positive diagnostic summary",
        "formal_fpp": None,
        "formal_fpp_available": False,
        "statistical_validation_claim_supported": False,
        "reason": (
            "No calibrated planet, eclipsing-binary, and background-binary "
            "population model with a common likelihood was run."
        ),
        "odd_even": fp["odd_even"],
        "secondary_eclipse": fp["secondary_eclipse"],
        "gaia_42arcsec": {
            "n_neighbors": aperture_42["n_neighbors"],
            "g_band_flux_ratio_sum": aperture_42[
                "neighbor_flux_ratio_sum_gband"
            ],
            "n_full_eclipse_mimics": len(mimics_42),
            "bandpass_caveat": (
                "Gaia G-band flux ratios are not a TESS PRF/aperture model."
            ),
        },
        "astrodensity": {
            "photometric_density_solar": density["photometric_density_solar"],
            "catalog_density_solar": density["catalog_density_solar"],
            "difference_sigma": density["density_difference_sigma"],
        },
        "interpretation": (
            "The odd/even, phase-0.5 secondary, and Gaia checks do not reveal "
            "an obvious false positive. They do not statistically validate or "
            "confirm the candidate."
        ),
    }

    output = ROOT / "outputs" / "statistical_validation_120s.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"Wrote {output.name}")


if __name__ == "__main__":
    main()
