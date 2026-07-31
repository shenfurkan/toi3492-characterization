import math

import numpy as np
import pandas as pd
import pytest

from toi3492.stage3.contracts import ContractError
from toi3492.stage3.metrics import (
    branch_mixture_rule,
    combine_branches,
    derive_null_threshold,
    evaluate_frozen_gates,
    mixture_quantiles,
    nominal_geometry_metrics,
    realization_selection_scores,
    selection_metrics,
)


def screening_fixture():
    rows = []
    for class_ordinal, delta in ((0, -1.0), (1, 2.0)):
        for realization in range(2):
            for branch in range(24):
                for held in (37, 63, 64, 90, 99, 100):
                    rows.append({
                        "class_ordinal": class_ordinal,
                        "realization_index": realization,
                        "model_id": "m{:02d}".format(branch),
                        "held_sector": held,
                        "joint_model_weight": 1.0 / 24.0,
                        "k0_score": 0.0,
                        "m1_score": delta / 6.0,
                    })
    return pd.DataFrame(rows)


def recovery_fixture():
    rows = []
    for realization, offset in ((0, 0.001), (1, -0.001)):
        for branch in range(24):
            row = {
                "class_ordinal": 1,
                "realization_index": realization,
                "model_id": "m{:02d}".format(branch),
                "joint_model_weight": 1.0 / 24.0,
                "injected_rp_rs": 0.05,
                "injected_a_rs": 10.0,
                "injected_impact_parameter": 0.5,
                "injected_t14_hours": 5.0,
                "recovered_rp_rs": 0.05 + offset,
                "recovered_a_rs": 10.0,
                "recovered_impact_parameter": 0.5,
                "recovered_t14_hours": 5.0,
            }
            for name, center in (
                ("rp_rs", 0.05), ("a_rs", 10.0),
                ("impact_parameter", 0.5), ("t14_hours", 5.0),
            ):
                row.update({
                    name + "_q025": center - 0.1,
                    name + "_q16": center - 0.05,
                    name + "_q84": center + 0.05,
                    name + "_q975": center + 0.1,
                })
            rows.append(row)
    return pd.DataFrame(rows)


def test_selection_rates_are_class_specific():
    realization = realization_selection_scores(screening_fixture())
    metrics = selection_metrics(realization)
    assert metrics["false_m1_rate_on_white"] == 0.0
    assert metrics["true_m1_rate_on_nominal"] == 1.0


def test_nominal_geometry_metrics_include_bias_standard_deviation():
    _, summary = nominal_geometry_metrics(recovery_fixture())
    assert np.isclose(summary["rp_rs_bias_median"], 0.0, atol=1e-12)
    assert summary["rp_rs_bias_standard_deviation"] > 0.0
    assert summary["rp_rs_coverage_68"] == 1.0


def test_null_threshold_uses_strict_greater_than():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 2.0},
    ])
    result = derive_null_threshold(recovery)
    assert result["delta_detect"] == 2.0
    assert result["false_detection_count"] == 0
    assert result["detection_rule"] == "delta_map > delta_detect"


def test_combine_branches_kernels_match_analytic_values():
    values = np.array([0.0, 1.0], dtype=np.float64)
    weights = np.array([0.5, 0.5], dtype=np.float64)
    assert combine_branches("max", values) == 1.0
    assert np.isclose(combine_branches("weighted_mean", values, weights), 0.5)
    expected = math.log(0.5 + 0.5 * math.e)
    assert np.isclose(combine_branches("log_evidence", values, weights), expected)


