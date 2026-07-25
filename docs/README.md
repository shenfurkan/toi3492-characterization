# TOI-3492.01 Documentation

Last synchronized: 2026-07-25.

This directory contains active operating notes and clearly separated historical
records. It does not override raw artifacts or frozen scientific protocols.

## Authority Order

When records disagree, use this target-science order:

1. Raw inputs and immutable result artifacts.
2. Protocols frozen before the corresponding real-data calculation.
3. `../currentproblem.md` for the original scientific gates.
4. `../currentproblemstage2.md` for the recovery plan and dated execution log.
5. `../stage3.md` after explicit approval for the proposed bounded continuation.
6. The applicable claim charter and `../outputs/release_status.json` for current
   claim permissions.
7. The exact publication-object source for what that manuscript says.
8. `lab/` and other active documents in this directory for operations,
   governance, and publication procedure.

`../outputs/release_status.json` is a working target-state record, not final
release evidence. The cross-project authority map and release-object taxonomy
are in `lab/README.md`.

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
| Stage 3 | Full calibration incomplete; K3 real-data adoption closed by the Stage-4 limited selector audit; real-data work remains closed |
| Stage 4 scoped artifact | `PASS`; RNAAS source, PDF, audit, and bundle exist; lab-wide submission authorization remains conditional |
| Characterization manuscript | Expanded working draft; current source-bound claim/math audit pending |
| Current test snapshot | 176 passed, 10 integration deselected, 0 failed; compact suite green |
| Final calculation wrapper | 59/59 PASS (2026-07-25) |
| Lab operating layer | Installed under `lab/`; current maturity 20/36, `SELF_REVIEW_ONLY`, not certified |
| Formal FPP | Not reported |
| Mass/confirmation | No target-specific RV mass; not confirmed |
| Public DOI | None verified or claimed |
| Release state | RNAAS bundle exists; current lab QA is not green, and no arXiv package, public deposit, DOI, submission, or publication is claimed |

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
| `lab/README.md` | Research-lab authority map and operating-system index |
| `lab/GOVERNANCE.md` | Roles, approvals, change classes, and supersession |
| `lab/RESEARCH_LIFECYCLE.md` | Project lifecycle from intake through archive |
| `lab/QUALITY_SYSTEM.md` | Verification, staleness, and release-object gates |
| `lab/ROADMAP.md` | Immediate, medium, long-term, and multi-project milestones |
| `lab/SELF_ASSESSMENT.md` | Dated maturity score, findings, and corrective actions |
| `templates/` | Reusable project, protocol, run, gate, decision, and handover forms |
| `review/` | Prepared independent-review package; not yet independently reviewed |

## Historical Documents

Superseded narrative and first-pass reading notes are under `archive/`. They are
preserved for provenance and must not be cited as current claim or release
authority.

## Final Verification Commands

Run these only after the scientific values and manuscript are frozen:

```powershell
python -m compileall scripts tests
python scripts/final_calculation_verification.py
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
python scripts/generate_release_manifest.py
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

Old audit output, test counts, manifests, PDFs, ZIPs, or sidecars are not current
evidence after a scientific, manuscript, or documentation change. The current
canonical suite is not green. The release manifest may match the files it lists,
but recursive coverage, clean-room reconstruction, and the Stage-3
input/environment relationship remain open controls until Track 0 in
`lab/ROADMAP.md` is complete.
