import numpy as np
import pandas as pd

from toi3492.stage3.metrics import (
    derive_null_threshold,
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
