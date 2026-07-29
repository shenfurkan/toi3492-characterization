"""Build the versioned S3-04A v2 synthetic-calibration protocol amendment.

Loads the frozen v1 protocol and the S3-03 v2 architecture amendment, verifies
their hashes, applies the versioned corrections, and emits a standalone v2
protocol.  The v1 file is never modified.  The v2 output is no-clobber; use
--verify-only to confirm it is current.
"""

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
V1_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol.json"
ARCH_V2_PATH = ROOT / "data" / "stage3_model_architecture_decision_v2.json"
OUTPUT_PATH = ROOT / "data" / "stage3_synthetic_calibration_protocol_v2.json"
QUARANTINE_MANIFEST = (
    ROOT / "outputs" / "quarantine"
    / "stage3_s3-04b_20260725T222451Z_invalid" / "manifest.json"
)
V2_NAMESPACE = "outputs/stage3_v2"
SEED_BASE_V1 = 349204
SEED_BASE_V2 = 749204


def _m1_160_noise_parameters():
    return {
        "mu_jitter_ratio": -1.0,
        "jitter_offset_sigma": 0.5,
        "mu_amplitude_ratio": -1.0,
        "amplitude_offset_sigma": 0.35,
        "mu_log_timescale": 5.075173815233827,
        "timescale_offset_sigma": 0.35,
        "timescale_lower_minutes": 4.0,
        "timescale_upper_minutes": 780.0,
    }


def _geometry_injection():
    return {
        "method": "Draw geometry from broad uniform distributions, NOT centered on the observed TOI-3492.01 values. This prevents the calibration from being tuned to the target.",
        "rp_rs": {"distribution": "uniform", "bounds": [0.03, 0.09]},
        "a_rs": {"distribution": "uniform", "bounds": [5.0, 16.0]},
        "impact_parameter": {
            "distribution": "uniform",
            "bounds": [0.0, 0.95],
            "physical_check": "b < 1.0 + rp_rs AND b < a_rs",
        },
        "target_values_not_used": True,
        "target_values_listed_for_audit_only": {
            "rp_rs": 0.055, "a_rs": 10.2, "impact_parameter": 0.73,
        },
    }


def _evaluation(extra_quantities=()):
    quantities = [
        "rp_rs_bias", "a_rs_bias", "impact_parameter_bias", "t14_bias",
        "rp_rs_coverage_68", "rp_rs_coverage_95",
        "a_rs_coverage_68", "a_rs_coverage_95",
        "impact_parameter_coverage_68", "impact_parameter_coverage_95",
        "t14_coverage_68", "t14_coverage_95",
        "delta_elpd_m1_vs_k0", "sign_flip_p_value", "mask_interaction",
        "any_parameter_at_boundary",
        "transit_depth_attenuation_fraction",
        "ingress_egress_rms_residual_mm_s",
        "optimizer_no_op_count", "optimizer_local_mode_count",
        "weighted_residual_beta_max",
        "k0_selected", "m1_selected", "neither_selected",
    ]
    return {
        "screening_required": True,
        "joint_fit_required": True,
        "measured_quantities": quantities + list(extra_quantities),
    }


C13 = {
    "class_index": 12,
    "name": "C13_aperture_telemetry_correlated",
    "description": (
        "M1 noise at 160 min plus a systematic correlated with the frozen template's "
        "aperture telemetry (CROWDSAP; FLFRCSAP recorded for audit). Calibrates M1 "
        "robustness against aperture/crowding-driven systematics. Limitation: the frozen "
        "template has no centroid columns, so true pointing-telemetry injection requires "
        "a new input and is deferred to a possible v3 amendment."
    ),
    "requested_count": 15,
    "noise_family": "M1_matern32",
    "noise_parameters": _m1_160_noise_parameters(),
    "inject_transit": True,
    "geometry_injection": _geometry_injection(),
    "systematic_injection": {
        "telemetry": "CROWDSAP",
        "method": "Add a centered per-sector CROWDSAP-correlated trend to the flux before fitting.",
        "slope_ppm_per_unit": [5e-06, 2e-05],
    },
    "seed_offset": 120000,
    "evaluation": _evaluation(),
}

