import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from astropy.io import fits


ROOT = Path(__file__).resolve().parents[1]

LC_REQUIRED_COLUMNS = {
    "TIME",
    "TIMECORR",
    "CADENCENO",
    "SAP_FLUX",
    "SAP_FLUX_ERR",
    "SAP_BKG",
    "SAP_BKG_ERR",
    "PDCSAP_FLUX",
    "PDCSAP_FLUX_ERR",
    "QUALITY",
    "PSF_CENTR1",
    "PSF_CENTR1_ERR",
    "PSF_CENTR2",
    "PSF_CENTR2_ERR",
    "MOM_CENTR1",
    "MOM_CENTR1_ERR",
    "MOM_CENTR2",
    "MOM_CENTR2_ERR",
    "POS_CORR1",
    "POS_CORR2",
}
TPF_REQUIRED_COLUMNS = {
    "TIME",
    "TIMECORR",
    "CADENCENO",
    "RAW_CNTS",
    "FLUX",
    "FLUX_ERR",
    "FLUX_BKG",
    "FLUX_BKG_ERR",
    "QUALITY",
    "POS_CORR1",
    "POS_CORR2",
}
REASONS = {
    "invalid_time",
    "invalid_pdcsap_flux",
    "nonpositive_pdcsap_flux",
    "quality_default_reject",
    "post_quality_clip_or_filter",
    "included_reference",
}
EXPECTED_EPOCHS = {
    37: [0, 1, 2],
    63: [76, 77, 78],
    64: [79, 80, 81],
    90: [156, 157, 158],
    99: [188, 189, 190],
    100: [191, 192, 193],
}


def load_json(relative_path):
    with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_faz1_exact_products_schema_hashes_pairs_and_apertures():
    inventory = load_json("outputs/faz1_product_inventory.json")
    assert inventory["gate_pass"] is True
    assert inventory["gate"]["gate_pass"] is True
    assert all(inventory["gate"]["checks"].values())
    assert inventory["counts"] == {
        "products": 18,
        "lc_products": 9,
        "tpf_products": 9,
        "paired_sector_cadence_keys": 9,
    }

    products = inventory["products"]
    keys = {
        (item["sector"], item["cadence_seconds"], item["product_type"])
        for item in products
    }
    assert len(keys) == 18
    assert all(item["size_match"] and item["sha256_match"] for item in products)
    assert all(item["schema"]["pass"] for item in products)
    assert all(item["exposure_metadata_pass"] for item in products)
    assert all(item["inventory_metadata_match"] for item in products)
    assert all(item["aperture"]["pass"] for item in products)

    for item in products:
        required = LC_REQUIRED_COLUMNS if item["product_type"] == "lc" else TPF_REQUIRED_COLUMNS
        assert set(item["schema"]["required_columns"]) == required
        assert item["schema"]["missing_columns"] == []
        assert item["schema"]["format_mismatches"] == {}
        assert item["schema"]["pixel_shape_mismatches"] == {}
        assert len(item["aperture"]["sha256"]) == 64
        assert item["aperture"]["optimal_pixel_count"] > 0

    assert len(inventory["pairs"]) == 9
    for pair in inventory["pairs"]:
        assert pair["pass"] is True
        assert pair["cadenceno_exact_match"] is True
        assert pair["quality_exact_match"] is True
        assert pair["aperture_exact_match"] is True
        assert all(
            comparison["exact_with_matching_nans"]
            for comparison in pair["array_comparisons"].values()
        )
        assert all(pair["metadata_field_matches"].values())


