# TOI-3492.01 Documentation

This directory contains operational runbooks, methodology notes, literature
tracking, and clearly separated historical records for the TOI-3492.01 project.

## Authority Order

When documents disagree, use this order:

1. `../toi3492_characterization.tex` and its compiled PDF for manuscript text.
2. `../outputs/release_status.json` for machine-readable claim and release gates.
3. `../outputs/manuscript_math_audit.json` for the bound mathematical audit.
4. `../REVIEW_NOTES.md` for the detailed review history and decisions.
5. `../EXOPLANET_RELEASE_ROADMAP.md` for reusable release standards.
6. Active documents in this directory for procedures and supporting notes.

Files under `archive/` are historical and never override current sources.
`../data/toi3492_characterization_qa.tex` is noncanonical and excluded from
public packages.

## Current Verified State

Last synchronized: 2026-07-14.

| Item | Current state |
|---|---|
| Release version | `v1.0.1` |
| Canonical PDF | 22 pages, 6 figures |
| Strongest supported gate | `descriptive_candidate_preprint` |
| Scientific audit | PASS |
| Mathematical audit | PASS, 276 expressions and 761 numeric tokens |
| Default tests | 27 passed, 1 deselected |
| Adopted fit window | +/-13 h, 26 h total |
| Sensitivity fit window | +/-6.5 h, 13 h total; converged and nonadopted |
| Window sensitivity | `Rp/Rstar` shift of 1.95 adopted posterior half-widths |
| Formal FPP | Not reported |
| Confirmation status | Unvalidated and unconfirmed candidate; no RV mass |
| Public DOI | None verified or claimed |

The local reproducibility package is
`../toi3492_reproducible_release_v1.0.1.zip`. Its adjacent `.sha256` sidecar is
the checksum authority. Local package readiness does not imply that a Zenodo or
other public archive deposit has been published or verified.

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

See `archive/README.md`. Historical documents preserve old values and claims
as provenance, but their commands and scientific interpretations are not
current.

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

Expected default verification results are the values in the table above. Any
change to a manifest-listed file invalidates the existing manifest, release
ZIP, and checksum sidecar until they are rebuilt.
