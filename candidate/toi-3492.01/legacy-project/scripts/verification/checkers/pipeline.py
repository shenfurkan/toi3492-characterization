"""Verification checks for the Phase-5 and Phase-6 pipeline stages."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
from scipy.special import logsumexp

from ..core import (
    ROOT,
    SECTORS,
    Verification,
    _as_bool,
    _close,
    _duration_hours,
    _load,
    _sign_flip_pvalue,
    _weighted_quantile,
)


def _phase5_retained(blocks):
    totals = blocks.groupby("cell_id")["elpd"].sum()
    best = totals.idxmax()
    retained = {best}
    comparisons = {}
    for cell in totals.index:
        if cell == best:
            continue
        selected = blocks.loc[blocks["cell_id"].isin([best, cell])]
        event = selected.groupby(["cell_id", "event_id"])["elpd"].sum().unstack(0)
        sector = selected.groupby(["cell_id", "sector"])["elpd"].sum().unstack(0)
        delta = float((event[best] - event[cell]).sum())
        se = max(
            math.sqrt(len(event) * np.var(event[best] - event[cell], ddof=1)),
            math.sqrt(len(sector) * np.var(sector[best] - sector[cell], ddof=1)),
        )
        comparisons[cell] = (delta, se)
        if not delta > 2.0 * se:
            retained.add(cell)
    return best, retained, comparisons


def verify_phase5_and_5b(audit: Verification) -> None:
    phase5 = _load("outputs/faz5_window_polynomial_grid.json")
    blocks = pd.read_csv(ROOT / "outputs" / "faz5_block_scores.csv")
    best, retained, comparisons = _phase5_retained(blocks)
    stored_pairwise = {row["cell_id"]: row for row in phase5["model_comparison"]["pairwise_against_best"]}
    pairs_ok = all(
        _close(stored_pairwise[cell]["delta_elpd_best_minus_cell"], value[0])
        and _close(stored_pairwise[cell]["adopted_standard_error"], value[1])
        for cell, value in comparisons.items()
    )
    audit.check("phase5", "elpd_selection_recomputed", bool(
        best == phase5["model_comparison"]["best_raw_elpd_cell"]
        and retained == set(phase5["model_comparison"]["retained_cell_ids"])
        and pairs_ok and phase5["status"] == "FAIL"
    ), f"best={best} retained={len(retained)}")
    with np.load(ROOT / "data" / "toi3492_faz5_geometry_draws.npz", allow_pickle=False) as payload:
        draws = np.asarray(payload["draws"], dtype=float)
    duration = _duration_hours(draws[:, :, 0], draws[:, :, 1], draws[:, :, 2], 9.2224171)
    audit.check("phase5", "geometry_draw_duration", bool(np.allclose(
        duration, draws[:, :, 3], rtol=0, atol=2e-14
    )), f"draws={draws.shape}")
    report = _load("outputs/faz5b_remediation.json")
    ledger = pd.read_csv(ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz")
    long_table = pd.read_csv(ROOT / "data" / "toi3492_faz4_reductions_120s.csv.gz",
                             usecols=["sector", "cadenceno", "branch"])
    included = ledger["in_current_reference"].map(_as_bool).to_numpy()
    quality = ledger["quality"].fillna(0).to_numpy(np.int64)
    valid = (np.isfinite(ledger["time_btjd"]) & np.isfinite(ledger["pdcsap_flux"])
             & np.isfinite(ledger["pdcsap_flux_err"]) & (ledger["pdcsap_flux"] > 0)
             & (ledger["pdcsap_flux_err"] > 0) & ((quality & 17087) == 0))
    raw_keys = set(map(tuple, long_table.loc[long_table["branch"] == "pdcsap", ["sector", "cadenceno"]].to_numpy()))
    reference_keys = set(map(tuple, ledger.loc[valid & included, ["sector", "cadenceno"]].to_numpy()))
    lineage_keys = set(map(tuple, pd.read_csv(ROOT / "outputs" / "faz5b_cadence_lineage.csv")[["sector", "cadenceno"]].to_numpy()))
    audit.check("phase5b", "cadence_lineage_recomputed", bool(
        raw_keys == set(map(tuple, ledger.loc[valid, ["sector", "cadenceno"]].to_numpy()))
        and lineage_keys == raw_keys - reference_keys
        and len(lineage_keys) == 60
    ), f"raw={len(raw_keys)} reference={len(reference_keys)} lineage={len(lineage_keys)}")
    with np.load(ROOT / "data" / "toi3492_faz5b_handoff_draws.npz", allow_pickle=False) as payload:
        handoff_draws = np.asarray(payload["draws"], dtype=float)
        handoff_weights = np.asarray(payload["joint_model_weights"], dtype=float)
        names = [str(name) for name in payload["parameter_names"]]
    flat = handoff_draws.reshape(-1, handoff_draws.shape[-1])
    weights = np.repeat(handoff_weights / handoff_draws.shape[1], handoff_draws.shape[1])
    stored_mixture = report["model_averaged_geometry"]["hierarchical_specification_mixture"]
    mixture_ok = names == ["rp_rs", "a_rs", "impact_parameter", "t14_hours"] and _close(np.sum(handoff_weights), 1.0)
    for index, name in enumerate(names):
        computed = _weighted_quantile(flat[:, index], weights, [0.025, 0.16, 0.5, 0.84, 0.975])
        expected = [stored_mixture[name][key] for key in ("p025", "p16", "median", "p84", "p975")]
        mixture_ok &= bool(np.allclose(computed, expected, rtol=0, atol=1e-12))
    audit.check("phase5b", "weighted_handoff_mixture", mixture_ok,
                f"models={handoff_draws.shape[0]} draws_per_model={handoff_draws.shape[1]}")
    audit.check("phase5b", "conditional_status_preserved", bool(
        report["status"] == "CONDITIONAL_CONTINUE"
        and report["original_phase5_status"] == "FAIL"
        and not report["gate"]["gate_pass"]
    ), report["status"])


def verify_phase6(audit: Verification) -> None:
    scores = pd.read_csv(ROOT / "outputs" / "faz6_loso_scores.csv")
    report = _load("outputs/faz6_kernel_comparison.json")
    mixture = pd.read_csv(ROOT / "outputs" / "faz6_kernel_sector_mixture.csv")
    audit.check("phase6", "complete_loso_contract", bool(
        len(scores) == 576 and scores["valid"].map(_as_bool).all()
        and scores.groupby(["model_id", "kernel_id"]).size().eq(6).all()
    ), f"rows={len(scores)} models={scores['model_id'].nunique()}")
    reconstructed = []
    for kernel in sorted(scores["kernel_id"].unique()):
        for sector in SECTORS:
            selected = scores.loc[(scores["kernel_id"] == kernel) & (scores["held_sector"] == sector)]
            by_mask = []
            for mask in ("raw_valid", "reference_included"):
                subset = selected.loc[selected["mask_id"] == mask]
                by_mask.append(logsumexp(
                    np.log(subset["conditional_cell_weight"].to_numpy(float))
                    + subset["branch_log_predictive_density"].to_numpy(float)
                ))
            reconstructed.append((kernel, sector, float(logsumexp(np.log([0.5, 0.5]) + by_mask))))
    mixture_ok = True
    for kernel, sector, value in reconstructed:
        stored = mixture.loc[(mixture["kernel_id"] == kernel) & (mixture["held_sector"] == sector)]
        mixture_ok &= len(stored) == 1 and _close(value, stored.iloc[0]["combined_log_predictive_density"], rel=0, abs_tol=1e-9)
    audit.check("phase6", "log_density_mixtures_recomputed", mixture_ok,
                f"rows={len(reconstructed)}")
    comparison_ok = True
    by_kernel = {kernel: np.asarray([value for k, _, value in reconstructed if k == kernel])
                 for kernel in ("K0_white", "K1_ou", "K2_matern32", "K3_sho")}
    stored_comparisons = {row["kernel_id"]: row for row in report["screening"]["comparisons_against_k0"]}
    for kernel in ("K1_ou", "K2_matern32", "K3_sho"):
        deltas = by_kernel[kernel] - by_kernel["K0_white"]
        total = float(np.sum(deltas))
        standard_error = float(math.sqrt(len(deltas) * np.var(deltas, ddof=1)))
        stored = stored_comparisons[kernel]
        comparison_ok &= (
            _close(total, stored["delta_elpd"])
            and _close(standard_error, stored["paired_standard_error"])
            and _close(_sign_flip_pvalue(deltas), stored["exact_sign_flip_one_sided_p"])
            and stored["predictive_and_physical_gates_pass"] is False
        )
    audit.check("phase6", "kernel_comparisons_and_closure", comparison_ok and bool(
        report["screening"]["predictive_candidates_pending_joint_diagnostics"] == []
        and report["gate"]["phase6_pass"] is False and report["gate"]["phase7_may_begin"] is False
    ), report["status"])
    protocol = _load("data/faz6_joint_diagnostics_protocol_v2.json")
    fits_v2 = pd.read_csv(ROOT / "outputs" / "faz6_k0_joint_fits_v2.csv")
    optimizer = protocol["optimizer"]
    recomputed_valid = (
        fits_v2["objective_improvement"].to_numpy(float) > 0
    )
    recomputed_valid &= fits_v2["parameter_movement_norm"].to_numpy(float) > 0
    recomputed_valid &= fits_v2["multistart_objective_spread"].to_numpy(float) <= optimizer["stationarity_maximum_objective_spread"]
    recomputed_valid &= fits_v2["multistart_unit_parameter_spread"].to_numpy(float) <= optimizer["stationarity_maximum_unit_parameter_spread"]
    recomputed_valid &= fits_v2["optimizer_success"].map(_as_bool).to_numpy()
    failed_ids = set(fits_v2.loc[~recomputed_valid, "model_id"])
    audit.check("phase6", "v2_stationarity_failure_recomputed", bool(
        len(fits_v2) == 24
        and failed_ids == {"raw_valid::W20_P0", "reference_included::W32_P2"}
        and int(np.sum(recomputed_valid)) == 22
    ), f"failed={sorted(failed_ids)}")
    remedial = pd.read_csv(ROOT / "outputs" / "faz6r_joint_fits.csv")
    result = _load("outputs/faz6r_result.json")
    thresholds = result["thresholds"]
    remedial_valid = (
        remedial["all_starts_finite"].map(_as_bool).to_numpy()
        & remedial["all_starts_moved"].map(_as_bool).to_numpy()
        & remedial["all_starts_improved"].map(_as_bool).to_numpy()
        & (remedial["objective_spread"].to_numpy(float) <= thresholds["objective_spread_max"])
        & (remedial["unit_parameter_spread"].to_numpy(float) <= thresholds["unit_parameter_spread_max"])
        & (remedial["minimum_bound_distance"].to_numpy(float) >= thresholds["minimum_bound_distance"])
        & (remedial["validator_objective_difference"].to_numpy(float) <= thresholds["powell_objective_difference_max"])
        & (remedial["validator_unit_parameter_difference"].to_numpy(float) <= thresholds["powell_unit_parameter_difference_max"])
    )
    maximum_beta = max(row["weighted_equal_sector_beta"] for row in result["beta_mixture"])
    audit.check("phase6", "remediation_stationarity_and_beta_gate", bool(
        len(remedial) == 24 and np.all(remedial_valid)
        and result["stationary_branch_count"] == 24
        and _close(maximum_beta, result["maximum_weighted_beta"])
        and maximum_beta > thresholds["beta_max"]
        and result["status"] == "FAIL_RESIDUAL_CORRELATION"
        and result["phase7_may_begin"] is False
    ), f"max_beta={maximum_beta:.9f}")
    audit.warning("phase6", "residual_replay_limit",
                  "The 6R residual time series are not retained, so beta is checked from the frozen mixture table rather than recomputed from raw residuals.")
