"""Map Gaia mimic-capable neighbors into the frozen SPOC apertures."""

import json
from pathlib import Path

import lightkurve as lk
import numpy as np


ROOT = Path(__file__).resolve().parent.parent


def nearest_aperture_distance(x, y, aperture):
    yy, xx = np.where(aperture)
    if len(xx) == 0:
        return np.nan
    return float(np.min(np.hypot(xx - x, yy - y)))


def main():
    gaia = json.loads(
        (ROOT / "outputs" / "gaia_contamination_check.json").read_text()
    )
    localization = json.loads(
        (ROOT / "outputs" / "tess_source_localization_120s.json").read_text()
    )
    inventory = json.loads(
        (ROOT / "outputs" / "asteroseismic_input_inventory.json").read_text()
    )
    centroid_by_sector = {
        row["sector"]: row for row in localization["sector_results"]
    }
    candidates = gaia["neighbor_summary"]["full_eclipse_mimic_candidates"]
    tpf_products = [
        item
        for item in inventory["products"]
        if item["product_type"] == "tpf" and item["cadence_seconds"] == 120
    ]
    if not tpf_products:
        raise RuntimeError("No frozen 120-s TPF products are listed")

    source_results = {
        str(candidate["source_id"]): {
            "source_id": str(candidate["source_id"]),
            "separation_arcsec": candidate["separation_arcsec"],
            "delta_g_mag": candidate["delta_g_mag"],
            "flux_ratio_vs_target_gband": candidate["flux_ratio_vs_target"],
            "sector_geometry": [],
        }
        for candidate in candidates
    }
    sector_apertures = []
    for product in tpf_products:
        path = ROOT / product["relative_path"]
        if not path.exists():
            raise FileNotFoundError(path)
        tpf = lk.TessTargetPixelFile(path, quality_bitmask="default")
        aperture = np.asarray(tpf.pipeline_mask, dtype=bool)
        sector = int(product["sector"])
        centroid = centroid_by_sector[sector]
        sector_apertures.append(
            {
                "sector": sector,
                "shape": list(aperture.shape),
                "n_pipeline_aperture_pixels": int(np.count_nonzero(aperture)),
            }
        )
        for candidate in candidates:
            x, y = tpf.wcs.world_to_pixel_values(candidate["ra"], candidate["dec"])
            x = float(np.asarray(x))
            y = float(np.asarray(y))
            ix, iy = int(np.rint(x)), int(np.rint(y))
            in_cutout = 0 <= iy < aperture.shape[0] and 0 <= ix < aperture.shape[1]
            in_aperture = bool(in_cutout and aperture[iy, ix])
            distance_to_aperture = nearest_aperture_distance(x, y, aperture)
            distance_to_difference_centroid = float(
                np.hypot(
                    centroid["difference_centroid_x_pix"] - x,
                    centroid["difference_centroid_y_pix"] - y,
                )
            )
            source_results[str(candidate["source_id"])]["sector_geometry"].append(
                {
                    "sector": sector,
                    "source_x_pix": x,
                    "source_y_pix": y,
                    "inside_tpf_cutout": in_cutout,
                    "nearest_pixel_in_pipeline_aperture": in_aperture,
                    "distance_to_nearest_aperture_pixel_pix": distance_to_aperture,
                    "distance_to_difference_centroid_pix": distance_to_difference_centroid,
                    "difference_centroid_distance_to_target_pix": centroid["offset_pix"],
                    "difference_centroid_closer_to_target_than_source": bool(
                        centroid["offset_pix"] < distance_to_difference_centroid
                    ),
                }
            )

    summaries = []
    for source in source_results.values():
        geometry = source["sector_geometry"]
        source["summary"] = {
            "inside_pipeline_aperture_sector_count": int(
                sum(row["nearest_pixel_in_pipeline_aperture"] for row in geometry)
            ),
            "inside_tpf_cutout_sector_count": int(
                sum(row["inside_tpf_cutout"] for row in geometry)
            ),
            "difference_centroid_closer_to_target_sector_count": int(
                sum(
                    row["difference_centroid_closer_to_target_than_source"]
                    for row in geometry
                )
            ),
            "median_distance_to_aperture_pix": float(
                np.median(
                    [row["distance_to_nearest_aperture_pixel_pix"] for row in geometry]
                )
            ),
        }
        summaries.append(
            {
                "source_id": source["source_id"],
                "separation_arcsec": source["separation_arcsec"],
                **source["summary"],
            }
        )

    nearest_mimic = min(summaries, key=lambda row: row["separation_arcsec"])
    result = {
        "status": "aperture_geometry_check_not_formal_prf_localization",
        "source": "Frozen SPOC 120-s TPF WCS and pipeline masks plus Gaia DR3 mimic-capable neighbors",
        "n_sectors": len(tpf_products),
        "n_full_eclipse_mimic_candidates_tested": len(candidates),
        "sector_apertures": sector_apertures,
        "nearest_mimic_candidate_summary": nearest_mimic,
        "candidate_summaries": summaries,
        "candidate_details": list(source_results.values()),
        "interpretation": "A source whose coordinate is outside the discrete SPOC aperture can still contribute PRF wings. This geometric test therefore strengthens source vetting but does not replace a calibrated TESS PRF fit or high-resolution imaging.",
    }
    output = ROOT / "outputs" / "source_specific_aperture_check.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(nearest_mimic, indent=2))
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
