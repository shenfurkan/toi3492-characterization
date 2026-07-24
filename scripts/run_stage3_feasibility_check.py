"""S3-04B feasibility check — parallel + progress bar.

Generates N white + N M1-160 synthetic realizations and runs K0 vs M1
screening on one representative branch (W16_P1, raw_valid mask).
Uses multiprocessing for parallel execution and tqdm for progress.

This script does NOT modify any frozen artifact.
"""

import json
import math
import sys
import time
import os
from pathlib import Path
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

K3_NAME = "K3_MATERN32_SECTOR"
SECTORS = (37, 63, 64, 90, 99, 100)
HELD_SECTOR = 37
N_REALIZATIONS = 10
SEED_BASE = 34920499
LOG_PATH = ROOT / "outputs" / "stage3_feasibility_check.log"

_pdcsap = None
_events = None
_t14 = None


def _init_worker():
    global _pdcsap, _events, _t14
    import stage3_synthetic_generator as gen
    _pdcsap, _events, _t14 = gen.load_timestamps()


def make_sector_data(frame, events, window_hours, degree, t14_hours):
    oot_inner = 0.75 * t14_hours / 24.0
    half = window_hours / 48.0
    result = {}
    for sector in SECTORS:
        sec_frame = frame[frame["sector"] == sector].copy()
        if sec_frame.empty:
            continue
        sec_frame.sort_values("time_btjd", inplace=True)
        sec_frame.reset_index(drop=True, inplace=True)

        event_ids = []
        for event in events:
            if event["sector"] != sector:
                continue
            dist = (sec_frame["time_btjd"].to_numpy(float) -
                    event["midpoint_btjd"])
            ids = np.full(len(sec_frame), f"S{sector:03d}-E{event['epoch']:03d}")
            event_ids.append((np.abs(dist) <= half, ids))
        n_events = len(event_ids)
        design = np.zeros((len(sec_frame), n_events * (degree + 1)),
                          dtype=np.float64)
        for idx, (mask, eid) in enumerate(event_ids):
            x = sec_frame.loc[mask, "time_btjd"].to_numpy(float)
            for mid in events:
                if mid["sector"] == sector:
                    x_days = x - mid["midpoint_btjd"]
                    break
            basis = np.column_stack([x_days**p for p in range(degree + 1)])
            design[mask, idx * (degree + 1):(idx + 1) * (degree + 1)] = basis

        oot_mask = np.ones(len(sec_frame), dtype=bool)
        for event in events:
            if event["sector"] != sector:
                continue
            dist = np.abs(sec_frame["time_btjd"].to_numpy(float) -
                         event["midpoint_btjd"])
            oot_mask &= (dist >= oot_inner)

        if oot_mask.sum() < 3:
            continue
        from faz6_noise_core import SectorData
        flux = sec_frame["flux"].to_numpy(float)[oot_mask] - 1.0
        time_arr = sec_frame["time_btjd"].to_numpy(float)[oot_mask]
        err = sec_frame["flux_err"].to_numpy(float)[oot_mask]
        result[sector] = SectorData(
            sector=sector,
            time=time_arr,
            flux=flux,
            flux_err=err,
            baseline_matrix=design[oot_mask],
        )
    return result


def _run_one(args):
    cls_name, noise_family, mu_amp, mu_jit, seed = args
    t0 = time.time()
    try:
        import stage3_synthetic_generator as gen
        from faz6_noise_core import fit_pooled_map as old_fit, SectorData
        from stage3_noise_core import (
            fit_pooled_map, held_sector_joint_log_predictive_density,
        )

        frame = gen.generate_realization(
            _pdcsap, _events, _t14, seed,
            noise_family=noise_family,
            inject_transit=True,
            mu_jitter=mu_jit,
            mu_amplitude=mu_amp,
        )
        sd = make_sector_data(frame, _events, 16, 1, _t14)
        train = [sd[s] for s in SECTORS if s != HELD_SECTOR and s in sd]
        held = sd.get(HELD_SECTOR)

        if len(train) < 5 or held is None:
            return {"class": cls_name, "seed": seed, "error": "insufficient data",
                    "elapsed": time.time() - t0}

        fit_k0 = old_fit(tuple(train), "K0_white")
        fit_m1 = fit_pooled_map(tuple(train), K3_NAME)

        score_k0 = held_sector_joint_log_predictive_density(held, fit_k0)
        score_m1 = held_sector_joint_log_predictive_density(held, fit_m1)

        if not (fit_m1.success and np.isfinite(score_m1)):
            return {"class": cls_name, "seed": seed, "error": "M1 fit failed",
                    "elapsed": time.time() - t0}
        if not (fit_k0.success and np.isfinite(score_k0)):
            score_k0 = -np.inf

        delta = score_m1 - score_k0
        winner = "M1" if delta > 0 else "K0"
        return {
            "class": cls_name, "realization": seed - SEED_BASE,
            "seed": seed,
            "k0_score": float(score_k0) if np.isfinite(score_k0) else None,
            "m1_score": float(score_m1) if np.isfinite(score_m1) else None,
            "delta": float(delta) if np.isfinite(delta) else None,
            "winner": winner,
            "elapsed": time.time() - t0,
        }
    except Exception as exc:
        return {"class": cls_name, "seed": seed, "error": str(exc),
                "elapsed": time.time() - t0}


