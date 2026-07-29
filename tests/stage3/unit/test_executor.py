from toi3492.stage3.contracts import RunSpec
from toi3492.stage3.executor import build_jobs


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
