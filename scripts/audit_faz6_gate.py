"""Produce the authoritative Phase-6 gate from frozen screening and joint attempts."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SCREEN_PATH = ROOT / "outputs" / "faz6_kernel_comparison.json"
V1_PROTOCOL_PATH = ROOT / "data" / "faz6_joint_diagnostics_protocol.json"
V1_REPORT_PATH = ROOT / "outputs" / "faz6_final_noise_model.json"
V1_FITS_PATH = ROOT / "outputs" / "faz6_k0_joint_fits.csv"
V2_PROTOCOL_PATH = ROOT / "data" / "faz6_joint_diagnostics_protocol_v2.json"
V2_REPORT_PATH = ROOT / "outputs" / "faz6_final_noise_model_v2.json"
V2_FITS_PATH = ROOT / "outputs" / "faz6_k0_joint_fits_v2.csv"
OUTPUT_PATH = ROOT / "outputs" / "faz6_gate_audit.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def bool_series(series):
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    return series.astype(str).str.lower().eq("true")


def source_record(path):
    return {
        "relative_path": relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_v2_protocol_sources(protocol):
    checks = {}
    for name, item in protocol["inputs"].items():
        path = ROOT / item["relative_path"]
        checks[name] = path.is_file() and sha256_file(path) == item["sha256"]
    return checks


def attempt_is_noop(attempt):
    return np.array_equal(
        np.asarray(attempt["initial"], dtype=float),
        np.asarray(attempt["final"], dtype=float),
    )


def build_audit():
    screening = load_json(SCREEN_PATH)
    v1_protocol = load_json(V1_PROTOCOL_PATH)
    v1_report = load_json(V1_REPORT_PATH)
    v1_fits = pd.read_csv(V1_FITS_PATH)
    v2_protocol = load_json(V2_PROTOCOL_PATH)
    v2_report = load_json(V2_REPORT_PATH)
    v2_fits = pd.read_csv(V2_FITS_PATH)
    source_checks = verify_v2_protocol_sources(v2_protocol)

    v1_attempts = [
        attempt
        for value in v1_fits["optimizer_attempts_json"]
        for attempt in json.loads(value)
    ]
    v1_all_noop = len(v1_attempts) == 72 and all(
        attempt_is_noop(attempt) for attempt in v1_attempts
    )
    v2_valid = bool_series(v2_fits["valid"])
    failed_ids = sorted(v2_fits.loc[~v2_valid, "model_id"].astype(str))
    expected_failed = ["raw_valid::W20_P0", "reference_included::W32_P2"]
    stationarity_checks = {
        "all_24_rows_present": len(v2_fits) == 24,
        "all_objectives_improved": bool((v2_fits["objective_improvement"] > 0).all()),
        "all_parameters_moved": bool((v2_fits["parameter_movement_norm"] > 0).all()),
        "all_objective_spreads_below_1e3": bool(
            (v2_fits["multistart_objective_spread"] < 1e-3).all()
        ),
        "all_unit_parameter_spreads_below_1e3": bool(
            (v2_fits["multistart_unit_parameter_spread"] < 1e-3).all()
        ),
        "all_24_stationarity_valid": bool(v2_valid.all()),
        "failed_branch_set_exact": failed_ids == expected_failed,
    }
    checks = {
        "v2_protocol_sources_match": all(source_checks.values()),
        "screening_complete": screening["screening"]["completed_score_rows"] == 576,
        "screening_invalid_rows_zero": screening["screening"]["invalid_score_rows"] == 0,
        "screening_complex_candidate_count_zero": len(
            screening["screening"]["predictive_candidates_pending_joint_diagnostics"]
        )
        == 0,
        "v1_all_optimizer_attempts_noop": v1_all_noop,
        "v1_report_not_adopted": v1_protocol["phase"] == "6-joint-diagnostics",
        "v2_report_phase7_closed": v2_report["gate"]["phase7_may_begin"] is False,
        "v2_stationarity_failure_present": not stationarity_checks[
            "all_24_stationarity_valid"
        ],
        "v2_beta_not_computed": v2_report["residual_diagnostics"][
            "weighted_max_beta"
        ]
        is None,
    }
    if not all(checks.values()):
        raise RuntimeError("Phase-6 gate audit contract failed: {}".format(checks))
    return {
        "phase": "6-authoritative-gate-audit",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL_STATIONARITY",
        "screening": {
            "row_count": 576,
            "invalid_row_count": 0,
            "complex_kernel_candidate_count": 0,
            "screening_report_modified": False,
        },
        "invalid_v1": {
            "status": "INVALID_NUMERICAL_RESULT",
            "optimizer_attempt_count": len(v1_attempts),
            "all_attempts_unchanged_from_initial": v1_all_noop,
            "beta_and_geometry_must_not_be_used": True,
        },
        "v2_joint": {
            "row_count": len(v2_fits),
            "valid_stationary_branch_count": int(v2_valid.sum()),
            "failed_stationarity_branch_ids": failed_ids,
            "stationarity_checks": stationarity_checks,
            "beta_computed": False,
        },
        "gate": {
            "checks": checks,
            "status": "FAIL_STATIONARITY",
            "phase6_pass": False,
            "phase7_may_begin": False,
            "required_next_action": "Freeze a separate numerical remediation before any further joint fit; do not relax the v2 gate retrospectively.",
        },
        "sources": {
            "screening_report": source_record(SCREEN_PATH),
            "v1_protocol": source_record(V1_PROTOCOL_PATH),
            "v1_report": source_record(V1_REPORT_PATH),
            "v1_fits": source_record(V1_FITS_PATH),
            "v2_protocol": source_record(V2_PROTOCOL_PATH),
            "v2_report": source_record(V2_REPORT_PATH),
            "v2_fits": source_record(V2_FITS_PATH),
        },
    }


def verify_existing():
    stored = load_json(OUTPUT_PATH)
    rebuilt = build_audit()
    for key in ("status", "screening", "invalid_v1", "v2_joint", "gate", "sources"):
        if stored[key] != rebuilt[key]:
            raise RuntimeError("Stored Phase-6 gate audit differs in {}".format(key))
    print("Verified {}: FAIL_STATIONARITY".format(relative(OUTPUT_PATH)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if not OUTPUT_PATH.is_file():
            raise FileNotFoundError(OUTPUT_PATH)
        verify_existing()
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError("Phase-6 gate audit is no-clobber; use --verify-only")
    payload = build_audit()
    temporary = OUTPUT_PATH.with_name(OUTPUT_PATH.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    temporary.replace(OUTPUT_PATH)
    print("Wrote {}: FAIL_STATIONARITY".format(relative(OUTPUT_PATH)))


if __name__ == "__main__":
    main()
