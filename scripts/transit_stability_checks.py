"""Deterministic maximum-likelihood checks across binning and fit windows."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from transit_model_120s_corrected import (
    OFFICIAL_PERIOD,
    OFFICIAL_T0_BTJD,
    model_flux,
    phase_bin,
)


ROOT = Path(__file__).resolve().parent.parent


def fit_variant(time, flux, u1, u2, initial, half_width_hours, bin_minutes):
    t_bin, f_bin, e_bin, _ = phase_bin(
        time,
        flux,
        OFFICIAL_PERIOD,
        OFFICIAL_T0_BTJD,
        half_width_hr=half_width_hours,
        bin_minutes=bin_minutes,
    )

    def objective(theta):
        rp, a_rs, b, baseline, log_jitter = theta
        if not (
            0.025 < rp < 0.09
            and 4.0 < a_rs < 13.0
            and 0.0 <= b < 1.0 + rp
            and 0.995 < baseline < 1.005
            and np.log(10e-6) < log_jitter < np.log(2000e-6)
        ):
            return np.inf
        model = model_flux(
            t_bin,
            rp,
            a_rs,
            b,
            baseline,
            u1,
            u2,
            exp_minutes=bin_minutes,
        )
        if model is None:
            return np.inf
        sigma = np.sqrt(e_bin**2 + np.exp(log_jitter) ** 2)
        residual = (f_bin - model) / sigma
        return 0.5 * np.sum(residual**2 + np.log(2.0 * np.pi * sigma**2))

    result = minimize(
        objective,
        initial,
        method="Nelder-Mead",
        options={"maxiter": 10000, "xatol": 1e-9, "fatol": 1e-6},
    )
    if not result.success:
        raise RuntimeError(
            f"Stability fit failed for +/-{half_width_hours} h/{bin_minutes} min: "
            f"{result.message}"
        )
    rp, a_rs, b, baseline, log_jitter = result.x
    return {
        "window_half_width_hours": half_width_hours,
        "window_total_width_hours": 2.0 * half_width_hours,
        "bin_minutes": bin_minutes,
        "n_bins": len(t_bin),
        "rp_rs": float(rp),
        "a_rs": float(a_rs),
        "impact_parameter": float(b),
        "baseline": float(baseline),
        "jitter_ppm": float(np.exp(log_jitter) * 1e6),
        "negative_log_likelihood": float(result.fun),
    }


def main():
    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    transit = config["transit_corrected_120s"]
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    initial = np.array(
        [
            transit["rp_rs"],
            transit["a_rs"],
            transit["impact_parameter"],
            1.0,
            np.log(transit["jitter_ppm"] * 1e-6),
        ]
    )
    variants = []
    for window in (10.0, 13.0, 16.0):
        for bin_minutes in (4.0, 8.0, 12.0):
            variants.append(
                fit_variant(
                    data["time"].to_numpy(),
                    data["flux"].to_numpy(),
                    config["limb_darkening"]["u1"],
                    config["limb_darkening"]["u2"],
                    initial,
                    window,
                    bin_minutes,
                )
            )
    reference = next(
        item
        for item in variants
        if item["window_half_width_hours"] == 13.0 and item["bin_minutes"] == 8.0
    )
    for item in variants:
        item["delta_rp_rs_vs_reference"] = item["rp_rs"] - reference["rp_rs"]
        item["delta_a_rs_vs_reference"] = item["a_rs"] - reference["a_rs"]
        item["delta_b_vs_reference"] = (
            item["impact_parameter"] - reference["impact_parameter"]
        )
    result = {
        "method": "prior-free maximum-likelihood perturbation checks",
        "reference": reference,
        "variants": variants,
        "caveat": "These optimization checks do not replace full posterior reruns.",
    }
    output = ROOT / "outputs" / "transit_stability_checks.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
