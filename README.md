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
| Rp/Rs | 0.05628 +/- 0.00046 |
| Depth | ~3167 ppm (model) |
| Rp | 15.92 +/- 0.68 Rearth (1.42 Rjup) |
| a/Rs | 9.21 +/- 0.29 |
| Impact parameter b | 0.789 +/- 0.016 |
| FPP (Morton-style) | ~0.01% |
| TRICERATOPS FPP | numerically 0 (PTP=0.999997) |
| Key caveat | a/Rs 2.6 sigma above TIC-density prediction |

## Repository Structure

```
.
├── references.bib       # BibTeX bibliography
├── data/
│   ├── config.json      # Stellar params from TIC v8
│   ├── config_corrected_120s.json  # Adopted transit solution
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

> **Note:** LaTeX sources, compiled PDFs, and reference paper copies are
> maintained locally and excluded from this repository via `.gitignore`.

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
| 9 | `scripts/statistical_validation.py` | Morton-style FPP |
| 10 | `scripts/triceratops_validation.py` | TRICERATOPS screening |
| 11 | `scripts/ttv_analysis.py` | Transit timing |
| 12 | `scripts/stellar_activity.py` | Rotation / variability |
| 13 | `scripts/audit_science_consistency.py` | Final verification |

Steps 1-2 and 5 require MAST/Gaia network access. All others run offline.

## Verification

```bash
python scripts/audit_science_consistency.py
```

This script independently recomputes all key parameters from local CSV/NPY/JSON
and compares them against the LaTeX tables. It also runs the full numerical
audit used for the checklist in `docs/`.

## Dependencies

- Python 3.9+: `numpy`, `scipy`, `pandas`, `matplotlib`, `corner`
- Astronomy: `lightkurve`, `astroquery`, `batman-package`, `emcee`
- Optional: `triceratops` (for screening run)
