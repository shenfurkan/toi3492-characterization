import json


def test_stage3_registry_audit_is_a_valid_current_snapshot(root):
    stored = json.loads(
        (root / "outputs" / "stage3_registry_audit.json").read_text(encoding="utf-8")
    )
    assert stored["status"] == "PASS"
    assert all(stored["checks"].values())
    assert stored["real_data_fit_executed"] is False
    assert stored["phase_7_may_begin"] is False
    assert all(
        len(record["sha256"]) == 64
        for record in stored["sources"].values()
    )


def test_stage3_does_not_authorize_real_data_or_phase7(root):
    release = json.loads(
        (root / "outputs" / "release_status.json").read_text(encoding="utf-8")
    )
    stage3 = release["stage3_scope_amendment"]
    assert stage3["approved"] is True
    assert stage3["status"] == "BLOCKED_REFACTOR_FREEZE_REQUIRED"
    assert stage3["active_execution_revision"] is None
    assert stage3["next_revision"] == 4
    assert stage3["real_data_fit_authorized"] is False
    assert stage3["phase_7_may_begin"] is False
    registry = json.loads(
        (root / "protocols" / "stage3" / "index.json").read_text(encoding="utf-8")
    )
    assert registry["active_execution_revision"] is None
    assert all(item["scientific_use"] == "NONE" for item in registry["revisions"].values())


def test_stage3_preserves_phase6_and_phase6r_failures(root):
    release = json.loads(
        (root / "outputs" / "release_status.json").read_text(encoding="utf-8")
    )
    assert release["phase_6_noise_model_audit"]["gate_status"] == "FAIL_STATIONARITY"
    phase6r = release["phase_6r_numerical_remediation"]
    assert phase6r["status"] == "FAIL_RESIDUAL_CORRELATION"
    assert phase6r["stationary_branches_valid"] == 24
    assert phase6r["stationary_branches_total"] == 24
    assert phase6r["maximum_weighted_beta"] > phase6r["frozen_beta_maximum"]
