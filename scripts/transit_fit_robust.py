"""Joint native-cadence transit fit with sector-level nuisance parameters.

The fit keeps every point within the transit window rather than fitting a
phase-binned median. Geometry and ephemeris are shared, while each sector has
its own radius ratio, linear baseline, and white-noise floor. Quadratic limb
darkening is sampled with Kipping's physical q1/q2 parameterization. A fixed
AR(1) coefficient, estimated from out-of-transit consecutive samples in each
sector, provides a transparent short-timescale correlated-noise treatment.

This script is an independent robustness analysis. It does not overwrite the
adopted configuration.
"""

import argparse
import json
from pathlib import Path

import batman
import emcee
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from science import percentile_summary, photometric_density_solar, transit_duration_hours


ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_PERIOD = 9.2224171
OFFICIAL_PERIOD_ERR = 0.0000098
OFFICIAL_T0 = 2459314.5211550 - 2457000.0
OFFICIAL_T0_ERR = 0.000615
WINDOW_HALF_WIDTH_HOURS = 13.0
LD_SYSTEMATIC_FLOOR = 0.05


def q_to_u(q1, q2):
    """Convert Kipping (2013) q1/q2 to quadratic coefficients."""
    root = np.sqrt(q1)
    return 2.0 * root * q2, root * (1.0 - 2.0 * q2)


def u_to_q(u1, u2):
    """Convert physical quadratic coefficients to Kipping q1/q2."""
    total = u1 + u2
    return total**2, u1 / (2.0 * total)


def ar1_coefficient(time, flux, phase, cadence_days):
    """Estimate lag-one correlation from consecutive out-of-transit points."""
    oot = np.abs(phase) > 0.16
    if np.count_nonzero(oot) < 20:
        return 0.0
    x = time - np.nanmedian(time)
    design = np.column_stack((np.ones_like(x), x))
    coef = np.linalg.lstsq(design[oot], flux[oot], rcond=None)[0]
    residual = flux - design @ coef
    pair = oot[1:] & oot[:-1] & (np.diff(time) < 2.5 * cadence_days)
    if np.count_nonzero(pair) < 20:
        return 0.0
    left = residual[:-1][pair]
    right = residual[1:][pair]
    phi = np.corrcoef(left, right)[0, 1]
    return float(np.clip(phi if np.isfinite(phi) else 0.0, 0.0, 0.8))


def ar1_transform(values, contiguous, phi):
    """Apply the conditional AR(1) whitening transform to a vector or matrix."""
    transformed = np.array(values, dtype=float, copy=True)
    if phi <= 0.0 or len(transformed) < 2:
        return transformed
    scale = np.sqrt(1.0 - phi**2)
    current = transformed[1:].copy()
    previous = transformed[:-1].copy()
    transformed[1:][contiguous] = (
        current[contiguous] - phi * previous[contiguous]
    ) / scale
    return transformed


