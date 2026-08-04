"""Phase 4 independent-reduction comparison for the six 120-s TESS sectors.

The script consumes only the active local products frozen by Phases 1--3.  It
does not search for products, use the network, or inspect historical archives.
Reduction tuning is based on out-of-transit predictive performance; transit
depth is used only after each reduction has been fixed.
"""

import gzip
import hashlib
import io
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import batman
import numpy as np
import pandas as pd
from astropy.io import fits
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parent.parent
FAZ1_PATH = ROOT / "outputs" / "faz1_product_inventory.json"
FAZ2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
FAZ3_PATH = ROOT / "outputs" / "faz3_quality_audit.json"
FAZ3_INPUT_PATH = ROOT / "outputs" / "faz3_input_inventory.json"
OFFICIAL_PATH = ROOT / "data" / "official_toi_metadata.json"
LEDGER_PATH = ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz"
LONG_TABLE_PATH = ROOT / "data" / "toi3492_faz4_reductions_120s.csv.gz"
SECTOR_DEPTH_PATH = ROOT / "outputs" / "faz4_sector_depths.csv"
OUTPUT_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"

SECTORS = (37, 63, 64, 90, 99, 100)
BRANCHES = ("pdcsap", "sap_cbv", "tpf_pipeline", "tpf_pld")
QUALITY_MASK = 17087
PERIOD_DAYS = 9.2224171
T0_BTJD = 2314.5211550001986
T14_HOURS = 5.296858
T14_DAYS = T14_HOURS / 24.0
HALF_MODEL_WINDOW_DAYS = 13.0 / 24.0
EXPOSURE_SECONDS = 120.0
SUPERSAMPLE_FACTOR = 7
LD_U1 = 0.3546454910932521
LD_U2 = 0.15379449038160178
MAX_GEOMETRY_SHIFT_SIGMA = 0.5

# Frozen Phase-4 screening thresholds.  These are deliberately less extensive
# than the later Phase-15 end-to-end campaign.
INJECTIONS_PER_SECTOR = 4
MIN_INJECTIONS_PER_BRANCH = 24
MIN_INJECTION_RECOVERY_RATE = 0.90
MAX_MEDIAN_ABS_INJECTION_BIAS = 0.05
MAX_RECOVERED_TRIAL_ABS_BIAS = 0.20
MIN_SECTOR_SIGNAL_SIGMA = 3.0
INJECTION_EXCLUSION_HALF_WIDTH_DAYS = 0.75 * T14_DAYS
INJECTION_CONFIGS = (
    (0.0450, 0.55),
    (0.0525, 0.70),
    (0.0600, 0.80),
    (0.0675, 0.65),
)

PLD_DIMENSION_GRID = (2, 4, 8, 12)
PLD_RIDGE_GRID = (0.0, 1.0, 100.0, 10000.0)
GEOMETRY_STARTS = (
    (0.05466, 10.44, 0.715),
    (0.05200, 8.50, 0.450),
    (0.05800, 12.00, 0.840),
    (0.04700, 7.00, 0.200),
    (0.06100, 14.00, 0.910),
)


@dataclass
class SectorData:
    sector: int
    time: np.ndarray
    cadenceno: np.ndarray
    quality: np.ndarray
    pdcsap: np.ndarray
    pdcsap_err: np.ndarray
    sap: np.ndarray
    sap_err: np.ndarray
    pixels: np.ndarray
    pixel_err: np.ndarray
    cbv: np.ndarray
    cbv_gap: np.ndarray
    crowdsap: float
    flfrcsap: float
    aperture_sha256: str
    aperture_pixel_count: int
    lc_product: dict
    tpf_product: dict
    cbv_product: dict
    alignment: dict


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha256(values):
    array = np.ascontiguousarray(values, dtype="<f8")
    return hashlib.sha256(array.tobytes()).hexdigest()


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return value


def phase_days(time):
    time = np.asarray(time, dtype=float)
    return ((time - T0_BTJD + 0.5 * PERIOD_DAYS) % PERIOD_DAYS) - 0.5 * PERIOD_DAYS


def quality_pass(quality):
    return (np.asarray(quality, dtype=np.int64) & QUALITY_MASK) == 0


def robust_scale(values):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return None
    median = np.median(values)
    scale = 1.4826 * np.median(np.abs(values - median))
    if not np.isfinite(scale) or scale <= 0:
        scale = np.std(values, ddof=1)
    return float(scale) if np.isfinite(scale) and scale > 0 else None


def same_array(left, right):
    return np.array_equal(np.asarray(left), np.asarray(right), equal_nan=True)


def used_events(faz2):
    events = [
        {
            "physical_event_id": item["physical_event_id"],
            "sector": int(item["sector"]),
            "epoch": int(item["epoch"]),
            "midpoint_btjd": float(item["predicted_midpoint_btjd"]),
        }
        for item in faz2["events"]
        if item["used"]
    ]
    gaps = [
        (int(item["sector"]), int(item["epoch"]))
        for item in faz2["events"]
        if not item["used"]
    ]
    if len(events) != 16 or sorted(gaps) != [(37, 2), (99, 189)]:
        raise RuntimeError("Phase 2 does not contain the frozen 16-used/two-gap event set")
    return events, gaps


def validate_inputs(faz1, faz2, faz3, faz3_input, official):
    selected_cbv = {
        int(sector): int(item["selected_n_cbv"])
        for sector, item in faz3["cbv_selection"]["by_sector"].items()
    }
    checks = {
        "phase1_gate_pass": faz1.get("gate_pass") is True,
        "phase2_gate_pass": faz2.get("gate_pass") is True,
        "phase3_gate_pass": faz3.get("gate_status") == "PASS",
        "phase3_input_gate_pass": faz3_input.get("gate_pass") is True,
        "all_prior_inputs_exclude_legacy_zip": all(
            payload.get("input_policy", {}).get("legacy_zip_inspected") is False
            for payload in (faz1, faz2, faz3, faz3_input)
        ),
        "ledger_hash_matches_phase2": sha256_file(LEDGER_PATH)
        == faz2["provenance"]["cadence_ledgers"]["120"]["sha256"],
        "official_period_exact": float(official["ephemeris"]["period_days"])
        == PERIOD_DAYS,
        "official_t0_exact": float(official["ephemeris"]["transit_midpoint_bjd"])
        - 2457000.0
        == T0_BTJD,
        "phase3_quality_mask_exact": int(
            faz3["quality_masks"]["definitions"]["lightkurve_default"][
                "numeric_bitmask"
            ]
        )
        == QUALITY_MASK,
        "phase3_selected_cbv_counts_present": selected_cbv
        == {37: 7, 63: 8, 64: 7, 90: 7, 99: 7, 100: 3},
    }
    if not all(checks.values()):
        raise RuntimeError(f"Phase 4 input validation failed: {checks}")
    return checks, selected_cbv


