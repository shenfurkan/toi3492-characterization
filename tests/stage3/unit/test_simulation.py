import numpy as np
import pandas as pd

from toi3492.stage3.inputs import EventSpec
from toi3492.stage3.simulation import _shared_baseline, _transit_flux


def architecture():
    return {
        "candidate": {
            "transit_model": {
                "t0_btjd_fixed": 100.0,
                "period_days_fixed": 9.0,
                "eccentricity_fixed": 0.0,
                "limb_darkening_quadratic_fixed": [0.35, 0.15],
                "supersample_factor": 7,
                "exposure_seconds": 120.0,
            }
        }
    }


def test_transit_is_generated_once_per_sector_not_once_per_event():
    times = np.linspace(99.7, 109.3, 1000)
    frame = pd.DataFrame({
        "time_btjd": np.concatenate((times, times)),
        "sector": np.concatenate((np.full(len(times), 37), np.full(len(times), 63))),
    })
    geometry = {"rp_rs": 0.06, "a_rs": 10.0, "impact_parameter": 0.5}
    flux = _transit_flux(frame, architecture(), geometry)
    sector_37 = flux[frame["sector"].to_numpy() == 37]
    sector_63 = flux[frame["sector"].to_numpy() == 63]
    np.testing.assert_array_equal(sector_37, sector_63)
    assert 0.99 < sector_37.min() < 1.0


def test_shared_baseline_records_events_without_cadences():
    frame = pd.DataFrame({
        "time_btjd": [100.0, 100.1],
        "sector": [37, 37],
    })
    events = (
        EventSpec("S037-E000", 37, 0, 100.0, True),
        EventSpec("S099-E189", 99, 189, 200.0, False),
    )
    baseline, draws = _shared_baseline(frame, events, 123)
    assert set(draws) == {"S037-E000", "S099-E189"}
    assert all(len(values) == 3 for values in draws.values())
    assert np.any(baseline != 0.0)
