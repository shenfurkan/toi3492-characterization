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

from .contracts import ContractError, GEOMETRY_PARAMETERS


@dataclass(frozen=True)
class GateResult:
    """Overall gate outcome.

    ``checks`` maps each gate to ``PASS``, ``FAIL``, or ``NOT_EVALUATED``.
    The overall status is ``FAIL`` if any gate fails, ``INCOMPLETE`` if any
    gate cannot be evaluated (missing data or unfrozen tolerance), and
    ``PASS`` only when every declared gate passes.
    """

    status: str
    checks: Mapping[str, str]
    metrics: Mapping


BRANCH_MIXTURE_KINDS = ("log_evidence", "weighted_mean", "max")
DEFAULT_BRANCH_MIXTURE_RULE = {
    "selection": "log_evidence",
    "geometry": "weighted_quantile",
    "null": "max",
}
NULL_THRESHOLD_RULES = ("in_sample_max", "order_statistic_loo", "held_out_split")


def branch_mixture_rule(protocol: Mapping) -> Mapping:
    """Resolve the single rule that drives every branch combination.

    Frozen protocols carry ``branch_mixture_rule``; development protocols get
    the provisional default, explicitly flagged so summaries cannot hide it.
    """
    rule = protocol.get("branch_mixture_rule")
    if rule is None:
        return {**DEFAULT_BRANCH_MIXTURE_RULE, "status": "PROVISIONAL_DEFAULT"}
    if not isinstance(rule, Mapping) or set(rule) != {"selection", "geometry", "null"}:
        raise ContractError("branch_mixture_rule must map selection/geometry/null")
    allowed = {
        "selection": {"log_evidence"},
        "geometry": {"weighted_quantile", "weighted_mean"},
        "null": set(BRANCH_MIXTURE_KINDS),
    }
    for name, kinds in allowed.items():
        if rule[name] not in kinds:
            raise ContractError(
                "branch_mixture_rule.{} must be one of {}".format(name, sorted(kinds))
            )
    return {**rule, "status": "FROZEN"}


def combine_branches(kind: str, values, weights=None) -> float:
    """The single scalar branch-combination kernel used by all metrics."""
    values = np.asarray(values, dtype=np.float64)
    if values.size == 0 or not np.isfinite(values).all():
        raise ContractError("branch values are empty or non-finite")
    if kind == "max":
        return float(values.max())
    if weights is None:
        raise ContractError("branch weights are required for kind {}".format(kind))
    weights = np.asarray(weights, dtype=np.float64)
    if (
        weights.shape != values.shape
        or (weights <= 0.0).any()
        or not np.isclose(weights.sum(), 1.0)
    ):
        raise ContractError("branch weights are not a normalized positive vector")
    if kind == "log_evidence":
        return float(logsumexp(np.log(weights) + values))
    if kind == "weighted_mean":
        return float(np.sum(weights * values))
    raise ContractError("unknown branch mixture kind: {}".format(kind))


def _piecewise_cdf(anchors, x) -> float:
    q025, q16, q84, q975 = (float(point) for point in anchors)
    if x <= q025:
        return 0.0
    if x >= q975:
        return 1.0
    for (x0, p0), (x1, p1) in zip(
        ((q025, 0.025), (q16, 0.16), (q84, 0.84)), ((q16, 0.16), (q84, 0.84), (q975, 0.975))
    ):
        if x0 <= x <= x1:
            if x1 == x0:
                return p1
            return p0 + (p1 - p0) * (x - x0) / (x1 - x0)
    return 1.0


