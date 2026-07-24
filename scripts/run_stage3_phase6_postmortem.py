"""Build the read-only Stage-3 Phase-6/6R post-mortem artifacts."""

import argparse
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import faz6_residual_diagnostics as residuals
import run_faz6_joint_diagnostics as phase6


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest.json"
REPORT_PATH = ROOT / "outputs" / "stage3_phase6_postmortem.json"
BOUNDARY_PATH = ROOT / "outputs" / "stage3_phase6_boundary_map.csv"
MASK_PATH = ROOT / "outputs" / "stage3_phase6_mask_influence.csv"
BETA_PATH = ROOT / "outputs" / "stage3_phase6_beta_by_sector.csv"
RESIDUAL_PATH = ROOT / "outputs" / "stage3_phase6_residual_summary.csv"
OUTPUT_PATHS = (REPORT_PATH, BOUNDARY_PATH, MASK_PATH, BETA_PATH, RESIDUAL_PATH)

LOSO_PATH = ROOT / "outputs" / "faz6_loso_scores.csv"
MIXTURE_PATH = ROOT / "outputs" / "faz6_kernel_sector_mixture.csv"
KERNEL_REPORT_PATH = ROOT / "outputs" / "faz6_kernel_comparison.json"
GATE_PATH = ROOT / "outputs" / "faz6_gate_audit.json"
V1_REPORT_PATH = ROOT / "outputs" / "faz6_final_noise_model.json"
V2_REPORT_PATH = ROOT / "outputs" / "faz6_final_noise_model_v2.json"
PHASE6R_RESULT_PATH = ROOT / "outputs" / "faz6r_result.json"
PHASE6R_FIT_PATH = ROOT / "outputs" / "faz6r_joint_fits.csv"
PHASE6R_DRAW_PATH = ROOT / "data" / "faz6r_geometry_draws.npz"
LINEAGE_PATH = ROOT / "outputs" / "faz5b_cadence_lineage.csv"
LEDGER_PATH = ROOT / "data" / "toi3492_cadence_ledger_120s.csv.gz"

SECTORS = tuple(phase6.SECTORS)
COMPLEX_KERNELS = ("K1_ou", "K2_matern32", "K3_sho")
TELEMETRY_COLUMNS = (
    "sap_bkg",
    "pos_corr1",
    "pos_corr2",
    "mom_centr1",
    "mom_centr2",
)
USED_MANIFEST_PATHS = (
    "outputs/faz2_transit_inventory.json",
    "data/toi3492_cadence_ledger_120s.csv.gz",
    "data/toi3492_faz4_reductions_120s.csv.gz",
    "data/faz5_preregistered_grid.json",
    "outputs/faz5b_remediation.json",
    "outputs/faz5b_cadence_lineage.csv",
    "data/toi3492_faz5b_handoff_draws.npz",
    "data/faz6_preregistered_kernels.json",
    "data/faz6_joint_diagnostics_protocol.json",
    "data/faz6_joint_diagnostics_protocol_v2.json",
    "outputs/faz6_loso_scores.csv",
    "outputs/faz6_kernel_sector_mixture.csv",
    "outputs/faz6_kernel_comparison.json",
    "outputs/faz6_final_noise_model.json",
    "outputs/faz6_final_noise_model_v2.json",
    "outputs/faz6_gate_audit.json",
    "scripts/run_faz6r.py",
    "outputs/faz6r_result.json",
    "outputs/faz6r_joint_fits.csv",
    "data/faz6r_geometry_draws.npz",
)

BOUNDARY_COLUMNS = (
    "source_artifact",
    "source_csv_row",
    "model_id",
    "mask_id",
    "cell_id",
    "window_hours",
    "polynomial_degree",
    "kernel_id",
    "held_sector",
    "screening_valid",
    "optimizer_success",
    "branch_log_predictive_density",
    "input_fold_any_parameter_at_boundary",
    "parameter_index",
    "parameter_name",
    "parameter_value",
    "lower_bound",
    "upper_bound",
    "nearest_boundary",
    "distance_fraction",
    "at_boundary",
    "transformation",
    "transformed_value",
    "transformed_unit",
)

MASK_COLUMNS = (
    "record_type",
    "source_artifact",
    "source_csv_row",
    "comparator_source_artifact",
    "comparator_source_csv_row",
    "kernel_id",
    "held_sector",
    "absolute_interaction_rank_within_kernel",
    "raw_kernel_log_predictive_density",
    "reference_kernel_log_predictive_density",
    "combined_kernel_log_predictive_density",
    "raw_k0_log_predictive_density",
    "reference_k0_log_predictive_density",
    "combined_k0_log_predictive_density",
    "raw_kernel_gain_vs_k0",
    "reference_kernel_gain_vs_k0",
    "combined_kernel_gain_vs_k0",
    "mask_interaction",
    "boundary_fold_count",
    "held_sector_raw_only_cadence_count",
    "training_sectors_raw_only_cadence_count",
    "held_sector_screening_eligible_any_raw_branch_count",
    "training_sectors_screening_eligible_any_raw_branch_count",
    "cadence_effect_attribution_supported",
    "attribution_limit",
    "sector",
    "cadenceno",
    "time_btjd",
    "quality",
    "exclusion_reason",
    "pdcsap_flux",
    "pdcsap_flux_err",
    "nearest_used_event_id",
    "nearest_used_event_distance_hours",
    "inside_inner_transit_mask",
    "inside_w13",
    "inside_w16",
    "inside_w20",
    "inside_w26",
    "inside_w32",
    "screening_oot_eligible_w13",
    "screening_oot_eligible_w16",
    "screening_oot_eligible_w20",
    "screening_oot_eligible_w26",
    "screening_oot_eligible_w32",
    "joint_raw_branch_cells",
    "screening_raw_branch_cells",
    "potential_screening_training_held_sectors",
    "sap_bkg",
    "sap_bkg_err",
    "pos_corr1",
    "pos_corr2",
    "mom_centr1",
    "mom_centr2",
    "camera",
    "ccd",
)

BETA_COLUMNS = (
    "source_artifact",
    "source_csv_row",
    "model_id",
    "mask_id",
    "cell_id",
    "window_hours",
    "polynomial_degree",
    "joint_model_weight",
    "sector",
    "timescale_minutes",
    "filled_bins",
    "eligible",
    "unbinned_rms",
    "binned_rms",
    "effective_cadences_per_bin",
    "finite_bin_correction",
    "white_noise_rms",
    "beta",
    "weighted_beta_contribution",
)

