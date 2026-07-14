# arXiv Readiness Checklist

Last synchronized: 2026-07-14 after the final mathematical, editorial, package,
and documentation audits.

Authoritative decisions are in `../REVIEW_NOTES.md`; the machine-readable gate
is `../outputs/release_status.json`. Local package readiness does not mean that
a public Zenodo record or DOI has been verified.

## Canonical Manuscript Gate

- [x] `toi3492_characterization.tex` is the sole canonical manuscript.
- [x] `data/toi3492_characterization_qa.tex` is noncanonical and excluded.
- [x] The canonical source completes the full PDFLaTeX/BibTeX build cycle.
- [x] The local PDF is 22 pages with 6 figures.
- [x] No undefined citations, undefined references, box warnings, or document
  errors remain in the final log.
- [x] The PDF received page-level visual and parsed-text review.

## Supported Scientific Scope

- [x] Descriptive, unvalidated, unconfirmed candidate characterization.
- [x] Candidate radius is conditional on the event being planetary and on the
  target, stellar model, and dilution assumptions.
- [x] No calibrated population FPP is reported.
- [x] No RV mass, measured eccentricity, or formal target localization is
  reported.
- [x] The density discrepancy is model conditional and a follow-up motivation,
  not a calibrated sigma result or central discovery claim.
- [x] Native-cadence fits are labeled diagnostic and unconverged.
- [x] Asteroseismic results are labeled preliminary and non-constraining.

## Window-Definition Gate

- [x] Adopted window is +/-13 h, or 26 h total.
- [x] Alternative window is +/-6.5 h, or 13 h total.
- [x] The alternative full MCMC is converged and explicitly nonadopted.
- [x] The 1.95 adopted-half-width `Rp/Rstar` shift is disclosed.
- [x] Adopted statistical intervals are not represented as including window
  choice.

## Audit and Test Gate

- [x] Scientific consistency and claim-boundary audit: PASS.
- [x] Mathematical audit: PASS.
- [x] Mathematical inventory: 276 expressions and 761 numeric tokens.
- [x] Default test suite: 27 passed, 1 deselected.
- [x] The deselected raw-SPOC integration test is identified separately rather
  than represented as passed.

## Package Gate

- [x] `arxiv_submission.zip` contains canonical TeX, bibliography, and only the
  six referenced figures.
- [x] Staged arXiv source completes `pdflatex -> bibtex -> pdflatex -> pdflatex`.
- [x] No local absolute paths are present.
- [x] arXiv ZIP CRC passes.
- [x] Current reproducibility package is
  `toi3492_reproducible_release_v1.0.1.zip`.
- [x] Manifest hashes and embedded release hashes pass.
- [x] Reproducibility ZIP extracts into an empty directory and returns
  27 passed, 1 deselected.
- [x] The adjacent `v1.0.1` SHA-256 sidecar is the checksum authority.
- [x] Repository `docs/` are intentionally not part of the compact release ZIP.

## DOI and Public-Archive Gate

- [x] No unresolved DOI is claimed in the manuscript, `README.md`, or
  `CITATION.cff`.
- [ ] Corrected `v1.0.1` files are uploaded to the intended public record.
- [ ] The record is published and its DOI resolves publicly.
- [ ] Public ZIP and sidecar are downloaded and independently verified.
- [ ] Only after verification is the DOI inserted consistently into public
  metadata and the manuscript.

## Material Controls Still Incomplete

- [ ] Converged native-cadence circular and eccentric posteriors.
- [ ] Event-level timing-offset and marginalized correlated-noise model.
- [ ] Alternative limb-darkening atmosphere prescription.
- [ ] Hierarchical sector-depth scatter and marginalized dilution.
- [ ] Coherent atmosphere/isochrone stellar posterior.
- [ ] Secondary-eclipse scan over eccentric phases.
- [ ] Calibrated PRF source localization and high-resolution contrast curve.
- [ ] Complete preregistered seismic detection gates.
- [ ] Calibrated population FPP and target-specific radial velocities.

## Submission Actions

- [ ] Obtain arXiv endorsement if requested.
- [ ] Upload `arxiv_submission.zip`, not the reproducibility ZIP.
- [ ] Select PDFLaTeX and inspect arXiv's generated log and PDF.
- [ ] Confirm title, author, abstract, 22-page count, six figures, references,
  and conservative candidate language.
- [ ] Leave article DOI blank unless a journal publisher has assigned one.
- [ ] Mention a supporting Zenodo package only after its public DOI and files
  have been verified.

Do not restore obsolete 2.6-sigma, grazing-eccentric, rotation, TTV, simplified
FPP, TRICERATOPS, or second-CROWDSAP claims from historical documents.
