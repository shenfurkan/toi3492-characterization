"""Verify the Stage-3 scope synchronization without running scientific fits."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "outputs" / "stage3_scope_audit.json"

SOURCE_PATHS = (
    "currentproblem.md",
    "currentproblemstage2.md",
    "stage3.md",
    "toi3492_characterization.tex",
    "outputs/release_status.json",
    "outputs/faz6_gate_audit.json",
    "outputs/faz6r_result.json",
    "outputs/wp09a_formal_sector_audit.json",
    "EXOPLANET_RELEASE_ROADMAP.md",
)


def load_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def sha256(relative_path):
    return hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()


def build_audit():
    release = load_json("outputs/release_status.json")
    phase6 = load_json("outputs/faz6_gate_audit.json")
    phase6r = load_json("outputs/faz6r_result.json")
    wp09a = load_json("outputs/wp09a_formal_sector_audit.json")
    stage3 = (ROOT / "stage3.md").read_text(encoding="utf-8")
    manuscript = (ROOT / "toi3492_characterization.tex").read_text(
        encoding="utf-8"
    )

    stage3_status = release["stage3_scope_amendment"]
    phase6r_status = release["phase_6r_numerical_remediation"]
    wp09a_status = release["wp09a_formal_sector_heterogeneity"]

    checks = {
        "all_sources_exist": all((ROOT / path).is_file() for path in SOURCE_PATHS),
        "release_schema_is_stage3": release["schema_version"] == "1.1",
        "stage3_document_protocol_only": "Belge durumu: `PROTOCOL_ONLY`" in stage3,
        "stage3_document_real_data_closed": (
            "Gercek-veri calisma yetkisi: `CLOSED`" in stage3
            or "Gerçek-veri çalışma yetkisi: `CLOSED`" in stage3
        ),
        "stage3_scope_approved": stage3_status["approved"] is True,
        "stage3_scope_protocol_only": stage3_status["status"] == "PROTOCOL_ONLY",
        "stage3_real_data_not_authorized": (
            stage3_status["real_data_fit_authorized"] is False
        ),
        "stage3_phase7_closed": stage3_status["phase_7_may_begin"] is False,
        "stage3_model_family_bounded": (
            stage3_status["new_model_candidates_maximum"] == 2
        ),
        "stage3_synthetic_calibration_required": (
            stage3_status["synthetic_calibration_required"] is True
        ),
        "stage3_second_approval_required": (
            stage3_status["second_protocol_approval_required_before_real_data"]
            is True
        ),
        "phase6_original_failure_preserved": (
            release["phase_6_noise_model_audit"]["gate_status"]
            == "FAIL_STATIONARITY"
            and phase6["status"] == "FAIL_STATIONARITY"
        ),
        "phase6r_completed": phase6r_status["completed"] is True,
        "phase6r_real_data_recorded": phase6r_status["real_data_executed"] is True,
        "phase6r_failure_preserved": (
            phase6r_status["status"] == "FAIL_RESIDUAL_CORRELATION"
            and phase6r["status"] == "FAIL_RESIDUAL_CORRELATION"
        ),
        "phase6r_stationarity_exact": (
            phase6r_status["stationary_branches_valid"] == 24
            and phase6r_status["stationary_branches_total"] == 24
            and phase6r["stationary_branch_count"] == 24
        ),
        "phase6r_beta_exact": abs(
            phase6r_status["maximum_weighted_beta"]
            - phase6r["maximum_weighted_beta"]
        )
        < 1e-15,
        "phase6r_beta_threshold_exact": abs(
            phase6r_status["frozen_beta_maximum"]
            - phase6r["thresholds"]["beta_max"]
        )
        < 1e-15,
        "phase6r_beta_failed": (
            phase6r_status["maximum_weighted_beta"]
            > phase6r_status["frozen_beta_maximum"]
        ),
        "phase6r_phase7_closed": phase6r_status["phase_7_may_begin"] is False,
        "phase6r_provenance_limit_recorded": (
            phase6r_status["standalone_preregistration_package_complete"] is False
        ),
        "wp09a_pass_preserved": (
            wp09a_status["status"] == "PASS" and wp09a["status"] == "PASS"
        ),
        "wp09a_cause_unassigned": (
            wp09a_status["cause_assigned"] is False
            and "does not identify an astrophysical cause" in wp09a["interpretation"]
        ),
        "manuscript_records_phase6r_failure": (
            "\\texttt{FAIL\\_RESIDUAL\\_CORRELATION}" in manuscript
        ),
        "manuscript_records_stationarity_24_of_24": (
            "stationarity in 24/24 branches" in manuscript
        ),
        "manuscript_records_beta_and_threshold": (
            "residual beta was 1.2936" in manuscript
            and "frozen limit of\n1.2" in manuscript
        ),
        "manuscript_stage3_is_protocol_only": (
            "Stage-3 continuation is\ncurrently protocol-only" in manuscript
            and "has not run a new real-data noise model" in manuscript
        ),
        "stale_no_real_data_statement_removed": (
            "failed before any\nnew real-data fit" not in manuscript
        ),
        "unconverged_sector_radius_range_removed": (
            "sector radius ratios from 0.0534 to 0.0559" not in manuscript
        ),
        "release_gates_remain_closed": all(
            value is False for value in release["gates"].values()
        ),
        "authoritative_documents_include_stage3": (
            "stage3.md" in release["authoritative_documents"]
        ),
    }

    sources = {
        path: {"sha256": sha256(path), "size_bytes": (ROOT / path).stat().st_size}
        for path in SOURCE_PATHS
    }

    return {
        "schema_version": "1.0",
        "work_package": "S3-00_SCOPE_SYNCHRONIZATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if all(checks.values()) else "FAIL",
        "real_data_fit_executed": False,
        "phase_7_may_begin": False,
        "checks": checks,
        "facts": {
            "phase6_status": phase6["status"],
            "phase6r_status": phase6r["status"],
            "phase6r_stationary_branches": phase6r["stationary_branch_count"],
            "phase6r_branch_count": phase6r["branch_count"],
            "phase6r_maximum_weighted_beta": phase6r["maximum_weighted_beta"],
            "phase6r_beta_maximum": phase6r["thresholds"]["beta_max"],
            "wp09a_status": wp09a["status"],
            "wp09a_cause_assigned": False,
            "stage3_status": stage3_status["status"],
        },
        "sources": sources,
    }
def comparable(report):
    report = dict(report)
    report.pop("generated_utc", None)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    current = build_audit()
    if current["status"] != "PASS":
        failed = [key for key, value in current["checks"].items() if not value]
        raise AssertionError("Stage-3 scope audit failed: " + ", ".join(failed))

    if args.verify_only:
        stored = json.loads(OUTPUT.read_text(encoding="utf-8"))
        if comparable(stored) != comparable(current):
            raise AssertionError("Stored Stage-3 scope audit is stale")
        print("STAGE-3 S3-00 SCOPE AUDIT: PASS (verified)")
        return

    if OUTPUT.exists():
        raise FileExistsError(
            "Stage-3 scope audit is no-clobber; use --verify-only"
        )
    OUTPUT.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    print("STAGE-3 S3-00 SCOPE AUDIT: PASS")


if __name__ == "__main__":
    main()
