import numpy as np

from science import (
    equilibrium_temperature_k,
    eccentric_cosi,
    incident_flux_earth,
    kepler_a_au,
    kepler_a_rs,
    luminosity_solar,
    photometric_density_solar,
    transit_duration_hours,
)
from transit_fit_robust import ar1_transform, q_to_u, u_to_q


PERIOD = 9.2224171


def test_keplerian_derived_quantities():
    a_rs = kepler_a_rs(PERIOD, 1.25, 2.59262)
    a_au = kepler_a_au(PERIOD, 1.25)
    luminosity = luminosity_solar(2.59262, 6332.0)
    assert np.isclose(a_rs, 7.689511792508893)
    assert np.isclose(a_au, 0.09271168650681884)
    assert np.isclose(incident_flux_earth(luminosity, a_au), 1132.5753528844589)
    assert np.isclose(
        equilibrium_temperature_k(6332.0, 2.59262, a_au),
        1614.64303938146,
    )


def test_circular_duration_and_density():
    duration = transit_duration_hours(PERIOD, 0.05472, 10.60, 0.705)
    density = photometric_density_solar(PERIOD, 10.60)
    assert np.isclose(duration, 5.231, atol=0.01)
    assert np.isclose(density, 0.1879, atol=0.001)


def test_eccentric_geometry_reduces_to_circular():
    circular = eccentric_cosi(9.0, 0.5, 0.0, 237.0)
    assert np.isclose(circular, 0.5 / 9.0)
    assert np.isclose(
        transit_duration_hours(PERIOD, 0.056, 9.0, 0.5, 0.0, 237.0),
        transit_duration_hours(PERIOD, 0.056, 9.0, 0.5),
    )


def test_eccentric_impact_parameter_mapping():
    expected = 0.5 / 9.0 * (1.0 + 0.3) / (1.0 - 0.3**2)
    assert np.isclose(eccentric_cosi(9.0, 0.5, 0.3, 90.0), expected)


def test_limb_darkening_parameterization_round_trip():
    u1, u2 = 0.39, 0.15
    q1, q2 = u_to_q(u1, u2)
    recovered = q_to_u(q1, q2)
    assert np.allclose(recovered, [u1, u2])
    assert 0.0 < q1 < 1.0
    assert 0.0 < q2 < 1.0


def test_ar1_transform_resets_across_gaps():
    values = np.array([1.0, 2.0, 10.0, 12.0])
    transformed = ar1_transform(values, np.array([True, False, True]), 0.5)
    scale = np.sqrt(1.0 - 0.5**2)
    assert np.isclose(transformed[1], (2.0 - 0.5) / scale)
    assert transformed[2] == 10.0
    assert np.isclose(transformed[3], (12.0 - 5.0) / scale)