def mixture_quantiles(anchor_rows, weights, levels=(0.025, 0.16, 0.84, 0.975)) -> Mapping:
    """Deterministic branch-mixture posterior quantiles (quantile_mixture_v1).

    Each branch contributes its four anchor quantiles; its CDF is approximated
    piecewise-linearly between them and clamped outside. The mixture CDF is
    the weight average; levels are read off by interpolation.
    """
    anchors = np.asarray(anchor_rows, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if anchors.ndim != 2 or anchors.shape[1] != 4 or not np.isfinite(anchors).all():
        raise ContractError("branch quantile anchors are malformed")
    if len(weights) != len(anchors) or (weights <= 0.0).any() or not np.isclose(weights.sum(), 1.0):
        raise ContractError("branch weights are not a normalized positive vector")
    grid = np.sort(np.unique(anchors))
    cdf = np.array([
        float(np.sum(weights * np.array([_piecewise_cdf(row, x) for row in anchors])))
        for x in grid
    ])
    result = {}
    for level in levels:
        result[float(level)] = float(np.interp(float(level), cdf, grid))
    return result


def _require_columns(frame: pd.DataFrame, columns: Sequence[str], name: str):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ContractError("{} is missing columns: {}".format(name, missing))
    if frame.empty:
        raise ContractError("{} is empty".format(name))


def realization_selection_scores(
    screening: pd.DataFrame, selection_kind: str = "log_evidence",
) -> pd.DataFrame:
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
        k0 = combine_branches(
            selection_kind, group["k0_score"].to_numpy(np.float64), weights,
        )
        m1 = combine_branches(
            selection_kind, group["m1_score"].to_numpy(np.float64), weights,
        )
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


def nominal_geometry_metrics(
    recovery: pd.DataFrame, nominal_class=1, geometry_kind: str = "weighted_quantile",
):
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
            recovered = combine_branches(
                "weighted_mean", group[recovered_column].to_numpy(np.float64), weights,
            )
            row["{}_bias".format(parameter)] = recovered - injected
            anchors = group[[
                "{}_q025".format(parameter), "{}_q16".format(parameter),
                "{}_q84".format(parameter), "{}_q975".format(parameter),
            ]].to_numpy(np.float64)
            if geometry_kind == "weighted_quantile":
                mixture = mixture_quantiles(anchors, weights)
            elif geometry_kind == "weighted_mean":
                mixture = {
                    0.025: float(np.sum(weights * anchors[:, 0])),
                    0.16: float(np.sum(weights * anchors[:, 1])),
                    0.84: float(np.sum(weights * anchors[:, 2])),
                    0.975: float(np.sum(weights * anchors[:, 3])),
                }
            else:
                raise ContractError("unknown geometry mixture kind: {}".format(geometry_kind))
            for level, suffix in ((0.025, "q025"), (0.16, "q16"), (0.84, "q84"), (0.975, "q975")):
                row["{}_mix_{}".format(parameter, suffix)] = mixture[level]
            row["{}_covered_68".format(parameter)] = bool(
                mixture[0.16] <= injected <= mixture[0.84]
            )
            row["{}_covered_95".format(parameter)] = bool(
                mixture[0.025] <= injected <= mixture[0.975]
            )
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


def derive_null_threshold(
    recovery: pd.DataFrame,
    rule=None,
    null_class=10,
    branch_kind: str = "max",
):
    """Calibrate the null-transit detection threshold from C11 realizations.

    ``rule`` selects the calibration strategy and is frozen in the protocol:

    - ``in_sample_max``: threshold is the in-sample maximum; false detections
      are zero by construction. PROVISIONAL development default only.
    - ``order_statistic_loo``: each realization is tested against the maximum
      of all *other* realizations, so a false detection is possible.
    - ``held_out_split``: even realization indices calibrate the threshold,
      odd indices are evaluated against it (deterministic split).
    """
    _require_columns(
        recovery,
        ("class_ordinal", "realization_index", "model_id", "delta_map"),
        "recovery records",
    )
    selected = recovery.loc[recovery["class_ordinal"] == null_class]
    if selected.empty or not np.isfinite(selected["delta_map"]).all():
        raise ContractError("C11 null distribution is incomplete or non-finite")
    rows = {}
    for realization_index, group in selected.groupby("realization_index", sort=True):
        weights = (
            group["joint_model_weight"].to_numpy(np.float64)
            if "joint_model_weight" in group.columns
            else None
        )
        rows[int(realization_index)] = combine_branches(
            branch_kind, group["delta_map"].to_numpy(np.float64), weights,
        )
    per_realization = pd.Series(rows, dtype=np.float64).sort_index()
    rule = dict(rule or {"type": "in_sample_max", "status": "PROVISIONAL_DEFAULT"})
    rule_type = rule.get("type")
    if rule_type == "in_sample_max":
        threshold = float(per_realization.max())
        detections = int(np.sum(per_realization.to_numpy(np.float64) > threshold))
    elif rule_type == "order_statistic_loo":
        if len(per_realization) < 2:
            raise ContractError("order_statistic_loo requires at least two null realizations")
        threshold = float(per_realization.max())
        detections = int(sum(
            value > float(per_realization.drop(index=index).max())
            for index, value in per_realization.items()
        ))
    elif rule_type == "held_out_split":
        calibration = per_realization[per_realization.index % 2 == 0]
        evaluation = per_realization[per_realization.index % 2 == 1]
        if calibration.empty or evaluation.empty:
            raise ContractError("held_out_split requires realizations in both splits")
        threshold = float(calibration.max())
        detections = int(np.sum(evaluation.to_numpy(np.float64) > threshold))
    else:
        raise ContractError("unknown null threshold rule: {}".format(rule_type))
    return {
        "delta_detect": threshold,
        "detection_rule": "delta_map > delta_detect",
        "null_realization_count": int(len(per_realization)),
        "false_detection_count": detections,
        "threshold_rule": rule_type,
        "threshold_rule_status": str(rule.get("status", "FROZEN")),
        "branch_statistic": branch_kind,
    }


def evaluate_frozen_gates(
    selection,
    geometry,
    null,
    thresholds: Mapping,
    supplementary=None,
) -> GateResult:
    """Evaluate every declared gate; unevaluable gates never pass silently."""
    supplementary = dict(supplementary or {})
    model = thresholds["model_selection"]
    transit = thresholds["transit"]
    numerical = thresholds.get("numerical", {})
    checks = {}

    def _limit_gate(name, value, limit, mode):
        if limit is None or value is None:
            checks[name] = "NOT_EVALUATED"
        elif mode == "max":
            checks[name] = "PASS" if value <= float(limit) else "FAIL"
        else:
            checks[name] = "PASS" if value >= float(limit) else "FAIL"

    _limit_gate(
        "false_m1_rate",
        selection.get("false_m1_rate_on_white"),
        model.get("false_m1_rate_on_white_max"),
        "max",
    )
    _limit_gate(
        "true_m1_rate",
        selection.get("true_m1_rate_on_nominal"),
        model.get("true_m1_rate_on_m1_minimum"),
        "min",
    )
    checks["null_false_detection"] = (
        "PASS" if null.get("false_detection_count") == 0 else "FAIL"
    )
    for level in ("68", "95"):
        key = "coverage_{}".format(level)
        limit = transit.get("coverage_{}_minimum".format(level))
        values = [
            geometry.get("{}_coverage_{}".format(parameter, level))
            for parameter in GEOMETRY_PARAMETERS
        ]
        if limit is None or any(value is None for value in values):
            checks[key] = "NOT_EVALUATED"
        else:
            checks[key] = (
                "PASS" if all(value >= float(limit) for value in values) else "FAIL"
            )
    attenuation = geometry.get("transit_depth_attenuation_median")
    _limit_gate(
        "transit_attenuation",
        None if attenuation is None else abs(attenuation),
        transit.get("transit_depth_attenuation_max"),
        "max",
    )
    for parameter in GEOMETRY_PARAMETERS:
        tolerance = transit.get(parameter, {}).get("bias_tolerance")
        median = geometry.get("{}_bias_median".format(parameter))
        _limit_gate(
            "bias_median_{}".format(parameter),
            None if median is None else abs(median),
            tolerance,
            "max",
        )
    _limit_gate(
        "optimizer_no_op_rate",
        supplementary.get("optimizer_no_op_rate"),
        numerical.get("optimizer_no_op_max_rate"),
        "max",
    )
    _limit_gate(
        "optimizer_local_mode_rate",
        supplementary.get("optimizer_local_mode_rate"),
        numerical.get("optimizer_local_mode_max_rate"),
        "max",
    )
    _limit_gate(
        "boundary_concentration",
        supplementary.get("boundary_concentration_rate"),
        numerical.get("boundary_concentration_warning_threshold"),
        "max",
    )
    _limit_gate(
        "ingress_egress_rms",
        supplementary.get("ingress_egress_rms_max_mm_s"),
        transit.get("ingress_egress_rms_excess_max_mm_s"),
        "max",
    )
    # The protocol declares no numeric residual threshold; the statistic is
    # reported in supplementary metrics but cannot gate yet.
    checks["residual_max"] = "NOT_EVALUATED"
    # Telemetry-slope recovery is not part of the fitted model; never fake it.
    checks["c13_telemetry_recovery"] = "NOT_EVALUATED"
    c14 = supplementary.get("c14_gap_edge_events_present")
    checks["c14_gap_edge_events_present"] = (
        "NOT_EVALUATED" if c14 is None else "PASS" if c14 else "FAIL"
    )
    completion = supplementary.get("class_completion")
    if not completion:
        checks["class_completeness"] = "NOT_EVALUATED"
    else:
        checks["class_completeness"] = (
            "PASS"
            if all(
                record["completed"] == record["requested"]
                for record in completion.values()
            )
            else "FAIL"
        )
    statuses = set(checks.values())
    if "FAIL" in statuses:
        status = "FAIL"
    elif "NOT_EVALUATED" in statuses:
        status = "INCOMPLETE"
    else:
        status = "PASS"
    return GateResult(
        status=status,
        checks=checks,
        metrics={
            "selection": selection,
            "geometry": geometry,
            "null": null,
            "supplementary": supplementary,
        },
    )


# Backward-compatible alias kept for any external references; prefer evaluate_frozen_gates.
evaluate_development_gates = evaluate_frozen_gates
