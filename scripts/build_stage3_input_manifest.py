"""Build or verify the immutable Stage-3 scientific input manifest."""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "stage3_input_manifest.json"

INPUT_GROUPS = {
    "phase1_raw_inventory": (
        "outputs/faz1_product_inventory.json",
        "data/toi3492_cadence_ledger_120s.csv.gz",
        "data/toi3492_cadence_ledger_20s.csv.gz",
    ),
    "phase2_event_inventory": (
        "outputs/faz2_transit_inventory.json",
    ),
    "phase3_instrumental_audit": (
        "outputs/faz3_input_inventory.json",
        "outputs/faz3_quality_audit.json",
        "outputs/faz3_event_telemetry.csv",
    ),
    "phase4_reduction_family": (
        "outputs/faz4_reduction_comparison.json",
        "outputs/faz4_sector_depths.csv",
        "data/toi3492_faz4_reductions_120s.csv.gz",
    ),
    "phase5_window_baseline": (
        "data/faz5_preregistered_grid.json",
        "outputs/faz5_window_polynomial_grid.json",
        "outputs/faz5_model_grid.csv",
        "outputs/faz5_block_scores.csv",
        "data/toi3492_faz5_geometry_draws.npz",
    ),
    "phase5b_discrete_handoff": (
        "data/faz5b_preregistered_handoff.json",
        "outputs/faz5b_remediation.json",
        "outputs/faz5b_reference_included_grid.json",
        "outputs/faz5b_reference_included_model_grid.csv",
        "outputs/faz5b_reference_included_block_scores.csv",
        "outputs/faz5b_cadence_lineage.csv",
        "outputs/faz5b_fold_audit.csv",
        "outputs/faz5b_mask_comparison.csv",
        "data/toi3492_faz5b_handoff_draws.npz",
        "data/toi3492_faz5b_reference_included_geometry_draws.npz",
    ),
    "phase6_kernel_and_joint_audit": (
        "data/faz6_common_validation_keys.csv",
        "data/faz6_preregistered_kernels.json",
        "data/faz6_joint_diagnostics_protocol.json",
        "data/faz6_joint_diagnostics_protocol_v2.json",
        "outputs/faz6_loso_scores.csv",
        "outputs/faz6_loso_scores.meta.json",
        "outputs/faz6_kernel_sector_mixture.csv",
        "outputs/faz6_kernel_comparison.json",
        "outputs/faz6_k0_joint_fits.csv",
        "outputs/faz6_k0_joint_fits_v2.csv",
        "outputs/faz6_final_noise_model.json",
        "outputs/faz6_final_noise_model_v2.json",
        "outputs/faz6_gate_audit.json",
        "data/toi3492_faz6_k0_geometry_draws.npz",
        "data/toi3492_faz6_k0_geometry_draws_v2.npz",
    ),
    "phase6r_negative_result": (
        "scripts/run_faz6r.py",
        "outputs/faz6r_result.json",
        "outputs/faz6r_joint_fits.csv",
        "data/faz6r_geometry_draws.npz",
    ),
    "wp09a_formal_heterogeneity": (
        "data/wp09a_formal_sector_protocol.json",
        "outputs/wp09a_formal_sector_audit.json",
        "outputs/wp09a_sector_descriptors.csv",
        "scripts/run_wp09a_formal_sector_audit.py",
    ),
    "stage3_scope_and_environment": (
        "outputs/stage3_scope_audit.json",
        "scripts/audit_stage3_scope.py",
        "tests/test_stage3.py",
        "scripts/build_stage3_input_manifest.py",
        "tests/test_stage3_input_manifest.py",
        "provenance/environment.json",
        "requirements-lock.txt",
    ),
}


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def file_record(relative_path):
    path = ROOT / relative_path
    return {
        "path": relative_path,
        "size_bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def event_id(event):
    return "S{:03d}-E{:03d}".format(int(event["sector"]), int(event["epoch"]))


def build_manifest():
    phase1 = load_json("outputs/faz1_product_inventory.json")
    phase2 = load_json("outputs/faz2_transit_inventory.json")
    phase3 = load_json("outputs/faz3_quality_audit.json")
    phase4 = load_json("outputs/faz4_reduction_comparison.json")
    phase5 = load_json("outputs/faz5_window_polynomial_grid.json")
    phase5b = load_json("outputs/faz5b_remediation.json")
    phase6 = load_json("outputs/faz6_gate_audit.json")
    phase6r = load_json("outputs/faz6r_result.json")
    wp09a = load_json("outputs/wp09a_formal_sector_audit.json")
    scope = load_json("outputs/stage3_scope_audit.json")

    required_paths = [
        path for paths in INPUT_GROUPS.values() for path in paths
    ]
    missing = [path for path in required_paths if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError("Missing Stage-3 inputs: " + ", ".join(missing))

    model_ids = list(phase5b["handoff"]["model_ids"])
    weights = dict(phase5b["handoff"]["joint_model_weights"])
    used_events = list(phase2["summary"]["used_event_keys"])
    events = [
        {
            "event_id": event_id(event),
            "sector": int(event["sector"]),
            "epoch": int(event["epoch"]),
        }
        for event in used_events
    ]

    raw_models = [item for item in model_ids if item.startswith("raw_valid::")]
    reference_models = [
        item for item in model_ids if item.startswith("reference_included::")
    ]

    checks = {
        "all_required_inputs_present": not missing,
        "all_required_inputs_unique": len(required_paths) == len(set(required_paths)),
        "phase1_pass": phase1["gate_pass"] is True,
        "phase1_product_count_exact": phase1["counts"]["products"] == 18,
        "phase2_pass": phase2["gate_pass"] is True,
        "phase2_physical_event_count_exact": (
            phase2["summary"]["physical_event_count"] == 18
        ),
        "phase2_used_event_count_exact": len(events) == 16,
        "phase2_used_events_unique": (
            len({item["event_id"] for item in events}) == 16
        ),
        "phase3_pass": phase3["gate_status"] == "PASS",
        "phase4_conditional_pass": (
            phase4["gate_status"] == "CONDITIONAL_PASS"
            and phase4["gate"]["conditional_pass"] is True
        ),
        "phase4_all_four_reductions_retained": (
            phase4["gate"]["accepted_branches"]
            == ["pdcsap", "sap_cbv", "tpf_pipeline", "tpf_pld"]
        ),
        "phase5_failure_preserved": phase5["status"] == "FAIL",
        "phase5b_conditional_continue": (
            phase5b["status"] == "CONDITIONAL_CONTINUE"
            and phase5b["original_phase5_status"] == "FAIL"
        ),
        "phase5b_model_count_exact": len(model_ids) == 24,
        "phase5b_model_ids_unique": len(set(model_ids)) == 24,
        "phase5b_weight_keys_exact": set(weights) == set(model_ids),
        "phase5b_weights_positive": all(value > 0 for value in weights.values()),
        "phase5b_weights_sum_one": math.isclose(
            sum(weights.values()), 1.0, rel_tol=0.0, abs_tol=1e-12
        ),
        "phase5b_raw_model_count_exact": len(raw_models) == 11,
        "phase5b_reference_model_count_exact": len(reference_models) == 13,
        "phase5b_raw_weight_sum_half": math.isclose(
            sum(weights[item] for item in raw_models),
            0.5,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "phase5b_reference_weight_sum_half": math.isclose(
            sum(weights[item] for item in reference_models),
            0.5,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
        "phase5b_dependent_reductions_not_multiplied": (
            phase5b["handoff"]["dependent_reduction_likelihoods_multiplied"]
            is False
        ),
        "phase6_failure_preserved": phase6["status"] == "FAIL_STATIONARITY",
        "phase6_screening_rows_exact": phase6["screening"]["row_count"] == 576,
        "phase6_v1_invalid_preserved": (
            phase6["invalid_v1"]["status"] == "INVALID_NUMERICAL_RESULT"
        ),
        "phase6_v2_stationarity_count_preserved": (
            phase6["v2_joint"]["valid_stationary_branch_count"] == 22
        ),
        "phase6r_failure_preserved": (
            phase6r["status"] == "FAIL_RESIDUAL_CORRELATION"
        ),
        "phase6r_branch_universe_exact": (
            phase6r["branch_count"] == 24
            and phase6r["stationary_branch_count"] == 24
        ),
        "phase6r_beta_failed": (
            phase6r["maximum_weighted_beta"] > phase6r["thresholds"]["beta_max"]
        ),
        "phase6r_missing_protocol_acknowledged": (
            not (ROOT / "data" / "faz6r_numerical_remediation_protocol.json").exists()
        ),
        "wp09a_pass_preserved": wp09a["status"] == "PASS",
        "wp09a_cause_unassigned": (
            wp09a["adoption"] == "FORMAL_HETEROGENEITY_ONLY"
        ),
        "s3_00_scope_pass": scope["status"] == "PASS",
        "no_new_real_data_fit": scope["real_data_fit_executed"] is False,
        "phase7_closed": scope["phase_7_may_begin"] is False,
    }

    groups = {
        name: [file_record(path) for path in paths]
        for name, paths in INPUT_GROUPS.items()
    }

    return {
        "schema_version": "1.0",
        "work_package": "S3-01_IMMUTABLE_INPUT_MANIFEST",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "real_data_fit_executed": False,
        "phase_7_may_begin": False,
        "checks": checks,
        "event_universe": {
            "physical_event_count": phase2["summary"]["physical_event_count"],
            "used_event_count": len(events),
            "events": events,
            "gap_events": phase2["summary"]["gap_event_keys"],
        },
        "model_universe": {
            "model_count": len(model_ids),
            "raw_valid_count": len(raw_models),
            "reference_included_count": len(reference_models),
            "model_ids": model_ids,
            "joint_model_weights": weights,
            "mask_weight_sums": phase5b["handoff"]["mask_weight_sums"],
            "dependent_reduction_likelihoods_multiplied": False,
        },
        "preserved_results": {
            "phase1": "PASS",
            "phase2": "PASS",
            "phase3": "PASS",
            "phase4": "CONDITIONAL_PASS",
            "phase5": "FAIL",
            "phase5b": "CONDITIONAL_CONTINUE",
            "phase6": "FAIL_STATIONARITY",
            "phase6r": "FAIL_RESIDUAL_CORRELATION",
            "wp09a": "PASS_FORMAL_HETEROGENEITY_ONLY",
        },
        "known_provenance_limitations": [
            "The standalone Phase-6R preregistration JSON required by the Stage-2 plan is absent.",
            "Phase-6R is retained as a negative computational result, not represented as a complete preregistered package.",
            "The release manifest is stale and is not regenerated during scientific work packages."
        ],
        "input_groups": groups,
    }


def comparable(report):
    report = dict(report)
    report.pop("generated_utc", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    current = build_manifest()
    if current["status"] != "PASS":
        failed = [key for key, value in current["checks"].items() if not value]
        raise AssertionError("Stage-3 input manifest failed: " + ", ".join(failed))

    if args.verify_only:
        stored = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(current):
            raise AssertionError("Stored Stage-3 input manifest is stale")
        print("STAGE-3 S3-01 INPUT MANIFEST: PASS (verified)")
        return

    if OUTPUT.exists():
        raise FileExistsError(
            "Stage-3 input manifest is no-clobber; use --verify-only"
        )
    OUTPUT.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print("STAGE-3 S3-01 INPUT MANIFEST: PASS")


if __name__ == "__main__":
    main()