def load_sector_data(faz1, faz3_input, ledger, selected_cbv):
    products = {
        (int(item["sector"]), item["product_type"]): item
        for item in faz1["products"]
        if int(item["cadence_seconds"]) == 120 and int(item["sector"]) in SECTORS
    }
    cbv_products = {
        int(item["sector"]): item for item in faz3_input["cbv_products"]
    }
    sectors = {}
    for sector in SECTORS:
        lc_item = products[(sector, "lc")]
        tpf_item = products[(sector, "tpf")]
        cbv_item = cbv_products[sector]
        lc_path = ROOT / lc_item["relative_path"]
        tpf_path = ROOT / tpf_item["relative_path"]
        cbv_path = ROOT / cbv_item["relative_path"]
        hashes = {
            "lc": sha256_file(lc_path),
            "tpf": sha256_file(tpf_path),
            "cbv": sha256_file(cbv_path),
        }
        if hashes["lc"] != lc_item["actual_sha256"]:
            raise RuntimeError(f"S{sector} LC hash changed after Phase 1")
        if hashes["tpf"] != tpf_item["actual_sha256"]:
            raise RuntimeError(f"S{sector} TPF hash changed after Phase 1")
        if hashes["cbv"] != cbv_item["sha256"]:
            raise RuntimeError(f"S{sector} CBV hash changed after Phase 3")

        with fits.open(lc_path, mode="readonly", memmap=True) as hdul:
            table_hdu = hdul[int(lc_item["table_hdu_index"])]
            table = table_hdu.data
            lc_aperture = np.asarray(
                hdul[int(lc_item["aperture_hdu_index"])].data
            ).copy()
            time = np.asarray(table["TIME"], dtype=float).copy()
            cadenceno = np.asarray(table["CADENCENO"], dtype=np.int64).copy()
            quality = np.asarray(table["QUALITY"], dtype=np.int64).copy()
            pdcsap = np.asarray(table["PDCSAP_FLUX"], dtype=float).copy()
            pdcsap_err = np.asarray(table["PDCSAP_FLUX_ERR"], dtype=float).copy()
            sap = np.asarray(table["SAP_FLUX"], dtype=float).copy()
            sap_err = np.asarray(table["SAP_FLUX_ERR"], dtype=float).copy()
            lc_pos1 = np.asarray(table["POS_CORR1"], dtype=float).copy()
            lc_pos2 = np.asarray(table["POS_CORR2"], dtype=float).copy()
            crowdsap = float(table_hdu.header["CROWDSAP"])
            flfrcsap = float(table_hdu.header["FLFRCSAP"])

        with fits.open(tpf_path, mode="readonly", memmap=True) as hdul:
            table = hdul[int(tpf_item["table_hdu_index"])].data
            tpf_aperture = np.asarray(
                hdul[int(tpf_item["aperture_hdu_index"])].data
            ).copy()
            optimal = (tpf_aperture & 2) != 0
            tpf_time = np.asarray(table["TIME"], dtype=float).copy()
            tpf_cadenceno = np.asarray(table["CADENCENO"], dtype=np.int64).copy()
            tpf_quality = np.asarray(table["QUALITY"], dtype=np.int64).copy()
            tpf_pos1 = np.asarray(table["POS_CORR1"], dtype=float).copy()
            tpf_pos2 = np.asarray(table["POS_CORR2"], dtype=float).copy()
            pixels = np.asarray(table["FLUX"], dtype=float)[:, optimal].copy()
            pixel_err = np.asarray(table["FLUX_ERR"], dtype=float)[:, optimal].copy()

        hdu_index = int(cbv_item["fits"]["single_scale_hdu_index"])
        with fits.open(cbv_path, mode="readonly", memmap=True) as hdul:
            table = hdul[hdu_index].data
            cbv_cadenceno = np.asarray(table["CADENCENO"], dtype=np.int64).copy()
            cbv_gap = np.asarray(table["GAP"], dtype=bool).copy()
            cbv = np.column_stack(
                [
                    np.asarray(table[f"VECTOR_{index}"], dtype=float)
                    for index in range(1, 9)
                ]
            )

        sector_ledger = ledger.loc[ledger["sector"] == sector].reset_index(drop=True)
        ledger_time = sector_ledger["time_btjd"].to_numpy(float)
        finite_ledger_time = np.isfinite(ledger_time) & np.isfinite(time)
        ledger_time_residual = (
            float(np.max(np.abs(ledger_time[finite_ledger_time] - time[finite_ledger_time])))
            if finite_ledger_time.any()
            else float("inf")
        )
        ledger_time_nan_pattern_exact = bool(
            np.array_equal(np.isfinite(ledger_time), np.isfinite(time))
        )
        tpf_total = np.sum(pixels, axis=1)
        sum_good = np.isfinite(tpf_total) & np.isfinite(sap) & (sap != 0)
        relative_sum_error = np.abs(tpf_total[sum_good] / sap[sum_good] - 1.0)
        alignment = {
            "row_count": int(len(time)),
            "lc_tpf_cadenceno_exact": bool(same_array(cadenceno, tpf_cadenceno)),
            "lc_tpf_time_exact": bool(same_array(time, tpf_time)),
            "lc_tpf_quality_exact": bool(same_array(quality, tpf_quality)),
            "lc_tpf_pos_corr1_exact": bool(same_array(lc_pos1, tpf_pos1)),
            "lc_tpf_pos_corr2_exact": bool(same_array(lc_pos2, tpf_pos2)),
            "lc_tpf_aperture_exact": bool(same_array(lc_aperture, tpf_aperture)),
            "lc_tpf_aperture_hash_exact": lc_item["aperture"]["sha256"]
            == tpf_item["aperture"]["sha256"],
            "optimal_pixel_count": int(optimal.sum()),
            "tpf_sum_vs_sap_median_ratio": float(np.median(tpf_total[sum_good] / sap[sum_good])),
            "tpf_sum_vs_sap_max_abs_fractional_difference": float(
                np.max(relative_sum_error)
            ),
            "cbv_cadenceno_exact": bool(same_array(cadenceno, cbv_cadenceno)),
            "ledger_row_count_exact": len(sector_ledger) == len(time),
            "ledger_cadenceno_exact": bool(
                same_array(sector_ledger["cadenceno"].to_numpy(np.int64), cadenceno)
            ),
            "ledger_time_max_abs_difference_days": ledger_time_residual,
            "ledger_time_within_1e_12_days": bool(
                ledger_time_nan_pattern_exact and ledger_time_residual <= 1e-12
            ),
            "ledger_quality_exact": bool(
                same_array(sector_ledger["quality"].to_numpy(np.int64), quality)
            ),
        }
        if not all(
            alignment[name]
            for name in (
                "lc_tpf_cadenceno_exact",
                "lc_tpf_time_exact",
                "lc_tpf_quality_exact",
                "lc_tpf_pos_corr1_exact",
                "lc_tpf_pos_corr2_exact",
                "lc_tpf_aperture_exact",
                "lc_tpf_aperture_hash_exact",
                "cbv_cadenceno_exact",
                "ledger_row_count_exact",
                "ledger_cadenceno_exact",
                "ledger_time_within_1e_12_days",
                "ledger_quality_exact",
            )
        ):
            raise RuntimeError(
                f"S{sector} LC/TPF/CBV/ledger alignment failed: {alignment}"
            )
        if alignment["optimal_pixel_count"] != int(
            tpf_item["aperture"]["optimal_pixel_count"]
        ):
            raise RuntimeError(f"S{sector} optimal aperture pixel count changed")
        if alignment["tpf_sum_vs_sap_max_abs_fractional_difference"] > 1e-6:
            raise RuntimeError(f"S{sector} TPF optimal sum does not reproduce SAP")
        if selected_cbv[sector] > cbv.shape[1]:
            raise RuntimeError(f"S{sector} selected CBV count is unavailable")

        sectors[sector] = SectorData(
            sector=sector,
            time=time,
            cadenceno=cadenceno,
            quality=quality,
            pdcsap=pdcsap,
            pdcsap_err=pdcsap_err,
            sap=sap,
            sap_err=sap_err,
            pixels=pixels,
            pixel_err=pixel_err,
            cbv=cbv,
            cbv_gap=cbv_gap,
            crowdsap=crowdsap,
            flfrcsap=flfrcsap,
            aperture_sha256=tpf_item["aperture"]["sha256"],
            aperture_pixel_count=int(optimal.sum()),
            lc_product=lc_item,
            tpf_product=tpf_item,
            cbv_product=cbv_item,
            alignment=alignment,
        )
    return sectors


def base_valid(data, flux, error):
    return (
        quality_pass(data.quality)
        & np.isfinite(data.time)
        & np.isfinite(flux)
        & np.isfinite(error)
        & (np.asarray(flux) > 0)
        & (np.asarray(error) > 0)
    )


def training_mask(data, valid, extra_exclude=None):
    if extra_exclude is None:
        extra_exclude = np.zeros(len(data.time), dtype=bool)
    return (
        np.asarray(valid, dtype=bool)
        & (np.abs(phase_days(data.time)) > 0.5 * T14_DAYS)
        & ~np.asarray(extra_exclude, dtype=bool)
    )


def reduce_pdcsap(data, raw_flux=None, extra_exclude=None):
    raw_flux = data.pdcsap if raw_flux is None else np.asarray(raw_flux, dtype=float)
    valid = base_valid(data, raw_flux, data.pdcsap_err)
    train = training_mask(data, valid, extra_exclude)
    normalization = float(np.median(raw_flux[train]))
    flux = np.full(len(raw_flux), np.nan)
    error = np.full(len(raw_flux), np.nan)
    flux[valid] = raw_flux[valid] / normalization
    error[valid] = data.pdcsap_err[valid] / normalization
    return {
        "flux": flux,
        "error": error,
        "valid": valid,
        "meta": {
            "initial_normalization_e_per_s": normalization,
            "normalization_training_count": int(train.sum()),
            "correction_training_count": 0,
            "crowdsap_applied_count": 0,
            "flfrcsap_applied_count": 0,
        },
    }


def reduce_sap_cbv(data, n_cbv, raw_flux=None, extra_exclude=None):
    raw_flux = data.sap if raw_flux is None else np.asarray(raw_flux, dtype=float)
    vectors = data.cbv[:, :n_cbv]
    valid = (
        base_valid(data, raw_flux, data.sap_err)
        & ~data.cbv_gap
        & np.all(np.isfinite(vectors), axis=1)
    )
    train = training_mask(data, valid, extra_exclude)
    normalization = float(np.median(raw_flux[train]))
    vector_mean = np.mean(vectors[train], axis=0)
    vector_scale = np.std(vectors[train], axis=0)
    if np.any(~np.isfinite(vector_scale)) or np.any(vector_scale <= 0):
        raise RuntimeError(f"S{data.sector} selected CBVs have invalid scale")
    standardized = (vectors - vector_mean) / vector_scale
    design = np.column_stack([np.ones(train.sum()), standardized[train]])
    target = raw_flux[train] / normalization - 1.0
    coefficients, _, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    if rank != design.shape[1]:
        raise RuntimeError(f"S{data.sector} selected CBV design is rank deficient")
    systematic = standardized @ coefficients[1:]
    preliminary = raw_flux / normalization - systematic
    post_normalization = float(np.median(preliminary[train]))
    pre_crowding = preliminary / post_normalization
    flux = np.full(len(raw_flux), np.nan)
    error = np.full(len(raw_flux), np.nan)
    flux[valid] = 1.0 + (pre_crowding[valid] - 1.0) / data.crowdsap
    error[valid] = (
        data.sap_err[valid] / normalization / post_normalization / data.crowdsap
    )
    return {
        "flux": flux,
        "error": error,
        "valid": valid,
        "meta": {
            "selected_n_cbv": int(n_cbv),
            "initial_normalization_e_per_s": normalization,
            "post_cbv_oot_normalization": post_normalization,
            "normalization_training_count": int(train.sum()),
            "correction_training_count": int(train.sum()),
            "correction_training_transit_count": 0,
            "cbv_intercept_not_subtracted": float(coefficients[0]),
            "cbv_coefficients_standardized": coefficients[1:].tolist(),
            "cbv_vector_training_means": vector_mean.tolist(),
            "cbv_vector_training_standard_deviations": vector_scale.tolist(),
            "cbv_design_rank": int(rank),
            "crowdsap_applied_count": 1,
            "flfrcsap_applied_count": 0,
        },
    }


def tpf_totals(data, pixels=None):
    pixels = data.pixels if pixels is None else np.asarray(pixels, dtype=float)
    total = np.sum(pixels, axis=1)
    error = np.sqrt(np.sum(data.pixel_err**2, axis=1))
    pixel_valid = np.all(np.isfinite(pixels), axis=1) & np.all(
        np.isfinite(data.pixel_err) & (data.pixel_err > 0), axis=1
    )
    return total, error, pixel_valid


