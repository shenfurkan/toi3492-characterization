# TOI-3492.01 Current Work List

Last synchronized: 2026-07-23.

This file is a short operational index. Binding scientific history remains in
`../currentproblem.md` and `../currentproblemstage2.md`; the plain-language
review and proposed continuation are in `../analiz.md`.

## Completed and Preserved

- [x] Verify all 18 raw SPOC products and time standards.
- [x] Inventory 18 expected transit windows; retain 16 usable events.
- [x] Complete quality, background, pointing, CBV, and control-star audits.
- [x] Compare four reductions and retain the Phase 4 systematic.
- [x] Preserve the original Phase 5 `FAIL`.
- [x] Carry 24 mask/window/polynomial branches through Phase 5B.
- [x] Complete all 576 Phase 6 kernel-screening folds.
- [x] Preserve the authoritative Phase 6 `FAIL_STATIONARITY` result.
- [x] Run the Phase 6R calculation: 24/24 stationarity followed by
  `FAIL_RESIDUAL_CORRELATION` at maximum beta 1.293606.
- [x] Complete WP-09A formal sector heterogeneity (`PASS`, cause not assigned).
- [x] Remove the central 4.3-sigma, measured-eccentricity, validation,
  confirmation, and asteroseismology claims from the working manuscript.

## Immediate Work

- [x] Synchronize `outputs/release_status.json` with Phase 6R, WP-09A, and the
  Stage-3 scope decision.
- [x] Recreate `EXOPLANET_RELEASE_ROADMAP.md` as the version-neutral methodology
  and release contract.
- [x] Correct the stale Phase 6R paragraph in the canonical TeX.
- [x] Remove the remaining numerical interval derived from an unconverged
  native-cadence analysis.
- [x] Record the dated Stage-3 scope amendment before any new real-data model.
- [x] Create the bounded continuation draft in `../stage3.md`.
- [x] Obtain explicit Stage-3 scope approval for gradual S3-00 through S3-05
  preparation.
- [ ] Obtain the separate S3-06 protocol approval before any new real-data fit.
- [x] Complete S3-00 scope synchronization and machine-readable audit.
- [x] Build and verify the S3-01 immutable input manifest.
- [x] Complete the S3-02 existing-artifact Phase-6 post-mortem without new fits.
- [x] Complete S3-03 by limiting the model architecture to a single Matern-3/2
  candidate with sector-partially-pooled timescales; K0 retained as failed
  reference only; froze before any real-data fit.
- [ ] Freeze and pass the S3-04 synthetic-calibration protocol before any new
  real-data model.
- [ ] Keep Phase 7 closed until a newly authorized Phase 6 model passes its
  frozen gates.
- [ ] Develop the coherent atmosphere/SED/isochrone stellar posterior in
  parallel where it does not depend on Phase 6.

## Scientific Gates

- [ ] Candidate-paper-ready.
- [ ] Final native-cadence geometry ready.
- [ ] Central density/eccentricity claim ready.
- [ ] Statistical-validation-ready.
- [ ] Planet-confirmation-ready.

All gates remain closed. A completed photometric characterization may still end
with an unvalidated and unconfirmed candidate; analysis completion does not
require a planet-validation or mass result.

## External Inputs

- [ ] Independent spectroscopy and metallicity.
- [ ] Speckle/AO contrast curve.
- [ ] Transit-time source-localization imaging where feasible.
- [ ] Target-specific reconnaissance and precision radial velocities.

These external inputs limit localization, validation, and mass claims. Their
absence does not prevent completion of a properly scoped TESS photometric paper.

## Publication Block

Do not build, upload, tag, or cite a new arXiv/Zenodo package until the science
is frozen, the final TeX and PDF pass review, all audits and tests are current,
and a newly generated manifest matches the staged files.
