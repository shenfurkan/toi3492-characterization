# TOI-3492.01: Photometric Characterization of an Unvalidated and Unconfirmed Transit Candidate

An independent photometric analysis of TESS Object of Interest TOI-3492.01
(TIC 81077799). Catalog parameters are consistent with a large, evolved
F-type target, but the source and planetary nature of the signal are unconfirmed.

**Status:** Scientific remediation in progress. The object remains unvalidated
and unconfirmed; source localization, RVs, and high-resolution imaging are still
needed.

## Quick Summary

| Quantity | Value |
|---:|---|
| Period | 9.2224171 d (official TOI) |
| Rp/Rs | 0.05472 +/- 0.00049 (diagnostic folded reference model) |
| Mid-transit model depth | 3094 ppm (same conditional reference model) |
| Rp | 15.47 +/- 0.66 Rearth only if planetary, on the catalog target, and under the adopted stellar/dilution assumptions |
| Circular-fit a/Rs | 10.60 +/- 0.45 (diagnostic reference model) |
| Impact parameter b | 0.705 +/- 0.032 (diagnostic reference model) |
| Formal FPP | Not reported; current diagnostics are not a calibrated population model |
| Key caveat | Circular transit density is about 2.6 times the catalog-model density, but a converged total-width 13-h fit shifts Rp/Rs by 1.95 adopted posterior half-widths; no calibrated significance is claimed |

These intervals are not final native-cadence system parameters. The active
problem list and quantitative acceptance gates are in `currentproblem.md`.

## Repository Structure

```
.
├── references.bib       # BibTeX bibliography
├── data/
│   ├── config_corrected_120s.json  # Stellar inputs and adopted transit solution
│   ├── toi3492_120s_reference.csv  # Corrected 120s light curve
│   └── *.npy            # MCMC chains
├── scripts/
│   ├── audit_science_consistency.py  # Comprehensive verification
│   ├── transit_model_120s_corrected.py  # MCMC transit fit
│   └── ...              # Full pipeline (see below)
├── figures/             # Active manuscript and diagnostic plots
├── outputs/             # JSON/CSV results from each pipeline step
└── docs/                # Methodology notes and checklists
```

The release includes the canonical LaTeX source and machine-readable outputs.
Literature PDFs and LaTeX build intermediates are excluded.

The reusable end-to-end workflow, claim gates, stop rules, and safe/unsafe
release practices are documented in `EXOPLANET_RELEASE_ROADMAP.md`.

## Pipeline and Status

Run from project root with Python 3.9.x. Existing outputs are a remediation
baseline rather than a release-ready final analysis; network scripts are
regeneration utilities.

| Stage | Script | Status and product |
|---:|---|---|
| 1 | `scripts/build_120s_reference_lightcurve.py` | Network regeneration of the six-sector 120-s reference CSV; frozen CSV is included |
| 2 | `scripts/check_20s_independent.py` | Same-pixel 20-s cadence-product consistency data and summaries |
| 3 | `scripts/transit_model_120s_corrected.py` | Adopted converged folded/binned circular reference fit; no stellar-density prior |
| 4 | `scripts/transit_fit_robust.py` | Native-cadence 120-s and 20-s diagnostic fits; not adopted because chains are unconverged |
| 5 | `scripts/transit_stability_checks.py` | Window/bin perturbation diagnostics |
| 6 | `scripts/false_positive_tests_120s.py` | Odd/even and phase-0.5 secondary checks |
| 7 | `scripts/phase_curve_search.py` | Systematics-limited harmonic fit and phase-0.5 box; not an eccentric-phase eclipse scan |
| 8 | `scripts/gaia_contamination_check.py` | Gaia field census and mimic-capable source list |
| 9 | `scripts/tess_source_localization_120s.py` | Qualitative difference-image centroids |
| 10 | `scripts/source_specific_aperture_check.py` | Discrete aperture geometry; not calibrated PRF localization |
| 11 | `scripts/dilution_robustness.py` | Residual-dilution sensitivity; no second CROWDSAP correction |
| 12 | `scripts/spoc_dv_extract.py` | Separate-pipeline analysis of the same TESS observations |
| 13 | `scripts/query_stellar_photometry.py` | Frozen 2MASS/WISE/APASS query |
| 14 | `scripts/stellar_sed_posterior.py` | Approximate blackbody radius-scale check; not an isochrone posterior |
| 15 | `scripts/robust_density_comparison.py` | Non-adopted model-conditional density diagnostic |
| 16 | `scripts/statistical_validation.py` | Non-probabilistic vetting summary; formal FPP remains null |
| 17 | `scripts/asteroseismic_prepare.py` | Re-downloadable SPOC FITS inventory and hashes |
| 18 | `scripts/asteroseismic_search.py` | Preliminary implementation of preregistered seismic diagnostics |
| 19 | `scripts/asteroseismic_injection_recovery.py` | Sensitivity calibration showing the null is non-constraining |
| 20 | `scripts/audit_science_consistency.py` | Offline consistency and claim-boundary audit |
| 21 | `scripts/transit_window_comparison.py` | Converged total-width 13-h sensitivity fit; not adopted |
| 22 | `scripts/audit_manuscript_math.py` | Line-by-line mathematical inventory and source-value recalculation |

