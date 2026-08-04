"""Verification checks for Stage 5 pixel source analysis and TPF depth maps."""

from __future__ import annotations

import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS

from ..core import ROOT, SECTORS, Verification, _close, _load


def _pixel_depth_result(fits_path, inputs, source_coordinates):
    quality_hard = 24319
    with fits.open(fits_path, memmap=False) as hdul:
        pixel_hdu, aperture_hdu = hdul[1], hdul[2]
        aperture = np.asarray(aperture_hdu.data, dtype=np.int16)
        pipeline = (aperture & 2) != 0
        wcs = WCS(aperture_hdu.header)
        time_values = np.asarray(pixel_hdu.data["TIME"], dtype=np.float64)
        quality = np.asarray(pixel_hdu.data["QUALITY"], dtype=np.int64)
        flux = np.asarray(pixel_hdu.data["FLUX"], dtype=np.float64)
    good = np.isfinite(time_values) & ((quality & quality_hard) == 0) & np.all(
        np.isfinite(flux), axis=(1, 2)
    )
    time_values, flux = time_values[good], flux[good]
    phase_hours = (((time_values - inputs["t0"] + inputs["period"] / 2.0)
                    % inputs["period"]) - inputs["period"] / 2.0) * 24.0
    in_transit = np.abs(phase_hours) < inputs["duration"] / 2.0
    out_transit = ((np.abs(phase_hours) > 1.2 * inputs["duration"])
                   & (np.abs(phase_hours) < 2.5 * inputs["duration"]))
    in_image = np.nanmedian(flux[in_transit], axis=0)
    out_image = np.nanmedian(flux[out_transit], axis=0)
    valid = np.isfinite(in_image) & np.isfinite(out_image) & (out_image > 0)
    depth = np.full(aperture.shape, np.nan, dtype=np.float64)
    depth[valid] = (out_image[valid] - in_image[valid]) / out_image[valid]
    positive = np.where(np.isfinite(depth) & (depth > 0), depth, 0.0)
    yy, xx = np.indices(depth.shape, dtype=np.float64)
    centroid_x = float(np.sum(positive * xx) / np.sum(positive))
    centroid_y = float(np.sum(positive * yy) / np.sum(positive))
    target_x, target_y = wcs.world_to_pixel_values(inputs["ra"], inputs["dec"])
    source_x, source_y = wcs.world_to_pixel_values(source_coordinates["ra"], source_coordinates["dec"])
    target_x, target_y = float(np.asarray(target_x)), float(np.asarray(target_y))
    source_x, source_y = float(np.asarray(source_x)), float(np.asarray(source_y))
    target_distance = float(np.hypot(centroid_x - target_x, centroid_y - target_y))
    source_distance = float(np.hypot(centroid_x - source_x, centroid_y - source_y))
    source_in_aperture = bool(
        0 <= int(round(source_y)) < aperture.shape[0]
        and 0 <= int(round(source_x)) < aperture.shape[1]
        and pipeline[int(round(source_y)), int(round(source_x))]
    )
    return {
        "n_cadences": int(len(time_values)), "n_in": int(np.sum(in_transit)),
        "n_out": int(np.sum(out_transit)), "centroid_x": centroid_x,
        "centroid_y": centroid_y, "target_distance": target_distance,
        "source_distance": source_distance, "source_in_aperture": source_in_aperture,
    }


def verify_stage5_pixels(audit: Verification) -> None:
    report = _load("outputs/stage5_pixel_source_analysis.json")
    inventory = _load("outputs/asteroseismic_input_inventory.json")
    metadata = _load("data/official_toi_metadata.json")
    config = _load("data/config_corrected_120s.json")["transit_corrected_120s"]
    neighbors = pd.read_csv(ROOT / "outputs" / "gaia_dr3_neighbors.csv")
    source = neighbors.loc[neighbors["source_id"].astype(str) == "5347362002981716992"]
    audit.check("stage5_pixels", "mimic_is_selected_by_source_id", len(source) == 1,
                f"matches={len(source)}")
    source_coordinates = {"ra": float(source.iloc[0]["ra"]), "dec": float(source.iloc[0]["dec"])}
    inputs = {
        "ra": float(metadata["coordinates"]["ra_deg"]),
        "dec": float(metadata["coordinates"]["dec_deg"]),
        "period": float(config["period"]), "t0": float(config["t0"]),
        "duration": float(config["duration_hrs"]),
    }
    tpf_paths = {}
    for product in inventory["products"]:
        if product["product_type"] == "tpf" and product["cadence_seconds"] == 120:
            sector = int(product["sector"])
            if sector in SECTORS:
                tpf_paths[sector] = ROOT / product["relative_path"]
    audit.check("stage5_pixels", "six_frozen_tpfs_available", set(tpf_paths) == set(SECTORS),
                f"sectors={sorted(tpf_paths)}")
    stored = {int(row["sector"]): row for row in report["sector_results"]}
    recalculated = {}
    for sector in SECTORS:
        recalculated[sector] = _pixel_depth_result(tpf_paths[sector], inputs, source_coordinates)
    comparisons = []
    for sector in SECTORS:
        actual, expected = recalculated[sector], stored[sector]
        comparisons.append(all((
            actual["n_cadences"] == expected["n_cadences"],
            actual["n_in"] == expected["n_in"], actual["n_out"] == expected["n_out"],
            _close(actual["centroid_x"], expected["depth_map_centroid_x_pix"], rel=0, abs_tol=1e-10),
            _close(actual["centroid_y"], expected["depth_map_centroid_y_pix"], rel=0, abs_tol=1e-10),
            _close(actual["target_distance"], expected["depth_map_centroid_to_target_pix"], rel=0, abs_tol=1e-10),
            _close(actual["source_distance"], expected["depth_map_centroid_to_source_pix"], rel=0, abs_tol=1e-10),
            actual["source_in_aperture"] == expected["source_in_aperture"],
        )))
    audit.check("stage5_pixels", "raw_tpf_depth_maps_reproduced", all(comparisons),
                f"{sum(comparisons)}/{len(comparisons)} sectors")
    closer = sum(item["target_distance"] < item["source_distance"] for item in recalculated.values())
    audit.check("stage5_pixels", "reported_target_closer_count", closer == 4
                and report["summary"]["sectors_centroid_closer_to_target"] == 4,
                f"target_closer={closer}/6")
    audit.check("stage5_pixels", "source_remains_unresolved", report["status"] != "all_centroids_closer_to_target",
                report["status"])
    audit.warning("stage5_pixels", "localization_limit",
                  "This reproduces the depth-map centroid calculation, not a calibrated PRF localization likelihood.")
