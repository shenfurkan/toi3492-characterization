"""Verification checks for release gates and expected closures."""

from __future__ import annotations

from ..core import Verification, _load


def verify_expected_closures(audit: Verification) -> None:
    release = _load("outputs/release_status.json")
    validation = _load("outputs/statistical_validation_120s.json")
    audit.check("release_gates", "no_overclaiming_release_state", bool(
        release["gates"]["archive_ready"] is False
        and release["gates"]["final_native_cadence_geometry_ready"] is False
        and release["gates"]["statistical_validation_ready"] is False
        and release["gates"]["planet_confirmation_ready"] is False
        and release["stage3_scope_amendment"]["real_data_fit_authorized"] is False
        and release["phase_6r_numerical_remediation"]["status"] == "FAIL_RESIDUAL_CORRELATION"
        and release["stage4_candidate_publication"]["limited_selector_status"] == "FAIL_CLAIM_REMOVED"
    ), release["strongest_supported_gate"])
    audit.check("release_gates", "formal_fpp_remains_unavailable", bool(
        validation["formal_fpp"] is None
        and validation["formal_fpp_available"] is False
        and validation["statistical_validation_claim_supported"] is False
    ), validation["reason"])
