import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_wp09a_formal_statistics_and_descriptors():
    result = load_json("outputs/wp09a_formal_sector_audit.json")
    descriptors = pd.read_csv(ROOT / "outputs/wp09a_sector_descriptors.csv")
    assert result["status"] == "PASS"
    assert result["adoption"] == "FORMAL_HETEROGENEITY_ONLY"
    assert result["statistics"]["chi_square"] == pytest.approx(29.849938162158445, abs=1e-12)
    assert result["statistics"]["degrees_of_freedom"] == 5
    assert result["statistics"]["p_value"] == pytest.approx(1.578626941110096e-5, rel=1e-12)
    assert len(descriptors) == 6
    assert descriptors.set_index("sector")[["camera", "ccd"]].to_dict("index") == {
        37: {"camera": 2, "ccd": 1}, 63: {"camera": 2, "ccd": 2},
        64: {"camera": 2, "ccd": 1}, 90: {"camera": 2, "ccd": 2},
        99: {"camera": 3, "ccd": 3}, 100: {"camera": 2, "ccd": 1},
    }
    assert descriptors["crowdsap"].between(0.0, 1.0).all()
    assert descriptors["optimal_aperture_pixel_count"].gt(0).all()


def test_wp09a_verifies_and_is_no_clobber():
    verify = subprocess.run(
        [sys.executable, "-B", "scripts/run_wp09a_formal_sector_audit.py", "--verify-only"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert verify.returncode == 0, verify.stderr
    rerun = subprocess.run(
        [sys.executable, "-B", "scripts/run_wp09a_formal_sector_audit.py"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert rerun.returncode != 0
    assert "no-clobber" in rerun.stderr
