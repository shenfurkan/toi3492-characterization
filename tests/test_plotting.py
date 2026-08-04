"""Tests for headless diagnostic figure generation."""

import numpy as np

from exonym.plotting import generate_candidate_plots, plot_centroid_offsets, plot_phase_folded_lc
from exonym.workspace import create_candidate


def test_plot_phase_folded_lc(tmp_path):
    time = np.linspace(0, 10, 200)
    flux = np.ones_like(time)
    out = tmp_path / "test_lc.png"
    result = plot_phase_folded_lc(time, flux, period_days=2.5, epoch_btjd=0.5, output_path=out)
    assert result.is_file()
    assert result.stat().st_size > 0


def test_plot_centroid_offsets(tmp_path):
    out = tmp_path / "test_centroid.png"
    result = plot_centroid_offsets([0.1, -0.1], [0.2, -0.05], sigma_arcsec=0.1, output_path=out)
    assert result.is_file()
    assert result.stat().st_size > 0


def test_generate_candidate_plots(tmp_path):
    workspace = create_candidate(tmp_path, "candidate-test-plot")
    plots = generate_candidate_plots(workspace)
    assert len(plots) == 2
    for path in plots:
        assert path.is_file()
