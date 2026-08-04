"""Faz 2: derive and classify every physical transit event from local cadences.

The physical event set is derived from the finite-time bounds in the Faz 1
cadence ledgers plus the pre-defined +/-13 hour analysis-window overlap.  The
120 s reference-membership flag determines coverage and use; raw ledger rows
provide quality, background, pointing, and centroid diagnostics.  Flux and
depth columns are not read for event classification.
"""

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
FAZ1_INVENTORY = ROOT / "outputs" / "faz1_product_inventory.json"
OFFICIAL_METADATA = ROOT / "data" / "official_toi_metadata.json"
EVENT_DEPTHS = ROOT / "outputs" / "toi3492_120s_event_depths.csv"
OUTPUT_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"

BJD_ZEROPOINT = 2457000.0
ANALYSIS_HALF_WINDOW_HOURS = 13.0
MIN_T14_COVERAGE = 0.80
MIN_INGRESS_OR_EGRESS_COVERAGE = 0.80
BASELINE_INNER_T14 = 1.2
BASELINE_OUTER_T14 = 2.5
GAP_CADENCE_MULTIPLIER = 1.5

# T14 is the official NASA Exoplanet Archive TOI duration, frozen in
# data/official_toi_metadata.json (retrieved 2026-07-10).  The ingress duration
# is the machine-readable SPOC S1-S96, TCE 1 value in
# outputs/spoc_dv_transit_metrics.csv.  Neither constant was selected from the
# local event depths used for reconciliation below.
OFFICIAL_T14_HOURS = 5.296858
SPOC_S1_S96_INGRESS_HOURS = 0.5593209107436028

EXPECTED_EVENT_EPOCHS = {
    37: (0, 1, 2),
    63: (76, 77, 78),
    64: (79, 80, 81),
    90: (156, 157, 158),
    99: (188, 189, 190),
    100: (191, 192, 193),
}
EXPECTED_GAP_EVENTS = {(37, 2), (99, 189)}

LEDGER_REQUIRED_COLUMNS = {
    "sector",
    "cadence_seconds",
    "product_id",
    "product_path",
    "product_sha256",
    "tpf_sha256",
    "time_btjd",
    "cadenceno",
    "sap_bkg",
    "sap_bkg_err",
    "quality",
    "mom_centr1",
    "mom_centr1_err",
    "mom_centr2",
    "mom_centr2_err",
    "pos_corr1",
    "pos_corr2",
    "quality_strict_zero_pass",
    "quality_default_17087_pass",
    "quality_hard_24319_pass",
    "in_current_reference",
}

NUMERIC_LEDGER_COLUMNS = (
    "time_btjd",
    "sap_bkg",
    "sap_bkg_err",
    "mom_centr1",
    "mom_centr1_err",
    "mom_centr2",
    "mom_centr2_err",
    "pos_corr1",
    "pos_corr2",
)
BOOLEAN_LEDGER_COLUMNS = (
    "quality_strict_zero_pass",
    "quality_default_17087_pass",
    "quality_hard_24319_pass",
    "in_current_reference",
)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_bool(value):
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"Invalid ledger boolean: {value!r}")


def load_inputs():
    with FAZ1_INVENTORY.open("r", encoding="utf-8") as handle:
        faz1 = json.load(handle)
    if not faz1.get("gate_pass"):
        raise RuntimeError("Faz 1 gate must pass before Faz 2")
    if faz1["input_policy"].get("legacy_zip_inspected") is not False:
        raise RuntimeError("Faz 1 input policy does not exclude legacy ZIP inputs")

    with OFFICIAL_METADATA.open("r", encoding="utf-8") as handle:
        official = json.load(handle)
    ephemeris = official["ephemeris"]
    period_days = float(ephemeris["period_days"])
    t0_btjd = float(ephemeris["transit_midpoint_bjd"]) - BJD_ZEROPOINT
    duration_hours = float(ephemeris["duration_hours"])
    if abs(duration_hours - OFFICIAL_T14_HOURS) >= 1e-12:
        raise ValueError("Frozen T14 no longer matches official_toi_metadata.json")

    return faz1, {
        "period_days": period_days,
        "t0_btjd": t0_btjd,
        "t0_bjd_tdb": float(ephemeris["transit_midpoint_bjd"]),
        "t14_hours": OFFICIAL_T14_HOURS,
        "t14_days": OFFICIAL_T14_HOURS / 24.0,
        "ingress_hours": SPOC_S1_S96_INGRESS_HOURS,
        "ingress_days": SPOC_S1_S96_INGRESS_HOURS / 24.0,
    }


