"""Class-specific synthetic-calibration metrics and gates.

The reducer calls these pure functions. They perform no file I/O and reject
missing rows instead of silently dropping them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.special import logsumexp

from .contracts import ContractError


GEOMETRY_PARAMETERS = ("rp_rs", "a_rs", "impact_parameter", "t14_hours")


@dataclass(frozen=True)
class GateResult:
    status: str
    checks: Mapping[str, bool]
    metrics: Mapping


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], name: str):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ContractError("{} is missing columns: {}".format(name, missing))
    if frame.empty:
        raise ContractError("{} is empty".format(name))


def realization_selection_scores(screening: pd.DataFrame) -> pd.DataFrame:
    required = (
        "class_ordinal", "realization_index", "model_id", "held_sector",
        "joint_model_weight", "k0_score", "m1_score",
    )
    _require_columns(screening, required, "screening records")
    if screening.duplicated([
            "class_ordinal", "realization_index", "model_id", "held_sector"]).any():
        raise ContractError("screening records contain duplicate task keys")
    if not np.isfinite(screening[["k0_score", "m1_score", "joint_model_weight"]]).all().all():
        raise ContractError("screening records contain non-finite scores or weights")
    branch = screening.groupby(
        ["class_ordinal", "realization_index", "model_id", "joint_model_weight"],
        sort=True,
        as_index=False,
    )[["k0_score", "m1_score"]].sum()
    rows = []
    for (class_ordinal, realization_index), group in branch.groupby(
            ["class_ordinal", "realization_index"], sort=True):
        weights = group["joint_model_weight"].to_numpy(np.float64)
        if len(group) != 24 or np.any(weights <= 0.0) or not np.isclose(weights.sum(), 1.0):
            raise ContractError("realization does not contain the exact weighted 24-branch universe")
        log_weights = np.log(weights)
        k0 = float(logsumexp(log_weights + group["k0_score"].to_numpy(np.float64)))
        m1 = float(logsumexp(log_weights + group["m1_score"].to_numpy(np.float64)))
        rows.append({
            "class_ordinal": int(class_ordinal),
            "realization_index": int(realization_index),
            "k0_mixture_score": k0,
            "m1_mixture_score": m1,
            "delta_elpd": m1 - k0,
            "selection": "M1" if m1 > k0 else "K0" if k0 > m1 else "NEITHER",
        })
    return pd.DataFrame(rows)


def selection_metrics(realizations: pd.DataFrame, white_class=0, nominal_class=1):
    _require_columns(
        realizations,
        ("class_ordinal", "realization_index", "delta_elpd", "selection"),
        "realization selection scores",
    )
    white = realizations.loc[realizations["class_ordinal"] == white_class]
    nominal = realizations.loc[realizations["class_ordinal"] == nominal_class]
    if white.empty or nominal.empty:
        raise ContractError("C01 or C02 selection population is missing")
    return {
        "false_m1_rate_on_white": float(np.mean(white["selection"] == "M1")),
        "true_m1_rate_on_nominal": float(np.mean(nominal["selection"] == "M1")),
        "white_neither_rate": float(np.mean(white["selection"] == "NEITHER")),
        "nominal_neither_rate": float(np.mean(nominal["selection"] == "NEITHER")),
    }


def nominal_geometry_metrics(recovery: pd.DataFrame, nominal_class=1):
    required = (
        "class_ordinal", "realization_index", "model_id", "joint_model_weight",
        "injected_rp_rs", "injected_a_rs", "injected_impact_parameter",
        "injected_t14_hours", "recovered_rp_rs", "recovered_a_rs",
        "recovered_impact_parameter", "recovered_t14_hours",
    )
    for parameter in GEOMETRY_PARAMETERS:
        required += (
            "{}_q025".format(parameter), "{}_q16".format(parameter),
            "{}_q84".format(parameter), "{}_q975".format(parameter),
        )
    _require_columns(recovery, required, "recovery records")
    selected = recovery.loc[recovery["class_ordinal"] == nominal_class].copy()
    if selected.empty:
        raise ContractError("C02 recovery population is missing")
    if selected.duplicated(["realization_index", "model_id"]).any():
        raise ContractError("C02 recovery records contain duplicate branch keys")
    rows = []
    for realization_index, group in selected.groupby("realization_index", sort=True):
        if len(group) != 24:
            raise ContractError("C02 realization is missing recovery branches")
        weights = group["joint_model_weight"].to_numpy(np.float64)
        if np.any(weights <= 0.0) or not np.isclose(weights.sum(), 1.0):
            raise ContractError("C02 recovery branch weights are invalid")
        row = {"realization_index": int(realization_index)}
        for parameter in GEOMETRY_PARAMETERS:
            injected_column = "injected_{}".format(parameter)
            recovered_column = "recovered_{}".format(parameter)
            injected_values = group[injected_column].to_numpy(np.float64)
            if not np.allclose(injected_values, injected_values[0], rtol=0.0, atol=0.0):
                raise ContractError("injected geometry differs across branches")
            injected = float(injected_values[0])
            recovered = float(np.sum(weights * group[recovered_column].to_numpy(np.float64)))
            row["{}_bias".format(parameter)] = recovered - injected
            row["{}_covered_68".format(parameter)] = bool(np.sum(
                weights * (
                    (group["{}_q16".format(parameter)] <= injected)
                    & (group["{}_q84".format(parameter)] >= injected)
                ).to_numpy(float)
            ) >= 0.5)
            row["{}_covered_95".format(parameter)] = bool(np.sum(
                weights * (
                    (group["{}_q025".format(parameter)] <= injected)
                    & (group["{}_q975".format(parameter)] >= injected)
                ).to_numpy(float)
            ) >= 0.5)
        injected_depth = float(group["injected_rp_rs"].iloc[0]) ** 2
        recovered_depth = float(np.sum(
            weights * np.square(group["recovered_rp_rs"].to_numpy(np.float64))
        ))
        row["transit_depth_attenuation_fraction"] = (
            injected_depth - recovered_depth
        ) / injected_depth
        rows.append(row)
    per_realization = pd.DataFrame(rows)
    summary = {}
    for parameter in GEOMETRY_PARAMETERS:
        biases = per_realization["{}_bias".format(parameter)].to_numpy(np.float64)
        if len(biases) < 2 or not np.isfinite(biases).all():
            raise ContractError("C02 bias population is incomplete")
        summary["{}_bias_median".format(parameter)] = float(np.median(biases))
        summary["{}_bias_standard_deviation".format(parameter)] = float(np.std(biases, ddof=1))
        summary["{}_coverage_68".format(parameter)] = float(np.mean(
            per_realization["{}_covered_68".format(parameter)]
        ))
        summary["{}_coverage_95".format(parameter)] = float(np.mean(
            per_realization["{}_covered_95".format(parameter)]
        ))
    summary["transit_depth_attenuation_median"] = float(np.median(
        per_realization["transit_depth_attenuation_fraction"]
    ))
    return per_realization, summary


def derive_null_threshold(recovery: pd.DataFrame, null_class=10):
    _require_columns(
        recovery,
        ("class_ordinal", "realization_index", "model_id", "delta_map"),
        "recovery records",
    )
    selected = recovery.loc[recovery["class_ordinal"] == null_class]
    if selected.empty or not np.isfinite(selected["delta_map"]).all():
        raise ContractError("C11 null distribution is incomplete or non-finite")
    per_realization = selected.groupby("realization_index", sort=True)["delta_map"].max()
    threshold = float(per_realization.max())
    detections = int(np.sum(per_realization.to_numpy(np.float64) > threshold))
    return {
        "delta_detect": threshold,
        "detection_rule": "delta_map > delta_detect",
        "null_realization_count": int(len(per_realization)),
        "false_detection_count": detections,
    }


def evaluate_development_gates(selection, geometry, null, thresholds: Mapping) -> GateResult:
    model = thresholds["model_selection"]
    transit = thresholds["transit"]
    checks = {
        "false_m1_rate": selection["false_m1_rate_on_white"]
        <= float(model["false_m1_rate_on_white_max"]),
        "true_m1_rate": selection["true_m1_rate_on_nominal"]
        >= float(model["true_m1_rate_on_m1_minimum"]),
        "null_false_detection": null["false_detection_count"] == 0,
        "coverage_68": all(
            geometry["{}_coverage_68".format(parameter)]
            >= float(transit["coverage_68_minimum"])
            for parameter in GEOMETRY_PARAMETERS
        ),
        "coverage_95": all(
            geometry["{}_coverage_95".format(parameter)]
            >= float(transit["coverage_95_minimum"])
            for parameter in GEOMETRY_PARAMETERS
        ),
        "transit_attenuation": geometry["transit_depth_attenuation_median"]
        <= float(transit["transit_depth_attenuation_max"]),
    }
    return GateResult(
        status="PASS" if all(checks.values()) else "FAIL",
        checks=checks,
        metrics={"selection": selection, "geometry": geometry, "null": null},
    )
