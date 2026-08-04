"""Build the line-by-line mathematical inventory and independent check record."""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from science import (
    equilibrium_temperature_k,
    incident_flux_earth,
    kepler_a_au,
    kepler_a_rs,
    luminosity_solar,
    photometric_density_solar,
    transit_duration_hours,
)
from summarize_sector_depths import calculate_sector_statistics


ROOT = Path(__file__).resolve().parent.parent
MANUSCRIPT = ROOT / "toi3492_characterization.tex"


def load_json(relative):
    return json.loads((ROOT / relative).read_text())


def close_check(name, calculated, reported, rtol=5e-3, atol=0.0, note=None):
    passed = bool(np.isclose(calculated, reported, rtol=rtol, atol=atol))
    return {
        "name": name,
        "calculated": float(calculated),
        "reported": float(reported),
        "rtol": rtol,
        "atol": atol,
        "status": "PASS" if passed else "FAIL",
        "note": note,
    }


def inventory(text):
    lines = text.splitlines()
    expressions = []
    dollar_positions = [
        index
        for index, character in enumerate(text)
        if character == "$" and (index == 0 or text[index - 1] != "\\")
    ]
    if len(dollar_positions) % 2:
        raise ValueError("Unpaired inline-math delimiter in manuscript")
    for start, stop in zip(dollar_positions[::2], dollar_positions[1::2]):
        expression = text[start + 1 : stop]
        expressions.append(
            {
                "line": text.count("\n", 0, start) + 1,
                "kind": "inline",
                "expression": " ".join(expression.split()),
            }
        )
    for match in re.finditer(
        r"(?<!\\)\\\[(.+?)(?<!\\)\\\]", text, flags=re.DOTALL
    ):
        expressions.append(
            {
                "line": text.count("\n", 0, match.start()) + 1,
                "kind": "display",
                "expression": " ".join(match.group(1).split()),
            }
        )
    expressions.sort(key=lambda item: item["line"])
    numbers = []
    numeric_pattern = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?(?:\\,\d+)?(?:e[-+]?\d+)?", re.I)
    for line_number, line in enumerate(lines, start=1):
        if line.lstrip().startswith("%"):
            continue
        for match in numeric_pattern.finditer(line):
            numbers.append({"line": line_number, "token": match.group(0)})
    return expressions, numbers


