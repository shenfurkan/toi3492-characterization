# EXONYM

**Exoplanet Naming, Observation, and Yield Verification Management** — a
factory-style workspace for rapid, evidence-first research on exoplanet
candidates. Every target-specific byte lives under `candidate/`; everything
outside `candidate/` is target-neutral shared infrastructure.

## The Core Rule

> No planet research happens outside `candidate/`. Archiving is a lifecycle
> state in `candidate/<candidate-id>/candidate.json`, never a directory move.

Run the enforcement check any time:

```powershell
exonym verify
```

The check rejects target identifiers, registered aliases, fixed sectors and
ephemerides, research payload formats, symlinks, and top-level `archive/` or
`data/` paths outside `candidate/`.

## Layout

| Path | Purpose |
| --- | --- |
| `candidate/` | All target research: identity, data, protocols, gates, claims, manuscripts, releases |
| `templates/` | Master gate documents cloned into every new workspace |
| `src/exonym/` | Target-neutral shared code (workspace, gates, tracking, vetting, freeze) |
| `tests/` | Tests for the shared layer (synthetic fixtures only) |
| `docs/` | Governance, lifecycle, and record templates |
| `protocols/` | Target-neutral protocol requirements and templates |
| `methods/` | Target-neutral method and feasibility guidance |
| `schemas/` | Machine-validated JSON schemas |
| `resources/` | Licensed metadata-only general resources |
| `policy/` | Enforced policy records and exception registry |

## CLI Command Matrix

| Command | Syntax | Description |
| --- | --- | --- |
| `init` | `exonym init <id> --toi <toi> --tic <tic> [--tag ...]` | Provision workspace and clone global templates |
| `list` | `exonym list [--phase <p>] [--tag <t>]` | Query and filter registered candidates |
| `status` | `exonym status <id>` | Show one candidate identity record |
| `track` | `exonym track <id>` | Render the QVG progress telemetry dashboard |
| `advance` | `exonym advance <id>` | Validate the current gate and promote the phase |
| `tag` | `exonym tag <id> <tag...>` | Attach metadata tags to a target record |
| `freeze` | `exonym freeze <id> [--version <v>]` | Build lockfiles and a reproducibility bundle |
| `verify` | `exonym verify` | Run the repository isolation audit |

## Workflow Phases

Seven sequential, gate-protected phases. `exonym advance` refuses to promote a
phase until every `[MANDATORY]` checkbox in the phase document is checked.

| Phase | Gate document | Gate check |
| --- | --- | --- |
| 0 `intake` | `docs/01_intake_manifest.md` | Canonical catalog identity verified; no collisions |
| 1 `feasibility` | `docs/02_feasibility_report.md` | Contamination, SNR, sector coverage assessed |
| 2 `acquisition` | `data/raw/` | Every raw FITS product has a `.provenance.json` sidecar |
| 3 `vetting` | `docs/03_spoc_dv_vetting.md` | Odd-even, centroid, ephemeris, secondary checks done |
| 4 `followup` | `docs/04_tfop_sg_followup.md` | TFOP SG1-SG5 status recorded |
| 5 `analysis` | `claims/` | An FPP claim below the preregistered threshold exists |
| 6 `review` | `decisions/review_gate.md` | Peer review signed; lifecycle locked |

## Fast Start

```powershell
pip install -e ".[test]"
exonym init candidate-alpha --toi <toi> --tic <tic>
exonym track candidate-alpha
```

## Development

```powershell
python -m pytest -q
exonym verify
```

Shared tests use only synthetic fixtures. Target-specific tests live inside
`candidate/<candidate-id>/tests/` and run separately.

## License

GNU General Public License v3.0. See `LICENSE`.