def reduce_tpf_pipeline(data, pixels=None, extra_exclude=None):
    total, total_error, pixel_valid = tpf_totals(data, pixels)
    valid = base_valid(data, total, total_error) & pixel_valid
    train = training_mask(data, valid, extra_exclude)
    normalization = float(np.median(total[train]))
    normalized = total / normalization
    flux = np.full(len(total), np.nan)
    error = np.full(len(total), np.nan)
    flux[valid] = 1.0 + (normalized[valid] - 1.0) / data.crowdsap
    error[valid] = total_error[valid] / normalization / data.crowdsap
    return {
        "flux": flux,
        "error": error,
        "valid": valid,
        "meta": {
            "initial_normalization_e_per_s": normalization,
            "normalization_training_count": int(train.sum()),
            "correction_training_count": 0,
            "optimal_aperture_pixel_count": data.aperture_pixel_count,
            "aperture_sha256": data.aperture_sha256,
            "crowdsap_applied_count": 1,
            "flfrcsap_applied_count": 0,
        },
    }


def make_time_blocks(time, maximum_duration_days=1.0, gap_days=0.25):
    time = np.asarray(time, dtype=float)
    labels = np.zeros(len(time), dtype=int)
    if len(time) == 0:
        return labels, []
    block_id = 0
    start = time[0]
    previous = time[0]
    for index in range(1, len(time)):
        if time[index] - previous > gap_days or time[index] - start >= maximum_duration_days:
            block_id += 1
            start = time[index]
        labels[index] = block_id
        previous = time[index]
    records = []
    for value in np.unique(labels):
        selected = labels == value
        records.append(
            {
                "block_id": int(value),
                "start_btjd": float(time[selected][0]),
                "stop_btjd": float(time[selected][-1]),
                "cadence_count": int(selected.sum()),
            }
        )
    return labels, records


def ridge_fit(design, target, alpha):
    information = design.T @ design
    penalty = np.zeros_like(information)
    if information.shape[0] > 1:
        penalty[1:, 1:] = np.eye(information.shape[0] - 1) * float(alpha)
    rhs = design.T @ target
    return np.linalg.solve(information + penalty, rhs)


def tune_pld(data):
    total, total_error, pixel_valid = tpf_totals(data)
    valid = base_valid(data, total, total_error) & pixel_valid
    oot = training_mask(data, valid)
    oot_index = np.flatnonzero(oot)
    order = np.argsort(data.time[oot_index])
    oot_index = oot_index[order]
    fractions = data.pixels / total[:, None]
    feature_mean = np.mean(fractions[oot_index], axis=0)
    centered = fractions[oot_index] - feature_mean
    _, singular_values, right = np.linalg.svd(centered, full_matrices=False)
    tolerance = singular_values[0] * max(centered.shape) * np.finfo(float).eps
    feature_rank = int(np.count_nonzero(singular_values > tolerance))
    maximum_dimension = min(data.aperture_pixel_count - 1, feature_rank)
    dimensions = sorted(
        set(
            [value for value in PLD_DIMENSION_GRID if value <= maximum_dimension]
            + [maximum_dimension]
        )
    )
    components = right[:maximum_dimension].T
    all_scores = (fractions - feature_mean) @ components
    score_scale = np.std(all_scores[oot], axis=0)
    if np.any(~np.isfinite(score_scale)) or np.any(score_scale <= 0):
        raise RuntimeError(f"S{data.sector} PLD basis has invalid scale")
    all_scores /= score_scale
    block_labels, block_records = make_time_blocks(data.time[oot_index])
    candidates = []
    for dimension in dimensions:
        for alpha in PLD_RIDGE_GRID:
            squared_errors = []
            log_score_sum = 0.0
            validation_count = 0
            fold_count = 0
            for block_id in np.unique(block_labels):
                validation_local = block_labels == block_id
                training_local = ~validation_local
                if validation_local.sum() < 20 or training_local.sum() < 100:
                    continue
                train_index = oot_index[training_local]
                validation_index = oot_index[validation_local]
                normalization = float(np.median(total[train_index]))
                y_train = total[train_index] / normalization - 1.0
                y_validation = total[validation_index] / normalization - 1.0
                train_design = np.column_stack(
                    [np.ones(len(train_index)), all_scores[train_index, :dimension]]
                )
                validation_design = np.column_stack(
                    [
                        np.ones(len(validation_index)),
                        all_scores[validation_index, :dimension],
                    ]
                )
                coefficients = ridge_fit(train_design, y_train, alpha)
                train_residual = y_train - train_design @ coefficients
                validation_residual = y_validation - validation_design @ coefficients
                sigma = max(
                    float(np.sqrt(np.mean(train_residual**2))),
                    float(np.median(total_error[train_index] / normalization)),
                    1e-8,
                )
                squared_errors.append(validation_residual**2)
                log_score_sum += float(
                    np.sum(
                        -0.5 * (validation_residual / sigma) ** 2
                        - math.log(sigma * math.sqrt(2.0 * math.pi))
                    )
                )
                validation_count += int(len(validation_index))
                fold_count += 1
            if validation_count:
                residuals = np.concatenate(squared_errors)
                rmse = float(np.sqrt(np.mean(residuals)))
                candidates.append(
                    {
                        "retained_basis_dimension": int(dimension),
                        "ridge_alpha": float(alpha),
                        "predictive_rmse_fraction": rmse,
                        "predictive_rmse_ppm": rmse * 1e6,
                        "mean_predictive_log_score": float(
                            log_score_sum / validation_count
                        ),
                        "fold_count": int(fold_count),
                        "validation_point_count": int(validation_count),
                    }
                )
    if not candidates:
        raise RuntimeError(f"S{data.sector} PLD validation produced no score")
    selected = min(
        candidates,
        key=lambda item: (
            item["predictive_rmse_fraction"],
            item["retained_basis_dimension"],
            item["ridge_alpha"],
        ),
    )
    return {
        "method": "leave-one-contiguous-out-of-transit-time-block-out prediction",
        "selection_metric": "minimum predictive RMSE; lower dimension then lower alpha break exact ties",
        "transit_points_used": False,
        "transit_depth_used": False,
        "basis_predictors": "first-order normalized fluxes of the SPOC optimal-aperture pixels",
        "basis_construction": "PCA/SVD on all out-of-transit predictors only; no flux target enters the basis",
        "quality_mask": QUALITY_MASK,
        "oot_rule": f"abs(official_phase) > {0.5 * T14_DAYS:.17g} d",
        "block_definition": "gap >0.25 d or elapsed block duration >=1.0 d",
        "block_count": len(block_records),
        "blocks": block_records,
        "out_of_transit_cadence_count": int(len(oot_index)),
        "aperture_pixel_count": data.aperture_pixel_count,
        "maximum_basis_dimension": int(maximum_dimension),
        "dimensions_tested": dimensions,
        "ridge_alphas_tested": list(PLD_RIDGE_GRID),
        "candidate_scores": candidates,
        "selected_retained_basis_dimension": selected["retained_basis_dimension"],
        "selected_ridge_alpha": selected["ridge_alpha"],
        "selected_predictive_rmse_ppm": selected["predictive_rmse_ppm"],
        "selected_mean_predictive_log_score": selected[
            "mean_predictive_log_score"
        ],
        "finite": bool(np.isfinite(selected["predictive_rmse_fraction"])),
    }


def reduce_tpf_pld(data, tuning, pixels=None, extra_exclude=None):
    pixels = data.pixels if pixels is None else np.asarray(pixels, dtype=float)
    total, total_error, pixel_valid = tpf_totals(data, pixels)
    valid = base_valid(data, total, total_error) & pixel_valid
    train = training_mask(data, valid, extra_exclude)
    fractions = pixels / total[:, None]
    feature_mean = np.mean(fractions[train], axis=0)
    centered_train = fractions[train] - feature_mean
    _, singular_values, right = np.linalg.svd(centered_train, full_matrices=False)
    tolerance = singular_values[0] * max(centered_train.shape) * np.finfo(float).eps
    feature_rank = int(np.count_nonzero(singular_values > tolerance))
    dimension = int(tuning["selected_retained_basis_dimension"])
    alpha = float(tuning["selected_ridge_alpha"])
    if dimension > min(data.aperture_pixel_count - 1, feature_rank):
        raise RuntimeError(f"S{data.sector} selected PLD dimension is unavailable")
    components = right[:dimension].T
    scores = (fractions - feature_mean) @ components
    score_scale = np.std(scores[train], axis=0)
    scores /= score_scale
    normalization = float(np.median(total[train]))
    target = total[train] / normalization - 1.0
    design = np.column_stack([np.ones(train.sum()), scores[train]])
    coefficients = ridge_fit(design, target, alpha)
    systematic = scores @ coefficients[1:]
    preliminary = total / normalization - systematic
    post_normalization = float(np.median(preliminary[train]))
    pre_crowding = preliminary / post_normalization
    flux = np.full(len(total), np.nan)
    error = np.full(len(total), np.nan)
    flux[valid] = 1.0 + (pre_crowding[valid] - 1.0) / data.crowdsap
    error[valid] = (
        total_error[valid] / normalization / post_normalization / data.crowdsap
    )
    return {
        "flux": flux,
        "error": error,
        "valid": valid,
        "meta": {
            "selected_retained_basis_dimension": dimension,
            "selected_ridge_alpha": alpha,
            "initial_normalization_e_per_s": normalization,
            "post_pld_oot_normalization": post_normalization,
            "normalization_training_count": int(train.sum()),
            "correction_training_count": int(train.sum()),
            "correction_training_transit_count": 0,
            "pld_intercept_not_subtracted": float(coefficients[0]),
            "pld_coefficients_standardized": coefficients[1:].tolist(),
            "pixel_fraction_training_means": feature_mean.tolist(),
            "basis_score_training_standard_deviations": score_scale.tolist(),
            "basis_component_sha256": array_sha256(components),
            "basis_rank": feature_rank,
            "optimal_aperture_pixel_count": data.aperture_pixel_count,
            "aperture_sha256": data.aperture_sha256,
            "crowdsap_applied_count": 1,
            "flfrcsap_applied_count": 0,
        },
    }


