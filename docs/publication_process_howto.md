# TOI-3492.01 Publication Process

Last synchronized: 2026-07-23.

This is a version-neutral operator runbook. It intentionally contains no fixed
release version, historical package filename, test count, DOI, arXiv identifier,
or copy-ready endorsement message.

No current release is ready.

## 1. Publication Objects

The project may publish three different objects:

| Object | Destination | Identifier |
|---|---|---|
| Reproducibility package | Zenodo | Zenodo version DOI and possibly concept DOI |
| Manuscript preprint | arXiv | arXiv identifier |
| Journal article | Journal submission system | Publisher DOI after publication |

These identifiers are not interchangeable. A Zenodo DOI must not be entered as
the journal-article DOI.

## 2. Scientific Release Gate

Do not begin release packaging until all are true:

1. The final scientific scope is recorded.
2. Every targeted claim is passed, removed, not claimed, or blocked externally.
3. No unconverged chain supplies a final interval.
4. The manuscript matches the adopted artifacts.
5. The object is described as unvalidated and unconfirmed unless independent
   evidence has genuinely changed that state.
6. Formal FPP, source localization, eccentricity, and mass appear only if their
   own gates pass.
7. `outputs/release_status.json` is synchronized with Phase 6R and WP-09A.
8. Final claim and mathematical audits pass on the exact final TeX hash.
9. The complete test suite passes.

Current supported wording is limited to a persistent transit-like signal in six
TESS sectors and conditional companion-scale interpretation. The final wording
must be taken from the scientifically frozen manuscript, not this runbook.

## 3. Assign Release Identity

After scientific freeze, assign one new version and use it consistently in:

- package filename;
- `pyproject.toml` or other project metadata where applicable;
- `CITATION.cff`;
- Zenodo metadata;
- Git tag;
- schema/release status;
- manuscript availability statement.

Do not reuse a historical version merely because old instructions contain it.

## 4. License Gate

Keep the existing license split:

| Artifact | License or treatment |
|---|---|
| Code in `scripts/` and `tests/` | MIT |
| Original manuscript, figures, narrative docs, and derived tables | CC BY 4.0 |
| TESS, Gaia, ExoFOP, and other upstream products | Their original terms |

Verify `LICENSE`, `LICENSES.md`, acknowledgements, and archive metadata agree.
Do not relicense third-party inputs.

## 5. Build and Verify Locally

Run from the repository root after scientific freeze:

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
python scripts/generate_release_manifest.py
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

Requirements:

1. Compile the canonical manuscript through the full bibliography cycle.
2. Inspect the local PDF page by page.
3. Build from an empty staging directory.
4. Reject undeclared, duplicate, absolute, or parent-traversal archive paths.
5. Verify ZIP CRC and every embedded hash.
6. Extract each archive into a new empty directory.
7. Run the documented offline suite from the extracted package.
8. Compile the staged arXiv source, not only the working-tree source.
9. Generate and independently verify a whole-archive SHA-256 sidecar.

Use actual command output. Never paste historical test counts or audit PASS text
into a checklist.

## 6. Zenodo Draft

Create the draft only after the exact local package passes verification.

Enter:

- resource type appropriate to the reproducibility package;
- current package title and version;
- actual publication date;
- creator name, affiliation, and ORCID where available;
- repository URL;
- conservative abstract/description copied from the frozen manuscript;
- explicit license matrix;
- related identifiers that genuinely exist.

Do not upload literature PDFs, credentials, API tokens, endorsement codes,
LaTeX intermediates, caches, or undeclared raw archive products.

### DOI rule

A reserved DOI is not yet a verified public DOI. Keep it out of public
manuscript and citation metadata until:

1. The record is published.
2. The DOI resolves publicly.
3. The public files are downloaded into an empty directory.
4. The downloaded ZIP matches its sidecar.
5. The intended title, creator, version, license, and files are confirmed.

