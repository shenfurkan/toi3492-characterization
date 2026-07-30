"""Realization-grouped Stage-3 execution.

One process owns one realization at a time. The latent frame is generated once,
both masks are cached, each branch is prepared once, and all requested folds
reuse that preparation.
"""

from __future__ import annotations

import hashlib
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from multiprocessing import cpu_count
from typing import Optional, Sequence, Tuple

import pandas as pd

from .contracts import ContractError, RunSpec, SECTORS, TaskKey
from .identity import normalize_thread_limits
from .inputs import Stage3Inputs, load_inputs
from .recovery import conditional_geometry_recovery
from .runtime import (
    initialize_namespace,
    task_path,
    validate_task,
    write_realization_metadata,
    write_task,
)
from .screening import prepare_branch, score_fold
from .simulation import generate_realization


normalize_thread_limits()


@dataclass(frozen=True)
class RealizationJob:
    class_ordinal: int
    realization_index: int
    components: Tuple[str, ...]
    branch_indices: Tuple[int, ...]
    held_sectors: Tuple[int, ...]


_WORKER_SPEC = None
_WORKER_INPUTS = None
_WORKER_MANIFEST = None


def _latent_hash(frame: pd.DataFrame) -> str:
    columns = ("sector", "cadenceno", "time_btjd", "flux", "flux_err")
    values = frame.loc[:, columns].sort_values(["sector", "cadenceno"])
    return hashlib.sha256(
        pd.util.hash_pandas_object(values, index=False).to_numpy().tobytes()
    ).hexdigest()


def _initialize_worker(spec: RunSpec, manifest):
    global _WORKER_SPEC, _WORKER_INPUTS, _WORKER_MANIFEST
    _WORKER_SPEC = spec
    _WORKER_INPUTS = load_inputs(spec)
    _WORKER_MANIFEST = manifest


def _class_spec(inputs: Stage3Inputs, class_ordinal: int):
    matches = [
        item for item in inputs.protocol["simulation_classes"]
        if int(item["class_index"]) == class_ordinal
    ]
    if len(matches) != 1:
        raise ContractError("class ordinal is absent or duplicated: {}".format(class_ordinal))
    return matches[0]


def _job_keys(job: RealizationJob):
    keys = []
    if "screening" in job.components:
        keys.extend(
            ("screening", TaskKey(job.class_ordinal, job.realization_index, branch, held))
            for branch in job.branch_indices
            for held in job.held_sectors
        )
    if "recovery" in job.components:
        keys.extend(
            ("recovery", TaskKey(job.class_ordinal, job.realization_index, branch, -1))
            for branch in job.branch_indices
        )
    return tuple(keys)


def _run_job(job: RealizationJob):
    spec = _WORKER_SPEC
    inputs = _WORKER_INPUTS
    manifest = _WORKER_MANIFEST
    if spec is None or inputs is None or manifest is None:
        raise RuntimeError("Stage-3 worker was not initialized")
    missing = []
    for component, key in _job_keys(job):
        path = task_path(spec, component, key)
        if path.is_file():
            validate_task(spec, manifest, component, key)
        else:
            missing.append((component, key))
    if not missing:
        return {"job": job, "created": 0, "resumed": len(_job_keys(job))}

    class_spec = _class_spec(inputs, job.class_ordinal)
    realization = generate_realization(inputs, class_spec, job.realization_index)
    latent_sha256 = _latent_hash(realization.frame)
    metadata = {
        **dict(realization.metadata),
        "latent_sha256": latent_sha256,
    }
    realization_record = write_realization_metadata(spec, manifest, metadata)
    masks = {
        "raw_valid": realization.frame,
        "reference_included": inputs.mask(realization.frame, "reference_included"),
    }
    created = 0
    missing_set = set(missing)
    for branch_index in job.branch_indices:
        branch = inputs.branches[branch_index]
        mask = masks[branch.mask_id]
        screening_keys = [
            TaskKey(job.class_ordinal, job.realization_index, branch_index, held)
            for held in job.held_sectors
            if ("screening", TaskKey(
                job.class_ordinal, job.realization_index, branch_index, held,
            )) in missing_set
        ]
        if screening_keys:
            prepared = prepare_branch(
                inputs, class_spec, realization.frame, branch, mask=mask,
            )
            for key in screening_keys:
                result = score_fold(prepared, key.held_sector)
                write_task(
                    spec, manifest, "screening", key, realization_record, result,
                    expected_branch=branch,
                )
                created += 1
        recovery_key = TaskKey(job.class_ordinal, job.realization_index, branch_index, -1)
        if ("recovery", recovery_key) in missing_set:
            result = conditional_geometry_recovery(
                inputs,
                class_spec,
                realization.frame,
                realization.metadata,
                branch,
                mask=mask,
            )
            write_task(
                spec, manifest, "recovery", recovery_key, realization_record, result,
                expected_branch=branch,
            )
            created += 1
    return {
        "job": job,
        "created": created,
        "resumed": len(_job_keys(job)) - created,
    }


def build_jobs(
    spec: RunSpec,
    components: Sequence[str] = ("screening", "recovery"),
    class_ordinals: Optional[Sequence[int]] = None,
    realization_indices: Optional[Sequence[int]] = None,
    branch_indices: Optional[Sequence[int]] = None,
    held_sectors: Optional[Sequence[int]] = None,
):
    components = tuple(components)
    if not components or any(item not in ("screening", "recovery") for item in components):
        raise ContractError("components must contain screening and/or recovery")
    classes = set(class_ordinals) if class_ordinals is not None else None
    realizations = set(realization_indices) if realization_indices is not None else None
    branches = tuple(branch_indices) if branch_indices is not None else tuple(range(24))
    held = tuple(held_sectors) if held_sectors is not None else SECTORS
    if any(branch < 0 or branch >= 24 for branch in branches):
        raise ContractError("branch index is outside [0, 23]")
    if any(sector not in SECTORS for sector in held):
        raise ContractError("held-sector filter is outside the six-sector universe")
    jobs = []
    for class_spec in spec.class_specs():
        class_ordinal = int(class_spec["class_index"])
        if classes is not None and class_ordinal not in classes:
            continue
        for realization_index in range(int(class_spec["requested_count"])):
            if realizations is not None and realization_index not in realizations:
                continue
            jobs.append(RealizationJob(
                class_ordinal,
                realization_index,
                components,
                branches,
                held,
            ))
    return tuple(jobs)


def execute_jobs(
    spec: RunSpec,
    jobs: Sequence[RealizationJob],
    workers: int,
    executor_factory=ProcessPoolExecutor,
):
    if not jobs:
        return {"jobs": 0, "created": 0, "resumed": 0}
    if int(workers) <= 0:
        raise ContractError("worker count must be positive")
    manifest = initialize_namespace(spec)
    worker_count = min(int(workers), cpu_count(), len(jobs))
    totals = {"jobs": len(jobs), "created": 0, "resumed": 0}
    with executor_factory(
        max_workers=worker_count,
        initializer=_initialize_worker,
        initargs=(spec, manifest),
    ) as executor:
        pending_jobs = iter(jobs)
        futures = {}
        for _ in range(worker_count):
            job = next(pending_jobs, None)
            if job is not None:
                futures[executor.submit(_run_job, job)] = job
        try:
            while futures:
                future = next(as_completed(tuple(futures)))
                futures.pop(future)
                result = future.result()
                totals["created"] += result["created"]
                totals["resumed"] += result["resumed"]
                job = next(pending_jobs, None)
                if job is not None:
                    futures[executor.submit(_run_job, job)] = job
        except Exception:
            for future in futures:
                future.cancel()
            raise
    return totals
