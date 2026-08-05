import json

import numpy as np
import pytest

from exonym.vetting.centroid import centroid_gate, centroid_offset_z
from exonym.vetting.oddeven import odd_even_gate, odd_even_z
from exonym.vetting.tricera_parse import fpp_gate, load_fpp_report


def test_centroid_offset_z_uses_cos_dec():
    z = centroid_offset_z(ra_offset_arcsec=0.0, dec_offset_arcsec=3.0, dec_deg=0.0, sigma_arcsec=1.0)
    assert z == pytest.approx(3.0)
    z_on_target = centroid_offset_z(0.5, 0.5, 0.0, 1.0)
    assert z_on_target < 3.0


def test_centroid_gate_threshold():
    passed, z = centroid_gate(0.1, 0.1, 0.0, 1.0)
    assert passed and z < 3.0
    failed, z = centroid_gate(3.0, 0.0, 0.0, 1.0)
    assert not failed and z >= 3.0


def test_centroid_requires_positive_sigma():
    with pytest.raises(ValueError):
        centroid_offset_z(0.0, 0.0, 0.0, 0.0)


def test_odd_even_z():
    z = odd_even_z(100.0, 10.0, 90.0, 10.0)
    assert z == pytest.approx(0.7071, abs=1e-3)
    assert odd_even_gate(100.0, 10.0, 90.0, 10.0)[0] is True
    assert odd_even_gate(100.0, 5.0, 70.0, 5.0)[0] is False


def test_fpp_gate_dict_and_value():
    report = {"fpp": 0.005, "nfpp": 0.0}
    passed, fpp = fpp_gate(report)
    assert passed and fpp == pytest.approx(0.005)
    assert fpp_gate(0.02)[0] is False


def test_fpp_report_probes_common_keys(tmp_path):
    path = tmp_path / "triceratops.json"
    path.write_text(json.dumps({"FPP_specific": 0.008}), encoding="utf-8")
    report = load_fpp_report(path)
    assert fpp_gate(report)[0] is True


def test_fpp_missing_value_raises(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"note": "no fpp"}), encoding="utf-8")
    with pytest.raises(ValueError, match="no FPP"):
        fpp_gate(load_fpp_report(path))


# ---------------------------------------------------------------------------
# Scientific analysis modules: asteroseismology
# ---------------------------------------------------------------------------


def test_asteroseismology_recovers_injected_comb():
    from exonym.asteroseismology import (
        _synthetic_oscillation_table,
        estimate_oscillation_envelope,
    )

    table = _synthetic_oscillation_table()
    result = estimate_oscillation_envelope(table["time"], table["flux"], 100.0, 1600.0)
    assert result["numax_candidate_uhz"] == pytest.approx(250.0, abs=15.0)
    assert result["dnu_candidate_uhz"] == pytest.approx(40.0, abs=5.0)
    assert result["dnu_correlation"] > 0.5


def test_seismic_scaling_relations():
    from exonym.asteroseismology import seismic_mass_radius

    solar = seismic_mass_radius(3090.0, 135.1, 5772.0)
    assert solar["mass_solar"] == pytest.approx(1.0, abs=0.01)
    assert solar["radius_solar"] == pytest.approx(1.0, abs=0.01)

    subgiant = seismic_mass_radius(250.0, 40.0, 5772.0)
    expected_radius = (250.0 / 3090.0) / (40.0 / 135.1) ** 2
    assert subgiant["radius_solar"] == pytest.approx(expected_radius, rel=0.01)
    assert subgiant["mass_solar"] == pytest.approx(expected_radius**3 * (40.0 / 135.1) ** 2, rel=0.02)


def test_seismic_mass_radius_falls_back_to_priors():
    from exonym.asteroseismology import seismic_mass_radius

    result = seismic_mass_radius(0.0, None, 5772.0, mass_prior_solar=1.2, radius_prior_solar=1.4)
    assert result["mass_solar"] == pytest.approx(1.2)
    assert result["radius_solar"] == pytest.approx(1.4)
    assert "priors" in result["method"]


# ---------------------------------------------------------------------------
# Scientific analysis modules: PRF localization
# ---------------------------------------------------------------------------


def test_prf_localization_recovers_deficit_offset():
    from exonym.localization import build_depth_map, localize_depth_deficit

    shape = (11, 11)
    target_x, target_y = 5.0, 5.0
    deficit_x, deficit_y = target_x + 0.3, target_y - 0.2
    sigma = 0.85
    yy, xx = np.indices(shape, dtype=float)
    out_image = 2000.0 + 20.0 * np.exp(
        -((xx - target_x) ** 2 + (yy - target_y) ** 2) / (2.0 * sigma**2)
    )
    deficit = 14.0 * np.exp(
        -((xx - deficit_x) ** 2 + (yy - deficit_y) ** 2) / (2.0 * sigma**2)
    )
    depth_map, valid = build_depth_map(out_image - deficit, out_image)
    aperture = np.zeros(shape, dtype=bool)
    aperture[2:-2, 2:-2] = True
    offset = localize_depth_deficit(depth_map, aperture, target_x, target_y)
    assert offset["ra_offset_arcsec"] == pytest.approx(6.3, abs=2.5)
    assert offset["dec_offset_arcsec"] == pytest.approx(-4.2, abs=2.5)
    assert offset["offset_arcsec"] > 2.0
    assert offset["n_depth_pixels"] >= 3


