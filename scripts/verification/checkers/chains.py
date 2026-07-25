"""Verification checks for MCMC chains (primary chain and stage 6 free limb-darkening chain)."""

from __future__ import annotations

import math
import numpy as np

from ..core import ROOT, Verification, _close, _integrated_autocorrelation_time, _load, _rank_split_rhat


def verify_primary_chain(audit: Verification) -> None:
    config = _load("data/config_corrected_120s.json")
    diagnostics = _load("outputs/mcmc_diagnostics_120s_corrected.json")
    raw = np.load(ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy", allow_pickle=False)
    flat = np.load(ROOT / "data" / "toi3492_chains_120s_corrected.npy", allow_pickle=False)
    discard = int(diagnostics["flat_discard_steps"])
    audit.check("primary_chain", "shape_and_finiteness", bool(
        tuple(raw.shape) == tuple(diagnostics["raw_chain_shape"])
        and tuple(flat.shape) == tuple(diagnostics["flat_chain_shape"])
        and np.isfinite(raw).all() and np.isfinite(flat).all()
    ), f"raw={raw.shape} flat={flat.shape}")
    audit.check("primary_chain", "flat_chain_is_exact_raw_slice", bool(
        np.array_equal(flat, raw[discard:].reshape(-1, raw.shape[-1]))
    ), f"discard={discard}")
    audit.check("primary_chain", "all_draws_physical", bool(
        np.all((flat[:, 0] > 0) & (flat[:, 0] < 1))
        and np.all(flat[:, 1] > 0)
        and np.all((flat[:, 2] >= 0) & (flat[:, 2] < 1.0 + flat[:, 0]))
        and np.all(flat[:, 2] < flat[:, 1])
    ), "rp/a/b support")
    medians = np.median(flat, axis=0)
    names = ("rp_rs", "a_rs", "impact_parameter")
    for index, name in enumerate(names):
        audit.check("primary_chain", f"median_{name}", _close(
            medians[index], config["transit"][name], rel=0, abs_tol=1e-12,
        ), f"computed={medians[index]:.12g} stored={config['transit'][name]:.12g}")
    rhat = _rank_split_rhat(raw[discard:])
    rhat_max = float(np.max(rhat))
    audit.check("primary_chain", "rank_split_rhat_computed", bool(
        np.isfinite(rhat).all() and rhat_max < 1.05
    ), f"max={rhat_max:.5f}")
    if rhat_max >= 1.01:
        audit.warning(
            "primary_chain", "strict_rank_split_rhat_not_met",
            f"Independent rank-normalized split-Rhat is {rhat_max:.5f}, above the 1.01 adoption threshold. "
            "The reference fit remains descriptive and must not be promoted to a native-cadence posterior.",
        )
    tau = _integrated_autocorrelation_time(raw[discard:])
    ratios = raw[discard:].shape[0] / tau
    audit.check("primary_chain", "independent_50tau", bool(np.all(ratios > 50.0)),
                f"min_steps_per_tau={float(np.min(ratios)):.1f}")


def verify_stage6_chain(audit: Verification) -> None:
    chain = np.load(ROOT / "data" / "stage6_free_ld_chain.npy", allow_pickle=False)
    result = _load("outputs/stage6_free_ld_transit.json")
    diagnostics = _load("outputs/stage6_free_ld_diagnostics.json")
    names = diagnostics["parameters"]
    audit.check("stage6_free_ld", "chain_metadata", bool(
        chain.shape == (384000, 7) and np.isfinite(chain).all()
        and result["mcmc"]["walkers"] == diagnostics["walkers"] == 48
        and result["mcmc"]["production"] == diagnostics["production"] == 8000
        and result["mcmc"]["flat_samples"] == diagnostics["flat_samples"] == len(chain)
    ), f"shape={chain.shape} production={result['mcmc']['production']}")
    posterior_ok = True
    for index, name in enumerate(names):
        quantiles = np.quantile(chain[:, index], [0.16, 0.50, 0.84])
        stored = result["posterior"][name]
        posterior_ok &= bool(np.allclose(
            quantiles, [stored["p16"], stored["median"], stored["p84"]], rtol=0, atol=1e-12,
        ))
    audit.check("stage6_free_ld", "posterior_quantiles_from_chain", posterior_ok,
                f"parameters={','.join(names)}")
    rp, a_rs, impact, _, _, q1, q2 = chain.T
    u1 = 2.0 * math.sqrt(float(np.median(q1))) * float(np.median(q2))
    u2 = math.sqrt(float(np.median(q1))) * (1.0 - 2.0 * float(np.median(q2)))
    tau_max = max(result["mcmc"]["autocorrelation_times"].values())
    audit.check("stage6_free_ld", "physical_support_and_kipping_transform", bool(
        np.all((rp > 0) & (a_rs > 0) & (impact >= 0) & (impact < 1.0 + rp))
        and np.all((q1 > 0) & (q1 < 1) & (q2 > 0) & (q2 < 1))
        and _close(u1, result["derived_u1_u2"]["u1"], rel=0, abs_tol=5e-7)
        and _close(u2, result["derived_u1_u2"]["u2"], rel=0, abs_tol=5e-7)
        and result["mcmc"]["production"] / tau_max > 50.0
    ), f"u1={u1:.6f} u2={u2:.6f} steps/tau={result['mcmc']['production'] / tau_max:.1f}")
    audit.check("stage6_free_ld", "nonadopted_diagnostic_scope", bool(
        result["status"] == "PASS" and "not an adopted native-cadence posterior" in result["caveat"]
    ), result["work_package"])
    audit.warning("stage6_free_ld", "walker_history_not_retained",
                  "Only the flattened diagnostic chain is retained, so split-Rhat and autocorrelation cannot be recomputed independently.")
