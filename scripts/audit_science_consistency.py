"""Offline, assertion-based scientific release audit."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from science import kepler_a_au, kepler_a_rs


ROOT = Path(__file__).resolve().parent.parent


def load_json(relative):
    return json.loads((ROOT / relative).read_text())


def main():
    config = load_json("data/config_corrected_120s.json")
    transit = config["transit_corrected_120s"]
    stellar = config["stellar"]
    reference = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    assert len(reference) == 102502
    assert set(reference["sector"]) == {37, 63, 64, 90, 99, 100}
    assert reference[["time", "flux", "flux_err"]].notna().all().all()

    chain = np.load(ROOT / "data" / "toi3492_chains_120s_corrected.npy")
    raw = np.load(ROOT / "data" / "toi3492_raw_chain_120s_corrected.npy")
    diagnostics = load_json("outputs/mcmc_diagnostics_120s_corrected.json")
    assert tuple(chain.shape) == tuple(diagnostics["flat_chain_shape"])
    assert tuple(raw.shape) == tuple(diagnostics["raw_chain_shape"])
    assert diagnostics["autocorr_reliable_50tau_rule"]
    assert not transit["stellar_density_prior_used"]

    expected_a = float(kepler_a_au(transit["period"], stellar["m_star"]))
    expected_a_rs = float(
        kepler_a_rs(transit["period"], stellar["m_star"], stellar["r_star"])
    )
    assert np.isclose(transit["a_au"], expected_a, rtol=0.01)
    assert np.isclose(
        transit["derived_posterior"]["catalog_a_rs"]["median"],
        expected_a_rs,
        rtol=0.01,
    )

    vetting = load_json("outputs/statistical_validation_120s.json")
    assert vetting["formal_fpp"] is None
    assert not vetting["statistical_validation_claim_supported"]

    cadence = load_json("outputs/cadence_independent_depth_check.json")
    gaia_stellar = load_json("outputs/gaia_stellar_crosscheck.json")
    localization = load_json("outputs/tess_source_localization_120s.json")
    assert cadence["n_points_20s"] == 310533
    assert abs(cadence["delta_20s_minus_matched_120s_robust_sigma_formal"]) < 3
    assert np.isclose(
        gaia_stellar["derived_from_flame_medians"]["expected_circular_a_rs"],
        7.9558813800220705,
    )
    assert localization["summary"]["n_sectors"] == 6

    print("SCIENTIFIC RELEASE AUDIT: PASS")
    print(f"Reference rows: {len(reference)}")
    print(f"Posterior samples: {len(chain)}")
    print(f"Rp/Rs: {transit['rp_rs']:.6f} +/- {transit['rp_rs_err']:.6f}")
    print(f"Circular a/Rs: {transit['a_rs']:.3f} +/- {transit['a_rs_err']:.3f}")
    print(f"Keplerian a: {transit['a_au']:.5f} AU")
    print(
        "Density difference: "
        f"{transit['derived_posterior']['density_difference_sigma']:.2f} sigma"
    )
    print("Formal FPP: not reported")
    print(
        "20s vs matched 120s robust depth: "
        f"{cadence['delta_20s_minus_matched_120s_robust_sigma_formal']:.2f} sigma"
    )
    print(
        "Gaia FLAME expected circular a/Rs: "
        f"{gaia_stellar['derived_from_flame_medians']['expected_circular_a_rs']:.3f}"
    )


if __name__ == "__main__":
    main()
