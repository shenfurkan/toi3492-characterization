"""Focused checks for the v2 data-generation boundary."""

import pytest

import stage3_joint_model as joint
import stage3_synthetic_calibration_core_v2 as core


@pytest.fixture(scope="module")
def context():
    return core.load_context()


def class_spec(context, name):
    return next(item for item in context.protocol["simulation_classes"]
                if item["name"] == name)


def test_v2_context_has_complete_and_gap_edge_event_sets(context):
    assert len(context.events) == 18
    assert len(context.complete_events) == 16
    assert len(context.gap_edge_events) == 2
    assert {event["physical_event_id"] for event in context.gap_edge_events} == {
        "S037-E002", "S099-E189",
    }


def test_c13_uses_frozen_aperture_telemetry(context):
    spec = class_spec(context, "C13_aperture_telemetry_correlated")
    frame, metadata = core.generate_latent_realization(context, spec, 0)
    assert metadata["telemetry_systematic"]["column"] == "crowdsap"
    assert metadata["telemetry_systematic"]["slope"] > 0.0
    assert len(metadata["event_ids"]) == 16
    assert frame["flux"].notna().all()


def test_c14_builds_joint_model_with_partial_event_inventory(context, root):
    spec = class_spec(context, "C14_partial_gap_edge_transit")
    frame, metadata = core.generate_latent_realization(context, spec, 0)
    branch = context.branches[0]
    mask = core.derive_mask(frame, context, branch["mask_id"])
    decision = core._load_json(
        root / "data" / "stage3_model_architecture_decision_v2.json"
    )
    model = joint.build_joint_model(
        branch, mask, context.events_for_class(spec), decision,
        expected_event_count=18,
    )
    assert len(model.sectors) == 6
    assert len(metadata["event_ids"]) == 18
