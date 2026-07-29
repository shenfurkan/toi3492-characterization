# Decision Log

Version: 1.0

Last reviewed: 2026-07-25

## Use

This is an append-only index. It links decisions to authoritative evidence and
does not replace detailed target-specific records. New entries use
`LAB-DEC-NNN` and the template at `../templates/decision-record.md`.

| ID | Date | Scope | Decision | Status | Evidence | Supersession |
|---|---|---|---|---|---|---|
| LAB-DEC-001 | 2026-07-23 | Target science | Preserve Phase 5 `FAIL`; no single window/polynomial model adopted | Active | `../../outputs/faz5_window_polynomial_grid.json` | None |
| LAB-DEC-002 | 2026-07-23 | Target science | Carry 24 correlated specification branches through Phase 5B without multiplying them as independent data | Active | `../../outputs/faz5b_remediation.json` | None |
| LAB-DEC-003 | 2026-07-23 | Target science | Preserve Phase 6 `FAIL_STATIONARITY` and Phase 6R `FAIL_RESIDUAL_CORRELATION`; keep Phase 7 closed | Active | `../../outputs/faz6_gate_audit.json`, `../../outputs/faz6r_result.json` | None |
| LAB-DEC-004 | 2026-07-23 | Method development | Permit bounded Stage 3 development only after synthetic calibration and separate real-data approval | Active | `../../stage3.md`, `../../data/stage3_model_architecture_decision.json` | Historical Stage-2 Path B remains preserved |
| LAB-DEC-005 | 2026-07-24 | Publication | Separate the RNAAS candidate note from the extended characterization manuscript | Active | `../../stage4.md`, `../../toi3492_rnaas.tex`, `../../toi3492_characterization.tex` | None |
| LAB-DEC-006 | 2026-07-24 | Claim control | Report no formal FPP; quarantine failed or uncalibrated TRICERATOPS/minimal-FPP experiments | Active | `../../outputs/statistical_validation_120s.json`, `../../outputs/release_status.json` | None |
| LAB-DEC-007 | 2026-07-25 | Lab governance | Add a lab operating layer without moving or rewriting frozen target records | Active | `README.md`, `GOVERNANCE.md` | None |
| LAB-DEC-008 | 2026-07-25 | Readiness | Distinguish candidate note, characterization, software, archive, DOI, validation, and confirmation readiness | Active | `README.md`, `QUALITY_SYSTEM.md` | Replaces ambiguous generic release-ready wording for lab operations |
| LAB-DEC-009 | 2026-07-25 | Review | Label current lab maturity `SELF_REVIEW_ONLY` until a second verifier is assigned | Active | `SELF_ASSESSMENT.md`, `lab_status.json` | None |

## Required Fields for New Decisions

1. Stable ID and date.
2. Question and scope.
3. Alternatives considered.
4. Prior result exposure.
5. Decision and rationale.
6. Evidence and exact hashes where material.
7. Claims and release objects affected.
8. Owner, approver, and reviewer.
9. Stop condition and review date.
10. Supersedes and superseded-by links.