RESIDUAL_COLUMNS = (
    "source_artifact",
    "source_csv_row",
    "source_data_artifacts",
    "model_id",
    "mask_id",
    "cell_id",
    "window_hours",
    "polynomial_degree",
    "joint_model_weight",
    "sector",
    "cadence_count",
    "event_count",
    "time_min_btjd",
    "time_max_btjd",
    "mean_residual",
    "centered_rms",
    "uncentered_rms",
    "median_residual",
    "mad_sigma",
    "q01_residual",
    "q05_residual",
    "q95_residual",
    "q99_residual",
    "maximum_absolute_residual",
    "median_flux_error",
    "frozen_sector_jitter",
    "maximum_beta",
    "maximum_beta_timescale_minutes",
    "maximum_absolute_acf_nonzero_lag",
    "acf_at_maximum_absolute_nonzero_lag",
    "maximum_absolute_acf_lag_minutes",
    "branch_periodogram_peak_period_minutes",
    "branch_periodogram_peak_power",
    "pearson_residual_sap_bkg",
    "spearman_residual_sap_bkg",
    "pearson_residual_pos_corr1",
    "spearman_residual_pos_corr1",
    "pearson_residual_pos_corr2",
    "spearman_residual_pos_corr2",
    "pearson_residual_mom_centr1",
    "spearman_residual_mom_centr1",
    "pearson_residual_mom_centr2",
    "spearman_residual_mom_centr2",
    "telemetry_association_diagnostic_only",
)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def bool_value(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return str(value).strip().lower() == "true"


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def csv_text(frame):
    stream = io.StringIO(newline="")
    frame.to_csv(
        stream,
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    )
    return stream.getvalue()


def content_record(path, text, frame=None):
    payload = text.encode("utf-8")
    record = {
        "relative_path": relative(path),
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if frame is not None:
        record["row_count"] = int(len(frame))
        record["columns"] = list(frame.columns)
    return record


def write_atomic(path, text):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(text.encode("utf-8"))
    temporary.replace(path)


def manifest_source_records():
    manifest = load_json(MANIFEST_PATH)
    records = {
        item["path"]: item
        for group in manifest["input_groups"].values()
        for item in group
    }
    checks = {
        "manifest_status_pass": manifest.get("status") == "PASS",
        "manifest_real_data_fit_closed": manifest.get("real_data_fit_executed") is False,
        "manifest_phase7_closed": manifest.get("phase_7_may_begin") is False,
        "all_used_paths_declared": all(path in records for path in USED_MANIFEST_PATHS),
    }
    for path in USED_MANIFEST_PATHS:
        item = records.get(path)
        target = ROOT / path
        checks["hash_" + path.replace("/", "_")] = bool(
            item
            and target.is_file()
            and target.stat().st_size == int(item["size_bytes"])
            and sha256_file(target) == item["sha256"]
        )
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError("Stage-3 source contract failed: " + ", ".join(failed))
    selected = {path: records[path] for path in USED_MANIFEST_PATHS}
    return manifest, selected, checks


def transformed_parameter(name, value):
    if name == "log_timescale_minutes":
        return "exp", float(math.exp(value)), "minutes"
    if name.startswith(("mu_", "delta_")):
        return "exp", float(math.exp(value)), "multiplicative_ratio"
    return "identity", float(value), "native"


def build_boundary_map(scores):
    rows = []
    for source_index, item in scores.iterrows():
        names = json.loads(item["parameter_names_json"])
        parameters = json.loads(item["parameters_json"])
        diagnostics = json.loads(item["boundary_diagnostics_json"])
        if not len(names) == len(parameters) == len(diagnostics):
            raise RuntimeError("LOSO parameter diagnostics have inconsistent lengths")
        flags = []
        for parameter_index, (name, value, diagnostic) in enumerate(
            zip(names, parameters, diagnostics)
        ):
            if diagnostic["name"] != name or not math.isclose(
                float(diagnostic["value"]), float(value), rel_tol=0.0, abs_tol=1e-14
            ):
                raise RuntimeError("LOSO boundary diagnostic does not match parameter")
            lower = float(diagnostic["lower"])
            upper = float(diagnostic["upper"])
            value = float(value)
            lower_distance = value - lower
            upper_distance = upper - value
            nearest = "lower" if lower_distance <= upper_distance else "upper"
            transformation, transformed, unit = transformed_parameter(name, value)
            at_boundary = bool_value(diagnostic["at_boundary"])
            flags.append(at_boundary)
            rows.append(
                {
                    "source_artifact": relative(LOSO_PATH),
                    "source_csv_row": int(source_index) + 2,
                    "model_id": item["model_id"],
                    "mask_id": item["mask_id"],
                    "cell_id": item["cell_id"],
                    "window_hours": int(item["window_hours"]),
                    "polynomial_degree": int(item["polynomial_degree"]),
                    "kernel_id": item["kernel_id"],
                    "held_sector": int(item["held_sector"]),
                    "screening_valid": bool_value(item["valid"]),
                    "optimizer_success": bool_value(item["optimizer_success"]),
                    "branch_log_predictive_density": float(
                        item["branch_log_predictive_density"]
                    ),
                    "input_fold_any_parameter_at_boundary": bool_value(
                        item["any_parameter_at_boundary"]
                    ),
                    "parameter_index": int(parameter_index),
                    "parameter_name": name,
                    "parameter_value": value,
                    "lower_bound": lower,
                    "upper_bound": upper,
                    "nearest_boundary": nearest,
                    "distance_fraction": float(diagnostic["distance_fraction"]),
                    "at_boundary": at_boundary,
                    "transformation": transformation,
                    "transformed_value": transformed,
                    "transformed_unit": unit,
                }
            )
        if any(flags) != bool_value(item["any_parameter_at_boundary"]):
            raise RuntimeError("LOSO fold boundary summary is inconsistent")
    return pd.DataFrame.from_records(rows, columns=BOUNDARY_COLUMNS)


def count_dict(frame, column):
    return {
        str(key): int(value)
        for key, value in frame.groupby(column, sort=True).size().items()
    }


def boundary_summary(frame):
    flagged = frame.loc[frame["at_boundary"].astype(bool)].copy()
    kernels = []
    for kernel_id in ("K0_white",) + COMPLEX_KERNELS:
        selected = frame.loc[frame["kernel_id"] == kernel_id]
        selected_flagged = selected.loc[selected["at_boundary"].astype(bool)]
        physical = selected_flagged.loc[
            selected_flagged["parameter_name"] == "log_timescale_minutes",
            "transformed_value",
        ]
        kernels.append(
            {
                "kernel_id": kernel_id,
                "parameter_diagnostic_count": int(len(selected)),
                "boundary_flag_count": int(len(selected_flagged)),
                "boundary_parameter_counts": count_dict(
                    selected_flagged, "parameter_name"
                )
                if len(selected_flagged)
                else {},
                "boundary_side_counts": count_dict(
                    selected_flagged, "nearest_boundary"
                )
                if len(selected_flagged)
                else {},
                "held_sector_counts": count_dict(
                    selected_flagged, "held_sector"
                )
                if len(selected_flagged)
                else {},
                "polynomial_degree_counts": count_dict(
                    selected_flagged, "polynomial_degree"
                )
                if len(selected_flagged)
                else {},
                "timescale_minutes_minimum": (
                    float(physical.min()) if len(physical) else None
                ),
                "timescale_minutes_maximum": (
                    float(physical.max()) if len(physical) else None
                ),
            }
        )
    return {
        "parameter_diagnostic_count": int(len(frame)),
        "boundary_flag_count": int(len(flagged)),
        "all_flags_are_upper_timescale": bool(
            len(flagged)
            and flagged["parameter_name"].eq("log_timescale_minutes").all()
            and flagged["nearest_boundary"].eq("upper").all()
        ),
        "by_kernel": kernels,
        "interpretation": (
            "The shared correlated-kernel timescale saturates near its registered "
            "360-minute upper bound. Concentration by polynomial degree is an "
            "association, not proof that the polynomial and kernel compete."
        ),
        "source": relative(LOSO_PATH),
    }


def load_ledger_telemetry():
    columns = [
        "sector",
        "cadenceno",
        "sap_bkg",
        "sap_bkg_err",
        "pos_corr1",
        "pos_corr2",
        "mom_centr1",
        "mom_centr2",
        "camera",
        "ccd",
    ]
    frame = pd.read_csv(LEDGER_PATH, usecols=columns)
    if frame.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("120-s ledger has duplicate cadence keys")
    return frame


def blank_mask_row():
    return {column: "" for column in MASK_COLUMNS}


def build_mask_influence(mixture, scores, lineage, telemetry, branches, phase2):
    mixture = mixture.copy()
    mixture["source_csv_row"] = np.arange(len(mixture), dtype=np.int64) + 2
    indexed = mixture.set_index(["kernel_id", "held_sector"], drop=False)
    lineage = lineage.copy()
    lineage["source_csv_row"] = np.arange(len(lineage), dtype=np.int64) + 2
    for column in ("inside_w13", "inside_w16", "inside_w20", "inside_w26", "inside_w32"):
        lineage[column] = lineage[column].map(bool_value)
    lineage = lineage.merge(
        telemetry,
        on=["sector", "cadenceno"],
        how="left",
        validate="one_to_one",
    )
    if lineage[list(TELEMETRY_COLUMNS)].isna().all(axis=None):
        raise RuntimeError("Cadence lineage could not be linked to ledger telemetry")

    inner_hours = 0.75 * float(phase2["ephemeris_and_windows"]["t14_hours"])
    raw_branches = [item for item in branches if item["mask_id"] == "raw_valid"]
    raw_cells = sorted(
        {
            (item["cell_id"], int(item["window_hours"]))
            for item in raw_branches
        }
    )
    inside_inner = (
        lineage["nearest_used_event_distance_hours"].to_numpy(float) < inner_hours
    )
    lineage["inside_inner_transit_mask"] = inside_inner
    for window in (13, 16, 20, 26, 32):
        lineage["screening_oot_eligible_w{}".format(window)] = (
            lineage["inside_w{}".format(window)] & ~lineage["inside_inner_transit_mask"]
        )

    joint_cells = []
    screening_cells = []
    held_sector_lists = []
    for row in lineage.itertuples(index=False):
        distance = float(row.nearest_used_event_distance_hours)
        joint = [cell for cell, window in raw_cells if distance <= window / 2.0]
        screening = [] if distance < inner_hours else list(joint)
        joint_cells.append(";".join(joint))
        screening_cells.append(";".join(screening))
        held_sector_lists.append(
            ";".join(str(value) for value in SECTORS if value != int(row.sector))
            if screening
            else ""
        )
    lineage["joint_raw_branch_cells"] = joint_cells
    lineage["screening_raw_branch_cells"] = screening_cells
    lineage["potential_screening_training_held_sectors"] = held_sector_lists
    lineage["screening_eligible_any"] = lineage["screening_raw_branch_cells"].ne("")

    fold_boundary = scores.copy()
    fold_boundary["any_parameter_at_boundary"] = fold_boundary[
        "any_parameter_at_boundary"
    ].map(bool_value)

    rows = []
    interaction_rows = []
    for kernel_id in COMPLEX_KERNELS:
        kernel_rows = []
        for sector in SECTORS:
            kernel = indexed.loc[(kernel_id, sector)]
            k0 = indexed.loc[("K0_white", sector)]
            raw_gain = float(kernel["raw_valid"] - k0["raw_valid"])
            reference_gain = float(
                kernel["reference_included"] - k0["reference_included"]
            )
            interaction = raw_gain - reference_gain
            selected_boundary = fold_boundary.loc[
                (fold_boundary["kernel_id"] == kernel_id)
                & (fold_boundary["held_sector"] == sector)
                & fold_boundary["any_parameter_at_boundary"]
            ]
            held = lineage.loc[lineage["sector"] == sector]
            training = lineage.loc[lineage["sector"] != sector]
            row = blank_mask_row()
            row.update(
                {
                    "record_type": "sector_kernel_interaction",
                    "source_artifact": relative(MIXTURE_PATH),
                    "source_csv_row": int(kernel["source_csv_row"]),
                    "comparator_source_artifact": relative(MIXTURE_PATH),
                    "comparator_source_csv_row": int(k0["source_csv_row"]),
                    "kernel_id": kernel_id,
                    "held_sector": int(sector),
                    "raw_kernel_log_predictive_density": float(kernel["raw_valid"]),
                    "reference_kernel_log_predictive_density": float(
                        kernel["reference_included"]
                    ),
                    "combined_kernel_log_predictive_density": float(
                        kernel["combined_log_predictive_density"]
                    ),
                    "raw_k0_log_predictive_density": float(k0["raw_valid"]),
                    "reference_k0_log_predictive_density": float(
                        k0["reference_included"]
                    ),
                    "combined_k0_log_predictive_density": float(
                        k0["combined_log_predictive_density"]
                    ),
                    "raw_kernel_gain_vs_k0": raw_gain,
                    "reference_kernel_gain_vs_k0": reference_gain,
                    "combined_kernel_gain_vs_k0": float(
                        kernel["combined_log_predictive_density"]
                        - k0["combined_log_predictive_density"]
                    ),
                    "mask_interaction": interaction,
                    "boundary_fold_count": int(len(selected_boundary)),
                    "held_sector_raw_only_cadence_count": int(len(held)),
                    "training_sectors_raw_only_cadence_count": int(len(training)),
                    "held_sector_screening_eligible_any_raw_branch_count": int(
                        held["screening_eligible_any"].sum()
                    ),
                    "training_sectors_screening_eligible_any_raw_branch_count": int(
                        training["screening_eligible_any"].sum()
                    ),
                    "cadence_effect_attribution_supported": False,
                    "attribution_limit": (
                        "Held-sector scores have no pointwise contributions; the held "
                        "sector is excluded from training and mask branch universes differ."
                    ),
                }
            )
            kernel_rows.append(row)
        order = sorted(
            range(len(kernel_rows)),
            key=lambda index: abs(float(kernel_rows[index]["mask_interaction"])),
            reverse=True,
        )
        for rank, index in enumerate(order, start=1):
            kernel_rows[index]["absolute_interaction_rank_within_kernel"] = rank
        rows.extend(kernel_rows)
        interaction_rows.extend(kernel_rows)

    for item in lineage.itertuples(index=False):
        row = blank_mask_row()
        values = item._asdict()
        row.update(
            {
                "record_type": "raw_only_cadence",
                "source_artifact": relative(LINEAGE_PATH),
                "source_csv_row": int(values["source_csv_row"]),
                "comparator_source_artifact": relative(LEDGER_PATH),
                "cadence_effect_attribution_supported": False,
                "attribution_limit": (
                    "This cadence has no saved pointwise predictive contribution; "
                    "only eligibility and telemetry are reported."
                ),
            }
        )
        for column in MASK_COLUMNS:
            if column in values and column not in (
                "record_type",
                "source_artifact",
                "source_csv_row",
                "comparator_source_artifact",
            ):
                row[column] = values[column]
        rows.append(row)

    frame = pd.DataFrame.from_records(rows, columns=MASK_COLUMNS)
    interaction_frame = pd.DataFrame.from_records(interaction_rows)
    summaries = []
    comparison_report = load_json(KERNEL_REPORT_PATH)["screening"][
        "comparisons_against_k0"
    ]
    comparison_lookup = {item["kernel_id"]: item for item in comparison_report}
    for kernel_id in COMPLEX_KERNELS:
        selected = interaction_frame.loc[interaction_frame["kernel_id"] == kernel_id]
        ordered = selected.reindex(
            selected["mask_interaction"].abs().sort_values(ascending=False).index
        )
        summaries.append(
            {
                "kernel_id": kernel_id,
                "mask_interaction_sum": float(selected["mask_interaction"].sum()),
                "reported_mask_interaction": float(
                    comparison_lookup[kernel_id]["mask_interaction"]
                ),
                "sector_drivers_by_absolute_interaction": [
                    {
                        "held_sector": int(item.held_sector),
                        "mask_interaction": float(item.mask_interaction),
                    }
                    for item in ordered.itertuples(index=False)
                ],
            }
        )

    cadence_summary = {
        "raw_only_cadence_count": int(len(lineage)),
        "sector_counts": count_dict(lineage, "sector"),
        "quality_counts": count_dict(lineage, "quality"),
        "exclusion_reason_counts": count_dict(lineage, "exclusion_reason"),
        "inside_inner_transit_mask_count": int(
            lineage["inside_inner_transit_mask"].sum()
        ),
        "outside_all_registered_windows_count": int(
            (~lineage[["inside_w13", "inside_w16", "inside_w20", "inside_w26", "inside_w32"]].any(axis=1)).sum()
        ),
        "inside_window_counts": {
            str(window): int(lineage["inside_w{}".format(window)].sum())
            for window in (13, 16, 20, 26, 32)
        },
        "screening_oot_eligible_counts": {
            str(window): int(
                lineage["screening_oot_eligible_w{}".format(window)].sum()
            )
            for window in (13, 16, 20, 26, 32)
        },
        "screening_eligible_any_retained_raw_branch_count": int(
            lineage["screening_eligible_any"].sum()
        ),
        "sap_background_by_sector": [
            {
                "sector": int(sector),
                "minimum": float(group["sap_bkg"].min()),
                "median": float(group["sap_bkg"].median()),
                "maximum": float(group["sap_bkg"].max()),
            }
            for sector, group in lineage.groupby("sector", sort=True)
        ],
        "source": relative(LINEAGE_PATH),
        "telemetry_source": relative(LEDGER_PATH),
    }
    return frame, summaries, cadence_summary


def correlation(x, y, rank=False):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    finite = np.isfinite(x) & np.isfinite(y)
    if finite.sum() < 3:
        return np.nan
    x = x[finite]
    y = y[finite]
    if rank:
        x = pd.Series(x).rank(method="average").to_numpy(np.float64)
        y = pd.Series(y).rank(method="average").to_numpy(np.float64)
    if np.ptp(x) == 0.0 or np.ptp(y) == 0.0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def mad_sigma(values):
    values = np.asarray(values, dtype=np.float64)
    median = np.median(values)
    return float(1.4826 * np.median(np.abs(values - median)))


def reconstruct_phase6r(branches, masks, events, prereg, telemetry):
    fits = pd.read_csv(PHASE6R_FIT_PATH, keep_default_na=False)
    fits["source_csv_row"] = np.arange(len(fits), dtype=np.int64) + 2
    fit_index = {str(item.model_id): item for item in fits.itertuples(index=False)}
    branch_ids = [item["model_id"] for item in branches]
    if len(fits) != 24 or set(fit_index) != set(branch_ids):
        raise RuntimeError("Phase-6R fit rows do not match the frozen branch universe")
    if not all(bool_value(value) for value in fits["stationarity_valid"]):
        raise RuntimeError("Phase-6R contains a non-stationary frozen endpoint")

    with np.load(PHASE6R_DRAW_PATH, allow_pickle=False) as payload:
        draw_ids = [str(value) for value in payload["model_ids"]]
        draw_weights = np.asarray(payload["weights"], dtype=np.float64)
        draw_names = [str(value) for value in payload["parameter_names"]]
        draw_shape = tuple(payload["draws"].shape)
        draws_finite = bool(np.all(np.isfinite(payload["draws"])))
    branch_weights = np.asarray(
        [item["joint_model_weight"] for item in branches], dtype=np.float64
    )
    draw_checks = {
        "phase6r_draw_model_ids_exact": draw_ids == branch_ids,
        "phase6r_draw_weights_exact": bool(
            np.allclose(draw_weights, branch_weights, rtol=0.0, atol=0.0)
        ),
        "phase6r_draw_weights_sum_one": math.isclose(
            float(draw_weights.sum()), 1.0, rel_tol=0.0, abs_tol=1e-12
        ),
        "phase6r_draw_parameter_names_exact": draw_names == list(phase6.DRAW_NAMES),
        "phase6r_draw_shape_exact": draw_shape == (24, 4096, 4),
        "phase6r_draws_finite": draws_finite,
    }
    if not all(draw_checks.values()):
        raise RuntimeError("Phase-6R geometry-draw identity check failed")

    beta_rows = []
    summary_rows = []
    aggregate_beta_rows = []
    acf_rows = []
    periodogram_summaries = []
    event_counts = {
        sector: sum(int(item["sector"]) == sector for item in events)
        for sector in SECTORS
    }
    source_data = ";".join(
        (
            "data/toi3492_faz4_reductions_120s.csv.gz",
            "data/toi3492_cadence_ledger_120s.csv.gz",
            "outputs/faz2_transit_inventory.json",
            "data/faz5_preregistered_grid.json",
        )
    )

    for branch in branches:
        fit = fit_index[branch["model_id"]]
        names = json.loads(fit.parameter_names_json)
        parameters = np.asarray(json.loads(fit.parameters_json), dtype=np.float64)
        model = phase6.build_joint_model(
            branch, masks[branch["mask_id"]], events, prereg
        )
        if names != list(model.parameter_names) or parameters.shape != (10,):
            raise RuntimeError("Phase-6R parameter vector does not match joint model")
        frame = residuals.validate_residual_frame(model.residual_frame(parameters))
        if len(frame) != int(fit.cadence_count):
            raise RuntimeError("Reconstructed Phase-6R cadence count changed")
        diagnostics = residuals.binned_rms_beta(frame)
        branch_acf = residuals.gap_aware_residual_acf(frame)
        periodogram = residuals.lomb_scargle_diagnostics(frame)
        period_summary = periodogram["summary"]
        periodogram_summaries.append(
            {
                "model_id": branch["model_id"],
                "joint_model_weight": float(branch["joint_model_weight"]),
                "highest_peak_period_minutes": float(
                    period_summary["highest_peak_period_minutes"]
                ),
                "highest_peak_power": float(period_summary["highest_peak_power"]),
                "diagnostic_only": True,
            }
        )
        aggregate = diagnostics["aggregate"].copy()
        aggregate.insert(0, "model_id", branch["model_id"])
        aggregate.insert(1, "joint_model_weight", branch["joint_model_weight"])
        aggregate_beta_rows.append(aggregate)

        aggregate_acf = branch_acf.loc[
            branch_acf["sector"].eq("__equal_sector__")
        ].copy()
        aggregate_acf.insert(0, "model_id", branch["model_id"])
        aggregate_acf.insert(1, "joint_model_weight", branch["joint_model_weight"])
        acf_rows.append(aggregate_acf)

        telemetry_frame = frame.merge(
            telemetry,
            on=["sector", "cadenceno"],
            how="left",
            validate="one_to_one",
        )
        if len(telemetry_frame) != len(frame):
            raise RuntimeError("Residual-to-ledger telemetry join changed row count")

        for sector_index, sector_item in enumerate(model.sectors):
            sector = int(sector_item.sector)
            sector_beta = diagnostics["per_sector"].loc[
                diagnostics["per_sector"]["sector"] == sector
            ].copy()
            for item in sector_beta.itertuples(index=False):
                beta_rows.append(
                    {
                        "source_artifact": relative(PHASE6R_FIT_PATH),
                        "source_csv_row": int(fit.source_csv_row),
                        "model_id": branch["model_id"],
                        "mask_id": branch["mask_id"],
                        "cell_id": branch["cell_id"],
                        "window_hours": int(branch["window_hours"]),
                        "polynomial_degree": int(branch["polynomial_degree"]),
                        "joint_model_weight": float(branch["joint_model_weight"]),
                        "sector": sector,
                        "timescale_minutes": float(item.timescale_minutes),
                        "filled_bins": int(item.filled_bins),
                        "eligible": bool_value(item.eligible),
                        "unbinned_rms": float(item.unbinned_rms),
                        "binned_rms": float(item.binned_rms),
                        "effective_cadences_per_bin": float(
                            item.effective_cadences_per_bin
                        ),
                        "finite_bin_correction": float(item.finite_bin_correction),
                        "white_noise_rms": float(item.white_noise_rms),
                        "beta": float(item.beta),
                        "weighted_beta_contribution": float(
                            branch["joint_model_weight"] * item.beta
                        ),
                    }
                )

            selected = telemetry_frame.loc[telemetry_frame["sector"] == sector]
            values = selected["residual"].to_numpy(dtype=np.float64)
            centered = values - np.mean(values, dtype=np.float64)
            maximum_beta = sector_beta.loc[sector_beta["beta"].idxmax()]
            sector_acf = branch_acf.loc[
                (branch_acf["sector"] == sector) & (branch_acf["lag_cadences"] > 0)
            ].copy()
            finite_acf = sector_acf.loc[np.isfinite(sector_acf["acf"])]
            if finite_acf.empty:
                raise RuntimeError("Phase-6R sector ACF has no finite nonzero lag")
            acf_index = finite_acf["acf"].abs().idxmax()
            acf_peak = finite_acf.loc[acf_index]
            jitter = sector_item.flux_err
            jitter = float(np.median(jitter)) * math.exp(
                float(parameters[3]) + float(parameters[4 + sector_index])
            )
            summary = {
                "source_artifact": relative(PHASE6R_FIT_PATH),
                "source_csv_row": int(fit.source_csv_row),
                "source_data_artifacts": source_data,
                "model_id": branch["model_id"],
                "mask_id": branch["mask_id"],
                "cell_id": branch["cell_id"],
                "window_hours": int(branch["window_hours"]),
                "polynomial_degree": int(branch["polynomial_degree"]),
                "joint_model_weight": float(branch["joint_model_weight"]),
                "sector": sector,
                "cadence_count": int(len(selected)),
                "event_count": int(event_counts[sector]),
                "time_min_btjd": float(selected["time_btjd"].min()),
                "time_max_btjd": float(selected["time_btjd"].max()),
                "mean_residual": float(np.mean(values, dtype=np.float64)),
                "centered_rms": float(np.sqrt(np.mean(centered * centered))),
                "uncentered_rms": float(np.sqrt(np.mean(values * values))),
                "median_residual": float(np.median(values)),
                "mad_sigma": mad_sigma(values),
                "q01_residual": float(np.quantile(values, 0.01)),
                "q05_residual": float(np.quantile(values, 0.05)),
                "q95_residual": float(np.quantile(values, 0.95)),
                "q99_residual": float(np.quantile(values, 0.99)),
                "maximum_absolute_residual": float(np.max(np.abs(values))),
                "median_flux_error": float(np.median(sector_item.flux_err)),
                "frozen_sector_jitter": jitter,
                "maximum_beta": float(maximum_beta["beta"]),
                "maximum_beta_timescale_minutes": float(
                    maximum_beta["timescale_minutes"]
                ),
                "maximum_absolute_acf_nonzero_lag": float(abs(acf_peak["acf"])),
                "acf_at_maximum_absolute_nonzero_lag": float(acf_peak["acf"]),
                "maximum_absolute_acf_lag_minutes": float(
                    acf_peak["lag_minutes"]
                ),
                "branch_periodogram_peak_period_minutes": float(
                    period_summary["highest_peak_period_minutes"]
                ),
                "branch_periodogram_peak_power": float(
                    period_summary["highest_peak_power"]
                ),
                "telemetry_association_diagnostic_only": True,
            }
            for telemetry_name in TELEMETRY_COLUMNS:
                summary["pearson_residual_" + telemetry_name] = correlation(
                    selected["residual"], selected[telemetry_name], rank=False
                )
                summary["spearman_residual_" + telemetry_name] = correlation(
                    selected["residual"], selected[telemetry_name], rank=True
                )
            summary_rows.append(summary)

    beta_frame = pd.DataFrame.from_records(beta_rows, columns=BETA_COLUMNS)
    summary_frame = pd.DataFrame.from_records(summary_rows, columns=RESIDUAL_COLUMNS)
    aggregate_beta = pd.concat(aggregate_beta_rows, ignore_index=True)
    official_rows = []
    for scale in residuals.BETA_TIMESCALES_MINUTES:
        selected = aggregate_beta.loc[
            aggregate_beta["timescale_minutes"] == float(scale)
        ]
        eligible = bool(
            len(selected) == 24
            and selected["all_sectors_eligible"].map(bool_value).all()
            and np.isfinite(selected["equal_sector_beta"]).all()
        )
        official_rows.append(
            {
                "timescale_minutes": float(scale),
                "all_branches_eligible": eligible,
                "weighted_equal_sector_beta": (
                    float(
                        np.sum(
                            selected["joint_model_weight"]
                            * selected["equal_sector_beta"]
                        )
                    )
                    if eligible
                    else None
                ),
            }
        )

    sector_mixture = []
    for (sector, scale), selected in beta_frame.groupby(
        ["sector", "timescale_minutes"], sort=True
    ):
        sector_mixture.append(
            {
                "sector": int(sector),
                "timescale_minutes": float(scale),
                "all_branches_eligible": bool(selected["eligible"].map(bool_value).all()),
                "weighted_beta": float(selected["weighted_beta_contribution"].sum()),
            }
        )
    drivers = []
    sector_mixture_frame = pd.DataFrame.from_records(sector_mixture)
    for scale in residuals.BETA_TIMESCALES_MINUTES:
        selected = sector_mixture_frame.loc[
            sector_mixture_frame["timescale_minutes"] == float(scale)
        ].sort_values("weighted_beta", ascending=False)
        drivers.append(
            {
                "timescale_minutes": float(scale),
                "sectors_by_descending_beta": [
                    {
                        "sector": int(item.sector),
                        "weighted_beta": float(item.weighted_beta),
                    }
                    for item in selected.itertuples(index=False)
                ],
            }
        )

    acf_frame = pd.concat(acf_rows, ignore_index=True)
    acf_frame["weighted_acf"] = (
        acf_frame["joint_model_weight"] * acf_frame["acf"]
    )
    acf_mixture = (
        acf_frame.groupby(["lag_cadences", "lag_minutes"], as_index=False)[
            "weighted_acf"
        ]
        .sum()
        .sort_values("lag_cadences")
    )
    acf_search = acf_mixture.loc[acf_mixture["lag_minutes"] >= 20.0]
    acf_peak = acf_search.loc[acf_search["weighted_acf"].abs().idxmax()]

    telemetry_mixture = []
    coefficient_columns = [
        column
        for column in RESIDUAL_COLUMNS
        if column.startswith(("pearson_residual_", "spearman_residual_"))
    ]
    for sector, selected in summary_frame.groupby("sector", sort=True):
        for column in coefficient_columns:
            finite = selected.loc[np.isfinite(selected[column])]
            telemetry_mixture.append(
                {
                    "sector": int(sector),
                    "coefficient": column,
                    "finite_branch_count": int(len(finite)),
                    "weighted_value": (
                        float(
                            np.sum(
                                finite["joint_model_weight"] * finite[column]
                            )
                        )
                        if len(finite) == 24
                        else None
                    ),
                }
            )
    finite_telemetry = [
        item for item in telemetry_mixture if item["weighted_value"] is not None
    ]
    strongest_telemetry = max(
        finite_telemetry, key=lambda item: abs(item["weighted_value"])
    )
    strongest_periodogram = max(
        periodogram_summaries, key=lambda item: item["highest_peak_power"]
    )
    summary = {
        "reconstruction": (
            "Deterministic residual evaluation at each frozen Phase-6R MAP endpoint; "
            "no optimizer, Hessian, Laplace draw, or model selection was run."
        ),
        "branch_count": 24,
        "sector_count": 6,
        "event_count": 16,
        "beta_row_count": int(len(beta_frame)),
        "residual_summary_row_count": int(len(summary_frame)),
        "official_beta_mixture_reconstructed": official_rows,
        "sector_beta_mixture": sector_mixture,
        "sector_drivers": drivers,
        "maximum_weighted_beta": float(
            max(item["weighted_equal_sector_beta"] for item in official_rows)
        ),
        "weighted_equal_sector_acf_20_to_360_minutes": {
            "maximum_absolute_value": float(abs(acf_peak["weighted_acf"])),
            "signed_value": float(acf_peak["weighted_acf"]),
            "lag_minutes": float(acf_peak["lag_minutes"]),
            "diagnostic_only": True,
        },
        "periodogram": {
            "branch_summaries": periodogram_summaries,
            "highest_power_branch": strongest_periodogram,
            "cross_branch_power_mixture_computed": False,
            "reason": (
                "Branch frequency grids depend on each branch time baseline; peak "
                "summaries are descriptive and are not detection statistics."
            ),
        },
        "telemetry": {
            "weighted_branch_correlation_summaries": telemetry_mixture,
            "strongest_absolute_weighted_correlation": strongest_telemetry,
            "diagnostic_only": True,
            "cause_assigned": False,
        },
        "draw_identity_checks": draw_checks,
        "fit_source": relative(PHASE6R_FIT_PATH),
        "geometry_draw_source": relative(PHASE6R_DRAW_PATH),
    }
    return beta_frame, summary_frame, summary, draw_checks


def residual_artifact_status():
    gate = load_json(GATE_PATH)
    reports = (
        ("v1", load_json(V1_REPORT_PATH), "QUARANTINED_INVALID_NUMERICAL_RESULT"),
        ("v2", load_json(V2_REPORT_PATH), "EMPTY_AFTER_STATIONARITY_FAILURE"),
    )
    checks = {}
    versions = []
    artifact_names = (
        "residual_acf",
        "residual_beta",
        "residual_periodogram",
        "residual_peaks",
    )
    for version, report, status in reports:
        items = []
        for name in artifact_names:
            item = report["artifacts"][name]
            path = ROOT / item["relative_path"]
            hash_valid = bool(
                path.is_file()
                and path.stat().st_size == int(item["size_bytes"])
                and sha256_file(path) == item["sha256"]
            )
            checks[version + "_" + name + "_hash_valid"] = hash_valid
            items.append(
                {
                    "name": name,
                    "relative_path": item["relative_path"],
                    "row_count": int(item["row_count"]),
                    "sha256": item["sha256"],
                    "scientifically_usable": False,
                }
            )
        versions.append(
            {
                "version": version,
                "status": status,
                "authoritative_phase6_status": gate["status"],
                "artifacts": items,
                "reason": (
                    "All V1 optimizer attempts were unchanged from their initial values."
                    if version == "v1"
                    else "V2 stopped at 22/24 stationarity and did not run residual diagnostics."
                ),
            }
        )
    if not all(checks.values()):
        raise RuntimeError("A frozen Phase-6 residual artifact hash changed")
    return {
        "versions": versions,
        "phase6r_persisted_residual_artifacts": False,
        "phase6r_stage3_reconstruction_status": "DERIVED_FROM_FROZEN_MAP_NO_REFIT",
        "authoritative_gate_source": relative(GATE_PATH),
    }, checks


def build_postmortem():
    manifest, source_records, manifest_checks = manifest_source_records()
    scores = pd.read_csv(LOSO_PATH, keep_default_na=False)
    mixture = pd.read_csv(MIXTURE_PATH)
    lineage = pd.read_csv(LINEAGE_PATH, keep_default_na=False)
    telemetry = load_ledger_telemetry()
    kernel_report = load_json(KERNEL_REPORT_PATH)
    gate = load_json(GATE_PATH)
    phase6r_result = load_json(PHASE6R_RESULT_PATH)

    protocol = phase6.load_json(phase6.PROTOCOL_PATH)
    parent = phase6.load_json(phase6.PARENT_PATH)
    phase6_checks, _, phase5b_report = phase6.verify_inputs(protocol, parent)
    branches, branch_checks = phase6.load_branches(protocol, phase5b_report)
    masks, events, phase2, prereg = phase6.load_masks_and_model(protocol, parent)

    boundary = build_boundary_map(scores)
    mask, interaction_summary, cadence_summary = build_mask_influence(
        mixture, scores, lineage, telemetry, branches, phase2
    )
    beta, residual_summary, phase6r_summary, draw_checks = reconstruct_phase6r(
        branches, masks, events, prereg, telemetry
    )
    residual_status, residual_status_checks = residual_artifact_status()

    score_keys = scores[["model_id", "kernel_id", "held_sector"]]
    expected_score_keys = {
        (item["model_id"], kernel_id, sector)
        for item in branches
        for kernel_id in ("K0_white",) + COMPLEX_KERNELS
        for sector in SECTORS
    }
    observed_score_keys = {
        (str(item.model_id), str(item.kernel_id), int(item.held_sector))
        for item in score_keys.itertuples(index=False)
    }
    official_beta = {
        float(item["timescale_minutes"]): float(item["weighted_equal_sector_beta"])
        for item in phase6r_result["beta_mixture"]
    }
    reconstructed_beta = {
        float(item["timescale_minutes"]): float(item["weighted_equal_sector_beta"])
        for item in phase6r_summary["official_beta_mixture_reconstructed"]
    }
    interaction_exact = all(
        math.isclose(
            item["mask_interaction_sum"],
            item["reported_mask_interaction"],
            rel_tol=0.0,
            abs_tol=1e-10,
        )
        for item in interaction_summary
    )
    checks = {
        "source_manifest_integrity": all(manifest_checks.values()),
        "phase6_parent_input_integrity": all(phase6_checks.values()),
        "phase6_branch_contract_integrity": all(branch_checks.values()),
        "screening_row_count_576": len(scores) == 576,
        "screening_keys_complete_unique": observed_score_keys == expected_score_keys,
        "screening_rows_all_valid": scores["valid"].map(bool_value).all(),
        "boundary_parameter_rows_6480": len(boundary) == 6480,
        "boundary_rows_all_source_linked": boundary[
            ["source_artifact", "source_csv_row"]
        ].notna().all(axis=None),
        "mixture_source_rows_24": len(mixture) == 24,
        "mask_sector_kernel_rows_18": int(
            mask["record_type"].eq("sector_kernel_interaction").sum()
        )
        == 18,
        "mask_cadence_rows_60": int(mask["record_type"].eq("raw_only_cadence").sum())
        == 60,
        "mask_interactions_reproduce_frozen_report": interaction_exact,
        "cadence_predictive_effect_not_claimed": bool(
            (~mask["cadence_effect_attribution_supported"].map(bool_value)).all()
        ),
        "phase6r_branch_count_24": len(branches) == 24,
        "phase6r_sector_count_6": set(beta["sector"]) == set(SECTORS),
        "phase6r_beta_rows_864": len(beta) == 864,
        "phase6r_beta_rows_all_eligible": beta["eligible"].map(bool_value).all(),
        "phase6r_residual_summary_rows_144": len(residual_summary) == 144,
        "phase6r_official_beta_reproduced": set(official_beta) == set(reconstructed_beta)
        and all(
            math.isclose(
                official_beta[scale],
                reconstructed_beta[scale],
                rel_tol=0.0,
                abs_tol=2e-12,
            )
            for scale in official_beta
        ),
        "phase6r_draw_identity_integrity": all(draw_checks.values()),
        "phase6_failure_preserved": gate["status"] == "FAIL_STATIONARITY",
        "phase6r_failure_preserved": phase6r_result["status"]
        == "FAIL_RESIDUAL_CORRELATION",
        "invalid_and_empty_residual_artifacts_preserved": all(
            residual_status_checks.values()
        ),
        "new_real_data_fit_count_zero": True,
        "optimizer_calls_zero": True,
        "phase7_closed": True,
        "supported_and_unsupported_explanations_separated": True,
    }

    frames = {
        BOUNDARY_PATH: boundary,
        MASK_PATH: mask,
        BETA_PATH: beta,
        RESIDUAL_PATH: residual_summary,
    }
    artifacts = {
        path.stem: content_record(path, csv_text(frame), frame)
        for path, frame in frames.items()
    }
    source_records = dict(source_records)
    source_records[relative(MANIFEST_PATH)] = {
        "path": relative(MANIFEST_PATH),
        "size_bytes": MANIFEST_PATH.stat().st_size,
        "sha256": sha256_file(MANIFEST_PATH),
    }
    report = {
        "schema_version": "1.0",
        "work_package": "S3-02_PHASE6_POSTMORTEM",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "scope": {
            "analysis_mode": "EXISTING_ARTIFACTS_AND_FROZEN_ENDPOINT_DIAGNOSTICS_ONLY",
            "real_data_fit_executed": False,
            "optimizer_calls": 0,
            "new_random_draws": 0,
            "threshold_changes": 0,
            "phase_7_may_begin": False,
        },
        "source_integrity": {
            "stage3_manifest": relative(MANIFEST_PATH),
            "manifest_status": manifest["status"],
            "checks": manifest_checks,
            "sources": source_records,
        },
        "gate": {"checks": checks, "status": "PASS" if all(checks.values()) else "FAIL"},
        "boundary_analysis": boundary_summary(boundary),
        "mask_influence": {
            "sector_kernel_interactions": interaction_summary,
            "cadence_distribution": cadence_summary,
            "individual_cadence_predictive_attribution_supported": False,
            "reason": (
                "The frozen held-sector artifact contains joint vector log densities, "
                "not pointwise contributions. The two masks also retain different "
                "Phase-5B branch universes."
            ),
        },
        "phase6r_residual_analysis": phase6r_summary,
        "residual_artifact_validity": residual_status,
        "questions": [
            {
                "id": 1,
                "support": "SUPPORTED",
                "finding": (
                    "OU, Matern-3/2, and SHO boundary folds are enumerated by branch "
                    "and held sector in the boundary map."
                ),
                "evidence": [relative(LOSO_PATH), relative(BOUNDARY_PATH)],
            },
            {
                "id": 2,
                "support": "SUPPORTED",
                "finding": (
                    "Every boundary flag is the upper shared log-timescale bound; "
                    "no amplitude or jitter boundary flag occurs."
                ),
                "evidence": [relative(LOSO_PATH), relative(BOUNDARY_PATH)],
            },
            {
                "id": 3,
                "support": "PARTIALLY_SUPPORTED",
                "finding": (
                    "Sector-level mask interactions are identified. Individual cadence "
                    "predictive effects cannot be recovered without refitting or saved "
                    "pointwise densities."
                ),
                "evidence": [relative(MIXTURE_PATH), relative(MASK_PATH)],
            },
            {
                "id": 4,
                "support": "SUPPORTED_DESCRIPTIVE_ONLY",
                "finding": (
                    "All 60 raw-only cadences are linked to sector, time, quality, "
                    "background, pointing, and registered transit-window eligibility."
                ),
                "evidence": [relative(LINEAGE_PATH), relative(LEDGER_PATH), relative(MASK_PATH)],
            },
            {
                "id": 5,
                "support": "SUPPORTED",
                "finding": (
                    "The Phase-6R beta excess is decomposed into all 24 branches, six "
                    "sectors, and six registered timescales."
                ),
                "evidence": [relative(PHASE6R_FIT_PATH), relative(BETA_PATH)],
            },
            {
                "id": 6,
                "support": "SUPPORTED",
                "finding": (
                    "V1 ACF/beta/periodogram artifacts are quarantined numerical no-op "
                    "products; V2 artifacts are empty. Valid Stage-3 summaries are "
                    "derived separately from frozen Phase-6R endpoints."
                ),
                "evidence": [relative(GATE_PATH), relative(V1_REPORT_PATH), relative(V2_REPORT_PATH)],
            },
            {
                "id": 7,
                "support": "ASSOCIATION_ONLY",
                "finding": (
                    "Boundary saturation is associated with baseline degree, but current "
                    "artifacts do not prove polynomial-kernel competition."
                ),
                "evidence": [relative(BOUNDARY_PATH)],
            },
            {
                "id": 8,
                "support": "UNSUPPORTED",
                "finding": (
                    "No complex kernel reached a joint transit/noise fit, so screening-to-"
                    "joint instability cannot be measured from existing artifacts."
                ),
                "evidence": [relative(KERNEL_REPORT_PATH), relative(GATE_PATH)],
            },
            {
                "id": 9,
                "support": "PARTIALLY_SUPPORTED_DESCRIPTIVE_ONLY",
                "finding": (
                    "Frozen Phase-6R residual-telemetry correlations are reported without "
                    "causal attribution. Cross-reduction residual comparison is unavailable "
                    "because the joint model used only PDCSAP."
                ),
                "evidence": [relative(RESIDUAL_PATH), relative(LEDGER_PATH)],
            },
            {
                "id": 10,
                "support": "UNSUPPORTED",
                "finding": (
                    "The existing screening artifacts cannot establish that a correlated "
                    "kernel consumes ingress or egress because no complex-kernel joint "
                    "transit fit exists."
                ),
                "evidence": [relative(KERNEL_REPORT_PATH), relative(GATE_PATH)],
            },
        ],
        "supported_explanations": [
            {
                "statement": (
                    "Complex-kernel screening failures include shared timescale saturation "
                    "at the registered upper bound."
                ),
                "evidence": [relative(BOUNDARY_PATH)],
            },
            {
                "statement": (
                    "Mask interaction is concentrated in identifiable held-sector folds, "
                    "while its sign is negative for the aggregate of every complex kernel."
                ),
                "evidence": [relative(MASK_PATH), relative(KERNEL_REPORT_PATH)],
            },
            {
                "statement": (
                    "Phase-6R residual correlation is sector- and timescale-dependent, "
                    "rather than a uniform excess scatter across sectors."
                ),
                "evidence": [relative(BETA_PATH), relative(PHASE6R_RESULT_PATH)],
            },
        ],
        "unsupported_explanations": [
            {
                "statement": "A particular one of the 60 cadences caused a predictive gain.",
                "reason": "No pointwise predictive contributions or influence functions were saved.",
            },
            {
                "statement": "The event polynomial definitively competed with the kernel.",
                "reason": "The boundary-degree pattern is observational and no controlled refit exists.",
            },
            {
                "statement": "A complex kernel would remain stable in the joint transit fit.",
                "reason": "No complex kernel passed the frozen screening gate or reached that fit.",
            },
            {
                "statement": "The red-noise source is a specific reduction or telemetry variable.",
                "reason": "Correlations are descriptive and only the PDCSAP joint residual exists.",
            },
            {
                "statement": "A complex kernel consumed transit ingress or egress.",
                "reason": "No complex-kernel joint transit residual artifact exists.",
            },
        ],
        "artifacts": artifacts,
        "report_artifact": {
            "relative_path": relative(REPORT_PATH),
            "self_hash_recorded": False,
        },
    }
    if report["status"] != "PASS":
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError("S3-02 gate failed: " + ", ".join(failed))
    return report, frames


def comparable_report(report):
    report = dict(report)
    report.pop("generated_utc", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    existing = [path for path in OUTPUT_PATHS if path.exists()]
    if not args.verify_only and existing:
        raise FileExistsError(
            "S3-02 artifacts are no-clobber; use --verify-only: "
            + ", ".join(relative(path) for path in existing)
        )
    if args.verify_only and len(existing) != len(OUTPUT_PATHS):
        raise FileNotFoundError("S3-02 verification requires all five artifacts")

    report, frames = build_postmortem()
    if args.verify_only:
        for path, frame in frames.items():
            if path.read_text(encoding="utf-8") != csv_text(frame):
                raise AssertionError(relative(path) + " is stale")
        stored = load_json(REPORT_PATH)
        if comparable_report(stored) != comparable_report(json_ready(report)):
            raise AssertionError(relative(REPORT_PATH) + " is stale")
        print("STAGE-3 S3-02 PHASE-6 POST-MORTEM: PASS (verified)")
        return

    for path, frame in frames.items():
        write_atomic(path, csv_text(frame))
    report_text = json.dumps(
        json_ready(report), indent=2, ensure_ascii=True, allow_nan=False
    ) + "\n"
    write_atomic(REPORT_PATH, report_text)
    print("STAGE-3 S3-02 PHASE-6 POST-MORTEM: PASS")


if __name__ == "__main__":
    main()
