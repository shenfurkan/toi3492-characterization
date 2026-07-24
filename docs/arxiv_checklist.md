# arXiv Readiness Checklist

Last synchronized: 2026-07-23.

Submission is blocked. No historical audit, ZIP, checksum, PDF, or test count is
accepted as current release evidence.

## Scientific Freeze

- [ ] Record the final scientific scope and close every targeted claim.
- [x] Record the Stage-3 scope amendment; real-data fitting remains closed until
  the separate S3-06 protocol approval.
- [ ] Complete or explicitly close the final noise-model path.
- [ ] Adopt only converged, provenance-bound final numerical results.
- [ ] Keep the candidate unvalidated and unconfirmed unless independent gates
  genuinely change that status.
- [ ] Report no formal FPP, measured mass, measured eccentricity, or on-target
  localization without the required evidence.
- [ ] Keep asteroseismology out of the canonical manuscript unless a new,
  sensitivity-calibrated claim gate is explicitly opened and passed.

## Canonical Manuscript

- [x] `../toi3492_characterization.tex` is the sole canonical manuscript source.
- [x] Correct the stale Phase 6R paragraph.
- [x] Remove or quarantine the remaining unconverged native-cadence interval.
- [ ] Convert to the required current AASTeX format.
- [ ] Freeze all tables, figures, values, captions, and claim language.
- [ ] Complete the full LaTeX/BibTeX build without undefined references.
- [ ] Inspect every page of the generated PDF.

## Current Audits and Tests

- [ ] Run the scientific consistency and claim-boundary audit on final TeX.
- [ ] Run the mathematical audit on final TeX and verify its recorded hash.
- [ ] Run the complete default pytest suite with zero failures.
- [ ] Run available integration tests separately and report any omission.
- [ ] Obtain an independent second-reader claim review.

The current development run is 107 passed. This is not final-release evidence:
the scientific scope, final TeX audits, and release manifest are still open.

## Package Gate

- [ ] Generate a new manifest after the final source freeze.
- [ ] Build a new arXiv source package from an empty staging directory.
- [ ] Compile the staged arXiv source through the full bibliography cycle.
- [ ] Confirm the arXiv ZIP contains only required source, bibliography, and
  referenced figures.
- [ ] Build a new reproducibility package with a newly assigned version.
- [ ] Verify safe ZIP paths, unique entries, CRC, embedded hashes, and offline
  tests after extraction into an empty directory.
- [ ] Generate and independently verify the whole-archive SHA-256 sidecar.

No current `arxiv_submission.zip` or versioned reproducibility ZIP is approved
for upload.

## DOI and Public Archive

- [x] No unresolved DOI is currently claimed.
- [ ] Create the intended Zenodo draft only after package verification.
- [ ] Upload the exact tested files.
- [ ] Publish and verify that the DOI resolves publicly.
- [ ] Download the public files into an empty directory and recheck their hash.
- [ ] Add the DOI to public metadata only after that verification.

## arXiv Submission

- [ ] Obtain endorsement if arXiv requests it.
- [ ] Upload the newly verified arXiv source package.
- [ ] Select the correct TeX engine and inspect arXiv's log and generated PDF.
- [ ] Confirm current title, author, abstract, figures, references, and cautious
  candidate language.
- [ ] Leave the journal DOI blank unless a publisher has assigned one.
- [ ] Mention Zenodo only after its public DOI and downloaded files are verified.

Do not restore historical adopted-fit, 4.3-sigma density, measured-eccentricity,
asteroseismology, simplified FPP, TRICERATOPS-validation, TTV, rotation, or
second-CROWDSAP claims.
