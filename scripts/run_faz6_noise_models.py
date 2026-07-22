"""Run the frozen Phase-6 LOSO correlated-noise screening protocol.

This script implements only the preregistered out-of-transit screening stage.
It does not perform the joint transit/noise fit or final residual diagnostics.
"""

import argparse
import hashlib
import importlib.metadata
import itertools
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logsumexp

import faz6_noise_core as noise
import run_faz5_window_grid as phase5
import run_faz5b_remediation as phase5b


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "data" / "faz6_preregistered_kernels.json"
SCORES_PATH = ROOT / "outputs" / "faz6_loso_scores.csv"
SCORES_META_PATH = ROOT / "outputs" / "faz6_loso_scores.meta.json"
MIXTURE_PATH = ROOT / "outputs" / "faz6_kernel_sector_mixture.csv"
OUTPUT_PATH = ROOT / "outputs" / "faz6_kernel_comparison.json"

KERNEL_IDS = ("K0_white", "K1_ou", "K2_matern32", "K3_sho")
MASK_IDS = ("raw_valid", "reference_included")
MODEL_PATTERN = re.compile(
    r"^(raw_valid|reference_included)::W(\d{2})_P([012])$"
)
SCORE_COLUMNS = (
    "protocol_sha256",
    "model_id",
    "mask_id",
    "cell_id",
    "window_hours",
    "polynomial_degree",
    "kernel_id",
    "held_sector",
    "conditional_cell_weight",
    "training_cadence_count",
    "held_cadence_count",
    "valid",
    "branch_log_predictive_density",
    "map_objective",
    "optimizer_success",
    "optimizer_attempt_count",
    "optimizer_retried",
    "any_parameter_at_boundary",
    "parameter_names_json",
    "parameters_json",
    "boundary_diagnostics_json",
    "error_type",
    "error_message",
)
MIXTURE_COLUMNS = (
    "protocol_sha256",
    "kernel_id",
    "held_sector",
    "raw_valid",
    "reference_included",
    "combined_log_predictive_density",
    "valid",
)


def load_json(path):
    return phase5b.load_json(path)


def sha256_file(path):
    return phase5b.sha256_file(path)


def relative(path):
    return phase5b.relative(path)


def json_ready(value):
    return phase5.json_ready(value)