def test_prf_nnls_assigns_depth_to_target():
    from exonym.localization import fit_depth_map_prf, gaussian_prf_kernel

    shape = (11, 11)
    yy, xx = np.indices(shape, dtype=float)
    kernel = gaussian_prf_kernel(xx, yy, 5.0, 5.0)
    depth_map = 0.01 * kernel
    pixel_mask = np.ones(shape, dtype=bool)
    amplitudes, residual, n_pixels = fit_depth_map_prf(
        depth_map, pixel_mask, [5.0, 8.0], [5.0, 5.0]
    )
    assert n_pixels > 5
    assert amplitudes[0] > 10.0 * amplitudes[1]
    assert residual is not None


# ---------------------------------------------------------------------------
# Scientific analysis modules: SED
# ---------------------------------------------------------------------------


def test_sed_recovers_synthetic_photometry():
    from exonym.sed import _fit_blackbody, _synthetic_photometry

    stellar = {
        "teff_k": 5772.0,
        "logg_cgs": 4.438,
        "feh": 0.0,
        "mass_solar": 1.0,
        "radius_solar": 1.0,
        "parallax_mas": 10.0,
    }
    observations = _synthetic_photometry(stellar)
    result = _fit_blackbody(observations, stellar, n_walkers=24, burn_in=150, production=250)
    posterior = result["posterior"]
    assert posterior["teff_k"]["median"] == pytest.approx(5772.0, abs=250.0)
    assert posterior["radius_solar"]["median"] == pytest.approx(1.0, abs=0.35)
    assert posterior["logg_cgs"]["median"] == pytest.approx(4.438, abs=0.3)


def test_sed_percentile_summary():
    from exonym.sed import percentile_summary

    samples = np.linspace(0.0, 10.0, 1001)
    summary = percentile_summary(samples)
    assert summary["median"] == pytest.approx(5.0)
    assert summary["p16"] < summary["median"] < summary["p84"]
    assert summary["plus"] == pytest.approx(summary["p84"] - summary["median"])


# ---------------------------------------------------------------------------
# Scientific analysis modules: transit fit
# ---------------------------------------------------------------------------


