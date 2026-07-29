"""Frozen input loading behind a narrow Stage-3 adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Tuple

import numpy as np
import pandas as pd

import run_faz5b_remediation as phase5b

from .contracts import BranchSpec, ContractError, RunSpec, SECTORS
from .jsonio import load_strict_json


@dataclass(frozen=True)
class EventSpec:
    event_id: str
    sector: int
    epoch: int
    midpoint_btjd: float
    complete: bool

    def as_legacy_mapping(self) -> Mapping:
        return {
            "physical_event_id": self.event_id,
            "sector": self.sector,
            "epoch": self.epoch,
            "midpoint_btjd": self.midpoint_btjd,
            "used": self.complete,
        }


@dataclass(frozen=True)
class Stage3Inputs:
    spec: RunSpec
    protocol: Mapping
    architecture: Mapping
    phase2: Mapping
    raw_template: pd.DataFrame
    reference_keys: pd.MultiIndex
    validation: pd.DataFrame
    events: Tuple[EventSpec, ...]
    branches: Tuple[BranchSpec, ...]

    @property
    def complete_events(self) -> Tuple[EventSpec, ...]:
        return tuple(event for event in self.events if event.complete)

    @property
    def gap_edge_events(self) -> Tuple[EventSpec, ...]:
        return tuple(event for event in self.events if not event.complete)

    def events_for_class(self, class_spec: Mapping) -> Tuple[EventSpec, ...]:
        mode = class_spec.get("event_coverage", {}).get("mode")
        return self.events if mode == "partial_gap_edge" else self.complete_events

    def mask(self, latent: pd.DataFrame, mask_id: str) -> pd.DataFrame:
        if mask_id == "raw_valid":
            return latent
        if mask_id != "reference_included":
            raise ContractError("unknown cadence mask: {}".format(mask_id))
        keys = pd.MultiIndex.from_frame(latent[["sector", "cadenceno"]])
        result = latent.loc[keys.isin(self.reference_keys)].copy()
        if len(result) != len(self.reference_keys):
            raise ContractError("reference mask is not an exact raw-valid subset")
        return result.reset_index(drop=True)


def _load_json(path):
    return load_strict_json(path)


def _parse_cell(cell_id: str):
    match = re.fullmatch(r"W(\d+)_P([012])", str(cell_id))
    if match is None:
        raise ContractError("invalid Phase-5B cell identifier: {}".format(cell_id))
    return int(match.group(1)), int(match.group(2))


def _branches(report: Mapping) -> Tuple[BranchSpec, ...]:
    branches = []
    for mask_id in ("raw_valid", "reference_included"):
        record = report["branches"][mask_id]
        for cell_id in record["retained_cell_ids"]:
            window_hours, degree = _parse_cell(cell_id)
            conditional = float(record["conditional_weights"][cell_id])
            branches.append(BranchSpec(
                ordinal=len(branches),
                model_id="{}::{}".format(mask_id, cell_id),
                mask_id=mask_id,
                cell_id=cell_id,
                window_hours=window_hours,
                polynomial_degree=degree,
                joint_model_weight=0.5 * conditional,
            ))
    if len(branches) != 24:
        raise ContractError("Phase-5B branch universe is not 24")
    return tuple(branches)


def load_inputs(spec: RunSpec) -> Stage3Inputs:
    root = spec.root
    protocol = _load_json(spec.protocol_path)
    architecture = _load_json(spec.architecture_path)
    phase2 = _load_json(root / "outputs" / "faz2_transit_inventory.json")
    phase4 = _load_json(root / "outputs" / "faz4_reduction_comparison.json")
    phase5b_protocol = _load_json(root / "data" / "faz5b_preregistered_handoff.json")
    phase5b_report = _load_json(root / "outputs" / "faz5b_remediation.json")
    raw, reference, _, checks, _, complete_event_mappings = phase5b.load_cadence_masks(
        phase5b_protocol, phase2, phase4,
    )
    if not all(checks.values()):
        raise ContractError("frozen Phase-5B cadence-mask contract failed")
    telemetry = pd.read_csv(
        root / "data" / "toi3492_cadence_ledger_120s.csv.gz",
        usecols=["sector", "cadenceno", "sap_bkg"],
    )
    raw = raw.merge(
        telemetry,
        on=["sector", "cadenceno"],
        how="left",
        validate="one_to_one",
    )
    required_telemetry = ("sap_bkg", "crowdsap", "flfrcsap")
    if any(column not in raw or raw[column].isna().any() for column in required_telemetry):
        raise ContractError("required Stage-3 telemetry is unavailable")
    validation = pd.read_csv(root / "data" / "faz6_common_validation_keys.csv")
    if validation.duplicated(["sector", "cadenceno"]).any():
        raise ContractError("validation cadence keys are not unique")
    events = tuple(EventSpec(
        event_id=item["physical_event_id"],
        sector=int(item["sector"]),
        epoch=int(item["epoch"]),
        midpoint_btjd=float(item["predicted_midpoint_btjd"]),
        complete=bool(item["used"]),
    ) for item in phase2["events"])
    if len(events) != 18 or len([event for event in events if event.complete]) != 16:
        raise ContractError("event universe is not 16 complete plus 2 gap/edge events")
    expected_complete = {
        (item["physical_event_id"], int(item["sector"]), int(item["epoch"]))
        for item in complete_event_mappings
    }
    actual_complete = {
        (event.event_id, event.sector, event.epoch)
        for event in events if event.complete
    }
    if actual_complete != expected_complete:
        raise ContractError("Phase-2 and Phase-5B complete-event identities differ")
    if tuple(sorted({event.sector for event in events})) != SECTORS:
        raise ContractError("event sectors differ from the six-sector contract")
    reference_keys = pd.MultiIndex.from_frame(reference[["sector", "cadenceno"]])
    return Stage3Inputs(
        spec=spec,
        protocol=protocol,
        architecture=architecture,
        phase2=phase2,
        raw_template=raw.sort_values(["sector", "cadenceno"]).reset_index(drop=True),
        reference_keys=reference_keys,
        validation=validation.sort_values(["sector", "cadenceno"]).reset_index(drop=True),
        events=events,
        branches=_branches(phase5b_report),
    )