def load_ledgers(faz1):
    raw_groups = defaultdict(lambda: defaultdict(list))
    group_sources = {}
    ledger_provenance = {}

    for cadence in (120, 20):
        declared = faz1["cadence_ledgers"][str(cadence)]
        path = ROOT / declared["relative_path"]
        actual_size = path.stat().st_size
        actual_sha256 = sha256_file(path)
        if actual_size != declared["size_bytes"] or actual_sha256 != declared["sha256"]:
            raise ValueError(f"Faz 1 ledger hash/size mismatch: {path}")

        row_count = 0
        with gzip.open(path, mode="rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = LEDGER_REQUIRED_COLUMNS - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Missing Faz 2 ledger columns in {path}: {sorted(missing)}")
            for row in reader:
                row_cadence = int(row["cadence_seconds"])
                if row_cadence != cadence:
                    raise ValueError(f"Mixed cadence ledger row in {path}: {row_cadence}")
                sector = int(row["sector"])
                key = (sector, cadence)
                group = raw_groups[key]
                for name in NUMERIC_LEDGER_COLUMNS:
                    group[name].append(float(row[name]))
                group["cadenceno"].append(int(row["cadenceno"]))
                group["quality"].append(int(row["quality"]))
                for name in BOOLEAN_LEDGER_COLUMNS:
                    group[name].append(parse_bool(row[name]))

                source = (
                    row["product_id"],
                    row["product_path"],
                    row["product_sha256"],
                    row["tpf_sha256"],
                )
                if key in group_sources and group_sources[key] != source:
                    raise ValueError(f"Multiple product provenances in ledger group {key}")
                group_sources[key] = source
                row_count += 1

        if row_count != int(declared["row_count"]):
            raise ValueError(f"Ledger row-count mismatch: {path}")
        ledger_provenance[str(cadence)] = {
            "relative_path": declared["relative_path"],
            "size_bytes": actual_size,
            "sha256": actual_sha256,
            "row_count": row_count,
            "hash_verified_against_faz1": True,
        }

    groups = {}
    for key, values in raw_groups.items():
        source = group_sources[key]
        group = {
            name: np.asarray(values[name], dtype=np.float64)
            for name in NUMERIC_LEDGER_COLUMNS
        }
        group["cadenceno"] = np.asarray(values["cadenceno"], dtype=np.int64)
        group["quality"] = np.asarray(values["quality"], dtype=np.int64)
        for name in BOOLEAN_LEDGER_COLUMNS:
            group[name] = np.asarray(values[name], dtype=bool)
        group["source"] = {
            "product_id": source[0],
            "product_path": source[1],
            "product_sha256": source[2],
            "tpf_sha256": source[3],
        }
        group["row_count"] = int(group["time_btjd"].size)
        groups[key] = group

    expected_rows = {
        (item["sector"], item["cadence_seconds"]): item
        for item in faz1["cadence_ledger_summary"]
    }
    if set(groups) != set(expected_rows):
        raise ValueError("Ledger sector/cadence keys differ from Faz 1 summary")
    for key, group in groups.items():
        expected = expected_rows[key]
        if group["row_count"] != expected["raw_row_count"]:
            raise ValueError(f"Raw ledger count mismatch for {key}")
        if int(group["in_current_reference"].sum()) != expected["reference_row_count"]:
            raise ValueError(f"Reference ledger count mismatch for {key}")
        if np.any(
            group["in_current_reference"] & ~group["quality_default_17087_pass"]
        ):
            raise ValueError(f"Reference includes default-quality rejected cadence for {key}")

    # The ledgers carry these LC hashes.  Re-hash the nine active local LC FITS
    # so Faz 2 cannot silently operate on a ledger detached from its raw source.
    active_lc_checks = []
    for key in sorted(groups):
        source = groups[key]["source"]
        raw_path = (ROOT / source["product_path"]).resolve()
        raw_path.relative_to((ROOT / "data" / "asteroseismology" / "raw").resolve())
        actual_sha256 = sha256_file(raw_path)
        match = actual_sha256 == source["product_sha256"]
        active_lc_checks.append(
            {
                "sector": key[0],
                "cadence_seconds": key[1],
                "relative_path": source["product_path"],
                "sha256": actual_sha256,
                "matches_ledger": match,
            }
        )
        if not match:
            raise ValueError(f"Active raw LC differs from ledger source: {raw_path}")
    return groups, ledger_provenance, active_lc_checks


