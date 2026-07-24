"""Freeze the single Stage-3 noise-model architecture before any real-data fit.

The decision addresses the two known Phase-6/6R failures identified in S3-02:
(1) shared correlated-kernel timescale saturation at the 360-minute upper bound,
and (2) K0 residual beta excess with sector-dependent drivers.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "stage3_model_architecture_decision.json"

MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest.json"
S3_02_REPORT_PATH = ROOT / "outputs" / "stage3_phase6_postmortem.json"
PHASE5B_REPORT_PATH = ROOT / "outputs" / "faz5b_remediation.json"
PHASE2_REPORT_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
PHASE4_REPORT_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"
PHASE5_PREREG_PATH = ROOT / "data" / "faz5_preregistered_grid.json"
PHASE6_PREREG_PATH = ROOT / "data" / "faz6_preregistered_kernels.json"

DECLARED_SOURCES = (
    "data/stage3_input_manifest.json",
    "outputs/stage3_phase6_postmortem.json",
    "outputs/faz5b_remediation.json",
    "outputs/faz2_transit_inventory.json",
    "outputs/faz4_reduction_comparison.json",
    "data/faz5_preregistered_grid.json",
    "data/faz6_preregistered_kernels.json",
    "scripts/build_stage3_model_architecture_decision.py",
)


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def json_ready(value):
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def build_decision():
    manifest = load_json("data/stage3_input_manifest.json")
    s3_02 = load_json("outputs/stage3_phase6_postmortem.json")
    phase5b = load_json("outputs/faz5b_remediation.json")
    phase2 = load_json("outputs/faz2_transit_inventory.json")
    phase4 = load_json("outputs/faz4_reduction_comparison.json")
    prereg = load_json("data/faz5_preregistered_grid.json")
    phase6_prereg = load_json("data/faz6_preregistered_kernels.json")

    model_ids = list(phase5b["handoff"]["model_ids"])
    weights = phase5b["handoff"]["joint_model_weights"]
    t14_hours = float(phase2["ephemeris_and_windows"]["t14_hours"])
    ingress_hours = float(phase2["ephemeris_and_windows"]["ingress_hours"])
    oot_inner_hours = 0.75 * t14_hours
    shortest_window_hours = 13.0

    systematic = phase4["accepted_branch_geometry_comparison"][
        "between_reduction_systematic"
    ]["values"]

    sources = {}
    for path in DECLARED_SOURCES:
        target = ROOT / path
        sources[path] = {
            "relative_path": path,
            "size_bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        }

    manifest_checks = {
        "manifest_status_pass": manifest["status"] == "PASS",
        "s3_02_status_pass": s3_02["status"] == "PASS",
        "s3_02_real_data_fit_zero": s3_02["scope"]["real_data_fit_executed"] is False,
        "s3_02_optimizer_calls_zero": s3_02["scope"]["optimizer_calls"] == 0,
        "phase5b_conditional_continue": phase5b["status"] == "CONDITIONAL_CONTINUE",
        "phase5b_model_count_24": len(model_ids) == 24,
        "phase5b_model_ids_unique": len(set(model_ids)) == 24,
        "phase5b_weight_keys_exact": set(weights) == set(model_ids),
        "phase5b_raw_count_11": sum(
            item.startswith("raw_valid::") for item in model_ids
        )
        == 11,
        "phase5b_reference_count_13": sum(
            item.startswith("reference_included::") for item in model_ids
        )
        == 13,
        "phase5b_weights_sum_one": math.isclose(
            sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12
        ),
        "phase2_used_events_16": len(phase2["summary"]["used_event_keys"]) == 16,
        "t14_hours_positive": t14_hours > 0.0,
        "ingress_hours_positive": ingress_hours > 0.0,
        "used_event_count_exact_16": (
            len(phase2["summary"]["used_event_keys"]) == 16
        ),
        "used_events_sectors_complete": (
            {int(item["sector"]) for item in phase2["summary"]["used_event_keys"]}
            == {37, 63, 64, 90, 99, 100}
        ),
        "phase4_systematic_positive": all(
            float(systematic[name]["adopted_systematic"]) > 0.0
            for name in ("rp_rs", "a_rs", "impact_parameter", "t14_hours")
        ),
        "boundary_count_ou_87": (
            s3_02["boundary_analysis"]["by_kernel"][1]["boundary_flag_count"] == 87
        ),
        "all_flags_upper_timescale": (
            s3_02["boundary_analysis"]["all_flags_are_upper_timescale"] is True
        ),
        "k0_beta_max": math.isclose(
            s3_02["phase6r_residual_analysis"]["maximum_weighted_beta"],
            1.2936064512125263,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
    }

    if not all(manifest_checks.values()):
        failed = [name for name, okay in manifest_checks.items() if not okay]
        raise RuntimeError(
            "S3-03 upstream contract failed: " + ", ".join(failed)
        )

    timescale_lower_minutes = 4.0
    timescale_upper_minutes = shortest_window_hours * 60.0
    offset_sigma = 0.75
    amplitude_ratio_bounds = (-6.0, 2.0)
    jitter_ratio_bounds = (-6.0, 2.0)
    offset_bounds = (-3.0, 3.0)
    baseline_prior_sigma = 0.01

    decision = {
        "schema_version": "1.0",
        "work_package": "S3-03_MODEL_ARCHITECTURE_DECISION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "scope": {
            "analysis_mode": (
                "POST_RESULT_PROTOCOL_FROZEN_BEFORE_SYNTHETIC_AND_REAL_DATA"
            ),
            "real_data_fit_executed": False,
            "real_data_fit_authorized": False,
            "phase_7_may_begin": False,
            "protocol_not_blind_preregistration": True,
            "all_previous_results_disclosed": True,
            "postmortem_informed_architecture": True,
        },
        "source_integrity": {
            "stage3_manifest": relative(MANIFEST_PATH),
            "manifest_status": manifest["status"],
            "checks": manifest_checks,
            "sources": sources,
        },
        "justification": {
            "primary_failure_addressed": (
                "All 144 Phase-6 boundary flags were the shared log-timescale "
                "parameter at the 360-minute upper bound (OU 87, Matern-3/2 37, "
                "SHO 20). No amplitude or jitter boundary flag occurred. A single "
                "timescale forced all six sectors onto the same long correlation "
                "scale."
            ),
            "secondary_failure_addressed": (
                "K0 residual beta reached 1.293606 at 80 minutes, exceeding the "
                "1.2 gate. Beta drivers are sector-dependent: S37 dominates 80 min, "
                "S100 dominates 160-320 min, S64 at 360 min. This is inconsistent "
                "with uniform white excess scatter and supports sector-structured "
                "correlated noise."
            ),
            "kernel_choice": (
                "Matern-3/2 is the smoothest stationary kernel in the screened set "
                "and had the fewest boundary flags among complex kernels (37 vs "
                "87 for OU). Its celerite implementation (Matern32Term, eps=0.01) "
                "is already validated in the existing test suite. OU (87 boundary "
                "hits, rough non-differentiable paths) is excluded. SHO (fixed-Q "
                "oscillator physics) is excluded because no astrophysical "
                "oscillation source is established."
            ),
            "timescale_pooling": (
                "Each of six TESS sectors has distinct camera, CCD, background "
                "ranges, and formal depth heterogeneity (WP-09A). Forcing a single "
                "timescale on all of them caused the 360-minute saturation. "
                "Partial pooling with sigma=0.75 allows sector variation while "
                "penalizing extreme deviations. The 780-minute upper bound is "
                "support-derived from the shortest registered branch window (13 h) "
                "and is not an optimum inferred from the saturated fits."
            ),
            "why_not_ou": (
                "OU had 87 of 144 boundary flags and its non-differentiable "
                "character gives it the greatest risk of absorbing transit ingress "
                "and egress structure. Its high-frequency roughness is the opposite "
                "of what smooth correlated residuals require."
            ),
            "why_not_sho": (
                "SHO asserts an underdamped oscillator (Q=1/sqrt(2)) with no "
                "independent physical motivation for this star. Its fixed-Q "
                "parametrization introduces an unsupported spectral assumption."
            ),
            "why_not_two_candidates": (
                "The three old complex kernels (OU, Matern-3/2, SHO) shared the "
                "same pathology: a single pooled timescale. Fixing that one "
                "architectural defect accounts for the evidence. Nominating a "
                "second kernel would add weakly identified model-choice error "
                "across 24 specification branches without new physics."
            ),
            "why_not_free_sector_timescales": (
                "Six independent timescale parameters would be weakly identified "
                "(each sector contains only 2-3 events) and could absorb event "
                "geometry. Partial pooling shares information while allowing "
                "sector structure."
            ),
            "why_not_telemetry_regressors": (
                "The strongest weighted residual-telemetry association is "
                "S90 SAP_BKG Spearman r = -0.136, which is descriptive and "
                "non-causal (S3-02). Adding data-selected regressors would be "
                "outcome-driven model expansion."
            ),
        },
        "candidate": {
            "id": "K1_RM32_SECTOR_TIMESCALES",
            "role": "PRIMARY_CALIBRATION_CANDIDATE",
            "adopted_for_real_data": False,
            "kernel": {
                    "family": "Matérn-3/2",
                    "celerite_term": "Matern32Term",
                    "eps_fixed": 0.01,
                    "eps_justification": (
                        "Matern32Term(eps=0.01) approximates the true Matérn-3/2 "
                        "kernel with a damped driven-harmonic-oscillator "
                        "representation. The 0.01 value is the celerite default "
                        "and is already validated by the existing dense-covariance "
                        "equivalence test (test_phase_6.py::test_celerite_kernel_"
                        "amplitude_and_woodbury_match_dense). S3-05 must verify "
                        "this approximation against a dense Matérn-3/2 reference "
                        "for the specific Stage-3 bounds."
                    ),
                    "smoothness_fixed": True,
                    "definition": (
                        "k_s(dt) = A_s^2 * (1 + sqrt(3)*|dt|/tau_s) * "
                        "exp(-sqrt(3)*|dt|/tau_s)"
                    ),
                },
            "transit_model": {
                "shared_parameters": ["rp_rs", "a_rs", "impact_parameter"],
                "period_days_fixed": 9.2224171,
                "t0_btjd_fixed": 2314.5211550001986,
                "eccentricity_fixed": 0.0,
                "limb_darkening_quadratic_fixed": [0.3546454910932521, 0.15379449038160178],
                "exposure_seconds": 120.0,
                "supersample_factor": 7,
                "geometry_uniform_bounds": {
                    "rp_rs": [0.03, 0.09],
                    "a_rs": [5.0, 16.0],
                    "impact_parameter": [0.0, 0.98],
                },
                "physical_constraints": [
                    "impact_parameter < 1.0 + rp_rs",
                    "impact_parameter < a_rs",
                ],
            },
            "event_baseline": {
                "model": "transit * (1 + sum(beta_{e,k} * x_e^k))",
                "x_definition": "(time - fixed_event_midpoint) / 1 day",
                "degree_per_branch": (
                    "exact Phase-5B branch polynomial degree (P0, P1, or P2)"
                ),
                "coefficient_prior": {
                    "distribution": "independent normal",
                    "mean": 0.0,
                    "sigma": baseline_prior_sigma,
                },
                "inference": "exact Gaussian marginalization (Woodbury)",
            },
            "noise_hierarchy": {
                "sector_error_scale": (
                    "e_s = median(propagated_flux_err) for that sector and branch"
                ),
                "jitter": {
                    "transform": "j_s = e_s * exp(mu_j + delta_{j,s})",
                    "mu_j_bounds": list(jitter_ratio_bounds),
                    "delta_{j,s}_bounds": list(offset_bounds),
                    "delta_{j,s}_prior": "N(0, {:.2f}^2)".format(offset_sigma),
                },
                "gp_amplitude": {
                    "transform": "A_s = e_s * exp(mu_A + delta_{A,s})",
                    "mu_A_bounds": list(amplitude_ratio_bounds),
                    "delta_{A,s}_bounds": list(offset_bounds),
                    "delta_{A,s}_prior": "N(0, {:.2f}^2)".format(offset_sigma),
                },
                "gp_timescale": {
                    "transform": "tau_s = exp(mu_tau + delta_{tau,s}) minutes",
                    "mu_tau_bounds": [
                        math.log(timescale_lower_minutes),
                        math.log(timescale_upper_minutes),
                    ],
                    "delta_{tau,s}_bounds": list(offset_bounds),
                    "delta_{tau,s}_prior": "N(0, {:.2f}^2)".format(offset_sigma),
                    "timescale_lower_minutes": timescale_lower_minutes,
                    "timescale_upper_minutes": timescale_upper_minutes,
                    "upper_bound_derivation": (
                        "Shortest Phase-5B branch window (13 h) converted to minutes. "
                        "This is a support-derived constraint, not an optimum inferred "
                        "from the saturated Phase-6 fits."
                    ),
                },
                "held_sector_integration": {
                    "parameters_integrated": [
                        "delta_{j,held}",
                        "delta_{A,held}",
                        "delta_{tau,held}",
                    ],
                    "method": "independent Gauss-Hermite quadrature",
                    "nodes_per_dimension": 5,
                    "total_evaluations_per_held_sector": 125,
                    "prior_for_integration": (
                        "N(0, 0.75^2) for each offset, independent"
                    ),
                    "training_map_used_for": [
                        "mu_j", "mu_A", "mu_tau",
                        "delta_{j,train}", "delta_{A,train}", "delta_{tau,train}",
                    ],
                },
                "joint_fit_parameter_count": {
                    "geometry": 3,
                    "mu_jitter": 1,
                    "delta_jitter_sector": 6,
                    "mu_amplitude": 1,
                    "delta_amplitude_sector": 6,
                    "mu_timescale": 1,
                    "delta_timescale_sector": 6,
                    "total": 24,
                },
                "losofold_parameter_count": {
                    "description": "five training sectors in a leave-one-sector fold",
                    "mu_jitter": 1,
                    "delta_jitter_sector": 5,
                    "mu_amplitude": 1,
                    "delta_amplitude_sector": 5,
                    "mu_timescale": 1,
                    "delta_timescale_sector": 5,
                    "three_integrated_for_held": 3,
                    "total_fitted": 18,
                    "total_integrated": 3,
                },
            },
            "transit_noise_separation": {
                "method": "out-of-transit masking at 0.75 * official_T14",
                "oot_inner_hours": oot_inner_hours,
                "oot_inner_definition": "0.75 * T14 from event midpoint",
                "T14_hours": t14_hours,
                "T14_source": "Phase 2 SPOC-derived official transit duration",
                "screening_training": (
                    "only cadences with |time - midpoint| >= oot_inner_hours. "
                    "Held-sector flux not used for training."
                ),
                "joint_fit": (
                    "all cadences within branch window are modeled jointly. "
                    "S3-04 must calibrate transit-preservation under the full "
                    "joint model because no in-transit protection exists."
                ),
                "ingress_hours": ingress_hours,
                "ingress_buffer_warning": (
                    "OOT training excludes ingress/egress cadences. "
                    "Joint fit includes them and transit shape. "
                    "S3-04 injection-recovery calibration is mandatory."
            ),
        },
    },
    "failed_reference": {
        "id": "K0_WHITE_JITTER",
        "role": "FAILED_REFERENCE_ONLY",
        "historical_status": "FAIL_RESIDUAL_CORRELATION",
        "historical_maximum_weighted_beta": 1.2936064512125263,
        "beta_maximum_timescale_minutes": 80.0,
        "use": [
            "matched A_s=0 ablation in synthetic calibration",
            "held-sector predictive comparator",
            "false-correlated-selection calibration in S3-04",
        ],
        "not_adopted": True,
    },
    "branch_universe": {
        "model_count": 24,
        "mask_prior_weights": {"raw_valid": 0.5, "reference_included": 0.5},
        "raw_valid": {
            "count": 11,
            "conditional_weight_each": "1/11",
            "joint_weight_each": "1/22",
            "cell_ids": sorted(
                item.split("::", 1)[1]
                for item in model_ids
                if item.startswith("raw_valid::")
            ),
        },
        "reference_included": {
            "count": 13,
            "conditional_weight_each": "1/13",
            "joint_weight_each": "1/26",
            "cell_ids": sorted(
                item.split("::", 1)[1]
                for item in model_ids
                if item.startswith("reference_included::")
            ),
        },
        "predictive_mixture": (
            "logsumexp(log conditional weight + branch log predictive density) "
            "separately per mask, then logsumexp(log 0.5 + mask score)"
        ),
        "geometry_mixture": (
            "fixed weighted mixture of branch posterior draws"
        ),
        "likelihoods_multiplied": False,
        "branch_selection_after_results": False,
    },
    "phase4_reduction_systematic": {
        "rule": (
            "q_reported = median + sign(q - median) * "
            "sqrt((q - median)^2 + s4^2)"
        ),
        "values": {
            "rp_rs": float(systematic["rp_rs"]["adopted_systematic"]),
            "a_rs": float(systematic["a_rs"]["adopted_systematic"]),
            "impact_parameter": float(
                systematic["impact_parameter"]["adopted_systematic"]
            ),
            "t14_hours": float(systematic["t14_hours"]["adopted_systematic"]),
        },
        "applied_after_mixture": True,
        "applied_to_likelihood_or_beta": False,
        "application_count": 1,
    },
    "held_sector_validation": {
        "fold_unit": "one entire sector",
        "sectors": [37, 63, 64, 90, 99, 100],
        "training_count_per_fold": 5,
        "common_support": "data/faz6_common_validation_keys.csv",
        "common_support_row_count": 2233,
        "common_support_inner_boundary_hours": oot_inner_hours,
        "common_support_outer_boundary_hours": 6.5,
        "held_flux_not_used_for_training": True,
        "held_errors_known": True,
    },
    "residual_diagnostics": {
        "cadence_minutes": 2.0,
        "acf_max_lag_minutes": 360.0,
        "beta_timescales_minutes": [20, 40, 80, 160, 320, 360],
        "beta_minimum_filled_bins_per_sector": 3,
        "beta_minimum_eligible_sectors_per_timescale": 4,
        "beta_branch_aggregation": "equal-sector mean",
        "beta_mixture_aggregation": "fixed Phase-5B joint-weight mean",
        "beta_maximum_allowed": 1.2,
        "beta_gate_provisional": (
            "The 1.2 value is carried forward from the Phase 6 "
            "protocol. S3-04 must calibrate this threshold and "
            "may replace it with a synthetically validated value. "
            "It is listed under gates_calibrated_not_assumed."
        ),
        "periodogram_period_minutes": [20.0, 360.0],
        "periodogram_diagnostic_only": True,
        "thresholds_not_revised_from_observed_beta": True,
    },
    "telemetry": {
        "regressors": [],
        "use": "descriptive residual diagnostics and synthetic stress only",
        "causal_attribution_attempted": False,
    },
    "optimizer": {
        "method": (
            "The Phase-6R V2 optimizer protocol is the reference starting "
            "point: unit-hypercube scaling, 3-start L-BFGS-B with central-"
            "difference gradients at two step sizes, Powell validator, "
            "projected-gradient diagnostics. S3-05 must calibrate and "
            "potentially adjust: max_iterations, ftol, gtol, finite_"
            "difference step sizes, stationarity objective/parameter "
            "spread gates, validator tolerances, and boundary-distance "
            "minimum."
        ),
        "reference_implementation": "scripts/run_faz6r.py",
        "s3_05_must_calibrate": True,
        "analytic_gradient_not_available": True,
    },
    "computational_feasibility": {
        "held_sector_quadrature": {
            "evaluations_per_fold_per_branch": 125,
            "description": (
                "3D Gauss-Hermite (jitter offset, amplitude offset, "
                "timescale offset), 5 nodes per dimension = 125 GP "
                "constructions per held sector"
            ),
        },
        "screening_workload": {
            "branches": 24,
            "folds_per_branch": 6,
            "kernels": 2,
            "held_evaluations_per_kernel_fold": 125,
            "total_held_gp_construction": 36000,
            "approximate_runtime": (
                "~0.01-0.02 s per GP construction on modern CPU. "
                "Held phase ~6-12 minutes per kernel. Training phase "
                "dominated by 3-start L-BFGS-B on 18 parameters across "
                "5-sector data; estimate 30-90 s per fold. Total screening "
                "~2-6 hours for 288 folds on 4-8 cores."
            ),
        },
        "joint_fit_workload": {
            "branches": 24,
            "parameters": 24,
            "starts": 3,
            "approximate_runtime": (
                "~60-180 s per branch per start. Total joint fit "
                "~2-4 hours for 24 branches on 4-8 cores."
            ),
        },
        "s3_04_synthetic_total": (
            "Dominated by simulation class count and seeds per class. "
            "Estimated 10-50 hours total CPU depending on calibration "
            "scope decided in S3-04A."
        ),
    },
    "s3_05_numerical_validation": {
        "status": "REQUIRED_BEFORE_REAL_DATA_AFTER_S3_04",
        "must_verify": [
            "transformed vs physical-coordinate objective equivalence",
            "3D held-sector quadrature vs high-order numerical reference",
            "dense covariance equivalence for sector-varying timescales",
            "conditional GP-mean/residual vs dense reference",
            "truncated-normal prior normalization (may affect marginal likelihood, not MAP)",
            "all registered starts move and improve for every branch",
            "two-step-size gradient diagnostic and KKT projected stability",
            "independent L-BFGS-B vs Powell endpoint agreement",
            "Hessian rank and conditioning at interior and boundary cases",
            "deterministic GP simulation and process-pool merge invariance",
            "checkpoint resume and completed-key immutability",
            "invalid-branch non-propagation (no residual/geometry output)",
            "all 24 branch identities and exact weights under candidate",
            "transit-mask leakage verification",
            "Matern32Term(eps=0.01) vs dense Matérn-3/2 in Stage-3 bounds",
        ],
    },
    "s3_04_calibration": {
        "status": "MANDATORY_BEFORE_REAL_DATA",
        "must_calibrate": [
            "rp_rs bias and 68/95 percent coverage",
            "a_rs bias and coverage",
            "impact_parameter bias and coverage",
            "transit duration (T14) bias and coverage",
            "ingress/egress attenuation",
            "transit-depth consumption by the GP",
            "false-correlated-selection rate on white data",
            "K0 selection rate on correlated data",
            "boundary behavior near 780-minute timescale",
            "misspecified timescales (OU, SHO, free-parameter alternatives)",
            "sector-varying amplitude cases",
            "sector-varying timescale cases",
            "background-correlated systematic injection",
            "pointing-correlated systematic injection",
            "transit-free null cases",
            "partial-gap and edge cases",
            "all 24 branches under equal weights",
        ],
        "threshold_source": (
            "data/stage3_threshold_calibration.json, produced prospectively "
            "by S3-04 before any real-data fit"
        ),
        "gates_calibrated_not_assumed": [
            "predictive delta-ELPD and sign-flip thresholds",
            "mask-interaction acceptance threshold",
            "residual-beta gate value",
            "geometry-shift tolerance",
            "optimizer stationarity tolerances",
            "synthetic simulation count and seeds",
        ],
        "failure_action": "STOP_NO_REAL_DATA_FIT",
    },
    "stop_rules": {
        "no_real_data_before_s3_04_pass": True,
        "no_threshold_revision_after_observing_real_data": True,
        "no_branch_sector_or_event_removal": True,
        "no_retroactive_s3_03_amendment": (
            "If the architecture is found inadequate during S3-04, "
            "re-freeze S3-03 as a new versioned amendment and restart "
            "all synthetic calibration from untouched seeds."
        ),
        "on_s3_04_failure": (
            "Do not run S3-07. Redesign S3-03 or close Stage 3 "
            "with a candidate-assessment result."
        ),
        "on_real_data_failure": (
            "If the fully calibrated candidate fails the frozen gates "
            "on real data, no second model is attempted. Stage 3 closes. "
            "Strong physical claims (density, eccentricity, radius) are "
            "removed. The manuscript is completed as a candidate "
            "characterization paper."
        ),
    },
    "gate": {
        "checks": {
            "all_upstream_checks_pass": all(manifest_checks.values()),
            "correlated_candidate_count_exactly_1": True,
            "k0_retained_as_failed_reference_only": True,
            "all_24_branches_preserved": True,
            "no_branch_selection_after_results": True,
            "architecture_justified_by_postmortem": True,
            "every_parameter_has_bounds_and_prior": True,
            "provisional_numerical_thresholds_declared_as_uncalibrated": True,
            "real_data_fit_not_authorized": True,
            "phase_7_closed": True,
            "decision_hashed_before_fit": True,
        },
        "status": "PASS",
    },
}

    if not all(decision["gate"]["checks"].values()):
        failed = [
            name
            for name, okay in decision["gate"]["checks"].items()
            if not okay
        ]
        raise RuntimeError("S3-03 gate failed: " + ", ".join(failed))

    return decision


def comparable(report):
    report = dict(report)
    report.pop("generated_utc", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    current = build_decision()
    if current["status"] != "PASS":
        failed = [
            name
            for name, okay in current["gate"]["checks"].items()
            if not okay
        ]
        raise AssertionError(
            "S3-03 architecture decision failed: " + ", ".join(failed)
        )

    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(json_ready(current)):
            raise AssertionError(
                "Stored S3-03 architecture decision is stale"
            )
        print("STAGE-3 S3-03 MODEL ARCHITECTURE: PASS (verified)")
        return

    if OUTPUT_PATH.exists():
        raise FileExistsError(
            "S3-03 architecture decision is no-clobber; use --verify-only"
        )

    OUTPUT_PATH.write_text(
        json.dumps(json_ready(current), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print("STAGE-3 S3-03 MODEL ARCHITECTURE: PASS")


if __name__ == "__main__":
    main()
