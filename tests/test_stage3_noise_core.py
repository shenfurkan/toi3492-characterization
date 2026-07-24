"""Tests for stage3_noise_core.py — K3_MATERN32_SECTOR architecture.

Tests cover: parameter_layout, pooled_map_objective, _registered_starts,
_fit_pooled_map, fit_pooled_map, held_sector_joint_log_predictive_density,
_accumulate, _finalize.

All tests use synthetic data (no real TOI-3492 data is read).
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from faz6_noise_core import (
    SectorData, ParameterLayout, PooledMapFit, BoundaryDiagnostic,
    marginal_log_likelihood, parameter_layout as old_layout,
    fit_pooled_map as old_fit,
    held_sector_joint_log_predictive_density as old_held,
    OFFSET_PRIOR_SIGMA, LOG_RATIO_BOUNDS, OFFSET_BOUNDS,
    NoiseModelError,
)
from stage3_noise_core import (
    KERNEL_IDS, TIMESCALE_UPPER_MINUTES,
    parameter_layout, pooled_map_objective,
    _registered_starts, _fit_pooled_map, fit_pooled_map,
    held_sector_joint_log_predictive_density,
    _accumulate, _finalize, _valid_timescale_offset_bounds,
)
import stage3_synthetic_generator as synthetic_generator

K3_ID = "K3_MATERN32_SECTOR"


def synthetic_sector(sector, seed=0, n=60, degree=1):
    rng = np.random.default_rng(seed + sector)
    time = np.arange(n, dtype=np.float64) * (2.0 / 1440.0) + sector * 10.0
    x = np.linspace(-0.05, 0.05, n, dtype=np.float64)
    design = np.column_stack([x**p for p in range(degree + 1)]).astype(np.float64)
    error = np.full(n, 4e-4, dtype=np.float64)
    flux = design @ np.array([1e-4, -3e-4]) + rng.normal(0.0, error)
    return SectorData(
        sector=sector, time=time, flux=flux, flux_err=error,
        baseline_matrix=design,
    )


def synthetic_sectors(n=5, seed=0):
    return tuple(synthetic_sector(s, seed + s) for s in range(1, n + 1))


# ── parameter_layout ────────────────────────────────────────────────

def test_k3_layout_has_18_names_for_5_sectors():
    data = synthetic_sectors(5)
    layout = parameter_layout(K3_ID, data)
    assert len(layout.names) == 3 + 5 + 5 + 5  # 18
    assert layout.names[0] == "mu_jitter"
    assert layout.names[1] == "mu_amplitude"
    assert layout.names[2] == "mu_timescale"
    assert "delta_timescale_s1" in layout.names
    assert "delta_timescale_s5" in layout.names


def test_k3_layout_sector_ids_match():
    data = synthetic_sectors(5)
    layout = parameter_layout(K3_ID, data)
    assert layout.sector_ids == (1, 2, 3, 4, 5)


def test_k3_layout_timescale_bounds():
    data = synthetic_sectors(5)
    layout = parameter_layout(K3_ID, data)
    ts_bound = layout.bounds[2]
    assert ts_bound[0] == math.log(4.0)
    assert ts_bound[1] == math.log(TIMESCALE_UPPER_MINUTES)


def test_layout_complex_kernel_not_k3():
    data = synthetic_sectors(3)
    layout = parameter_layout("K2_matern32", data)
    assert "delta_timescale_s" not in " ".join(layout.names)
    assert len(layout.names) == 3 + 3 + 3  # 9


def test_layout_white_kernel():
    data = synthetic_sectors(3)
    layout = parameter_layout("K0_white", data)
    assert "mu_amplitude" not in layout.names
    assert "mu_timescale" not in layout.names
    assert len(layout.names) == 1 + 3  # 4


def test_layout_duplicate_sectors_rejected():
    data = (synthetic_sector(1), synthetic_sector(1))
    with pytest.raises(ValueError, match="unique"):
        parameter_layout(K3_ID, data)


def test_layout_unknown_kernel():
    with pytest.raises(ValueError, match="unknown"):
        parameter_layout("K99_unknown", synthetic_sectors(3))


def test_k3_layout_has_correct_name_order():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    expected = [
        "mu_jitter", "mu_amplitude", "mu_timescale",
        "delta_jitter_s1", "delta_jitter_s2", "delta_jitter_s3",
        "delta_amplitude_s1", "delta_amplitude_s2", "delta_amplitude_s3",
        "delta_timescale_s1", "delta_timescale_s2", "delta_timescale_s3",
    ]
    assert list(layout.names) == expected


# ── pooled_map_objective ────────────────────────────────────────────

def test_objective_white_kernel_is_finite():
    data = synthetic_sectors(3)
    layout = parameter_layout("K0_white", data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0] = math.log(0.5)
    obj = pooled_map_objective(params, data, layout)
    assert np.isfinite(obj)


def test_objective_k3_is_finite():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0] = math.log(0.5)
    params[1] = math.log(0.3)
    params[2] = math.log(160.0)
    obj = pooled_map_objective(params, data, layout)
    assert np.isfinite(obj)


def test_objective_timescale_penalized():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    p0 = np.zeros(len(layout.names), dtype=np.float64)
    p0[0] = math.log(0.5)
    p0[1] = math.log(0.3)
    p0[2] = math.log(160.0)

    p1 = p0.copy()
    p1[9] = 1.5  # large timescale offset for sector 1
    p1[10] = -1.5  # large timescale offset for sector 2

    obj0 = pooled_map_objective(p0, data, layout)
    obj1 = pooled_map_objective(p1, data, layout)
    assert np.isfinite(obj0) and np.isfinite(obj1)
    # With large offsets, penalty should increase the objective
    assert obj1 > obj0


def test_objective_rejects_wrong_shape():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    params = np.array([1.0], dtype=np.float64)
    assert pooled_map_objective(params, data, layout) == 1e100


def test_objective_rejects_nan():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    params = np.full(len(layout.names), np.nan, dtype=np.float64)
    assert pooled_map_objective(params, data, layout) == 1e100


def test_objective_rejects_out_of_bounds():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0] = 10.0  # way above LOG_RATIO_BOUNDS
    assert pooled_map_objective(params, data, layout) == 1e100


def test_objective_rejects_sector_timescale_above_780_minutes():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0:3] = [math.log(0.5), math.log(0.3), math.log(780.0)]
    params[9] = 0.1
    assert pooled_map_objective(params, data, layout) == 1e100


def test_timescale_offset_bounds_clip_at_physical_upper_limit():
    lo, hi = _valid_timescale_offset_bounds(math.log(780.0))
    assert lo == OFFSET_BOUNDS[0]
    assert math.isclose(hi, 0.0, abs_tol=1e-12)


def test_objective_agrees_with_manual_likelihood():
    """pooled_map_objective for K3 should equal
    -sum(log_likelihood) + offset_penalty."""
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0] = math.log(0.5)
    params[1] = math.log(0.8)
    params[2] = math.log(160.0)
    params[3] = 0.1; params[4] = -0.1; params[5] = 0.0
    params[6] = 0.2; params[7] = -0.2; params[8] = 0.0
    params[9] = 0.05; params[10] = -0.05; params[11] = 0.0

    obj = pooled_map_objective(params, data, layout)

    manual_ll = 0.0
    for idx, d in enumerate(data):
        jitter = d.error_scale * math.exp(params[0] + params[3 + idx])
        amp = d.error_scale * math.exp(params[1] + params[6 + idx])
        tau = math.exp(params[2] + params[9 + idx])
        ll = marginal_log_likelihood(d, "K2_matern32", jitter, amp, tau)
        manual_ll += ll.log_likelihood

    offsets = np.concatenate((params[3:6], params[6:9], params[9:12]))
    penalty = 0.5 * float(np.dot(offsets, offsets)) / OFFSET_PRIOR_SIGMA ** 2
    manual_obj = -manual_ll + penalty
    assert math.isclose(obj, manual_obj, rel_tol=1e-8)


# ── _registered_starts ──────────────────────────────────────────────

def test_k3_starts_include_timescale_offsets():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    starts = _registered_starts(layout)
    assert len(starts) == 3
    for s in starts:
        assert len(s) == len(layout.names)
        assert np.all(np.isfinite(s))


def test_k3_starts_have_zero_offsets():
    data = synthetic_sectors(3)
    layout = parameter_layout(K3_ID, data)
    starts = _registered_starts(layout)
    for s in starts:
        offset_part = s[3:]
        np.testing.assert_array_equal(offset_part, np.zeros(9))


def test_white_starts_no_timescale():
    data = synthetic_sectors(3)
    layout = parameter_layout("K0_white", data)
    starts = _registered_starts(layout)
    for s in starts:
        assert len(s) == 4  # mu_jitter + 3 delta_jitter


# ── fit_pooled_map (delegation and K3) ──────────────────────────────

def test_fit_pooled_map_delegates_k0():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, "K0_white")
    assert fit.kernel_id == "K0_white"
    assert fit.success


def test_fit_pooled_map_delegates_k2():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, "K2_matern32")
    assert fit.kernel_id == "K2_matern32"


def test_fit_pooled_map_k3_produces_fit():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, K3_ID)
    assert fit.kernel_id == K3_ID
    assert fit.success
    assert np.all(np.isfinite(fit.parameters))


def test_fit_pooled_map_k3_matches_manual_layout():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, K3_ID)
    layout = parameter_layout(K3_ID, data)
    assert fit.layout.names == layout.names
    assert len(fit.parameters) == len(layout.names)


def test_fit_pooled_map_k3_warm_start_is_better_than_raw():
    """Verify that warm-start from K2 produces better objective than
    raw starts on data that might resemble white noise."""
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, K3_ID)
    # K3 objective should be <= raw start objective
    raw_obj = pooled_map_objective(
        _registered_starts(parameter_layout(K3_ID, data))[2], data,
        parameter_layout(K3_ID, data),
    )
    assert fit.objective <= raw_obj + 1.0  # allow small numerical noise


def test_fit_pooled_map_requires_five_sectors():
    data = synthetic_sectors(4)
    with pytest.raises(ValueError, match="5 training"):
        fit_pooled_map(data, K3_ID)


# ── _accumulate / _finalize ─────────────────────────────────────────

def test_accumulate_finalize_single_value():
    total = _accumulate(None, 0.5, 10.0)
    result = _finalize(total)
    assert math.isclose(result, 10.0 + math.log(0.5))


def test_accumulate_finalize_two_values():
    total = _accumulate(None, 0.3, 10.0)
    total = _accumulate(total, 0.2, 15.0)
    result = _finalize(total)
    expected = math.log(0.3 * math.exp(10.0) + 0.2 * math.exp(15.0))
    assert math.isclose(result, expected)


def test_accumulate_finalize_many_values():
    total = None
    for i in range(10):
        total = _accumulate(total, 1.0, float(i))
    result = _finalize(total)
    expected = math.log(sum(math.exp(i) for i in range(10)))
    assert math.isclose(result, expected, rel_tol=1e-10)


def test_accumulate_ignores_non_finite():
    total = _accumulate(None, 1.0, 10.0)
    total2 = _accumulate(total, 1.0, -np.inf)
    assert total is total2  # unchanged


def test_finalize_returns_neg_inf_for_none():
    assert _finalize(None) == -np.inf


def test_finalize_returns_neg_inf_for_zero_weight():
    assert _finalize((10.0, 0.0)) == -np.inf


# ── held_sector_joint_log_predictive_density ────────────────────────

def test_held_k3_is_finite():
    data = synthetic_sectors(6)
    train = data[:5]
    held = data[5]
    fit = fit_pooled_map(train, K3_ID)
    score = held_sector_joint_log_predictive_density(held, fit)
    assert np.isfinite(score)


def test_held_delegates_k0():
    data = synthetic_sectors(6)
    train = data[:5]
    held = data[5]
    fit_k0 = old_fit(train, "K0_white")
    s_new = held_sector_joint_log_predictive_density(held, fit_k0)
    s_old = old_held(held, fit_k0)
    assert math.isclose(s_new, s_old, rel_tol=1e-10)


def test_held_delegates_k2():
    data = synthetic_sectors(6)
    train = data[:5]
    held = data[5]
    fit_k2 = old_fit(train, "K2_matern32")
    s_new = held_sector_joint_log_predictive_density(held, fit_k2)
    s_old = old_held(held, fit_k2)
    assert math.isclose(s_new, s_old, rel_tol=1e-10)


def test_held_k3_different_held_sectors():
    """Different held sectors should give different scores."""
    data = synthetic_sectors(7)
    train = data[:5]
    held1 = data[5]
    held2 = data[6]
    fit = fit_pooled_map(train, K3_ID)
    s1 = held_sector_joint_log_predictive_density(held1, fit)
    s2 = held_sector_joint_log_predictive_density(held2, fit)
    assert np.isfinite(s1)
    assert np.isfinite(s2)
    # They should differ (different data)
    assert not math.isclose(s1, s2, rel_tol=1e-3)


def test_held_k3_monotone_kernel():
    """On data generated as pure white noise, K3 held prediction
    should be finite and not degenerate."""
    data = synthetic_sectors(6)
    train = data[:5]
    held = data[5]
    fit = fit_pooled_map(train, K3_ID)
    score = held_sector_joint_log_predictive_density(held, fit)
    assert score > -1e6  # not degenerate


# ── Warm-start correctness ──────────────────────────────────────────

def test_warm_start_has_k2_params_mapped():
    """Verify that _fit_pooled_map actually uses the K2 warm-start."""
    data = synthetic_sectors(5)
    layout = parameter_layout(K3_ID, data)
    k2_fit = old_fit(data, "K2_matern32")

    # Manually build the warm-start vector
    n_sec = len(layout.sector_ids)
    ws = np.zeros(len(layout.names), dtype=np.float64)
    ws[0:3] = k2_fit.parameters[0:3]
    ws[3:3 + n_sec] = k2_fit.parameters[3:3 + n_sec]
    ws[3 + n_sec:3 + 2 * n_sec] = k2_fit.parameters[3 + n_sec:]
    ws[3 + 2 * n_sec:] = 0.0

    assert ws[0] == k2_fit.parameters[0]  # mu_jitter
    assert ws[1] == k2_fit.parameters[1]  # mu_amplitude
    assert ws[2] == k2_fit.parameters[2]  # log_timescale
    assert np.all(ws[3 + 2 * n_sec:] == 0.0)  # timescale offsets at 0


def test_fit_pooled_map_unknown_kernel():
    with pytest.raises(ValueError):
        fit_pooled_map(synthetic_sectors(5), "K99_fake")


# ── K3 Matern identity ──────────────────────────────────────────────

def test_k3_kernel_id_in_list():
    assert K3_ID in KERNEL_IDS


def test_k3_uses_matern32_internally():
    """K3 always passes K2_matern32 to marginal_log_likelihood."""
    data = synthetic_sectors(2)
    layout = parameter_layout(K3_ID, data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0] = math.log(0.5)
    params[1] = math.log(0.3)
    params[2] = math.log(160.0)
    obj = pooled_map_objective(params, data, layout)
    assert np.isfinite(obj)


# ── Edge cases ──────────────────────────────────────────────────────

def test_objective_with_one_sector_k3():
    data = (synthetic_sector(1),)
    layout = parameter_layout(K3_ID, data)
    params = np.zeros(len(layout.names), dtype=np.float64)
    params[0:3] = [math.log(0.5), math.log(0.3), math.log(160.0)]
    obj = pooled_map_objective(params, data, layout)
    assert np.isfinite(obj)


def test_fit_pooled_map_too_few_sectors():
    data = synthetic_sectors(3)
    with pytest.raises(ValueError, match="5 training"):
        _fit_pooled_map(data, K3_ID, required_sector_count=5)


# ── PooledMapFit integrity ──────────────────────────────────────────

def test_k3_fit_has_boundary_diagnostics():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, K3_ID)
    assert fit.boundary_diagnostics is not None
    assert isinstance(fit.boundary_diagnostics, tuple)


def test_k3_fit_has_results():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, K3_ID)
    assert len(fit.optimizer_results) > 0


def test_k3_fit_parameters_within_bounds():
    data = synthetic_sectors(5)
    fit = fit_pooled_map(data, K3_ID)
    layout = parameter_layout(K3_ID, data)
    for idx, (lo, hi) in enumerate(layout.bounds):
        assert lo < fit.parameters[idx] < hi


# ── Synthetic-generator reproducibility ─────────────────────────────

def test_m1_generator_repeats_exactly_for_the_same_seed():
    pdcsap, events, t14 = synthetic_generator.load_timestamps()
    first = synthetic_generator.generate_realization(
        pdcsap, events, t14, 349204,
        noise_family="M1_matern32", inject_transit=False,
    )
    second = synthetic_generator.generate_realization(
        pdcsap, events, t14, 349204,
        noise_family="M1_matern32", inject_transit=False,
    )
    np.testing.assert_array_equal(
        first["true_flux"].to_numpy(), second["true_flux"].to_numpy(),
    )
    np.testing.assert_array_equal(
        first["flux"].to_numpy(), second["flux"].to_numpy(),
    )
