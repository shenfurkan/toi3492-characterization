# TOI-3492.01: A Short-Period Giant Planet Candidate Orbiting an Evolved F-type Subgiant

An independent photometric analysis of TESS Object of Interest TOI-3492.01
(TIC 81077799), a short-period giant-planet candidate around an evolved
F-type subgiant star.

**Status:** Photometric-only candidate characterization.  
RV confirmation and high-resolution imaging are still needed.

## Quick Summary

| Quantity | Value |
|---:|---|
| Period | 9.2224171 d (official TOI) |
| Rp/Rs | 0.05472 +/- 0.00049 |
| Mid-transit model depth | 3094 ppm |
| Rp | 15.47 +/- 0.66 Rearth (1.38 Rjup) |
| Circular-fit a/Rs | 10.60 +/- 0.45 |
| Impact parameter b | 0.705 +/- 0.032 |
| Formal FPP | Not reported; current diagnostics are not a calibrated population model |
| Key caveat | Circular photometric density is about 4.3 sigma above the catalog density |

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
├── figures/             # 14 diagnostic plots
├── outputs/             # JSON/CSV results from each pipeline step
└── docs/                # Methodology notes and checklists
```

The release includes the canonical LaTeX source and machine-readable outputs.
Literature PDFs and LaTeX build intermediates are excluded.

## Pipeline (Reproducibility Order)

Run from project root with Python 3.9+:

| Step | Script | Produces |
|---:|---|---|
| 1 | `scripts/stellar_params.py` | `config.json`, LD coefficients |
| 2 | `scripts/build_120s_reference_lightcurve.py` | `toi3492_120s_reference.csv` |
| 3 | `scripts/transit_model_120s_corrected.py` | `config_corrected_120s.json`, chains, figures |
| 4 | `scripts/false_positive_tests_120s.py` | Odd/even, secondary eclipse checks |
| 5 | `scripts/gaia_contamination_check.py` | Gaia DR3 neighbor census |
| 6 | `scripts/dilution_robustness.py` | CROWDSAP/ExoFOP dilution corrections |
| 7 | `scripts/tess_source_localization_120s.py` | Difference-image centroid check |
| 8 | `scripts/spoc_dv_extract.py` | SPOC DV product parsing |
| 9 | `scripts/statistical_validation.py` | Non-probabilistic vetting summary |
| 10 | `scripts/triceratops_validation.py` | Optional, non-adopted screening experiment |
| 11 | `scripts/ttv_analysis.py` | Transit timing |
| 12 | `scripts/stellar_activity.py` | Rotation / variability |
| 13 | `scripts/audit_science_consistency.py` | Final verification |
| 14 | `scripts/asteroseismic_prepare.py` | Re-downloadable SPOC FITS inventory and hashes |
| 15 | `scripts/asteroseismic_search.py` | Preregistered block-level seismic diagnostics |
| 16 | `scripts/asteroseismic_injection_recovery.py` | Preliminary sensitivity calibration |

Steps 1-2, 5, 7-8, 10, and 12 can require network access.  Frozen release
artifacts can be audited offline.

## Verification

```bash
python scripts/audit_science_consistency.py
```

The publication gate is `python -m pytest -q`.  The audit script provides a
human-readable summary; the tests enforce schemas, equations, chain/output
consistency, manuscript claims, and required release artifacts.

## Dependencies

- Python 3.9.13 and the versions pinned in `requirements-lock.txt`
- Core: `numpy`, `scipy`, `pandas`, `matplotlib`, `corner`, `pytest`
- Astronomy: `astropy`, `lightkurve`, `astroquery`, `batman-package`, `emcee`, `ldtk`
- Optional: `triceratops` for a non-adopted screening experiment
- Optional: `tess-atl` and `pysyd` for the exploratory asteroseismic extension

## Asteroseismic Status

The preregistered exploratory search is documented in `REVIEW_NOTES.md`.
Neither the local search nor the independent pySYD block analysis found a
replicated seismic solution, so no asteroseismic measurement is adopted in the
manuscript. The non-detection is not constraining at the expected few-ppm mode
amplitudes; the injection/recovery experiment only becomes efficient for much
stronger signals.