def event_window_mask(time, events, sector, half_width):
    selected = np.zeros(len(time), dtype=bool)
    for event in events:
        if int(event["sector"]) == int(sector):
            selected |= np.abs(time - event["midpoint_btjd"]) <= half_width
    return selected


def fixed_depth_fit(time, flux, error, center, valid=None):
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    error = np.asarray(error, dtype=float)
    distance = time - float(center)
    in_transit = np.abs(distance) <= 0.5 * T14_DAYS
    baseline = (np.abs(distance) >= 1.2 * T14_DAYS) & (
        np.abs(distance) <= 2.5 * T14_DAYS
    )
    selected = (
        (in_transit | baseline)
        & np.isfinite(time)
        & np.isfinite(flux)
        & np.isfinite(error)
        & (error > 0)
    )
    if valid is not None:
        selected &= np.asarray(valid, dtype=bool)
    in_selected = in_transit[selected]
    if in_selected.sum() < 20 or (~in_selected).sum() < 40:
        return None
    x = distance[selected] / T14_DAYS
    design = np.column_stack([np.ones(selected.sum()), x, -in_selected.astype(float)])
    weights = 1.0 / error[selected] ** 2
    information = design.T @ (weights[:, None] * design)
    rhs = design.T @ (weights * flux[selected])
    covariance = np.linalg.pinv(information)
    coefficients = covariance @ rhs
    residual = flux[selected] - design @ coefficients
    chi2 = float(np.sum((residual / error[selected]) ** 2))
    dof = max(1, int(selected.sum() - design.shape[1]))
    depth = float(coefficients[-1])
    depth_error = float(math.sqrt(max(0.0, covariance[-1, -1])))
    return {
        "depth_fraction": depth,
        "depth_ppm": depth * 1e6,
        "depth_error_fraction": depth_error,
        "depth_error_ppm": depth_error * 1e6,
        "significance": depth / depth_error if depth_error > 0 else None,
        "n_points": int(selected.sum()),
        "n_in_transit": int(in_selected.sum()),
        "n_out_of_transit": int((~in_selected).sum()),
        "reduced_chi2_formal_errors": chi2 / dof,
        "design_rank": int(np.linalg.matrix_rank(design)),
    }


def sector_depth_fit(data, reduction, sector_events):
    rows = []
    for event_index, event in enumerate(sector_events):
        distance = data.time - event["midpoint_btjd"]
        in_transit = np.abs(distance) <= 0.5 * T14_DAYS
        baseline = (np.abs(distance) >= 1.2 * T14_DAYS) & (
            np.abs(distance) <= 2.5 * T14_DAYS
        )
        selected = reduction["valid"] & (in_transit | baseline)
        selected &= (
            np.isfinite(reduction["flux"])
            & np.isfinite(reduction["error"])
            & (reduction["error"] > 0)
        )
        for index in np.flatnonzero(selected):
            rows.append(
                (
                    event_index,
                    (data.time[index] - event["midpoint_btjd"]) / T14_DAYS,
                    bool(in_transit[index]),
                    reduction["flux"][index],
                    reduction["error"][index],
                )
            )
    event_count = len(sector_events)
    if not rows:
        return None
    design = np.zeros((len(rows), 2 * event_count + 1))
    flux = np.empty(len(rows))
    error = np.empty(len(rows))
    in_count = 0
    for row_index, (event_index, x, in_transit, value, uncertainty) in enumerate(rows):
        design[row_index, 2 * event_index] = 1.0
        design[row_index, 2 * event_index + 1] = x
        design[row_index, -1] = -float(in_transit)
        flux[row_index] = value
        error[row_index] = uncertainty
        in_count += int(in_transit)
    weights = 1.0 / error**2
    information = design.T @ (weights[:, None] * design)
    covariance = np.linalg.pinv(information)
    coefficients = covariance @ (design.T @ (weights * flux))
    residual = flux - design @ coefficients
    dof = max(1, len(rows) - int(np.linalg.matrix_rank(design)))
    depth = float(coefficients[-1])
    depth_error = float(math.sqrt(max(0.0, covariance[-1, -1])))
    significance = depth / depth_error if depth_error > 0 else float("nan")
    return {
        "sector": int(data.sector),
        "event_count": event_count,
        "used_epochs": [int(item["epoch"]) for item in sector_events],
        "n_points": len(rows),
        "n_in_transit": int(in_count),
        "n_out_of_transit": int(len(rows) - in_count),
        "depth_fraction": depth,
        "depth_ppm": depth * 1e6,
        "depth_error_fraction": depth_error,
        "depth_error_ppm": depth_error * 1e6,
        "significance": significance,
        "positive_at_least_3sigma": bool(
            np.isfinite(significance)
            and depth > 0
            and significance >= MIN_SECTOR_SIGNAL_SIGMA
        ),
        "formal_error_definition": "inverse weighted linear-design information; not residual-inflated",
        "reduced_chi2_formal_errors": float(np.sum((residual / error) ** 2) / dof),
        "design_rank": int(np.linalg.matrix_rank(design)),
    }


def duration_hours(theta):
    rp, a_rs, impact = [float(value) for value in theta]
    if impact >= 1.0 + rp or impact >= a_rs:
        return float("nan")
    sin_i = math.sqrt(max(0.0, 1.0 - (impact / a_rs) ** 2))
    numerator = math.sqrt(max(0.0, (1.0 + rp) ** 2 - impact**2))
    argument = numerator / (a_rs * sin_i)
    if not 0.0 <= argument <= 1.0:
        return float("nan")
    return PERIOD_DAYS * 24.0 / math.pi * math.asin(argument)


class TransitProfiler:
    def __init__(self, frame):
        self.frame = frame
        self.time = frame["time_btjd"].to_numpy(float)
        self.phase = phase_days(self.time)
        self.flux = frame["flux"].to_numpy(float)
        self.sector = frame["sector"].to_numpy(int)
        self.noise = np.empty(len(frame))
        self.indices = {}
        self.design = {}
        self.noise_by_sector = {}
        for sector in SECTORS:
            index = np.flatnonzero(self.sector == sector)
            self.indices[sector] = index
            time = self.time[index]
            mean = float(np.mean(time))
            scale = float(np.std(time))
            self.design[sector] = np.column_stack(
                [np.ones(len(index)), (time - mean) / scale]
            )
            oot = np.abs(self.phase[index]) > 0.5 * T14_DAYS
            ordered = np.argsort(time[oot])
            differences = np.diff(self.flux[index][oot][ordered])
            difference_scale = robust_scale(differences)
            if difference_scale is not None:
                difference_scale /= math.sqrt(2.0)
            formal = float(np.median(frame.iloc[index]["flux_err"]))
            noise = max(difference_scale or 0.0, formal, 1e-7)
            self.noise[index] = noise
            self.noise_by_sector[str(sector)] = {
                "fixed_robust_noise_fraction": noise,
                "median_propagated_error_fraction": formal,
            }
        params = batman.TransitParams()
        params.t0 = 0.0
        params.per = PERIOD_DAYS
        params.rp = 0.055
        params.a = 10.4
        params.inc = 86.0
        params.ecc = 0.0
        params.w = 90.0
        params.u = [LD_U1, LD_U2]
        params.limb_dark = "quadratic"
        self.params = params
        self.model = batman.TransitModel(
            params,
            self.phase,
            supersample_factor=SUPERSAMPLE_FACTOR,
            exp_time=EXPOSURE_SECONDS / 86400.0,
        )

    def transit(self, theta):
        rp, a_rs, impact = [float(value) for value in theta]
        if impact >= 1.0 + rp or impact >= a_rs:
            return None
        cosine = impact / a_rs
        if not 0.0 <= cosine < 1.0:
            return None
        self.params.rp = rp
        self.params.a = a_rs
        self.params.inc = math.degrees(math.acos(cosine))
        return self.model.light_curve(self.params)

    def profile(self, theta):
        transit = self.transit(theta)
        if transit is None or not np.all(np.isfinite(transit)):
            return None
        residual = np.empty_like(self.flux)
        coefficients = {}
        ranks = {}
        for sector in SECTORS:
            index = self.indices[sector]
            design = self.design[sector]
            beta, _, rank, _ = np.linalg.lstsq(
                design, self.flux[index] - transit[index], rcond=None
            )
            residual[index] = self.flux[index] - transit[index] - design @ beta
            coefficients[sector] = beta
            ranks[sector] = int(rank)
        return residual, transit, coefficients, ranks

    def residual(self, theta):
        profile = self.profile(theta)
        if profile is None:
            return np.full(len(self.flux), 1e6)
        return profile[0] / self.noise


