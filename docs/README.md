# TOI-3492.01 Documentation

Last synchronized: 2026-07-23.

This directory contains active operating notes and clearly separated historical
records. It does not override raw artifacts or frozen scientific protocols.

## Authority Order

When records disagree, use this order:

1. Raw inputs and immutable result artifacts.
2. Protocols frozen before the corresponding real-data calculation.
3. `../currentproblem.md` for the original scientific gates.
4. `../currentproblemstage2.md` for the recovery plan and dated execution log.
5. `../stage3.md` after explicit approval for the proposed bounded continuation.
6. `../toi3492_characterization.tex` for the current manuscript text.
7. Active documents in this directory for operations and publication procedure.

`../outputs/release_status.json` is synchronized through S3-02. It is a
working-state record, not final release evidence.

## Current State

| Item | Current state |
|---|---|
| Scientific status | Working draft under remediation |
| Supported signal claim | Persistent transit-like signal in six 120-s TESS sectors |
| Object status | Unvalidated and unconfirmed candidate |
| Phase 0 | Major wording corrections applied; final claim/math audits remain stale |
| Phases 1-3 | `PASS` |
| Phase 4 | `CONDITIONAL_PASS`; reduction systematic retained |
| Original Phase 5 | `FAIL`; no single window/baseline model adopted |
| Phase 5B | `CONDITIONAL_CONTINUE`; 24 discrete branches retained |
| Phase 6 | `FAIL_STATIONARITY`; 576/576 screening folds completed |
| Phase 6R calculation | 24/24 stationarity, then `FAIL_RESIDUAL_CORRELATION` |
| Phase 6R beta | Maximum weighted beta 1.293606 at 80 minutes; threshold 1.2 |
| Phase 6R provenance | Required standalone preregistration/audit package is incomplete |
| WP-09A | `PASS`, formal sector heterogeneity only; cause not assigned |
| Phase 7 | Closed under the current Stage-2 plan |
| Current Stage-2 path | Path B after the Phase 6R stop rule |
| Proposed continuation | Dated Stage-3 scope amendment approved |
| Stage 3 | `PROTOCOL_ONLY`; S3-00 through S3-04A `PASS`; S3-04B next; real-data work closed |
| Current test run | 165 passed |
| Formal FPP | Not reported |
| Mass/confirmation | No target-specific RV mass; not confirmed |
| Public DOI | None verified or claimed |
| Release state | No arXiv or reproducibility package is ready |

The full plain-language scientific review and approved bounded continuation are
in `../analiz.md` and `../stage3.md`. The historical Stage-2 stop record remains
preserved; the dated Stage-3 amendment is recorded separately.

## Active Documents

| File | Purpose |
|---|---|
| `todo.md` | Current operational work only |
| `reproducibility_order.md` | Safe verification order and artifact status |
| `publication_process_howto.md` | Version-neutral publication runbook |
| `arxiv_checklist.md` | Submission gate; all release evidence must be current |
| `literature_matrix.md` | Active literature tracking |
| `potansiyel.md` | Separate future-target planning |

## Historical Documents

Superseded narrative and first-pass reading notes are under `archive/`. They are
preserved for provenance and must not be cited as current claim or release
authority.

## Final Verification Commands

Run these only after the scientific values and manuscript are frozen:

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
python scripts/generate_release_manifest.py
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

Old audit output, test counts, manifests, PDFs, ZIPs, or sidecars are not current
evidence after a scientific, manuscript, or documentation change. The current
tests pass, but the release manifest still contains the superseded roadmap hash
and remains stale until final scientific freeze.
