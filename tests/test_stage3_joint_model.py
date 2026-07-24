"""Structural tests for the S3 24-parameter joint transit/noise model."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import stage3_joint_model as joint
import stage3_synthetic_calibration_core as core
import stage3_noise_core as noise


@pytest.fixture(scope="module")
def prepared_model():
    context = core.load_context()
    spec = next(item for item in context.protocol["simulation_classes"]
                if item["name"] == "C02_m1_160_transit")
    latent, metadata = core.generate_latent_realization(context, spec, 0)
    branch = context.branches[0]
    branch_frame, _ = core.apply_branch_baseline(
        latent, context.events, branch, metadata["realization_seed"],
    )
    mask = core.derive_mask(branch_frame, context, branch["mask_id"])
    decision = json.loads((ROOT / "data" / "stage3_model_architecture_decision.json").read_text(encoding="utf-8"))
    return joint.build_joint_model(branch, mask, context.events, decision), spec


def test_joint_model_has_frozen_24_parameter_structure(prepared_model):
    model, _ = prepared_model
    assert len(model.parameter_names) == 24
    assert model.parameter_names[:3] == joint.GEOMETRY_NAMES
    assert len(model.noise_layout.names) == 21
    assert tuple(item.sector for item in model.sectors) == joint.SECTORS


def test_joint_model_builds_transit_adjusted_sector_data(prepared_model):
    model, spec = prepared_model
    geometry = [0.055, 10.2, 0.73]
    data, transits = model.sector_data(geometry)
    assert len(data) == 6
    assert len(transits) == 6
    assert all(np.all(np.isfinite(item.flux)) for item in data)
    assert all(item.baseline_matrix.shape[0] == len(item.time) for item in data)


def test_joint_objective_is_finite_at_registered_noise_start(prepared_model):
    model, _ = prepared_model
    start = noise._registered_starts(model.noise_layout)[0]
    parameters = np.concatenate(([0.055, 10.2, 0.73], start))
    value = model.objective(parameters)
    assert np.isfinite(value)
    assert value < 1e100


def test_joint_model_rejects_invalid_transit_geometry(prepared_model):
    model, _ = prepared_model
    assert model.transit([0.055, 10.2, 11.0]) is None
