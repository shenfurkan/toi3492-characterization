# Corrected Reproducibility Order

Date: 2026-07-09 (updated post SPOC DV, dilution, and TRICERATOPS 100k audit)

This is the rerun order for the current TOI-3492.01 analysis. The current physical interpretation uses the 120 s-only products and `config_corrected_120s.json`.

## Corrected Pipeline

Run from the project root with Python:

| Step | Command | Main outputs | Notes |
|---:|---|---|---|
| 1 | `python scripts\scripts\stellar_params.py` | `config.json` | Network-dependent TIC query; computes limb-darkening via LDTk (Claret 2017 PHOENIX models). |
| 2 | `python scripts\alias_120s_analysis.py` | `alias_120s_results.json`, `toi3492_120s_alias_analysis.png` | Confirms the official 9.2224171 d period in 120 s SPOC products. |
| 3 | `python scripts\build_120s_reference_lightcurve.py` | `toi3492_120s_reference.csv`, `toi3492_120s_sector_depths.csv`, `toi3492_120s_reference_fold.png` | Builds the preferred corrected photometry product. |
| 4 | `python scripts\transit_model_120s_corrected.py` | `config_corrected_120s.json`, `toi3492_chains_120s_corrected.npy`, `toi3492_raw_chain_120s_corrected.npy`, `mcmc_diagnostics_120s_corrected.json`, `toi3492_transit_fit_120s_corrected.png`, `toi3492_corner_120s_corrected.png` | Current working free-geometry circular transit fit. Uses LD from config.json. |
| 5 | `python scripts\transit_model_120s_density_locked.py` | `transit_fit_120s_density_locked.json`, `toi3492_transit_fit_120s_density_locked.png`, `toi3492_corner_120s_density_locked.png` | Comparison fit only; a/Rstar fixed to TIC density prediction. Not the adopted solution. |
| 6 | `python scripts\false_positive_tests_120s.py` | `false_positive_tests_120s.json`, `toi3492_120s_event_depths.csv`, `toi3492_false_positive_120s.png` | Corrected odd/even and secondary-eclipse checks. |
| 7 | `python scripts\gaia_contamination_check.py` | `gaia_contamination_check.json`, `gaia_dr3_neighbors.csv`, `toi3492_gaia_neighbors.png` | Network-dependent Gaia DR3 neighbor/RUWE check. |
| 8 | `python scripts\dilution_robustness.py` | `dilution_corrected_transit_params.json`, `dilution_summary_120s.csv`, `dilution_worst_case_scenarios.json`, `toi3492_dilution_robustness.png` | Quantifies CROWDSAP, ExoFOP, and Gaia-flux dilution corrections. |
| 9 | `python scripts\tess_source_localization_120s.py` | `tess_source_localization_120s.json`, `toi3492_120s_difference_centroids.csv`, `toi3492_tess_difference_images.png` | First-pass TESS target-pixel difference-image check. |
| 10 | `python scripts\spoc_dv_extract.py` | `spoc_dv_summary.json`, `spoc_vs_local_comparison.json`, `spoc_dv_transit_metrics.csv`, `spoc_dv_pdf_metrics.csv`, `spoc_dv_summary.md` | Parses local SPOC DVT FITS and DVR PDF products; compares official-period DV results against the corrected 120 s fit. |
| 11 | `python scripts\verify_final.py` | terminal summary | Sanity check that the corrected config reports the current giant-planet-size candidate result. |
| 12 | `python scripts\transit_model_120s_eccentric.py` | `transit_fit_120s_eccentric.json`, `toi3492_transit_fit_120s_eccentric.png`, `toi3492_corner_120s_eccentric.png` | Exploratory eccentric-orbit fit (free e, omega). Diagnostic only; does not produce a viable preferred solution. |
| 13 | `python scripts\triceratops_validation.py --n 100000 --search-radius 4 --bins 240 --window-days 0.70` | `triceratops_validation_120s.json`, `triceratops_probs_120s.csv`, `triceratops_120s_folded_binned.csv` | Adopted TRICERATOPS screening run. Uses runtime compatibility shims for this local Python environment; no site-packages edits. |

## Current Adopted Result

Use the top-level `transit` block and `transit_corrected_120s` block in `config_corrected_120s.json`.

Rounded current values:

| Quantity | Value |
|---:|---:|
| Period | 9.2224171 d |
| Rp/Rstar | 0.05628 +/- 0.00046 |
| Depth | 3167 ppm |
| Radius | 15.92 +/- 0.68 Rearth |
| a/Rstar | 9.21 +/- 0.29 |
| Impact parameter | 0.789 +/- 0.016 |
| Limb darkening (LDTk/Claret 2017) | u1=0.393, u2=0.150 |
| MCMC acceptance fraction | 0.595 |
| MCMC autocorrelation time | 40.2-43.8 production steps |
| Simplified Morton-style FPP | 0.011% |
| TRICERATOPS screening FPP | numerically 0.0; scenario table dominated by PTP=0.999997 (finite-run result, not exact zero probability) |
| SPOC DV S1-S96 TCE 1 | P=9.222408 d, depth=3128 +/- 30 ppm, Rp=15.7 +/- 0.7 Rearth, MES=99.4, centroid offset 0.90 sigma |
| CROWDSAP-mean dilution correction | depth=3244 ppm, Rp=16.11 Rearth |

## Removed Legacy Scripts

These obsolete entry points have been removed from the current workflow:

| Script or product | Status |
|---|---|
| `download_and_clean.py` | Removed; legacy preprocessing. |
| `toi3492_cleaned.csv` | Removed; obsolete product. |
| `toi3492_unflattened.csv` | Removed; obsolete. |
| `transit_modeling.py` | Removed; legacy transit model. |
| `false_positive_tests.py` | Removed; legacy false-positive checks. |
| `period_harmonic_check.py` | Removed; superseded by `alias_120s_analysis.py`. |

`config_corrected_120s.json` contains the current corrected 120 s solution.

## Remaining Non-Reproducible Or External Pieces

- `stellar_params.py`, `alias_120s_analysis.py`, `build_120s_reference_lightcurve.py`, `gaia_contamination_check.py`, and `tess_source_localization_120s.py` depend on remote catalog or MAST access.
- SPOC DV dashboard centroid metrics have been extracted; independent PRF-level validation has not been added.
- No high-resolution imaging contrast curve is available for the TRICERATOPS run.
- No radial-velocity confirmation or mass measurement is included.
