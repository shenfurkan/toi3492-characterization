# Process Log

This log records what was done, what was learned, and what should happen next.

## 2026-07-08

### Academic Value Check

- Assessed the current project as academically valuable if framed as an independent candidate characterization rather than confirmation.
- Identified the then-assumed main strengths: evolved-host correction, sub-Saturn radius, self-consistent circular photometric solution, cautious TTV conclusion.
- Identified the main weaknesses: no Gaia contamination check, no centroid vetting, no RV mass, incomplete MCMC diagnostics, no sector-depth consistency.

### Novelty Check

- arXiv exact search for `TOI-3492` returned no direct results.
- arXiv exact search for `TIC 81077799` returned no direct results.
- NASA Exoplanet Archive direct TAP query attempt returned a 400 error; the archive status still needs a clean query or manual check.

### Workflow Correction

- Decided to stop treating LaTeX/arXiv packaging as the active priority.
- Re-centered the project on data verification, methodology learning, literature comparison, figure review, then article drafting.

### Files Created

- `academic_value_assessment.md`
- `research_stages.md`
- `literature_matrix.md`
- `process_log.md`

### Next Step

- Download a small core set of open-access reference PDFs into `literature/`.
- Then extract methodology notes into `literature_matrix.md`.

### Literature Download

Downloaded five core open-access PDFs into `literature/`:

- `Chontos2024_TESSKeck_Subgiants.pdf`, 22 pages
- `Wittenmyer2021_TOI1842b_EvolvingSubgiant.pdf`, 28 pages
- `Thomas2025_TOI5108_TOI5786_SubSaturns.pdf`, 25 pages
- `LilloBox2024_AstraLux_TESS_Companions.pdf`, 10 pages
- `Ross2023_DEATHSTAR_TESS_FalsePositives.pdf`, 17 pages

Created `literature_reading_notes.md` as the extraction notebook.

### First-Pass Literature Method Scan

Scanned section headings and method keywords from the five downloaded PDFs. The scan shows that professional TESS characterization papers commonly include:

- TESS photometry section.
- Ground-based photometry or high-resolution imaging where available.
- Spectroscopy and/or radial velocities for confirmation papers.
- Gaia and broadband photometry for stellar characterization.
- Explicit false-positive screening.
- Clear distinction between candidate characterization and confirmed planetary nature.

Immediate implication: the TOI-3492.01 paper has academic value as a candidate characterization, but it must not be framed like the confirmation papers unless additional validation is added.

### Stage 1 Data Verification

Created and ran:

- `data_verification.py`
- `period_harmonic_check.py`

Generated:

- `data_verification_results.json`
- `period_harmonic_results.json`
- `toi3492_period_harmonic_check.png`
- `data_verification_report.md`

Main result: TIC stellar parameters strongly support an evolved host, and the adopted circular transit geometry is self-consistent if P = 9.222 d is correct.

### Official Metadata and 120 s Alias Follow-Up

Queried NASA Exoplanet Archive and ExoFOP for TOI-3492.01 / TIC 81077799.

Official status:

- TFOPWG disposition: PC.
- Period: 9.2224171 d.
- Duration: 5.296858 h.
- Depth: 3109.8 ppm.
- Radius: 15.65 Rearth.
- ExoFOP says confirmed planets: N/A.
- ExoFOP TIC contamination ratio: 0.019471.

Created and ran `alias_120s_analysis.py` using only 120 s SPOC products. Result: BLS selects the official 9.222 d period in all tested modes.

### Corrected 120 s Reference Light Curve and Transit Refit

Built a corrected 120 s-only reference light curve from the six SPOC 120 s products: Sectors 37, 63, 64, 90, 99, and 100. The reference file has 102,502 rows and is saved as `toi3492_120s_reference.csv`.

Created and ran `transit_model_120s_corrected.py` with the official ephemeris fixed. The working corrected photometric solution is:

- Rp/Rstar = 0.05633 +/- 0.00047.
- Depth = 3173 ppm.
- Rp = 15.93 +/- 0.69 Rearth.
- a/Rstar = 9.226 +/- 0.297.
- Impact parameter = 0.787 +/- 0.017.
- Duration = 5.406 h.
- Mean MCMC acceptance fraction = 0.590.

Ran `transit_model_120s_density_locked.py` as a comparison with a/Rstar fixed by the TIC stellar density. That fit gives Rp = 16.55 +/- 0.70 Rearth and depth = 3421 ppm, but has a worse objective value and more structured ingress/egress residuals. Working interpretation: use the free-geometry corrected 120 s fit as the current photometric solution, while reporting the a/Rstar versus TIC-density tension as a caveat.

Sector-depth check from `toi3492_120s_sector_depths.csv` shows all six sectors have a deep transit, roughly 2490-2874 ppm. The weighted mean is 2692 +/- 26 ppm formally, or +/- 63 ppm after scaling for sector scatter. The corrected large-radius result is not driven by one sector, but the scatter indicates residual systematics.

Updated `data_verification_report.md` and `todo.md` accordingly. Manuscript files were later revised with updated results.

### Manuscript Correction Pass

Updated the main drafts and planning notes with the current solution.

Files updated:

- `professional_article.md`
- `extraplan.md`
- `arxiv_main.tex`
- `plan.md`
- `academic_value_assessment.md`
- `methodology_notes.md`
- `article_phases.md`
- `data_verification_report.md`
- `todo.md`

Current manuscript wording now treats TOI-3492.01 as a plausible giant-planet-size transiting candidate, not a sub-Saturn candidate. The drafts use the corrected 120 s working solution: P = 9.2224171 d, Rp/Rstar = 0.05633 +/- 0.00047, depth = 3173 ppm, Rp = 15.93 +/- 0.69 Rearth, and a/Rstar = 9.23 +/- 0.30. The a/Rstar tension with the TIC-density prediction remains a stated caveat.

