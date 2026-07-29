"""Deterministic one-latent-per-realization synthetic data generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from .contracts import ContractError, SECTORS
from .inputs import EventSpec, Stage3Inputs


BASELINE_SIGMA = 0.01
BASELINE_HALF_WIDTH_DAYS = 32.0 / 48.0


@dataclass(frozen=True)
class LatentRealization:
    frame: pd.DataFrame
    metadata: Mapping


def _rng(seed: int, stream: int):
    return np.random.default_rng(np.random.SeedSequence([int(seed), int(stream)]))


def _truncated_normal(rng, mean, sigma, lower, upper):
    if sigma == 0.0:
        if not lower <= mean <= upper:
            raise ContractError("degenerate normal lies outside its support")
        return float(mean)
    for _ in range(10000):
        value = float(rng.normal(mean, sigma))
        if lower <= value <= upper:
            return value
    raise ContractError("truncated-normal draw did not enter its support")


def _sample_gp(gp, rng):
    """Use celerite's global sampler reproducibly within one worker process."""
    sample_seed = int(rng.integers(0, np.iinfo(np.uint32).max, dtype=np.uint32))
    state = np.random.get_state()
    try:
        np.random.seed(sample_seed)
        return gp.sample().astype(np.float64)
    finally:
        np.random.set_state(state)


def _draw_geometry(class_spec: Mapping, seed: int):
    if not class_spec["inject_transit"]:
        return None
    geometry = class_spec["geometry_injection"]
    random = _rng(seed, 1)
    result = {
        name: float(random.uniform(*geometry[name]["bounds"]))
        for name in ("rp_rs", "a_rs", "impact_parameter")
    }
    if result["impact_parameter"] >= 1.0 + result["rp_rs"]:
        raise ContractError("drawn impact parameter violates the transit support")
    if result["impact_parameter"] >= result["a_rs"]:
        raise ContractError("drawn impact parameter exceeds a/Rstar")
    return result


def _noise_parameters(class_spec: Mapping):
    parameters = class_spec["noise_parameters"]
    return {
        "family": class_spec["noise_family"],
        "mu_jitter": float(parameters["mu_jitter_ratio"]),
        "jitter_sigma": float(parameters["jitter_offset_sigma"]),
        "mu_amplitude": float(parameters["mu_amplitude_ratio"] or 0.0),
        "amplitude_sigma": float(parameters["amplitude_offset_sigma"] or 0.0),
        "mu_log_timescale": float(parameters["mu_log_timescale"] or math.log(160.0)),
        "timescale_sigma": float(parameters["timescale_offset_sigma"] or 0.0),
        "timescale_bounds": (
            float(parameters.get("timescale_lower_minutes") or 4.0),
            float(parameters.get("timescale_upper_minutes") or 780.0),
        ),
    }


def _draw_noise(frame: pd.DataFrame, class_spec: Mapping, seed: int):
    from celerite import GP
    from faz6_noise_core import build_kernel_term

    parameters = _noise_parameters(class_spec)
    random = _rng(seed, 100)
    noise = np.zeros(len(frame), dtype=np.float64)
    sector_draws = {}
    sectors = frame["sector"].to_numpy(np.int64)
    for sector in SECTORS:
        selected = sectors == sector
        if not np.any(selected):
            continue
        errors = frame.loc[selected, "flux_err"].to_numpy(np.float64)
        error_scale = float(np.median(errors))
        jitter_offset = _truncated_normal(
            random, 0.0, parameters["jitter_sigma"], -3.0, 3.0,
        )
        jitter = error_scale * math.exp(parameters["mu_jitter"] + jitter_offset)
        if parameters["family"] == "K0_white":
            noise[selected] = random.normal(0.0, jitter, int(np.sum(selected)))
            sector_draws[str(sector)] = {"jitter_ratio": jitter / error_scale}
            continue
        amplitude_offset = _truncated_normal(
            random, 0.0, parameters["amplitude_sigma"], -3.0, 3.0,
        )
        tau_lower, tau_upper = parameters["timescale_bounds"]
        offset_lower = max(-3.0, math.log(tau_lower) - parameters["mu_log_timescale"])
        offset_upper = min(3.0, math.log(tau_upper) - parameters["mu_log_timescale"])
        timescale_offset = _truncated_normal(
            random, 0.0, parameters["timescale_sigma"], offset_lower, offset_upper,
        )
        amplitude = error_scale * math.exp(parameters["mu_amplitude"] + amplitude_offset)
        timescale_minutes = math.exp(parameters["mu_log_timescale"] + timescale_offset)
        kernel_id = {
            "M1_matern32": "K2_matern32",
            "OU": "K1_ou",
            "SHO": "K3_sho",
        }.get(parameters["family"])
        if kernel_id is None:
            raise ContractError("unknown simulation noise family: {}".format(parameters["family"]))
        times = frame.loc[selected, "time_btjd"].to_numpy(np.float64)
        gp = GP(build_kernel_term(kernel_id, amplitude, timescale_minutes))
        gp.compute(times, yerr=1e-12, check_sorted=True)
        noise[selected] = _sample_gp(gp, random) + random.normal(
            0.0, jitter, len(times),
        )
        sector_draws[str(sector)] = {
            "jitter_ratio": jitter / error_scale,
            "amplitude_ratio": amplitude / error_scale,
            "timescale_minutes": timescale_minutes,
        }
    return noise, sector_draws