def atomic_json(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_csv(path, frame, columns):
    temporary = path.with_name(path.name + ".tmp")
    frame.loc[:, list(columns)].to_csv(
        temporary,
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    )
    temporary.replace(path)


def artifact_record(path, **extra):
    result = {
        "relative_path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    result.update(extra)
    return result


def parse_model_id(model_id):
    match = MODEL_PATTERN.fullmatch(str(model_id))
    if match is None:
        raise RuntimeError("Invalid frozen Phase-5B model_id: {}".format(model_id))
    mask_id, window, degree = match.groups()
    window_hours = int(window)
    cell_id = "W{:02d}_P{}".format(window_hours, degree)
    return mask_id, cell_id, window_hours, int(degree)


def celerite_version():
    try:
        return importlib.metadata.version("celerite")
    except importlib.metadata.PackageNotFoundError:
        return getattr(noise.celerite, "__version__", "missing")


def verify_upstream(protocol):
    checks = {}
    for name, item in protocol["inputs"].items():
        path = ROOT / item["relative_path"]
        checks[name] = bool(
            path.is_file() and sha256_file(path) == item["sha256"]
        )
    report_item = protocol["inputs"]["phase5b_report"]
    report = load_json(ROOT / report_item["relative_path"])
    checks["phase5b_required_status"] = (
        report.get("status") == report_item["required_status"]
    )
    checks["celerite_version"] = (
        celerite_version() == protocol["software"]["celerite"]
    )
    checks["protocol_revision_pre_fit"] = bool(
        protocol.get("revision_before_any_kernel_fit") is True
    )
    if not all(checks.values()):
        raise RuntimeError("Phase-6 input contract failed: {}".format(checks))
    return checks, report


def load_branch_contract(protocol, report):
    item = protocol["inputs"]["phase5b_handoff_draws"]
    with np.load(ROOT / item["relative_path"], allow_pickle=False) as handoff:
        required = {
            "model_ids",
            "mask_ids",
            "cell_ids",
            "conditional_cell_weights",
            "joint_model_weights",
            "draws",
        }
        if not required.issubset(handoff.files):
            raise RuntimeError("Phase-5B handoff NPZ schema is incomplete")
        model_ids = [str(value) for value in handoff["model_ids"]]
        mask_ids = [str(value) for value in handoff["mask_ids"]]
        cell_ids = [str(value) for value in handoff["cell_ids"]]
        conditional = np.asarray(
            handoff["conditional_cell_weights"], dtype=np.float64
        )
        joint = np.asarray(handoff["joint_model_weights"], dtype=np.float64)
        draw_shape = tuple(handoff["draws"].shape)

    expected_count = int(protocol["branch_contract"]["model_count"])
    parsed = [parse_model_id(identifier) for identifier in model_ids]
    report_ids = report["handoff"]["model_ids"]
    report_joint = report["handoff"]["joint_model_weights"]
    checks = {
        "model_count_exact": len(model_ids) == expected_count == draw_shape[0],
        "model_ids_unique": len(set(model_ids)) == expected_count,
        "model_ids_match_report": model_ids == report_ids,
        "npz_mask_ids_match_model_ids": all(
            parsed_item[0] == mask_id
            for parsed_item, mask_id in zip(parsed, mask_ids)
        ),
        "npz_cell_ids_match_model_ids": all(
            parsed_item[1] == cell_id
            for parsed_item, cell_id in zip(parsed, cell_ids)
        ),
        "weights_finite_positive": bool(
            np.all(np.isfinite(conditional))
            and np.all(conditional > 0.0)
            and np.all(np.isfinite(joint))
            and np.all(joint > 0.0)
        ),
        "joint_weights_match_report": all(
            float(weight) == float(report_joint[identifier])
            for identifier, weight in zip(model_ids, joint)
        ),
        "joint_equals_half_conditional": bool(
            np.allclose(joint, 0.5 * conditional, rtol=0.0, atol=1e-15)
        ),
        "joint_weights_sum_one": math.isclose(
            float(np.sum(joint)), 1.0, rel_tol=0.0, abs_tol=1e-12
        ),
    }
    for mask_id in MASK_IDS:
        selected = np.asarray(mask_ids) == mask_id
        checks["{}_conditional_weights_sum_one".format(mask_id)] = math.isclose(
            float(np.sum(conditional[selected])),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        expected = report["branches"][mask_id]["conditional_weights"]
        checks["{}_conditional_weights_match_report".format(mask_id)] = all(
            float(weight) == float(expected[cell_id])
            for selected_mask, cell_id, weight in zip(
                mask_ids, cell_ids, conditional
            )
            if selected_mask == mask_id
        )
    if not all(checks.values()):
        raise RuntimeError("Phase-6 branch/weight contract failed: {}".format(checks))

    return [
        {
            "model_id": identifier,
            "mask_id": parsed_item[0],
            "cell_id": parsed_item[1],
            "window_hours": parsed_item[2],
            "polynomial_degree": parsed_item[3],
            "conditional_cell_weight": float(weight),
        }
        for identifier, parsed_item, weight in zip(model_ids, parsed, conditional)
    ], checks


def load_analysis_inputs(protocol):
    phase2 = load_json(ROOT / protocol["inputs"]["phase2_report"]["relative_path"])
    phase4 = load_json(ROOT / "outputs" / "faz4_reduction_comparison.json")
    raw = phase5.load_reference_table(phase4)
    ledger = pd.read_csv(
        ROOT / protocol["inputs"]["phase1_ledger"]["relative_path"]
    )
    included = phase5b.bool_series(ledger["in_current_reference"])
    included_keys = pd.MultiIndex.from_frame(
        ledger.loc[included, ["sector", "cadenceno"]]
    )
    raw_keys = pd.MultiIndex.from_frame(raw[["sector", "cadenceno"]])
    reference = raw.loc[raw_keys.isin(included_keys)].copy()
    reference.reset_index(drop=True, inplace=True)

    validation = pd.read_csv(
        ROOT / protocol["inputs"]["common_validation_keys"]["relative_path"]
    )
    validation_item = protocol["inputs"]["common_validation_keys"]
    validation_counts = {
        str(int(key)): int(value)
        for key, value in validation.groupby("sector", sort=True).size().items()
    }
    if (
        len(validation) != validation_item["row_count"]
        or validation_counts != validation_item["sector_counts"]
        or validation.duplicated(["sector", "cadenceno"]).any()
    ):
        raise RuntimeError("Frozen common validation key contract failed")

    events = phase5b.used_events(phase2)
    if len(events) != 16:
        raise RuntimeError("Phase-6 training requires exactly 16 used events")
    expected_counts = report_mask_counts(protocol)
    actual_counts = {
        "raw_valid": len(raw),
        "reference_included": len(reference),
    }
    if expected_counts != actual_counts:
        raise RuntimeError(
            "Phase-5B cadence mask counts changed: {} != {}".format(
                actual_counts, expected_counts
            )
        )
    return {"raw_valid": raw, "reference_included": reference}, validation, events, phase2


def report_mask_counts(protocol):
    report = load_json(ROOT / protocol["inputs"]["phase5b_report"]["relative_path"])
    return {
        mask_id: int(report["cadence_lineage"]["masks"][mask_id]["row_count"])
        for mask_id in MASK_IDS
    }


def event_block_sector_data(frame, sector, degree):
    selected = frame.loc[frame["sector"] == sector].copy()
    selected.sort_values("time_btjd", inplace=True)
    selected.reset_index(drop=True, inplace=True)
    if selected.empty:
        raise RuntimeError("Sector {} has no selected cadences".format(sector))
    if selected.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("A cadence is assigned to multiple event blocks")
    event_ids = sorted(selected["event_id"].unique())
    design = np.zeros(
        (len(selected), len(event_ids) * (degree + 1)), dtype=np.float64
    )
    for event_index, event_id in enumerate(event_ids):
        rows = selected["event_id"].eq(event_id).to_numpy()
        basis = phase5.polynomial_basis(
            selected.loc[rows, "x_days"].to_numpy(np.float64), degree
        )
        start = event_index * (degree + 1)
        design[rows, start : start + degree + 1] = basis
    return noise.SectorData(
        sector=int(sector),
        time=selected["time_btjd"].to_numpy(np.float64),
        flux=selected["flux"].to_numpy(np.float64) - 1.0,
        flux_err=selected["flux_err"].to_numpy(np.float64),
        baseline_matrix=design,
    )


def build_model_sector_data(reference, validation, events, phase2, model):
    half_width_days = model["window_hours"] / 48.0
    inner_days = (
        0.75 * float(phase2["ephemeris_and_windows"]["t14_hours"]) / 24.0
    )
    training_parts = []
    for event in events:
        rows = phase5.event_rows(reference, event, half_width_days)
        rows = rows.loc[np.abs(rows["x_days"]) >= inner_days].copy()
        if rows.empty:
            raise RuntimeError(
                "Event {} has no OOT training cadence".format(
                    event["physical_event_id"]
                )
            )
        training_parts.append(rows)
    training = pd.concat(training_parts, ignore_index=True)

    held = validation.merge(
        reference[["sector", "cadenceno", "flux", "flux_err"]],
        on=["sector", "cadenceno"],
        how="left",
        validate="one_to_one",
    )
    if held[["flux", "flux_err"]].isna().any().any() or len(held) != len(validation):
        raise RuntimeError("Frozen held-sector keys are absent from this mask")

    sectors = tuple(int(value) for value in sorted(validation["sector"].unique()))
    if sectors != tuple(int(x) for x in protocol_sectors()):
        raise RuntimeError("Frozen validation sector set changed")
    training_data = {
        sector: event_block_sector_data(
            training, sector, model["polynomial_degree"]
        )
        for sector in sectors
    }
    held_data = {
        sector: event_block_sector_data(held, sector, model["polynomial_degree"])
        for sector in sectors
    }
    if sum(len(item.time) for item in held_data.values()) != 2233:
        raise RuntimeError("Held SectorData does not contain exactly 2233 cadences")
    return training_data, held_data


def protocol_sectors():
    return (37, 63, 64, 90, 99, 100)


def checkpoint_metadata(protocol_hash, upstream_checks, branch_checks):
    return {
        "phase": "6-LOSO-screening-checkpoint",
        "protocol": {
            "relative_path": relative(PROTOCOL_PATH),
            "sha256": protocol_hash,
        },
        "expected_row_count": 576,
        "key_columns": ["model_id", "kernel_id", "held_sector"],
        "columns": list(SCORE_COLUMNS),
        "upstream_checks": upstream_checks,
        "branch_contract_checks": branch_checks,
        "invalid_rows_are_completed_rows": True,
        "resume_policy": "Never refit any key already recorded as valid or invalid.",
    }


def load_or_initialize_checkpoint(protocol_hash, metadata):
    if SCORES_META_PATH.exists():
        stored = load_json(SCORES_META_PATH)
        if stored != metadata:
            raise RuntimeError("LOSO checkpoint metadata/protocol mismatch")
    else:
        atomic_json(SCORES_META_PATH, metadata)

    if not SCORES_PATH.exists():
        frame = pd.DataFrame(columns=SCORE_COLUMNS)
        atomic_csv(SCORES_PATH, frame, SCORE_COLUMNS)
        return frame
    frame = pd.read_csv(SCORES_PATH, keep_default_na=False)
    if tuple(frame.columns) != SCORE_COLUMNS:
        raise RuntimeError("LOSO checkpoint schema mismatch")
    if len(frame) and not frame["protocol_sha256"].eq(protocol_hash).all():
        raise RuntimeError("LOSO checkpoint protocol hash mismatch")
    keys = ["model_id", "kernel_id", "held_sector"]
    if frame.duplicated(keys).any():
        raise RuntimeError("LOSO checkpoint contains duplicate completed keys")
    return frame


def score_fold(model, kernel_id, held_sector, training_data, held_data, protocol_hash):
    base = {
        "protocol_sha256": protocol_hash,
        "model_id": model["model_id"],
        "mask_id": model["mask_id"],
        "cell_id": model["cell_id"],
        "window_hours": model["window_hours"],
        "polynomial_degree": model["polynomial_degree"],
        "kernel_id": kernel_id,
        "held_sector": held_sector,
        "conditional_cell_weight": model["conditional_cell_weight"],
        "training_cadence_count": sum(
            len(data.time)
            for sector, data in training_data.items()
            if sector != held_sector
        ),
        "held_cadence_count": len(held_data[held_sector].time),
        "valid": False,
        "branch_log_predictive_density": np.nan,
        "map_objective": np.nan,
        "optimizer_success": False,
        "optimizer_attempt_count": 0,
        "optimizer_retried": False,
        "any_parameter_at_boundary": False,
        "parameter_names_json": "[]",
        "parameters_json": "[]",
        "boundary_diagnostics_json": "[]",
        "error_type": "",
        "error_message": "",
    }
    try:
        training = tuple(
            training_data[sector]
            for sector in protocol_sectors()
            if sector != held_sector
        )
        fit = noise.fit_pooled_map(training, kernel_id)
        diagnostics = [
            {
                "name": item.name,
                "value": item.value,
                "lower": item.lower,
                "upper": item.upper,
                "distance_fraction": item.distance_fraction,
                "at_boundary": item.at_boundary,
            }
            for item in fit.boundary_diagnostics
        ]
        base.update(
            {
                "map_objective": fit.objective,
                "optimizer_success": fit.success,
                "optimizer_attempt_count": len(fit.optimizer_results),
                "optimizer_retried": fit.retried,
                "any_parameter_at_boundary": any(
                    item.at_boundary for item in fit.boundary_diagnostics
                ),
                "parameter_names_json": json.dumps(
                    fit.layout.names, separators=(",", ":"), ensure_ascii=True
                ),
                "parameters_json": json.dumps(
                    fit.parameters.tolist(), separators=(",", ":"), ensure_ascii=True
                ),
                "boundary_diagnostics_json": json.dumps(
                    diagnostics, separators=(",", ":"), ensure_ascii=True
                ),
            }
        )
        if not fit.success:
            raise noise.NoiseModelError("Pooled MAP did not converge")
        score = noise.held_sector_joint_log_predictive_density(
            held_data[held_sector], fit
        )
        base["branch_log_predictive_density"] = score
        base["valid"] = bool(np.isfinite(score))
    except Exception as exc:  # A failed numerical fold is a completed invalid row.
        base["valid"] = False
        base["error_type"] = type(exc).__name__
        base["error_message"] = str(exc).replace("\r", " ").replace("\n", " ")
    return base


def append_checkpoint(frame, row):
    result = pd.concat([frame, pd.DataFrame([row])], ignore_index=True)
    atomic_csv(SCORES_PATH, result, SCORE_COLUMNS)
    return result


def bool_value(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() == "true"


def aggregate_mixtures(scores, models, protocol_hash):
    lookup = {
        (str(row.model_id), str(row.kernel_id), int(row.held_sector)): row
        for row in scores.itertuples(index=False)
    }
    rows = []
    for kernel_id in KERNEL_IDS:
        for sector in protocol_sectors():
            mask_scores = {}
            valid = True
            for mask_id in MASK_IDS:
                components = []
                for model in models:
                    if model["mask_id"] != mask_id:
                        continue
                    row = lookup[(model["model_id"], kernel_id, sector)]
                    if not bool_value(row.valid):
                        valid = False
                        continue
                    components.append(
                        math.log(model["conditional_cell_weight"])
                        + float(row.branch_log_predictive_density)
                    )
                expected = sum(model["mask_id"] == mask_id for model in models)
                if len(components) == expected:
                    mask_scores[mask_id] = float(logsumexp(components))
                else:
                    mask_scores[mask_id] = np.nan
            combined = np.nan
            if valid and all(np.isfinite(mask_scores[value]) for value in MASK_IDS):
                combined = float(
                    logsumexp(
                        [math.log(0.5) + mask_scores[value] for value in MASK_IDS]
                    )
                )
            rows.append(
                {
                    "protocol_sha256": protocol_hash,
                    "kernel_id": kernel_id,
                    "held_sector": sector,
                    "raw_valid": mask_scores["raw_valid"],
                    "reference_included": mask_scores["reference_included"],
                    "combined_log_predictive_density": combined,
                    "valid": bool(valid and np.isfinite(combined)),
                }
            )
    return pd.DataFrame(rows, columns=MIXTURE_COLUMNS)


def paired_summary(differences):
    values = np.asarray(differences, dtype=np.float64)
    delta = float(np.sum(values))
    standard_error = float(np.sqrt(6.0 * np.var(values, ddof=1)))
    flipped = [
        float(np.sum(values * np.asarray(signs, dtype=np.float64)))
        for signs in itertools.product((-1.0, 1.0), repeat=6)
    ]
    p_value = float(np.mean(np.asarray(flipped) >= delta))
    return delta, standard_error, p_value


def comparison_rows(mixture, scores, protocol):
    indexed = mixture.set_index(["kernel_id", "held_sector"])
    results = []
    for kernel_id in KERNEL_IDS[1:]:
        all_valid = all(
            bool_value(indexed.loc[(name, sector), "valid"])
            for name in ("K0_white", kernel_id)
            for sector in protocol_sectors()
        )
        relevant = scores.loc[scores["kernel_id"].isin(["K0_white", kernel_id])]
        boundary_clear = bool(
            all_valid
            and not any(bool_value(value) for value in relevant["any_parameter_at_boundary"])
        )
        result = {
            "kernel_id": kernel_id,
            "reference_kernel_id": "K0_white",
            "all_six_folds_valid": all_valid,
            "all_map_parameters_outside_boundary_fraction": boundary_clear,
            "delta_elpd": None,
            "paired_standard_error": None,
            "strict_delta_elpd_gt_2se": False,
            "exact_sign_flip_one_sided_p": None,
            "exact_sign_flip_p_at_most_0p05": False,
            "mask_specific_delta_elpd": {mask_id: None for mask_id in MASK_IDS},
            "both_mask_specific_deltas_positive": False,
            "mask_interaction": None,
            "mask_interaction_standard_error": None,
            "absolute_mask_interaction_at_most_2se": False,
            "predictive_and_physical_gates_pass": False,
            "final_phase6_eligible": False,
        }
        if all_valid:
            combined_differences = [
                float(
                    indexed.loc[(kernel_id, sector), "combined_log_predictive_density"]
                    - indexed.loc[("K0_white", sector), "combined_log_predictive_density"]
                )
                for sector in protocol_sectors()
            ]
            delta, standard_error, p_value = paired_summary(combined_differences)
            mask_differences = {
                mask_id: [
                    float(
                        indexed.loc[(kernel_id, sector), mask_id]
                        - indexed.loc[("K0_white", sector), mask_id]
                    )
                    for sector in protocol_sectors()
                ]
                for mask_id in MASK_IDS
            }
            mask_deltas = {
                mask_id: float(np.sum(values))
                for mask_id, values in mask_differences.items()
            }
            interaction_values = np.asarray(mask_differences["raw_valid"]) - np.asarray(
                mask_differences["reference_included"]
            )
            interaction = float(np.sum(interaction_values))
            interaction_se = float(
                np.sqrt(6.0 * np.var(interaction_values, ddof=1))
            )
            interaction_gate = abs(interaction) <= 2.0 * interaction_se
            strict_gate = delta > 2.0 * standard_error
            p_gate = p_value <= float(
                protocol["selection"]["exact_sign_flip_p_max"]
            )
            mask_gate = all(value > 0.0 for value in mask_deltas.values())
            predictive_pass = all(
                (strict_gate, p_gate, mask_gate, interaction_gate, boundary_clear)
            )
            result.update(
                {
                    "delta_elpd": delta,
                    "paired_standard_error": standard_error,
                    "strict_delta_elpd_gt_2se": strict_gate,
                    "exact_sign_flip_one_sided_p": p_value,
                    "exact_sign_flip_p_at_most_0p05": p_gate,
                    "mask_specific_delta_elpd": mask_deltas,
                    "both_mask_specific_deltas_positive": mask_gate,
                    "mask_interaction": interaction,
                    "mask_interaction_standard_error": interaction_se,
                    "absolute_mask_interaction_at_most_2se": interaction_gate,
                    "predictive_and_physical_gates_pass": predictive_pass,
                }
            )
        results.append(result)
    return results


def expected_keys(models):
    return {
        (model["model_id"], kernel_id, sector)
        for model in models
        for kernel_id in KERNEL_IDS
        for sector in protocol_sectors()
    }


def run_screening(protocol, upstream_checks, report):
    if OUTPUT_PATH.exists():
        raise FileExistsError(
            "Phase-6 comparison JSON is no-clobber; use --verify-only"
        )
    protocol_hash = sha256_file(PROTOCOL_PATH)
    models, branch_checks = load_branch_contract(protocol, report)
    metadata = checkpoint_metadata(protocol_hash, upstream_checks, branch_checks)
    scores = load_or_initialize_checkpoint(protocol_hash, metadata)
    completed = {
        (str(row.model_id), str(row.kernel_id), int(row.held_sector))
        for row in scores.itertuples(index=False)
    }
    expected = expected_keys(models)
    if not completed.issubset(expected):
        raise RuntimeError("LOSO checkpoint contains a non-protocol row")

    masks, validation, events, phase2 = load_analysis_inputs(protocol)
    for model in models:
        pending = [
            (kernel_id, sector)
            for kernel_id in KERNEL_IDS
            for sector in protocol_sectors()
            if (model["model_id"], kernel_id, sector) not in completed
        ]
        if not pending:
            continue
        training_data, held_data = build_model_sector_data(
            masks[model["mask_id"]], validation, events, phase2, model
        )
        for kernel_id, sector in pending:
            row = score_fold(
                model, kernel_id, sector, training_data, held_data, protocol_hash
            )
            scores = append_checkpoint(scores, row)
            completed.add((model["model_id"], kernel_id, sector))

    if completed != expected or len(scores) != 576:
        raise RuntimeError("LOSO checkpoint is not the exact 576-row grid")
    mixture = aggregate_mixtures(scores, models, protocol_hash)
    atomic_csv(MIXTURE_PATH, mixture, MIXTURE_COLUMNS)
    comparisons = comparison_rows(mixture, scores, protocol)
    invalid_count = int(sum(not bool_value(value) for value in scores["valid"]))
    predictive_candidates = [
        item["kernel_id"]
        for item in comparisons
        if item["predictive_and_physical_gates_pass"]
    ]
    result = {
        "phase": "6-noise-model-screening",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "screening_complete_final_diagnostics_pending",
        "protocol": {
            "relative_path": relative(PROTOCOL_PATH),
            "sha256": protocol_hash,
            "revision": protocol["protocol_revision"],
            "frozen_utc": protocol["frozen_utc"],
        },
        "software": {
            "celerite_required": protocol["software"]["celerite"],
            "celerite_observed": celerite_version(),
        },
        "source_integrity": {"checks": upstream_checks},
        "branch_contract": {
            "checks": branch_checks,
            "model_count": len(models),
            "mask_prior_weights": protocol["branch_contract"][
                "mask_prior_weights"
            ],
            "within_mask_aggregation": "logsumexp(log conditional weight + branch score)",
            "mask_aggregation": "logsumexp(log(0.5) + within-mask score)",
        },
        "screening": {
            "expected_score_rows": 576,
            "completed_score_rows": len(scores),
            "invalid_score_rows": invalid_count,
            "common_validation_cadence_count": 2233,
            "training_event_count": 16,
            "comparisons_against_k0": comparisons,
            "predictive_candidates_pending_joint_diagnostics": predictive_candidates,
        },
        "gate": {
            "all_576_rows_recorded": len(scores) == 576,
            "all_576_rows_valid": invalid_count == 0,
            "joint_transit_noise_stage_complete": False,
            "residual_beta_gate_complete": False,
            "phase6_pass": False,
            "phase7_may_begin": False,
        },
        "limitations": [
            "This output is MAP plus held-sector Gauss-Hermite screening, not a hyperparameter posterior.",
            "The comparison is conditional on the frozen all-sector Phase-5B branch universe and is not fully nested selection.",
            "The two cadence masks are correlated specification branches and are not multiplied as independent likelihoods.",
            "The joint transit/noise fit, geometry-shift test, ACF, beta, and periodogram diagnostics are not implemented by this script.",
            "No kernel is finally eligible and Phase 7 may not begin until those registered stages are completed elsewhere.",
        ],
    }
    result["artifacts"] = {
        "loso_scores": artifact_record(
            SCORES_PATH, row_count=len(scores), columns=list(SCORE_COLUMNS)
        ),
        "loso_scores_meta": artifact_record(SCORES_META_PATH),
        "kernel_sector_mixture": artifact_record(
            MIXTURE_PATH, row_count=len(mixture), columns=list(MIXTURE_COLUMNS)
        ),
    }
    atomic_json(OUTPUT_PATH, result)
    print(
        "Wrote {}: rows=576, invalid={}, phase7_may_begin=false".format(
            relative(OUTPUT_PATH), invalid_count
        )
    )


def verify_existing(protocol, upstream_checks, report):
    if not OUTPUT_PATH.is_file():
        raise FileNotFoundError(OUTPUT_PATH)
    protocol_hash = sha256_file(PROTOCOL_PATH)
    models, branch_checks = load_branch_contract(protocol, report)
    result = load_json(OUTPUT_PATH)
    checks = {
        "protocol_hash": result["protocol"]["sha256"] == protocol_hash,
        "status": result["status"]
        == "screening_complete_final_diagnostics_pending",
        "phase7_closed": result["gate"]["phase7_may_begin"] is False,
        "upstream_checks": all(upstream_checks.values()),
        "branch_contract_checks": all(branch_checks.values()),
    }
    for name, artifact in result["artifacts"].items():
        path = ROOT / artifact["relative_path"]
        checks["artifact_{}".format(name)] = bool(
            path.is_file() and sha256_file(path) == artifact["sha256"]
        )
    metadata = checkpoint_metadata(protocol_hash, upstream_checks, branch_checks)
    checks["checkpoint_meta_contract"] = (
        load_json(SCORES_META_PATH) == metadata
    )
    scores = pd.read_csv(SCORES_PATH, keep_default_na=False)
    score_keys = {
        (str(row.model_id), str(row.kernel_id), int(row.held_sector))
        for row in scores.itertuples(index=False)
    }
    checks["score_grid_exact"] = (
        tuple(scores.columns) == SCORE_COLUMNS
        and len(scores) == 576
        and score_keys == expected_keys(models)
    )
    mixture = pd.read_csv(MIXTURE_PATH, keep_default_na=False)
    checks["mixture_grid_exact"] = (
        tuple(mixture.columns) == MIXTURE_COLUMNS and len(mixture) == 24
    )
    if not all(checks.values()):
        raise RuntimeError("Phase-6 artifact verification failed: {}".format(checks))
    print("Verified {} and all upstream/artifact hashes".format(relative(OUTPUT_PATH)))


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--screen-only",
        action="store_true",
        help="Run/resume only the preregistered LOSO screening stage.",
    )
    mode.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify upstream inputs and frozen Phase-6 artifact hashes.",
    )
    args = parser.parse_args()
    protocol = load_json(PROTOCOL_PATH)
    upstream_checks, report = verify_upstream(protocol)
    if args.verify_only:
        verify_existing(protocol, upstream_checks, report)
        return
    run_screening(protocol, upstream_checks, report)


if __name__ == "__main__":
    main()
