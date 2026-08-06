# Active Candidates

Every research target has one permanent directory: `candidate/<candidate-id>/`.
Archiving, publishing, or stopping work never moves that directory; it only
updates the lifecycle state in the candidate's `candidate.json`.

## Workspace Layout

| Path | Use |
| --- | --- |
| `candidate.json` | Identity and lifecycle record (schema v2) |
| `README.md` | Target summary and entry point |
| `config/` | Target constants and catalog snapshots |
| `data/` | Raw, external, interim, and processed data |
| `protocols/` | Preregistered, versioned scientific decisions |
| `runs/` | Execution records |
| `gates/` | Gate reviews and dispositions |
| `claims/` | Claim-to-evidence mappings |
| `decisions/` | Decision log entries |
| `provenance/` | Dataset, run, and environment provenance |
| `outputs/` | Generated analysis products |
| `figures/` | Rendered diagnostics and publication figures |
| `literature/` | Target-specific reading notes and metadata |
| `manuscripts/` | Manuscript source, submissions, and receipts |
| `releases/` | Versioned release packages |
| `scripts/` | Target-specific entry points |
| `tests/` | Target-specific tests |
| `docs/` | Intake, feasibility, and handover records |
| `scratch/` | Disposable local work |

## Lifecycle

`active`, `paused`, `stopped`, `published`, and `archived` are lifecycle
states recorded in `candidate.json`. They are independent of scientific
disposition (`unknown`, `candidate`, `unvalidated_candidate`, `false_positive`,
`validated`, `confirmed`, `inconclusive`), workflow phase (`intake`,
`feasibility`, `acquisition`, `vetting`, `followup`, `analysis`, `review`),
and publication state.

## Gate Documents

Every workspace receives the master gate documents from `templates/` at
instantiation: intake manifest, feasibility report, SPOC DV vetting, TFOP
subgroup follow-up, transit fitting and radial-velocity protocols, review
gate, and pipeline status. `exonym advance` promotes phases only after all
`[MANDATORY]` items are checked.

## Campaigns

Multi-target screening lives in `candidate/_campaigns/<campaign-id>/`; each
measured or decided target still gets its own `candidate/<candidate-id>/`
record.

Create a workspace:

```powershell
exonym init candidate-alpha --toi <toi> --tic <tic>
exonym track candidate-alpha
```
