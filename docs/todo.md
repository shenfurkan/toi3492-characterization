# TOI-3492.01 Todo List

## High Priority

- [x] Assess academic value in `academic_value_assessment.md`.
- [x] Create staged research workflow in `research_stages.md`.
- [x] Create literature tracking matrix in `literature_matrix.md`.
- [x] Create process monitor in `process_log.md`.
- [x] Confirm current pipeline state with `verify_final.py`.
- [x] Identify the primary exoplanet-methodology book.
- [x] Decide against full PDF-to-Markdown conversion for now.
- [x] Create `plan.md`.
- [x] Create and maintain `methodology_notes.md`.
- [x] Add methodology framework text to `extraplan.md`.
- [x] Add derived physical parameters to the results section.
- [x] Create 10-phase article-to-arXiv plan in `article_phases.md`.
- [x] Create professional article-first manuscript in `professional_article.md`.
- [x] Start arXiv LaTeX source in `arxiv_main.tex`.
- [x] Create BibTeX reference file in `references.bib`.
- [x] Create arXiv readiness checklist in `arxiv_checklist.md`.
- [x] Run Gaia DR3 neighbor/RUWE/contamination check.
- [x] Run corrected odd/even transit-depth comparison on the 120 s reference light curve.
- [x] Run corrected secondary-eclipse search on the 120 s reference light curve.
- [x] Run first-pass TESS difference-image source-localization check.
- [x] Extract formal SPOC DV dashboard centroid products from local DVT/DVR files.
- [ ] Improve source localization with independent PRF modeling if publication-quality validation is needed.
- [x] Improve corrected MCMC diagnostics, including autocorrelation time.
- [x] Add sector-by-sector transit-depth consistency check.
- [x] Document first-pass MCMC quality diagnostics.
- [x] Download selected open-access reference papers into `literature/`.
- [ ] Extract methodology notes from selected reference papers.
- [x] Create data verification report before further article drafting.
- [x] Resolve BLS period ambiguity.
- [x] Rebuild reference light curve using 120 s SPOC products only.
- [x] Refit transit depth/radius from corrected 120 s analysis.
- [x] Revise manuscripts with updated results.
- [x] Remove formal-validation and genuine-planet overclaims from `arxiv_main.tex`.
- [x] Run TRICERATOPS screening check (`N=100000`, search radius 4 TESS pixels).

## Medium Priority

- [x] Fix wording in `verify_final.py` so circular orbit is not justified by overconfident tidal circularization language.
- [x] Add a reproducibility section with exact script order.
- [ ] Add figure captions that explain what each diagnostic demonstrates.
- [x] Remove obsolete `toi3492_unflattened.csv` / `toi3492_cleaned.csv` references from active config files.
- [x] Clean `config_corrected_120s.json` so stale old transit values cannot be accidentally reused.
- [ ] Consider a phase-curve/ellipsoidal-variation diagnostic if the data quality supports it.

## Low Priority

- [ ] Improve references into a consistent journal style.
- [ ] Add a radius-period context plot against confirmed exoplanets.
- [ ] Try exact TESS-band limb-darkening interpolation from Claret tables if practical.
- [ ] Add stellar-evolution context for the subgiant host.

## Done Criteria

- The paper describes TOI-3492.01 as a candidate, not a confirmed planet.
- Every major methodological choice has either a literature basis or an explicit practical justification.
- The analysis can be rerun from documented scripts and local files, except where network-dependent catalog queries are clearly marked.
- Remaining limitations are stated plainly: no RV mass, no full centroid validation, no high-resolution imaging contrast curve, and unresolved a/Rstar tension.
