import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from astropy.io import fits


ROOT = Path(__file__).resolve().parents[1]
SECTORS = (37, 63, 64, 90, 99, 100)
BRANCHES = ("pdcsap", "sap_cbv", "tpf_pipeline", "tpf_pld")
QUALITY_MASK = 17087
PARAMETERS = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")


def load_json(relative_path):
    with (ROOT / relative_path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.fixture(scope="module")
def report():
    return load_json("outputs/faz4_reduction_comparison.json")


@pytest.fixture(scope="module")
def faz1():
    return load_json("outputs/faz1_product_inventory.json")


@pytest.fixture(scope="module")
def faz2():
    return load_json("outputs/faz2_transit_inventory.json")


@pytest.fixture(scope="module")
def faz3():
    return load_json("outputs/faz3_quality_audit.json")


@pytest.fixture(scope="module")
def long_table():
    return pd.read_csv(ROOT / "data" / "toi3492_faz4_reductions_120s.csv.gz")


def products_120s(faz1):
    return {
        (int(item["sector"]), item["product_type"]): item
        for item in faz1["products"]
        if int(item["cadence_seconds"]) == 120
    }


def test_frozen_inputs_exact_events_table_schema_and_counts(report, faz2, long_table):
    assert report["phase"] == 4
    assert report["input_policy"] == {
        "active_local_120s_fits_only": True,
        "legacy_zip_inspected": False,
        "network_used": False,
        "git_used": False,
        "phase5_started": False,
    }
    assert report["inputs"]["quality_mask"]["numeric_bitmask"] == QUALITY_MASK
    events = report["inputs"]["events"]
    assert events["used_event_count"] == 16
    assert events["gap_event_keys"] == [
        {"sector": 37, "epoch": 2},
        {"sector": 99, "epoch": 189},
    ]
    expected_used = {
        (int(item["sector"]), int(item["epoch"]))
        for item in faz2["events"]
        if item["used"]
    }
    actual_used = {
        (int(item["sector"]), int(item["epoch"]))
        for item in events["used_events"]
    }
    assert actual_used == expected_used

    artifact = report["artifacts"]["long_table"]
    path = ROOT / artifact["relative_path"]
    assert path.stat().st_size == artifact["size_bytes"]
    assert sha256_file(path) == artifact["sha256"]
    assert len(long_table) == artifact["row_count"]
    assert list(long_table.columns) == artifact["columns"]
    assert set(long_table["branch"]) == set(BRANCHES)
    assert set(long_table["sector"]) == set(SECTORS)
    assert np.all(np.isfinite(long_table["time_btjd"]))
    assert np.all(np.isfinite(long_table["flux"]))
    assert np.all(np.isfinite(long_table["flux_err"]))
    assert np.all(long_table["flux_err"] > 0)
    assert np.all(long_table["exposure_seconds"] == 120.0)
    assert np.all((long_table["quality"].to_numpy(np.int64) & QUALITY_MASK) == 0)
    assert not long_table.duplicated(["branch", "sector", "cadenceno"]).any()
    grouped = long_table.groupby(["branch", "sector"]).size()
    for branch in BRANCHES:
        for sector in SECTORS:
            assert grouped.loc[(branch, sector)] == artifact[
                "row_count_by_branch_sector"
            ][branch][str(sector)]
    assert set(long_table["provenance_id"]) == set(
        report["provenance_identifiers"]
    )


def test_recompute_branch_sector_counts_and_native_alignment(report, faz1, long_table):
    products = products_120s(faz1)
    cbv_inputs = {
        int(item["sector"]): item
        for item in load_json("outputs/faz3_input_inventory.json")["cbv_products"]
    }
    grouped = long_table.groupby(["branch", "sector"]).size()
    for sector in SECTORS:
        lc_item = products[(sector, "lc")]
        tpf_item = products[(sector, "tpf")]
        with fits.open(ROOT / lc_item["relative_path"], memmap=True) as lc_hdul:
            lc = lc_hdul[1].data
            lc_aperture = np.asarray(lc_hdul[2].data)
            time = np.asarray(lc["TIME"], dtype=float)
            cadence = np.asarray(lc["CADENCENO"], dtype=np.int64)
            quality = np.asarray(lc["QUALITY"], dtype=np.int64)
            pdcsap = np.asarray(lc["PDCSAP_FLUX"], dtype=float)
            pdcsap_err = np.asarray(lc["PDCSAP_FLUX_ERR"], dtype=float)
            sap = np.asarray(lc["SAP_FLUX"], dtype=float)
            sap_err = np.asarray(lc["SAP_FLUX_ERR"], dtype=float)
        with fits.open(ROOT / tpf_item["relative_path"], memmap=True) as tpf_hdul:
            tpf = tpf_hdul[1].data
            tpf_aperture = np.asarray(tpf_hdul[2].data)
            optimal = (tpf_aperture & 2) != 0
            pixels = np.asarray(tpf["FLUX"], dtype=float)[:, optimal]
            pixel_err = np.asarray(tpf["FLUX_ERR"], dtype=float)[:, optimal]
            assert np.array_equal(cadence, tpf["CADENCENO"])
            assert np.array_equal(time, tpf["TIME"], equal_nan=True)
            assert np.array_equal(quality, tpf["QUALITY"])
            assert np.array_equal(lc_aperture, tpf_aperture)
        cbv_item = cbv_inputs[sector]
        with fits.open(ROOT / cbv_item["relative_path"], memmap=True) as hdul:
            cbv = hdul[int(cbv_item["fits"]["single_scale_hdu_index"])].data
            assert np.array_equal(cadence, cbv["CADENCENO"])
            n_cbv = report["inputs"]["phase3_selected_n_cbv"][str(sector)]
            vectors = np.column_stack(
                [np.asarray(cbv[f"VECTOR_{index}"], float) for index in range(1, n_cbv + 1)]
            )
            cbv_gap = np.asarray(cbv["GAP"], bool)

        quality_ok = (quality & QUALITY_MASK) == 0
        pdcsap_valid = (
            quality_ok
            & np.isfinite(time)
            & np.isfinite(pdcsap)
            & np.isfinite(pdcsap_err)
            & (pdcsap > 0)
            & (pdcsap_err > 0)
        )
        sap_cbv_valid = (
            quality_ok
            & np.isfinite(time)
            & np.isfinite(sap)
            & np.isfinite(sap_err)
            & (sap > 0)
            & (sap_err > 0)
            & ~cbv_gap
            & np.all(np.isfinite(vectors), axis=1)
        )
        tpf_valid = (
            quality_ok
            & np.isfinite(time)
            & np.all(np.isfinite(pixels), axis=1)
            & np.all(np.isfinite(pixel_err) & (pixel_err > 0), axis=1)
            & (np.sum(pixels, axis=1) > 0)
            & (np.sqrt(np.sum(pixel_err**2, axis=1)) > 0)
        )
        assert grouped.loc[("pdcsap", sector)] == int(pdcsap_valid.sum())
        assert grouped.loc[("sap_cbv", sector)] == int(sap_cbv_valid.sum())
        assert grouped.loc[("tpf_pipeline", sector)] == int(tpf_valid.sum())
        assert grouped.loc[("tpf_pld", sector)] == int(tpf_valid.sum())

        for branch, valid in (
            ("pdcsap", pdcsap_valid),
            ("sap_cbv", sap_cbv_valid),
            ("tpf_pipeline", tpf_valid),
            ("tpf_pld", tpf_valid),
        ):
            actual = long_table.loc[
                (long_table["branch"] == branch) & (long_table["sector"] == sector),
                ["cadenceno", "time_btjd", "quality"],
            ].sort_values("cadenceno")
            order = np.argsort(cadence[valid])
            assert np.array_equal(actual["cadenceno"], cadence[valid][order])
            assert np.allclose(
                actual["time_btjd"], time[valid][order], rtol=0, atol=1e-12
            )
            assert np.array_equal(actual["quality"], quality[valid][order])


def test_one_time_crowdsap_and_pipeline_formula(report, faz1, long_table):
    formulas = report["correction_formulas"]
    assert formulas["pdcsap"]["additional_crowdsap_applications"] == 0
    for branch in ("sap_cbv", "tpf_pipeline", "tpf_pld"):
        assert formulas[branch]["additional_crowdsap_applications"] == 1
    assert formulas["flfrcsap"]["applied"] is False
    expected_counts = {
        "pdcsap": {0},
        "sap_cbv": {1},
        "tpf_pipeline": {1},
        "tpf_pld": {1},
    }
    for branch in BRANCHES:
        assert set(long_table.loc[long_table["branch"] == branch, "crowdsap_applied_count"]) == expected_counts[branch]
        for sector in SECTORS:
            meta = report["branches"][branch]["per_sector_reduction"][str(sector)]
            assert meta["crowdsap_applied_count"] in expected_counts[branch]
            assert meta["flfrcsap_applied_count"] == 0

    products = products_120s(faz1)
    for sector in SECTORS:
        lc_item = products[(sector, "lc")]
        tpf_item = products[(sector, "tpf")]
        with fits.open(ROOT / lc_item["relative_path"], memmap=True) as hdul:
            lc = hdul[1].data
            cadence = np.asarray(lc["CADENCENO"], np.int64)
            raw_pdcsap = np.asarray(lc["PDCSAP_FLUX"], float)
        pdcsap_branch = long_table.loc[
            (long_table["branch"] == "pdcsap") & (long_table["sector"] == sector)
        ].set_index("cadenceno")
        norm = report["branches"]["pdcsap"]["per_sector_reduction"][str(sector)][
            "initial_normalization_e_per_s"
        ]
        sample_cadences = pdcsap_branch.index.to_numpy()[::997]
        positions = pd.Series(np.arange(len(cadence)), index=cadence).loc[sample_cadences].to_numpy()
        assert np.allclose(
            pdcsap_branch.loc[sample_cadences, "flux"],
            raw_pdcsap[positions] / norm,
            rtol=0,
            atol=2e-15,
        )

        with fits.open(ROOT / tpf_item["relative_path"], memmap=True) as hdul:
            tpf = hdul[1].data
            aperture = (np.asarray(hdul[2].data) & 2) != 0
            raw_total = np.sum(np.asarray(tpf["FLUX"], float)[:, aperture], axis=1)
        pipeline = long_table.loc[
            (long_table["branch"] == "tpf_pipeline") & (long_table["sector"] == sector)
        ].set_index("cadenceno")
        meta = report["branches"]["tpf_pipeline"]["per_sector_reduction"][str(sector)]
        sample_cadences = pipeline.index.to_numpy()[::997]
        positions = pd.Series(np.arange(len(cadence)), index=cadence).loc[sample_cadences].to_numpy()
        expected = 1.0 + (
            raw_total[positions] / meta["initial_normalization_e_per_s"] - 1.0
        ) / meta["crowdsap"]
        assert np.allclose(
            pipeline.loc[sample_cadences, "flux"], expected, rtol=0, atol=3e-15
        )


def test_tpf_aperture_identity_same_pixels_and_observations(report, long_table):
    for sector in SECTORS:
        pipeline = long_table.loc[
            (long_table["branch"] == "tpf_pipeline") & (long_table["sector"] == sector)
        ].sort_values("cadenceno")
        pld = long_table.loc[
            (long_table["branch"] == "tpf_pld") & (long_table["sector"] == sector)
        ].sort_values("cadenceno")
        assert np.array_equal(pipeline["cadenceno"], pld["cadenceno"])
        assert np.array_equal(pipeline["time_btjd"], pld["time_btjd"])
        assert np.array_equal(pipeline["quality"], pld["quality"])
        assert np.array_equal(pipeline["aperture_sha256"], pld["aperture_sha256"])
        for branch in ("tpf_pipeline", "tpf_pld"):
            meta = report["branches"][branch]["per_sector_reduction"][str(sector)]
            alignment = meta["alignment"]
            assert alignment["lc_tpf_cadenceno_exact"] is True
            assert alignment["lc_tpf_time_exact"] is True
            assert alignment["lc_tpf_quality_exact"] is True
            assert alignment["lc_tpf_aperture_exact"] is True
            assert alignment["tpf_sum_vs_sap_max_abs_fractional_difference"] < 1e-6
            assert meta["aperture_sha256"] == pipeline["aperture_sha256"].iloc[0]
            assert meta["optimal_aperture_pixel_count"] == alignment["optimal_pixel_count"]


def test_cbv_and_pld_tuning_are_finite_blocked_and_oot_only(report, faz3):
    cbv = report["branches"]["sap_cbv"]
    pld = report["branches"]["tpf_pld"]
    for sector in SECTORS:
        key = str(sector)
        cbv_tuning = cbv["predictive_tuning"][key]
        phase3 = faz3["cbv_selection"]["by_sector"][key]
        assert cbv_tuning["selected_n_cbv"] == phase3["selected_n_cbv"]
        assert cbv_tuning["transit_points_used"] is False
        assert cbv_tuning["transit_depth_used"] is False
        assert cbv_tuning["blocked_validation"]["block_count"] >= 3
        assert len(cbv_tuning["candidate_scores"]) == 9
        assert all(np.isfinite(item["predictive_rmse_ppm"]) for item in cbv_tuning["candidate_scores"])
        assert cbv["per_sector_reduction"][key]["correction_training_transit_count"] == 0

        pld_tuning = pld["predictive_tuning"][key]
        assert pld_tuning["transit_points_used"] is False
        assert pld_tuning["transit_depth_used"] is False
        assert pld_tuning["block_count"] >= 3
        assert pld_tuning["finite"] is True
        candidates = pld_tuning["candidate_scores"]
        assert candidates
        assert all(np.isfinite(item["predictive_rmse_ppm"]) for item in candidates)
        selected = min(
            candidates,
            key=lambda item: (
                item["predictive_rmse_fraction"],
                item["retained_basis_dimension"],
                item["ridge_alpha"],
            ),
        )
        assert pld_tuning["selected_retained_basis_dimension"] == selected[
            "retained_basis_dimension"
        ]
        assert pld_tuning["selected_ridge_alpha"] == selected["ridge_alpha"]
        assert pld["per_sector_reduction"][key]["correction_training_transit_count"] == 0
        assert pld_tuning["aperture_pixel_count"] == pld["per_sector_reduction"][key][
            "optimal_aperture_pixel_count"
        ]


def test_injection_counts_recovery_bias_and_training_exclusion(report):
    design = report["injection_design"]
    assert design["purpose"].startswith("bounded Phase-4")
    assert design["deterministic"] is True
    assert design["raw_quality_gaps_timestamps_and_errors_modified"] is False
    trial_keys = None
    for branch in BRANCHES:
        screen = report["branches"][branch]["injection_screen"]
        trials = screen["trials"]
        assert screen["trial_count"] == 24
        assert screen["trial_count_by_sector"] == {str(sector): 4 for sector in SECTORS}
        assert screen["recovered_count"] == sum(item["recovered"] for item in trials)
        assert screen["recovery_rate"] == pytest.approx(screen["recovered_count"] / 24)
        biases = np.asarray(
            [item["absolute_fractional_depth_recovery_bias"] for item in trials]
        )
        assert screen["median_absolute_fractional_depth_recovery_bias"] == pytest.approx(
            np.median(biases)
        )
        assert screen["recovery_rate"] >= 0.90
        assert np.median(biases) <= 0.05
        assert all(item["injected_window_excluded_from_training"] for item in trials)
        assert all(not item["quality_and_timestamps_modified"] for item in trials)
        keys = [(item["trial_id"], item["center_btjd"]) for item in trials]
        if trial_keys is None:
            trial_keys = keys
        else:
            assert keys == trial_keys
        if branch.startswith("tpf"):
            assert all(item["same_spoc_aperture_pixels"] for item in trials)
        assert report["branches"][branch]["acceptance"]["checks"][
            "injection_trial_count_at_least_24"
        ] is True


def test_sector_signal_and_event_recovery(report, faz2):
    depths = pd.read_csv(ROOT / "outputs" / "faz4_sector_depths.csv")
    assert len(depths) == 24
    assert set(depths["branch"]) == set(BRANCHES)
    assert set(depths["sector"]) == set(SECTORS)
    assert np.all(depths["depth_ppm"] > 0)
    assert np.all(depths["depth_error_ppm"] > 0)
    assert np.allclose(
        depths["significance"], depths["depth_ppm"] / depths["depth_error_ppm"]
    )
    assert np.all(depths["significance"] >= 3.0)
    expected_event_counts = {37: 2, 63: 3, 64: 3, 90: 3, 99: 2, 100: 3}
    for row in depths.itertuples():
        assert row.event_count == expected_event_counts[row.sector]
        result = report["branches"][row.branch]["sector_depths"][str(row.sector)]
        assert result["depth_ppm"] == pytest.approx(row.depth_ppm)
        assert result["depth_error_ppm"] == pytest.approx(row.depth_error_ppm)
        assert result["positive_at_least_3sigma"] is True
    used = {
        (int(item["sector"]), int(item["epoch"]))
        for item in faz2["events"]
        if item["used"]
    }
    event_depths = report["event_depths"]
    assert len(event_depths) == 16 * 4
    for branch in BRANCHES:
        actual = {
            (int(item["sector"]), int(item["epoch"]))
            for item in event_depths
            if item["branch"] == branch
        }
        assert actual == used


def test_geometry_covariance_pairwise_shifts_systematic_and_gate(report):
    accepted = report["gate"]["accepted_branches"]
    assert accepted == list(BRANCHES)
    geometry = {
        branch: report["branches"][branch]["geometry"] for branch in BRANCHES
    }
    for branch, result in geometry.items():
        model = result["model"]
        assert model["timestamps"].startswith("native 120-s BTJD")
        assert model["period_days_fixed"] == 9.2224171
        assert model["t0_btjd_fixed"] == 2314.5211550001986
        assert model["limb_darkening_fixed"] == [
            0.3546454910932521,
            0.15379449038160178,
        ]
        assert model["exposure_seconds"] == 120.0
        assert model["supersample_factor"] >= 7
        assert model["profiled_per_sector"] == [
            "sector_offset",
            "sector_linear_time",
        ]
        assert model["branches_combined_as_independent_likelihoods"] is False
        assert result["optimizer"]["multiple_start_count"] >= 4
        covariance = result["covariance"]
        matrix = np.asarray(covariance["matrix"], dtype=float)
        assert covariance["valid"] is True
        assert covariance["jacobian_rank"] == 3
        assert matrix.shape == (3, 3)
        assert np.all(np.isfinite(matrix))
        assert np.all(np.diag(matrix) > 0)
        for name in PARAMETERS:
            assert np.isfinite(result["parameters"][name]["value"])
            assert result["parameters"][name]["error"] > 0

    comparison = report["accepted_branch_geometry_comparison"]
    assert len(comparison["pairwise_shifts"]) == math.comb(len(accepted), 2)
    maxima = {name: 0.0 for name in PARAMETERS}
    for pair in comparison["pairwise_shifts"]:
        left = geometry[pair["left_branch"]]["parameters"]
        right = geometry[pair["right_branch"]]["parameters"]
        for name, shift in pair["shifts"].items():
            combined = math.hypot(left[name]["error"], right[name]["error"])
            sigma = abs(left[name]["value"] - right[name]["value"]) / combined
            assert shift["quadrature_combined_error"] == pytest.approx(combined)
            assert shift["combined_sigma_shift"] == pytest.approx(sigma)
            assert shift["pass"] == (sigma <= 0.5)
            maxima[name] = max(maxima[name], sigma)
    assert comparison["maximum_combined_sigma_shift"] == pytest.approx(maxima)
    assert comparison["shift_gate_pass"] == all(value <= 0.5 for value in maxima.values())

    systematic = comparison["between_reduction_systematic"]
    if comparison["shift_gate_pass"]:
        assert systematic["propagated"] is False
    else:
        assert systematic["propagated"] is True
        for name in PARAMETERS:
            values = np.asarray(
                [geometry[branch]["parameters"][name]["value"] for branch in accepted]
            )
            adopted = max(float(np.std(values, ddof=1)), float(0.5 * np.ptp(values)))
            assert systematic["values"][name]["adopted_systematic"] == pytest.approx(adopted)
            for branch in accepted:
                propagated = systematic["propagated_uncertainties"][branch][name]
                assert propagated["total_error"] == pytest.approx(
                    math.hypot(propagated["formal_error"], adopted)
                )

    required = (
        report["branches"]["pdcsap"]["acceptance"]["accepted"]
        and any(
            report["branches"][branch]["acceptance"]["accepted"]
            for branch in BRANCHES
            if branch != "pdcsap"
        )
    )
    if required and comparison["shift_gate_pass"]:
        expected_status = "PASS"
    elif required and not comparison["shift_gate_pass"] and systematic["propagated"]:
        expected_status = "CONDITIONAL_PASS"
    else:
        expected_status = "FAIL"
    assert report["gate_status"] == expected_status
    assert report["gate"]["gate_pass"] == (expected_status == "PASS")
    assert report["gate"]["conditional_pass"] == (expected_status == "CONDITIONAL_PASS")
    assert report["gate"]["phase5_may_begin"] == (
        expected_status in ("PASS", "CONDITIONAL_PASS")
    )
    assert report["gate"]["phase5_started"] is False
