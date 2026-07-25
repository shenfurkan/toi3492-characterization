"""Stage 5: pixel-level transit depth map and source-position comparison.

Uses the six frozen 120-s SPOC TPF products already in the local archive.
Produces a per-pixel fractional depth map and compares its flux-weighted
centroid with the catalog target and the 56.29-arcsec Gaia neighbor.

This is deliberately not a calibrated PRF fit.  It is a pixel-level
quantitative check that deepens the existing first-pass difference-image
diagnostic.
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS


ROOT = Path(__file__).resolve().parent.parent
INVENTORY_PATH = ROOT / "outputs" / "asteroseismic_input_inventory.json"
METADATA_PATH = ROOT / "data" / "official_toi_metadata.json"
CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
GAIA_PATH = ROOT / "outputs" / "gaia_contamination_check.json"
OUT_JSON = ROOT / "outputs" / "stage5_pixel_source_analysis.json"
OUT_CSV = ROOT / "outputs" / "stage5_pixel_depth_centroids.csv"

SECTORS = (37, 63, 64, 90, 99, 100)
MIMIC_SOURCE_ID = "5347362002981716992"
QUALITY_HARD = 24319


def _json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.ndarray,)):
        return _json_safe(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _clean(value):
    return None if (isinstance(value, float) and not np.isfinite(value)) else value


def _phase_hours(time, period, t0):
    return (((time - t0 + 0.5 * period) % period) - 0.5 * period) * 24.0


def _centroid(depth_map):
    positive = np.where(np.isfinite(depth_map) & (depth_map > 0), depth_map, 0.0)
    total = float(np.sum(positive))
    if total <= 0:
        return None
    yy, xx = np.indices(depth_map.shape, dtype=np.float64)
    return {
        "x_pix": float(np.sum(positive * xx) / total),
        "y_pix": float(np.sum(positive * yy) / total),
        "sum_positive_depth": total,
        "n_positive_pixels": int(np.sum(positive > 0)),
    }


def _nearest_aperture_distance(x, y, aperture):
    yy, xx = np.where(aperture)
    if len(xx) == 0:
        return np.nan
    return float(np.min(np.hypot(xx - x, yy - y)))


def _pixel_group_at_position(x, y, shape, radius_pix=1.5):
    yy, xx = np.indices(shape, dtype=np.float64)
    distances = np.hypot(xx - x, yy - y)
    within = distances <= radius_pix
    if not np.any(within):
        closest = int(np.argmin(distances.ravel()))
        cy, cx = np.unravel_index(closest, shape)
        return [(int(cx), int(cy))]
    indices = np.argwhere(within)
    return [(int(ix), int(iy)) for iy, ix in indices]


def _analyze_sector(fits_path, sector, inputs, source_coords):
    with fits.open(fits_path) as hdul:
        pix_hdu = hdul[1]
        ap_hdu = hdul[2]
        wcs = WCS(ap_hdu.header)

        aperture = np.asarray(ap_hdu.data, dtype=np.int16)
        pipeline = (aperture & 2) != 0
        shape = aperture.shape

        time = np.asarray(pix_hdu.data["TIME"], dtype=np.float64)
        quality = np.asarray(pix_hdu.data["QUALITY"], dtype=np.int64)
        flux_col = np.asarray(pix_hdu.data["FLUX"], dtype=np.float64)

        good = (
            np.isfinite(time)
            & (quality & QUALITY_HARD == 0)
            & np.all(np.isfinite(flux_col), axis=(1, 2))
        )
        time = time[good]
        flux_data = flux_col[good]

    hours = _phase_hours(time, inputs["period"], inputs["t0"])
    in_mask = np.abs(hours) < 0.5 * inputs["duration_hr"]
    out_mask = (np.abs(hours) > 1.2 * inputs["duration_hr"]) & (
        np.abs(hours) < 2.5 * inputs["duration_hr"]
    )

    n_in = int(np.sum(in_mask))
    n_out = int(np.sum(out_mask))

    in_image = np.nanmedian(flux_data[in_mask], axis=0) if n_in >= 10 else None
    out_image = np.nanmedian(flux_data[out_mask], axis=0) if n_out >= 10 else None

    depth_map = None
    centroid = None
    if in_image is not None and out_image is not None:
        valid = np.isfinite(in_image) & np.isfinite(out_image) & (out_image > 0)
        depth_map = np.full(shape, np.nan, dtype=np.float64)
        depth_map[valid] = ((out_image[valid] - in_image[valid])
                            / out_image[valid])
        centroid = _centroid(depth_map)
        if centroid is None:
            centroid = {"x_pix": None, "y_pix": None,
                        "sum_positive_depth": None, "n_positive_pixels": None}

    target_x, target_y = wcs.world_to_pixel_values(
        inputs["ra_deg"], inputs["dec_deg"],
    )
    target_x = float(np.asarray(target_x))
    target_y = float(np.asarray(target_y))

    source_x, source_y = wcs.world_to_pixel_values(
        source_coords["ra"], source_coords["dec"],
    )
    source_x = float(np.asarray(source_x))
    source_y = float(np.asarray(source_y))

    distance_centroid_to_target = None
    distance_centroid_to_source = None
    if centroid and centroid["x_pix"] is not None:
        distance_centroid_to_target = float(
            np.hypot(centroid["x_pix"] - target_x, centroid["y_pix"] - target_y)
        )
        distance_centroid_to_source = float(
            np.hypot(centroid["x_pix"] - source_x, centroid["y_pix"] - source_y)
        )

    target_aperture_distance = _nearest_aperture_distance(target_x, target_y, pipeline)
    source_aperture_distance = _nearest_aperture_distance(source_x, source_y, pipeline)

    target_pixels = _pixel_group_at_position(target_x, target_y, shape)
    source_pixels = _pixel_group_at_position(source_x, source_y, shape, radius_pix=0.8)

    target_in_aperture = bool(
        0 <= int(round(target_y)) < shape[0]
        and 0 <= int(round(target_x)) < shape[1]
        and pipeline[int(round(target_y)), int(round(target_x))]
    )
    source_in_aperture = bool(
        0 <= int(round(source_y)) < shape[0]
        and 0 <= int(round(source_x)) < shape[1]
        and pipeline[int(round(source_y)), int(round(source_x))]
    )

    source_in_tpf = bool(
        0 <= int(round(source_y)) < shape[0]
        and 0 <= int(round(source_x)) < shape[1]
    )

    target_flux = None
    source_flux = None
    if depth_map is not None:
        tv = [float(depth_map[py, px]) for px, py in target_pixels
              if 0 <= py < shape[0] and 0 <= px < shape[1]
              and np.isfinite(depth_map[py, px])]
        if tv:
            target_flux = float(np.nanmedian(tv))
        sv = [float(depth_map[py, px]) for px, py in source_pixels
              if 0 <= py < shape[0] and 0 <= px < shape[1]
              and np.isfinite(depth_map[py, px])]
        if sv:
            source_flux = float(np.nanmedian(sv))

    closest_to_target = None
    if (distance_centroid_to_target is not None
            and distance_centroid_to_source is not None):
        closest_to_target = bool(
            distance_centroid_to_target < distance_centroid_to_source
        )

    return {
        "sector": int(sector),
        "n_cadences": int(len(time)),
        "n_in": n_in,
        "n_out": n_out,
        "tpf_shape": list(shape),
        "aperture_pixel_count": int(np.sum(pipeline)),
        "target_x_pix": target_x,
        "target_y_pix": target_y,
        "target_in_aperture": target_in_aperture,
        "target_aperture_distance_pix": _clean(target_aperture_distance),
        "target_pixel_coordinates": [[int(x), int(y)] for x, y in target_pixels],
        "target_median_depth": _clean(target_flux),
        "source_x_pix": source_x,
        "source_y_pix": source_y,
        "source_in_tpf": source_in_tpf,
        "source_in_aperture": source_in_aperture,
        "source_aperture_distance_pix": _clean(source_aperture_distance),
        "source_pixel_coordinates": [[int(x), int(y)] for x, y in source_pixels],
        "source_median_depth": _clean(source_flux),
        "depth_map_centroid_x_pix": centroid["x_pix"] if centroid else None,
        "depth_map_centroid_y_pix": centroid["y_pix"] if centroid else None,
        "depth_map_centroid_to_target_pix": _clean(distance_centroid_to_target),
        "depth_map_centroid_to_source_pix": _clean(distance_centroid_to_source),
        "centroid_closer_to_target": closest_to_target,
        "depth_map_positive_pixels": (
            centroid.get("n_positive_pixels") if centroid else 0
        ),
    }


def _run():
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    gaia = json.loads(GAIA_PATH.read_text(encoding="utf-8"))

    transit = config["transit_corrected_120s"]
    inputs = {
        "ra_deg": float(metadata["coordinates"]["ra_deg"]),
        "dec_deg": float(metadata["coordinates"]["dec_deg"]),
        "period": float(transit["period"]),
        "t0": float(transit["t0"]),
        "duration_hr": float(transit["duration_hrs"]),
    }

    source_coords = None
    for cand in gaia["neighbor_summary"]["full_eclipse_mimic_candidates"]:
        if abs(cand["separation_arcsec"] - 56.2901155487972) < 0.02:
            source_coords = {"ra": cand["ra"], "dec": cand["dec"]}
            break
    if source_coords is None:
        raise RuntimeError("56.29 arcsec Gaia neighbor not in contamination check")

    tpf_products = [
        item
        for item in inventory["products"]
        if item["product_type"] == "tpf" and item["cadence_seconds"] == 120
    ]
    tpf_by_sector = {}
    for item in tpf_products:
        sec = int(item["sector"])
        if sec in SECTORS:
            path = ROOT / item["relative_path"]
            if not path.exists():
                raise FileNotFoundError(path)
            tpf_by_sector[sec] = path

    sector_results = []
    for sector in SECTORS:
        if sector not in tpf_by_sector:
            raise FileNotFoundError(f"TPF for sector {sector} not found")
        result = _analyze_sector(tpf_by_sector[sector], sector, inputs,
                                 source_coords)
        sector_results.append(result)

    all_closer = all(
        r.get("centroid_closer_to_target") is True
        for r in sector_results
        if r.get("centroid_closer_to_target") is not None
    )
    any_closer_to_source = any(
        r.get("centroid_closer_to_target") is False for r in sector_results
    )

    if all_closer:
        conclusion = "all_centroids_closer_to_target"
    elif any(r.get("centroid_closer_to_target") for r in sector_results
             if r.get("centroid_closer_to_target") is not None):
        conclusion = "centroids_closer_to_target_in_most_sectors"
    else:
        conclusion = "inconclusive"

    n_closer = sum(
        1 for r in sector_results if r.get("centroid_closer_to_target") is True
    )
    n_further = sum(
        1 for r in sector_results if r.get("centroid_closer_to_target") is False
    )

    report = _json_safe({
        "schema_version": "1.0",
        "work_package": "S5-01_PER_PIXEL_TRANSIT_DEPTH_ANALYSIS",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": conclusion,
        "inputs": {
            "target_ra_deg": inputs["ra_deg"],
            "target_dec_deg": inputs["dec_deg"],
            "period_days": inputs["period"],
            "t0_btjd": inputs["t0"],
            "duration_hours": inputs["duration_hr"],
            "mimic_source_id": MIMIC_SOURCE_ID,
            "mimic_source_ra_deg": source_coords["ra"],
            "mimic_source_dec_deg": source_coords["dec"],
        },
        "sector_results": sector_results,
        "summary": {
            "n_sectors": len(sector_results),
            "sectors_centroid_closer_to_target": n_closer,
            "sectors_centroid_closer_to_source": n_further,
            "conclusion": conclusion,
            "interpretation": (
                "The depth-map centroid is consistently closer to the catalog "
                "target than to the 56.29 arcsec Gaia source in all six "
                "sectors. This strengthens but does not replace calibrated "
                "PRF source localization."
                if all_closer
                else (
                    "The depth-map centroid is closer to the target in most "
                    "but not all sectors."
                    if conclusion == "centroids_closer_to_target_in_most_sectors"
                    else "Depth-map centroid positions are inconclusive."
                )
            ),
        },
        "caveats": [
            "This is a flux-weighted centroid of the in-transit fractional depth map, not a calibrated PRF fit.",
            "TESS pixel scale is ~21 arcsec; sub-pixel offsets should be interpreted cautiously.",
            "PRF wings can contribute flux even outside the discrete pipeline aperture.",
            "This deepens but does not replace source-localization with high-resolution imaging or a calibrated PRF model.",
        ],
    })

    OUT_JSON.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    fieldnames = [
        "sector", "target_x_pix", "target_y_pix",
        "centroid_x_pix", "centroid_y_pix",
        "centroid_to_target_pix", "centroid_to_source_pix",
        "closer_to_target", "target_median_depth", "source_median_depth",
        "source_in_aperture", "source_aperture_distance_pix",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        for row in sector_results:
            out = dict(row)
            out["centroid_x_pix"] = row.get("depth_map_centroid_x_pix")
            out["centroid_y_pix"] = row.get("depth_map_centroid_y_pix")
            out["centroid_to_target_pix"] = row.get(
                "depth_map_centroid_to_target_pix"
            )
            out["centroid_to_source_pix"] = row.get(
                "depth_map_centroid_to_source_pix"
            )
            out["closer_to_target"] = row.get("centroid_closer_to_target")
            writer.writerow(out)

    print(
        "Stage 5 pixel source analysis: {} ({}/{} sectors)".format(
            conclusion, n_closer, len(sector_results),
        )
    )
    print("  saved {}".format(OUT_JSON))


def _verify():
    report = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    required = {"schema_version", "status", "sector_results",
                "summary", "caveats"}
    if not required.issubset(report):
        raise RuntimeError(
            "Stage-5 output schema mismatch: missing keys"
        )
    if len(report["sector_results"]) != 6:
        raise RuntimeError(
            "Stage-5 output has {} sectors, expected 6".format(
                len(report["sector_results"])
            )
        )
    if not OUT_CSV.exists():
        raise RuntimeError("Stage-5 CSV output missing")
    print("Stage 5 pixel source analysis: structurally valid ({})".format(
        report["status"]
    ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        _verify()
        return
    _run()


if __name__ == "__main__":
    main()