"""Build the Phase-5B cadence-mask and discrete-model handoff.

The original Phase-5 report is immutable and remains a failure. This script
fits only the historical reference-included cadence branch, audits both masks
with real cadence-key intersections, and emits a separate conditional handoff
for Phase 6. It never adds the Phase-5 cell spread to the model mixture a
second time.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import run_faz5_window_grid as phase5


ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_PATH = ROOT / "data" / "faz5b_preregistered_handoff.json"
LEDGER_PATH = ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz"
PHASE2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
PHASE4_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"
PHASE5_REPORT_PATH = ROOT / "outputs" / "faz5_window_polynomial_grid.json"
PHASE5_GRID_PATH = ROOT / "outputs" / "faz5_model_grid.csv"
PHASE5_BLOCK_PATH = ROOT / "outputs" / "faz5_block_scores.csv"
PHASE5_DRAW_PATH = ROOT / "data" / "toi3492_faz5_geometry_draws.npz"

ALT_REPORT_PATH = ROOT / "outputs" / "faz5b_reference_included_grid.json"
ALT_GRID_PATH = ROOT / "outputs" / "faz5b_reference_included_model_grid.csv"
ALT_BLOCK_PATH = ROOT / "outputs" / "faz5b_reference_included_block_scores.csv"
ALT_DRAW_PATH = (
    ROOT / "data" / "toi3492_faz5b_reference_included_geometry_draws.npz"
)
LINEAGE_PATH = ROOT / "outputs" / "faz5b_cadence_lineage.csv"
FOLD_AUDIT_PATH = ROOT / "outputs" / "faz5b_fold_audit.csv"
MASK_COMPARISON_PATH = ROOT / "outputs" / "faz5b_mask_comparison.csv"
HANDOFF_DRAW_PATH = ROOT / "data" / "toi3492_faz5b_handoff_draws.npz"
OUTPUT_PATH = ROOT / "outputs" / "faz5b_remediation.json"

PARAMETERS = phase5.PARAMETERS
MASK_IDS = ("raw_valid", "reference_included")
OUTPUT_PATHS = (
    ALT_REPORT_PATH,
    ALT_GRID_PATH,
    ALT_BLOCK_PATH,
    ALT_DRAW_PATH,
    LINEAGE_PATH,
    FOLD_AUDIT_PATH,
    MASK_COMPARISON_PATH,
    HANDOFF_DRAW_PATH,
    OUTPUT_PATH,
)


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def json_ready(value):
    return phase5.json_ready(value)


def artifact_record(path, **extra):
    result = {
        "relative_path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    result.update(extra)
    return result


def write_json(path, payload):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_csv(path, frame):
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(temporary, index=False, lineterminator="\n", float_format="%.17g")
    temporary.replace(path)


def write_npz(path, **arrays):
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(path)


def verify_source_hashes(protocol):
    declared = {}
    declared.update(protocol["immutable_phase5"]["source_artifacts"])
    declared.update(protocol["upstream_inputs"])
    checks = {}
    for name, item in declared.items():
        path = ROOT / item["relative_path"]
        checks[name] = path.is_file() and sha256_file(path) == item["sha256"]
    if not all(checks.values()):
        raise RuntimeError(f"Phase-5B source hash validation failed: {checks}")
    return checks


def bool_series(series):
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    return series.astype(str).str.lower().eq("true")


def cadence_map(frame):
    result = {}
    for sector, cadenceno, time_btjd in frame[
        ["sector", "cadenceno", "time_btjd"]
    ].itertuples(index=False, name=None):
        key = (int(sector), int(cadenceno))
        value = float(time_btjd)
        if key in result and not math.isclose(result[key], value, abs_tol=1e-12):
            raise RuntimeError(f"Conflicting time for cadence key {key}")
        result[key] = value
    return result


def merge_cadence_maps(*mappings):
    result = {}
    for mapping in mappings:
        for key, value in mapping.items():
            if key in result and not math.isclose(result[key], value, abs_tol=1e-12):
                raise RuntimeError(f"Conflicting time while merging cadence key {key}")
            result[key] = value
    return result


def cadence_map_hash(mapping):
    digest = hashlib.sha256()
    for (sector, cadenceno), time_btjd in sorted(mapping.items()):
        digest.update(
            f"{sector},{cadenceno},{format(time_btjd, '.17g')}\n".encode("ascii")
        )
    return digest.hexdigest()


def sector_counts(frame):
    return {
        str(int(sector)): int(count)
        for sector, count in frame.groupby("sector", sort=True).size().items()
    }


def used_events(phase2):
    return [
        {
            "physical_event_id": item["physical_event_id"],
            "sector": int(item["sector"]),
            "epoch": int(item["epoch"]),
            "midpoint_btjd": float(item["predicted_midpoint_btjd"]),
        }
        for item in phase2["events"]
        if item["used"]
    ]


def load_cadence_masks(protocol, phase2, phase4):
    raw = phase5.load_reference_table(phase4)
    ledger = pd.read_csv(LEDGER_PATH)
    included = bool_series(ledger["in_current_reference"])
    quality = ledger["quality"].fillna(0).to_numpy(np.int64)
    base_valid = (
        np.isfinite(ledger["time_btjd"])
        & np.isfinite(ledger["pdcsap_flux"])
        & np.isfinite(ledger["pdcsap_flux_err"])
        & (ledger["pdcsap_flux"] > 0)
        & (ledger["pdcsap_flux_err"] > 0)
        & ((quality & 17087) == 0)
    )
    ledger_valid = ledger.loc[base_valid].copy()
    ledger_included = ledger.loc[base_valid & included].copy()

    raw_keys = cadence_map(raw)
    valid_keys = cadence_map(ledger_valid)
    included_keys = cadence_map(ledger_included)
    if set(raw_keys) != set(valid_keys):
        missing = sorted(set(valid_keys) - set(raw_keys))[:10]
        extra = sorted(set(raw_keys) - set(valid_keys))[:10]
        raise RuntimeError(
            f"Phase-4 PDCSAP keys differ from ledger base-valid keys: "
            f"missing={missing}, extra={extra}"
        )
    maximum_time_residual = max(
        abs(raw_keys[key] - valid_keys[key]) for key in raw_keys
    )
    if maximum_time_residual >= 1e-8:
        raise RuntimeError("Phase-4 and ledger cadence times do not match")
    if not set(included_keys).issubset(raw_keys):
        raise RuntimeError("Reference-included mask is not a subset of raw-valid")

    raw_index = pd.MultiIndex.from_frame(raw[["sector", "cadenceno"]])
    included_index = pd.MultiIndex.from_tuples(
        sorted(included_keys), names=("sector", "cadenceno")
    )
    reference_included = raw.loc[raw_index.isin(included_index)].copy()
    reference_included.sort_values(["sector", "cadenceno"], inplace=True)
    reference_included.reset_index(drop=True, inplace=True)

    raw_only_keys = set(raw_keys) - set(included_keys)
    raw_only = ledger_valid.loc[
        [
            (int(sector), int(cadenceno)) in raw_only_keys
            for sector, cadenceno in ledger_valid[["sector", "cadenceno"]].itertuples(
                index=False, name=None
            )
        ]
    ].copy()
    events = used_events(phase2)
    nearest_ids = []
    nearest_hours = []
    for sector, time_btjd in raw_only[["sector", "time_btjd"]].itertuples(
        index=False, name=None
    ):
        candidates = [item for item in events if item["sector"] == int(sector)]
        nearest = min(
            candidates,
            key=lambda item: abs(float(time_btjd) - item["midpoint_btjd"]),
        )
        nearest_ids.append(nearest["physical_event_id"])
        nearest_hours.append(abs(float(time_btjd) - nearest["midpoint_btjd"]) * 24.0)
    raw_only["nearest_used_event_id"] = nearest_ids
    raw_only["nearest_used_event_distance_hours"] = nearest_hours
    for window in protocol["grid_and_selection"]["total_window_hours"]:
        raw_only[f"inside_w{int(window):02d}"] = (
            raw_only["nearest_used_event_distance_hours"] <= float(window) / 2.0
        )
    lineage_columns = [
        "sector",
        "cadenceno",
        "time_btjd",
        "quality",
        "pdcsap_flux",
        "pdcsap_flux_err",
        "in_current_reference",
        "exclusion_reason",
        "nearest_used_event_id",
        "nearest_used_event_distance_hours",
    ] + [
        f"inside_w{int(window):02d}"
        for window in protocol["grid_and_selection"]["total_window_hours"]
    ]
    lineage = raw_only[lineage_columns].sort_values(
        ["sector", "cadenceno"]
    ).reset_index(drop=True)

    expected = protocol["cadence_policies"]
    checks = {
        "raw_total_count_exact": len(raw)
        == expected["raw_valid"]["expected_total_count"],
        "raw_sector_counts_exact": sector_counts(raw)
        == expected["raw_valid"]["expected_sector_counts"],
        "reference_total_count_exact": len(reference_included)
        == expected["reference_included"]["expected_total_count"],
        "reference_sector_counts_exact": sector_counts(reference_included)
        == expected["reference_included"]["expected_sector_counts"],
        "raw_mask_equals_phase4_pdcsap_keys": set(raw_keys) == set(valid_keys),
        "reference_mask_is_exact_raw_subset": set(cadence_map(reference_included))
        == set(included_keys),
        "raw_only_count_exact": len(lineage) == expected["expected_raw_only_count"],
        "raw_only_reasons_exact": set(lineage["exclusion_reason"])
        == {expected["expected_raw_only_reason"]},
        "time_alignment_better_than_1e8_day": maximum_time_residual < 1e-8,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Phase-5B cadence-lineage validation failed: {checks}")
    metadata = {
        "raw_valid": {
            "row_count": len(raw),
            "sector_counts": sector_counts(raw),
            "cadence_key_sha256": cadence_map_hash(raw_keys),
        },
        "reference_included": {
            "row_count": len(reference_included),
            "sector_counts": sector_counts(reference_included),
            "cadence_key_sha256": cadence_map_hash(
                cadence_map(reference_included)
            ),
        },
        "raw_only_count": len(lineage),
        "maximum_phase4_ledger_time_residual_days": maximum_time_residual,
    }
    return raw, reference_included, lineage, checks, metadata, events


def frame_parts(reference, event, half_width_days, inner_days, common_outer_days):
    frame = phase5.event_rows(reference, event, half_width_days)
    transit = frame.loc[np.abs(frame["x_days"]) < inner_days].copy()
    oot = frame.loc[np.abs(frame["x_days"]) >= inner_days].copy()
    left = oot.loc[oot["x_days"] < 0].copy()
    right = oot.loc[oot["x_days"] > 0].copy()
    return {
        "event": event,
        "transit": cadence_map(transit),
        "left": cadence_map(left),
        "right": cadence_map(right),
        "left_common": cadence_map(
            left.loc[np.abs(left["x_days"]) <= common_outer_days]
        ),
        "right_common": cadence_map(
            right.loc[np.abs(right["x_days"]) <= common_outer_days]
        ),
    }


def audit_fold_sets(reference, events, prereg, phase2, mask_id):
    t14_hours = float(phase2["ephemeris_and_windows"]["t14_hours"])
    inner_days = 0.75 * t14_hours / 24.0
    common_outer_days = (
        float(
            prereg["blocked_predictive_comparison"][
                "common_score_outer_boundary_hours"
            ]
        )
        / 24.0
    )
    minimum_side = int(
        prereg["blocked_predictive_comparison"][
            "minimum_cadences_per_common_side"
        ]
    )
    rows = []
    for window in prereg["grid"]["total_window_hours"]:
        half_width_days = float(window) / 48.0
        parts = {
            event["physical_event_id"]: frame_parts(
                reference,
                event,
                half_width_days,
                inner_days,
                common_outer_days,
            )
            for event in events
        }
        eligible = [
            key
            for key, item in parts.items()
            if len(item["left_common"]) >= minimum_side
            and len(item["right_common"]) >= minimum_side
        ]
        for key in eligible:
            item = parts[key]
            event = item["event"]
            sector = event["sector"]
            other_oot = merge_cadence_maps(
                *(
                    merge_cadence_maps(other["left"], other["right"])
                    for other_key, other in parts.items()
                    if other_key != key and other["event"]["sector"] == sector
                )
            )
            sector_transit = merge_cadence_maps(
                *(
                    other["transit"]
                    for other in parts.values()
                    if other["event"]["sector"] == sector
                )
            )
            for side in ("left", "right"):
                opposite = item["right"] if side == "left" else item["left"]
                held = item[side]
                validation = item[f"{side}_common"]
                training = merge_cadence_maps(other_oot, opposite)
                validation_keys = set(validation)
                training_keys = set(training)
                transit_keys = set(sector_transit)
                held_keys = set(held)
                for degree in prereg["grid"]["event_polynomial_degrees"]:
                    rows.append(
                        {
                            "mask_id": mask_id,
                            "cell_id": phase5.cell_id(window, degree),
                            "total_window_hours": int(window),
                            "polynomial_degree": int(degree),
                            "event_id": key,
                            "sector": int(sector),
                            "epoch": int(event["epoch"]),
                            "side": side,
                            "validation_cadence_count": len(validation),
                            "held_event_opposite_side_training_count": len(opposite),
                            "sector_training_cadence_count": len(training),
                            "transit_cadences_in_training": len(
                                transit_keys & training_keys
                            ),
                            "held_side_cadences_in_training": len(
                                held_keys & training_keys
                            ),
                            "training_validation_overlap_count": len(
                                validation_keys & training_keys
                            ),
                            "validation_key_sha256": cadence_map_hash(validation),
                            "training_key_sha256": cadence_map_hash(training),
                        }
                    )
    return pd.DataFrame(rows)


def attach_fold_audit(blocks, audit):
    keys = ["cell_id", "event_id", "sector", "epoch", "side"]
    audit_columns = keys + [
        "validation_cadence_count",
        "held_event_opposite_side_training_count",
        "sector_training_cadence_count",
        "transit_cadences_in_training",
        "held_side_cadences_in_training",
        "training_validation_overlap_count",
        "validation_key_sha256",
        "training_key_sha256",
    ]
    stored = blocks.drop(
        columns=[
            "transit_cadences_in_training",
            "held_side_cadences_in_training",
            "training_validation_overlap_count",
        ]
    )
    merged = stored.merge(
        audit[audit_columns],
        on=keys,
        how="left",
        suffixes=("_stored", "_audited"),
        validate="one_to_one",
    )
    if merged["validation_key_sha256"].isna().any():
        raise RuntimeError("A blocked score is absent from the cadence-set audit")
    for name in (
        "validation_cadence_count",
        "held_event_opposite_side_training_count",
    ):
        if not np.array_equal(
            merged[f"{name}_stored"].to_numpy(),
            merged[f"{name}_audited"].to_numpy(),
        ):
            raise RuntimeError(f"Stored and audited fold counts differ for {name}")
        merged[name] = merged.pop(f"{name}_audited")
        merged.drop(columns=f"{name}_stored", inplace=True)
    return merged


def run_reference_grid(reference, events, prereg):
    jitter_values = phase5.log_jitter_grid(prereg)
    block_frames = []
    score_metadata = {}
    cells = []
    draw_arrays = []
    combinations = [
        (window, degree)
        for window in prereg["grid"]["total_window_hours"]
        for degree in prereg["grid"]["event_polynomial_degrees"]
    ]
    for index, (window, degree) in enumerate(combinations):
        identifier = phase5.cell_id(window, degree)
        print(f"Phase 5B scoring and fitting reference_included::{identifier}")
        block_frame, score_meta = phase5.blocked_scores(
            reference, events, window, degree, prereg, jitter_values
        )
        event_frames = phase5.build_cell_events(reference, events, window / 48.0)
        fit = phase5.fit_cell(
            event_frames, window, degree, prereg, jitter_values, index
        )
        fit["blocked_predictive"] = {
            **score_meta,
            "elpd": float(block_frame["elpd"].sum()),
        }
        block_frames.append(block_frame)
        score_metadata[identifier] = score_meta
        draw_arrays.append(fit.pop("draws"))
        cells.append(fit)

    block_scores = pd.concat(block_frames, ignore_index=True)
    totals = block_scores.groupby("cell_id")["elpd"].sum().to_dict()
    best_id = max(totals, key=totals.get)
    comparisons = []
    for identifier in totals:
        if identifier == best_id:
            comparisons.append(
                {
                    "cell_id": identifier,
                    "delta_elpd_best_minus_cell": 0.0,
                    "event_cluster_standard_error": 0.0,
                    "sector_cluster_standard_error": 0.0,
                    "adopted_standard_error": 0.0,
                    "two_standard_errors": 0.0,
                    "strictly_distinguished": False,
                }
            )
        else:
            comparisons.append(
                phase5.paired_comparison(block_scores, best_id, identifier)
            )
    comparison_by_id = {item["cell_id"]: item for item in comparisons}
    retained = sorted(
        (
            identifier
            for identifier in totals
            if identifier == best_id
            or not comparison_by_id[identifier]["strictly_distinguished"]
        ),
        key=lambda identifier: (-totals[identifier], identifier),
    )
    weights = {identifier: 1.0 / len(retained) for identifier in retained}
    for cell in cells:
        identifier = cell["cell_id"]
        comparison = comparison_by_id[identifier]
        cell["blocked_predictive"]["delta_elpd_from_best"] = comparison[
            "delta_elpd_best_minus_cell"
        ]
        cell["blocked_predictive"]["paired_standard_error_vs_best"] = comparison[
            "adopted_standard_error"
        ]
        cell["retained_for_model_average"] = identifier in retained
        cell["model_weight"] = weights.get(identifier, 0.0)

    grid_rows = []
    for cell in cells:
        comparison = comparison_by_id[cell["cell_id"]]
        row = {
            "cell_id": cell["cell_id"],
            "total_window_hours": cell["total_window_hours"],
            "half_window_hours": cell["half_window_hours"],
            "polynomial_degree": cell["event_polynomial_degree"],
            "n_points": cell["n_points"],
            "n_events": cell["n_events"],
            "elpd": cell["blocked_predictive"]["elpd"],
            "delta_elpd_from_best": comparison["delta_elpd_best_minus_cell"],
            "paired_se_vs_best": comparison["adopted_standard_error"],
            "retained": cell["retained_for_model_average"],
            "model_weight": cell["model_weight"],
        }
        for name in PARAMETERS:
            for statistic in ("p16", "median", "p84"):
                row[f"{name}_{statistic}"] = cell["posterior"][name][statistic]
        grid_rows.append(row)
    return {
        "cells": cells,
        "draw_arrays": np.stack(draw_arrays),
        "block_scores": block_scores,
        "grid": pd.DataFrame(grid_rows),
        "score_metadata": score_metadata,
        "best_id": best_id,
        "comparisons": comparisons,
        "retained": retained,
        "weights": weights,
    }


def load_original_draws():
    with np.load(PHASE5_DRAW_PATH, allow_pickle=False) as payload:
        ids = [str(item) for item in payload["cell_ids"]]
        names = [str(item) for item in payload["parameter_names"]]
        draws = np.asarray(payload["draws"], dtype=float)
    if names != list(PARAMETERS):
        raise RuntimeError("Original Phase-5 draw parameter order changed")
    return {identifier: array for identifier, array in zip(ids, draws)}


def weighted_summary(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    p025, p16, median, p84, p975 = phase5.weighted_quantile(
        values, weights, [0.025, 0.16, 0.50, 0.84, 0.975]
    )
    mean = float(np.sum(weights * values))
    variance = float(np.sum(weights * (values - mean) ** 2))
    return {
        "p025": float(p025),
        "p16": float(p16),
        "median": float(median),
        "p84": float(p84),
        "p975": float(p975),
        "mean": mean,
        "standard_deviation": math.sqrt(variance),
    }


def build_handoff(protocol, phase4, original_report, original_draws, alternate):
    mask_weights = protocol["cadence_policies"]["mask_prior_weights"]
    alternate_draws = {
        cell["cell_id"]: draws
        for cell, draws in zip(alternate["cells"], alternate["draw_arrays"])
    }
    branch_data = {
        "raw_valid": {
            "retained": original_report["model_comparison"]["retained_cell_ids"],
            "draws": original_draws,
        },
        "reference_included": {
            "retained": alternate["retained"],
            "draws": alternate_draws,
        },
    }
    model_ids = []
    mask_ids = []
    cell_ids = []
    conditional_weights = []
    joint_weights = []
    arrays = []
    for mask_id in MASK_IDS:
        retained = branch_data[mask_id]["retained"]
        conditional = 1.0 / len(retained)
        for identifier in retained:
            model_ids.append(f"{mask_id}::{identifier}")
            mask_ids.append(mask_id)
            cell_ids.append(identifier)
            conditional_weights.append(conditional)
            joint_weights.append(float(mask_weights[mask_id]) * conditional)
            arrays.append(branch_data[mask_id]["draws"][identifier])
    draw_stack = np.stack(arrays)
    joint_weights = np.asarray(joint_weights, dtype=float)
    draw_count = draw_stack.shape[1]
    flattened = draw_stack.reshape(-1, draw_stack.shape[-1])
    flattened_weights = np.repeat(joint_weights / draw_count, draw_count)
    summaries = {
        name: weighted_summary(flattened[:, index], flattened_weights)
        for index, name in enumerate(PARAMETERS)
    }
    mean = np.sum(flattened_weights[:, None] * flattened, axis=0)
    centered = flattened - mean
    covariance = (centered * flattened_weights[:, None]).T @ centered

    component_summaries = {}
    medians = {name: [] for name in PARAMETERS}
    interval68 = {name: [] for name in PARAMETERS}
    interval95 = {name: [] for name in PARAMETERS}
    for model_id, draws in zip(model_ids, draw_stack):
        component_summaries[model_id] = {}
        for index, name in enumerate(PARAMETERS):
            p025, p16, median, p84, p975 = np.percentile(
                draws[:, index], [2.5, 16.0, 50.0, 84.0, 97.5]
            )
            component_summaries[model_id][name] = {
                "p025": float(p025),
                "p16": float(p16),
                "median": float(median),
                "p84": float(p84),
                "p975": float(p975),
            }
            medians[name].append(float(median))
            interval68[name].append((float(p16), float(p84)))
            interval95[name].append((float(p025), float(p975)))
    envelopes = {}
    for name in PARAMETERS:
        envelopes[name] = {
            "model_median_min": min(medians[name]),
            "model_median_max": max(medians[name]),
            "component_68_min": min(item[0] for item in interval68[name]),
            "component_68_max": max(item[1] for item in interval68[name]),
            "component_95_min": min(item[0] for item in interval95[name]),
            "component_95_max": max(item[1] for item in interval95[name]),
            "interpretation": "specification envelope, not a credible interval",
        }

    phase4_systematic = phase4["accepted_branch_geometry_comparison"][
        "between_reduction_systematic"
    ]["values"]
    cumulative = {}
    for name in PARAMETERS:
        summary = summaries[name]
        systematic = float(phase4_systematic[name]["adopted_systematic"])
        cumulative[name] = {
            **summary,
            "phase4_between_reduction_systematic": systematic,
            "cumulative_p16": summary["median"]
            - math.hypot(summary["median"] - summary["p16"], systematic),
            "cumulative_p84": summary["median"]
            + math.hypot(summary["p84"] - summary["median"], systematic),
            "cumulative_p025": summary["median"]
            - math.hypot(summary["median"] - summary["p025"], systematic),
            "cumulative_p975": summary["median"]
            + math.hypot(summary["p975"] - summary["median"], systematic),
            "phase5_between_cell_padding_added": False,
        }
    return {
        "model_ids": model_ids,
        "mask_ids": mask_ids,
        "cell_ids": cell_ids,
        "conditional_weights": np.asarray(conditional_weights, dtype=float),
        "joint_weights": joint_weights,
        "draws": draw_stack,
        "summaries": summaries,
        "cumulative": cumulative,
        "covariance": covariance,
        "component_summaries": component_summaries,
        "envelopes": envelopes,
    }


def mask_comparison_frame(original_grid, alternate_grid, protocol):
    frames = []
    for mask_id, frame in (
        ("raw_valid", original_grid),
        ("reference_included", alternate_grid),
    ):
        item = frame.copy()
        item.insert(0, "mask_id", mask_id)
        item["mask_prior_weight"] = protocol["cadence_policies"][
            "mask_prior_weights"
        ][mask_id]
        item["conditional_cell_weight"] = item["model_weight"]
        item["joint_model_weight"] = (
            item["mask_prior_weight"] * item["conditional_cell_weight"]
        )
        frames.append(item)
    return pd.concat(frames, ignore_index=True)


def verify_existing_outputs():
    if not OUTPUT_PATH.is_file():
        raise FileNotFoundError(OUTPUT_PATH)
    protocol = load_json(PROTOCOL_PATH)
    verify_source_hashes(protocol)
    report = load_json(OUTPUT_PATH)
    if report["protocol"]["sha256"] != sha256_file(PROTOCOL_PATH):
        raise RuntimeError("Phase-5B protocol hash changed")
    if not all(report["source_integrity"]["checks"].values()):
        raise RuntimeError("Frozen Phase-5B report contains a failed source check")
    for name, artifact in report["artifacts"].items():
        path = ROOT / artifact["relative_path"]
        if not path.is_file() or sha256_file(path) != artifact["sha256"]:
            raise RuntimeError(f"Phase-5B artifact verification failed: {name}")
    if report["status"] != "CONDITIONAL_CONTINUE":
        raise RuntimeError("Existing Phase-5B output does not permit conditional continuation")
    print(f"Verified {relative(OUTPUT_PATH)} and {len(report['artifacts'])} artifacts")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify the frozen Phase-5B output and artifact hashes without fitting.",
    )
    args = parser.parse_args()
    if args.verify_only:
        verify_existing_outputs()
        return
    existing = [relative(path) for path in OUTPUT_PATHS if path.exists()]
    if existing:
        raise FileExistsError(
            "Phase-5B is no-clobber; existing outputs must be verified, not overwritten: "
            + ", ".join(existing)
        )

    protocol = load_json(PROTOCOL_PATH)
    source_checks = verify_source_hashes(protocol)
    prereg = load_json(phase5.PREREG_PATH)
    phase2 = load_json(PHASE2_PATH)
    phase4 = load_json(PHASE4_PATH)
    original_report = load_json(PHASE5_REPORT_PATH)
    original_grid = pd.read_csv(PHASE5_GRID_PATH)
    original_blocks = pd.read_csv(PHASE5_BLOCK_PATH)
    original_draws = load_original_draws()

    raw, reference, lineage, lineage_checks, mask_metadata, events = (
        load_cadence_masks(protocol, phase2, phase4)
    )
    raw_audit = audit_fold_sets(raw, events, prereg, phase2, "raw_valid")
    raw_blocks_audited = attach_fold_audit(original_blocks, raw_audit)

    alternate = run_reference_grid(reference, events, prereg)
    reference_audit = audit_fold_sets(
        reference, events, prereg, phase2, "reference_included"
    )
    alternate["block_scores"] = attach_fold_audit(
        alternate["block_scores"], reference_audit
    )
    fold_audit = pd.concat([raw_audit, reference_audit], ignore_index=True)

    expected_reference = protocol["cadence_policies"]["reference_included"]
    expected_window_counts = {
        int(key): int(value)
        for key, value in expected_reference["expected_window_counts"].items()
    }
    reference_count_gate = all(
        cell["n_points"]
        == expected_window_counts[cell["total_window_hours"]]
        for cell in alternate["cells"]
    )
    expected_validation = int(
        expected_reference["expected_common_validation_cadences"]
    )
    reference_support_gate = all(
        item["fold_count"] == 30
        and item["validation_cadence_count"] == expected_validation
        and len(item["eligible_event_ids"]) == 15
        for item in alternate["score_metadata"].values()
    )
    fold_overlap_gate = bool(
        (
            fold_audit[
                [
                    "transit_cadences_in_training",
                    "held_side_cadences_in_training",
                    "training_validation_overlap_count",
                ]
            ]
            == 0
        )
        .all()
        .all()
    )
    common_hash_gate = bool(
        (
            fold_audit.groupby(
                ["mask_id", "event_id", "side"], sort=True
            )["validation_key_sha256"].nunique()
            == 1
        ).all()
    )

    required_original = set(
        protocol["immutable_phase5"]["required_retained_cell_ids"]
    )
    original_retained = set(
        original_report["model_comparison"]["retained_cell_ids"]
    )
    handoff = build_handoff(
        protocol, phase4, original_report, original_draws, alternate
    )
    alternate_draws = {
        cell["cell_id"]: draws
        for cell, draws in zip(alternate["cells"], alternate["draw_arrays"])
    }
    source_draws = {
        "raw_valid": original_draws,
        "reference_included": alternate_draws,
    }
    handoff_draws_match_sources = all(
        np.array_equal(draws, source_draws[mask_id][identifier])
        for mask_id, identifier, draws in zip(
            handoff["mask_ids"], handoff["cell_ids"], handoff["draws"]
        )
    )
    dependent_reductions_not_multiplied = bool(
        original_report["model"][
            "reductions_combined_as_independent_likelihoods"
        ]
        is False
        and set(raw["branch"]) == {"pdcsap"}
        and set(reference["branch"]) == {"pdcsap"}
        and protocol["phase6_handoff"][
            "dependent_reduction_likelihoods_must_not_be_multiplied"
        ]
        is True
    )
    mask_weight_sums = {
        mask_id: float(
            sum(
                weight
                for item_mask, weight in zip(
                    handoff["mask_ids"], handoff["joint_weights"]
                )
                if item_mask == mask_id
            )
        )
        for mask_id in MASK_IDS
    }
    gates = {
        "source_hashes_match": all(source_checks.values()),
        "original_phase5_status_remains_fail": original_report["status"] == "FAIL",
        "original_phase5_gate_remains_closed": original_report["gate"][
            "phase6_may_begin"
        ]
        is False,
        "original_retained_set_exact": original_retained == required_original,
        "w26_p1_preserved": "W26_P1" in original_retained,
        "cadence_lineage_checks_pass": all(lineage_checks.values()),
        "alternate_all_15_cells_completed": len(alternate["cells"]) == 15,
        "alternate_native_cadence_counts_exact": reference_count_gate,
        "alternate_common_score_support_exact": reference_support_gate,
        "alternate_all_baseline_designs_full_rank": all(
            cell["baseline_marginalization"]["minimum_design_rank"]
            == cell["baseline_marginalization"]["required_design_rank"]
            for cell in alternate["cells"]
        ),
        "alternate_all_laplace_covariances_valid": all(
            cell["laplace"]["valid"] for cell in alternate["cells"]
        ),
        "actual_fold_intersections_are_zero": fold_overlap_gate,
        "common_validation_key_hash_within_each_mask": common_hash_gate,
        "mask_prior_weights_sum_to_one": math.isclose(
            sum(
                protocol["cadence_policies"]["mask_prior_weights"].values()
            ),
            1.0,
            abs_tol=1e-12,
        ),
        "joint_model_weights_sum_to_one": math.isclose(
            float(handoff["joint_weights"].sum()), 1.0, abs_tol=1e-12
        ),
        "joint_model_weights_reproduce_mask_priors": all(
            math.isclose(
                mask_weight_sums[mask_id],
                protocol["cadence_policies"]["mask_prior_weights"][mask_id],
                abs_tol=1e-12,
            )
            for mask_id in MASK_IDS
        ),
        "phase5_between_cell_padding_not_added": handoff_draws_match_sources,
        "dependent_reduction_likelihoods_not_multiplied": dependent_reductions_not_multiplied,
    }
    conditional_continue = all(gates.values())
    status = "CONDITIONAL_CONTINUE" if conditional_continue else "FAIL"

    comparison = mask_comparison_frame(
        original_grid, alternate["grid"], protocol
    )
    write_csv(LINEAGE_PATH, lineage)
    write_csv(FOLD_AUDIT_PATH, fold_audit)
    write_csv(ALT_GRID_PATH, alternate["grid"])
    write_csv(ALT_BLOCK_PATH, alternate["block_scores"])
    write_csv(MASK_COMPARISON_PATH, comparison)
    write_npz(
        ALT_DRAW_PATH,
        cell_ids=np.asarray(
            [cell["cell_id"] for cell in alternate["cells"]], dtype="U8"
        ),
        parameter_names=np.asarray(PARAMETERS, dtype="U32"),
        draws=alternate["draw_arrays"],
    )
    write_npz(
        HANDOFF_DRAW_PATH,
        model_ids=np.asarray(handoff["model_ids"], dtype="U40"),
        mask_ids=np.asarray(handoff["mask_ids"], dtype="U24"),
        cell_ids=np.asarray(handoff["cell_ids"], dtype="U8"),
        parameter_names=np.asarray(PARAMETERS, dtype="U32"),
        conditional_cell_weights=handoff["conditional_weights"],
        joint_model_weights=handoff["joint_weights"],
        draws=handoff["draws"],
    )

    alternate_report = {
        "phase": "5B-reference-included-grid",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SENSITIVITY_BRANCH_COMPLETE",
        "mask_id": "reference_included",
        "protocol": {
            "relative_path": relative(PROTOCOL_PATH),
            "sha256": sha256_file(PROTOCOL_PATH),
        },
        "model": {
            "phase5_model_and_priors_reused_without_change": True,
            "source_phase5_script": protocol["immutable_phase5"][
                "source_artifacts"
            ]["producer_script"],
            "phase5_results_overwritten": False,
        },
        "cells": alternate["cells"],
        "model_comparison": {
            "best_raw_elpd_cell": alternate["best_id"],
            "pairwise_against_best": alternate["comparisons"],
            "retained_cell_ids": alternate["retained"],
            "retained_model_count": len(alternate["retained"]),
            "weights": alternate["weights"],
            "selection_rule": protocol["grid_and_selection"][
                "same_strict_retention_rule"
            ],
        },
        "gate": {
            "all_15_cells_completed": len(alternate["cells"]) == 15,
            "native_cadence_counts_exact": reference_count_gate,
            "common_score_support_exact": reference_support_gate,
            "all_baseline_designs_full_rank": gates[
                "alternate_all_baseline_designs_full_rank"
            ],
            "all_laplace_covariances_valid": gates[
                "alternate_all_laplace_covariances_valid"
            ],
        },
        "limitations": [
            "This is a disclosed post-Phase-5 cadence-mask sensitivity branch, not a blind preregistration.",
            "It uses the original Phase-5 128-point jitter quadrature and Laplace approximation.",
            "It does not replace the later GP, injection-recovery, or final MCMC convergence phases.",
        ],
    }
    alternate_report["artifacts"] = {
        "model_grid_csv": artifact_record(
            ALT_GRID_PATH,
            row_count=len(alternate["grid"]),
            columns=list(alternate["grid"].columns),
        ),
        "block_scores_csv": artifact_record(
            ALT_BLOCK_PATH,
            row_count=len(alternate["block_scores"]),
            columns=list(alternate["block_scores"].columns),
        ),
        "geometry_draws_npz": artifact_record(
            ALT_DRAW_PATH,
            cell_count=len(alternate["cells"]),
            draws_per_cell=int(prereg["posterior_approximation"]["draws_per_cell"]),
            parameter_order=list(PARAMETERS),
        ),
    }
    write_json(ALT_REPORT_PATH, alternate_report)

    result = {
        "phase": "5B",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "original_phase5_status": original_report["status"],
        "protocol": {
            "relative_path": relative(PROTOCOL_PATH),
            "sha256": sha256_file(PROTOCOL_PATH),
            "frozen_utc": protocol["frozen_utc"],
            "disclosure": protocol["disclosure"],
        },
        "source_integrity": {
            "checks": source_checks,
            "immutable_phase5_report": protocol["immutable_phase5"][
                "source_artifacts"
            ]["report"],
        },
        "cadence_lineage": {
            "checks": lineage_checks,
            "masks": mask_metadata,
            "mask_prior_weights": protocol["cadence_policies"][
                "mask_prior_weights"
            ],
            "raw_only_count": len(lineage),
            "raw_only_reason": protocol["cadence_policies"][
                "expected_raw_only_reason"
            ],
            "raw_only_inside_window_counts": {
                str(window): int(lineage[f"inside_w{int(window):02d}"].sum())
                for window in prereg["grid"]["total_window_hours"]
            },
        },
        "fold_audit": {
            "row_count": len(fold_audit),
            "rows_per_mask": {
                mask_id: int((fold_audit["mask_id"] == mask_id).sum())
                for mask_id in MASK_IDS
            },
            "actual_overlap_maxima": {
                name: int(fold_audit[name].max())
                for name in (
                    "transit_cadences_in_training",
                    "held_side_cadences_in_training",
                    "training_validation_overlap_count",
                )
            },
            "common_validation_key_hash_within_each_mask": common_hash_gate,
        },
        "branches": {
            "raw_valid": {
                "source": relative(PHASE5_REPORT_PATH),
                "status": original_report["status"],
                "best_raw_elpd_cell": original_report["model_comparison"][
                    "best_raw_elpd_cell"
                ],
                "retained_cell_ids": original_report["model_comparison"][
                    "retained_cell_ids"
                ],
                "retained_model_count": original_report["model_comparison"][
                    "retained_model_count"
                ],
                "conditional_weights": original_report["model_comparison"][
                    "weights"
                ],
                "validation_cadence_count_per_cell": int(
                    raw_blocks_audited.groupby("cell_id")[
                        "validation_cadence_count"
                    ].sum().iloc[0]
                ),
            },
            "reference_included": {
                "source": relative(ALT_REPORT_PATH),
                "status": alternate_report["status"],
                "best_raw_elpd_cell": alternate["best_id"],
                "retained_cell_ids": alternate["retained"],
                "retained_model_count": len(alternate["retained"]),
                "conditional_weights": alternate["weights"],
                "validation_cadence_count_per_cell": expected_validation,
            },
        },
        "handoff": {
            "factorization": protocol["phase6_handoff"]["factorization"],
            "model_count": len(handoff["model_ids"]),
            "model_ids": handoff["model_ids"],
            "mask_weight_sums": mask_weight_sums,
            "joint_model_weights": {
                identifier: float(weight)
                for identifier, weight in zip(
                    handoff["model_ids"], handoff["joint_weights"]
                )
            },
            "phase5_between_cell_padding_added": False,
            "phase4_systematic_in_handoff_draws": False,
            "phase4_systematic_treatment": protocol["uncertainty_policy"][
                "phase4_between_reduction_systematic"
            ],
            "dependent_reduction_likelihoods_multiplied": False,
        },
        "model_averaged_geometry": {
            "hierarchical_specification_mixture": handoff["summaries"],
            "with_phase4_reduction_systematic_once": handoff["cumulative"],
            "covariance_parameter_order": list(PARAMETERS),
            "hierarchical_mixture_covariance": handoff["covariance"].tolist(),
            "specification_envelopes": handoff["envelopes"],
        },
        "gate": {
            "checks": gates,
            "status": status,
            "gate_pass": False,
            "conditional_continue": conditional_continue,
            "phase6_may_begin": conditional_continue,
            "phase6_started": False,
            "meaning": protocol["status_semantics"]["meaning"],
        },
        "limitations": [
            "The original preregistered Phase-5 status remains FAIL.",
            "The two masks are correlated specification branches, not independent observations.",
            "The Phase-5 model spread is already present in the discrete mixture and is not added again as a scalar systematic.",
            "The Phase-4 reduction systematic remains outside the handoff draws and is shown only once in marginal reporting intervals.",
            "The 128-point jitter quadrature and Laplace approximation are retained for this handoff; later GP, injection, and MCMC convergence gates remain mandatory for final parameters.",
        ],
    }
    result["artifacts"] = {
        "alternate_report": artifact_record(ALT_REPORT_PATH),
        "alternate_model_grid": artifact_record(
            ALT_GRID_PATH, row_count=len(alternate["grid"])
        ),
        "alternate_block_scores": artifact_record(
            ALT_BLOCK_PATH, row_count=len(alternate["block_scores"])
        ),
        "alternate_geometry_draws": artifact_record(ALT_DRAW_PATH),
        "cadence_lineage": artifact_record(LINEAGE_PATH, row_count=len(lineage)),
        "fold_audit": artifact_record(FOLD_AUDIT_PATH, row_count=len(fold_audit)),
        "mask_comparison": artifact_record(
            MASK_COMPARISON_PATH, row_count=len(comparison)
        ),
        "handoff_draws": artifact_record(
            HANDOFF_DRAW_PATH,
            model_count=len(handoff["model_ids"]),
            draws_per_model=int(handoff["draws"].shape[1]),
            parameter_order=list(PARAMETERS),
        ),
    }
    write_json(OUTPUT_PATH, result)
    print(
        f"Phase 5B {status}: raw retained={len(original_retained)}, "
        f"reference retained={len(alternate['retained'])}, "
        f"handoff models={len(handoff['model_ids'])}, output={relative(OUTPUT_PATH)}"
    )


if __name__ == "__main__":
    main()