class JointTransitLikelihood:
    """Native-cadence likelihood with analytically profiled sector baselines."""

    def __init__(self, data, config):
        phase = (
            (data["time"].to_numpy() - OFFICIAL_T0 + 0.5 * OFFICIAL_PERIOD)
            % OFFICIAL_PERIOD
        ) - 0.5 * OFFICIAL_PERIOD
        selected = data.loc[
            np.abs(phase) < WINDOW_HALF_WIDTH_HOURS / 24.0
        ].copy()
        selected["phase"] = phase[
            np.abs(phase) < WINDOW_HALF_WIDTH_HOURS / 24.0
        ]
        selected = selected.sort_values(["sector", "time"])

        self.sectors = sorted(int(value) for value in selected["sector"].unique())
        self.ld_u = np.array(
            [config["limb_darkening"]["u1"], config["limb_darkening"]["u2"]]
        )
        self.ld_sigma = np.maximum(
            [
                config["limb_darkening"].get("u1_err", 0.0),
                config["limb_darkening"].get("u2_err", 0.0),
            ],
            LD_SYSTEMATIC_FLOOR,
        )
        self.blocks = []
        initial = config["transit"]

        depth_path = ROOT / "outputs" / "toi3492_120s_sector_depths.csv"
        depth_scale = {}
        if depth_path.exists():
            depths = pd.read_csv(depth_path).set_index("sector")["depth_ppm"]
            median_depth = float(np.nanmedian(depths))
            depth_scale = {
                int(sector): np.sqrt(float(depth) / median_depth)
                for sector, depth in depths.items()
            }

        rp_initial = []
        for sector in self.sectors:
            block = selected[selected["sector"] == sector]
            time = block["time"].to_numpy(float)
            flux = block["flux"].to_numpy(float)
            error = block["flux_err"].to_numpy(float)
            exposure_seconds = float(np.nanmedian(block["exptime"]))
            cadence_days = exposure_seconds / 86400.0
            contiguous = np.diff(time) < 2.5 * cadence_days
            phi = ar1_coefficient(
                time, flux, block["phase"].to_numpy(float), cadence_days
            )
            x = time - np.nanmedian(time)

            params = batman.TransitParams()
            params.t0 = OFFICIAL_T0
            params.per = OFFICIAL_PERIOD
            params.rp = initial["rp_rs"]
            params.a = initial["a_rs"]
            params.inc = initial["inc"]
            params.ecc = 0.0
            params.w = 90.0
            params.u = self.ld_u.tolist()
            params.limb_dark = "quadratic"
            supersample = 7 if exposure_seconds > 60.0 else 3
            transit_model = batman.TransitModel(
                params,
                time,
                supersample_factor=supersample,
                exp_time=exposure_seconds / 86400.0,
            )
            self.blocks.append(
                {
                    "sector": sector,
                    "time": time,
                    "flux": flux,
                    "error": error,
                    "x": x,
                    "contiguous": contiguous,
                    "phi": phi,
                    "params": params,
                    "model": transit_model,
                    "exposure_seconds": exposure_seconds,
                }
            )
            rp_initial.append(initial["rp_rs"] * depth_scale.get(sector, 1.0))

        q1, q2 = u_to_q(*self.ld_u)
        initial_jitter = np.full(len(self.sectors), np.log(100e-6))
        self.initial = np.concatenate(
            (
                [initial["a_rs"], initial["impact_parameter"], 0.0, 0.0, q1, q2],
                rp_initial,
                initial_jitter,
            )
        )

    @property
    def ndim(self):
        return 6 + 2 * len(self.sectors)

    def bounds(self):
        n = len(self.sectors)
        return (
            [(4.0, 16.0), (0.0, 1.09), (-8.0, 8.0), (-8.0, 8.0)]
            + [(1e-4, 0.9999), (1e-4, 0.9999)]
            + [(0.025, 0.09)] * n
            + [(np.log(1e-6), np.log(3000e-6))] * n
        )

    def unpack(self, theta):
        n = len(self.sectors)
        a_rs, impact, period_z, t0_z, q1, q2 = theta[:6]
        return (
            a_rs,
            impact,
            OFFICIAL_PERIOD + period_z * OFFICIAL_PERIOD_ERR,
            OFFICIAL_T0 + t0_z * OFFICIAL_T0_ERR,
            q1,
            q2,
            np.asarray(theta[6 : 6 + n]),
            np.exp(np.asarray(theta[6 + n : 6 + 2 * n])),
        )

    def log_prior(self, theta):
        for value, (lower, upper) in zip(theta, self.bounds()):
            if not lower < value < upper:
                return -np.inf
        a_rs, impact, _, _, q1, q2 = theta[:6]
        rp = np.asarray(theta[6 : 6 + len(self.sectors)])
        if np.any(impact >= 1.0 + rp) or impact >= a_rs:
            return -np.inf
        u1, u2 = q_to_u(q1, q2)
        ld_pull = (np.array([u1, u2]) - self.ld_u) / self.ld_sigma
        ephemeris_pull = np.asarray(theta[2:4])
        return float(-0.5 * (np.sum(ld_pull**2) + np.sum(ephemeris_pull**2)))

    def evaluate(self, theta, return_baselines=False):
        prior = self.log_prior(theta)
        if not np.isfinite(prior):
            return (-np.inf, None) if return_baselines else -np.inf
        a_rs, impact, period, t0, q1, q2, radii, jitters = self.unpack(theta)
        u1, u2 = q_to_u(q1, q2)
        cos_inc = impact / a_rs
        if not 0.0 <= cos_inc <= 1.0:
            return (-np.inf, None) if return_baselines else -np.inf
        inclination = np.degrees(np.arccos(cos_inc))
        log_likelihood = 0.0
        baselines = []

        for block, radius, jitter in zip(self.blocks, radii, jitters):
            params = block["params"]
            params.t0 = t0
            params.per = period
            params.rp = radius
            params.a = a_rs
            params.inc = inclination
            params.u = [u1, u2]
            transit = block["model"].light_curve(params)
            design = np.column_stack((transit, transit * block["x"]))
            whitened_flux = ar1_transform(
                block["flux"], block["contiguous"], block["phi"]
            )
            whitened_design = ar1_transform(
                design, block["contiguous"], block["phi"]
            )
            sigma = np.sqrt(block["error"] ** 2 + jitter**2)
            weight = 1.0 / sigma**2
            normal = whitened_design.T @ (weight[:, None] * whitened_design)
            rhs = whitened_design.T @ (weight * whitened_flux)
            try:
                coef = np.linalg.solve(normal, rhs)
            except np.linalg.LinAlgError:
                return (-np.inf, None) if return_baselines else -np.inf
            if not 0.97 < coef[0] < 1.03 or abs(coef[1]) > 0.02:
                return (-np.inf, None) if return_baselines else -np.inf
            residual = whitened_flux - whitened_design @ coef
            log_likelihood -= 0.5 * np.sum(
                (residual / sigma) ** 2 + np.log(2.0 * np.pi * sigma**2)
            )
            baselines.append(
                {
                    "sector": block["sector"],
                    "offset": float(coef[0]),
                    "slope_per_day": float(coef[1]),
                    "ar1_phi_fixed": block["phi"],
                    "jitter_ppm": float(jitter * 1e6),
                    "n_points": len(block["time"]),
                }
            )
        value = prior + log_likelihood
        return (value, baselines) if return_baselines else value