def test_combine_branches_rejects_invalid_inputs():
    with pytest.raises(ContractError, match="unknown branch mixture kind"):
        combine_branches("median", np.array([1.0]), np.array([1.0]))
    with pytest.raises(ContractError, match="empty or non-finite"):
        combine_branches("max", np.array([]))
    with pytest.raises(ContractError, match="empty or non-finite"):
        combine_branches("max", np.array([1.0, float("nan")]))
    with pytest.raises(ContractError, match="required for kind"):
        combine_branches("weighted_mean", np.array([1.0, 2.0]))
    with pytest.raises(ContractError, match="not a normalized positive vector"):
        combine_branches("weighted_mean", np.array([1.0, 2.0]), np.array([0.5, 0.4]))
    with pytest.raises(ContractError, match="not a normalized positive vector"):
        combine_branches("weighted_mean", np.array([1.0, 2.0]), np.array([0.0, 1.0]))


def test_mixture_quantiles_are_ordered_and_bounded():
    anchors = np.array([
        [0.03, 0.04, 0.06, 0.09],
        [0.02, 0.05, 0.08, 0.10],
    ], dtype=np.float64)
    weights = np.array([0.5, 0.5], dtype=np.float64)
    result = mixture_quantiles(anchors, weights)
    assert set(result) == {0.025, 0.16, 0.84, 0.975}
    assert result[0.025] < result[0.16] < result[0.84] < result[0.975]
    low = float(anchors[:, 0].min())
    high = float(anchors[:, 3].max())
    assert all(low <= value <= high for value in result.values())


def test_branch_mixture_rule_default_is_provisional():
    result = branch_mixture_rule({})
    assert result["status"] == "PROVISIONAL_DEFAULT"
    assert result["selection"] == "log_evidence"
    assert result["geometry"] == "weighted_quantile"
    assert result["null"] == "max"


def test_branch_mixture_rule_accepts_a_frozen_rule():
    rule = {
        "selection": "log_evidence",
        "geometry": "weighted_mean",
        "null": "log_evidence",
    }
    result = branch_mixture_rule({"branch_mixture_rule": rule})
    assert result["status"] == "FROZEN"
    assert result["geometry"] == "weighted_mean"
    assert result["null"] == "log_evidence"


@pytest.mark.parametrize("rule", [
    {"selection": "weighted_mean", "geometry": "weighted_quantile", "null": "max"},
    {"selection": "log_evidence", "geometry": "weighted_quantile", "null": "bogus"},
    {"selection": "log_evidence", "geometry": "weighted_quantile"},
    {"selection": "log_evidence"},
    "log_evidence",
])
def test_branch_mixture_rule_rejects_invalid_rules(rule):
    with pytest.raises(ContractError, match="branch_mixture_rule"):
        branch_mixture_rule({"branch_mixture_rule": rule})


def test_null_threshold_order_statistic_loo_admits_the_design_false_detection():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 2.0},
        {"class_ordinal": 10, "realization_index": 2, "model_id": "a", "delta_map": 5.0},
    ])
    result = derive_null_threshold(recovery, rule={"type": "order_statistic_loo"})
    assert result["threshold_rule"] == "order_statistic_loo"
    assert result["delta_detect"] == 5.0
    assert result["false_detection_count"] == 1


def test_null_threshold_order_statistic_loo_requires_two_realizations():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
    ])
    with pytest.raises(ContractError, match="at least two null realizations"):
        derive_null_threshold(recovery, rule={"type": "order_statistic_loo"})


def test_null_threshold_held_out_split_calibrates_even_evaluates_odd():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 6.0},
        {"class_ordinal": 10, "realization_index": 2, "model_id": "a", "delta_map": 2.0},
        {"class_ordinal": 10, "realization_index": 3, "model_id": "a", "delta_map": 3.0},
        {"class_ordinal": 10, "realization_index": 4, "model_id": "a", "delta_map": 4.0},
    ])
    result = derive_null_threshold(recovery, rule={"type": "held_out_split"})
    assert result["threshold_rule"] == "held_out_split"
    assert result["delta_detect"] == 4.0
    assert result["false_detection_count"] == 1


def test_null_threshold_held_out_split_requires_both_splits():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
    ])
    with pytest.raises(ContractError, match="both splits"):
        derive_null_threshold(recovery, rule={"type": "held_out_split"})


