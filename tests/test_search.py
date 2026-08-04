"""Tests for the target-neutral BLS transit search engine."""

import numpy as np
import pytest

from exonym.lightcurve import phase_hours
from exonym.search import find_transits, run_bls_on_candidate
from exonym.workspace import create_candidate


def test_find_transits_synthetic():
    time = np.linspace(0, 20, 2000)
    period = 4.0
    epoch = 1.0
    ph = phase_hours(time, period, epoch)
    flux = np.ones_like(time)
    flux[np.abs(ph) < 1.5] = 0.995

    res = find_transits(time, flux, period_min=1.0, period_max=10.0, duration_hours=3.0)
    assert res.best_period > 0
    assert res.snr > 0


def test_find_transits_invalid():
    with pytest.raises(ValueError):
        find_transits([1.0, 2.0], [1.0, 1.0])

    with pytest.raises(ValueError):
        find_transits(np.linspace(0, 10, 100), np.ones(100), period_min=-1.0)


def test_run_bls_on_candidate(tmp_path):
    workspace = create_candidate(tmp_path, "candidate-test-bls")
    out = run_bls_on_candidate(workspace)
    assert out.is_file()
    assert out.name == "bls_search_results.json"