def _transit_flux(frame: pd.DataFrame, architecture: Mapping, geometry):
    if geometry is None:
        return np.ones(len(frame), dtype=np.float64)
    import batman

    transit_spec = architecture["candidate"]["transit_model"]
    parameters = batman.TransitParams()
    parameters.t0 = float(transit_spec["t0_btjd_fixed"])
    parameters.per = float(transit_spec["period_days_fixed"])
    parameters.rp = float(geometry["rp_rs"])
    parameters.a = float(geometry["a_rs"])
    parameters.inc = math.degrees(math.acos(
        float(geometry["impact_parameter"]) / float(geometry["a_rs"])
    ))
    parameters.ecc = float(transit_spec["eccentricity_fixed"])
    parameters.w = 90.0
    parameters.u = list(transit_spec["limb_darkening_quadratic_fixed"])
    parameters.limb_dark = "quadratic"
    result = np.ones(len(frame), dtype=np.float64)
    sectors = frame["sector"].to_numpy(np.int64)
    for sector in SECTORS:
        selected = sectors == sector
        if not np.any(selected):
            continue
        times = frame.loc[selected, "time_btjd"].to_numpy(np.float64)
        model = batman.TransitModel(
            parameters,
            times,
            supersample_factor=int(transit_spec["supersample_factor"]),
            exp_time=float(transit_spec["exposure_seconds"]) / 86400.0,
        )
        result[selected] = model.light_curve(parameters).astype(np.float64)
    return result


def _shared_baseline(frame: pd.DataFrame, events: Tuple[EventSpec, ...], seed: int):
    random = _rng(seed, 500)
    baseline = np.zeros(len(frame), dtype=np.float64)
    assigned = np.zeros(len(frame), dtype=bool)
    time = frame["time_btjd"].to_numpy(np.float64)
    sectors = frame["sector"].to_numpy(np.int64)
    draws = {}
    for event in events:
        coefficients = random.normal(0.0, BASELINE_SIGMA, 3).astype(np.float64)
        draws[event.event_id] = coefficients.tolist()
        selected = (
            (sectors == event.sector)
            & (np.abs(time - event.midpoint_btjd) <= BASELINE_HALF_WIDTH_DAYS)
        )
        if np.any(assigned & selected):
            raise ContractError("event baseline windows overlap")
        x_days = time[selected] - event.midpoint_btjd
        baseline[selected] = np.polynomial.polynomial.polyval(x_days, coefficients)
        assigned[selected] = True
    return baseline, draws


def _telemetry_systematic(frame: pd.DataFrame, class_spec: Mapping, seed: int):
    systematic = class_spec.get("systematic_injection")
    if systematic is None:
        return np.zeros(len(frame), dtype=np.float64), None
    telemetry = str(systematic["telemetry"]).lower()
    column = {"sap_bkg": "sap_bkg", "crowdsap": "crowdsap"}.get(telemetry)
    if column is None:
        raise ContractError("unsupported telemetry injection: {}".format(telemetry))
    bounds_key = (
        "slope_ppm_per_unit"
        if "slope_ppm_per_unit" in systematic
        else "slope_ppm_per_e_per_s"
    )
    slope = float(_rng(seed, 2).uniform(*systematic[bounds_key]))
    centered = frame[column].to_numpy(np.float64).copy()
    sectors = frame["sector"].to_numpy(np.int64)
    for sector in SECTORS:
        selected = sectors == sector
        centered[selected] -= np.median(centered[selected])
    return slope * centered, {
        "telemetry": systematic["telemetry"],
        "column": column,
        "slope": slope,
    }


def generate_realization(
    inputs: Stage3Inputs,
    class_spec: Mapping,
    realization_index: int,
) -> LatentRealization:
    seed = inputs.spec.realization_seed(int(class_spec["class_index"]), realization_index)
    geometry = _draw_geometry(class_spec, seed)
    frame = inputs.raw_template.copy()
    noise, sector_draws = _draw_noise(frame, class_spec, seed)
    transit = _transit_flux(frame, inputs.architecture, geometry)
    events = inputs.events_for_class(class_spec)
    baseline, baseline_draws = _shared_baseline(frame, events, seed)
    telemetry, telemetry_metadata = _telemetry_systematic(frame, class_spec, seed)
    measurement = _rng(seed, 600).normal(
        0.0, frame["flux_err"].to_numpy(np.float64), len(frame),
    )
    noise = noise + telemetry
    true_flux = transit * (1.0 + baseline) + noise
    frame["transit_flux"] = transit
    frame["shared_baseline"] = baseline
    frame["noise_flux"] = noise
    frame["measurement_noise"] = measurement
    frame["true_flux"] = true_flux
    frame["flux"] = true_flux + measurement
    if not np.isfinite(frame[["flux", "true_flux", "transit_flux"]].to_numpy()).all():
        raise ContractError("latent realization contains non-finite flux")
    metadata = {
        "class_id": class_spec["name"].split("_", 1)[0],
        "class_name": class_spec["name"],
        "class_ordinal": int(class_spec["class_index"]),
        "realization_index": int(realization_index),
        "realization_seed": int(seed),
        "drawn_geometry": geometry,
        "sector_noise": sector_draws,
        "telemetry_systematic": telemetry_metadata,
        "shared_baseline_draws": baseline_draws,
        "event_ids": [event.event_id for event in events],
    }
    return LatentRealization(frame=frame, metadata=metadata)