def test_null_threshold_rejects_an_unknown_rule():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 2.0},
    ])
    with pytest.raises(ContractError, match="unknown null threshold rule"):
        derive_null_threshold(recovery, rule={"type": "bogus"})


def test_null_threshold_reports_independent_evaluation_fields():
    recovery = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 6.0},
        {"class_ordinal": 10, "realization_index": 2, "model_id": "a", "delta_map": 2.0},
        {"class_ordinal": 10, "realization_index": 3, "model_id": "a", "delta_map": 3.0},
        {"class_ordinal": 10, "realization_index": 4, "model_id": "a", "delta_map": 4.0},
    ])
    result = derive_null_threshold(recovery, rule={"type": "held_out_split"})
    assert result["null_realization_count"] == 5
    assert result["evaluation_realization_count"] == 2
    assert result["evaluation_independence"] is True
    assert result["false_detection_count"] == 1
    assert np.isclose(result["false_detection_rate_upper_bound_95"], np.sqrt(0.95))


def test_null_threshold_marks_overlapping_rules_as_not_independent():
    in_sample = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 2.0},
    ])
    default = derive_null_threshold(in_sample)
    assert default["evaluation_realization_count"] == 2
    assert default["evaluation_independence"] is False
    assert default["false_detection_rate_upper_bound_95"] is None

    loo = pd.DataFrame([
        {"class_ordinal": 10, "realization_index": 0, "model_id": "a", "delta_map": 1.0},
        {"class_ordinal": 10, "realization_index": 1, "model_id": "a", "delta_map": 2.0},
        {"class_ordinal": 10, "realization_index": 2, "model_id": "a", "delta_map": 5.0},
    ])
    result = derive_null_threshold(loo, rule={"type": "order_statistic_loo"})
    assert result["evaluation_realization_count"] == 3
    assert result["evaluation_independence"] is False
    assert result["false_detection_rate_upper_bound_95"] is None


def _selection_payload():
    return {
        "false_m1_rate_on_white": 0.0,
        "true_m1_rate_on_nominal": 1.0,
        "white_neither_rate": 0.0,
        "nominal_neither_rate": 0.0,
    }


def _geometry_payload():
    payload = {}
    for parameter in ("rp_rs", "a_rs", "impact_parameter", "t14_hours"):
        payload["{}_bias_median".format(parameter)] = 0.0
        payload["{}_coverage_68".format(parameter)] = 1.0
        payload["{}_coverage_95".format(parameter)] = 1.0
    payload["transit_depth_attenuation_median"] = 0.0
    return payload


def _null_payload():
    return {
        "delta_detect": 1.0,
        "false_detection_count": 0,
        "null_realization_count": 10,
    }


def _thresholds_payload():
    return {
        "model_selection": {
            "false_m1_rate_on_white_max": 0.1,
            "true_m1_rate_on_m1_minimum": 0.7,
            "false_transit_on_null_max": 0.0,
        },
        "transit": {
            "coverage_68_minimum": 0.5,
            "coverage_95_minimum": 0.85,
            "transit_depth_attenuation_max": 0.05,
            "ingress_egress_rms_excess_max_mm_s": 1.0,
            "rp_rs": {"bias_tolerance": 0.001},
            "a_rs": {"bias_tolerance": 0.5},
            "impact_parameter": {"bias_tolerance": 0.05},
            "t14_hours": {"bias_tolerance": 0.05},
        },
        "numerical": {
            "optimizer_no_op_max_rate": 0.0,
            "optimizer_local_mode_max_rate": 0.05,
            "boundary_concentration_warning_threshold": 0.2,
        },
    }


def _supplementary_payload():
    return {
        "optimizer_no_op_rate": 0.0,
        "optimizer_local_mode_rate": 0.0,
        "boundary_concentration_rate": 0.0,
        "ingress_egress_rms_max_mm_s": 0.0,
        "max_abs_standardized_residual": 0.0,
        "c14_gap_edge_events_present": True,
        "class_completion": {
            "C01_white_jitter_transit": {"completed": 30, "requested": 30},
            "C02_m1_160_transit": {"completed": 30, "requested": 30},
        },
    }


