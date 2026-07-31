import hashlib
import json
import threading
import types
from concurrent.futures import Future, ThreadPoolExecutor

import pandas as pd
import pytest

import toi3492.stage3.executor as executor_module
from toi3492.stage3.contracts import BranchSpec, ContractError, RunSpec
from toi3492.stage3.executor import build_jobs, execute_jobs
from toi3492.stage3.jsonio import canonical_json_bytes, create_immutable_json


def test_executor_groups_work_by_realization(root):
    spec = RunSpec.from_registry(root, 3)
    jobs = build_jobs(
        spec,
        components=("screening", "recovery"),
        class_ordinals=(0,),
        realization_indices=(0,),
    )
    assert len(jobs) == 1
    job = jobs[0]
    assert len(job.branch_indices) == 24
    assert len(job.held_sectors) == 6


def test_filtered_plan_does_not_expand_to_full_universe(root):
    spec = RunSpec.from_registry(root, 3)
    jobs = build_jobs(
        spec,
        components=("screening",),
        class_ordinals=(0,),
        realization_indices=(0, 1),
        branch_indices=(0,),
        held_sectors=(37,),
    )
    assert len(jobs) == 2
    assert all(job.branch_indices == (0,) for job in jobs)


_SIMULATION_CLASSES = [
    {"class_index": 0, "class_name": "C01_white_jitter_transit", "requested_count": 30},
    {"class_index": 1, "class_name": "C02_m1_160_transit", "requested_count": 30},
    {"class_index": 2, "class_name": "C03_m1_80_transit", "requested_count": 20},
    {"class_index": 3, "class_name": "C04_m1_320_transit", "requested_count": 20},
    {"class_index": 4, "class_name": "C05_m1_720_boundary", "requested_count": 15},
    {"class_index": 5, "class_name": "C06_ou_160_misspec", "requested_count": 15},
    {"class_index": 6, "class_name": "C07_sho_160_misspec", "requested_count": 15},
    {"class_index": 7, "class_name": "C08_sector_vary_amplitude", "requested_count": 15},
    {"class_index": 8, "class_name": "C09_sector_vary_timescale", "requested_count": 15},
    {"class_index": 9, "class_name": "C10_background_correlated", "requested_count": 15},
    {"class_index": 10, "class_name": "C11_no_transit_null", "requested_count": 10},
    {"class_index": 11, "class_name": "C12_near_boundary_tau4", "requested_count": 10},
    {"class_index": 12, "class_name": "C13_aperture_telemetry_correlated", "requested_count": 15},
    {"class_index": 13, "class_name": "C14_partial_gap_edge_transit", "requested_count": 10},
]


def _manifest(run_hash=None):
    payload = {
        "components": {
            "common": {"sha256": "b" * 64},
            "screening": {"sha256": "c" * 64},
            "recovery": {"sha256": "d" * 64},
        },
    }
    payload["sha256"] = run_hash or hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    return payload


def _execution_spec(tmp_path, namespace_name="stage3_v4"):
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({
        "implementation_contract": {
            "runner": "toi3492-stage3/2.0",
            "task_schema": "stage3-task-record/2.0",
            "reducer_gates": "stage3-reducer-gates/2.0",
        },
        "simulation_classes": _SIMULATION_CLASSES,
    }), encoding="utf-8")
    architecture = tmp_path / "architecture.json"
    architecture.write_text(json.dumps({
        "candidate": {
            "transit_model": {
                "geometry_uniform_bounds": {
                    "rp_rs": [0.03, 0.09],
                    "a_rs": [5.0, 16.0],
                    "impact_parameter": [0.0, 0.98],
                },
            },
        },
    }), encoding="utf-8")
    return RunSpec(
        protocol_revision=4,
        root=tmp_path,
        protocol_path=protocol,
        architecture_path=architecture,
        input_manifest_path=tmp_path / "placeholder.json",
        authorization_path=tmp_path / "placeholder.json",
        artifact_namespace=tmp_path / "outputs" / namespace_name,
        task_schema_version="stage3-task-record/2.0",
        seed_base=949204,
        status="DEVELOPMENT",
        scientific_use="DEVELOPMENT_ONLY",
    )


def _branch(index):
    return BranchSpec(
        ordinal=index,
        model_id="raw_valid::W13_P0",
        mask_id="raw_valid",
        cell_id="W13_P0",
        window_hours=13,
        polynomial_degree=0,
        joint_model_weight=1.0 / 24.0,
    )


def _stub_inputs():
    return types.SimpleNamespace(
        protocol={"simulation_classes": [{"class_index": 0}]},
        branches=tuple(_branch(index) for index in range(24)),
        mask=lambda frame, name: frame,
    )


