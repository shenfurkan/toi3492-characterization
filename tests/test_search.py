"""Tests for the target-neutral BLS transit search engine."""

import json

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


def test_find_transits_resolves_double_period_alias():
    rng = np.random.default_rng(11)
    period = 4.2608
    epoch = 100.0
    duration_days = 6.45 / 24.0

    segments = []
    for start in (0.0, 165.0, 357.0):
        segments.append(np.arange(start, start + 26.0, 120.0 / 86400.0))
    time = np.concatenate(segments)

    flux = np.ones_like(time)
    ph = ((time - epoch + 0.5 * period) % period) / period - 0.5
    flux[np.abs(ph) < duration_days / period / 2.0] -= 0.003857
    flux += rng.normal(0.0, 0.0035, time.size)

    from exonym.search import _median_bin

    time_b, flux_b = _median_bin(time, flux, n_bins=3500)

    res = find_transits(time_b, flux_b, period_min=2.0, period_max=12.0)
    assert abs(res.best_period - period) < 0.02, "fundamental period lost to 2x alias"
    assert res.snr > 10.0
    assert res.best_depth_ppm > 2000.0


def test_find_transits_invalid():
    with pytest.raises(ValueError):
        find_transits([1.0, 2.0], [1.0, 1.0])

    with pytest.raises(ValueError):
        find_transits(np.linspace(0, 10, 100), np.ones(100), period_min=-1.0)


def test_run_bls_on_candidate_synthetic_fallback(tmp_path):
    workspace = create_candidate(tmp_path, "candidate-test-bls")
    out = run_bls_on_candidate(workspace)
    assert out.is_file()
    assert out.name == "bls_search_results.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source"] == "synthetic-demo"
    assert payload["n_points"] > 0


def test_run_bls_on_candidate_with_real_data(tmp_path):
    import lightkurve as lk

    workspace = create_candidate(tmp_path, "candidate-test-data")
    raw = workspace.path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    time = np.linspace(2459000.0, 2459030.0, 600)
    period = 4.2
    epoch = 2459005.0
    ph = phase_hours(time, period, epoch)
    flux = 1.0 - 0.005 * (np.abs(ph) < 1.5).astype(float)
    meta = {
        "MISSION": "TESS",
        "TELESCOP": "TESS",
        "TIMEDEL": 120.0 / 86400.0,
        "TIMEUNIT": "BJD",
        "BJDREFI": 2457000,
        "BJDREFF": 0.0,
    }
    lk.LightCurve(time=time, flux=flux, meta=meta).to_fits(
        path=raw / "test_lc.fits", overwrite=True
    )

    out = run_bls_on_candidate(workspace)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source"] == "candidate-data"
    assert payload["n_points"] == 600
    assert payload["best_period"] > 0


def test_quality_flag_masking_excludes_bad_cadences(tmp_path):
    """Quality-flagged cadences must be removed before BLS.

    Injects a cluster of flagged cadences that carry a strong artificial dip
    (simulating a momentum dump plus scattered-light artefact). After the
    quality mask the dip is absent and BLS must NOT recover a period near
    the spacing of the bad-cadence cluster (which would be ~1 day here).
    """
    import lightkurve as lk
    from astropy.io import fits as fitsio
    from astropy.table import Table

    workspace = create_candidate(tmp_path, "quality-mask-test")
    raw = workspace.path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    n = 800
    time = np.linspace(2459000.0, 2459030.0, n)
    flux = 1.0 + rng.normal(0.0, 0.0008, n)
    quality = np.zeros(n, dtype=np.int32)

    # Inject 16 consecutive cadences with quality flag=2048 (scattered light)
    # and a strong artificial dip — these must be excluded by the quality mask.
    bad_start = 300
    quality[bad_start : bad_start + 16] = 2048
    flux[bad_start : bad_start + 16] = 0.98  # 2% dip — far deeper than any real planet

    table = Table()
    table["TIME"] = time
    table["FLUX"] = flux
    table["FLUX_ERR"] = np.full(n, 0.001)
    table["QUALITY"] = quality
    ext = fitsio.BinTableHDU(table)
    ext.header["SECTOR"] = 30
    ext.header["TIMEDEL"] = 120.0 / 86400.0
    ext.header["BJDREFI"] = 2457000
    ext.header["BJDREFF"] = 0.0
    primary = fitsio.PrimaryHDU()
    primary.header["MISSION"] = "TESS"
    primary.header["TELESCOP"] = "TESS"
    fitsio.HDUList([primary, ext]).writeto(raw / "s0030_lc.fits", overwrite=True)

    out = run_bls_on_candidate(workspace, period_min=0.5, period_max=10.0)
    payload = json.loads(out.read_text(encoding="utf-8"))
    # The loader uses quality==0 masking; the dip should be absent so BLS
    # should not lock onto the ~1-day spurious period of the bad cluster.
    # We assert SNR is low, meaning no strong periodic signal was detected.
    assert payload["snr"] < 50.0, (
        "BLS SNR is suspiciously high — quality masking may not have removed the bad cadences. "
        f"Recovered period={payload['best_period']:.3f} d, SNR={payload['snr']:.1f}"
    )