Active remediation phases supersede the historical stage numbering above:

| Phase | Script | Current gate |
|---:|---|---|
| 1 | `scripts/verify_faz1_inventory.py` | `PASS`; 18/18 local LC/TPF products and cadence ledgers verified |
| 2 | `scripts/verify_faz2_transit_inventory.py` | `PASS`; 18 expected windows classified, 16 usable events |
| 3 | `scripts/verify_faz3_quality_audit.py` | `PASS`; quality, telemetry, CBV, and control-star audit |
| 4 | `scripts/run_faz4_reductions.py` | `CONDITIONAL_PASS`; accepted reduction dispersion retained separately |
| 5 | `scripts/run_faz5_window_grid.py` | Original preregistered result remains `FAIL` |
| 5B | `scripts/run_faz5b_remediation.py` | `CONDITIONAL_CONTINUE`; 24 discrete mask/window/polynomial branches handed to Phase 6 |
| 6 | `scripts/run_faz6_noise_models.py`, `scripts/run_faz6_joint_diagnostics.py` | `FAIL_STATIONARITY`; screening complete, Phase 7 closed |

`scripts/ttv_analysis.py`, `scripts/stellar_activity.py`, and
`scripts/triceratops_validation.py` are retained for provenance but are not
active adopted pipeline steps. Their old claims are unsupported: timing is
signal-to-noise limited, no rotation result is adopted, and no calibrated FPP
is reported. `scripts/stellar_params.py` is a network regeneration utility; its
catalog `a/Rstar` calculation is comparison-only.

The machine-readable current claim gate is `outputs/release_status.json`.

## Verification

```bash
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python scripts/run_faz5b_remediation.py --verify-only
python -m pytest -q
```

`python scripts/run_all_tests.py` is a thin wrapper around the same pytest suite.
The audit scripts provide human-readable consistency summaries; tests enforce selected equations,
chain/output consistency, claim-boundary statuses, manifest hashes, and
required artifacts. They are not a substitute for peer review or independent
scientific reproduction.

Raw SPOC FITS files are re-downloadable and intentionally excluded from the
release ZIP. After downloading them, verify their sizes and hashes separately
with the integration-test command documented in `docs/reproducibility_order.md`.

## Dependencies

- Python 3.9.13 and the versions pinned in `requirements-lock.txt`
- Core: `numpy`, `scipy`, `pandas`, `matplotlib`, `corner`
- Astronomy: `astropy`, `lightkurve`, `astroquery`, `batman-package`, `emcee`, `ldtk`
- Optional: `triceratops` only for explicitly non-adopted method development;
  no output from it supports the release claims
- Optional: `tess-atl` and `pysyd` for the exploratory asteroseismic extension

## Citation

If you use this reproducibility package or the associated manuscript, please cite:

Şen, F. (2026). TOI-3492.01 Photometric Characterization: Reproducibility Package (v1.0.1). The Zenodo DOI must be added after the corrected package is deposited; no DOI is claimed in this draft.

## Licensing

- Source code in `scripts/` and `tests/`: MIT License.
- Original manuscript, figures, narrative documentation, and original derived
  tables: Creative Commons Attribution 4.0 International (CC BY 4.0).
- Upstream TESS, Gaia, ExoFOP, NASA Exoplanet Archive, and catalog material:
  original archive terms and acknowledgement requirements continue to apply.

See `LICENSES.md` for the artifact-level license matrix and upstream-data
notice.

## Asteroseismic Status

The current complete-or-remove decision for the exploratory search is documented
in Phase 28 of `currentproblem.md`.
Neither the local search nor the independent pySYD block analysis found a
replicated seismic solution, so no asteroseismic measurement is adopted in the
manuscript. The non-detection is not constraining at the expected few-ppm mode
amplitudes; the injection/recovery experiment only becomes efficient for much
stronger signals.
