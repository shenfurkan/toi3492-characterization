import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits


ROOT = Path(__file__).resolve().parents[1]
SECTORS = {37, 63, 64, 90, 99, 100}
MASKS = {
    "strict_zero": 0,
    "lightkurve_default": 17087,
    "explicit_hard": 24319,
}
TELEMETRY = {"SAP_BKG", "POS_CORR1", "POS_CORR2", "MOM_CENTR1", "MOM_CENTR2"}
PARAMETERS = {"rp_rs", "a_rs", "impact_parameter", "t14_hours"}


def load_json(relative_path):
    with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quality_pass(quality, name):
    quality = np.asarray(quality, dtype=np.int64)
    if name == "strict_zero":
        return quality == 0
    return (quality & MASKS[name]) == 0


@pytest.fixture(scope="module")
def audit():
    return load_json("outputs/faz3_quality_audit.json")


@pytest.fixture(scope="module")
def input_inventory():
    return load_json("outputs/faz3_input_inventory.json")


@pytest.fixture(scope="module")
def faz2():
    return load_json("outputs/faz2_transit_inventory.json")


@pytest.fixture(scope="module")
def ledger():
    return pd.read_csv(ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz")


def test_three_exact_quality_masks_counts_and_rejected_bits(audit, ledger):
    section = audit["quality_masks"]
    assert set(section["definitions"]) == set(MASKS)
    assert {
        name: definition["numeric_bitmask"]
        for name, definition in section["definitions"].items()
    } == MASKS

    phase = (
        (ledger["time_btjd"].to_numpy(float) - 2314.5211550001986 + 9.2224171 / 2)
        % 9.2224171
    ) - 9.2224171 / 2
    finite = (
        np.isfinite(ledger["time_btjd"])
        & np.isfinite(ledger["pdcsap_flux"])
        & np.isfinite(ledger["pdcsap_flux_err"])
        & (ledger["pdcsap_flux_err"] > 0)
    ).to_numpy(bool)
    window = np.abs(phase) <= 13.0 / 24.0

    for sector in sorted(SECTORS):
        sector_rows = ledger["sector"].to_numpy(int) == sector
        quality = ledger.loc[sector_rows, "quality"].to_numpy(np.int64)
        reported = section["per_sector"][str(sector)]
        assert reported["raw_row_count"] == len(quality)
        for name, bitmask in MASKS.items():
            accepted = quality_pass(quality, name)
            result = reported["masks"][name]
            assert result["numeric_bitmask"] == bitmask
            assert result["accepted_count"] == int(accepted.sum())
            assert result["rejected_count"] == int((~accepted).sum())
            global_accepted = np.zeros(len(ledger), dtype=bool)
            global_accepted[sector_rows] = accepted
            assert result["model_window_accepted_count"] == int(
                np.count_nonzero(global_accepted & finite & window)
            )

            expected_bits = {}
            rejected_quality = quality[~accepted]
            for bit_index in range(32):
                bit_value = 1 << bit_index
                if name != "strict_zero" and not bit_value & bitmask:
                    continue
                count = int(np.count_nonzero(rejected_quality & bit_value))
                if count:
                    expected_bits[bit_value] = count
            actual_bits = {
                item["bit_value"]: item["cadence_count"]
                for item in result["bits_causing_rejection"]
            }
            assert actual_bits == expected_bits


def test_real_geometry_optimizer_covariance_and_pairwise_shifts(audit):
    geometry = audit["mask_geometry"]
    assert set(geometry["fits"]) == set(MASKS)
    total_points = 0
    for mask_name, result in geometry["fits"].items():
        assert result["numeric_bitmask"] == MASKS[mask_name]
        assert result["model"]["timestamps"].startswith("native 120-s BTJD")
        assert result["model"]["exposure_seconds"] == 120.0
        assert result["model"]["supersample_factor"] >= 7
        assert result["model"]["period_days_fixed"] == 9.2224171
        assert result["model"]["t0_btjd_fixed"] == 2314.5211550001986
        assert result["model"]["limb_darkening_fixed"] == [
            0.3546454910932521,
            0.15379449038160178,
        ]
        assert {int(key) for key in result["n_points_by_sector"]} == SECTORS
        assert result["n_points"] == sum(result["n_points_by_sector"].values())
        total_points = result["n_points"]

        optimizer = result["optimizer"]
        assert optimizer["multiple_start_count"] >= 4
        assert optimizer["selected_success"] is True
        assert len(optimizer["attempts"]) == optimizer["multiple_start_count"]
        assert all("movement" in attempt for attempt in optimizer["attempts"])
        assert all(np.isfinite(attempt["final_robust_objective"]) for attempt in optimizer["attempts"])

        covariance = result["covariance"]
        matrix = np.asarray(covariance["matrix"], dtype=float)
        assert covariance["valid"] is True
        assert covariance["jacobian_rank"] == 3
        assert matrix.shape == (3, 3)
        assert np.all(np.isfinite(matrix))
        assert np.all(np.diag(matrix) > 0)
        assert set(result["parameters"]) == PARAMETERS
        for parameter in result["parameters"].values():
            assert np.isfinite(parameter["value"])
            assert np.isfinite(parameter["error"])
            assert parameter["error"] > 0
    assert total_points == 12072

    assert len(geometry["pairwise_shifts"]) == 3
    for pair in geometry["pairwise_shifts"]:
        assert set(pair["shifts"]) == PARAMETERS
        left = geometry["fits"][pair["left_mask"]]["parameters"]
        right = geometry["fits"][pair["right_mask"]]["parameters"]
        for name, shift in pair["shifts"].items():
            combined = math.hypot(left[name]["error"], right[name]["error"])
            expected = abs(left[name]["value"] - right[name]["value"]) / combined
            assert shift["combined_error"] == pytest.approx(combined)
            assert shift["combined_sigma_shift"] == pytest.approx(expected)
            assert shift["pass"] == (expected <= 0.5)
    assert geometry["shift_gate_pass"] == all(
        value <= 0.5 for value in geometry["maximum_combined_sigma_shift"].values()
    )


def test_real_telemetry_names_standardization_and_exact_threshold(audit):
    telemetry = audit["telemetry_correlations"]
    assert set(telemetry["available_variables"]) == TELEMETRY
    assert telemetry["threshold_absolute_r"] == 0.10
    assert set(telemetry["by_sector"]) == {str(sector) for sector in SECTORS}
    post_values = []
    for sector in telemetry["by_sector"].values():
        assert set(sector["correlations"]) == TELEMETRY
        for name, result in sector["correlations"].items():
            assert name in TELEMETRY
            assert result["threshold_absolute_r"] == 0.10
            assert np.isfinite(result["before_correction_r"])
            assert np.isfinite(result["after_correction_r"])
            post_values.append(abs(result["after_correction_r"]))
    assert set(telemetry["global"]) == TELEMETRY
    for result in telemetry["global"].values():
        post_values.append(abs(result["after_correction_r"]))
    assert telemetry["maximum_available_post_correction_absolute_r"] == pytest.approx(
        max(post_values)
    )
    assert telemetry["gate_pass"] == (max(post_values) < 0.10)
    assert set(telemetry["psf_centroids"]) == {"PSF_CENTR1", "PSF_CENTR2"}
    assert all(not item["available"] for item in telemetry["psf_centroids"].values())
    assert all(
        item["finite_count_in_raw_120s_ledger"] == 0
        for item in telemetry["psf_centroids"].values()
    )


def test_six_official_cbvs_and_out_of_transit_blocked_selections(
    audit, input_inventory
):
    assert input_inventory["gate_pass"] is True
    products = input_inventory["cbv_products"]
    assert len(products) == 6
    assert {item["sector"] for item in products} == SECTORS
    assert len({item["relative_path"] for item in products}) == 6
    for item in products:
        path = ROOT / item["relative_path"]
        assert path.is_file()
        assert path.stat().st_size == item["size_bytes"]
        assert sha256_file(path) == item["sha256"]
        assert "tesscurl_sector_" in item["curl_script_url"]
        assert item["url"].endswith("s_cbv.fits")
        assert item["fits"]["single_scale_vector_count"] >= 8
        assert len(item["fits"]["scale_extensions"]) >= 2
        with fits.open(path, mode="readonly", memmap=True) as hdul:
            hdu = hdul[item["fits"]["single_scale_hdu_index"]]
            assert int(hdu.header["CAMERA"]) == item["camera"]
            assert int(hdu.header["CCD"]) == item["ccd"]
            assert {f"VECTOR_{index}" for index in range(1, 9)}.issubset(hdu.columns.names)

    selection = audit["cbv_selection"]
    assert selection["transit_depth_used_for_selection"] is False
    assert selection["all_six_sectors_valid"] is True
    assert set(selection["by_sector"]) == {str(sector) for sector in SECTORS}
    for result in selection["by_sector"].values():
        assert result["valid"] is True
        assert result["alignment"]["key"] == "CADENCENO"
        assert result["alignment"]["exact_full_alignment"] is True
        assert result["selection_data"]["transit_points_used"] is False
        assert result["vectors_tested"] == list(range(9))
        assert {item["n_cbv"] for item in result["candidate_scores"]} == set(range(9))
        assert result["blocked_validation"]["block_count"] >= 3
        assert "leave-one-contiguous-time-block-out" in result["blocked_validation"]["method"]
        assert 0 <= result["selected_n_cbv"] <= 8
        assert np.isfinite(result["selected_predictive_rmse_ppm"])
        assert np.isfinite(result["selected_mean_predictive_log_score"])


def test_real_control_tic_six_products_events_and_trial_gate(
    audit, input_inventory, faz2
):
    control_input = input_inventory["control"]
    assert control_input["tic_id"] == 81400324
    assert control_input["preregistered_tmag"] == 9.1105
    assert control_input["magnitude_difference_control_minus_target"] == pytest.approx(0.6601, abs=1e-3)
    assert control_input["angular_separation_arcmin"] > 0
    products = input_inventory["control_products"]
    assert len(products) == 6
    assert {item["sector"] for item in products} == SECTORS
    target_detectors = {
        int(item["sector"]): (
            int(item["metadata"]["camera"]),
            int(item["metadata"]["ccd"]),
        )
        for item in load_json("outputs/faz1_product_inventory.json")["products"]
        if item["product_type"] == "lc" and item["cadence_seconds"] == 120
    }
    for item in products:
        assert item["tic_id"] == 81400324
        assert item["cadence_seconds"] == 120
        assert (item["camera"], item["ccd"]) == target_detectors[item["sector"]]
        assert "81400324" in item["dataURI"]
        assert "81077799" not in item["dataURI"]
        path = ROOT / item["relative_path"]
        assert sha256_file(path) == item["sha256"]

    control = audit["control_star"]
    assert control["identity"]["tic_id"] == 81400324
    assert control["identity"]["product_count"] == 6
    assert control["identity"]["target_data_substituted"] is False
    assert control["criteria_frozen_before_values"]["threshold_sigma"] == 3.0
    assert control["trial_count"] == 48
    assert len(control["event_results"]) == 18 * 3
    used = {(event["sector"], event["epoch"]) for event in faz2["events"] if event["used"]}
    for name in MASKS:
        events = [item for item in control["event_results"] if item["mask"] == name]
        assert len(events) == 18
        evaluable = {(item["sector"], item["epoch"]) for item in events if item["evaluable"]}
        assert used.issubset(evaluable)
        assert control["global_by_mask"][name]["evaluable_event_count"] == 16
        assert control["target_control_event_depth_correlations"][name][
            "paired_event_count"
        ] == 16
    expected_gate = (
        control["required_phase2_used_event_coverage"]
        and control["maximum_global_absolute_sigma"] < 3.0
        and control["maximum_trial_adjusted_event_absolute_sigma"] < 3.0
    )
    assert control["gate_pass"] == expected_gate


def test_all_18_phase2_events_link_to_raw_telemetry_and_gate_semantics(audit, faz2):
    event_section = audit["event_telemetry"]
    events = event_section["events"]
    assert event_section["event_count"] == 18
    assert event_section["phase2_event_ids_exactly_linked"] is True
    assert [item["physical_event_id"] for item in events] == [
        item["physical_event_id"] for item in faz2["events"]
    ]
    for event, source in zip(events, faz2["events"]):
        assert event["sector"] == source["sector"]
        assert event["epoch"] == source["epoch"]
        assert event["phase2_link"]["classification"] == source["classification"]
        assert event["phase2_link"]["used"] == source["used"]
        assert set(event["telemetry_ranges"]) == TELEMETRY
        assert set(event["quality"]["accepted_counts_by_mask"]) == set(MASKS)
        assert "maximum_gap_duration_days" in event["gaps"]
        assert isinstance(event["flags"], list)

    gate = audit["gate"]
    checks = gate["checks"]
    non_geometry = all(
        checks[name]
        for name in (
            "phase1_gate_true",
            "phase2_gate_true",
            "all_required_inputs_valid",
            "all_available_post_correction_telemetry_abs_r_below_0_10",
            "cbv_blocked_validation_complete_six_sectors",
            "real_control_star_gate_pass",
            "all_18_phase2_events_linked_to_raw_telemetry",
        )
    )
    geometry = audit["mask_geometry"]
    if non_geometry and geometry["gate_pass"]:
        expected_status = "PASS"
    elif (
        non_geometry
        and geometry["optimizer_covariance_pass"]
        and not geometry["shift_gate_pass"]
        and geometry["between_mask_systematic"]["propagated"]
    ):
        expected_status = "CONDITIONAL_PASS"
    else:
        expected_status = "FAIL"
    assert audit["gate_status"] == expected_status
    assert audit["gate_pass"] == (expected_status == "PASS")
    assert gate["phase4_may_begin"] == (expected_status == "PASS")
    assert gate["phase4_closed"] == (expected_status != "PASS")
