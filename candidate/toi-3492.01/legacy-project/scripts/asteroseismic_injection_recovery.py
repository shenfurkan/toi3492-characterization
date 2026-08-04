"""Calibrate the preliminary seismic search with stochastic mode injections.

The injections use Lorentzian mode combs sampled on the actual 120-s PDCSAP
timestamps. They are a sensitivity diagnostic, not a replacement for a second
pipeline or a full astrophysical mode-amplitude simulation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from asteroseismic_search import BLOCKS, RAW_DIR, analyze_series, collect


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "asteroseismic_injection_recovery.json"
RNG_SEED = 349201
N_TRIALS = 40
RMS_LEVELS_PPM = (5.0, 10.0, 20.0, 40.0, 80.0)
LINEWIDTH_UHZ = 3.0
SCENARIOS = {
    "tic": {"numax_uhz": 548.63, "dnu_uhz": 36.18},
    "gaia_flame": {"numax_uhz": 639.86, "dnu_uhz": 38.08},
    "circular_transit_fixed_flame_mass": {
        "numax_uhz": 1135.0,
        "dnu_uhz": 58.56,
    },
}


def stochastic_mode_comb(time, numax, dnu, rms_ppm, rng):
    cadence_seconds = 120.0
    grid_length = int(np.ceil((time.max() - time.min()) * 86400.0 / cadence_seconds)) + 1
    frequency_hz = np.fft.rfftfreq(grid_length, cadence_seconds)
    frequency_uhz = frequency_hz * 1e6
    envelope_fwhm = 0.66 * numax ** 0.88
    envelope_sigma = envelope_fwhm / 2.355
    profile = np.zeros_like(frequency_uhz)

    radial = numax + np.arange(-8, 9) * dnu
    for center in radial:
        for offset, visibility in ((0.0, 1.0), (0.5 * dnu, 1.4), (-0.12 * dnu, 0.6)):
            mode = center + offset
            if mode <= 0:
                continue
            height = visibility * np.exp(-0.5 * ((mode - numax) / envelope_sigma) ** 2)
            profile += height / (1.0 + 4.0 * ((frequency_uhz - mode) / LINEWIDTH_UHZ) ** 2)

    random_spectrum = (
        rng.normal(size=len(profile)) + 1j * rng.normal(size=len(profile))
    ) * np.sqrt(profile)
    random_spectrum[0] = 0.0
    signal_grid = np.fft.irfft(random_spectrum, n=grid_length)
    indices = np.rint((time - time.min()) * 86400.0 / cadence_seconds).astype(int)
    signal = signal_grid[indices]
    signal -= np.mean(signal)
    scale = np.std(signal)
    if not np.isfinite(scale) or scale == 0:
        raise RuntimeError("Degenerate stochastic injection")
    return signal * rms_ppm / scale


def recovered(result, expected_numax, expected_dnu):
    numax_ok = abs(result["numax_candidate_uhz"] - expected_numax) <= 0.20 * expected_numax
    dnu_ok = abs(result["dnu_candidate_uhz"] - expected_dnu) <= 0.10 * expected_dnu
    return bool(numax_ok and dnu_ok), bool(numax_ok), bool(dnu_ok)


def main():
    rng = np.random.default_rng(RNG_SEED)
    per_sector = collect("PDCSAP_FLUX", 120)
    blocks = {}
    for block, sectors in BLOCKS.items():
        time = np.concatenate([per_sector[sector][0] for sector in sectors])
        flux = np.concatenate([per_sector[sector][1] for sector in sectors])
        blocks[block] = (time, flux)

    rows = []
    for scenario, expected in SCENARIOS.items():
        for rms_ppm in RMS_LEVELS_PPM:
            strict_trials = 0
            numax_trials = 0
            block_strict = {block: 0 for block in blocks}
            block_numax = {block: 0 for block in blocks}
            block_dnu = {block: 0 for block in blocks}
            for _ in range(N_TRIALS):
                strict_count = 0
                numax_count = 0
                for block, (time, flux) in blocks.items():
                    injection = stochastic_mode_comb(
                        time,
                        expected["numax_uhz"],
                        expected["dnu_uhz"],
                        rms_ppm,
                        rng,
                    )
                    result, _ = analyze_series(time, flux + injection)
                    strict, numax_ok, dnu_ok = recovered(
                        result, expected["numax_uhz"], expected["dnu_uhz"]
                    )
                    block_strict[block] += int(strict)
                    block_numax[block] += int(numax_ok)
                    block_dnu[block] += int(dnu_ok)
                    strict_count += int(strict)
                    numax_count += int(numax_ok)
                strict_trials += int(strict_count >= 2)
                numax_trials += int(numax_count >= 2)

            row = {
                "scenario": scenario,
                **expected,
                "injected_rms_ppm": rms_ppm,
                "n_trials": N_TRIALS,
                "two_block_numax_recovery_fraction": numax_trials / N_TRIALS,
                "two_block_strict_recovery_fraction": strict_trials / N_TRIALS,
                "per_block_numax_recovery_fraction": {
                    block: count / N_TRIALS for block, count in block_numax.items()
                },
                "per_block_dnu_recovery_fraction": {
                    block: count / N_TRIALS for block, count in block_dnu.items()
                },
                "per_block_strict_recovery_fraction": {
                    block: count / N_TRIALS for block, count in block_strict.items()
                },
            }
            rows.append(row)
            print(
                f"{scenario:36s} rms={rms_ppm:5.1f} ppm: "
                f"numax2={row['two_block_numax_recovery_fraction']:.2f}, "
                f"strict2={row['two_block_strict_recovery_fraction']:.2f}"
            )

    payload = {
        "status": "sensitivity_calibration_not_a_detection_test",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": RNG_SEED,
        "n_trials_per_grid_point": N_TRIALS,
        "cadence_seconds": 120,
        "flux_source": "PDCSAP_FLUX with the preregistered preprocessing",
        "mode_linewidth_uhz": LINEWIDTH_UHZ,
        "recovery_definition": {
            "numax_tolerance_fraction": 0.20,
            "dnu_tolerance_fraction": 0.10,
            "experiment_gate": "both parameters recovered in at least two of four blocks",
        },
        "limitations": [
            "Injected rms is the total sampled mode-comb rms, not a radial-mode amplitude.",
            "Lorentzian Fourier simulations approximate stochastic modes but do not span all mixed-mode and activity physics.",
            "A second independent pipeline and colored-noise null calibration remain required.",
        ],
        "results": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
