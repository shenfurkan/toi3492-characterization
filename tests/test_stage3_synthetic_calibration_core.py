"""Protocol-contract tests for the S3-04B synthetic calibration core."""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import stage3_synthetic_calibration_core as core
import run_faz6_noise_models as phase6


@pytest.fixture(scope="module")
def context():
    return core.load_context()


def class_by_name(context, name):
    return next(item for item in context.protocol["simulation_classes"]
                if item["name"] == name)


def test_context_matches_frozen_12_class_210_realization_contract(context):
    assert len(context.protocol["simulation_classes"]) == 12
    assert context.protocol["requested_total"] == 210
    assert sum(item["requested_count"]
               for item in context.protocol["simulation_classes"]) == 210
    assert len(context.branches) == 24
    assert {item["mask_id"] for item in context.branches} == {
        "raw_valid", "reference_included",
    }


def test_realization_seed_follows_frozen_formula(context):
    c01 = class_by_name(context, "C01_white_jitter_transit")
    c02 = class_by_name(context, "C02_m1_160_transit")
    assert core.realization_seed(context.protocol, c01, 0) == 349204
    assert core.realization_seed(context.protocol, c02, 0) == 359204
    assert core.realization_seed(context.protocol, c02, 7) == 359904


def test_latent_m1_realization_is_exactly_reproducible(context):
    spec = class_by_name(context, "C02_m1_160_transit")
    first, first_meta = core.generate_latent_realization(context, spec, 0)
    second, second_meta = core.generate_latent_realization(context, spec, 0)
    assert first_meta == second_meta
    for column in ("noise_flux", "transit_flux", "measurement_noise", "flux"):
        np.testing.assert_array_equal(
            first[column].to_numpy(), second[column].to_numpy(),
        )


def test_latent_geometry_uses_frozen_uniform_bounds(context):
    spec = class_by_name(context, "C02_m1_160_transit")
    _, metadata = core.generate_latent_realization(context, spec, 1)
    geometry = metadata["drawn_geometry"]
    frozen = spec["geometry_injection"]
    for name in ("rp_rs", "a_rs", "impact_parameter"):
        lo, hi = frozen[name]["bounds"]
        assert lo <= geometry[name] <= hi
    assert geometry["impact_parameter"] < 1.0 + geometry["rp_rs"]
    assert geometry["impact_parameter"] < geometry["a_rs"]


def test_masks_are_derived_from_one_latent_realization(context):
    spec = class_by_name(context, "C01_white_jitter_transit")
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    raw = core.derive_mask(latent, context, "raw_valid")
    reference = core.derive_mask(latent, context, "reference_included")
    assert len(raw) == 102562
    assert len(reference) == 102502
    merged = reference.merge(
        raw[["sector", "cadenceno", "flux"]],
        on=["sector", "cadenceno"], suffixes=("_reference", "_raw"),
        validate="one_to_one",
    )
    np.testing.assert_array_equal(
        merged["flux_reference"].to_numpy(), merged["flux_raw"].to_numpy(),
    )


def test_branch_baselines_are_deterministic_and_branch_specific(context):
    spec = class_by_name(context, "C02_m1_160_transit")
    latent, metadata = core.generate_latent_realization(context, spec, 2)
    first_branch = context.branches[0]
    second_branch = context.branches[1]
    first_a, draws_a = core.apply_branch_baseline(
        latent, context.events, first_branch, metadata["realization_seed"],
    )
    first_b, draws_b = core.apply_branch_baseline(
        latent, context.events, first_branch, metadata["realization_seed"],
    )
    second, _ = core.apply_branch_baseline(
        latent, context.events, second_branch, metadata["realization_seed"],
    )
    assert draws_a == draws_b
    np.testing.assert_array_equal(first_a["flux"].to_numpy(), first_b["flux"].to_numpy())
    assert not np.array_equal(first_a["branch_baseline"].to_numpy(),
                              second["branch_baseline"].to_numpy())


def test_c10_background_systematic_is_recorded(context):
    spec = class_by_name(context, "C10_background_correlated")
    _, metadata = core.generate_latent_realization(context, spec, 0)
    systematic = metadata["telemetry_systematic"]
    lo, hi = spec["systematic_injection"]["slope_ppm_per_e_per_s"]
    assert systematic["telemetry"] == "SAP_BKG"
    assert lo <= systematic["slope"] <= hi


def test_no_transit_class_keeps_unity_transit_component(context):
    spec = class_by_name(context, "C11_no_transit_null")
    frame, metadata = core.generate_latent_realization(context, spec, 0)
    assert metadata["drawn_geometry"] is None
    np.testing.assert_array_equal(frame["transit_flux"].to_numpy(),
                                  np.ones(len(frame)))


def test_injected_timescales_respect_the_frozen_physical_support(context):
    for class_name in ("C05_m1_720_boundary", "C12_near_boundary_tau4"):
        spec = class_by_name(context, class_name)
        _, metadata = core.generate_latent_realization(context, spec, 0)
        for draw in metadata["sector_draws"].values():
            assert 4.0 <= draw["timescale_minutes"] <= 780.0


def test_branch_mask_builds_the_frozen_six_sector_loso_inputs(context):
    spec = class_by_name(context, "C02_m1_160_transit")
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    branch = context.branches[0]
    branch_frame, _ = core.apply_branch_baseline(
        latent, context.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])
    training, held = phase6.build_model_sector_data(
        mask, context.validation, context.events, context.phase2, branch,
    )
    assert tuple(training) == core.SECTORS
    assert tuple(held) == core.SECTORS
    assert sum(len(item.time) for item in held.values()) == 2233