Only then update `CITATION.cff`, the repository README, and the manuscript
availability statement. Regenerate any package whose contents changed.

## 7. arXiv Submission

Upload the verified arXiv source package, not the reproducibility ZIP.

Before submitting:

1. Use the title and abstract from the final canonical manuscript.
2. Select the appropriate category, normally `astro-ph.EP` for this project.
3. Obtain endorsement only if arXiv requests it.
4. Send any endorsement request privately and never commit its active code.
5. Let arXiv identify the top-level TeX source.
6. Select the correct TeX engine.
7. Inspect all warnings and the generated PDF.
8. Confirm figures, citations, author, title, abstract, and availability text.
9. Leave journal reference and article DOI blank until they genuinely exist.
10. Mention Zenodo only after its DOI and public files pass verification.

If an error is found before announcement, correct the existing submission rather
than creating a duplicate. After announcement, use arXiv replacement versions.

## 8. Journal Submission

Journal submission is separate from Zenodo community curation and arXiv.

Before submission:

1. Read the selected journal's current author instructions.
2. Convert to its current supported manuscript class, including AASTeX where
   required.
3. Preserve the frozen scientific claims during conversion.
4. Prepare machine-readable tables and figure data when required.
5. Resolve single- versus dual-anonymous review before exposing identity through
   review-only links.
6. Cite the verified reproducibility package according to journal instructions.
7. Submit through the journal portal, not the Zenodo community page.

The publisher assigns the article DOI only after publication.

## 9. Version and Correction Policy

Every public release must be immutable. If file contents or scientific results
change:

1. Preserve the old version.
2. Record the affected claims and files.
3. Assign a new release version.
4. Regenerate manifests, packages, sidecars, and tests.
5. Create a new Zenodo version.
6. Use an arXiv replacement for the same paper.
7. Update related identifiers after verification.

Do not silently replace files, move a public tag, or rewrite old failure
artifacts.

## 10. Stop Conditions

Stop and do not publish if any of these is true:

- scientific scope is unresolved;
- current audits or tests fail;
- the manuscript hash differs from the audited hash;
- release status conflicts with authoritative artifacts;
- a final number comes from an unconverged or diagnostic-only chain;
- a package contains secrets, local absolute paths, or undeclared files;
- ZIP and sidecar hashes disagree;
- the staged arXiv source does not compile to the inspected PDF;
- metadata calls the candidate validated, confirmed, on-target, eccentric, or
  mass-measured without the required evidence;
- uploaded files differ from tested files;
- a DOI is unresolved or points to the wrong record.

## 11. Final Checklist

### Science and manuscript

- [ ] Scientific scope frozen.
- [ ] Final TeX, tables, and figures frozen.
- [ ] Claim audit passed on final hash.
- [ ] Mathematical audit passed on final hash.
- [ ] Tests passed.
- [ ] PDF compiled and visually inspected.

### Packages

- [ ] New version assigned consistently.
- [ ] Manifest generated after freeze.
- [ ] arXiv source package compiled from staging.
- [ ] Reproducibility package extracted and tested cleanly.
- [ ] Whole-archive hash independently verified.

### Public records

- [ ] Zenodo metadata and files reviewed.
- [ ] Public DOI resolved and downloaded files verified.
- [ ] arXiv-generated PDF inspected.
- [ ] Journal submission prepared separately if pursued.
- [ ] GitHub, CFF, Zenodo, arXiv, and journal identifiers synchronized only
  after they exist.

## 12. Official References

Recheck immediately before submission because interfaces and policies change:

- Zenodo DOI reservation: `https://help.zenodo.org/docs/deposit/describe-records/reserve-doi/`
- AAS Journals Data Guide: `https://journals.aas.org/data-guide/`
- AAS submission guidance: `https://journals.aas.org/submission/`
- arXiv endorsement: `https://info.arxiv.org/help/endorsement.html`
- arXiv submission: `https://info.arxiv.org/help/submit/`
