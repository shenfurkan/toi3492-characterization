import json
from pathlib import Path

from build_stage3_input_manifest import build_manifest, comparable


def load(root, relative_path):
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def test_stage3_input_manifest_is_current_and_passes(root):
    stored = load(root, "data/stage3_input_manifest.json")
    current = build_manifest()
    assert stored["status"] == "PASS"
    assert all(stored["checks"].values())
    assert comparable(stored) == comparable(current)


def test_stage3_input_manifest_freezes_events_and_models(root):
    stored = load(root, "data/stage3_input_manifest.json")
    phase2 = load(root, "outputs/faz2_transit_inventory.json")
    phase5b = load(root, "outputs/faz5b_remediation.json")

    assert stored["event_universe"]["used_event_count"] == 16
    assert [
        {"sector": item["sector"], "epoch": item["epoch"]}
        for item in stored["event_universe"]["events"]
    ] == phase2["summary"]["used_event_keys"]
    assert stored["model_universe"]["model_count"] == 24
    assert stored["model_universe"]["model_ids"] == phase5b["handoff"]["model_ids"]
    assert (
        stored["model_universe"]["joint_model_weights"]
        == phase5b["handoff"]["joint_model_weights"]
    )


def test_stage3_input_manifest_hashes_every_declared_input(root):
    stored = load(root, "data/stage3_input_manifest.json")
    records = [
        record
        for group in stored["input_groups"].values()
        for record in group
    ]
    assert len(records) == len({record["path"] for record in records})
    for record in records:
        path = root / record["path"]
        assert path.is_file()
        assert path.stat().st_size == record["size_bytes"]
        assert len(record["sha256"]) == 64


def test_stage3_input_manifest_preserves_failures_and_closes_real_data(root):
    stored = load(root, "data/stage3_input_manifest.json")
    results = stored["preserved_results"]
    assert results["phase5"] == "FAIL"
    assert results["phase6"] == "FAIL_STATIONARITY"
    assert results["phase6r"] == "FAIL_RESIDUAL_CORRELATION"
    assert stored["real_data_fit_executed"] is False
    assert stored["phase_7_may_begin"] is False
    assert not Path(root / "data" / "faz6r_numerical_remediation_protocol.json").exists()