def derive_physical_events(groups, ephemeris):
    half_window_days = ANALYSIS_HALF_WINDOW_HOURS / 24.0
    events = []
    derivation = []
    sectors_120s = sorted(sector for sector, cadence in groups if cadence == 120)
    for sector in sectors_120s:
        group = groups[(sector, 120)]
        finite_times = group["time_btjd"][np.isfinite(group["time_btjd"])]
        if finite_times.size == 0:
            raise ValueError(f"No finite 120 s times for sector {sector}")
        start = float(np.min(finite_times))
        stop = float(np.max(finite_times))
        first_epoch = math.ceil(
            (start - half_window_days - ephemeris["t0_btjd"])
            / ephemeris["period_days"]
        )
        last_epoch = math.floor(
            (stop + half_window_days - ephemeris["t0_btjd"])
            / ephemeris["period_days"]
        )
        epochs = list(range(first_epoch, last_epoch + 1))
        derivation.append(
            {
                "sector": sector,
                "finite_raw_120s_time_min_btjd": start,
                "finite_raw_120s_time_max_btjd": stop,
                "analysis_half_window_hours": ANALYSIS_HALF_WINDOW_HOURS,
                "overlapping_epochs": epochs,
            }
        )
        for epoch in epochs:
            events.append(
                {
                    "sector": sector,
                    "epoch": epoch,
                    "predicted_midpoint_btjd": (
                        ephemeris["t0_btjd"] + epoch * ephemeris["period_days"]
                    ),
                }
            )
    return events, derivation


def interval_coverage(times, lower, upper, cadence_days):
    times = np.sort(np.asarray(times, dtype=np.float64))
    center_mask = (times >= lower) & (times <= upper)
    cadence_count = int(center_mask.sum())
    overlap_mask = (times + cadence_days / 2.0 > lower) & (
        times - cadence_days / 2.0 < upper
    )
    overlap_times = times[overlap_mask]
    intervals = []
    for value in overlap_times:
        start = max(lower, float(value - cadence_days / 2.0))
        stop = min(upper, float(value + cadence_days / 2.0))
        if stop > start:
            intervals.append((start, stop))
    covered = 0.0
    if intervals:
        current_start, current_stop = intervals[0]
        for start, stop in intervals[1:]:
            if start <= current_stop:
                current_stop = max(current_stop, stop)
            else:
                covered += current_stop - current_start
                current_start, current_stop = start, stop
        covered += current_stop - current_start
    width = upper - lower
    fraction = min(1.0, max(0.0, covered / width)) if width > 0.0 else 0.0
    return {
        "start_btjd": lower,
        "stop_btjd": upper,
        "duration_days": width,
        "cadence_count": cadence_count,
        "nominal_expected_cadence_equivalent": width / cadence_days,
        "covered_duration_days": covered,
        "coverage_fraction": fraction,
    }


def finite_summary(values):
    values = np.asarray(values, dtype=np.float64)
    finite = values[np.isfinite(values)]
    result = {
        "row_count": int(values.size),
        "finite_count": int(finite.size),
        "nan_count": int(np.isnan(values).sum()),
        "nonfinite_count": int((~np.isfinite(values)).sum()),
        "minimum": None,
        "maximum": None,
        "median": None,
        "mean": None,
        "standard_deviation": None,
    }
    if finite.size:
        result.update(
            {
                "minimum": float(np.min(finite)),
                "maximum": float(np.max(finite)),
                "median": float(np.median(finite)),
                "mean": float(np.mean(finite)),
                "standard_deviation": float(np.std(finite)),
            }
        )
    return result


def quality_summary(group, mask):
    quality = group["quality"][mask]
    if quality.size:
        quality_or = int(np.bitwise_or.reduce(quality))
        max_bit = max(quality_or.bit_length(), 1)
    else:
        quality_or = 0
        max_bit = 1
    bit_counts = []
    for index in range(max_bit):
        bit = 1 << index
        count = int(np.count_nonzero((quality & bit) != 0))
        if count:
            bit_counts.append({"bit_index": index, "bit_value": bit, "cadence_count": count})
    return {
        "cadence_count": int(quality.size),
        "quality_zero_count": int(np.count_nonzero(quality == 0)),
        "quality_nonzero_count": int(np.count_nonzero(quality != 0)),
        "quality_or": quality_or,
        "set_bit_counts": bit_counts,
        "strict_zero_pass_count": int(group["quality_strict_zero_pass"][mask].sum()),
        "default_17087_pass_count": int(
            group["quality_default_17087_pass"][mask].sum()
        ),
        "hard_24319_pass_count": int(group["quality_hard_24319_pass"][mask].sum()),
    }