def test_transit_fit_recovers_synthetic_parameters(tmp_path):
    from exonym.transit_fit import run_mcmc_transit_fit
    from exonym.workspace import create_candidate

    workspace = create_candidate(tmp_path, "fit-test")
    output = run_mcmc_transit_fit(
        workspace, n_samples=160, n_walkers=16, burn_in=40
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    posterior = payload["posterior"]
    injected_rp = 1200.0**0.5 / 1000.0
    assert posterior["rp_rs"]["median"] == pytest.approx(injected_rp, abs=0.004)
    assert posterior["impact_parameter"]["median"] == pytest.approx(0.3, abs=0.1)
    assert posterior["rho_star_solar"]["median"] == pytest.approx(1.0, rel=0.3)
    assert posterior["q1"]["median"] == pytest.approx(0.35, abs=0.05)
    assert posterior["q2"]["median"] == pytest.approx(0.3, abs=0.05)
    assert payload["source"] == "synthetic-demo"


def test_transit_fit_eccentric_mode_runs(tmp_path):
    from exonym.transit_fit import run_mcmc_transit_fit
    from exonym.workspace import create_candidate

    workspace = create_candidate(tmp_path, "fit-ecc-test")
    output = run_mcmc_transit_fit(
        workspace, n_samples=120, eccentric=True, n_walkers=20, burn_in=30
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "eccentricity" in payload["posterior"]
    assert "omega_deg" in payload["posterior"]
    assert payload["posterior"]["eccentricity"]["median"] < 0.3


def test_stellar_density_a_rs_monotonic():
    from exonym.transit_fit import stellar_density_a_rs

    assert stellar_density_a_rs(1.0, 3.5) > stellar_density_a_rs(1.0, 1.0)
    assert stellar_density_a_rs(4.0, 3.5) > stellar_density_a_rs(1.0, 3.5)
    with pytest.raises(ValueError):
        stellar_density_a_rs(0.0, 3.5)


# ---------------------------------------------------------------------------
# Scientific analysis modules: phase curve
# ---------------------------------------------------------------------------


def test_phase_curve_recovers_injected_reflection():
    from exonym.phasecurve import _synthetic_phase_curve_table, fit_phase_curve_components

    table = _synthetic_phase_curve_table()
    ephemeris = {
        "period_days": table.pop("_period_days"),
        "epoch_btjd": table.pop("_epoch_btjd"),
        "duration_days": table.pop("_duration_days"),
    }
    result = fit_phase_curve_components(
        table["time"], table["flux"], table["flux_err"], table["sector"], ephemeris
    )
    reflection = result["components"]["reflection_semiamplitude"]
    assert reflection["value_ppm"] == pytest.approx(150.0, abs=50.0)
    assert result["maximum_absolute_significance_sigma"] >= 2.0


def test_phase_curve_cluster_covariance_shapes():
    from exonym.phasecurve import cluster_sandwich_covariance

    rng = np.random.default_rng(seed=3)
    design = rng.normal(size=(200, 4))
    residual = rng.normal(size=200)
    sigma = np.full(200, 0.001)
    cluster = np.repeat(np.arange(20), 10)
    covariance, n_clusters = cluster_sandwich_covariance(design, residual, sigma, cluster)
    assert covariance.shape == (4, 4)
    assert n_clusters == 20


# ---------------------------------------------------------------------------
# Scientific analysis modules: TTV
# ---------------------------------------------------------------------------


def test_ttv_linear_ephemeris_has_small_residuals():
    from exonym.search import calculate_ttv_super_period
    from exonym.transit_fit import stellar_density_a_rs
    from exonym.ttv import _synthetic_timing_table, transit_timing_analysis

    table = _synthetic_timing_table(ttv_amplitude_minutes=0.0)
    ephemeris = {
        "period_days": table.pop("_period_days"),
        "epoch_btjd": table.pop("_epoch_btjd"),
        "duration_days": table.pop("_duration_days"),
        "depth_ppm": table.pop("_depth_ppm"),
    }
    a_rs = stellar_density_a_rs(1.0, ephemeris["period_days"])
    analysis = transit_timing_analysis(
        table["time"], table["flux"], table["flux_err"], ephemeris, a_rs
    )
    assert analysis["n_transits_fit"] >= 5
    assert analysis["oc_rms_minutes"] < 2.0

    assert calculate_ttv_super_period(3.5, 5.0, j_resonance=2) == pytest.approx(8.75, rel=0.01)


def test_ttv_injected_signal_is_detected():
    from exonym.transit_fit import stellar_density_a_rs
    from exonym.ttv import _synthetic_timing_table, transit_timing_analysis

    table = _synthetic_timing_table(ttv_amplitude_minutes=20.0)
    ephemeris = {
        "period_days": table.pop("_period_days"),
        "epoch_btjd": table.pop("_epoch_btjd"),
        "duration_days": table.pop("_duration_days"),
        "depth_ppm": table.pop("_depth_ppm"),
    }
    a_rs = stellar_density_a_rs(1.0, ephemeris["period_days"])
    analysis = transit_timing_analysis(
        table["time"], table["flux"], table["flux_err"], ephemeris, a_rs
    )
    assert analysis["oc_rms_minutes"] > 5.0


# ---------------------------------------------------------------------------
# Scientific analysis modules: stellar activity
# ---------------------------------------------------------------------------


def test_activity_recovers_rotation_period():
    from exonym.activity import (
        _synthetic_rotation_table,
        gls_periodogram,
        sinusoid_amplitude_ppm,
        weighted_period_summary,
    )

    table = _synthetic_rotation_table()
    periods, powers, fap = gls_periodogram(table["time"], table["flux"])
    best_period = float(periods[int(np.argmax(powers))])
    assert best_period == pytest.approx(5.0, abs=0.2)
    assert fap < 0.01

    amplitude = sinusoid_amplitude_ppm(table["time"], table["flux"], best_period)
    assert amplitude == pytest.approx(400.0, abs=100.0)

    summary = weighted_period_summary([5.0, 5.1], [1.0, 1.0])
    assert summary["weighted_mean_period_days"] == pytest.approx(5.05)


# ---------------------------------------------------------------------------
# Scientific analysis modules: dilution
# ---------------------------------------------------------------------------


def test_dilution_contamination_factor_sums_neighbors():
    from exonym.dilution import gaia_contamination_factor

    rows = [
        {"separation_arcsec": 10.0, "flux_ratio": 0.02, "is_target": False},
        {"separation_arcsec": 100.0, "flux_ratio": 0.5, "is_target": False},
        {"separation_arcsec": 5.0, "flux_ratio": None, "is_target": False, "g_mag": 14.0},
    ]
    result = gaia_contamination_factor(rows, search_radius_arcsec=60.0, target_g_mag=10.0)
    expected = 0.02 + 10.0 ** (-0.4 * (14.0 - 10.0))
    assert result["contamination_factor"] == pytest.approx(expected, abs=1e-6)
    assert result["n_neighbors_included"] == 2


def test_dilution_aperture_depth_decreases_with_size():
    from exonym.dilution import (
        _extract_cube_light_curves,
        _synthetic_tpf_cube,
        aperture_depth_ppm,
    )

    cube = _synthetic_tpf_cube()
    ephemeris = {
        "period_days": cube.pop("_period_days"),
        "epoch_btjd": cube.pop("_epoch_btjd"),
        "duration_days": cube.pop("_duration_days"),
    }
    extracted = _extract_cube_light_curves(cube, ephemeris)
    small = aperture_depth_ppm(extracted["time"], extracted["light_curves"]["box_3x3"], ephemeris)
    large = aperture_depth_ppm(extracted["time"], extracted["light_curves"]["box_7x7"], ephemeris)
    assert small["depth_ppm"] > large["depth_ppm"]
    assert small["n_in_transit"] > 100
