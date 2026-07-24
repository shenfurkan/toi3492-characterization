"""Frozen-protocol inputs and latent simulations for S3-04B.

This module deliberately separates one deterministic latent realization from
the Phase-5B mask and branch projections derived from it. It never reads the
observed flux column as a simulation input.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

import run_faz5b_remediation as phase5b
import stage3_synthetic_generator as generator


ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_PROTOCOL_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol.json"
PHASE2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
PHASE4_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"
PHASE5B_PROTOCOL_PATH = ROOT / "data" / "faz5b_preregistered_handoff.json"
PHASE5B_RESULT_PATH = ROOT / "outputs" / "faz5b_remediation.json"
VALIDATION_PATH = ROOT / "data" / "faz6_common_validation_keys.csv"
LEDGER_PATH = ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz"
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


def _parse_cell(cell_id):
    match = re.fullmatch(r"W(\d+)_P([012])", str(cell_id))
    if match is None:
        raise ValueError("invalid frozen Phase-5B cell identifier: {}".format(cell_id))
    return int(match.group(1)), int(match.group(2))


def _build_branches(report):
    branches = []
    for mask_id in ("raw_valid", "reference_included"):
        record = report["branches"][mask_id]
        cells = tuple(record["retained_cell_ids"])
        conditional = record["conditional_weights"]
        for cell_id in cells:
            window_hours, degree = _parse_cell(cell_id)
            branches.append({
                "model_index": len(branches),
                "model_id": "{}::{}".format(mask_id, cell_id),
                "mask_id": mask_id,
                "cell_id": cell_id,
                "window_hours": window_hours,
                "polynomial_degree": degree,
                "conditional_model_weight": float(conditional[cell_id]),
                "joint_model_weight": 0.5 * float(conditional[cell_id]),
            })
    if len(branches) != 24:
        raise RuntimeError("frozen Phase-5B branch count is not 24")
    return tuple(branches)


@dataclass(frozen=True)
class CalibrationContext:
    protocol: dict
    protocol_sha256: str
    phase2: dict
    events: Tuple[dict, ...]
    raw_template: pd.DataFrame
    reference_keys: pd.MultiIndex
    validation: pd.DataFrame
    branches: Tuple[dict, ...]


def load_context():
    protocol = _load_json(CALIBRATION_PROTOCOL_PATH)
    phase2 = _load_json(PHASE2_PATH)
    phase4 = _load_json(PHASE4_PATH)
    phase5b_protocol = _load_json(PHASE5B_PROTOCOL_PATH)
    phase5b_report = _load_json(PHASE5B_RESULT_PATH)
    raw, reference, _, checks, _, events = phase5b.load_cadence_masks(
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

    validation = pd.read_csv(VALIDATION_PATH)
    if validation.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("frozen held validation keys are not unique")
    reference_keys = pd.MultiIndex.from_frame(reference[["sector", "cadenceno"]])
    branches = _build_branches(phase5b_report)

    if len(protocol["simulation_classes"]) != 12 or protocol["requested_total"] != 210:
        raise RuntimeError("S3-04A class universe is not the frozen 12/210 contract")
    if sum(item["requested_count"] for item in protocol["simulation_classes"]) != 210:
        raise RuntimeError("S3-04A requested realization total is inconsistent")
    if tuple(sorted({int(item["sector"]) for item in events})) != SECTORS:
        raise RuntimeError("used-event sectors differ from frozen six-sector contract")

    return CalibrationContext(
        protocol=protocol,
        protocol_sha256=_sha256(CALIBRATION_PROTOCOL_PATH),
        phase2=phase2,
        events=tuple(events),
        raw_template=raw.sort_values(["sector", "cadenceno"]).reset_index(drop=True),
        reference_keys=reference_keys,
        validation=validation.sort_values(["sector", "cadenceno"]).reset_index(drop=True),
        branches=branches,
    )


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


def _inject_background_systematic(frame, class_spec, seed):
    systematic = class_spec.get("systematic_injection")
    if systematic is None:
        return None
    low, high = systematic["slope_ppm_per_e_per_s"]
    rng = _seed_stream(seed, 2)
    slope = float(rng.uniform(float(low), float(high)))
    centered = frame["sap_bkg"].to_numpy(np.float64).copy()
    for sector in SECTORS:
        selected = frame["sector"].to_numpy(np.int64) == sector
        centered[selected] -= np.median(centered[selected])
    contribution = slope * centered
    frame["noise_flux"] += contribution
    frame["true_flux"] += contribution
    frame["flux"] += contribution
    return {"telemetry": systematic["telemetry"], "slope": slope}


def generate_latent_realization(context, class_spec, realization_index):
    """Generate exactly one deterministic raw-valid latent realization."""
    seed = realization_seed(context.protocol, class_spec, realization_index)
    geometry = _draw_geometry(class_spec, seed)
    noise_seed = int(_seed_stream(seed, 0).integers(0, np.iinfo(np.uint32).max))
    kwargs = _noise_kwargs(class_spec)
    frame, metadata = generator.generate_realization(
        context.raw_template,
        context.events,
        float(context.phase2["ephemeris_and_windows"]["t14_hours"]),
        noise_seed,
        inject_transit=bool(class_spec["inject_transit"]),
        rp_rs=geometry["rp_rs"] if geometry else 0.055,
        a_rs=geometry["a_rs"] if geometry else 10.2,
        impact_parameter=geometry["impact_parameter"] if geometry else 0.73,
        return_metadata=True,
        **kwargs
    )
    telemetry = _inject_background_systematic(frame, class_spec, seed)
    metadata.update({
        "class_name": class_spec["name"],
        "class_index": int(class_spec["class_index"]),
        "realization_index": int(realization_index),
        "realization_seed": int(seed),
        "noise_seed": int(noise_seed),
        "drawn_geometry": geometry,
        "telemetry_systematic": telemetry,
    })
    return frame, metadata


def apply_branch_baseline(latent, events, branch, realization_seed_value):
    """Apply the registered per-event polynomial baseline to one branch."""
    frame = latent.copy()
    rng = _seed_stream(realization_seed_value, 1000 + int(branch["model_index"]))
    baseline = np.zeros(len(frame), dtype=np.float64)
    time = frame["time_btjd"].to_numpy(np.float64)
    sectors = frame["sector"].to_numpy(np.int64)
    half_width = float(branch["window_hours"]) / 48.0
    degree = int(branch["polynomial_degree"])
    draws = {}
    for event in events:
        selected = ((sectors == int(event["sector"])) &
                    (np.abs(time - float(event["midpoint_btjd"])) <= half_width))
        if not np.any(selected):
            raise RuntimeError("branch has an empty registered event window")
        x_days = time[selected] - float(event["midpoint_btjd"])
        coefficients = rng.normal(0.0, BASELINE_SIGMA, degree + 1)
        baseline[selected] = np.polynomial.polynomial.polyval(x_days, coefficients)
        draws[event["physical_event_id"]] = coefficients.tolist()
    frame["branch_baseline"] = baseline
    frame["flux"] = (
        frame["transit_flux"] * (1.0 + baseline)
        + frame["noise_flux"] + frame["measurement_noise"]
    )
    return frame, draws


def derive_mask(frame, context, mask_id):
    if mask_id == "raw_valid":
        return frame
    if mask_id != "reference_included":
        raise ValueError("unknown frozen mask: {}".format(mask_id))
    keys = pd.MultiIndex.from_frame(frame[["sector", "cadenceno"]])
    result = frame.loc[keys.isin(context.reference_keys)].copy()
    if len(result) != len(context.reference_keys):
        raise RuntimeError("reference mask is not an exact raw-valid subset")
    return result.reset_index(drop=True)


def source_metadata(context):
    return {
        "calibration_protocol": {
            "path": "data/stage3_synthetic_calibration_protocol.json",
            "sha256": context.protocol_sha256,
        },
        "raw_template_rows": int(len(context.raw_template)),
        "reference_template_rows": int(len(context.reference_keys)),
        "branch_count": int(len(context.branches)),
        "sectors": list(SECTORS),
    }
