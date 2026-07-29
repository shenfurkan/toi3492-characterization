"""Immutable contracts shared by Stage-3 producers, reducers, and the CLI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

from .errors import ContractError
from .jsonio import load_strict_json


SECTORS = (37, 63, 64, 90, 99, 100)
JOINT_HELD_SECTOR = -1
CANONICAL_TASK_SCHEMA_VERSION = "stage3-task-record/2.0"
CANONICAL_IMPLEMENTATION_CONTRACT = {
    "runner": "toi3492-stage3/2.0",
    "task_schema": CANONICAL_TASK_SCHEMA_VERSION,
    "reducer_gates": "stage3-reducer-gates/2.0",
}
EXECUTABLE_REGISTRY_STATUS = "READY_FOR_EXECUTION"
FORMAL_SCIENTIFIC_USE = "FORMAL_SYNTHETIC_CALIBRATION"


def load_registry(root: Path) -> Mapping:
    path = Path(root).resolve() / "protocols" / "stage3" / "index.json"
    registry = load_strict_json(path)
    if set(registry) != {
        "schema_version", "active_execution_revision", "next_revision",
        "execution_state", "revisions",
    }:
        raise ContractError("Stage-3 registry has the wrong schema")
    if not isinstance(registry["revisions"], Mapping):
        raise ContractError("Stage-3 registry revisions must be a mapping")
    return registry


@dataclass(frozen=True, order=True)
class TaskKey:
    class_ordinal: int
    realization_index: int
    branch_index: int
    held_sector: int

    def as_dict(self) -> dict:
        return {
            "class_ordinal": self.class_ordinal,
            "realization_index": self.realization_index,
            "branch_index": self.branch_index,
            "held_sector": self.held_sector,
        }


@dataclass(frozen=True)
class BranchSpec:
    ordinal: int
    model_id: str
    mask_id: str
    cell_id: str
    window_hours: int
    polynomial_degree: int
    joint_model_weight: float


@dataclass(frozen=True)
class RunSpec:
    protocol_revision: int
    root: Path
    protocol_path: Path
    architecture_path: Path
    input_manifest_path: Path
    authorization_path: Path
    artifact_namespace: Path
    task_schema_version: str
    seed_base: int
    status: str
    scientific_use: str

    @classmethod
    def from_registry(cls, root: Path, revision: Optional[int] = None) -> "RunSpec":
        root = Path(root).resolve()
        registry = load_registry(root)
        selected = revision if revision is not None else registry.get("active_execution_revision")
        if selected is None:
            raise ContractError(
                "no Stage-3 revision is authorized for execution; use an explicit "
                "historical revision only for read-only inspection"
            )
        record = registry["revisions"].get(str(int(selected)))
        if record is None:
            raise ContractError("unknown Stage-3 protocol revision: {}".format(selected))
        required = {
            "protocol", "architecture", "input_manifest", "authorization",
            "artifact_namespace", "task_schema_version", "seed_base", "status",
            "scientific_use",
        }
        if set(record) != required:
            raise ContractError("Stage-3 registry record has the wrong schema")
        paths = {
            name: (root / record[name]).resolve()
            for name in ("protocol", "architecture", "input_manifest", "authorization")
        }
        if any(root not in path.parents or not path.is_file() for path in paths.values()):
            raise ContractError("Stage-3 registry points outside the repository or to a missing file")
        namespace = (root / record["artifact_namespace"]).resolve()
        if root not in namespace.parents:
            raise ContractError("Stage-3 artifact namespace is outside the repository")
        return cls(
            protocol_revision=int(selected),
            root=root,
            protocol_path=paths["protocol"],
            architecture_path=paths["architecture"],
            input_manifest_path=paths["input_manifest"],
            authorization_path=paths["authorization"],
            artifact_namespace=namespace,
            task_schema_version=str(record["task_schema_version"]),
            seed_base=int(record["seed_base"]),
            status=str(record["status"]),
            scientific_use=str(record["scientific_use"]),
        )

    def load_protocol(self) -> Mapping:
        return load_strict_json(self.protocol_path)

    def load_architecture(self) -> Mapping:
        return load_strict_json(self.architecture_path)

    def has_canonical_implementation_contract(self) -> bool:
        return (
            self.task_schema_version == CANONICAL_TASK_SCHEMA_VERSION
            and self.load_protocol().get("implementation_contract")
            == CANONICAL_IMPLEMENTATION_CONTRACT
        )

    def class_specs(self) -> Tuple[Mapping, ...]:
        protocol = self.load_protocol()
        classes = tuple(protocol["simulation_classes"])
        if len(classes) != 14 or sum(int(item["requested_count"]) for item in classes) != 235:
            raise ContractError("Stage-3 class universe is not 14/235")
        ordinals = [int(item["class_index"]) for item in classes]
        if sorted(ordinals) != list(range(14)):
            raise ContractError("Stage-3 class ordinals are not the contiguous range 0..13")
        return classes

    def realization_seed(self, class_ordinal: int, realization_index: int) -> int:
        if class_ordinal < 0 or realization_index < 0:
            raise ContractError("seed coordinates must be non-negative")
        return self.seed_base + class_ordinal * 10000 + realization_index * 100

    def expected_task_keys(self, component: str) -> Tuple[TaskKey, ...]:
        if component not in ("screening", "recovery"):
            raise ContractError("unknown Stage-3 component: {}".format(component))
        held_sectors = SECTORS if component == "screening" else (JOINT_HELD_SECTOR,)
        return tuple(
            TaskKey(int(spec["class_index"]), realization, branch, held)
            for spec in self.class_specs()
            for realization in range(int(spec["requested_count"]))
            for branch in range(24)
            for held in held_sectors
        )