Ran a stale-claim scan after edits. Python syntax checks passed for `transit_model_120s_density_locked.py` and `transit_model_120s_corrected.py`. A LaTeX build was attempted, but `pdflatex` is not installed in the current environment.

### Corrected Validation Pass

Added and ran `false_positive_tests_120s.py` using the corrected 120 s reference light curve and the corrected transit model duration. Outputs:

- `false_positive_tests_120s.json`
- `toi3492_120s_event_depths.csv`
- `toi3492_false_positive_120s.png`

The corrected odd/even depth comparison uses 16 transit events and gives odd depth = 2686 +/- 40 ppm, even depth = 2673 +/- 35 ppm, and a 13 ppm difference, or 0.24 sigma. The corrected secondary-eclipse search at phase 0.5 gives 9 +/- 15 ppm, or 0.63 sigma, with a 3-sigma upper limit of 54 ppm. These checks do not show an obvious eclipsing-binary signature.

Added and ran `gaia_contamination_check.py` against Gaia DR3 using the official TOI coordinates. Outputs:

- `gaia_contamination_check.json`
- `gaia_dr3_neighbors.csv`
- `toi3492_gaia_neighbors.png`

The Gaia target match is source 5347362071701193344 at 0.006 arcsec from the TOI coordinate, with parallax 4.9324 +/- 0.0137 mas and RUWE = 0.985. No Gaia source inside 42 arcsec is bright enough to mimic the 3173 ppm signal as a fully eclipsed contaminant. The nearest neighbor is at 7.37 arcsec and is too faint to matter at this depth. One source at 56.29 arcsec could mimic the signal only if nearly fully eclipsed, and several wider-field sources out to 120 arcsec could mimic it in principle. The conclusion at this step was cautious: Gaia was reassuring for close contamination and target astrometry, but TESS centroid/source-localization work was still needed before validation-level claims.

Updated `data_verification_report.md`, `todo.md`, and methodology/planning notes so Gaia and corrected false-positive checks are no longer listed as missing.

### First-Pass TESS Source Localization

Added and ran `tess_source_localization_120s.py` using the six 120 s SPOC target-pixel files. Outputs:

- `tess_source_localization_120s.json`
- `toi3492_120s_difference_centroids.csv`
- `toi3492_tess_difference_images.png`

The script forms median out-of-transit minus in-transit difference images at the official ephemeris and compares the positive difference-image centroid with the target coordinate projected into each target-pixel file. The current rerun gives a median offset of 11.8 arcsec and a largest offset of 22.2 arcsec, about one TESS pixel. This first-pass diagnostic is now supplemented by the SPOC DV dashboard centroid extraction described below.

### Corrected Config Cleanup

Cleaned `config_corrected_120s.json` so the top-level `transit` block now mirrors the 120 s result. Also patched `transit_model_120s_corrected.py` so future reruns preserve this safer config structure.

### Corrected MCMC Autocorrelation Rerun

Patched and reran `transit_model_120s_corrected.py` so the corrected 120 s MCMC now saves both the flat samples and the raw production chain. New outputs:

- `toi3492_raw_chain_120s_corrected.npy`
- `mcmc_diagnostics_120s_corrected.json`

The rerun gives the same rounded photometric solution: Rp/Rstar = 0.05632 +/- 0.00047, depth = 3172 ppm, Rp = 15.93 +/- 0.69 Rearth, a/Rstar = 9.23 +/- 0.29, and b = 0.787 +/- 0.016. The mean acceptance fraction is 0.594. Integrated autocorrelation times are 40.2-42.0 production steps, and the 2500-step production run spans 59.5-62.2 autocorrelation times depending on parameter. This passes the conservative 50-tau reporting heuristic used here.

### Exact Reproducibility Order

Created `reproducibility_order.md` to define the rerun sequence. It separates the current 120 s-only pipeline from legacy scripts and records the current adopted rounded values from `config_corrected_120s.json`.

### Article Draft Rewrite Started

Rewrote `professional_article.md` into a cleaner current-status article draft. The new draft opens with an explicit status note, uses the corrected 120 s result as the current solution, presents the validation checks in a coherent order, and keeps the conclusion at candidate-characterization level. A figure-reference check found eight referenced figures and no missing files. A stale-value check found no active uses of outdated results or sub-Saturn language as the current interpretation.

### Legacy Script Cleanup

Removed obsolete legacy references from active config files and deleted the superseded `outputs/period_harmonic_check.py` / `outputs/period_harmonic_results.json` pair. The current workflow no longer exposes a legacy-audit switch in `run_overnight_pipeline.ps1`, and `utils.load_lightcurve()` now defaults to the corrected 120 s reference light curve.

### SPOC DV Product Extraction

Added and ran `spoc_dv_extract.py` against the local MAST SPOC DV products. The script parses eight DVT FITS files and eight DVR PDF reports, then writes `spoc_dv_summary.json`, `spoc_dv_summary.md`, `spoc_vs_local_comparison.json`, `spoc_dv_transit_metrics.csv`, and `spoc_dv_pdf_metrics.csv`. The strongest multi-sector product, S1-S96 TCE 1, matches the official ephemeris with P=9.22240805 d, depth=3128.3 ppm, Rp=15.66 Rearth, MES=99.4, and DVR dashboard centroid offset 0.90 sigma. This independently supports the corrected deep-transit scale and strengthens the on-target candidate interpretation, while still not constituting RV confirmation.