def systematics_summary(group, mask):
    return {
        "background": {
            "sap_bkg_e_per_s": finite_summary(group["sap_bkg"][mask]),
            "sap_bkg_err_e_per_s": finite_summary(group["sap_bkg_err"][mask]),
        },
        "pointing": {
            "pos_corr1_pixels": finite_summary(group["pos_corr1"][mask]),
            "pos_corr2_pixels": finite_summary(group["pos_corr2"][mask]),
        },
        "moment_centroid": {
            "mom_centr1_pixels": finite_summary(group["mom_centr1"][mask]),
            "mom_centr1_err_pixels": finite_summary(group["mom_centr1_err"][mask]),
            "mom_centr2_pixels": finite_summary(group["mom_centr2"][mask]),
            "mom_centr2_err_pixels": finite_summary(group["mom_centr2_err"][mask]),
        },
    }


def distance_to_interval(value, interval):
    start, stop = interval
    if start <= value <= stop:
        return 0.0
    return min(abs(value - start), abs(value - stop))


def nearest_cadence_distance(times, value):
    if times.size == 0:
        return None
    return float(np.min(np.abs(times - value)))


def gap_summary(selected_times, analysis_start, analysis_stop, midpoint, contacts, cadence_days):
    selected_times = np.sort(np.asarray(selected_times, dtype=np.float64))
    nearby = selected_times[
        (selected_times >= analysis_start - cadence_days)
        & (selected_times <= analysis_stop + cadence_days)
    ]
    gaps = []
    threshold = GAP_CADENCE_MULTIPLIER * cadence_days
    if nearby.size == 0:
        gaps.append((analysis_start, analysis_stop))
    else:
        leading_stop = float(nearby[0] - cadence_days / 2.0)
        if leading_stop - analysis_start > threshold:
            gaps.append((analysis_start, min(analysis_stop, leading_stop)))
        for left, right in zip(nearby[:-1], nearby[1:]):
            if right - left > threshold:
                start = max(analysis_start, float(left + cadence_days / 2.0))
                stop = min(analysis_stop, float(right - cadence_days / 2.0))
                if stop > start:
                    gaps.append((start, stop))
        trailing_start = float(nearby[-1] + cadence_days / 2.0)
        if analysis_stop - trailing_start > threshold:
            gaps.append((max(analysis_start, trailing_start), analysis_stop))

    nearest = None
    if gaps:
        nearest_interval = min(gaps, key=lambda item: distance_to_interval(midpoint, item))
        nearest = {
            "start_btjd": nearest_interval[0],
            "stop_btjd": nearest_interval[1],
            "duration_days": nearest_interval[1] - nearest_interval[0],
            "distance_from_midpoint_days": distance_to_interval(midpoint, nearest_interval),
            "distance_from_midpoint_hours": 24.0
            * distance_to_interval(midpoint, nearest_interval),
        }
    left_distances = [midpoint - stop for start, stop in gaps if stop <= midpoint]
    right_distances = [start - midpoint for start, stop in gaps if start >= midpoint]
    contact_names = ("first_contact", "second_contact", "third_contact", "fourth_contact")
    return {
        "significant_gap_threshold_seconds": threshold * 86400.0,
        "significant_gap_count_in_analysis_window": len(gaps),
        "maximum_gap_duration_days": (
            max(stop - start for start, stop in gaps) if gaps else None
        ),
        "nearest_gap": nearest,
        "nearest_gap_before_midpoint_distance_days": min(left_distances)
        if left_distances
        else None,
        "nearest_gap_after_midpoint_distance_days": min(right_distances)
        if right_distances
        else None,
        "nearest_cadence_distances_days": {
            "midpoint": nearest_cadence_distance(selected_times, midpoint),
            **{
                name: nearest_cadence_distance(selected_times, value)
                for name, value in zip(contact_names, contacts)
            },
        },
    }