def _stub_initialize_namespace(spec):
    manifest = _manifest()
    create_immutable_json(spec.artifact_namespace / "run_identity.json", manifest)
    return manifest


def _stub_initialize_worker(spec, manifest):
    executor_module._WORKER_SPEC = spec
    executor_module._WORKER_INPUTS = _stub_inputs()
    executor_module._WORKER_MANIFEST = manifest


def _stub_realization(class_ordinal, realization_index, seed):
    frame = pd.DataFrame({
        "sector": [37, 37],
        "cadenceno": [1, 2],
        "time_btjd": [2000.0, 2000.1],
        "flux": [1.0, 1.0],
        "flux_err": [0.01, 0.01],
    })
    metadata = {
        "class_id": "C01",
        "class_name": "C01_white_jitter_transit",
        "class_ordinal": class_ordinal,
        "realization_index": realization_index,
        "realization_seed": seed,
        "drawn_geometry": None,
        "sector_noise": {},
        "telemetry_systematic": None,
        "shared_baseline_draws": {},
        "event_ids": [],
    }
    return types.SimpleNamespace(frame=frame, metadata=metadata)


def _stub_generate_realization(inputs, class_spec, realization_index):
    spec = executor_module._WORKER_SPEC
    class_ordinal = int(class_spec["class_index"])
    return _stub_realization(
        class_ordinal,
        realization_index,
        spec.realization_seed(class_ordinal, realization_index),
    )


def _stub_prepare_branch(inputs, class_spec, frame, branch, mask=None):
    return types.SimpleNamespace(branch=branch, mask=mask)


def _stub_score_fold(prepared, held_sector):
    branch = prepared.branch
    return {
        "model_id": branch.model_id,
        "mask_id": branch.mask_id,
        "cell_id": branch.cell_id,
        "joint_model_weight": branch.joint_model_weight,
        "held_sector": held_sector,
        "k0_score": 0.0,
        "m1_score": 1.0,
        "delta_elpd": 1.0,
        "k0_objective": 0.0,
        "m1_objective": 1.0,
        "k0_boundary_count": 0,
        "m1_boundary_count": 0,
        "gap_edge_coverage": {},
    }


def _stub_recovery(inputs, class_spec, frame, metadata, branch, mask=None):
    return {
        "model_id": branch.model_id,
        "mask_id": branch.mask_id,
        "cell_id": branch.cell_id,
        "joint_model_weight": branch.joint_model_weight,
        "objective_h0": 1.0,
        "objective_h1": 0.5,
        "delta_map": 0.5,
        "recovery_mode": "conditional_geometry_with_fixed_oot_noise",
        "recovered_geometry": {
            "rp_rs": 0.05,
            "a_rs": 10.0,
            "impact_parameter": 0.5,
            "t14_hours": 5.0,
        },
        "injected_geometry": None,
        "intervals": {
            "rp_rs": [0.03, 0.04, 0.06, 0.09],
            "a_rs": [6.0, 8.0, 12.0, 15.0],
            "impact_parameter": [0.1, 0.3, 0.7, 0.9],
            "t14_hours": [3.0, 4.0, 6.0, 7.0],
        },
        "noise_boundary_count": 0,
        "geometry_boundary_count": 0,
        "gap_edge_coverage": {},
        "optimizer_no_op_count": 0,
        "optimizer_local_mode_count": 0,
        "max_abs_standardized_residual": 0.0,
        "ingress_egress_rms_relative_flux": 0.0,
    }


@pytest.fixture
def stubbed_execution(monkeypatch):
    monkeypatch.setattr(executor_module, "initialize_namespace", _stub_initialize_namespace)
    monkeypatch.setattr(executor_module, "_initialize_worker", _stub_initialize_worker)
    monkeypatch.setattr(executor_module, "generate_realization", _stub_generate_realization)
    monkeypatch.setattr(executor_module, "prepare_branch", _stub_prepare_branch)
    monkeypatch.setattr(executor_module, "score_fold", _stub_score_fold)
    monkeypatch.setattr(
        executor_module, "conditional_geometry_recovery", _stub_recovery,
    )
    monkeypatch.setattr(executor_module, "cpu_count", lambda: 8)