def initialize_walkers(fit, optimum, walkers, rng):
    """Draw a finite, non-degenerate walker cloud around the optimizer result."""
    scales = np.concatenate(
        (
            [0.08, 0.015, 0.15, 0.15, 0.015, 0.015],
            np.full(len(fit.sectors), 3e-4),
            np.full(len(fit.sectors), 0.08),
        )
    )
    cloud = np.empty((walkers, fit.ndim))
    bounds = fit.bounds()
    for index in range(walkers):
        for _ in range(1000):
            candidate = optimum + rng.normal(size=fit.ndim) * scales
            for column, (lower, upper) in enumerate(bounds):
                candidate[column] = np.clip(candidate[column], lower + 1e-8, upper - 1e-8)
            if np.isfinite(fit.evaluate(candidate)):
                cloud[index] = candidate
                break
        else:
            raise RuntimeError("Could not initialize finite MCMC walkers")
    return cloud


def summarize(fit, samples, optimum, sampler, cadence):
    """Create the JSON-ready robustness result."""
    a_rs, impact, period, t0, q1, q2, radii, jitters = fit.unpack(
        np.median(samples, axis=0)
    )
    u1, u2 = q_to_u(q1, q2)
    radius_draws = samples[:, 6 : 6 + len(fit.sectors)]
    mean_radius_draws = np.mean(radius_draws, axis=1)
    density_draws = photometric_density_solar(
        OFFICIAL_PERIOD + samples[:, 2] * OFFICIAL_PERIOD_ERR, samples[:, 0]
    )
    duration_draws = transit_duration_hours(
        OFFICIAL_PERIOD + samples[:, 2] * OFFICIAL_PERIOD_ERR,
        mean_radius_draws,
        samples[:, 0],
        samples[:, 1],
    )
    _, baselines = fit.evaluate(np.median(samples, axis=0), return_baselines=True)
    sector_results = []
    for index, sector in enumerate(fit.sectors):
        sector_results.append(
            {
                "sector": sector,
                "rp_rs": percentile_summary(radius_draws[:, index]),
                "area_ratio_ppm": percentile_summary(radius_draws[:, index] ** 2 * 1e6),
                "jitter_ppm": percentile_summary(
                    np.exp(samples[:, 6 + len(fit.sectors) + index]) * 1e6
                ),
                "ar1_phi_fixed": fit.blocks[index]["phi"],
            }
        )
    try:
        tau = sampler.get_autocorr_time(tol=0)
        tau = [float(value) for value in tau]
    except Exception:
        tau = None
    return {
        "status": "robustness_fit_not_adopted",
        "cadence_seconds": cadence,
        "method": "native-cadence circular joint fit; shared geometry and ephemeris; sector radius ratios, profiled linear baselines, sector jitters; fixed empirical AR(1) whitening",
        "n_points": int(sum(len(block["time"]) for block in fit.blocks)),
        "sectors": fit.sectors,
        "window_half_width_hours": WINDOW_HALF_WIDTH_HOURS,
        "window_total_width_hours": 2.0 * WINDOW_HALF_WIDTH_HOURS,
        "exposure_integration": {
            str(block["sector"]): {
                "seconds": block["exposure_seconds"],
                "supersample_factor": 7 if block["exposure_seconds"] > 60.0 else 3,
            }
            for block in fit.blocks
        },
        "shared_geometry": {
            "a_rs": percentile_summary(samples[:, 0]),
            "impact_parameter": percentile_summary(samples[:, 1]),
            "inclination_deg": percentile_summary(
                np.degrees(np.arccos(samples[:, 1] / samples[:, 0]))
            ),
            "period_days": percentile_summary(
                OFFICIAL_PERIOD + samples[:, 2] * OFFICIAL_PERIOD_ERR
            ),
            "t0_btjd": percentile_summary(OFFICIAL_T0 + samples[:, 3] * OFFICIAL_T0_ERR),
            "mean_rp_rs": percentile_summary(mean_radius_draws),
            "duration_hours": percentile_summary(duration_draws),
            "circular_density_solar": percentile_summary(density_draws),
        },
        "limb_darkening": {
            "u1": float(u1),
            "u2": float(u2),
            "prior_mean": fit.ld_u.tolist(),
            "prior_sigma_with_systematic_floor": fit.ld_sigma.tolist(),
            "parameterization": "Kipping q1/q2",
        },
        "sector_posteriors": sector_results,
        "profiled_baselines_at_posterior_median": baselines,
        "optimizer": {
            "theta": [float(value) for value in optimum],
            "log_posterior": float(fit.evaluate(optimum)),
        },
        "mcmc": {
            "walkers": int(sampler.get_chain().shape[1]),
            "production_steps": int(sampler.get_chain().shape[0]),
            "retained_samples": int(len(samples)),
            "acceptance_fraction_mean": float(np.mean(sampler.acceptance_fraction)),
            "autocorrelation_time_steps": tau,
            "reliable_50tau_rule": bool(
                tau is not None
                and min(sampler.get_chain().shape[0] / np.asarray(tau)) >= 50.0
            ),
        },
        "caveats": [
            "AR(1) coefficients are fixed empirical out-of-transit estimates, not sampled Gaussian-process hyperparameters.",
            "The cadence products come from the same TESS pixels and are not independent observations.",
            "No event-level or sector-level timing offsets are fitted beyond the shared linear ephemeris.",
            "Sector baselines are profiled rather than marginalized, and the fixed AR(1) uncertainty is not propagated.",
            "Sector radius ratios have independent bounded priors; their arithmetic mean is not a hierarchical common-radius posterior.",
            "Only broadened LDTk-centered limb-darkening priors are tested; no alternate atmosphere prescription is included.",
            "The optimizer did not move materially from its supplied initial vector; posterior movement comes from the short ensemble chain.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cadence", type=int, choices=(20, 120), default=120)
    parser.add_argument("--burnin", type=int, default=600)
    parser.add_argument("--steps", type=int, default=1800)
    parser.add_argument("--walkers", type=int, default=64)
    args = parser.parse_args()
    if args.walkers < 2 * (6 + 12):
        parser.error("--walkers must be at least 36")

    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    data = pd.read_csv(ROOT / "data" / f"toi3492_{args.cadence}s_reference.csv")
    fit = JointTransitLikelihood(data, config)
    if args.walkers < 2 * fit.ndim:
        parser.error(f"--walkers must be at least {2 * fit.ndim} for this dataset")

    print(f"Fitting {sum(len(block['time']) for block in fit.blocks)} points")
    print("AR(1) coefficients:", {block["sector"]: block["phi"] for block in fit.blocks})
    result = minimize(
        lambda theta: -fit.evaluate(theta),
        fit.initial,
        method="L-BFGS-B",
        bounds=fit.bounds(),
        options={"maxiter": 1500, "ftol": 1e-10, "maxls": 40},
    )
    if not np.isfinite(result.fun):
        raise RuntimeError(f"Robust transit optimization failed: {result.message}")
    print(f"Optimizer: success={result.success}, objective={result.fun:.3f}")

    rng = np.random.default_rng(3492 + args.cadence)
    walkers = initialize_walkers(fit, result.x, args.walkers, rng)
    sampler = emcee.EnsembleSampler(args.walkers, fit.ndim, fit.evaluate)
    state = sampler.run_mcmc(walkers, args.burnin, progress=True)
    sampler.reset()
    sampler.run_mcmc(state, args.steps, progress=True)
    discard = min(max(args.steps // 5, 1), args.steps - 1)
    samples = sampler.get_chain(discard=discard, flat=True)

    output = summarize(fit, samples, result.x, sampler, args.cadence)
    output_path = ROOT / "outputs" / f"transit_fit_robust_{args.cadence}s.json"
    chain_path = ROOT / "data" / f"toi3492_chains_robust_{args.cadence}s.npy"
    output_path.write_text(json.dumps(output, indent=2))
    np.save(chain_path, samples)
    print(json.dumps(output["shared_geometry"], indent=2))
    print(f"Wrote {output_path.relative_to(ROOT)}")
    print(f"Wrote {chain_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