def build_coverage(group, cadence_seconds, midpoint, ephemeris):
    cadence_days = cadence_seconds / 86400.0
    t14 = ephemeris["t14_days"]
    ingress = ephemeris["ingress_days"]
    half_analysis = ANALYSIS_HALF_WINDOW_HOURS / 24.0
    contacts = (
        midpoint - t14 / 2.0,
        midpoint - t14 / 2.0 + ingress,
        midpoint + t14 / 2.0 - ingress,
        midpoint + t14 / 2.0,
    )
    intervals = {
        "analysis_window": (midpoint - half_analysis, midpoint + half_analysis),
        "t14": (contacts[0], contacts[3]),
        "ingress": (contacts[0], contacts[1]),
        "egress": (contacts[2], contacts[3]),
        "left_out_of_transit_baseline": (
            midpoint - BASELINE_OUTER_T14 * t14,
            midpoint - BASELINE_INNER_T14 * t14,
        ),
        "right_out_of_transit_baseline": (
            midpoint + BASELINE_INNER_T14 * t14,
            midpoint + BASELINE_OUTER_T14 * t14,
        ),
    }
    times = group["time_btjd"]
    finite_time = np.isfinite(times)
    selected_mask = finite_time & group["in_current_reference"]
    selected_times = times[selected_mask]
    regions = {
        name: interval_coverage(selected_times, lower, upper, cadence_days)
        for name, (lower, upper) in intervals.items()
    }
    analysis_mask = finite_time & (times >= intervals["analysis_window"][0]) & (
        times <= intervals["analysis_window"][1]
    )
    t14_mask = finite_time & (times >= intervals["t14"][0]) & (
        times <= intervals["t14"][1]
    )
    finite_sector_times = times[finite_time]
    return {
        "cadence_seconds": cadence_seconds,
        "source": group["source"],
        "sector_cadences": {
            "raw_row_count": group["row_count"],
            "finite_time_count": int(finite_time.sum()),
            "reference_included_count": int(selected_mask.sum()),
            "finite_time_min_btjd": float(np.min(finite_sector_times)),
            "finite_time_max_btjd": float(np.max(finite_sector_times)),
        },
        "contact_times_btjd": {
            "first_contact": contacts[0],
            "second_contact": contacts[1],
            "third_contact": contacts[2],
            "fourth_contact": contacts[3],
        },
        "regions": regions,
        "quality_bit_summaries": {
            "analysis_window_raw_cadences": quality_summary(group, analysis_mask),
            "t14_raw_cadences": quality_summary(group, t14_mask),
        },
        "systematics_summaries": {
            "analysis_window_raw_cadences": systematics_summary(group, analysis_mask),
            "t14_raw_cadences": systematics_summary(group, t14_mask),
        },
        "nearest_gap_distances": gap_summary(
            selected_times,
            intervals["analysis_window"][0],
            intervals["analysis_window"][1],
            midpoint,
            contacts,
            cadence_days,
        ),
    }


def classify_coverage(coverage):
    regions = coverage["regions"]
    t14_fraction = regions["t14"]["coverage_fraction"]
    ingress_fraction = regions["ingress"]["coverage_fraction"]
    egress_fraction = regions["egress"]["coverage_fraction"]
    limb_fraction = max(ingress_fraction, egress_fraction)
    if (
        t14_fraction >= MIN_T14_COVERAGE
        and limb_fraction >= MIN_INGRESS_OR_EGRESS_COVERAGE
    ):
        return "FULL", "t14_and_ingress_or_egress_meet_0.8"
    if limb_fraction >= MIN_INGRESS_OR_EGRESS_COVERAGE:
        return "PARTIAL_OK", "ingress_or_egress_meets_0.8_but_t14_does_not"
    if regions["t14"]["cadence_count"] > 0:
        return "PARTIAL_POOR", "some_t14_cadences_but_coverage_gates_fail"
    return "GAP", "no_reference_included_120s_cadence_in_t14"


def load_used_event_keys():
    keys = []
    with EVENT_DEPTHS.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"sector", "epoch"}.issubset(reader.fieldnames or []):
            raise ValueError(f"Event-depth key columns are absent: {EVENT_DEPTHS}")
        for row in reader:
            # Deliberately read only identifiers; depth and depth-error columns
            # have no role in event classification.
            keys.append((int(row["sector"]), int(row["epoch"])))
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate physical event keys in event-depth table")
    return set(keys), {
        "relative_path": EVENT_DEPTHS.relative_to(ROOT).as_posix(),
        "size_bytes": EVENT_DEPTHS.stat().st_size,
        "sha256": sha256_file(EVENT_DEPTHS),
        "row_count": len(keys),
        "columns_read": ["sector", "epoch"],
        "depth_columns_read_for_classification": False,
    }


