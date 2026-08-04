"""Run TRICERATOPS with fixed shims applied BEFORE pytransit import."""
from __future__ import annotations
import argparse, importlib.util, json, sys, time, types, warnings
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TIC_ID = 81077799
SECTORS = np.array([37, 63, 64, 90, 99, 100], dtype=int)

warnings.filterwarnings("ignore", message=".*tpfmodel.*")
warnings.filterwarnings("ignore", message=".*siphash24.*")

# --- Apply shims BEFORE importing triceratops ---
if not hasattr(np, "int"):
    np.int = int
if not hasattr(np, "float"):
    np.float = float
if not hasattr(np, "bool"):
    np.bool = bool
if not hasattr(np, "object"):
    np.object = object
if not hasattr(np, "complex"):
    np.complex = complex

if "pkg_resources" not in sys.modules:
    module = types.ModuleType("pkg_resources")
    def resource_filename(package, resource):
        parts = package.split(".")
        spec = importlib.util.find_spec(parts[0])
        base = Path(spec.submodule_search_locations[0])
        for part in parts[1:]:
            base = base / part
        return str(base / resource)
    module.resource_filename = resource_filename
    sys.modules["pkg_resources"] = module

import triceratops.funcs as triceratops_funcs
import triceratops.triceratops as triceratops_module

# Patch TRILEGAL: return None to trigger the "saved stellar populations" fallback
# This skips the slow Italian server entirely
triceratops_module.query_TRILEGAL = lambda ra, dec, verbose=1, verify_ssl=True: None


def load_config():
    return json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())


def build_binned(config, bin_count, window_days):
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    period = config["transit"]["period"]
    t0 = config["transit"]["t0"]
    dur = config["transit"]["duration_hrs"] / 24.0
    phase = ((data["time"].to_numpy() - t0 + 0.5 * period) % period) - 0.5 * period
    flux = data["flux"].to_numpy()
    keep = np.isfinite(phase) & np.isfinite(flux) & (np.abs(phase) <= window_days)
    phase, flux = phase[keep], flux[keep]
    order = np.argsort(phase)
    phase, flux = phase[order], flux[order]
    edges = np.linspace(-window_days, window_days, bin_count + 1)
    idx = np.digitize(phase, edges) - 1
    rows = []
    for i in range(bin_count):
        m = idx == i
        if np.count_nonzero(m) < 3:
            continue
        rows.append({"time": 0.5*(edges[i]+edges[i+1]),
                     "flux": float(np.nanmedian(flux[m])),
                     "n": int(np.count_nonzero(m))})
    binned = pd.DataFrame(rows)
    oot = np.abs(binned["time"].to_numpy()) > 1.5 * dur
    oot_flux = binned.loc[oot, "flux"].to_numpy()
    scatter = 1.4826 * np.nanmedian(np.abs(oot_flux - np.nanmedian(oot_flux)))
    if not np.isfinite(scatter) or scatter <= 0:
        scatter = float(np.nanstd(oot_flux))
    if not np.isfinite(scatter) or scatter <= 0:
        scatter = float(np.nanmedian(data["flux_err"].to_numpy()))
    return binned, float(scatter)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--search-radius", type=int, default=10)
    parser.add_argument("--bins", type=int, default=120)
    parser.add_argument("--window-days", type=float, default=0.70)
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--allow-nonadopted-screening", action="store_true")
    args = parser.parse_args()
    if not args.allow_nonadopted_screening:
        parser.error("quarantined: pass --allow-nonadopted-screening")

    started = time.time()
    np.random.seed(349201)
    config = load_config()
    binned, flux_err = build_binned(config, args.bins, args.window_days)
    binned_path = ROOT / "outputs" / "triceratops_120s_folded_binned.csv"
    binned.to_csv(binned_path, index=False)
    print(f"binned: {len(binned)} bins, flux_err={flux_err:.6f}")

    target = triceratops_module.target
    print("Initializing TRICERATOPS target (TRILEGAL will use fallback)...")
    try:
        targ = target(ID=TIC_ID, sectors=SECTORS,
                      search_radius=args.search_radius, mission="TESS")
    except Exception as e:
        print(f"target() failed even with fallback: {type(e).__name__}: {e}")
        # Try with synthetic stellar population
        print("Attempting manual Gaia-based target initialization...")
        raise

    depth_ppm = float(config["transit"]["depth_ppm"])
    period = float(config["transit"]["period"])
    exp_days = 120.0 / 86400.0
    print("Calculating depths...")
    targ.calc_depths(depth_ppm * 1e-6)

    print(f"Running calc_probs N={args.n}...")
    targ.calc_probs(
        time=binned["time"].to_numpy(dtype=float),
        flux_0=binned["flux"].to_numpy(dtype=float),
        flux_err_0=flux_err,
        P_orb=period,
        N=args.n,
        parallel=args.parallel,
        verbose=1,
        exptime=exp_days,
        nsamples=10,
    )

    probs_path = ROOT / "outputs" / "triceratops_probs_120s.csv"
    targ.probs.to_csv(probs_path, index=False)

    fpp = float(targ.FPP)
    nfpp = float(targ.NFPP)
    scenarios = targ.probs.groupby("scenario")["prob"].sum().sort_values(ascending=False).to_dict()

    result = {
        "method": "TRICERATOPS",
        "status": "quarantined_screening_not_validation",
        "tic_id": TIC_ID,
        "sectors": SECTORS.tolist(),
        "n_draws": args.n,
        "search_radius_tess_pixels": args.search_radius,
        "bin_count": int(len(binned)),
        "FPP": fpp,
        "FPP_percent": 100.0 * fpp,
        "NFPP": nfpp,
        "NFPP_percent": 100.0 * nfpp,
        "scenario_probabilities": scenarios,
        "runtime_seconds": time.time() - started,
    }
    out = ROOT / "outputs" / "triceratops_validation_120s.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()