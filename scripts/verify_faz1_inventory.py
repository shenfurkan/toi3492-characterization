"""Faz 1: verify active local SPOC FITS products and build cadence ledgers.

Only the 18 raw FITS paths declared by
``outputs/asteroseismic_input_inventory.json`` are opened.  The frozen
reference CSVs are read solely to identify which raw LC cadences survived the
historical default-quality and post-quality filtering; they are never changed.
"""

import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astropy.io import fits


ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = (ROOT / "data" / "asteroseismology" / "raw").resolve()
SOURCE_INVENTORY = ROOT / "outputs" / "asteroseismic_input_inventory.json"
OUTPUT_INVENTORY = ROOT / "outputs" / "faz1_product_inventory.json"

REFERENCE_PATHS = {
    120: ROOT / "data" / "toi3492_120s_reference.csv",
    20: ROOT / "data" / "toi3492_20s_reference.csv",
}
LEDGER_PATHS = {
    120: ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz",
    20: ROOT / "data" / "toi3492_cadence_ledger_20s.csv.gz",
}

EXPECTED_CADENCE_KEYS = {
    (37, 120),
    (63, 120),
    (64, 120),
    (90, 120),
    (99, 120),
    (100, 120),
    (90, 20),
    (99, 20),
    (100, 20),
}
EXPECTED_PRODUCT_KEYS = {
    (sector, cadence, product_type)
    for sector, cadence in EXPECTED_CADENCE_KEYS
    for product_type in ("lc", "tpf")
}

BJD_ZEROPOINT = 2457000.0
TIME_TOLERANCE_DAYS = 1e-8
TIMEDEL_TOLERANCE_DAYS = 1e-12
DEFAULT_QUALITY_BITMASK = 17087
HARD_QUALITY_BITMASK = 24319

LC_COLUMN_FORMATS = {
    "TIME": "D",
    "TIMECORR": "E",
    "CADENCENO": "J",
    "SAP_FLUX": "E",
    "SAP_FLUX_ERR": "E",
    "SAP_BKG": "E",
    "SAP_BKG_ERR": "E",
    "PDCSAP_FLUX": "E",
    "PDCSAP_FLUX_ERR": "E",
    "QUALITY": "J",
    "PSF_CENTR1": "D",
    "PSF_CENTR1_ERR": "E",
    "PSF_CENTR2": "D",
    "PSF_CENTR2_ERR": "E",
    "MOM_CENTR1": "D",
    "MOM_CENTR1_ERR": "E",
    "MOM_CENTR2": "D",
    "MOM_CENTR2_ERR": "E",
    "POS_CORR1": "E",
    "POS_CORR2": "E",
}
TPF_SCALAR_COLUMN_FORMATS = {
    "TIME": "D",
    "TIMECORR": "E",
    "CADENCENO": "J",
    "QUALITY": "J",
    "POS_CORR1": "E",
    "POS_CORR2": "E",
}
TPF_PIXEL_COLUMN_TYPES = {
    "RAW_CNTS": "J",
    "FLUX": "E",
    "FLUX_ERR": "E",
    "FLUX_BKG": "E",
    "FLUX_BKG_ERR": "E",
}

EXCLUSION_REASONS = (
    "invalid_time",
    "invalid_pdcsap_flux",
    "nonpositive_pdcsap_flux",
    "quality_default_reject",
    "post_quality_clip_or_filter",
    "included_reference",
)

LEDGER_COLUMNS = (
    "sector",
    "cadence_seconds",
    "product_id",
    "product_path",
    "product_sha256",
    "tpf_sha256",
    "time_btjd",
    "time_bjd_tdb",
    "timecorr",
    "cadenceno",
    "sap_flux",
    "sap_flux_err",
    "pdcsap_flux",
    "pdcsap_flux_err",
    "sap_bkg",
    "sap_bkg_err",
    "quality",
    "psf_centr1",
    "psf_centr1_err",
    "psf_centr2",
    "psf_centr2_err",
    "mom_centr1",
    "mom_centr1_err",
    "mom_centr2",
    "mom_centr2_err",
    "pos_corr1",
    "pos_corr2",
    "tic_id",
    "camera",
    "ccd",
    "data_release",
    "pipeline_version",
    "timesys",
    "bjdrefi",
    "bjdreff",
    "timedel_days",
    "num_frames",
    "int_time_seconds",
    "frame_time_seconds",
    "read_time_seconds",
    "dead_correction",
    "crowdsap",
    "flfrcsap",
    "aperture_sha256",
    "aperture_optimal_pixel_count",
    "quality_strict_zero_pass",
    "quality_default_17087_pass",
    "quality_hard_24319_pass",
    "in_current_reference",
    "reference_time_residual_days",
    "exclusion_reason",
)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def float_text(value):
    """Round-trip-safe text for FITS float64/float32 values, including NaNs."""
    value = float(value)
    if np.isnan(value):
        return "nan"
    if np.isposinf(value):
        return "inf"
    if np.isneginf(value):
        return "-inf"
    return format(value, ".17g")


