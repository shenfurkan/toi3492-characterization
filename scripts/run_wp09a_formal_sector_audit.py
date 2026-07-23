"""Recompute WP-09A formal sector heterogeneity and detector descriptors."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "data" / "wp09a_formal_sector_protocol.json"
OUTPUT = ROOT / "outputs" / "wp09a_formal_sector_audit.json"
DESCRIPTORS = ROOT / "outputs" / "wp09a_sector_descriptors.csv"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def calculate(depths):
    depth = depths["depth_ppm"].to_numpy(np.float64)
    error = depths["depth_err_ppm"].to_numpy(np.float64)
    weight = error ** -2
    mean = float(np.sum(weight * depth) / np.sum(weight))
    statistic = float(np.sum(weight * (depth - mean) ** 2))
    dof = len(depth) - 1
    scale = float(np.sqrt(statistic / dof))
    formal_error = float(np.sqrt(1.0 / np.sum(weight)))
    return {
        "weighted_mean_depth_ppm": mean,
        "weighted_mean_formal_error_ppm": formal_error,
        "chi_square": statistic,
        "degrees_of_freedom": dof,
        "p_value": float(chi2.sf(statistic, dof)),
        "formal_error_scale": scale,
        "scatter_scaled_mean_error_ppm": formal_error * scale,
    }


def build(protocol):
    for item in protocol["inputs"].values():
        path = ROOT / item["relative_path"]
        if sha256_file(path) != item["sha256"]:
            raise RuntimeError("WP-09A input hash mismatch: {}".format(item["relative_path"]))
    depths = pd.read_csv(ROOT / protocol["inputs"]["sector_depths"]["relative_path"])
    inventory = load_json(ROOT / protocol["inputs"]["phase3_inventory"]["relative_path"])
    phase4 = load_json(ROOT / protocol["inputs"]["phase4_report"]["relative_path"])
    telemetry = pd.read_csv(ROOT / protocol["inputs"]["event_telemetry"]["relative_path"])
    telemetry = telemetry.loc[telemetry["used"].astype(bool)].copy()
    detectors = {int(item["sector"]): item for item in inventory["cbv_products"]}
    reductions = phase4["branches"]["pdcsap"]["per_sector_reduction"]
    rows = []
    for row in depths.itertuples(index=False):
        sector = int(row.sector)
        events = telemetry.loc[telemetry["sector"] == sector]
        reduction = reductions[str(sector)]
        rows.append({
            "sector": sector,
            "depth_ppm": float(row.depth_ppm),
            "formal_depth_error_ppm": float(row.depth_err_ppm),
            "camera": int(detectors[sector]["camera"]),
            "ccd": int(detectors[sector]["ccd"]),
            "optimal_aperture_pixel_count": int(reduction["alignment"]["optimal_pixel_count"]),
            "crowdsap": float(reduction["crowdsap"]),
            "flfrcsap_metadata_only": float(reduction["flfrcsap_metadata_only"]),
            "used_event_count": len(events),
            "sap_background_min_e_per_s": float(events["sap_bkg_min"].min()),
            "sap_background_max_e_per_s": float(events["sap_bkg_max"].max()),
            "background_excursion_event_count": int(events["flags"].fillna("").str.contains("BACKGROUND_8_MAD_EXCURSION").sum()),
        })
    descriptors = pd.DataFrame(rows).sort_values("sector").reset_index(drop=True)
    statistics = calculate(depths)
    expected = protocol["gate"]["expected"]
    checks = {
        "six_sectors_exact": len(depths) == 6 and set(depths["sector"]) == {37, 63, 64, 90, 99, 100},
        "chi_square_within_absolute_tolerance": abs(statistics["chi_square"] - expected["chi_square"]) <= protocol["gate"]["chi_square_absolute_tolerance"],
        "degrees_of_freedom_exact": statistics["degrees_of_freedom"] == expected["degrees_of_freedom"],
        "p_value_within_relative_tolerance": abs(statistics["p_value"] / expected["p_value"] - 1.0) <= protocol["gate"]["p_value_relative_tolerance"],
        "all_descriptors_complete": not descriptors.isna().any().any(),
    }
    result = {
        "work_package": "WP-09A",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "protocol": {"relative_path": "data/wp09a_formal_sector_protocol.json", "sha256": sha256_file(PROTOCOL)},
        "statistics": statistics,
        "gate_checks": checks,
        "interpretation": "Formal errors reject a constant-depth model. This does not identify an astrophysical cause; camera, CCD, aperture, crowding, background, reduction, and unmodeled covariance remain possible contributors.",
        "adoption": "FORMAL_HETEROGENEITY_ONLY",
    }
    return result, descriptors


def write_csv(path, frame):
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n", float_format="%.17g")
    temporary.replace(path)


def write_json(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    protocol = load_json(PROTOCOL)
    result, descriptors = build(protocol)
    if args.verify_only:
        stored_result = load_json(OUTPUT)
        stored_artifacts = stored_result.pop("artifacts")
        if stored_result != result:
            raise RuntimeError("WP-09A JSON is stale")
        stored = pd.read_csv(DESCRIPTORS)
        pd.testing.assert_frame_equal(stored, descriptors, check_dtype=False, rtol=1e-12)
        artifact = stored_artifacts["sector_descriptors"]
        if sha256_file(DESCRIPTORS) != artifact["sha256"] or len(stored) != artifact["row_count"]:
            raise RuntimeError("WP-09A descriptor artifact hash mismatch")
        print("Verified WP-09A: {}".format(result["status"]))
    else:
        if OUTPUT.exists() or DESCRIPTORS.exists():
            raise FileExistsError("WP-09A outputs are no-clobber")
        write_csv(DESCRIPTORS, descriptors)
        result["artifacts"] = {
            "sector_descriptors": {
                "relative_path": "outputs/wp09a_sector_descriptors.csv",
                "sha256": sha256_file(DESCRIPTORS),
                "row_count": len(descriptors),
            }
        }
        write_json(OUTPUT, result)
        print("Wrote WP-09A: {}".format(result["status"]))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