def build_inventory():
    faz1, ephemeris = load_inputs()
    groups, ledger_provenance, active_lc_checks = load_ledgers(faz1)
    derived_events, derivation = derive_physical_events(groups, ephemeris)
    event_depth_keys, event_depth_provenance = load_used_event_keys()

    events = []
    for derived in derived_events:
        sector = derived["sector"]
        epoch = derived["epoch"]
        midpoint = derived["predicted_midpoint_btjd"]
        coverage_120s = build_coverage(groups[(sector, 120)], 120, midpoint, ephemeris)
        coverage_20s = (
            build_coverage(groups[(sector, 20)], 20, midpoint, ephemeris)
            if (sector, 20) in groups
            else None
        )
        classification, classification_reason = classify_coverage(coverage_120s)
        used = classification == "FULL"
        exclusion_reason = None if used else classification_reason
        events.append(
            {
                "physical_event_id": f"S{sector:03d}-E{epoch:03d}",
                "sector": sector,
                "epoch": epoch,
                "predicted_midpoint_btjd": midpoint,
                "predicted_midpoint_bjd_tdb": midpoint + BJD_ZEROPOINT,
                "analysis_window_start_btjd": midpoint
                - ANALYSIS_HALF_WINDOW_HOURS / 24.0,
                "analysis_window_stop_btjd": midpoint
                + ANALYSIS_HALF_WINDOW_HOURS / 24.0,
                "coverage_120s": coverage_120s,
                "coverage_20s": coverage_20s,
                "classification": classification,
                "depth_blind_classification_reason": classification_reason,
                "used": used,
                "exclusion_reason": exclusion_reason,
            }
        )

    event_keys = {(item["sector"], item["epoch"]) for item in events}
    expected_keys = {
        (sector, epoch)
        for sector, epochs in EXPECTED_EVENT_EPOCHS.items()
        for epoch in epochs
    }
    used_keys = {(item["sector"], item["epoch"]) for item in events if item["used"]}
    class_counts = Counter(item["classification"] for item in events)
    gap_keys = {
        (item["sector"], item["epoch"])
        for item in events
        if item["classification"] == "GAP"
    }
    full_events = [item for item in events if item["classification"] == "FULL"]
    min_full_t14 = min(
        item["coverage_120s"]["regions"]["t14"]["coverage_fraction"]
        for item in full_events
    )
    min_full_ingress_or_egress = min(
        max(
            item["coverage_120s"]["regions"]["ingress"]["coverage_fraction"],
            item["coverage_120s"]["regions"]["egress"]["coverage_fraction"],
        )
        for item in full_events
    )
    checks = {
        "faz1_gate_pass": faz1["gate_pass"] is True,
        "active_local_lc_hashes_match_ledgers": all(
            item["matches_ledger"] for item in active_lc_checks
        ),
        "exactly_18_physical_events": len(events) == 18,
        "all_physical_event_keys_unique": len(events) == len(event_keys),
        "derived_event_epochs_match_expected": event_keys == expected_keys,
        "exactly_16_full": class_counts.get("FULL", 0) == 16,
        "exactly_2_gap": class_counts.get("GAP", 0) == 2,
        "no_partial_events": class_counts.get("PARTIAL_OK", 0) == 0
        and class_counts.get("PARTIAL_POOR", 0) == 0,
        "explicit_gap_set_matches": gap_keys == EXPECTED_GAP_EVENTS,
        "all_full_t14_coverage_at_least_0.8": min_full_t14 >= MIN_T14_COVERAGE,
        "all_full_ingress_or_egress_at_least_0.8": min_full_ingress_or_egress
        >= MIN_INGRESS_OR_EGRESS_COVERAGE,
        "exactly_16_used": len(used_keys) == 16,
        "used_events_are_full_only": all(
            item["used"] == (item["classification"] == "FULL") for item in events
        ),
        "used_event_set_matches_event_depth_table": used_keys == event_depth_keys,
        "20s_is_optional_subobject_not_physical_event_duplication": len(events) == 18
        and sum(item["coverage_20s"] is not None for item in events) == 9,
    }
    gate_pass = all(checks.values())
    expected_epoch_json = {
        str(sector): list(epochs) for sector, epochs in EXPECTED_EVENT_EPOCHS.items()
    }
    return {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input_policy": {
            "cadence_source": "Faz 1 ledgers generated from active local raw LC FITS",
            "legacy_zip_inspected": False,
            "network_used": False,
            "hard_coded_sector_dates_used": False,
            "event_depth_values_inspected_for_classification": False,
            "classification_cadence": "120s reference-included rows",
            "20s_role": "same-pixel optional diagnostic subobject; never a second physical event",
        },
        "provenance": {
            "faz1_inventory": FAZ1_INVENTORY.relative_to(ROOT).as_posix(),
            "cadence_ledgers": ledger_provenance,
            "active_local_lc_fits": active_lc_checks,
            "used_event_reconciliation": event_depth_provenance,
        },
        "ephemeris_and_windows": {
            **ephemeris,
            "time_system": "BTJD = BJD_TDB - 2457000.0",
            "period_and_t0_provenance": OFFICIAL_METADATA.relative_to(ROOT).as_posix(),
            "t14_provenance": (
                "NASA Exoplanet Archive TOI duration frozen in "
                "data/official_toi_metadata.json; retrieved 2026-07-10"
            ),
            "ingress_provenance": (
                "SPOC S1-S96 TCE 1 INDUR in outputs/spoc_dv_transit_metrics.csv; "
                "product relation_to_official=official_period"
            ),
            "analysis_half_window_hours": ANALYSIS_HALF_WINDOW_HOURS,
            "baseline_proxy_t14_multipliers": [BASELINE_INNER_T14, BASELINE_OUTER_T14],
            "minimum_t14_coverage": MIN_T14_COVERAGE,
            "minimum_ingress_or_egress_coverage": MIN_INGRESS_OR_EGRESS_COVERAGE,
            "classification_is_depth_blind": True,
        },
        "event_derivation_from_actual_120s_bounds": derivation,
        "expected_epochs_gate": expected_epoch_json,
        "events": events,
        "summary": {
            "physical_event_count": len(events),
            "unique_physical_event_count": len(event_keys),
            "class_counts": {
                name: int(class_counts.get(name, 0))
                for name in ("FULL", "PARTIAL_OK", "PARTIAL_POOR", "GAP")
            },
            "used_event_count": len(used_keys),
            "excluded_event_count": len(events) - len(used_keys),
            "events_with_optional_20s_coverage": sum(
                item["coverage_20s"] is not None for item in events
            ),
            "minimum_full_t14_coverage": min_full_t14,
            "minimum_full_ingress_or_egress_coverage": min_full_ingress_or_egress,
            "used_event_keys": [
                {"sector": sector, "epoch": epoch} for sector, epoch in sorted(used_keys)
            ],
            "gap_event_keys": [
                {"sector": sector, "epoch": epoch} for sector, epoch in sorted(gap_keys)
            ],
        },
        "gate": {
            "checks": checks,
            "gate_pass": gate_pass,
        },
        "gate_pass": gate_pass,
    }


def main():
    result = build_inventory()
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")

    summary = result["summary"]
    print("FAZ 2: physical transit-event inventory from actual local cadences")
    print(
        f"Events: {summary['physical_event_count']} physical; "
        f"FULL={summary['class_counts']['FULL']}, GAP={summary['class_counts']['GAP']}, "
        f"used={summary['used_event_count']}"
    )
    for event in result["events"]:
        regions = event["coverage_120s"]["regions"]
        print(
            f"S{event['sector']} E{event['epoch']}: {event['classification']} "
            f"T14={regions['t14']['coverage_fraction']:.6f}, "
            f"ingress={regions['ingress']['coverage_fraction']:.6f}, "
            f"egress={regions['egress']['coverage_fraction']:.6f}, "
            f"used={event['used']}"
        )
    print(f"FAZ 2 GATE: {'PASS' if result['gate_pass'] else 'FAIL'}")
    print(f"Output: {OUTPUT_PATH.relative_to(ROOT).as_posix()}")
    if not result["gate_pass"]:
        failed = [name for name, passed in result["gate"]["checks"].items() if not passed]
        print(f"Failed checks: {', '.join(failed)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
