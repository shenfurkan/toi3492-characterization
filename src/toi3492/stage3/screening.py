"""Branch preparation and leave-one-sector-out screening."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np

from .compat import ensure_legacy_imports
from .contracts import BranchSpec, ContractError, SECTORS
from .inputs import Stage3Inputs

ensure_legacy_imports()

import run_faz5_window_grid as phase5
import run_faz6_noise_models as phase6
import stage3_noise_core as noise


@dataclass(frozen=True)
class PreparedScreeningBranch:
    branch: BranchSpec
    training: Mapping
    held: Mapping
    gap_edge_coverage: Mapping[str, bool]


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


def prepare_branch(
    inputs: Stage3Inputs,
    class_spec: Mapping,
    latent,
    branch: BranchSpec,
    mask=None,
) -> PreparedScreeningBranch:
    mask = inputs.mask(latent, branch.mask_id) if mask is None else mask
    usable_events = []
    gap_coverage = {}
    for event in inputs.events_for_class(class_spec):
        rows = phase5.event_rows(
            mask,
            event.as_legacy_mapping(),
            branch.window_hours / 48.0,
        )
        if rows.empty:
            if event.complete:
                raise ContractError("complete event has no screening cadence: {}".format(event.event_id))
            gap_coverage[event.event_id] = False
            continue
        usable_events.append(event.as_legacy_mapping())
        if not event.complete:
            gap_coverage[event.event_id] = True
    training, held = phase6.build_model_sector_data(
        mask,
        inputs.validation,
        tuple(usable_events),
        inputs.phase2,
        _legacy_branch(branch),
    )
    return PreparedScreeningBranch(branch, training, held, gap_coverage)


def boundary_count(fit) -> int:
    return int(sum(diagnostic.at_boundary for diagnostic in fit.boundary_diagnostics))


def score_fold(prepared: PreparedScreeningBranch, held_sector: int) -> Mapping:
    if held_sector not in SECTORS:
        raise ContractError("unknown held sector: {}".format(held_sector))
    training = tuple(
        prepared.training[sector]
        for sector in SECTORS
        if sector != held_sector
    )
    fit_k0 = noise.fit_pooled_map(training, "K0_white")
    if not fit_k0.success:
        raise ContractError("K0 screening fit failed")
    fit_m1 = noise.fit_pooled_map(
        training,
        "K3_MATERN32_SECTOR",
        use_warm_start=True,
        warm_start_fit=fit_k0,
    )
    if not fit_m1.success:
        raise ContractError("M1 screening fit failed")
    score_k0 = noise.held_sector_joint_log_predictive_density(
        prepared.held[held_sector], fit_k0,
    )
    score_m1 = noise.held_sector_joint_log_predictive_density(
        prepared.held[held_sector], fit_m1,
    )
    if not np.isfinite(score_k0) or not np.isfinite(score_m1):
        raise ContractError("screening score is non-finite")
    return {
        "model_id": prepared.branch.model_id,
        "mask_id": prepared.branch.mask_id,
        "cell_id": prepared.branch.cell_id,
        "joint_model_weight": prepared.branch.joint_model_weight,
        "held_sector": int(held_sector),
        "k0_score": float(score_k0),
        "m1_score": float(score_m1),
        "delta_elpd": float(score_m1 - score_k0),
        "k0_objective": float(fit_k0.objective),
        "m1_objective": float(fit_m1.objective),
        "k0_boundary_count": boundary_count(fit_k0),
        "m1_boundary_count": boundary_count(fit_m1),
        "gap_edge_coverage": dict(prepared.gap_edge_coverage),
    }
