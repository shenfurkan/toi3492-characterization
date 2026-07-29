"""V2 synthetic-data context and one-shared-realization generator.

This module has its own protocol and input checks.  It does not read the
quarantined v1 checkpoints or CSV artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

import run_faz5b_remediation as phase5b
import stage3_synthetic_calibration_core as legacy_helpers
import stage3_synthetic_generator as generator


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v2.json"
ARCHITECTURE_PATH = ROOT / "data" / "stage3_model_architecture_decision_v2.json"
PHASE2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
PHASE4_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"
PHASE5B_PROTOCOL_PATH = ROOT / "data" / "faz5b_preregistered_handoff.json"
PHASE5B_RESULT_PATH = ROOT / "outputs" / "faz5b_remediation.json"
VALIDATION_PATH = ROOT / "data" / "faz6_common_validation_keys.csv"
LEDGER_PATH = ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz"
INPUT_MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest.json"
SECTORS = (37, 63, 64, 90, 99, 100)
BASELINE_SIGMA = 0.01


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seed_stream(realization_seed, stream):
    sequence = np.random.SeedSequence([int(realization_seed), int(stream)])
    return np.random.default_rng(sequence)


def realization_seed(protocol, class_spec, realization_index):
    return (
        int(protocol["deterministic_seeds"]["base_seed"])
        + int(class_spec["class_index"]) * 10000
        + int(realization_index) * 100
    )


def _all_events(phase2):
    return tuple(
        {
            "physical_event_id": item["physical_event_id"],
            "sector": int(item["sector"]),
            "epoch": int(item["epoch"]),
            "midpoint_btjd": float(item["predicted_midpoint_btjd"]),
            "used": bool(item["used"]),
        }
        for item in phase2["events"]
    )


@dataclass(frozen=True)
class CalibrationContextV2:
    protocol: dict
    protocol_sha256: str
    architecture_sha256: str
    input_manifest_sha256: str
    phase2: dict
    events: Tuple[dict, ...]
    complete_events: Tuple[dict, ...]
    gap_edge_events: Tuple[dict, ...]
    raw_template: pd.DataFrame
    reference_keys: pd.MultiIndex
    validation: pd.DataFrame
    branches: Tuple[dict, ...]

    def events_for_class(self, class_spec):
        if class_spec.get("event_coverage", {}).get("mode") == "partial_gap_edge":
            return self.events
        return self.complete_events


def _build_context():
    protocol = _load_json(PROTOCOL_PATH)
    architecture = _load_json(ARCHITECTURE_PATH)
    phase2 = _load_json(PHASE2_PATH)
    phase4 = _load_json(PHASE4_PATH)
    phase5b_protocol = _load_json(PHASE5B_PROTOCOL_PATH)
    phase5b_report = _load_json(PHASE5B_RESULT_PATH)
    raw, reference, _, checks, _, complete_events = phase5b.load_cadence_masks(
        phase5b_protocol, phase2, phase4,
    )
    if not all(checks.values()):
        raise RuntimeError("frozen Phase-5B mask contract failed")

    telemetry = pd.read_csv(
        LEDGER_PATH, usecols=["sector", "cadenceno", "sap_bkg"],
    )
    if telemetry.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("ledger telemetry cadence keys are not unique")
    raw = raw.merge(
        telemetry, on=["sector", "cadenceno"], how="left", validate="one_to_one",
    )
    if raw["sap_bkg"].isna().any():
        raise RuntimeError("raw mask cannot be joined to SAP_BKG telemetry")
    for column in ("crowdsap", "flfrcsap"):
        if column not in raw.columns or raw[column].isna().any():
            raise RuntimeError("v2 C13 telemetry column is unavailable: {}".format(column))

    validation = pd.read_csv(VALIDATION_PATH)
    if validation.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("frozen held validation keys are not unique")
    events = _all_events(phase2)
    complete = tuple(event for event in events if event["used"])
    gap_edge = tuple(event for event in events if not event["used"])
    if len(events) != 18 or len(complete) != 16 or len(gap_edge) != 2:
        raise RuntimeError("v2 event inventory is not 16 complete plus 2 gap/edge events")
    if tuple(sorted((event["sector"], event["epoch"]) for event in gap_edge)) != (
        (37, 2), (99, 189),
    ):
        raise RuntimeError("v2 gap/edge event identities changed")
    if len(protocol["simulation_classes"]) != 14 or protocol["requested_total"] != 235:
        raise RuntimeError("v2 class universe is not the frozen 14/235 contract")
    if tuple(complete_events) != tuple({key: event[key] for key in (
            "physical_event_id", "sector", "epoch", "midpoint_btjd"
        )} for event in complete):
        raise RuntimeError("Phase-5B complete event identity differs from Phase-2")

    return CalibrationContextV2(
        protocol=protocol,
        protocol_sha256=_sha256(PROTOCOL_PATH),
        architecture_sha256=_sha256(ARCHITECTURE_PATH),
        input_manifest_sha256=_sha256(INPUT_MANIFEST_PATH),
        phase2=phase2,
        events=events,
        complete_events=complete,
        gap_edge_events=gap_edge,
        raw_template=raw.sort_values(["sector", "cadenceno"]).reset_index(drop=True),
        reference_keys=pd.MultiIndex.from_frame(reference[["sector", "cadenceno"]]),
        validation=validation.sort_values(["sector", "cadenceno"]).reset_index(drop=True),
        branches=legacy_helpers._build_branches(phase5b_report),
    )


def load_context():
    return _build_context()


def _draw_geometry(class_spec, seed):
    if not class_spec["inject_transit"]:
        return None
    geometry = class_spec["geometry_injection"]
    rng = _seed_stream(seed, 1)
    values = {
        name: float(rng.uniform(*geometry[name]["bounds"]))
        for name in ("rp_rs", "a_rs", "impact_parameter")
    }
    if values["impact_parameter"] >= 1.0 + values["rp_rs"]:
        raise RuntimeError("generated impact parameter violates transit constraint")
    if values["impact_parameter"] >= values["a_rs"]:
        raise RuntimeError("generated impact parameter exceeds a/Rstar")
    return values


def _noise_kwargs(class_spec):
    params = class_spec["noise_parameters"]
    return {
        "noise_family": class_spec["noise_family"],
        "mu_jitter": float(params["mu_jitter_ratio"]),
        "jitter_sigma": float(params["jitter_offset_sigma"]),
        "mu_amplitude": float(params["mu_amplitude_ratio"] or 0.0),
        "amp_sigma": float(params["amplitude_offset_sigma"] or 0.0),
        "mu_log_tau": float(params["mu_log_timescale"] or math.log(160.0)),
        "tau_sigma": float(params["timescale_offset_sigma"] or 0.0),
        "timescale_bounds": (
            float(params.get("timescale_lower_minutes") or 4.0),
            float(params.get("timescale_upper_minutes") or 780.0),
        ),
    }


def _inject_telemetry_systematic(frame, class_spec, seed):
    systematic = class_spec.get("systematic_injection")
    if systematic is None:
        return None
    telemetry_name = str(systematic["telemetry"]).lower()
    column = {"sap_bkg": "sap_bkg", "crowdsap": "crowdsap"}.get(telemetry_name)
    if column is None or column not in frame.columns:
        raise RuntimeError("unsupported v2 telemetry column: {}".format(telemetry_name))
    bounds_key = "slope_ppm_per_unit" if "slope_ppm_per_unit" in systematic else "slope_ppm_per_e_per_s"
    low, high = systematic[bounds_key]
    rng = _seed_stream(seed, 2)
    slope = float(rng.uniform(float(low), float(high)))
    values = frame[column].to_numpy(np.float64).copy()
    sectors = frame["sector"].to_numpy(np.int64)
    for sector in SECTORS:
        selected = sectors == sector
        values[selected] -= np.median(values[selected])
    contribution = slope * values
    frame["noise_flux"] += contribution
    frame["true_flux"] += contribution
    frame["flux"] += contribution
    return {"telemetry": str(systematic["telemetry"]), "column": column, "slope": slope}


def generate_latent_realization(context, class_spec, realization_index):
    seed = realization_seed(context.protocol, class_spec, realization_index)
    geometry = _draw_geometry(class_spec, seed)
    noise_seed = int(_seed_stream(seed, 0).integers(0, np.iinfo(np.uint32).max))
    frame, metadata = generator.generate_realization(
        context.raw_template,
        context.events_for_class(class_spec),
        float(context.phase2["ephemeris_and_windows"]["t14_hours"]),
        noise_seed,
        inject_transit=bool(class_spec["inject_transit"]),
        rp_rs=geometry["rp_rs"] if geometry else 0.0,
        a_rs=geometry["a_rs"] if geometry else 10.2,
        impact_parameter=geometry["impact_parameter"] if geometry else 0.73,
        return_metadata=True,
        **_noise_kwargs(class_spec),
    )
    telemetry = _inject_telemetry_systematic(frame, class_spec, seed)
    shared_draws = legacy_helpers._inject_shared_event_baseline(
        frame, context.events_for_class(class_spec), seed,
    )
    frame["flux"] = (
        frame["transit_flux"] * (1.0 + frame.get("shared_baseline", 0.0))
        + frame["noise_flux"] + frame["measurement_noise"]
    )
    metadata.update({
        "class_name": class_spec["name"],
        "class_index": int(class_spec["class_index"]),
        "realization_index": int(realization_index),
        "realization_seed": int(seed),
        "noise_seed": int(noise_seed),
        "drawn_geometry": geometry,
        "telemetry_systematic": telemetry,
        "shared_baseline_draws": shared_draws,
        "event_ids": [event["physical_event_id"] for event in context.events_for_class(class_spec)],
    })
    return frame, metadata


def apply_branch_baseline(latent, events, branch, realization_seed_value):
    """Return the same latent frame for every branch and mask."""
    return latent.copy(), {}


def derive_mask(frame, context, mask_id):
    return legacy_helpers.derive_mask(frame, context, mask_id)


def source_metadata(context):
    return {
        "calibration_protocol": {
            "path": "data/stage3_synthetic_calibration_protocol_v2.json",
            "sha256": context.protocol_sha256,
        },
        "architecture": {
            "path": "data/stage3_model_architecture_decision_v2.json",
            "sha256": context.architecture_sha256,
        },
        "input_manifest": {
            "path": "data/stage3_input_manifest.json",
            "sha256": context.input_manifest_sha256,
        },
        "raw_template_rows": int(len(context.raw_template)),
        "reference_template_rows": int(len(context.reference_keys)),
        "branch_count": int(len(context.branches)),
        "complete_event_count": int(len(context.complete_events)),
        "gap_edge_event_count": int(len(context.gap_edge_events)),
        "sectors": list(SECTORS),
    }