class _SyncExecutor:
    """Executes every job eagerly in the caller's process (no multiprocessing)."""

    def __init__(self, max_workers, initializer=None, initargs=()):
        self.max_workers = max_workers
        self.initializer = initializer
        self.initargs = initargs

    def __enter__(self):
        if self.initializer is not None:
            self.initializer(*self.initargs)
        return self

    def __exit__(self, *exc_info):
        return False

    def submit(self, fn, *args):
        future = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class _ScriptedExecutor:
    """Resolves submitted futures from a background thread according to a script.

    ``"ok"`` resolves with zeroed totals; ``"raise"`` sets a ContractError.
    Futures resolve in submission order, so ``as_completed`` sees the first
    submitted future first, deterministically.
    """

    def __init__(self, script, max_workers, initializer=None, initargs=()):
        self.script = list(script)
        self.max_workers = max_workers
        self.initializer = initializer
        self.initargs = initargs
        self.submitted_futures = []
        self._pending = []
        self._condition = threading.Condition()
        self._thread = None

    def __enter__(self):
        if self.initializer is not None:
            self.initializer(*self.initargs)
        return self

    def __exit__(self, *exc_info):
        if self._thread is not None:
            self._thread.join(timeout=15)
        return False

    def submit(self, fn, *args):
        future = Future()
        self.submitted_futures.append(future)
        with self._condition:
            self._pending.append((future, fn, args))
            self._condition.notify_all()
        if self._thread is None:
            self._thread = threading.Thread(target=self._drive, daemon=True)
            self._thread.start()
        return future

    def _drive(self):
        for action in self.script:
            with self._condition:
                while not self._pending:
                    self._condition.wait(timeout=10)
                future, fn, args = self._pending.pop(0)
            if action == "raise":
                future.set_exception(ContractError("scripted failure"))
            else:
                future.set_result({"created": 0, "resumed": 0})


def _factory_harness(script, **kwargs):
    holder = {}

    def factory(**kwargs):
        holder["executor"] = _ScriptedExecutor(script=script, **kwargs)
        return holder["executor"]

    return factory, holder


def test_execute_jobs_rejects_nonpositive_worker_counts(stubbed_execution, tmp_path):
    spec = _execution_spec(tmp_path)
    jobs = build_jobs(
        spec, components=("screening",), class_ordinals=(0,), realization_indices=(0,),
    )
    with pytest.raises(ContractError, match="worker count must be positive"):
        execute_jobs(spec, jobs, 0, _SyncExecutor)
    with pytest.raises(ContractError, match="worker count must be positive"):
        execute_jobs(spec, jobs, -1, _SyncExecutor)


def test_failure_cancels_pending_futures_and_does_not_top_up(stubbed_execution, tmp_path):
    spec = _execution_spec(tmp_path)
    jobs = build_jobs(
        spec, components=("screening",), class_ordinals=(0,), realization_indices=(0, 1, 2),
    )
    factory, holder = _factory_harness(("raise",))
    with pytest.raises(ContractError, match="scripted failure"):
        execute_jobs(spec, jobs, 2, factory)
    executor = holder["executor"]
    assert len(executor.submitted_futures) == 2
    failed, pending = executor.submitted_futures
    assert failed.done() and not failed.cancelled()
    assert pending.cancelled()


def test_resume_revalidates_existing_tasks_without_rerunning(
    stubbed_execution, tmp_path, monkeypatch,
):
    spec = _execution_spec(tmp_path)
    jobs = build_jobs(
        spec, components=("screening", "recovery"),
        class_ordinals=(0,), realization_indices=(0,),
    )
    first = execute_jobs(spec, jobs, 2, _SyncExecutor)
    assert first["jobs"] == 1
    assert first["created"] == 24 * 6 + 24
    assert first["resumed"] == 0

    def _fail_on_regeneration(inputs, class_spec, realization_index):
        raise AssertionError("resume must not regenerate a realization")

    monkeypatch.setattr(executor_module, "generate_realization", _fail_on_regeneration)
    second = execute_jobs(spec, jobs, 2, _SyncExecutor)
    assert second == {"jobs": 1, "created": 0, "resumed": 24 * 6 + 24}


def test_worker_count_invariance_produces_byte_identical_task_records(
    stubbed_execution, tmp_path,
):
    spec_a = _execution_spec(tmp_path, "a")
    spec_b = _execution_spec(tmp_path, "b")
    jobs = build_jobs(
        spec_a, components=("screening", "recovery"),
        class_ordinals=(0,), realization_indices=(0, 1),
    )
    first = execute_jobs(spec_a, jobs, 1, ThreadPoolExecutor)
    second = execute_jobs(spec_b, jobs, 3, ThreadPoolExecutor)
    expected_created = 2 * (24 * 6 + 24)
    assert first == {"jobs": 2, "created": expected_created, "resumed": 0}
    assert second == {"jobs": 2, "created": expected_created, "resumed": 0}
    files_a = sorted((spec_a.artifact_namespace / "tasks").rglob("*.json"))
    files_b = sorted((spec_b.artifact_namespace / "tasks").rglob("*.json"))
    assert [path.name for path in files_a] == [path.name for path in files_b]
    for path_a, path_b in zip(files_a, files_b):
        assert path_a.read_bytes() == path_b.read_bytes()
