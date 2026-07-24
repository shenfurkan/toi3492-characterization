"""Rapid synthetic data generator for Stage-3 feasibility check."""

import math
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LONG_TABLE = ROOT / "data" / "toi3492_faz4_reductions_120s.csv.gz"
PHASE2 = ROOT / "outputs" / "faz2_transit_inventory.json"

SECTORS = (37, 63, 64, 90, 99, 100)


def _sample_gp_with_rng(gp, rng):
    """Sample celerite's legacy global RNG reproducibly from ``rng``."""
    sample_seed = int(rng.integers(0, np.iinfo(np.uint32).max, dtype=np.uint32))
    state = np.random.get_state()
    try:
        np.random.seed(sample_seed)
        return gp.sample().astype(np.float64)
    finally:
        np.random.set_state(state)


def _truncated_normal(rng, mean, sigma, lower, upper):
    for _ in range(10000):
        value = rng.normal(mean, sigma)
        if lower <= value <= upper:
            return float(value)
    raise RuntimeError("truncated-normal draw did not enter its support")


def load_timestamps():
    import json
    frame = pd.read_csv(LONG_TABLE)
    pdcsap = frame.loc[frame["branch"] == "pdcsap"].copy()
    pdcsap.sort_values(["sector", "cadenceno"], inplace=True)
    pdcsap.reset_index(drop=True, inplace=True)

    phase2 = json.loads(PHASE2.read_text(encoding="utf-8"))
    events = [
        {
            "sector": item["sector"],
            "epoch": item["epoch"],
            "midpoint_btjd": item["predicted_midpoint_btjd"],
        }
        for item in phase2["events"] if item["used"]
    ]
    t14_hours = float(phase2["ephemeris_and_windows"]["t14_hours"])

    return pdcsap, events, t14_hours


def generate_realization(pdcsap, events, t14_hours, seed, noise_family="K0_white",
                          mu_jitter=-1.0, jitter_sigma=0.5,
                          mu_amplitude=-1.0, amp_sigma=0.35,
                          mu_log_tau=math.log(160.0), tau_sigma=0.35,
                          inject_transit=True, rp_rs=0.055, a_rs=10.2,
                          impact_parameter=0.73, return_metadata=False,
                          offset_bounds=(-3.0, 3.0),
                          timescale_bounds=(4.0, 780.0)):
    import math
    rng = np.random.default_rng(seed)
    import batman
    from faz6_noise_core import build_kernel_term

    result = pdcsap.copy()
    result["noise_flux"] = 0.0
    result["transit_flux"] = 1.0
    sector_draws = {}

    if noise_family == "K0_white":
        for sector in SECTORS:
            mask = result["sector"] == sector
            if mask.sum() == 0:
                continue
            jitter_offset = _truncated_normal(
                rng, 0.0, jitter_sigma, offset_bounds[0], offset_bounds[1],
            )
            jitter = math.exp(mu_jitter + jitter_offset)
            sector_draws[int(sector)] = {"jitter_ratio": jitter}
            result.loc[mask, "noise_flux"] = rng.normal(
                0.0, float(result.loc[mask, "flux_err"].median()) * jitter,
                int(mask.sum()),
            )
    else:
        from celerite import GP
        for sector in SECTORS:
            mask = result["sector"] == sector
            if mask.sum() < 3:
                continue
            s_jitter = mu_jitter + _truncated_normal(
                rng, 0.0, jitter_sigma, offset_bounds[0], offset_bounds[1],
            )
            s_amp = mu_amplitude + _truncated_normal(
                rng, 0.0, amp_sigma, offset_bounds[0], offset_bounds[1],
            )
            tau_offset_lo = max(offset_bounds[0], math.log(timescale_bounds[0]) - mu_log_tau)
            tau_offset_hi = min(offset_bounds[1], math.log(timescale_bounds[1]) - mu_log_tau)
            s_tau = mu_log_tau + _truncated_normal(
                rng, 0.0, tau_sigma, tau_offset_lo, tau_offset_hi,
            )

            times = result.loc[mask, "time_btjd"].to_numpy(float)
            errs = result.loc[mask, "flux_err"].to_numpy(float)
            jitter = result.loc[mask, "flux_err"].median() * math.exp(s_jitter)
            amp = result.loc[mask, "flux_err"].median() * math.exp(s_amp)
            tau_minutes = math.exp(s_tau)
            sector_draws[int(sector)] = {
                "jitter_ratio": math.exp(s_jitter),
                "amplitude_ratio": math.exp(s_amp),
                "timescale_minutes": tau_minutes,
            }

            if noise_family == "M1_matern32":
                kernel_id = "K2_matern32"
            elif noise_family == "OU":
                kernel_id = "K1_ou"
            elif noise_family == "SHO":
                kernel_id = "K3_sho"
            else:
                raise ValueError(f"Unknown: {noise_family}")

            term = build_kernel_term(kernel_id, amp, tau_minutes)
            gp = GP(term)
            gp.compute(times, yerr=1e-12, check_sorted=True)
            gp_sample = _sample_gp_with_rng(gp, rng)
            extra_jitter = rng.normal(0.0, jitter, len(times))
            result.loc[mask, "noise_flux"] = gp_sample + extra_jitter

    if inject_transit:
        params = batman.TransitParams()
        params.t0 = 0.0
        params.per = 9.2224171
        params.rp = float(rp_rs)
        params.a = float(a_rs)
        inc = math.degrees(math.acos(float(impact_parameter) / float(a_rs)))
        params.inc = inc
        params.ecc = 0.0
        params.w = 90.0
        params.u = [0.3546454910932521, 0.15379449038160178]
        params.limb_dark = "quadratic"

        for event in events:
            mask = result["sector"] == event["sector"]
            if mask.sum() == 0:
                continue
            times = result.loc[mask, "time_btjd"].to_numpy(float)
            x_days = times - event["midpoint_btjd"]
            model = batman.TransitModel(
                params, x_days,
                supersample_factor=7,
                exp_time=120.0 / 86400.0,
            )
            transit_flux = model.light_curve(params).astype(np.float64)
            result.loc[mask, "transit_flux"] *= transit_flux

    result["measurement_noise"] = rng.normal(
        0.0, result["flux_err"].to_numpy(float),
        len(result),
    )
    result["true_flux"] = result["transit_flux"] - 1.0 + result["noise_flux"]
    result["flux"] = (result["transit_flux"] + result["noise_flux"] +
                      result["measurement_noise"])
    if not return_metadata:
        return result
    return result, {
        "seed": int(seed),
        "noise_family": noise_family,
        "inject_transit": bool(inject_transit),
        "geometry": {
            "rp_rs": float(rp_rs),
            "a_rs": float(a_rs),
            "impact_parameter": float(impact_parameter),
        },
        "sector_draws": sector_draws,
    }
