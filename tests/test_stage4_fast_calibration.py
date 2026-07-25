import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_stage4_fast_calibration as fast


def test_exact_sign_flip_is_exact_for_six_positive_folds():
    assert fast.exact_one_sided_sign_flip_pvalue([1.0] * 6) == pytest.approx(1.0 / 64.0)


def test_ineligible_fold_cannot_select_k3(monkeypatch):
    monkeypatch.setattr(fast, "PROTOCOL", {
        "screening": {"selection_rule": {"minimum_total_delta_elpd": 0.0}},
    })
    result = fast.select_m1([
        {"eligible": False, "delta_elpd": None},
    ] * 6)
    assert result["status"] == "INELIGIBLE"
    assert result["m1_selected"] is False


def test_clopper_pearson_zero_success_has_zero_lower_bound():
    lower, upper = fast._clopper_pearson(0, 30)
    assert lower == 0.0
    assert 0.09 < upper < 0.10


def test_stage4_protocol_selects_only_c01_c02_and_one_branch():
    protocol = json.loads((ROOT / "data" / "stage4_fast_calibration_protocol.json").read_text(
        encoding="utf-8",
    ))
    assert [item["class_index"] for item in protocol["selected_classes"]] == [0, 1]
    assert protocol["fixed_branch"]["model_id"] == "raw_valid::W16_P1"
    assert protocol["reporting"]["required_records"] == 60
