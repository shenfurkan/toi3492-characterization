"""Single version-neutral command line for Stage-3 work."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .contracts import ContractError, RunSpec, load_registry


ROOT = Path(__file__).resolve().parents[3]


def _spec(args):
    if args.revision is None:
        raise ContractError("--revision is required for this command")
    return RunSpec.from_registry(ROOT, args.revision)


def _status(args):
    registry = load_registry(ROOT)
    if args.revision is None:
        print(json.dumps(registry, indent=2, sort_keys=True))
        return 0
    from .runtime import readiness

    report = readiness(_spec(args))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _preflight(args):
    from .runtime import readiness

    report = readiness(_spec(args))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["execution_ready"] else 2


def _plan(args):
    from .executor import build_jobs

    spec = _spec(args)
    components = tuple(args.component or ("screening", "recovery"))
    jobs = build_jobs(
        spec,
        components=components,
        class_ordinals=args.class_ordinal,
        realization_indices=args.realization,
        branch_indices=args.branch,
        held_sectors=args.held_sector,
    )
    task_count = sum(len(job.branch_indices) * (
        (len(job.held_sectors) if "screening" in job.components else 0)
        + (1 if "recovery" in job.components else 0)
    ) for job in jobs)
    print(json.dumps({
        "protocol_revision": spec.protocol_revision,
        "jobs": len(jobs),
        "logical_tasks": task_count,
        "components": components,
        "implementation_compatible": spec.has_canonical_implementation_contract(),
        "formal_execution_started": False,
    }, indent=2, sort_keys=True))
    return 0


def _run(args):
    from .executor import build_jobs, execute_jobs
    from .runtime import require_execution_ready

    spec = _spec(args)
    require_execution_ready(spec)
    if not args.confirm_full_run:
        raise ContractError("formal execution requires --confirm-full-run")
    if args.workers <= 0:
        raise ContractError("worker count must be positive")
    jobs = build_jobs(spec, components=("screening", "recovery"))
    result = execute_jobs(spec, jobs, args.workers)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _verify(args):
    from .runtime import verify_component

    spec = _spec(args)
    components = tuple(args.component or ("screening", "recovery"))
    reports = [
        verify_component(spec, component, require_complete=not args.allow_partial)
        for component in components
    ]
    print(json.dumps(reports, indent=2, sort_keys=True))
    return 0 if all(report["missing"] == 0 for report in reports) else 3


def _reduce(args):
    from .reducer import reduce_completed_run

    summary = reduce_completed_run(_spec(args))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["gate_status"] == "PASS" else 4


def _diagnose_realization(args):
    from .inputs import load_inputs
    from .runtime import require_development_ready
    from .simulation import generate_realization

    if not args.acknowledge_nonformal:
        raise ContractError("diagnostic generation requires --acknowledge-nonformal")
    spec = _spec(args)
    require_development_ready(spec)
    inputs = load_inputs(spec)
    matches = [
        item for item in inputs.protocol["simulation_classes"]
        if int(item["class_index"]) == args.class_ordinal
    ]
    if len(matches) != 1:
        raise ContractError("diagnostic class ordinal is absent or duplicated")
    class_spec = matches[0]
    latent = generate_realization(inputs, class_spec, args.realization)
    print(json.dumps({
        "protocol_revision": spec.protocol_revision,
        "class_ordinal": args.class_ordinal,
        "realization_index": args.realization,
        "row_count": len(latent.frame),
        "minimum_transit_flux": float(latent.frame["transit_flux"].min()),
        "metadata": latent.metadata,
        "formal_artifact_written": False,
        "scientific_gate_use": "FORBIDDEN",
    }, indent=2, sort_keys=True))
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="stage3")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def revision(command):
        command.add_argument("--revision", type=int)

    status = subparsers.add_parser("status")
    revision(status)
    status.set_defaults(handler=_status)

    preflight = subparsers.add_parser("preflight")
    revision(preflight)
    preflight.set_defaults(handler=_preflight)

    plan = subparsers.add_parser("plan")
    revision(plan)
    _task_filters(plan)
    plan.set_defaults(handler=_plan)

    run = subparsers.add_parser("run")
    revision(run)
    run.add_argument("--workers", type=int, default=1)
    run.add_argument("--confirm-full-run", action="store_true")
    run.set_defaults(handler=_run)

    verify = subparsers.add_parser("verify")
    revision(verify)
    verify.add_argument(
        "--component", choices=("screening", "recovery"), action="append",
    )
    verify.add_argument("--allow-partial", action="store_true")
    verify.set_defaults(handler=_verify)

    reduce_parser = subparsers.add_parser("reduce-only")
    revision(reduce_parser)
    reduce_parser.set_defaults(handler=_reduce)

    diagnose = subparsers.add_parser("diagnose-realization")
    revision(diagnose)
    diagnose.add_argument("--class-ordinal", type=int, required=True)
    diagnose.add_argument("--realization", type=int, required=True)
    diagnose.add_argument("--acknowledge-nonformal", action="store_true")
    diagnose.set_defaults(handler=_diagnose_realization)
    return parser.parse_args(argv)


def _task_filters(parser):
    parser.add_argument(
        "--component", choices=("screening", "recovery"), action="append",
    )
    parser.add_argument("--class-ordinal", type=int, action="append")
    parser.add_argument("--realization", type=int, action="append")
    parser.add_argument("--branch", type=int, action="append")
    parser.add_argument("--held-sector", type=int, action="append")


def main(argv=None):
    try:
        args = parse_args(argv)
        return int(args.handler(args))
    except (ContractError, OSError, KeyError, ValueError) as exc:
        print("Stage-3 command failed: {}".format(exc), file=sys.stderr)
        return 1
