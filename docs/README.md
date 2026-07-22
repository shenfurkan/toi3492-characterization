# TOI-3492.01 Documentation

This directory contains operational runbooks, methodology notes, literature
tracking, and clearly separated historical records for the TOI-3492.01 project.

## Authority Order

When documents disagree, use this order:

1. `../currentproblem.md` for the active problem list, claim matrix, and phase gates.
2. `../toi3492_characterization.tex` for the current, not-yet-final manuscript text.
3. `../outputs/release_status.json` for machine-readable claim gates.
4. `../EXOPLANET_RELEASE_ROADMAP.md` for reusable release standards.
5. Active documents in this directory for procedures and supporting notes.

Historical drafts and the former noncanonical QA source were consolidated into
`../toi3492_legacy_material_20260722.zip`. They never override current sources;
see `../LEGACY_ARCHIVE.md`.

## Current Verified State

Last synchronized: 2026-07-22.

| Item | Current state |
|---|---|
| State | Scientific remediation in progress |
| Active plan | 26 problems and 31 phases in `currentproblem.md` |
| Canonical source | Existing article draft; AASTeX conversion pending |
| Canonical PDF | Removed as superseded; rebuild after scientific values freeze |
| Strongest supported wording | Descriptive, unvalidated, unconfirmed candidate |
| Phase 0 claim gate | FAIL; unsafe and incomplete claims remain in the draft |
| Phases 1-3 | PASS |
| Phase 4 | CONDITIONAL_PASS; reduction systematic propagated |
| Original Phase 5 | FAIL; retained-model median coverage gate failed |
| Phase 5B | CONDITIONAL_CONTINUE; 24 discrete mask/window/polynomial branches handed to Phase 6 |
| Scientific audit | Stale; rerun after remediation |
| Mathematical audit | Stale; recorded TeX hash does not match the current source |
| Default tests | Full pytest suite: 57/57 passed |
| Active baseline/window treatment | No single adopted cell; discrete Phase 5B nuisance handoff |
| Cadence-mask treatment | 102562 raw-valid and 102502 historical-reference branches, weight 0.5 each |
| Formal FPP | Not reported |
| Confirmation status | Unvalidated and unconfirmed candidate; no RV mass |
| Public DOI | None verified or claimed |

No current reproducibility or arXiv package is release-ready. New packages must
be built only after the scientific phases, AASTeX conversion, audits, and tests
are complete.

## Active Documents

| File | Purpose |
|---|---|
| `todo.md` | Current completed and outstanding work |
| `reproducibility_order.md` | Supported rerun and release-verification order |
| `publication_process_howto.md` | Project publication, arXiv, and archive runbook |
| `arxiv_checklist.md` | Conservative submission gate |
| `methodology_notes.md` | Method references mapped to the current analysis |
| `literature_matrix.md` | Literature tracking and implementation status |
| `literature_reading_notes.md` | Reading notes and project implications |
| `arxiv_endorsement_email.txt` | Endorsement-request template |
| `potansiyel.md` | Separate planning document for future targets |

## Historical Documents

See `../LEGACY_ARCHIVE.md`. Historical documents preserve old values and claims
inside one noncanonical ZIP, but their commands and scientific interpretations
are not current.

## Core Verification Commands

Run from the repository root:

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
python scripts/generate_release_manifest.py
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

These commands are final verification steps, not publication-ready claims. The
manifest was regenerated for the Phase 5B source snapshot; any subsequent
scientific or manuscript change invalidates it until regeneration and testing.
