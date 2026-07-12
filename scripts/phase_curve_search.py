"""All-orbital-phase harmonic and secondary-eclipse search."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
PERIOD = 9.2224171
T0 = 2459314.5211550 - 2457000.0
DURATION_DAYS = 5.2326 / 24.0
BLOCK_DAYS = 0.5


def cluster_covariance(design, residual, sigma, cluster):
    """Return a finite-sample-corrected cluster-sandwich covariance."""
    weighted_design = design / sigma[:, None]
    weighted_residual = residual / sigma
    bread = np.linalg.inv(weighted_design.T @ weighted_design)
    meat = np.zeros((design.shape[1], design.shape[1]))
    groups = np.unique(cluster)
    for group in groups:
        mask = cluster == group
        score = weighted_design[mask].T @ weighted_residual[mask]
        meat += np.outer(score, score)
    n, p = design.shape
    correction = len(groups) / (len(groups) - 1.0) * (n - 1.0) / (n - p)
    return correction * bread @ meat @ bread, len(groups)


def main():
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    time = data["time"].to_numpy(float)
    phase_days = ((time - T0 + 0.5 * PERIOD) % PERIOD) - 0.5 * PERIOD
    keep = np.abs(phase_days) > 0.65 * DURATION_DAYS
    data = data.loc[keep].copy()
    time = data["time"].to_numpy(float)
    phase_days = phase_days[keep]
    angle = 2.0 * np.pi * phase_days / PERIOD
    sectors = sorted(int(value) for value in data["sector"].unique())

    columns = []
    names = []
    cluster = np.empty(len(data), dtype=int)
    group_offset = 0
    for sector in sectors:
        in_sector = data["sector"].to_numpy(int) == sector
        columns.append(in_sector.astype(float))
        names.append(f"sector_{sector}_offset")
        centered_time = np.zeros(len(data))
        centered_time[in_sector] = time[in_sector] - np.median(time[in_sector])
        columns.append(centered_time)
        names.append(f"sector_{sector}_slope")
        local_block = np.floor(
            (time[in_sector] - np.min(time[in_sector])) / BLOCK_DAYS
        ).astype(int)
        cluster[in_sector] = group_offset + local_block
        group_offset += int(np.max(local_block)) + 1

    half_orbit_distance = np.abs(np.abs(phase_days) - 0.5 * PERIOD)
    eclipse = (half_orbit_distance < 0.5 * DURATION_DAYS).astype(float)
    physical_columns = {
        "reflection_semiamplitude": -np.cos(angle),
        "beaming_semiamplitude": np.sin(angle),
        "ellipsoidal_semiamplitude": -np.cos(2.0 * angle),
        "second_harmonic_sine_control": np.sin(2.0 * angle),
        "secondary_eclipse_depth": -eclipse,
    }
    for name, values in physical_columns.items():
        columns.append(values)
        names.append(name)

    design = np.column_stack(columns)
    flux = data["flux"].to_numpy(float)
    sigma = data["flux_err"].to_numpy(float)
    weighted_design = design / sigma[:, None]
    weighted_flux = flux / sigma
    coefficients = np.linalg.lstsq(weighted_design, weighted_flux, rcond=None)[0]
    model = design @ coefficients
    residual = flux - model
    covariance, n_clusters = cluster_covariance(
        design, residual, sigma, cluster
    )
    errors = np.sqrt(np.diag(covariance))

    components = {}
    for name in physical_columns:
        index = names.index(name)
        value_ppm = float(coefficients[index] * 1e6)
        error_ppm = float(errors[index] * 1e6)
        components[name] = {
            "value_ppm": value_ppm,
            "block_robust_error_ppm": error_ppm,
            "significance_sigma": value_ppm / error_ppm,
            "three_sigma_absolute_upper_bound_ppm": abs(value_ppm) + 3.0 * error_ppm,
        }

    sector_components = []
    sector_values = data["sector"].to_numpy(int)
    for sector in sectors:
        mask = sector_values == sector
        local_time = time[mask] - np.median(time[mask])
        local_design = np.column_stack(
            (
                np.ones(np.count_nonzero(mask)),
                local_time,
                *(values[mask] for values in physical_columns.values()),
            )
        )
        local_sigma = sigma[mask]
        local_flux = flux[mask]
        local_weighted_design = local_design / local_sigma[:, None]
        local_coefficients = np.linalg.lstsq(
            local_weighted_design, local_flux / local_sigma, rcond=None
        )[0]
        local_residual = local_flux - local_design @ local_coefficients
        local_covariance, local_clusters = cluster_covariance(
            local_design, local_residual, local_sigma, cluster[mask]
        )
        local_errors = np.sqrt(np.diag(local_covariance))
        sector_components.append(
            {
                "sector": sector,
                "n_points": int(np.count_nonzero(mask)),
                "n_clusters": local_clusters,
                "components": {
                    name: {
                        "value_ppm": float(local_coefficients[index + 2] * 1e6),
                        "block_robust_error_ppm": float(local_errors[index + 2] * 1e6),
                    }
                    for index, name in enumerate(physical_columns)
                },
            }
        )

    max_significance = max(
        abs(item["significance_sigma"]) for item in components.values()
    )
    reflection = components["reflection_semiamplitude"]
    unphysical_reflection = (
        reflection["value_ppm"] < 0.0
        and abs(reflection["significance_sigma"]) >= 3.0
    )
    result = {
        "status": "unphysical_phase_harmonic_detected_systematics_limited"
        if unphysical_reflection
        else (
            "no_significant_phase_curve_component"
            if max_significance < 3.0
            else "component_above_three_sigma_requires_followup"
        ),
        "source": "120 s SPOC PDCSAP reference light curve",
        "method": "weighted simultaneous harmonic and box-eclipse regression with sector offsets/slopes and 0.5-day cluster-sandwich covariance",
        "period_days": PERIOD,
        "t0_btjd": T0,
        "n_points_after_primary_transit_mask": int(len(data)),
        "n_sectors": len(sectors),
        "n_covariance_clusters": n_clusters,
        "primary_mask_half_width_hours": 0.65 * DURATION_DAYS * 24.0,
        "secondary_box_duration_hours": DURATION_DAYS * 24.0,
        "secondary_phase_scan_performed": False,
        "components": components,
        "sector_components": sector_components,
        "maximum_absolute_significance_sigma": max_significance,
        "interpretation": (
            "The strongest harmonic has the opposite sign from reflected/emitted planetary light, so the all-phase baseline is systematics-limited. No albedo, phase-curve mass, or physical harmonic detection is reported. The secondary box is fixed at phase 0.5; no eccentric-phase eclipse scan was performed."
            if unphysical_reflection
            else "This is a photometric vetting constraint, not a mass measurement or statistical validation."
        ),
    }
    output = ROOT / "outputs" / "phase_curve_search_120s.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
