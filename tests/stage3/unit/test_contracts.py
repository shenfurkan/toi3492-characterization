import json

import pytest

from toi3492.stage3.contracts import (
    CANONICAL_TASK_SCHEMA_VERSION,
    ContractError,
    RunSpec,
)


def test_registry_has_no_active_execution_revision(root):
    registry = json.loads(
        (root / "protocols" / "stage3" / "index.json").read_text(encoding="utf-8")
    )
    assert registry["active_execution_revision"] is None
    assert registry["next_revision"] == 4
    assert registry["execution_state"] == "BLOCKED_REFACTOR_FREEZE_REQUIRED"
    with pytest.raises(ContractError, match="no Stage-3 revision"):
        RunSpec.from_registry(root)


def test_historical_revisions_are_explicitly_non_scientific(root):
    expected = {
        1: "QUARANTINED_INVALID",
        2: "SUPERSEDED_REVIEW_FAILED",
        3: "SUPERSEDED_IMPLEMENTATION_DEFECTS",
    }
    for revision, status in expected.items():
        spec = RunSpec.from_registry(root, revision)
        assert spec.status == status
        assert spec.scientific_use == "NONE"
        assert spec.has_canonical_implementation_contract() is False


def test_no_historical_revision_claims_the_canonical_task_schema(root):
    for revision in (1, 2, 3):
        spec = RunSpec.from_registry(root, revision)
        assert spec.task_schema_version != CANONICAL_TASK_SCHEMA_VERSION


def test_task_counts_remain_frozen(root):
    spec = RunSpec.from_registry(root, 3)
    assert len(spec.expected_task_keys("screening")) == 33840
    assert len(spec.expected_task_keys("recovery")) == 5640


def test_historical_v3_class_ordinals_are_contiguous(root):
    spec = RunSpec.from_registry(root, 3)
    ordinals = [int(item["class_index"]) for item in spec.class_specs()]
    assert ordinals == list(range(14))