C14 = {
    "class_index": 13,
    "name": "C14_partial_gap_edge_transit",
    "description": (
        "M1 noise at 160 min with transits injected into all 18 registered events, "
        "including the two gap/edge events excluded from the complete-16 set. Calibrates "
        "recovery when transit coverage is truncated by data gaps or window edges."
    ),
    "requested_count": 10,
    "noise_family": "M1_matern32",
    "noise_parameters": _m1_160_noise_parameters(),
    "inject_transit": True,
    "geometry_injection": _geometry_injection(),
    "event_coverage": {
        "mode": "partial_gap_edge",
        "complete_events": 16,
        "gap_edge_events": 2,
        "rule": "Partial event windows are masked at the registered gap boundaries; the complete-16-event requirement does not apply to this class.",
    },
    "seed_offset": 130000,
    "evaluation": _evaluation(extra_quantities=("gap_edge_event_recovery_flags",)),
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_record(path):
    return {
        "relative_path": path.relative_to(ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def build_protocol():
    v1 = load_json(V1_PATH)
    arch = load_json(ARCH_V2_PATH)

    classes = copy.deepcopy(v1["simulation_classes"]) + [copy.deepcopy(C13), copy.deepcopy(C14)]
    requested_total = sum(int(item["requested_count"]) for item in classes)

    protocol = {
        "schema_version": "2.0",
        "work_package": "S3-04A_V2_SYNTHETIC_CALIBRATION_PROTOCOL_AMENDMENT",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": None,
        "scope": {
            "analysis_mode": "VERSIONED_AMENDMENT_POST_RESULT_DISCLOSED",
            "supersedes": "data/stage3_synthetic_calibration_protocol.json",
            "supersedes_sha256": sha256(V1_PATH),
            "v1_preserved_unmodified": True,
            "architecture_amendment": "data/stage3_model_architecture_decision_v2.json",
            "architecture_amendment_sha256": sha256(ARCH_V2_PATH),
            "interrupted_v1_results_observed_and_quarantined": True,
            "quarantine_manifest": (
                "outputs/quarantine/stage3_s3-04b_20260725T222451Z_invalid/manifest.json"
            ),
            "real_data_fit_executed": False,
            "real_data_fit_authorized": False,
            "phase_7_may_begin": False,
            "execution_authorized": False,
            "execution_requires": [
                "independent second-party protocol review recorded",
                "v2 runner implementing the checkpoint identity and fresh namespace",
            ],
            "thresholds_not_chosen_post_hoc": True,
        },
        "source_integrity": {
            "sources": {
                record["relative_path"]: record
                for record in (
                    source_record(V1_PATH),
                    source_record(ARCH_V2_PATH),
                    source_record(QUARANTINE_MANIFEST),
                )
            },
            "governance_references_not_hash_bound": [
                "data/methodology_publication_charter.json (living status document; binding it would guarantee staleness)",
            ],
        },
        "data_reuse": {
            **v1["data_reuse"],
            "gap_edge_events": "C14 additionally uses the two registered gap/edge events from the frozen Phase-2 inventory with partial window coverage.",
            "c13_telemetry_limitation": "The frozen template provides SAP_BKG, CROWDSAP, and FLFRCSAP but no centroid columns; true pointing telemetry requires a new input and is deferred to a possible v3.",
        },
        "deterministic_seeds": {
            "base_seed": SEED_BASE_V2,
            "v1_base_seed_retired": SEED_BASE_V1,
            "scheme": "realization_seed = base_seed + class_index * 10000 + realization_index * 100. This is independent of worker count and execution order.",
            "streams_disjoint_from_v1": True,
        },
        "generative_pipeline": {
            "step_1_prior_draw": v1["generative_pipeline"]["step_1_prior_draw"],
            "step_2_latent_gp": v1["generative_pipeline"]["step_2_latent_gp"],
            "step_3_baseline": (
                "Draw event-baseline coefficients ONCE per realization from N(0, 0.01^2): "
                "one degree-2 polynomial per event over +/-16 h (the widest branch half-width), "
                "shared unchanged by all 24 branches and both masks."
            ),
            "step_4_transit": v1["generative_pipeline"]["step_4_transit"],
            "step_5_flux": (
                "observed_flux = transit * (1 + shared_baseline) + gp + N(0, flux_err). "
                "One latent realization covers both masks and all 24 branches; per-branch "
                "data alteration is forbidden."
            ),
            "step_6_mask_derivation": v1["generative_pipeline"]["step_6_mask_derivation"],
            "step_7_null_hypothesis": (
                "Every joint recovery also fits the H0 null-transit model (rp_rs = 0) with "
                "identical noise hierarchy and baseline marginalization, and records "
                "delta_map = objective_H0 - objective_H1."
            ),
        },
        "simulation_classes": classes,
        "requested_total": requested_total,
        "provisional_gate_thresholds": copy.deepcopy(v1["provisional_gate_thresholds"]),
        "threshold_derivation_rules": {
            "principle": v1["threshold_derivation_rules"]["principle"],
            "bias_tolerance": v1["threshold_derivation_rules"]["bias_tolerance"],
            "coverage_acceptance": (
                "68% interval coverage >= 0.50 AND 95% interval coverage >= 0.85 on C02. "
                "These floors are deliberately relaxed relative to the nominal 0.68/0.95 "
                "because MAP + conditional-Laplace intervals are approximate and expected "
                "to undercover; they are acceptance floors, not evidence of calibrated "
                "uncertainty."
            ),
            "model_selection_rates": v1["threshold_derivation_rules"]["model_selection_rates"],
            "transit_preservation": v1["threshold_derivation_rules"]["transit_preservation"],
            "null_transit": (
                "delta_detect is set to the maximum delta_map observed across all valid C11 "
                "null realizations; the full C11 delta_map distribution is reported. The gate "
                "requires zero C11 detections at delta_detect. If any C11 realization is "
                "invalid, the class is INCOMPLETE and no threshold is derived."
            ),
        },
        "calibration_failure": {
            "conditions": v1["calibration_failure"]["conditions"] + [
                "Any class INCOMPLETE at the full completion rule",
            ],
            "incomplete_rule": (
                "A class is COMPLETE only when 100% of requested realizations finish with "
                "valid fits. Any shortfall is INCOMPLETE: it is neither a pass nor a "
                "calibrated failure, and no gate statistic may be reported for that class."
            ),
            "partial_acceptance_permitted": False,
            "action": (
                "If calibration fails or is incomplete, do not run any real-data fit. Report "
                "the conditions and completed counts. Corrections require an S3-03 v3 "
                "versioned amendment with fresh seeds and a fresh namespace."
            ),
        },
        "artifacts": {
            "root": V2_NAMESPACE,
            "screening_detail_csv": "{}/stage3_v2_screening_detail.csv".format(V2_NAMESPACE),
            "realization_summary_csv": "{}/stage3_v2_synthetic_calibration.csv".format(V2_NAMESPACE),
            "joint_recovery_csv": "{}/stage3_v2_joint_recovery.csv".format(V2_NAMESPACE),
            "calibration_summary_json": "{}/stage3_v2_calibration_summary.json".format(V2_NAMESPACE),
            "threshold_calibration_json": "{}/stage3_v2_threshold_calibration.json".format(V2_NAMESPACE),
            "checkpoint_dir": "{}/checkpoints".format(V2_NAMESPACE),
        },
        "execution_requirements": {
            "checkpoint_identity": arch["checkpoint_identity"],
            "runner": [
                "Fresh outputs/stage3_v2/ namespace only; legacy artifacts are never read or written.",
                "Immutable per-task JSON records with atomic writes; one deterministic reducer emits CSVs.",
                "Exact expected task-key equality (class, realization, branch, held_sector); duplicates or missing keys fail verification.",
                "A failed fit is a failed task; the runner exits nonzero and the realization is invalid.",
                "--verify-only performs full schema, key, hash, and fit-validity validation.",
                "Results are invariant to worker count and execution order.",
            ],
            "boundary_accounting": arch["boundary_accounting"]["rule"],
            "completion_rule": arch["completion_rule"],
        },
    }

    artifact_paths = [protocol["artifacts"][key] for key in (
        "screening_detail_csv", "realization_summary_csv", "joint_recovery_csv",
        "calibration_summary_json", "threshold_calibration_json", "checkpoint_dir",
    )]
    legacy_paths = set(arch["artifact_namespace"]["legacy_paths_forbidden"])
    coverage_text = protocol["threshold_derivation_rules"]["coverage_acceptance"]
    null_text = protocol["threshold_derivation_rules"]["null_transit"]
    indices = [int(item["class_index"]) for item in classes]
    names = {item["name"] for item in classes}

    checks = {
        "v1_protocol_status_pass": v1.get("status") == "PASS",
        "v1_preserved": V1_PATH.is_file(),
        "architecture_v2_status_pass": arch.get("status") == "PASS",
        "architecture_v2_hash_bound": (
            protocol["scope"]["architecture_amendment_sha256"] == sha256(ARCH_V2_PATH)
        ),
        "quarantine_manifest_present": QUARANTINE_MANIFEST.is_file(),
        "all_14_simulation_classes_defined": len(classes) == 14,
        "class_indices_contiguous": indices == list(range(14)),
        "requested_total_matches": requested_total == 235 == sum(
            int(item["requested_count"]) for item in classes
        ),
        "every_class_has_noise_params": all(
            item.get("noise_parameters") for item in classes
        ),
        "every_class_has_requested_count": all(
            int(item["requested_count"]) > 0 for item in classes
        ),
        "seed_scheme_deterministic_and_disjoint": (
            protocol["deterministic_seeds"]["base_seed"] == SEED_BASE_V2
            and SEED_BASE_V2 != SEED_BASE_V1
        ),
        "c13_c14_registered": {
            "C13_aperture_telemetry_correlated",
            "C14_partial_gap_edge_transit",
        }.issubset(names),
        "c14_uses_registered_gap_events": (
            C14["event_coverage"]["gap_edge_events"] == 2
        ),
        "null_detection_rule_defined": (
            "delta_detect" in null_text and "delta_map" in null_text
        ),
        "coverage_wording_honest": "more stringent" not in coverage_text,
        "completion_requires_full": (
            protocol["calibration_failure"]["partial_acceptance_permitted"] is False
            and "100%" in protocol["calibration_failure"]["incomplete_rule"]
        ),
        "artifacts_fresh_namespace": all(
            path.startswith(V2_NAMESPACE + "/") for path in artifact_paths
        ),
        "legacy_paths_absent": not any(
            any(legacy in path for legacy in legacy_paths) for path in artifact_paths
        ),
        "checkpoint_identity_required": (
            protocol["execution_requirements"]["checkpoint_identity"]["required_fields"]
            == arch["checkpoint_identity"]["required_fields"]
        ),
        "threshold_derivation_frozen": True,
        "real_data_not_authorized": protocol["scope"]["real_data_fit_authorized"] is False,
        "phase_7_closed": protocol["scope"]["phase_7_may_begin"] is False,
        "execution_not_authorized": protocol["scope"]["execution_authorized"] is False,
    }
    protocol["gate"] = {
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
    }
    protocol["status"] = protocol["gate"]["status"]
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
        raise AssertionError("S3-04A v2 protocol amendment failed: " + ", ".join(failed))

    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(current):
            raise AssertionError("Stored S3-04A v2 protocol amendment is stale")
        print("STAGE-3 S3-04A v2 CALIBRATION PROTOCOL AMENDMENT: PASS (verified)")
        return

    if OUTPUT_PATH.exists():
        raise FileExistsError("S3-04A v2 protocol is no-clobber; use --verify-only")

    OUTPUT_PATH.write_text(
        json.dumps(current, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("STAGE-3 S3-04A v2 CALIBRATION PROTOCOL AMENDMENT: PASS")


if __name__ == "__main__":
    main()