def bool_text(value):
    return "true" if bool(value) else "false"


def json_number(value):
    if value is None:
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def aperture_digest(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def column_schema(hdu):
    schema = []
    for column in hdu.columns:
        data_shape = list(np.asarray(hdu.data[column.name]).shape[1:])
        schema.append(
            {
                "name": column.name,
                "format": str(column.format),
                "unit": column.unit,
                "dim": column.dim,
                "data_shape_per_row": data_shape,
            }
        )
    return schema


def verify_schema(product_type, table_hdu, aperture_shape):
    actual = {column.name: str(column.format) for column in table_hdu.columns}
    if product_type == "lc":
        required = LC_COLUMN_FORMATS
        format_mismatches = {
            name: {"expected": expected, "actual": actual.get(name)}
            for name, expected in required.items()
            if actual.get(name) != expected
        }
        pixel_shape_mismatches = {}
    else:
        required_names = set(TPF_SCALAR_COLUMN_FORMATS) | set(TPF_PIXEL_COLUMN_TYPES)
        format_mismatches = {
            name: {"expected": expected, "actual": actual.get(name)}
            for name, expected in TPF_SCALAR_COLUMN_FORMATS.items()
            if actual.get(name) != expected
        }
        pixel_shape_mismatches = {}
        pixel_count = int(np.prod(aperture_shape))
        for name, element_type in TPF_PIXEL_COLUMN_TYPES.items():
            expected_format = f"{pixel_count}{element_type}"
            if actual.get(name) != expected_format:
                format_mismatches[name] = {
                    "expected": expected_format,
                    "actual": actual.get(name),
                }
            if name in actual:
                shape = tuple(np.asarray(table_hdu.data[name]).shape[1:])
                if shape != tuple(aperture_shape):
                    pixel_shape_mismatches[name] = {
                        "expected": list(aperture_shape),
                        "actual": list(shape),
                    }
        required = {name: actual.get(name) for name in required_names}

    missing = sorted(name for name in required if name not in actual)
    return {
        "required_columns": sorted(required),
        "actual_columns": column_schema(table_hdu),
        "missing_columns": missing,
        "format_mismatches": format_mismatches,
        "pixel_shape_mismatches": pixel_shape_mismatches,
        "pass": not missing and not format_mismatches and not pixel_shape_mismatches,
    }


def inspect_product(declared):
    relative_path = Path(declared["relative_path"])
    if relative_path.is_absolute():
        raise ValueError(f"Absolute inventory path is not allowed: {relative_path}")
    path = (ROOT / relative_path).resolve()
    try:
        path.relative_to(RAW_ROOT)
    except ValueError as exc:
        raise ValueError(f"Product is outside active raw FITS root: {path}") from exc
    if path.suffix.lower() != ".fits" or any(part.lower().endswith(".zip") for part in path.parts):
        raise ValueError(f"Only active unarchived FITS are allowed: {path}")
    if not path.is_file():
        raise FileNotFoundError(path)

    actual_size = path.stat().st_size
    actual_sha256 = sha256_file(path)
    product_type = declared["product_type"]
    sector = int(declared["sector"])
    cadence = int(declared["cadence_seconds"])
    expected_hdu_name = "LIGHTCURVE" if product_type == "lc" else "PIXELS"

    with fits.open(path, mode="readonly", memmap=True) as hdul:
        if len(hdul) < 3:
            raise ValueError(f"{relative_path}: expected table and aperture HDUs")
        primary = hdul[0].header
        table = hdul[1]
        table_header = table.header
        aperture_hdu = hdul[2]
        aperture = np.asarray(aperture_hdu.data)
        times = np.asarray(table.data["TIME"], dtype=np.float64)
        finite_time = np.isfinite(times)
        bjdrefi = float(table_header["BJDREFI"])
        bjdreff = float(table_header["BJDREFF"])
        bjd_reference = bjdrefi + bjdreff
        bjd = times[finite_time] + bjd_reference
        round_trip = bjd - bjd_reference
        residual = np.abs(round_trip - times[finite_time])
        max_round_trip = float(np.max(residual)) if residual.size else None

        exposure_keys = (
            "EXPOSURE",
            "TELAPSE",
            "LIVETIME",
            "TIMEDEL",
            "NUM_FRM",
            "INT_TIME",
            "FRAMETIM",
            "READTIME",
            "DEADC",
            "TIMEPIXR",
        )
        exposure = {key.lower(): json_number(table_header.get(key)) for key in exposure_keys}
        exposure["cadence_from_timedel_seconds"] = float(table_header["TIMEDEL"] * 86400.0)
        exposure["frame_cycle_seconds"] = float(
            table_header["NUM_FRM"] * table_header["FRAMETIM"]
        )
        exposure["integration_plus_read_seconds"] = float(
            table_header["INT_TIME"] + table_header["READTIME"]
        )
        exposure["livetime_minus_telapse_times_deadc_days"] = float(
            table_header["LIVETIME"]
            - table_header["TELAPSE"] * table_header["DEADC"]
        )

        aperture_sha256 = aperture_digest(aperture)
        optimal_count = int(np.count_nonzero(np.bitwise_and(aperture, 2)))
        aperture_header_count = int(aperture_hdu.header["NPIXSAP"])
        expected_metadata = declared["fits"]
        metadata = {
            "tic_id": int(primary["TICID"]),
            "sector": int(primary["SECTOR"]),
            "camera": int(primary["CAMERA"]),
            "ccd": int(primary["CCD"]),
            "data_release": int(primary["DATA_REL"]),
            "pipeline_version": str(primary["PROCVER"]),
            "timesys": str(table_header["TIMESYS"]),
            "timeunit": str(table_header["TIMEUNIT"]),
            "bjdrefi": bjdrefi,
            "bjdreff": bjdreff,
            "tstart_btjd": float(table_header["TSTART"]),
            "tstop_btjd": float(table_header["TSTOP"]),
            "date_obs": str(table_header["DATE-OBS"]),
            "date_end": str(table_header["DATE-END"]),
            "crowdsap": float(table_header["CROWDSAP"]),
            "flfrcsap": float(table_header["FLFRCSAP"]),
        }
        inventory_metadata_match = (
            metadata["sector"] == int(expected_metadata["sector"])
            and metadata["camera"] == int(expected_metadata["camera"])
            and metadata["ccd"] == int(expected_metadata["ccd"])
            and metadata["data_release"] == int(expected_metadata["data_rel"])
            and metadata["pipeline_version"] == expected_metadata["procver"]
            and metadata["timesys"] == expected_metadata["timesys"]
            and abs(metadata["bjdrefi"] - float(expected_metadata["bjdrefi"])) < 1e-12
            and abs(metadata["bjdreff"] - float(expected_metadata["bjdreff"])) < 1e-12
            and abs(metadata["crowdsap"] - float(expected_metadata["crowdsap"])) < 1e-12
            and abs(metadata["flfrcsap"] - float(expected_metadata["flfrcsap"])) < 1e-12
            and abs(exposure["timedel"] - float(expected_metadata["timedel_days"])) < 1e-15
            and len(table.data) == int(expected_metadata["naxis2"])
        )
        exposure_pass = (
            all(exposure[key] is not None for key in [key.lower() for key in exposure_keys])
            and exposure["exposure"] > 0.0
            and exposure["telapse"] > 0.0
            and exposure["livetime"] > 0.0
            and abs(exposure["cadence_from_timedel_seconds"] - cadence) < 1e-9
            and abs(exposure["frame_cycle_seconds"] - cadence) < 1e-9
            and abs(exposure["integration_plus_read_seconds"] - exposure["frametim"]) < 1e-12
            and 0.0 < exposure["deadc"] <= 1.0
            and abs(exposure["livetime_minus_telapse_times_deadc_days"]) < 1e-10
        )
        schema = verify_schema(product_type, table, aperture.shape)
        hdu_names = [hdu.name for hdu in hdul]
        hdu_pass = (
            hdu_names[0] == "PRIMARY"
            and hdu_names[1] == expected_hdu_name
            and hdu_names[2] == "APERTURE"
        )
        time_pass = (
            metadata["timesys"] == "TDB"
            and metadata["timeunit"] == "d"
            and abs(bjd_reference - BJD_ZEROPOINT) < TIME_TOLERANCE_DAYS
            and max_round_trip is not None
            and max_round_trip < TIME_TOLERANCE_DAYS
            and abs(exposure["timedel"] - cadence / 86400.0) < TIMEDEL_TOLERANCE_DAYS
        )
        aperture_pass = (
            aperture.ndim == 2
            and aperture.size > 0
            and optimal_count > 0
            and optimal_count == aperture_header_count
        )

        result = {
            "product_key": f"S{sector:03d}-{cadence}s-{product_type}",
            "product_type": product_type,
            "sector": sector,
            "cadence_seconds": cadence,
            "product_id": declared["filename"],
            "relative_path": relative_path.as_posix(),
            "declared_size_bytes": int(declared["size_bytes"]),
            "actual_size_bytes": int(actual_size),
            "size_match": actual_size == int(declared["size_bytes"]),
            "declared_sha256": declared["sha256"],
            "actual_sha256": actual_sha256,
            "sha256_match": actual_sha256 == declared["sha256"],
            "hdu_names": hdu_names,
            "hdu_names_pass": hdu_pass,
            "table_hdu_index": 1,
            "aperture_hdu_index": 2,
            "row_count": int(len(table.data)),
            "schema": schema,
            "time": {
                "row_count": int(times.size),
                "finite_count": int(finite_time.sum()),
                "nan_count": int(np.isnan(times).sum()),
                "nonfinite_count": int((~finite_time).sum()),
                "minimum_btjd": float(np.min(times[finite_time])) if finite_time.any() else None,
                "maximum_btjd": float(np.max(times[finite_time])) if finite_time.any() else None,
                "bjd_reference": bjd_reference,
                "conversion": "BJD_TDB = TIME_BTJD + BJDREFI + BJDREFF",
                "max_btjd_bjd_tdb_btjd_residual_days": max_round_trip,
                "tolerance_days": TIME_TOLERANCE_DAYS,
                "pass": time_pass,
            },
            "metadata": metadata,
            "inventory_metadata_match": inventory_metadata_match,
            "exposure_metadata": exposure,
            "exposure_metadata_pass": exposure_pass,
            "aperture": {
                "shape": list(aperture.shape),
                "dtype": str(aperture.dtype),
                "sha256": aperture_sha256,
                "optimal_pixel_bit": 2,
                "optimal_pixel_count": optimal_count,
                "npixsap_header": aperture_header_count,
                "unique_bitmask_values": sorted(int(value) for value in np.unique(aperture)),
                "pass": aperture_pass,
            },
        }
        result["pass"] = all(
            (
                result["size_match"],
                result["sha256_match"],
                hdu_pass,
                schema["pass"],
                time_pass,
                inventory_metadata_match,
                exposure_pass,
                aperture_pass,
            )
        )
    return result


def compare_float_arrays(left, right):
    left = np.asarray(left)
    right = np.asarray(right)
    if left.shape != right.shape:
        return {
            "same_shape": False,
            "exact_with_matching_nans": False,
            "mismatch_count": None,
            "nan_pattern_mismatch_count": None,
            "max_absolute_residual": None,
        }
    left_nan = np.isnan(left)
    right_nan = np.isnan(right)
    nan_mismatch = int(np.count_nonzero(left_nan != right_nan))
    finite = np.isfinite(left) & np.isfinite(right)
    differences = np.abs(left[finite].astype(np.float64) - right[finite].astype(np.float64))
    max_residual = float(np.max(differences)) if differences.size else 0.0
    equal = (left == right) | (left_nan & right_nan)
    return {
        "same_shape": True,
        "exact_with_matching_nans": bool(np.all(equal)),
        "mismatch_count": int(np.count_nonzero(~equal)),
        "nan_pattern_mismatch_count": nan_mismatch,
        "max_absolute_residual": max_residual,
    }


def verify_pair(key, lc_declared, tpf_declared, product_results):
    sector, cadence = key
    lc_path = ROOT / lc_declared["relative_path"]
    tpf_path = ROOT / tpf_declared["relative_path"]
    with fits.open(lc_path, mode="readonly", memmap=True) as lc_hdul, fits.open(
        tpf_path, mode="readonly", memmap=True
    ) as tpf_hdul:
        lc_data = lc_hdul[1].data
        tpf_data = tpf_hdul[1].data
        comparisons = {
            "time": compare_float_arrays(lc_data["TIME"], tpf_data["TIME"]),
            "timecorr": compare_float_arrays(lc_data["TIMECORR"], tpf_data["TIMECORR"]),
            "pos_corr1": compare_float_arrays(lc_data["POS_CORR1"], tpf_data["POS_CORR1"]),
            "pos_corr2": compare_float_arrays(lc_data["POS_CORR2"], tpf_data["POS_CORR2"]),
        }
        cadence_equal = bool(np.array_equal(lc_data["CADENCENO"], tpf_data["CADENCENO"]))
        quality_equal = bool(np.array_equal(lc_data["QUALITY"], tpf_data["QUALITY"]))
        aperture_equal = bool(np.array_equal(lc_hdul[2].data, tpf_hdul[2].data))

    lc_result = product_results[(sector, cadence, "lc")]
    tpf_result = product_results[(sector, cadence, "tpf")]
    metadata_fields = (
        "tic_id",
        "sector",
        "camera",
        "ccd",
        "data_release",
        "pipeline_version",
        "timesys",
        "timeunit",
        "bjdrefi",
        "bjdreff",
        "crowdsap",
        "flfrcsap",
    )
    metadata_match = {
        field: lc_result["metadata"][field] == tpf_result["metadata"][field]
        for field in metadata_fields
    }
    pass_value = (
        lc_result["row_count"] == tpf_result["row_count"]
        and all(item["exact_with_matching_nans"] for item in comparisons.values())
        and cadence_equal
        and quality_equal
        and aperture_equal
        and lc_result["aperture"]["sha256"] == tpf_result["aperture"]["sha256"]
        and lc_result["aperture"]["optimal_pixel_count"]
        == tpf_result["aperture"]["optimal_pixel_count"]
        and all(metadata_match.values())
    )
    return {
        "pair_key": f"S{sector:03d}-{cadence}s",
        "sector": sector,
        "cadence_seconds": cadence,
        "lc_product_id": lc_declared["filename"],
        "tpf_product_id": tpf_declared["filename"],
        "lc_row_count": lc_result["row_count"],
        "tpf_row_count": tpf_result["row_count"],
        "array_comparisons": comparisons,
        "cadenceno_exact_match": cadence_equal,
        "quality_exact_match": quality_equal,
        "aperture_exact_match": aperture_equal,
        "aperture_sha256": lc_result["aperture"]["sha256"],
        "optimal_pixel_count": lc_result["aperture"]["optimal_pixel_count"],
        "metadata_field_matches": metadata_match,
        "pass": pass_value,
    }


def load_reference_times():
    reference = {}
    provenance = {}
    for cadence, path in REFERENCE_PATHS.items():
        grouped = {}
        row_count = 0
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"time", "sector", "exptime"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError(f"Reference schema is incomplete: {path}")
            for row in reader:
                sector = int(row["sector"])
                exptime = float(row["exptime"])
                if abs(exptime - cadence) >= 1e-9:
                    raise ValueError(f"Unexpected exptime in {path}: {exptime}")
                grouped.setdefault(sector, []).append(float(row["time"]))
                row_count += 1
        for sector, values in grouped.items():
            times = np.sort(np.asarray(values, dtype=np.float64))
            if not np.isfinite(times).all() or np.any(np.diff(times) <= 0.0):
                raise ValueError(f"Reference times are not finite and unique: {path}, S{sector}")
            reference[(sector, cadence)] = times
        provenance[cadence] = {
            "relative_path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "row_count": row_count,
            "sectors": sorted(grouped),
            "read_only": True,
        }
    return reference, provenance


def nearest_reference_matches(raw_times, reference_times):
    raw_times = np.asarray(raw_times, dtype=np.float64)
    reference_times = np.asarray(reference_times, dtype=np.float64)
    distances = np.full(raw_times.shape, np.inf, dtype=np.float64)
    finite_indices = np.flatnonzero(np.isfinite(raw_times))
    finite_times = raw_times[finite_indices]
    if reference_times.size and finite_times.size:
        positions = np.searchsorted(reference_times, finite_times)
        right = positions < reference_times.size
        distances[finite_indices[right]] = np.abs(
            finite_times[right] - reference_times[positions[right]]
        )
        left = positions > 0
        left_distance = np.abs(finite_times[left] - reference_times[positions[left] - 1])
        target_indices = finite_indices[left]
        distances[target_indices] = np.minimum(distances[target_indices], left_distance)

    matches = distances < TIME_TOLERANCE_DAYS
    if reference_times.size:
        sorted_raw = np.sort(finite_times)
        positions = np.searchsorted(sorted_raw, reference_times)
        ref_distances = np.full(reference_times.shape, np.inf, dtype=np.float64)
        right = positions < sorted_raw.size
        ref_distances[right] = np.abs(reference_times[right] - sorted_raw[positions[right]])
        left = positions > 0
        ref_distances[left] = np.minimum(
            ref_distances[left],
            np.abs(reference_times[left] - sorted_raw[positions[left] - 1]),
        )
    else:
        ref_distances = np.asarray([], dtype=np.float64)
    return matches, distances, ref_distances


def classify_reasons(times, pdcsap_flux, quality, reference_match):
    times = np.asarray(times, dtype=np.float64)
    pdcsap_flux = np.asarray(pdcsap_flux, dtype=np.float64)
    quality = np.asarray(quality, dtype=np.int64)
    reasons = np.full(times.shape, "post_quality_clip_or_filter", dtype=object)
    remaining = np.ones(times.shape, dtype=bool)

    invalid_time = ~np.isfinite(times)
    reasons[invalid_time] = "invalid_time"
    remaining &= ~invalid_time

    invalid_flux = remaining & ~np.isfinite(pdcsap_flux)
    reasons[invalid_flux] = "invalid_pdcsap_flux"
    remaining &= ~invalid_flux

    nonpositive = remaining & (pdcsap_flux <= 0.0)
    reasons[nonpositive] = "nonpositive_pdcsap_flux"
    remaining &= ~nonpositive

    default_reject = remaining & ((quality & DEFAULT_QUALITY_BITMASK) != 0)
    reasons[default_reject] = "quality_default_reject"
    remaining &= ~default_reject

    included = remaining & reference_match
    reasons[included] = "included_reference"

    if not set(np.unique(reasons)).issubset(EXCLUSION_REASONS):
        raise RuntimeError("An unknown cadence exclusion reason was generated")
    return reasons


def write_ledgers(declared_by_key, product_results, reference_times):
    summaries = []
    ledger_results = {}
    for cadence, output_path in LEDGER_PATHS.items():
        cadence_products = sorted(
            (
                item
                for key, item in declared_by_key.items()
                if key[1] == cadence and key[2] == "lc"
            ),
            key=lambda item: item["sector"],
        )
        with gzip.open(
            output_path,
            mode="wt",
            encoding="utf-8",
            newline="",
            compresslevel=9,
        ) as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(LEDGER_COLUMNS)
            for declared in cadence_products:
                sector = int(declared["sector"])
                key = (sector, cadence, "lc")
                result = product_results[key]
                tpf_result = product_results[(sector, cadence, "tpf")]
                path = ROOT / declared["relative_path"]
                with fits.open(path, mode="readonly", memmap=True) as hdul:
                    data = hdul[1].data
                    times = np.asarray(data["TIME"], dtype=np.float64)
                    flux = np.asarray(data["PDCSAP_FLUX"], dtype=np.float64)
                    quality = np.asarray(data["QUALITY"], dtype=np.int64)
                    refs = reference_times.get((sector, cadence), np.asarray([], dtype=float))
                    matches, distances, ref_distances = nearest_reference_matches(times, refs)
                    reasons = classify_reasons(times, flux, quality, matches)

                    if ref_distances.size and not np.all(ref_distances < TIME_TOLERANCE_DAYS):
                        raise ValueError(f"Reference cadence is absent from raw LC: S{sector} {cadence}s")
                    if int(matches.sum()) != int(refs.size):
                        raise ValueError(
                            f"Reference/raw cadence mapping is not one-to-one: S{sector} {cadence}s"
                        )
                    valid_for_reference = (
                        np.isfinite(times)
                        & np.isfinite(flux)
                        & (flux > 0.0)
                        & ((quality & DEFAULT_QUALITY_BITMASK) == 0)
                    )
                    if np.any(matches & ~valid_for_reference):
                        raise ValueError(f"Reference contains a pre-filter-rejected row: S{sector}")

                    metadata = result["metadata"]
                    exposure = result["exposure_metadata"]
                    aperture = result["aperture"]
                    bjd_reference = metadata["bjdrefi"] + metadata["bjdreff"]
                    arrays = {name: data[name.upper()] for name in (
                        "timecorr",
                        "cadenceno",
                        "sap_flux",
                        "sap_flux_err",
                        "pdcsap_flux",
                        "pdcsap_flux_err",
                        "sap_bkg",
                        "sap_bkg_err",
                        "quality",
                        "psf_centr1",
                        "psf_centr1_err",
                        "psf_centr2",
                        "psf_centr2_err",
                        "mom_centr1",
                        "mom_centr1_err",
                        "mom_centr2",
                        "mom_centr2_err",
                        "pos_corr1",
                        "pos_corr2",
                    )}
                    for index in range(len(data)):
                        time_value = float(times[index])
                        time_bjd = time_value + bjd_reference if np.isfinite(time_value) else np.nan
                        qvalue = int(quality[index])
                        reference_residual = distances[index] if matches[index] else np.nan
                        writer.writerow(
                            (
                                sector,
                                cadence,
                                declared["filename"],
                                Path(declared["relative_path"]).as_posix(),
                                result["actual_sha256"],
                                tpf_result["actual_sha256"],
                                float_text(time_value),
                                float_text(time_bjd),
                                float_text(arrays["timecorr"][index]),
                                int(arrays["cadenceno"][index]),
                                float_text(arrays["sap_flux"][index]),
                                float_text(arrays["sap_flux_err"][index]),
                                float_text(arrays["pdcsap_flux"][index]),
                                float_text(arrays["pdcsap_flux_err"][index]),
                                float_text(arrays["sap_bkg"][index]),
                                float_text(arrays["sap_bkg_err"][index]),
                                qvalue,
                                float_text(arrays["psf_centr1"][index]),
                                float_text(arrays["psf_centr1_err"][index]),
                                float_text(arrays["psf_centr2"][index]),
                                float_text(arrays["psf_centr2_err"][index]),
                                float_text(arrays["mom_centr1"][index]),
                                float_text(arrays["mom_centr1_err"][index]),
                                float_text(arrays["mom_centr2"][index]),
                                float_text(arrays["mom_centr2_err"][index]),
                                float_text(arrays["pos_corr1"][index]),
                                float_text(arrays["pos_corr2"][index]),
                                metadata["tic_id"],
                                metadata["camera"],
                                metadata["ccd"],
                                metadata["data_release"],
                                metadata["pipeline_version"],
                                metadata["timesys"],
                                float_text(metadata["bjdrefi"]),
                                float_text(metadata["bjdreff"]),
                                float_text(exposure["timedel"]),
                                int(exposure["num_frm"]),
                                float_text(exposure["int_time"]),
                                float_text(exposure["frametim"]),
                                float_text(exposure["readtime"]),
                                float_text(exposure["deadc"]),
                                float_text(metadata["crowdsap"]),
                                float_text(metadata["flfrcsap"]),
                                aperture["sha256"],
                                aperture["optimal_pixel_count"],
                                bool_text(qvalue == 0),
                                bool_text((qvalue & DEFAULT_QUALITY_BITMASK) == 0),
                                bool_text((qvalue & HARD_QUALITY_BITMASK) == 0),
                                bool_text(matches[index]),
                                float_text(reference_residual),
                                reasons[index],
                            )
                        )

                counts = Counter(str(reason) for reason in reasons)
                summary = {
                    "sector": sector,
                    "cadence_seconds": cadence,
                    "raw_row_count": int(len(reasons)),
                    "reference_row_count": int(refs.size),
                    "reference_matched_row_count": int(matches.sum()),
                    "reference_unmatched_row_count": int(
                        np.count_nonzero(ref_distances >= TIME_TOLERANCE_DAYS)
                    ),
                    "max_reference_time_residual_days": (
                        float(np.max(distances[matches])) if matches.any() else None
                    ),
                    "reason_counts": {
                        reason: int(counts.get(reason, 0)) for reason in EXCLUSION_REASONS
                    },
                    "reason_count_sum": int(sum(counts.values())),
                    "pass": (
                        int(sum(counts.values())) == len(reasons)
                        and int(matches.sum()) == int(refs.size)
                        and int(counts.get("included_reference", 0)) == int(refs.size)
                    ),
                }
                summaries.append(summary)

        cadence_summaries = [item for item in summaries if item["cadence_seconds"] == cadence]
        ledger_results[cadence] = {
            "cadence_seconds": cadence,
            "relative_path": output_path.relative_to(ROOT).as_posix(),
            "compression": "gzip",
            "float_encoding": ".17g round-trip text; non-finite values encoded as nan/inf",
            "size_bytes": output_path.stat().st_size,
            "sha256": sha256_file(output_path),
            "row_count": int(sum(item["raw_row_count"] for item in cadence_summaries)),
            "reference_row_count": int(
                sum(item["reference_row_count"] for item in cadence_summaries)
            ),
            "columns": list(LEDGER_COLUMNS),
            "pass": all(item["pass"] for item in cadence_summaries),
        }
    return summaries, ledger_results


def build_inventory():
    with SOURCE_INVENTORY.open("r", encoding="utf-8") as handle:
        source = json.load(handle)
    declared_products = source["products"]
    declared_by_key = {}
    for product in declared_products:
        key = (
            int(product["sector"]),
            int(product["cadence_seconds"]),
            product["product_type"],
        )
        if key in declared_by_key:
            raise ValueError(f"Duplicate product key in source inventory: {key}")
        declared_by_key[key] = product

    product_results = {}
    for key in sorted(declared_by_key, key=lambda item: (item[0], item[1], item[2])):
        product_results[key] = inspect_product(declared_by_key[key])

    pairs = []
    for key in sorted(EXPECTED_CADENCE_KEYS):
        pairs.append(
            verify_pair(
                key,
                declared_by_key[(key[0], key[1], "lc")],
                declared_by_key[(key[0], key[1], "tpf")],
                product_results,
            )
        )

    reference_times, reference_provenance = load_reference_times()
    summaries, ledgers = write_ledgers(declared_by_key, product_results, reference_times)
    products = [product_results[key] for key in sorted(product_results)]
    max_time_residual = max(
        product["time"]["max_btjd_bjd_tdb_btjd_residual_days"] for product in products
    )
    checks = {
        "exactly_18_products": len(products) == 18,
        "exactly_9_lc": sum(item["product_type"] == "lc" for item in products) == 9,
        "exactly_9_tpf": sum(item["product_type"] == "tpf" for item in products) == 9,
        "unique_expected_product_keys": set(declared_by_key) == EXPECTED_PRODUCT_KEYS,
        "all_sizes_and_hashes_match": all(
            item["size_match"] and item["sha256_match"] for item in products
        ),
        "all_required_hdu_schemas_pass": all(
            item["hdu_names_pass"] and item["schema"]["pass"] for item in products
        ),
        "all_time_conversions_pass": all(item["time"]["pass"] for item in products),
        "all_exposure_metadata_pass": all(item["exposure_metadata_pass"] for item in products),
        "all_pipeline_metadata_match": all(
            item["inventory_metadata_match"] for item in products
        ),
        "all_apertures_pass": all(item["aperture"]["pass"] for item in products),
        "exactly_9_lc_tpf_pairs": len(pairs) == 9,
        "all_lc_tpf_pairs_match": all(pair["pass"] for pair in pairs),
        "all_reference_rows_reconciled": all(item["pass"] for item in summaries),
        "both_cadence_ledgers_pass": set(ledgers) == {20, 120}
        and all(item["pass"] for item in ledgers.values()),
        "max_time_residual_below_1e_8_days": max_time_residual < TIME_TOLERANCE_DAYS,
    }
    gate_pass = all(checks.values())
    return {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "target": source["target"],
        "tic_id": int(source["tic_id"]),
        "input_policy": {
            "fits_source": SOURCE_INVENTORY.relative_to(ROOT).as_posix(),
            "allowed_raw_root": RAW_ROOT.relative_to(ROOT).as_posix(),
            "legacy_zip_inspected": False,
            "network_used": False,
            "reference_csvs_read_only": True,
        },
        "quality_masks": {
            "strict_zero": 0,
            "lightkurve_default": DEFAULT_QUALITY_BITMASK,
            "explicit_hard": HARD_QUALITY_BITMASK,
            "pass_rule": "QUALITY & bitmask == 0; strict-zero pass is QUALITY == 0",
        },
        "counts": {
            "products": len(products),
            "lc_products": sum(item["product_type"] == "lc" for item in products),
            "tpf_products": sum(item["product_type"] == "tpf" for item in products),
            "paired_sector_cadence_keys": len(pairs),
        },
        "max_btjd_bjd_tdb_btjd_residual_days": max_time_residual,
        "time_residual_tolerance_days": TIME_TOLERANCE_DAYS,
        "products": products,
        "pairs": pairs,
        "reference_csvs": {str(key): value for key, value in reference_provenance.items()},
        "cadence_ledger_summary": summaries,
        "cadence_ledgers": {str(key): value for key, value in ledgers.items()},
        "gate": {
            "checks": checks,
            "gate_pass": gate_pass,
        },
        "gate_pass": gate_pass,
    }


def main():
    result = build_inventory()
    with OUTPUT_INVENTORY.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")

    print("FAZ 1: active local SPOC FITS inventory")
    print(
        f"Products: {result['counts']['products']} "
        f"({result['counts']['lc_products']} LC + {result['counts']['tpf_products']} TPF)"
    )
    print(
        "Max BTJD->BJD_TDB->BTJD residual: "
        f"{result['max_btjd_bjd_tdb_btjd_residual_days']:.3e} d"
    )
    for item in result["cadence_ledger_summary"]:
        reason_text = ", ".join(
            f"{reason}={count}" for reason, count in item["reason_counts"].items()
        )
        print(
            f"S{item['sector']} {item['cadence_seconds']}s: "
            f"rows={item['raw_row_count']}, reference={item['reference_row_count']}; "
            f"{reason_text}"
        )
    print(f"FAZ 1 GATE: {'PASS' if result['gate_pass'] else 'FAIL'}")
    print(f"Output: {OUTPUT_INVENTORY.relative_to(ROOT).as_posix()}")
    if not result["gate_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
