"""Run a TRICERATOPS false-positive calculation for TOI-3492.01.

This is an optional formal-validation attempt. The installed TRICERATOPS stack
uses older dependencies, so the script applies runtime-only compatibility shims
without modifying site-packages.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time as time_module
import types
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
TIC_ID = 81077799
SECTORS = np.array([37, 63, 64, 90, 99, 100], dtype=int)


warnings.filterwarnings(
    "ignore",
    message="Warning: the tpfmodel submodule is not available without oktopus installed.*",
)
warnings.filterwarnings(
    "ignore",
    message="Unable to import recommended hash 'siphash24.siphash13'.*",
)


def install_compatibility_shims() -> None:
    """Patch old dependency expectations at runtime only."""
    if not hasattr(np, "int"):
        np.int = int  # type: ignore[attr-defined]

    if "pkg_resources" not in sys.modules:
        module = types.ModuleType("pkg_resources")

        def resource_filename(package: str, resource: str) -> str:
            parts = package.split(".")
            spec = importlib.util.find_spec(parts[0])
            if spec is None or spec.submodule_search_locations is None:
                raise ImportError(f"Cannot locate package {package!r}")
            base = Path(spec.submodule_search_locations[0])
            for part in parts[1:]:
                base = base / part
            return str(base / resource)

        module.resource_filename = resource_filename  # type: ignore[attr-defined]
        sys.modules["pkg_resources"] = module


def load_config() -> dict:
    return json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())


def build_folded_binned_light_curve(config: dict, bin_count: int, window_days: float):
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    period = config["transit"]["period"]
    t0 = config["transit"]["t0"]
    duration_days = config["transit"]["duration_hrs"] / 24.0

    phase_days = ((data["time"].to_numpy() - t0 + 0.5 * period) % period) - 0.5 * period
    flux = data["flux"].to_numpy()

    keep = np.isfinite(phase_days) & np.isfinite(flux) & (np.abs(phase_days) <= window_days)
    phase_days = phase_days[keep]
    flux = flux[keep]

    order = np.argsort(phase_days)
    phase_days = phase_days[order]
    flux = flux[order]

    edges = np.linspace(-window_days, window_days, bin_count + 1)
    bin_index = np.digitize(phase_days, edges) - 1

    rows = []
    for idx in range(bin_count):
        in_bin = bin_index == idx
        if np.count_nonzero(in_bin) < 3:
            continue
        rows.append(
            {
                "time": 0.5 * (edges[idx] + edges[idx + 1]),
                "flux": float(np.nanmedian(flux[in_bin])),
                "n": int(np.count_nonzero(in_bin)),
            }
        )

    binned = pd.DataFrame(rows)
    if binned.empty:
        raise RuntimeError("No folded light-curve bins were produced")

    oot = np.abs(binned["time"].to_numpy()) > 1.5 * duration_days
    oot_flux = binned.loc[oot, "flux"].to_numpy()
    scatter = 1.4826 * np.nanmedian(np.abs(oot_flux - np.nanmedian(oot_flux)))
    if not np.isfinite(scatter) or scatter <= 0:
        scatter = float(np.nanstd(oot_flux))
    if not np.isfinite(scatter) or scatter <= 0:
        scatter = float(np.nanmedian(data["flux_err"].to_numpy()))

    return binned, float(scatter)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20000, help="Monte Carlo draws")
    parser.add_argument("--search-radius", type=int, default=10, help="TRICERATOPS search radius in TESS pixels")
    parser.add_argument("--bins", type=int, default=240, help="Number of folded light-curve bins")
    parser.add_argument("--window-days", type=float, default=0.70, help="Folded time window around transit midpoint")
    parser.add_argument("--parallel", action="store_true", help="Use TRICERATOPS parallel mode")
    args = parser.parse_args()

    started = time_module.time()
    np.random.seed(349201)
    config = load_config()

    binned, flux_err = build_folded_binned_light_curve(config, args.bins, args.window_days)
    binned_path = ROOT / "outputs" / "triceratops_120s_folded_binned.csv"
    binned.to_csv(binned_path, index=False)

    install_compatibility_shims()
    import triceratops.funcs as triceratops_funcs
    import triceratops.triceratops as triceratops_module

    original_query_trilegal = triceratops_funcs.query_TRILEGAL

    def query_trilegal_no_ssl(ra, dec, verbose=1, verify_ssl=True):
        return original_query_trilegal(ra, dec, verbose=verbose, verify_ssl=False)

    # The installed TRICERATOPS target initializer hard-codes verify_ssl=True
    # when calling TRILEGAL. Override the imported function in this process
    # only so the run can proceed on systems with incomplete CA bundles.
    triceratops_module.query_TRILEGAL = query_trilegal_no_ssl
    target = triceratops_module.target

    print("Initializing TRICERATOPS target...")
    targ = target(ID=TIC_ID, sectors=SECTORS, search_radius=args.search_radius, mission="TESS")

    depth_ppm = float(config["transit"]["depth_ppm"])
    period = float(config["transit"]["period"])
    exptime_days = 120.0 / 86400.0

    print("Calculating per-star required depths...")
    # This TRICERATOPS version documents tdepth as ppm, but the implementation
    # treats it as a fractional depth when computing per-star depths.
    depth_fraction = depth_ppm * 1e-6
    targ.calc_depths(depth_fraction)

    print(f"Running TRICERATOPS calc_probs with N={args.n}...")
    targ.calc_probs(
        time=binned["time"].to_numpy(dtype=float),
        flux_0=binned["flux"].to_numpy(dtype=float),
        flux_err_0=flux_err,
        P_orb=period,
        N=args.n,
        parallel=args.parallel,
        verbose=1,
        exptime=exptime_days,
        nsamples=10,
    )

    probs_path = ROOT / "outputs" / "triceratops_probs_120s.csv"
    targ.probs.to_csv(probs_path, index=False)

    fpp = float(targ.FPP)
    nfpp = float(targ.NFPP)
    scenario_probs = (
        targ.probs.groupby("scenario")["prob"].sum().sort_values(ascending=False).to_dict()
    )
    dominant_scenario = max(scenario_probs, key=scenario_probs.get) if scenario_probs else None
    dominant_probability = scenario_probs.get(dominant_scenario, 0.0) if dominant_scenario else 0.0

    result = {
        "method": "TRICERATOPS",
        "status": "supporting screening run, not RV confirmation",
        "tic_id": TIC_ID,
        "sectors": SECTORS.tolist(),
        "n_draws": args.n,
        "search_radius_tess_pixels": args.search_radius,
        "bin_count_requested": args.bins,
        "bin_count_used": int(len(binned)),
        "window_days": args.window_days,
        "flux_err_used": flux_err,
        "period_days": period,
        "depth_ppm": depth_ppm,
        "depth_fraction_passed_to_calc_depths": depth_fraction,
        "FPP": fpp,
        "FPP_percent": 100.0 * fpp,
        "NFPP": nfpp,
        "NFPP_percent": 100.0 * nfpp,
        "scenario_probabilities": scenario_probs,
        "dominant_scenario": dominant_scenario,
        "dominant_scenario_probability": dominant_probability,
        "interpretation": (
            f"TRICERATOPS returned FPP numerically {fpp:.3g} for this finite "
            f"run. The dominant listed scenario is {dominant_scenario} with "
            f"probability {dominant_probability:.6g}; interpret the "
            "scenario_probabilities table directly rather than rounding this "
            "to TP=1.0. Treat this as extremely low FPP under the run "
            "assumptions, not as an exact zero probability or mass confirmation."
        ),
        "limitations": [
            "No radial-velocity mass measurement.",
            "No high-resolution imaging contrast curve was supplied.",
            "The fitted a/Rstar remains in 2.6 sigma tension with the TIC-density prediction.",
            "Runtime compatibility shims were needed for this local Python environment.",
        ],
        "runtime_seconds": time_module.time() - started,
        "outputs": {
            "folded_binned_light_curve": binned_path.name,
            "scenario_probabilities_csv": probs_path.name,
        },
        "note": "Runtime compatibility shims applied for numpy.int and pkg_resources.resource_filename; site-packages not modified.",
        "trilegal_ssl_verification": "disabled inside this process because the installed TRICERATOPS target initializer hard-codes verify_ssl=True and the local CA bundle rejects the TRILEGAL certificate.",
    }
    out_path = ROOT / "outputs" / "triceratops_validation_120s.json"
    out_path.write_text(json.dumps(result, indent=2))

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
