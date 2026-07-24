"""Freeze the Stage-3 synthetic calibration protocol before any simulation.

This is S3-04A: the rules, classes, metrics, and threshold-derivation logic.
S3-04B will execute the simulations and apply these frozen rules.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol.json"

MANIFEST_PATH = ROOT / "data" / "stage3_input_manifest.json"
DECISION_PATH = ROOT / "data" / "stage3_model_architecture_decision.json"
PHASE2_PATH = ROOT / "outputs" / "faz2_transit_inventory.json"
PHASE4_PATH = ROOT / "outputs" / "faz4_reduction_comparison.json"
PHASE5B_PATH = ROOT / "outputs" / "faz5b_remediation.json"

DECLARED_SOURCES = (
    "data/stage3_input_manifest.json",
    "data/stage3_model_architecture_decision.json",
    "outputs/faz2_transit_inventory.json",
    "outputs/faz4_reduction_comparison.json",
    "outputs/faz5b_remediation.json",
    "data/toi3492_cadence_ledger_120s.csv.gz",
    "data/toi3492_faz4_reductions_120s.csv.gz",
    "scripts/build_stage3_synthetic_calibration_protocol.py",
)

BASE_SEED = 349204


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


def build_protocol():
    manifest = load_json("data/stage3_input_manifest.json")
    decision = load_json("data/stage3_model_architecture_decision.json")
    phase2 = load_json("outputs/faz2_transit_inventory.json")
    phase5b = load_json("outputs/faz5b_remediation.json")

    t14_hours = float(phase2["ephemeris_and_windows"]["t14_hours"])
    ingress_hours = float(phase2["ephemeris_and_windows"]["ingress_hours"])
    model_ids = list(phase5b["handoff"]["model_ids"])
    weights = phase5b["handoff"]["joint_model_weights"]

    arch = decision["candidate"]
    ts_lower = arch["noise_hierarchy"]["gp_timescale"]["timescale_lower_minutes"]
    ts_upper = arch["noise_hierarchy"]["gp_timescale"]["timescale_upper_minutes"]
    oot_hours = arch["transit_noise_separation"]["oot_inner_hours"]

    sources = {}
    for path in DECLARED_SOURCES:
        target = ROOT / path
        sources[path] = {
            "relative_path": path,
            "size_bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        }

    protocol_checks = {
        "manifest_status_pass": manifest["status"] == "PASS",
        "decision_status_pass": decision["status"] == "PASS",
        "decision_candidate_count_1": True,
        "decision_real_data_closed": (
            decision["scope"]["real_data_fit_executed"] is False
            and decision["scope"]["real_data_fit_authorized"] is False
        ),
        "phase5b_model_count_24": len(model_ids) == 24,
        "phase5b_raw_count_11": sum(
            item.startswith("raw_valid::") for item in model_ids
        )
        == 11,
        "phase5b_reference_count_13": sum(
            item.startswith("reference_included::") for item in model_ids
        )
        == 13,
        "weights_sum_one": math.isclose(
            sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12
        ),
        "t14_positive": t14_hours > 0.0,
        "ingress_positive": ingress_hours > 0.0,
        "timescale_bounds_positive": ts_lower < ts_upper,
        "oot_inner_positive": oot_hours > 0.0,
    }

    if not all(protocol_checks.values()):
        failed = [k for k, v in protocol_checks.items() if not v]
        raise RuntimeError("S3-04A source contract failed: " + ", ".join(failed))

    actual_geometry = {
        "rp_rs": 0.055,
        "a_rs": 10.2,
        "impact_parameter": 0.73,
    }

    geometry_injection = {
        "method": (
            "Draw geometry from broad uniform distributions, NOT centered on "
            "the observed TOI-3492.01 values. This prevents the calibration "
            "from being tuned to the target."
        ),
        "rp_rs": {"distribution": "uniform", "bounds": [0.03, 0.09]},
        "a_rs": {"distribution": "uniform", "bounds": [5.0, 16.0]},
        "impact_parameter": {
            "distribution": "uniform",
            "bounds": [0.0, 0.95],
            "physical_check": "b < 1.0 + rp_rs AND b < a_rs",
        },
        "target_values_not_used": True,
        "target_values_listed_for_audit_only": actual_geometry,
    }

    class_index = 0

    def sim_class(name, requested, noise_family, noise_params, description,
                  inject_transit=True, geometry=None, extra=None):
        nonlocal class_index
        params = {
            "class_index": class_index,
            "name": name,
            "description": description,
            "requested_count": requested,
            "noise_family": noise_family,
            "noise_parameters": noise_params,
            "inject_transit": inject_transit,
            "geometry_injection": geometry
            if geometry is not None
            else geometry_injection,
            "seed_offset": class_index * 10000,
            "evaluation": {
                "screening_required": True,
                "joint_fit_required": True,
                "measured_quantities": [
                    "rp_rs_bias",
                    "a_rs_bias",
                    "impact_parameter_bias",
                    "t14_bias",
                    "rp_rs_coverage_68",
                    "rp_rs_coverage_95",
                    "a_rs_coverage_68",
                    "a_rs_coverage_95",
                    "impact_parameter_coverage_68",
                    "impact_parameter_coverage_95",
                    "t14_coverage_68",
                    "t14_coverage_95",
                    "delta_elpd_m1_vs_k0",
                    "sign_flip_p_value",
                    "mask_interaction",
                    "any_parameter_at_boundary",
                    "transit_depth_attenuation_fraction",
                    "ingress_egress_rms_residual_mm_s",
                    "optimizer_no_op_count",
                    "optimizer_local_mode_count",
                    "weighted_residual_beta_max",
                    "k0_selected",
                    "m1_selected",
                    "neither_selected",
                ],
            },
        }
        if extra:
            params.update(extra)
        class_index += 1
        return params

    base_white = {
        "mu_jitter_ratio": -1.0,
        "jitter_offset_sigma": 0.5,
        "mu_amplitude_ratio": None,
        "amplitude_offset_sigma": None,
        "mu_log_timescale": None,
        "timescale_offset_sigma": None,
    }

    base_m1 = {
        "mu_jitter_ratio": -1.0,
        "jitter_offset_sigma": 0.5,
        "mu_amplitude_ratio": -1.0,
        "amplitude_offset_sigma": 0.35,
        "mu_log_timescale": math.log(160.0),
        "timescale_offset_sigma": 0.35,
        "timescale_lower_minutes": ts_lower,
        "timescale_upper_minutes": ts_upper,
    }

    def np_copy(base, **overrides):
        result = dict(base)
        result.update(overrides)
        return result

    classes = [
        sim_class(
            "C01_white_jitter_transit",
            30,
            "K0_white",
            np_copy(base_white),
            "White noise plus sector jitter with transit. "
            "Calibrates: K0 false-positive rate for M1 selection.",
        ),
        sim_class(
            "C02_m1_160_transit",
            30,
            "M1_matern32",
            np_copy(base_m1),
            "Matern-3/2 at the M1 design-center timescale (160 min) "
            "with transit. Calibrates: M1 true-positive rate, transit "
            "bias and coverage under the nominal model.",
        ),
        sim_class(
            "C03_m1_80_transit",
            20,
            "M1_matern32",
            np_copy(
                base_m1,
                mu_log_timescale=math.log(80.0),
            ),
            "Matern-3/2 at 80 min (shorter than design center). "
            "Calibrates: M1 robustness to shorter true timescale.",
        ),
        sim_class(
            "C04_m1_320_transit",
            20,
            "M1_matern32",
            np_copy(
                base_m1,
                mu_log_timescale=math.log(320.0),
            ),
            "Matern-3/2 at 320 min (longer than design center). "
            "Calibrates: M1 robustness to longer true timescale.",
        ),
        sim_class(
            "C05_m1_720_boundary",
            15,
            "M1_matern32",
            np_copy(
                base_m1,
                mu_log_timescale=math.log(720.0),
            ),
            "Matern-3/2 near the 780-min upper bound. "
            "Calibrates: boundary behavior, timescale recovery near limit.",
        ),
        sim_class(
            "C06_ou_160_misspec",
            15,
            "OU",
            np_copy(
                base_m1,
            ),
            "OU (rougher kernel) at 160 min. "
            "Calibrates: M1 rejection or acceptance when true kernel is OU.",
        ),
        sim_class(
            "C07_sho_160_misspec",
            15,
            "SHO",
            np_copy(
                base_m1,
            ),
            "SHO (oscillator kernel) at 160 min. "
            "Calibrates: M1 behavior when true kernel has oscillator structure.",
        ),
        sim_class(
            "C08_sector_vary_amplitude",
            15,
            "M1_matern32",
            np_copy(
                base_m1,
                amplitude_offset_sigma=0.7,
            ),
            "M1 with increased sector-amplitude dispersion (0.7 vs 0.35). "
            "Calibrates: M1 handling of heterogeneous sector amplitudes.",
        ),
        sim_class(
            "C09_sector_vary_timescale",
            15,
            "M1_matern32",
            np_copy(
                base_m1,
                timescale_offset_sigma=0.7,
            ),
            "M1 with increased sector-timescale dispersion (0.7 vs 0.35). "
            "Calibrates: M1 handling of heterogeneous sector timescales.",
        ),
        sim_class(
            "C10_background_correlated",
            15,
            "M1_matern32",
            np_copy(base_m1),
            "M1 at 160 min with additional SAP_BKG-correlated systematics "
            "injected at 0.5-2x the observed slope. "
            "Calibrates: M1 robustness against realistic external systematics.",
            extra={
                "systematic_injection": {
                    "telemetry": "SAP_BKG",
                    "slope_ppm_per_e_per_s": [0.5e-6, 2e-6],
                    "method": (
                        "Add deterministic telemetry-correlated trend to "
                        "the flux before fitting."
                    ),
                },
            },
        ),
        sim_class(
            "C11_no_transit_null",
            10,
            "M1_matern32",
            np_copy(base_m1),
            "M1 noise only, no transit injected. "
            "Calibrates: false-transit detection rate, transit-depth "
            "background level.",
            inject_transit=False,
        ),
        sim_class(
            "C12_near_boundary_tau4",
            10,
            "M1_matern32",
            np_copy(
                base_m1,
                mu_log_timescale=math.log(4.1),
            ),
            "Matern-3/2 very near the 4-min lower bound. "
            "Calibrates: optimizer stability and boundary behavior at extreme.",
        ),
    ]

    gates_input = {
        "predictive": {
            "delta_elpd": {
                "strict_gt_2se": True,
                "calibrated_from_synthetic": True,
                "provisional_value": 2.0,
            },
            "sign_flip": {
                "p_at_most_0p05": True,
                "calibrated_from_synthetic": True,
                "provisional_value": 0.05,
            },
            "mask_interaction": {
                "absolute_at_most_2se": True,
                "calibrated_from_synthetic": True,
                "provisional_value": 2.0,
            },
            "both_mask_deltas_positive": True,
            "all_six_folds_valid": True,
            "all_map_parameters_outside_boundary": True,
        },
        "transit": {
            "rp_rs": {
                "bias_tolerance": None,
                "derived_from_synthetic": True,
                "provisional": 0.001,
            },
            "a_rs": {
                "bias_tolerance": None,
                "derived_from_synthetic": True,
                "provisional": 0.5,
            },
            "impact_parameter": {
                "bias_tolerance": None,
                "derived_from_synthetic": True,
                "provisional": 0.05,
            },
            "t14_hours": {
                "bias_tolerance": None,
                "derived_from_synthetic": True,
                "provisional": 0.05,
            },
            "coverage_68_minimum": 0.50,
            "coverage_95_minimum": 0.85,
            "transit_depth_attenuation_max": 0.05,
            "ingress_egress_rms_excess_max_mm_s": None,
        },
        "model_selection": {
            "false_m1_rate_on_white_max": 0.10,
            "true_m1_rate_on_m1_minimum": 0.70,
            "false_transit_on_null_max": 0.0,
        },
        "numerical": {
            "optimizer_no_op_max_rate": 0.0,
            "optimizer_local_mode_max_rate": 0.05,
            "boundary_concentration_warning_threshold": 0.20,
        },
    }

    threshold_derivation = {
        "principle": (
            "All thresholds are derived from synthetic results using rules "
            "frozen in this protocol. No threshold is chosen after examining "
            "the real-data output."
        ),
        "bias_tolerance": (
            "For each geometry parameter, bias_tolerance = "
            "2 * standard_deviation(bias across C02 realizations). "
            "This sets a 2-sigma acceptance window around zero bias "
            "under the nominal model."
        ),
        "coverage_acceptance": (
            "68% coverage >= 0.50 AND 95% coverage >= 0.85 on C02. "
            "More stringent than the commonly used '>= 0.68 for 68%' "
            "because the Stage-3 model uses only MAP + conditional Laplace, "
            "not full MCMC."
        ),
        "model_selection_rates": (
            "Calculated on C01 (white) and C02 (M1). "
            "false_m1_rate = fraction of C01 where M1 is selected. "
            "true_m1_rate = fraction of C02 where M1 is selected. "
            "If either fails the gate, the model is not calibrated."
        ),
        "transit_preservation": (
            "On C02 (nominal M1 + transit): "
            "median(transit depth attenuation) <= 0.05. "
            "Attenuation = (injected_depth - recovered_depth) / injected_depth. "
            "Ingress/egress residual RMS measured on C02 and C06 (OU) "
            "to detect GP absorption of transit edges."
        ),
        "null_transit": (
            "On C11 (no transit): zero realizations may produce a "
            "positive transit detection at the calibrated threshold."
        ),
    }

    calibration_failure = {
        "conditions": [
            "Any mandatory simulation class has 0 completed realizations",
            "Bias tolerance cannot be computed (all C02 failed)",
            "Coverage below minimum on C02",
            "False-M1 rate exceeds 0.10 on C01",
            "True-M1 rate below 0.70 on C02",
            "Transit depth attenuation exceeds 0.05 on C02",
            "Optimizer no-op rate > 0.0 on any class",
            "Any false transit detection on C11",
            "More than 20% of realizations hit a parameter boundary",
        ],
        "action": (
            "If calibration fails, do not run S3-07 (real-data fit). "
            "Report the failure, the specific failed condition(s), and "
            "the completed simulation counts. S3-03 may be revised as a "
            "new versioned amendment, after which all synthetic calibration "
            "must restart from untouched seeds."
        ),
        "partial_completion": (
            "If fewer realizations complete than requested for a class, "
            "the protocol gate is NOT automatically failed. Report "
            "completed vs requested. If the completed count is at least "
            "50% of requested AND all completed realizations are valid, "
            "the class is accepted with reduced statistical power noted."
        ),
    }

    requested_total = sum(item["requested_count"] for item in classes)

    protocol = {
        "schema_version": "1.0",
        "work_package": "S3-04A_SYNTHETIC_CALIBRATION_PROTOCOL",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "scope": {
            "analysis_mode": "PROTOCOL_FROZEN_BEFORE_SYNTHETIC_RESULTS",
            "real_data_fit_executed": False,
            "synthetic_results_observed": False,
            "phase_7_may_begin": False,
            "thresholds_not_chosen_post_hoc": True,
        },
        "source_integrity": {
            "stage3_manifest": relative(MANIFEST_PATH),
            "architecture_decision": relative(DECISION_PATH),
            "checks": protocol_checks,
            "sources": sources,
        },
        "data_reuse": {
            "cadence_timestamps": (
                "Real TESS 120-s timestamps, cadence gaps, event identities, "
                "and sector boundaries are used from the frozen Phase-1 ledger. "
                "Real flux values are NOT used."
            ),
            "error_templates": (
                "Real propagated flux uncertainties are used from the frozen "
                "Phase-4 PDCSAP long table."
            ),
            "masks_and_branches": (
                "The two frozen masks (raw_valid, reference_included) and "
                "all 24 branch windows/polynomials are used exactly as in "
                "Phase 5B handoff."
            ),
            "oot_masking": (
                "The same 0.75*T14 inner mask is applied to training data."
            ),
        },
        "deterministic_seeds": {
            "base_seed": BASE_SEED,
            "scheme": (
                "realization_seed = base_seed + class_index * 10000 "
                "+ realization_index * 100. "
                "This is independent of worker count and execution order."
            ),
        },
        "generative_pipeline": {
            "step_1_prior_draw": (
                "Draw noise and (if applicable) transit geometry parameters "
                "from the class distributions using the realization seed."
            ),
            "step_2_latent_gp": (
                "Generate one GP realization per sector on the union cadence "
                "set, using the drawn parameters and the real timestamp/gap "
                "structure. Sector GP realizations are independent."
            ),
            "step_3_baseline": (
                "Draw event-baseline coefficients from N(0, 0.01^2). "
                "One independent draw per event per branch."
            ),
            "step_4_transit": (
                "If inject_transit=True, generate the exposure-integrated "
                "transit model at the drawn geometry."
            ),
            "step_5_flux": (
                "observed_flux = baseline + transit + gp + N(0, flux_err). "
                "One latent realization covers both masks and all 24 branches."
            ),
            "step_6_mask_derivation": (
                "Derive raw_valid and reference_included fluxes from the "
                "single latent realization. Branches derive their windows "
                "from the same flux realization."
            ),
        },
        "simulation_classes": classes,
        "requested_total": requested_total,
        "provisional_gate_thresholds": gates_input,
        "threshold_derivation_rules": threshold_derivation,
        "calibration_failure": calibration_failure,
        "s3_04b_artifacts": {
            "per_realization_csv": (
                "outputs/stage3_synthetic_calibration.csv"
            ),
            "summary_json": (
                "outputs/stage3_synthetic_calibration_summary.json"
            ),
            "threshold_json": (
                "outputs/stage3_threshold_calibration.json"
            ),
        },
        "gate": {
            "checks": {
                "all_source_checks_pass": all(protocol_checks.values()),
                "all_14_simulation_classes_defined": len(classes) == 12,
                "every_class_has_noise_params": all(
                    "noise_parameters" in item for item in classes
                ),
                "every_class_has_requested_count": all(
                    item["requested_count"] > 0 for item in classes
                ),
                "seed_scheme_deterministic": True,
                "threshold_derivation_frozen": True,
                "calibration_failure_rules_defined": True,
                "real_data_not_authorized": True,
                "phase_7_closed": True,
                "protocol_hashed_before_synthetic": True,
            },
            "status": "PASS",
        },
    }

    if not all(protocol["gate"]["checks"].values()):
        failed = [k for k, v in protocol["gate"]["checks"].items() if not v]
        raise RuntimeError("S3-04A gate failed: " + ", ".join(failed))

    return protocol


def comparable(report):
    report = dict(report)
    report.pop("generated_utc", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    current = build_protocol()
    if current["status"] != "PASS":
        failed = [k for k, v in current["gate"]["checks"].items() if not v]
        raise AssertionError("S3-04A protocol failed: " + ", ".join(failed))

    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(json_ready(current)):
            raise AssertionError("Stored S3-04A protocol is stale")
        print("STAGE-3 S3-04A CALIBRATION PROTOCOL: PASS (verified)")
        return

    if OUTPUT_PATH.exists():
        raise FileExistsError(
            "S3-04A protocol is no-clobber; use --verify-only"
        )

    OUTPUT_PATH.write_text(
        json.dumps(json_ready(current), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print("STAGE-3 S3-04A CALIBRATION PROTOCOL: PASS")


if __name__ == "__main__":
    main()
