"""Conditional geometry recovery and null-hypothesis evaluation."""

from __future__ import annotations

from typing import Mapping

import numpy as np

from .compat import ensure_legacy_imports
from .contracts import BranchSpec, ContractError
from .inputs import Stage3Inputs

ensure_legacy_imports()

import run_faz5_window_grid as phase5
import stage3_joint_model as joint


def _legacy_branch(branch: BranchSpec):
    return {
        "model_index": branch.ordinal,
        "model_id": branch.model_id,
        "mask_id": branch.mask_id,
        "cell_id": branch.cell_id,
        "window_hours": branch.window_hours,
        "polynomial_degree": branch.polynomial_degree,
        "joint_model_weight": branch.joint_model_weight,
    }


GEOMETRY_BOUNDARY_FRACTION = 0.01


def boundary_count(diagnostics) -> int:
    return int(sum(diagnostic.at_boundary for diagnostic in diagnostics))


def geometry_boundary_count(architecture: Mapping, recovered: Mapping) -> int:
    """Count recovered geometry values sitting at the frozen uniform bounds."""
    bounds = architecture["candidate"]["transit_model"]["geometry_uniform_bounds"]
    count = 0
    for name in ("rp_rs", "a_rs", "impact_parameter"):
        lower, upper = (float(bound) for bound in bounds[name])
        margin = GEOMETRY_BOUNDARY_FRACTION * (upper - lower)
        value = float(recovered[name])
        if value - lower <= margin or upper - value <= margin:
            count += 1
    return count


def conditional_geometry_recovery(
    inputs: Stage3Inputs,
    class_spec: Mapping,
    latent,
    metadata: Mapping,
    branch: BranchSpec,
    mask=None,
):
    """Recover geometry conditional on the OOT-fitted noise MAP.

    This is intentionally not called a 24-parameter joint fit: only geometry is
    optimized in the full event windows after the noise parameters are trained
    out of transit.
    """
    mask = inputs.mask(latent, branch.mask_id) if mask is None else mask
    events = tuple(
        event.as_legacy_mapping()
        for event in inputs.events_for_class(class_spec)
    )
    laplace_seed = (
        int(metadata["realization_seed"])
        + 1000000
        + branch.ordinal
    )
    branch_mapping = _legacy_branch(branch)
    h1 = joint.fit_joint_map(
        branch_mapping,
        mask,
        events,
        inputs.phase2,
        inputs.architecture,
        laplace_seed,
        require_stationarity=True,
        expected_event_count=len(events),
        use_v2_starts=True,
    )
    h0 = joint.fit_joint_null_map(
        branch_mapping,
        mask,
        events,
        inputs.architecture,
        expected_event_count=len(events),
        noise_parameters=h1["noise_parameters"],
    )
    if not h1.get("success") or not h1.get("stationary") or not h0.get("success"):
        raise ContractError("mandatory H0/H1 recovery did not converge")
    objective_h1 = float(h1["objective"])
    objective_h0 = float(h0["objective"])
    if not np.isfinite(objective_h1) or not np.isfinite(objective_h0):
        raise ContractError("H0/H1 objective is non-finite")
    injected = metadata["drawn_geometry"]
    injected_t14 = None
    if injected is not None:
        injected_t14 = float(phase5.duration_hours([[
            injected["rp_rs"], injected["a_rs"], injected["impact_parameter"],
        ]], float(inputs.architecture["candidate"]["transit_model"]["period_days_fixed"]))[0])
    recovered = h1["recovered_geometry"]
    recovered_t14 = float(phase5.duration_hours([[
        recovered["rp_rs"], recovered["a_rs"], recovered["impact_parameter"],
    ]], float(inputs.architecture["candidate"]["transit_model"]["period_days_fixed"]))[0])
    event_coverage = h1["event_coverage"]
    gap_coverage = {
        event.event_id: bool(event_coverage.get(event.event_id, 0))
        for event in inputs.gap_edge_events
        if event in inputs.events_for_class(class_spec)
    }
    diagnostics = h1["residual_diagnostics"]
    return {
        "model_id": branch.model_id,
        "mask_id": branch.mask_id,
        "cell_id": branch.cell_id,
        "joint_model_weight": branch.joint_model_weight,
        "objective_h0": objective_h0,
        "objective_h1": objective_h1,
        "delta_map": objective_h0 - objective_h1,
        "recovery_mode": "conditional_geometry_with_fixed_oot_noise",
        "recovered_geometry": {**recovered, "t14_hours": recovered_t14},
        "injected_geometry": (
            None if injected is None else {**injected, "t14_hours": injected_t14}
        ),
        "intervals": h1["intervals"],
        "noise_boundary_count": boundary_count(h1["boundary_diagnostics"]),
        "geometry_boundary_count": geometry_boundary_count(
            inputs.architecture, recovered,
        ),
        "gap_edge_coverage": gap_coverage,
        "optimizer_no_op_count": int(diagnostics["optimizer_no_op_count"]),
        "optimizer_local_mode_count": int(diagnostics["optimizer_local_mode_count"]),
        "max_abs_standardized_residual": float(diagnostics["weighted_residual_beta_max"]),
        "ingress_egress_rms_relative_flux": float(
            diagnostics["ingress_egress_rms_residual_mm_s"] / 1e3
        ),
    }