def _evaluate(**overrides):
    selection = overrides.pop("selection", _selection_payload())
    geometry = overrides.pop("geometry", _geometry_payload())
    null = overrides.pop("null", _null_payload())
    thresholds = overrides.pop("thresholds", _thresholds_payload())
    supplementary = overrides.pop("supplementary", _supplementary_payload())
    assert not overrides
    return evaluate_frozen_gates(selection, geometry, null, thresholds, supplementary)


def test_gates_report_incomplete_when_all_evaluable_gates_pass():
    gate = _evaluate()
    assert gate.status == "INCOMPLETE"
    assert gate.checks["residual_max"] == "NOT_EVALUATED"
    assert gate.checks["c13_telemetry_recovery"] == "NOT_EVALUATED"
    for name in (
        "false_m1_rate", "true_m1_rate", "null_false_detection",
        "coverage_68", "coverage_95", "transit_attenuation",
        "bias_median_rp_rs", "bias_median_a_rs",
        "bias_median_impact_parameter", "bias_median_t14_hours",
        "optimizer_no_op_rate", "optimizer_local_mode_rate",
        "boundary_concentration", "ingress_egress_rms",
        "c14_gap_edge_events_present", "class_completeness",
    ):
        assert gate.checks[name] == "PASS"


def test_any_failed_gate_forces_overall_fail():
    gate = _evaluate(selection={"false_m1_rate_on_white": 0.5})
    assert gate.checks["false_m1_rate"] == "FAIL"
    assert gate.status == "FAIL"


def test_null_false_detection_gate_honors_the_protocol_tolerance():
    null = {"false_detection_count": 1}
    assert _evaluate(null=null).checks["null_false_detection"] == "FAIL"
    thresholds = _thresholds_payload()
    thresholds["model_selection"]["false_transit_on_null_max"] = 1
    assert _evaluate(null=null, thresholds=thresholds).checks["null_false_detection"] == "PASS"
    missing = {"delta_detect": 1.0, "null_realization_count": 10}
    assert _evaluate(null=missing).checks["null_false_detection"] == "NOT_EVALUATED"
    missing_limit = _thresholds_payload()
    missing_limit["model_selection"].pop("false_transit_on_null_max")
    assert _evaluate(null=null, thresholds=missing_limit).checks["null_false_detection"] == "NOT_EVALUATED"


def test_bias_gates_not_evaluated_when_tolerance_is_missing():
    thresholds = _thresholds_payload()
    for parameter in ("rp_rs", "a_rs", "impact_parameter", "t14_hours"):
        thresholds["transit"][parameter]["bias_tolerance"] = None
    gate = _evaluate(thresholds=thresholds)
    for parameter in ("rp_rs", "a_rs", "impact_parameter", "t14_hours"):
        assert gate.checks["bias_median_{}".format(parameter)] == "NOT_EVALUATED"
    assert gate.status == "INCOMPLETE"


@pytest.mark.parametrize("value, expected", [
    (None, "NOT_EVALUATED"),
    (True, "PASS"),
    (False, "FAIL"),
])
def test_c14_gap_edge_gate_matrix(value, expected):
    gate = _evaluate(supplementary={"c14_gap_edge_events_present": value})
    assert gate.checks["c14_gap_edge_events_present"] == expected


def test_class_completeness_gate_edges():
    incomplete = _supplementary_payload()
    incomplete["class_completion"]["C02_m1_160_transit"]["completed"] = 29
    assert _evaluate(supplementary=incomplete).checks["class_completeness"] == "FAIL"
    missing = _supplementary_payload()
    del missing["class_completion"]
    assert _evaluate(supplementary=missing).checks["class_completeness"] == "NOT_EVALUATED"


def test_c13_telemetry_recovery_gate_is_never_evaluated():
    assert _evaluate().checks["c13_telemetry_recovery"] == "NOT_EVALUATED"