def test_faz1_actual_fits_time_round_trip_required_columns_and_aperture_hash():
    inventory = load_json("outputs/faz1_product_inventory.json")
    measured_maximum = 0.0
    for item in inventory["products"]:
        path = ROOT / item["relative_path"]
        with fits.open(path, mode="readonly", memmap=True) as hdul:
            required = LC_REQUIRED_COLUMNS if item["product_type"] == "lc" else TPF_REQUIRED_COLUMNS
            assert required.issubset(hdul[1].columns.names)
            times = np.asarray(hdul[1].data["TIME"], dtype=np.float64)
            times = times[np.isfinite(times)]
            bjdref = float(hdul[1].header["BJDREFI"]) + float(
                hdul[1].header["BJDREFF"]
            )
            residual = np.max(np.abs(((times + bjdref) - bjdref) - times))
            measured_maximum = max(measured_maximum, float(residual))

            aperture = np.asarray(hdul[2].data)
            actual_aperture_hash = hashlib.sha256(
                np.ascontiguousarray(aperture).tobytes()
            ).hexdigest()
            assert list(aperture.shape) == item["aperture"]["shape"]
            assert actual_aperture_hash == item["aperture"]["sha256"]
            assert int(np.count_nonzero(aperture & 2)) == item["aperture"][
                "optimal_pixel_count"
            ]

    assert measured_maximum < 1e-8
    assert measured_maximum == inventory["max_btjd_bjd_tdb_btjd_residual_days"]


