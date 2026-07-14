# TOI-3492.01 Current Work List

Last synchronized: 2026-07-14. Historical task lists are preserved under
`archive/`; this file contains only the current project state.

## Verified Complete

- [x] Adopt `toi3492_characterization.tex` as the sole canonical manuscript.
- [x] Build the six-sector 120-s reference light curve and adopted circular
  transit fit without a stellar-density prior.
- [x] Verify adopted-chain convergence and retain 252,000 posterior samples.
- [x] Complete the same-pixel 20-s cadence-product consistency check.
- [x] Complete native-cadence 120-s and 20-s robustness fits and label their
  short chains nonadopted.
- [x] Quantify bin-size and fit-window sensitivity.
- [x] Run a converged nonadopted +/-6.5 h window fit and document the 1.95
  adopted-posterior-half-width shift in `Rp/Rstar`.
- [x] Complete odd/even, phase-0.5 secondary-eclipse, SPOC DV, Gaia neighbor,
  difference-image, and source-specific aperture diagnostics.
- [x] Complete the all-phase harmonic regression and label it
  systematics-limited rather than a physical phase-curve detection.
- [x] Avoid a second CROWDSAP correction; retain residual dilution only as a
  sensitivity calculation.
- [x] Freeze TIC v8 provenance and identify metallicity as a limb-darkening
  interpolation assumption rather than a measurement.
- [x] Complete the approximate SED radius-scale check and label it non-isochrone.
- [x] Complete the preliminary asteroseismic search and injection/recovery
  analysis; report neither a detection nor a constraining non-detection.
- [x] Quarantine TTV, stellar-activity, and TRICERATOPS branches from adopted
  release claims.
- [x] Complete the scientific consistency audit.
- [x] Complete the manuscript mathematics audit: PASS, 276 expressions and 761
  numeric tokens.
- [x] Compile and visually inspect the 22-page canonical PDF.
- [x] Pass the default test suite: 27 passed, 1 deselected.
- [x] Build and verify `arxiv_submission.zip`.
- [x] Build and clean-room test
  `toi3492_reproducible_release_v1.0.1.zip` and its SHA-256 sidecar.
- [x] Exclude `data/toi3492_characterization_qa.tex` from canonical and release
  use.

## Publication Actions Still Open

- [ ] Decide whether to publish the current preprint on arXiv.
- [ ] Obtain arXiv endorsement if the account requires it.
- [ ] Publish or replace the corrected Zenodo draft with the exact `v1.0.1`
  package and checksum sidecar.
- [ ] Verify the public Zenodo download and DOI independently before adding a
  DOI to the manuscript, `README.md`, `CITATION.cff`, or arXiv comments.
- [ ] Inspect arXiv's generated PDF against the local 22-page PDF before final
  submission.
- [ ] If journal submission is pursued, convert the canonical source to the
  journal's current class without changing the scientific claim boundary.

## Scientific Follow-Up Needed for Stronger Claims

- [ ] Obtain reconnaissance and precision radial velocities for mass,
  eccentricity, and blend assessment.
- [ ] Obtain high-resolution imaging and a contrast curve.
- [ ] Perform calibrated TESS PRF source localization.
- [ ] Obtain independent spectroscopy and a coherent isochrone posterior for
  the host star.
- [ ] Refit event-level timing, correlated noise, baselines, limb darkening,
  dilution, and hierarchical sector-depth scatter if the density discrepancy
  becomes a central claim.
- [ ] Scan secondary-eclipse phases allowed by eccentric orbits if needed for
  validation-level vetting.
- [ ] Run a calibrated population false-positive model only after the required
  source-localization and companion constraints exist.

## Optional Extensions

- [ ] Add a carefully selected radius-period context figure if it supports the
  descriptive candidate framing and includes an explicit selection caveat.
- [ ] Expand comparison with confirmed evolved-host systems after follow-up.
- [ ] Complete additional literature extraction where it changes a method or
  limitation, not merely the reference count.

## Binding Done Criteria

- The object remains described as an unvalidated and unconfirmed transiting
  candidate.
- No calibrated FPP, measured mass, measured eccentricity, or formal target
  localization is claimed.
- The adopted fit window is always described as +/-13 h, or 26 h total.
- The +/-6.5 h, 13-h-total fit remains a nonadopted sensitivity result.
- The density discrepancy remains model conditional and a follow-up motivation.
- Every manifest-listed file matches `provenance/SHA256SUMS.json` before a
  release package is uploaded.
- A DOI is publicized only after the intended corrected deposit resolves and
  its downloaded files pass independent hash verification.