def _log(msg, f=None):
    line = msg + "\n"
    print(msg, flush=True)
    if f:
        f.write(line)
        f.flush()


def run():
    classes = [
        ("C01_white", "K0_white", -1.0, -1.0, 0),
        ("C02_M1_160", "M1_matern32", -1.0, -1.0, 10000),
    ]

    task_args = []
    for cls_name, noise_family, mu_amp, mu_jit, offset in classes:
        for n in range(N_REALIZATIONS):
            seed = SEED_BASE + offset + n
            task_args.append((cls_name, noise_family, mu_amp, mu_jit, seed))

    total_tasks = len(task_args)
    _log(f"S3-04B Feasibility Check: {total_tasks} realizations, "
         f"{min(cpu_count(), 4)} workers")

    try:
        from tqdm import tqdm
        use_tqdm = True
    except ImportError:
        use_tqdm = False
        _log("  (tqdm not available, using simple progress)")

    n_workers = min(cpu_count(), 4)
    results = []

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        _log(f"=== S3-04B Feasibility Check ===", f)
        _log(f"Workers: {n_workers}  Tasks: {total_tasks}", f)
        _log(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}", f)
        _log("", f)

        if use_tqdm:
            pbar = tqdm(total=total_tasks, desc="S3-04B", file=sys.stderr)
        else:
            pbar = None

        with Pool(n_workers, initializer=_init_worker) as pool:
            completed = 0
            for res in pool.imap_unordered(_run_one, task_args):
                completed += 1
                results.append(res)
                if pbar:
                    pbar.update(1)
                if "error" in res:
                    _log(f"  [{completed}/{total_tasks}] {res['class']} "
                         f"seed={res['seed']} ERROR: {res['error']} "
                         f"({res.get('elapsed', 0):.0f}s)", f)
                else:
                    _log(f"  [{completed}/{total_tasks}] {res['class']} "
                         f"seed={res['seed']} -> {res['winner']} "
                         f"(delta={res['delta']:.3f}) "
                         f"({res.get('elapsed', 0):.0f}s)", f)

        if pbar:
            pbar.close()

        _log("", f)
        _log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}", f)

    df = pd.DataFrame(results)
    _log(f"\n=== SUMMARY ===")
    for cls in df["class"].dropna().unique():
        sub = df[df["class"] == cls]
        m1 = (sub["winner"] == "M1").sum()
        k0 = (sub["winner"] == "K0").sum()
        total = m1 + k0
        err = (sub["error"].notna()).sum() if "error" in sub.columns else 0
        rate = m1 / total if total else 0
        _log(f"  {cls}: M1={m1} K0={k0} errors={err}  M1-rate={rate:.2f}")

    if (df["class"] == "C01_white").any():
        white_m1 = ((df["class"] == "C01_white") & (df["winner"] == "M1")).sum()
        white_total = ((df["class"] == "C01_white") &
                       (df["winner"].isin(["M1", "K0"]))).sum()
        white_rate = white_m1 / max(1, white_total)
        _log(f"  False-M1 rate on white: {white_rate:.2f}  (target <= 0.10)")

    if (df["class"] == "C02_M1_160").any():
        m1_m1 = ((df["class"] == "C02_M1_160") & (df["winner"] == "M1")).sum()
        m1_total = ((df["class"] == "C02_M1_160") &
                    (df["winner"].isin(["M1", "K0"]))).sum()
        m1_rate = m1_m1 / max(1, m1_total)
        _log(f"  True-M1 rate on M1-160: {m1_rate:.2f}  (target >= 0.70)")

    return df


if __name__ == "__main__":
    df = run()
    csv_path = "outputs/stage3_feasibility_check.csv"
    df.to_csv(csv_path, index=False)
    print("Saved", csv_path)
    print("Full log: outputs/stage3_feasibility_check.log")