def test_faz1_ledger_reason_counts_cover_every_raw_row():
    inventory = load_json("outputs/faz1_product_inventory.json")
    expected_aggregate = {
        120: {
            "raw": 115832,
            "reference": 102502,
            "invalid_time": 8549,
            "invalid_pdcsap_flux": 4718,
            "nonpositive_pdcsap_flux": 0,
            "quality_default_reject": 3,
            "post_quality_clip_or_filter": 60,
            "included_reference": 102502,
        },
        20: {
            "raw": 354555,
            "reference": 310533,
            "invalid_time": 40659,
            "invalid_pdcsap_flux": 2231,
            "nonpositive_pdcsap_flux": 0,
            "quality_default_reject": 310,
            "post_quality_clip_or_filter": 822,
            "included_reference": 310533,
        },
    }

    for cadence in (120, 20):
        summaries = [
            item
            for item in inventory["cadence_ledger_summary"]
            if item["cadence_seconds"] == cadence
        ]
        assert all(set(item["reason_counts"]) == REASONS for item in summaries)
        assert all(item["reason_count_sum"] == item["raw_row_count"] for item in summaries)
        assert all(
            item["reason_counts"]["included_reference"] == item["reference_row_count"]
            for item in summaries
        )
        aggregate = Counter()
        for item in summaries:
            aggregate["raw"] += item["raw_row_count"]
            aggregate["reference"] += item["reference_row_count"]
            for reason, count in item["reason_counts"].items():
                aggregate[reason] += count
        assert dict(aggregate) == expected_aggregate[cadence]

        ledger = inventory["cadence_ledgers"][str(cadence)]
        assert ledger["row_count"] == expected_aggregate[cadence]["raw"]
        assert ledger["reference_row_count"] == expected_aggregate[cadence]["reference"]
        actual_by_sector = defaultdict(Counter)
        actual_rows = 0
        with gzip.open(ROOT / ledger["relative_path"], mode="rt", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames
            for row in reader:
                reason = row["exclusion_reason"]
                assert reason in REASONS
                assert (row["in_current_reference"] == "true") == (
                    reason == "included_reference"
                )
                actual_by_sector[int(row["sector"])][reason] += 1
                actual_rows += 1
        assert actual_rows == ledger["row_count"]
        for item in summaries:
            assert {
                reason: actual_by_sector[item["sector"]][reason] for reason in REASONS
            } == item["reason_counts"]
        assert set(REASONS).isdisjoint(header)
        assert "exclusion_reason" in header
        assert "quality_default_17087_pass" in header
        assert "quality_hard_24319_pass" in header
        assert "in_current_reference" in header
def test_faz2_exact_physical_epochs_classes_and_no_20s_duplicates():
    inventory = load_json("outputs/faz2_transit_inventory.json")
    assert inventory["gate_pass"] is True
    assert inventory["gate"]["gate_pass"] is True
    assert all(inventory["gate"]["checks"].values())
    events = inventory["events"]
    assert len(events) == 18
    assert len({item["physical_event_id"] for item in events}) == 18
    assert len({(item["sector"], item["epoch"]) for item in events}) == 18

    actual_epochs = {
        sector: [item["epoch"] for item in events if item["sector"] == sector]
        for sector in EXPECTED_EPOCHS
    }
    assert actual_epochs == EXPECTED_EPOCHS
    expected_gaps = {(37, 2), (99, 189)}
    actual_gaps = {
        (item["sector"], item["epoch"])
        for item in events
        if item["classification"] == "GAP"
    }
    assert actual_gaps == expected_gaps
    assert sum(item["classification"] == "FULL" for item in events) == 16
    assert sum(item["classification"] == "GAP" for item in events) == 2
    assert sum(item["used"] for item in events) == 16
    assert sum(item["coverage_20s"] is not None for item in events) == 9
    assert all(
        (item["coverage_20s"] is not None) == (item["sector"] in {90, 99, 100})
        for item in events
    )


def test_faz2_events_are_derived_from_actual_bounds_and_meet_coverage_gates():
    inventory = load_json("outputs/faz2_transit_inventory.json")
    ephemeris = inventory["ephemeris_and_windows"]
    derived = inventory["event_derivation_from_actual_120s_bounds"]
    assert inventory["input_policy"]["hard_coded_sector_dates_used"] is False
    assert inventory["input_policy"]["event_depth_values_inspected_for_classification"] is False

    half_window = ephemeris["analysis_half_window_hours"] / 24.0
    for sector in derived:
        first = math.ceil(
            (
                sector["finite_raw_120s_time_min_btjd"]
                - half_window
                - ephemeris["t0_btjd"]
            )
            / ephemeris["period_days"]
        )
        last = math.floor(
            (
                sector["finite_raw_120s_time_max_btjd"]
                + half_window
                - ephemeris["t0_btjd"]
            )
            / ephemeris["period_days"]
        )
        assert sector["overlapping_epochs"] == list(range(first, last + 1))

    full_events = [item for item in inventory["events"] if item["classification"] == "FULL"]
    t14_fractions = []
    limb_fractions = []
    for event in full_events:
        coverage = event["coverage_120s"]
        regions = coverage["regions"]
        t14_fractions.append(regions["t14"]["coverage_fraction"])
        limb_fractions.append(
            max(
                regions["ingress"]["coverage_fraction"],
                regions["egress"]["coverage_fraction"],
            )
        )
        assert regions["t14"]["cadence_count"] > 0
        assert regions["left_out_of_transit_baseline"]["cadence_count"] >= 0
        assert regions["right_out_of_transit_baseline"]["cadence_count"] >= 0
        assert "analysis_window_raw_cadences" in coverage["quality_bit_summaries"]
        systematics = coverage["systematics_summaries"]["t14_raw_cadences"]
        assert set(systematics) == {"background", "pointing", "moment_centroid"}
        assert "nearest_cadence_distances_days" in coverage["nearest_gap_distances"]

    assert min(t14_fractions) >= 0.8
    assert min(limb_fractions) >= 0.8
    assert min(t14_fractions) == inventory["summary"]["minimum_full_t14_coverage"]
    assert min(limb_fractions) == inventory["summary"][
        "minimum_full_ingress_or_egress_coverage"
    ]
    for event in inventory["events"]:
        if event["classification"] == "GAP":
            assert event["coverage_120s"]["regions"]["t14"]["cadence_count"] == 0
            assert event["used"] is False
            assert event["exclusion_reason"] == (
                "no_reference_included_120s_cadence_in_t14"
            )


def test_faz2_used_events_reconcile_exactly_to_event_depth_identifiers():
    inventory = load_json("outputs/faz2_transit_inventory.json")
    used = {
        (item["sector"], item["epoch"])
        for item in inventory["events"]
        if item["used"]
    }
    with (ROOT / "outputs" / "toi3492_120s_event_depths.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        expected = {
            (int(row["sector"]), int(row["epoch"])) for row in csv.DictReader(handle)
        }
    assert len(used) == 16
    assert used == expected
    assert inventory["provenance"]["used_event_reconciliation"][
        "depth_columns_read_for_classification"
    ] is False