def geometry_frame(sectors, reductions, events, branch):
    frames = []
    for sector in SECTORS:
        data = sectors[sector]
        reduction = reductions[branch][sector]
        window = event_window_mask(
            data.time, events, sector, HALF_MODEL_WINDOW_DAYS
        )
        selected = reduction["valid"] & window
        selected &= (
            np.isfinite(reduction["flux"])
            & np.isfinite(reduction["error"])
            & (reduction["error"] > 0)
        )
        frames.append(
            pd.DataFrame(
                {
                    "time_btjd": data.time[selected],
                    "sector": sector,
                    "flux": reduction["flux"][selected],
                    "flux_err": reduction["error"][selected],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def fit_geometry(frame, branch):
    profiler = TransitProfiler(frame)
    lower = np.array([0.03, 5.0, 0.0])
    upper = np.array([0.09, 16.0, 0.98])
    results = []
    attempts = []
    for start_index, start_values in enumerate(GEOMETRY_STARTS):
        start = np.asarray(start_values, dtype=float)
        result = least_squares(
            profiler.residual,
            start,
            bounds=(lower, upper),
            method="trf",
            loss="soft_l1",
            f_scale=1.0,
            x_scale="jac",
            max_nfev=500,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        results.append(result)
        attempts.append(
            {
                "start_index": start_index,
                "initial": start.tolist(),
                "final": result.x.tolist(),
                "movement": (result.x - start).tolist(),
                "cost": float(result.cost),
                "success": bool(result.success),
                "status": int(result.status),
                "n_function_evaluations": int(result.nfev),
                "optimality": float(result.optimality),
            }
        )
    finite = [index for index, result in enumerate(results) if np.isfinite(result.cost)]
    successful = [index for index in finite if results[index].success]
    candidates = successful or finite
    if not candidates:
        raise RuntimeError(f"{branch} geometry optimizer has no finite result")
    best_index = min(candidates, key=lambda index: results[index].cost)
    result = results[best_index]
    profile = profiler.profile(result.x)
    if profile is None:
        raise RuntimeError(f"{branch} geometry optimum is invalid")
    _, _, coefficients, ranks = profile
    nuisance_rank = int(sum(ranks.values()))
    dof = max(1, len(frame) - 3 - nuisance_rank)
    jacobian = np.asarray(result.jac, dtype=float)
    information = jacobian.T @ jacobian
    jacobian_rank = int(np.linalg.matrix_rank(jacobian))
    condition = float(np.linalg.cond(information))
    scale = max(1.0, float(2.0 * result.cost / dof))
    covariance = np.linalg.pinv(information) * scale
    errors = np.sqrt(np.clip(np.diag(covariance), 0.0, np.inf))
    covariance_valid = bool(
        result.success
        and jacobian_rank == 3
        and np.all(np.isfinite(covariance))
        and np.all(np.diag(covariance) > 0)
        and np.isfinite(condition)
        and condition < 1e14
    )
    t14 = duration_hours(result.x)
    gradient = np.empty(3)
    steps = np.array([1e-6, 1e-4, 1e-5])
    for index, step in enumerate(steps):
        plus = result.x.copy()
        minus = result.x.copy()
        plus[index] += step
        minus[index] -= step
        gradient[index] = (duration_hours(plus) - duration_hours(minus)) / (2 * step)
    t14_variance = float(gradient @ covariance @ gradient)
    t14_error = math.sqrt(max(0.0, t14_variance))
    covariance_valid &= bool(np.isfinite(t14_error) and t14_error > 0)
    parameters = {
        "rp_rs": {"value": float(result.x[0]), "error": float(errors[0])},
        "a_rs": {"value": float(result.x[1]), "error": float(errors[1])},
        "impact_parameter": {
            "value": float(result.x[2]),
            "error": float(errors[2]),
        },
        "t14_hours": {"value": float(t14), "error": float(t14_error)},
    }
    return {
        "model": {
            "timestamps": "native 120-s BTJD in +/-13 h around exactly the 16 Phase-2 used events",
            "period_days_fixed": PERIOD_DAYS,
            "t0_btjd_fixed": T0_BTJD,
            "limb_darkening_fixed": [LD_U1, LD_U2],
            "exposure_seconds": EXPOSURE_SECONDS,
            "supersample_factor": SUPERSAMPLE_FACTOR,
            "shared_parameters": ["rp_rs", "a_rs", "impact_parameter"],
            "profiled_per_sector": ["sector_offset", "sector_linear_time"],
            "branches_combined_as_independent_likelihoods": False,
        },
        "n_points": int(len(frame)),
        "n_points_by_sector": {
            str(sector): int(np.count_nonzero(frame["sector"] == sector))
            for sector in SECTORS
        },
        "optimizer": {
            "algorithm": "scipy least_squares TRF, bounded soft_l1",
            "multiple_start_count": len(GEOMETRY_STARTS),
            "selected_start_index": best_index,
            "selected_success": bool(result.success),
            "selected_cost": float(result.cost),
            "attempts": attempts,
        },
        "covariance": {
            "method": "profiled robust Gauss-Newton inverse information; scale floored at unity",
            "matrix_parameter_order": ["rp_rs", "a_rs", "impact_parameter"],
            "matrix": covariance.tolist(),
            "jacobian_shape": list(jacobian.shape),
            "jacobian_rank": jacobian_rank,
            "information_condition_number": condition,
            "residual_degrees_of_freedom": dof,
            "nuisance_parameter_rank": nuisance_rank,
            "scale_factor": scale,
            "valid": covariance_valid,
        },
        "parameters": parameters,
        "profiled_coefficients": {
            str(sector): {
                "sector_offset": float(coefficients[sector][0]),
                "sector_linear_time": float(coefficients[sector][1]),
            }
            for sector in SECTORS
        },
        "fixed_noise_by_sector": profiler.noise_by_sector,
        "pass_optimizer_and_covariance": covariance_valid,
    }


def synthetic_transit(time, center, rp_rs, impact_parameter):
    params = batman.TransitParams()
    params.t0 = float(center)
    params.per = PERIOD_DAYS
    params.rp = float(rp_rs)
    params.a = 10.135975091911344
    params.inc = math.degrees(math.acos(float(impact_parameter) / params.a))
    params.ecc = 0.0
    params.w = 90.0
    params.u = [LD_U1, LD_U2]
    params.limb_dark = "quadratic"
    model = batman.TransitModel(
        params,
        np.asarray(time, dtype=float),
        supersample_factor=SUPERSAMPLE_FACTOR,
        exp_time=EXPOSURE_SECONDS / 86400.0,
    )
    light_curve = model.light_curve(params)
    # Keep one off-target event rather than the neighboring periodic copies.
    light_curve[np.abs(np.asarray(time, dtype=float) - center) > 0.5 * PERIOD_DAYS] = 1.0
    return light_curve


def choose_injection_centers(data):
    total, total_error, pixel_valid = tpf_totals(data)
    common = (
        base_valid(data, data.pdcsap, data.pdcsap_err)
        & base_valid(data, data.sap, data.sap_err)
        & base_valid(data, total, total_error)
        & pixel_valid
        & ~data.cbv_gap
        & np.all(np.isfinite(data.cbv[:, :8]), axis=1)
    )
    indices = np.flatnonzero(common)
    candidates = []
    minimum_in = int(math.floor(0.80 * T14_DAYS * 720.0))
    minimum_side = int(math.floor(0.70 * 1.3 * T14_DAYS * 720.0))
    for index in indices[::20]:
        center = data.time[index]
        if abs(float(phase_days([center])[0])) <= 3.5 * T14_DAYS:
            continue
        distance = data.time - center
        in_count = np.count_nonzero(common & (np.abs(distance) <= 0.5 * T14_DAYS))
        left_count = np.count_nonzero(
            common
            & (distance >= -2.5 * T14_DAYS)
            & (distance <= -1.2 * T14_DAYS)
        )
        right_count = np.count_nonzero(
            common
            & (distance >= 1.2 * T14_DAYS)
            & (distance <= 2.5 * T14_DAYS)
        )
        if in_count >= minimum_in and left_count >= minimum_side and right_count >= minimum_side:
            candidates.append(float(center))
    if len(candidates) < INJECTIONS_PER_SECTOR:
        raise RuntimeError(f"S{data.sector} lacks four bounded injection windows")
    candidates = np.asarray(candidates)
    targets = np.quantile(candidates, [0.10, 0.37, 0.63, 0.90])
    selected = []
    for target in targets:
        for candidate in candidates[np.argsort(np.abs(candidates - target))]:
            if all(abs(candidate - prior) > 5.0 * T14_DAYS for prior in selected):
                selected.append(float(candidate))
                break
    if len(selected) < INJECTIONS_PER_SECTOR:
        for candidate in candidates:
            if all(abs(candidate - prior) > 5.0 * T14_DAYS for prior in selected):
                selected.append(float(candidate))
            if len(selected) == INJECTIONS_PER_SECTOR:
                break
    if len(selected) != INJECTIONS_PER_SECTOR:
        raise RuntimeError(f"S{data.sector} injection centers could not be separated")
    return sorted(selected)


def injected_pixels(data, model, extra_exclude, normalization):
    total, total_error, pixel_valid = tpf_totals(data)
    valid = base_valid(data, total, total_error) & pixel_valid
    train = training_mask(data, valid, extra_exclude)
    pixel_profile = np.median(data.pixels[train], axis=0)
    pixel_profile = np.clip(pixel_profile, 0.0, np.inf)
    weights = pixel_profile / np.sum(pixel_profile)
    signal = normalization * data.crowdsap * (model - 1.0)
    return data.pixels + signal[:, None] * weights[None, :], weights


def injection_trial_result(
    branch, data, center, rp_rs, impact_parameter, sham, injected, model, extra
):
    common_valid = sham["valid"] & injected["valid"]
    sham_depth = fixed_depth_fit(
        data.time, sham["flux"], sham["error"], center, common_valid
    )
    injected_depth = fixed_depth_fit(
        data.time, injected["flux"], injected["error"], center, common_valid
    )
    expected_depth = fixed_depth_fit(
        data.time,
        model,
        sham["error"],
        center,
        common_valid,
    )
    if sham_depth is None or injected_depth is None or expected_depth is None:
        raise RuntimeError(f"{branch} S{data.sector} injection depth fit failed")
    recovered = injected_depth["depth_fraction"] - sham_depth["depth_fraction"]
    expected = expected_depth["depth_fraction"]
    fractional_bias = (recovered - expected) / expected
    recovered_gate = bool(
        recovered > 0 and abs(fractional_bias) <= MAX_RECOVERED_TRIAL_ABS_BIAS
    )
    return {
        "branch": branch,
        "sector": int(data.sector),
        "center_btjd": float(center),
        "injected_rp_rs": float(rp_rs),
        "injected_impact_parameter": float(impact_parameter),
        "expected_fixed_window_depth_ppm": expected * 1e6,
        "sham_fixed_window_depth_ppm": sham_depth["depth_ppm"],
        "injected_series_fixed_window_depth_ppm": injected_depth["depth_ppm"],
        "recovered_incremental_depth_ppm": recovered * 1e6,
        "fractional_depth_recovery_bias": float(fractional_bias),
        "absolute_fractional_depth_recovery_bias": float(abs(fractional_bias)),
        "recovery_definition": (
            "positive incremental depth and absolute fractional bias <= "
            f"{MAX_RECOVERED_TRIAL_ABS_BIAS:.2f}"
        ),
        "recovered": recovered_gate,
        "quality_and_timestamps_modified": False,
        "injected_window_excluded_from_training": True,
        "injected_window_excluded_cadence_count": int(extra.sum()),
        "fixed_window_point_count": injected_depth["n_points"],
    }


def run_injections(sectors, selected_cbv, pld_tuning):
    trials = {branch: [] for branch in BRANCHES}
    centers_by_sector = {}
    for sector in SECTORS:
        data = sectors[sector]
        centers = choose_injection_centers(data)
        centers_by_sector[str(sector)] = centers
        for trial_index, (center, config) in enumerate(zip(centers, INJECTION_CONFIGS), 1):
            rp_rs, impact = config
            model = synthetic_transit(data.time, center, rp_rs, impact)
            extra = np.abs(data.time - center) <= INJECTION_EXCLUSION_HALF_WIDTH_DAYS

            pdcsap_sham = reduce_pdcsap(data, extra_exclude=extra)
            pdcsap_raw = data.pdcsap + pdcsap_sham["meta"][
                "initial_normalization_e_per_s"
            ] * (model - 1.0)
            pdcsap_injected = reduce_pdcsap(data, pdcsap_raw, extra)

            sap_sham = reduce_sap_cbv(
                data, selected_cbv[sector], extra_exclude=extra
            )
            sap_raw = data.sap + (
                sap_sham["meta"]["initial_normalization_e_per_s"]
                * data.crowdsap
                * (model - 1.0)
            )
            sap_injected = reduce_sap_cbv(
                data, selected_cbv[sector], sap_raw, extra
            )

            pipeline_sham = reduce_tpf_pipeline(data, extra_exclude=extra)
            pixels_injected, pixel_weights = injected_pixels(
                data,
                model,
                extra,
                pipeline_sham["meta"]["initial_normalization_e_per_s"],
            )
            pipeline_injected = reduce_tpf_pipeline(data, pixels_injected, extra)
            pld_sham = reduce_tpf_pld(
                data, pld_tuning[sector], extra_exclude=extra
            )
            pld_injected = reduce_tpf_pld(
                data, pld_tuning[sector], pixels_injected, extra
            )

            branch_pairs = {
                "pdcsap": (pdcsap_sham, pdcsap_injected),
                "sap_cbv": (sap_sham, sap_injected),
                "tpf_pipeline": (pipeline_sham, pipeline_injected),
                "tpf_pld": (pld_sham, pld_injected),
            }
            for branch, (sham, injected) in branch_pairs.items():
                result = injection_trial_result(
                    branch,
                    data,
                    center,
                    rp_rs,
                    impact,
                    sham,
                    injected,
                    model,
                    extra,
                )
                result["trial_id"] = f"S{sector:03d}-I{trial_index:02d}"
                result["injection_domain"] = (
                    "raw PDCSAP_FLUX"
                    if branch == "pdcsap"
                    else "raw SAP_FLUX"
                    if branch == "sap_cbv"
                    else "calibrated optimal-aperture TPF FLUX pixels"
                )
                if branch.startswith("tpf"):
                    result["injected_pixel_weight_min"] = float(pixel_weights.min())
                    result["injected_pixel_weight_max"] = float(pixel_weights.max())
                    result["same_spoc_aperture_pixels"] = True
                trials[branch].append(result)
    summaries = {}
    for branch in BRANCHES:
        records = trials[branch]
        absolute_bias = np.asarray(
            [item["absolute_fractional_depth_recovery_bias"] for item in records]
        )
        signed_bias = np.asarray(
            [item["fractional_depth_recovery_bias"] for item in records]
        )
        recovered_count = int(sum(item["recovered"] for item in records))
        recovery_rate = recovered_count / len(records) if records else 0.0
        counts_by_sector = {
            str(sector): int(sum(item["sector"] == sector for item in records))
            for sector in SECTORS
        }
        checks = {
            "at_least_24_trials": len(records) >= MIN_INJECTIONS_PER_BRANCH,
            "all_six_sectors_with_four_trials": all(
                count == INJECTIONS_PER_SECTOR for count in counts_by_sector.values()
            ),
            "recovery_rate_at_least_0_90": recovery_rate
            >= MIN_INJECTION_RECOVERY_RATE,
            "median_absolute_fractional_bias_at_most_0_05": bool(
                len(absolute_bias)
                and np.median(absolute_bias) <= MAX_MEDIAN_ABS_INJECTION_BIAS
            ),
        }
        summaries[branch] = {
            "trial_count": len(records),
            "trial_count_by_sector": counts_by_sector,
            "recovered_count": recovered_count,
            "recovery_rate": recovery_rate,
            "median_fractional_depth_recovery_bias": float(np.median(signed_bias)),
            "median_absolute_fractional_depth_recovery_bias": float(
                np.median(absolute_bias)
            ),
            "maximum_absolute_fractional_depth_recovery_bias": float(
                np.max(absolute_bias)
            ),
            "checks": checks,
            "gate_pass": all(checks.values()),
            "trials": records,
        }
    return summaries, centers_by_sector


def provenance_id(branch, data, tuning=None):
    if branch == "pdcsap":
        return f"S{data.sector:03d}-PDCSAP-{data.lc_product['actual_sha256'][:12]}"
    if branch == "sap_cbv":
        return (
            f"S{data.sector:03d}-SAPCBV-{data.lc_product['actual_sha256'][:8]}-"
            f"{data.cbv_product['sha256'][:8]}"
        )
    if branch == "tpf_pipeline":
        return f"S{data.sector:03d}-TPFOPT-{data.tpf_product['actual_sha256'][:12]}"
    return (
        f"S{data.sector:03d}-TPFPLD-{data.tpf_product['actual_sha256'][:8]}-"
        f"d{int(tuning['selected_retained_basis_dimension']):02d}-"
        f"a{float(tuning['selected_ridge_alpha']):g}"
    )


def build_long_table(sectors, reductions, pld_tuning):
    frames = []
    provenance = {}
    counts = {}
    for branch in BRANCHES:
        counts[branch] = {}
        for sector in SECTORS:
            data = sectors[sector]
            result = reductions[branch][sector]
            selected = result["valid"]
            identifier = provenance_id(
                branch, data, pld_tuning[sector] if branch == "tpf_pld" else None
            )
            source = data.lc_product if branch in ("pdcsap", "sap_cbv") else data.tpf_product
            provenance[identifier] = {
                "branch": branch,
                "sector": sector,
                "source_product_id": source["product_id"],
                "source_relative_path": source["relative_path"],
                "source_sha256": source["actual_sha256"],
                "cbv_relative_path": data.cbv_product["relative_path"]
                if branch == "sap_cbv"
                else None,
                "cbv_sha256": data.cbv_product["sha256"]
                if branch == "sap_cbv"
                else None,
                "aperture_sha256": data.aperture_sha256,
            }
            counts[branch][str(sector)] = int(selected.sum())
            frames.append(
                pd.DataFrame(
                    {
                        "time_btjd": data.time[selected],
                        "sector": sector,
                        "cadenceno": data.cadenceno[selected],
                        "branch": branch,
                        "flux": result["flux"][selected],
                        "flux_err": result["error"][selected],
                        "quality": data.quality[selected],
                        "crowdsap": data.crowdsap,
                        "crowdsap_applied_count": result["meta"][
                            "crowdsap_applied_count"
                        ],
                        "flfrcsap": data.flfrcsap,
                        "exposure_seconds": EXPOSURE_SECONDS,
                        "provenance_id": identifier,
                        "source_product_id": source["product_id"],
                        "source_sha256": source["actual_sha256"],
                        "aperture_sha256": data.aperture_sha256,
                    }
                )
            )
    table = pd.concat(frames, ignore_index=True)
    return table, provenance, counts


def write_deterministic_gzip_csv(frame, path):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(
            fileobj=raw, mode="wb", filename="", compresslevel=9, mtime=0
        ) as compressed:
            with io.TextIOWrapper(compressed, encoding="ascii", newline="") as text:
                frame.to_csv(text, index=False, float_format="%.17g")
    temporary.replace(path)


def geometry_comparison(geometry, accepted):
    parameter_names = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")
    pairwise = []
    maxima = {name: 0.0 for name in parameter_names}
    for left_index, left in enumerate(accepted):
        for right in accepted[left_index + 1 :]:
            shifts = {}
            for parameter in parameter_names:
                left_value = geometry[left]["parameters"][parameter]
                right_value = geometry[right]["parameters"][parameter]
                combined = math.hypot(left_value["error"], right_value["error"])
                absolute = abs(left_value["value"] - right_value["value"])
                sigma = absolute / combined if combined > 0 else float("inf")
                maxima[parameter] = max(maxima[parameter], sigma)
                shifts[parameter] = {
                    "absolute_shift": absolute,
                    "quadrature_combined_error": combined,
                    "combined_sigma_shift": sigma,
                    "threshold_combined_sigma": MAX_GEOMETRY_SHIFT_SIGMA,
                    "pass": bool(sigma <= MAX_GEOMETRY_SHIFT_SIGMA),
                }
            pairwise.append({"left_branch": left, "right_branch": right, "shifts": shifts})
    shift_gate = bool(
        len(accepted) >= 2
        and all(value <= MAX_GEOMETRY_SHIFT_SIGMA for value in maxima.values())
    )
    systematic_values = {}
    propagated_uncertainties = {branch: {} for branch in accepted}
    for parameter in parameter_names:
        values = np.asarray(
            [geometry[branch]["parameters"][parameter]["value"] for branch in accepted]
        )
        if len(values) > 1:
            standard_deviation = float(np.std(values, ddof=1))
            half_range = float(0.5 * np.ptp(values))
        else:
            standard_deviation = 0.0
            half_range = 0.0
        adopted = max(standard_deviation, half_range)
        systematic_values[parameter] = {
            "between_reduction_standard_deviation": standard_deviation,
            "half_range": half_range,
            "adopted_systematic": adopted,
        }
        for branch in accepted:
            formal = geometry[branch]["parameters"][parameter]["error"]
            propagated_uncertainties[branch][parameter] = {
                "formal_error": formal,
                "between_reduction_systematic": adopted if not shift_gate else 0.0,
                "total_error": math.hypot(formal, adopted)
                if not shift_gate
                else formal,
            }
    propagated = bool(len(accepted) >= 2 and not shift_gate)
    return {
        "accepted_branches_only": accepted,
        "gate_definition": "all accepted-branch shifts <=0.5 quadrature-combined sigma",
        "pairwise_shifts": pairwise,
        "maximum_combined_sigma_shift": maxima,
        "shift_gate_pass": shift_gate,
        "between_reduction_systematic": {
            "rule": "larger of accepted-branch sample SD and half-range, added in quadrature when the 0.5-sigma gate fails",
            "values": systematic_values,
            "propagated": propagated,
            "propagated_uncertainties": propagated_uncertainties,
        },
    }


def branch_acceptance(branch, reductions, depths, geometry, injection, tuning):
    six_valid = all(
        int(reductions[branch][sector]["valid"].sum()) > 100 for sector in SECTORS
    )
    signal = all(depths[branch][sector]["positive_at_least_3sigma"] for sector in SECTORS)
    covariance = geometry[branch]["covariance"]["valid"]
    if branch == "sap_cbv":
        tuning_finite = all(
            np.isfinite(tuning[sector]["selected_predictive_rmse_ppm"])
            for sector in SECTORS
        )
    elif branch == "tpf_pld":
        tuning_finite = all(tuning[sector]["finite"] for sector in SECTORS)
    else:
        tuning_finite = True
    checks = {
        "six_valid_sectors": six_valid,
        "positive_depth_at_least_3sigma_each_sector": signal,
        "finite_geometry_covariance": covariance,
        "finite_predictive_tuning_if_applicable": tuning_finite,
        "injection_recovery_rate_at_least_0_90": injection["recovery_rate"]
        >= MIN_INJECTION_RECOVERY_RATE,
        "median_absolute_injection_bias_at_most_0_05": injection[
            "median_absolute_fractional_depth_recovery_bias"
        ]
        <= MAX_MEDIAN_ABS_INJECTION_BIAS,
        "injection_trial_count_at_least_24": injection["trial_count"]
        >= MIN_INJECTIONS_PER_BRANCH,
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "checks": checks,
        "accepted": all(checks.values()),
        "rejection_reasons": reasons,
    }


def main():
    print("PHASE 4: INDEPENDENT 120-S REDUCTION COMPARISON")
    faz1 = load_json(FAZ1_PATH)
    faz2 = load_json(FAZ2_PATH)
    faz3 = load_json(FAZ3_PATH)
    faz3_input = load_json(FAZ3_INPUT_PATH)
    official = load_json(OFFICIAL_PATH)
    input_checks, selected_cbv = validate_inputs(
        faz1, faz2, faz3, faz3_input, official
    )
    events, gaps = used_events(faz2)
    ledger = pd.read_csv(LEDGER_PATH)
    expected_ledger_rows = int(
        faz2["provenance"]["cadence_ledgers"]["120"]["row_count"]
    )
    if len(ledger) != expected_ledger_rows:
        raise RuntimeError("120-s ledger row count changed after Phase 2")
    sectors = load_sector_data(faz1, faz3_input, ledger, selected_cbv)

    pld_tuning = {}
    for sector in SECTORS:
        pld_tuning[sector] = tune_pld(sectors[sector])
        selected = pld_tuning[sector]
        print(
            f"S{sector:03d} PLD: d={selected['selected_retained_basis_dimension']}, "
            f"alpha={selected['selected_ridge_alpha']:g}, "
            f"RMSE={selected['selected_predictive_rmse_ppm']:.2f} ppm"
        )

    reductions = {branch: {} for branch in BRANCHES}
    for sector in SECTORS:
        data = sectors[sector]
        reductions["pdcsap"][sector] = reduce_pdcsap(data)
        reductions["sap_cbv"][sector] = reduce_sap_cbv(
            data, selected_cbv[sector]
        )
        reductions["tpf_pipeline"][sector] = reduce_tpf_pipeline(data)
        reductions["tpf_pld"][sector] = reduce_tpf_pld(
            data, pld_tuning[sector]
        )

    event_depths = []
    sector_depths = {branch: {} for branch in BRANCHES}
    sector_depth_rows = []
    for branch in BRANCHES:
        for sector in SECTORS:
            data = sectors[sector]
            sector_events = [item for item in events if item["sector"] == sector]
            for event in sector_events:
                result = fixed_depth_fit(
                    data.time,
                    reductions[branch][sector]["flux"],
                    reductions[branch][sector]["error"],
                    event["midpoint_btjd"],
                    reductions[branch][sector]["valid"],
                )
                if result is None:
                    raise RuntimeError(
                        f"{branch} {event['physical_event_id']} fixed depth failed"
                    )
                event_depths.append({"branch": branch, **event, **result})
            result = sector_depth_fit(
                data, reductions[branch][sector], sector_events
            )
            if result is None:
                raise RuntimeError(f"{branch} S{sector} sector depth failed")
            sector_depths[branch][sector] = result
            sector_depth_rows.append(
                {
                    "branch": branch,
                    "sector": sector,
                    "event_count": result["event_count"],
                    "used_epochs": ";".join(str(value) for value in result["used_epochs"]),
                    "n_points": result["n_points"],
                    "n_in_transit": result["n_in_transit"],
                    "n_out_of_transit": result["n_out_of_transit"],
                    "depth_ppm": result["depth_ppm"],
                    "depth_error_ppm": result["depth_error_ppm"],
                    "significance": result["significance"],
                    "positive_at_least_3sigma": result[
                        "positive_at_least_3sigma"
                    ],
                    "reduced_chi2_formal_errors": result[
                        "reduced_chi2_formal_errors"
                    ],
                }
            )

    geometry = {}
    for branch in BRANCHES:
        frame = geometry_frame(sectors, reductions, events, branch)
        geometry[branch] = fit_geometry(frame, branch)
        parameter = geometry[branch]["parameters"]
        print(
            f"{branch}: rp/Rs={parameter['rp_rs']['value']:.7f} +/- "
            f"{parameter['rp_rs']['error']:.7f}; a/Rs={parameter['a_rs']['value']:.4f}; "
            f"b={parameter['impact_parameter']['value']:.4f}"
        )

    injection, injection_centers = run_injections(
        sectors, selected_cbv, pld_tuning
    )
    for branch in BRANCHES:
        print(
            f"{branch} injections: {injection[branch]['recovered_count']}/"
            f"{injection[branch]['trial_count']}, median |bias|="
            f"{injection[branch]['median_absolute_fractional_depth_recovery_bias']:.4%}"
        )

    cbv_tuning = {}
    for sector in SECTORS:
        source = faz3["cbv_selection"]["by_sector"][str(sector)]
        cbv_tuning[sector] = {
            "selection_source": relative(FAZ3_PATH),
            "selected_n_cbv": int(source["selected_n_cbv"]),
            "selected_predictive_rmse_ppm": float(
                source["selected_predictive_rmse_ppm"]
            ),
            "selected_mean_predictive_log_score": float(
                source["selected_mean_predictive_log_score"]
            ),
            "candidate_scores": source["candidate_scores"],
            "blocked_validation": source["blocked_validation"],
            "transit_points_used": False,
            "transit_depth_used": False,
            "finite": bool(np.isfinite(source["selected_predictive_rmse_ppm"])),
        }

    acceptance = {}
    for branch in BRANCHES:
        tuning = (
            cbv_tuning
            if branch == "sap_cbv"
            else pld_tuning
            if branch == "tpf_pld"
            else {}
        )
        acceptance[branch] = branch_acceptance(
            branch,
            reductions,
            sector_depths,
            geometry,
            injection[branch],
            tuning,
        )
    accepted = [branch for branch in BRANCHES if acceptance[branch]["accepted"]]
    geometry_comparison_result = geometry_comparison(geometry, accepted)
    independent_accepted = [branch for branch in accepted if branch != "pdcsap"]
    required_branches = "pdcsap" in accepted and bool(independent_accepted)
    if required_branches and geometry_comparison_result["shift_gate_pass"]:
        status = "PASS"
    elif (
        required_branches
        and not geometry_comparison_result["shift_gate_pass"]
        and geometry_comparison_result["between_reduction_systematic"]["propagated"]
    ):
        status = "CONDITIONAL_PASS"
    else:
        status = "FAIL"

    long_table, provenance, long_counts = build_long_table(
        sectors, reductions, pld_tuning
    )
    LONG_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_deterministic_gzip_csv(long_table, LONG_TABLE_PATH)
    sector_depth_frame = pd.DataFrame(sector_depth_rows)
    sector_depth_frame.to_csv(SECTOR_DEPTH_PATH, index=False, float_format="%.17g")

    branch_payload = {}
    for branch in BRANCHES:
        branch_payload[branch] = {
            "label": {
                "pdcsap": "raw SPOC PDCSAP, OOT-normalized, no second CROWDSAP",
                "sap_cbv": "raw SPOC SAP plus official SingleScale CBVs",
                "tpf_pipeline": "calibrated TPF FLUX summed over SPOC optimal aperture",
                "tpf_pld": "first-order PLD on the same SPOC optimal-aperture pixels",
            }[branch],
            "same_target_observations": True,
            "statistically_independent_of_other_branches": False,
            "per_sector_reduction": {
                str(sector): {
                    "valid_cadence_count": int(
                        reductions[branch][sector]["valid"].sum()
                    ),
                    "crowdsap": sectors[sector].crowdsap,
                    "flfrcsap_metadata_only": sectors[sector].flfrcsap,
                    "alignment": sectors[sector].alignment,
                    **reductions[branch][sector]["meta"],
                }
                for sector in SECTORS
            },
            "predictive_tuning": (
                {str(key): value for key, value in cbv_tuning.items()}
                if branch == "sap_cbv"
                else {str(key): value for key, value in pld_tuning.items()}
                if branch == "tpf_pld"
                else {
                    "applicable": False,
                    "reason": "fixed SPOC product/aperture; no data-selected reduction hyperparameter",
                }
            ),
            "sector_depths": {
                str(sector): sector_depths[branch][sector] for sector in SECTORS
            },
            "geometry": geometry[branch],
            "injection_screen": injection[branch],
            "acceptance": acceptance[branch],
        }

    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "phase": 4,
        "input_policy": {
            "active_local_120s_fits_only": True,
            "legacy_zip_inspected": False,
            "network_used": False,
            "git_used": False,
            "phase5_started": False,
        },
        "preregistered_acceptance": {
            "declared_before_result_sections": True,
            "branch_requirements": {
                "six_valid_sectors": True,
                "positive_depth_minimum_formal_sigma_each_sector": MIN_SECTOR_SIGNAL_SIGMA,
                "finite_geometry_covariance": True,
                "finite_predictive_tuning_where_applicable": True,
                "minimum_injection_trials_total": MIN_INJECTIONS_PER_BRANCH,
                "injections_per_sector": INJECTIONS_PER_SECTOR,
                "minimum_injection_recovery_rate": MIN_INJECTION_RECOVERY_RATE,
                "maximum_median_absolute_fractional_injected_depth_bias": MAX_MEDIAN_ABS_INJECTION_BIAS,
                "single_trial_recovery_absolute_fractional_bias_limit": MAX_RECOVERED_TRIAL_ABS_BIAS,
            },
            "overall_status": {
                "PASS": "PDCSAP and >=1 non-PDCSAP branch accepted; every accepted-branch geometry shift <=0.5 combined sigma",
                "CONDITIONAL_PASS": "required branches accepted but geometry shift exceeds 0.5 combined sigma; quantified between-reduction systematic propagated",
                "FAIL": "required branch/signal/injection/covariance/tuning gate fails or a geometry excess is not propagated",
            },
        },
        "inputs": {
            "checks": input_checks,
            "consumed": [
                relative(FAZ1_PATH),
                relative(FAZ2_PATH),
                relative(FAZ3_PATH),
                relative(FAZ3_INPUT_PATH),
                relative(OFFICIAL_PATH),
                relative(LEDGER_PATH),
            ],
            "ledger": {
                "row_count": len(ledger),
                "sha256": sha256_file(LEDGER_PATH),
            },
            "quality_mask": {
                "name": "lightkurve_default",
                "numeric_bitmask": QUALITY_MASK,
                "rule": "(QUALITY & 17087) == 0",
            },
            "events": {
                "used_event_count": len(events),
                "used_events": events,
                "gap_event_count": len(gaps),
                "gap_event_keys": [
                    {"sector": sector, "epoch": epoch} for sector, epoch in gaps
                ],
                "model_half_window_hours": 13.0,
            },
            "ephemeris": {
                "period_days_fixed": PERIOD_DAYS,
                "t0_btjd_fixed": T0_BTJD,
                "source": relative(OFFICIAL_PATH),
            },
            "phase3_selected_n_cbv": {
                str(key): value for key, value in selected_cbv.items()
            },
        },
        "correction_formulas": {
            "pdcsap": {
                "formula": "f = PDCSAP_FLUX / median_OOT(PDCSAP_FLUX)",
                "error": "sigma_f = PDCSAP_FLUX_ERR / median_OOT(PDCSAP_FLUX)",
                "additional_crowdsap_applications": 0,
                "reason": "SPOC PDCSAP already includes the nominal crowding treatment",
            },
            "sap_cbv": {
                "formula": "q=SAP/N; fit q-1 = beta0 + sum(beta_k z(CBV_k)) on OOT only; g=(q-sum(beta_k z_k))/median_OOT(q-sum(beta_k z_k)); f=1+(g-1)/CROWDSAP",
                "error": "sigma_f=SAP_FLUX_ERR/N/median_OOT(g_pre)/CROWDSAP; coefficient uncertainty is not included in this formal propagated error",
                "additional_crowdsap_applications": 1,
                "cbv_alignment_key": "CADENCENO",
            },
            "tpf_pipeline": {
                "formula": "S=sum_optimal_pixels(FLUX); sigma_S=sqrt(sum_optimal_pixels(FLUX_ERR^2)); q=S/median_OOT(S); f=1+(q-1)/CROWDSAP",
                "additional_crowdsap_applications": 1,
                "aperture": "APERTURE bit 2 (SPOC optimal aperture)",
            },
            "tpf_pld": {
                "formula": "x_j=pixel_j/sum_pixels; choose OOT PCA dimension/ridge by blocked prediction; fit q-1=beta0+sum(beta_k PC_k) on OOT only; g=(q-sum(beta_k PC_k))/median_OOT(g_pre); f=1+(g-1)/CROWDSAP",
                "error": "quadrature pixel FLUX_ERR propagated through normalization and CROWDSAP; PLD coefficient uncertainty is not included in this formal error",
                "additional_crowdsap_applications": 1,
                "aperture": "exactly the same APERTURE-bit-2 pixels and cadences as tpf_pipeline",
            },
            "flfrcsap": {
                "applied": False,
                "role": "metadata only; multiplicative throughput cancels under relative OOT normalization",
            },
            "timestamps": "native FITS BTJD, never binned or resampled",
            "exposure_integration": {
                "seconds": EXPOSURE_SECONDS,
                "batman_supersample_factor": SUPERSAMPLE_FACTOR,
            },
        },
        "fixed_depth_estimator": {
            "same_for_every_branch_event_and_sector": True,
            "in_transit": "abs(t-tc) <= 0.5*T14",
            "out_of_transit": "1.2*T14 <= abs(t-tc) <= 2.5*T14",
            "event_model": "weighted intercept + linear time - box depth",
            "sector_model": "shared box depth with separate intercept/slope for each used event",
            "t14_hours_fixed_for_estimator": T14_HOURS,
            "formal_errors": "inverse supplied-error weighted design information; no residual inflation",
        },
        "injection_design": {
            "purpose": "bounded Phase-4 reduction-selection screen, not the Phase-15 campaign",
            "deterministic": True,
            "random_seed": None,
            "centers_by_sector_btjd": injection_centers,
            "configurations_rp_rs_impact_parameter": [
                {"rp_rs": rp, "impact_parameter": impact}
                for rp, impact in INJECTION_CONFIGS
            ],
            "synthetic_period_days_for_local_shape": PERIOD_DAYS,
            "single_event_rule": "neighboring periodic model copies are set to unity",
            "injection_exclusion_half_width_days": INJECTION_EXCLUSION_HALF_WIDTH_DAYS,
            "injection_exclusion_rule": "injected windows excluded from normalization, CBV coefficient training, and PLD coefficient training",
            "raw_quality_gaps_timestamps_and_errors_modified": False,
            "depth_recovery": "incremental injected-minus-sham fixed-window depth, so the same real-noise realization cancels",
            "tpf_injection": "additive target signal distributed over the same optimal pixels in proportion to their OOT median calibrated flux",
        },
        "provenance_identifiers": provenance,
        "branches": branch_payload,
        "event_depths": event_depths,
        "accepted_branch_geometry_comparison": geometry_comparison_result,
        "gate": {
            "checks": {
                "pdcsap_accepted": acceptance["pdcsap"]["accepted"],
                "at_least_one_non_pdcsap_branch_accepted": bool(independent_accepted),
                "required_signal_injection_tuning_covariance_gates": required_branches,
                "accepted_geometry_shifts_at_most_0_5_combined_sigma": geometry_comparison_result[
                    "shift_gate_pass"
                ],
                "between_reduction_systematic_propagated_if_needed": bool(
                    geometry_comparison_result["shift_gate_pass"]
                    or geometry_comparison_result["between_reduction_systematic"][
                        "propagated"
                    ]
                ),
            },
            "accepted_branches": accepted,
            "rejected_branches": [
                branch for branch in BRANCHES if branch not in accepted
            ],
            "status": status,
            "gate_pass": status == "PASS",
            "conditional_pass": status == "CONDITIONAL_PASS",
            "phase5_may_begin": status in ("PASS", "CONDITIONAL_PASS"),
            "phase5_started": False,
            "conditional_justification": (
                "All required branch, six-sector signal, injection, tuning, and covariance gates pass; accepted-reduction geometry dispersion is explicitly added in quadrature."
                if status == "CONDITIONAL_PASS"
                else None
            ),
        },
        "artifacts": {
            "long_table": {
                "relative_path": relative(LONG_TABLE_PATH),
                "row_count": len(long_table),
                "row_count_by_branch_sector": long_counts,
                "size_bytes": LONG_TABLE_PATH.stat().st_size,
                "sha256": sha256_file(LONG_TABLE_PATH),
                "columns": list(long_table.columns),
            },
            "sector_depths": {
                "relative_path": relative(SECTOR_DEPTH_PATH),
                "row_count": len(sector_depth_frame),
                "size_bytes": SECTOR_DEPTH_PATH.stat().st_size,
                "sha256": sha256_file(SECTOR_DEPTH_PATH),
            },
        },
        "gate_status": status,
        "gate_pass": status == "PASS",
    }
    OUTPUT_PATH.write_text(
        json.dumps(json_ready(payload), indent=2) + "\n", encoding="ascii"
    )
    print(f"PHASE 4 GATE: {status}")
    print(f"Wrote {LONG_TABLE_PATH}")
    print(f"Wrote {SECTOR_DEPTH_PATH}")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