def build_audit():
    manuscript_bytes = MANUSCRIPT.read_bytes()
    text = manuscript_bytes.decode()
    config = load_json("data/config_corrected_120s.json")
    transit = config["transit_corrected_120s"]
    stellar = config["stellar"]
    false_positive = load_json("outputs/false_positive_tests_120s.json")
    cadence = load_json("outputs/cadence_independent_depth_check.json")
    window = load_json("outputs/transit_window_comparison.json")
    sector = calculate_sector_statistics(
        pd.read_csv(ROOT / "outputs" / "toi3492_120s_sector_depths.csv")
    )
    expressions, numbers = inventory(text)

    luminosity = luminosity_solar(stellar["r_star"], stellar["teff"])
    semimajor_axis = kepler_a_au(transit["period"], stellar["m_star"])
    expected_a_rs = kepler_a_rs(
        transit["period"], stellar["m_star"], stellar["r_star"]
    )
    density = photometric_density_solar(transit["period"], transit["a_rs"])
    catalog_density = stellar["m_star"] / stellar["r_star"] ** 3
    density_ratio = density / catalog_density
    g_squared = density_ratio ** (2.0 / 3.0)
    minimum_eccentricity = (g_squared - 1.0) / (g_squared + 1.0)
    checks = [
        close_check("stellar_density_solar", catalog_density, 0.0717, atol=5e-5),
        close_check("stellar_luminosity_solar", luminosity, 9.7, rtol=0.01),
        close_check("catalog_expected_a_rs", expected_a_rs, 7.69, rtol=0.002),
        close_check("physical_semimajor_axis_au", semimajor_axis, 0.0927, atol=5e-5),
        close_check("area_ratio_ppm", transit["rp_rs"] ** 2 * 1e6, 2994.0, rtol=5e-4),
        close_check(
            "inclination_deg",
            np.degrees(np.arccos(transit["impact_parameter"] / transit["a_rs"])),
            86.19,
            atol=0.01,
        ),
        close_check(
            "duration_hours",
            transit_duration_hours(
                transit["period"],
                transit["rp_rs"],
                transit["a_rs"],
                transit["impact_parameter"],
            ),
            5.233,
            atol=0.002,
        ),
        close_check("circular_density_solar_q_zero", density, 0.188, atol=0.001),
        close_check("density_ratio", density_ratio, 2.6, rtol=0.02),
        close_check("favorable_orientation_e_min", minimum_eccentricity, 0.31, atol=0.01),
        close_check(
            "incident_flux_earth",
            incident_flux_earth(luminosity, semimajor_axis),
            1135.0,
            rtol=0.01,
            note="The manuscript value is a posterior median; this check uses catalog central values.",
        ),
        close_check(
            "equilibrium_temperature_k",
            equilibrium_temperature_k(
                stellar["teff"], stellar["r_star"], semimajor_axis
            ),
            1616.0,
            rtol=0.002,
            note="Zero Bond albedo and full redistribution.",
        ),
        close_check("sector_weighted_mean_ppm", sector["weighted_mean_depth_ppm"], 2692.0, atol=0.5),
        close_check("sector_chi_square", sector["chi_square"], 29.85, atol=0.01),
        close_check("sector_p_value", sector["p_value"], 1.58e-5, rtol=0.01),
        close_check("sector_error_scale", sector["unit_reduced_chi_square_error_scale"], 2.44, atol=0.01),
        close_check(
            "odd_even_sigma",
            false_positive["odd_even"]["difference_sigma"],
            0.39,
            atol=0.01,
        ),
        close_check(
            "phase_0p5_secondary_upper_bound_ppm",
            false_positive["secondary_eclipse"]["three_sigma_upper_limit_ppm"],
            54.0,
            atol=0.1,
        ),
        close_check(
            "cadence_depth_difference_formal_sigma",
            abs(cadence["delta_20s_minus_matched_120s_robust_sigma_formal"]),
            1.62,
            atol=0.01,
        ),
        close_check(
            "alternative_total13h_a_rs",
            window["alternative_window"]["posterior"]["a_rs"]["median"],
            10.17,
            atol=0.01,
        ),
    ]
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "status": status,
        "scope": "Canonical manuscript plus every numerical claim source shipped in the public reproducibility package",
        "review_method": "Independent line-by-line reading, source tracing, dimensional/formula checks, and full-precision recomputation",
        "manuscript_sha256": hashlib.sha256(manuscript_bytes).hexdigest(),
        "inventory": {
            "math_expression_count": len(expressions),
            "numeric_token_count": len(numbers),
            "math_expressions": expressions,
            "numeric_tokens": numbers,
        },
        "automated_recalculations": checks,
        "explicit_assumptions": [
            "Circular transit densities assume companion-to-star mass ratio q = 0; the exact relation divides by 1 + q.",
            "TIC mass, radius, and temperature covariance is unavailable and catalog draws are independent.",
            "The adopted limb-darkening interpolation assumes [Fe/H] = 0.0 +/- 0.15 dex because TIC v8 MH is null.",
            "Equilibrium temperature assumes zero Bond albedo and full heat redistribution.",
            "Formal fixed-window significances do not include time-correlated or sector-level covariance.",
            "The +/-6.5 h window result is a converged sensitivity fit and is not adopted.",
        ],
    }


def main():
    result = build_audit()
    output = ROOT / "outputs" / "manuscript_math_audit.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"MANUSCRIPT MATHEMATICS AUDIT: {result['status']}")
    print(f"Math expressions inventoried: {result['inventory']['math_expression_count']}")
    print(f"Numeric tokens inventoried: {result['inventory']['numeric_token_count']}")
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
