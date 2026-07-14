# TOI-3492.01 Reproducibility Order

Last synchronized: 2026-07-14.

This runbook separates offline verification of the frozen `v1.0.1` release from
network-dependent or computationally expensive regeneration. Run commands from
the repository root with Python 3.9.x and the versions in
`requirements-lock.txt`.

## Authority and Scope

- Canonical manuscript: `toi3492_characterization.tex`.
- Adopted configuration: `data/config_corrected_120s.json`.
- Machine-readable claim gate: `outputs/release_status.json`.
- Mathematical audit: `outputs/manuscript_math_audit.json`.
- Adopted window: `|t-Tc| < 13 h`, a 26-h total width.
- Sensitivity window: `|t-Tc| < 6.5 h`, a 13-h total width; converged but not
  adopted.
- Formal FPP: not reported.

The frozen reference data and outputs are sufficient for the default offline
tests. Raw SPOC FITS files and live catalog queries are regeneration inputs and
are not distributed in the compact release.

## Fast Offline Verification

Run this before any regeneration:

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
```

Expected results:

- scientific consistency and claim-boundary audit: PASS;
- manuscript mathematics audit: PASS, 276 expressions and 761 numeric tokens;
- tests: 27 passed, 1 deselected.

The deselected integration test requires the 18 re-downloadable raw SPOC
products. If those files are present, run:

```powershell
python -m pytest -q -m integration -o addopts=""
```

## Regeneration Order

Do not overwrite frozen release outputs casually. Regeneration can involve
network services, stochastic chains, and substantial runtime. Preserve seeds
and compare regenerated products with the frozen artifacts.

| Step | Command | Main role | Adoption status |
|---:|---|---|---|
| 1 | `python scripts/stellar_params.py` | Refresh TIC metadata and LDTk inputs | Network utility; catalog comparison only |
| 2 | `python scripts/build_120s_reference_lightcurve.py` | Rebuild six-sector 120-s reference CSV and sector depths | Adopted data product |
| 3 | `python scripts/alias_120s_analysis.py` | Targeted BLS recovery near the official period | Consistency check, not independent ephemeris confirmation |
| 4 | `python scripts/check_20s_independent.py` | Build 20-s reference and matched-cadence comparison | Same-pixel consistency check |
| 5 | `python scripts/transit_model_120s_corrected.py` | Five-parameter folded/binned circular MCMC | Adopted reference fit |
| 6 | `python scripts/transit_stability_checks.py` | Deterministic bin and window perturbations | Sensitivity diagnostic |
| 7 | `python scripts/transit_window_comparison.py` | Full MCMC for the +/-6.5 h interpretation | Converged, nonadopted sensitivity fit |
| 8 | `python scripts/transit_fit_robust.py` | Native-cadence 120-s and 20-s fits | Nonadopted; chains do not meet 50-tau rule |
| 9 | `python scripts/robust_density_comparison.py` | Compare diagnostic density scales | Model conditional, nonadopted |
| 10 | `python scripts/false_positive_tests_120s.py` | Odd/even and phase-0.5 secondary checks | Direct diagnostics only |
| 11 | `python scripts/phase_curve_search.py` | Harmonic and phase-0.5 box regression | Systematics limited; no physical detection |
| 12 | `python scripts/gaia_contamination_check.py` | Gaia field census and mimic-capable sources | Network regeneration utility |
| 13 | `python scripts/tess_source_localization_120s.py` | First-pass difference-image centroids | Qualitative, not calibrated PRF localization |
| 14 | `python scripts/source_specific_aperture_check.py` | Frozen WCS and pipeline-aperture geometry | Qualitative, not formal exclusion |
| 15 | `python scripts/dilution_robustness.py` | Residual dilution sensitivity | No second CROWDSAP correction |
| 16 | `python scripts/spoc_dv_extract.py` | Parse local SPOC DVT/DVR products | Separate pipeline using the same TESS observations |
| 17 | `python scripts/query_spectroscopic_archives.py` | Query four public spectroscopic archives | Network utility; zero matches is not proof of no spectrum elsewhere |
| 18 | `python scripts/query_stellar_photometry.py` | Freeze selected broadband photometry | Network utility |
| 19 | `python scripts/stellar_sed_posterior.py` | Blackbody radius-scale fit | Approximate cross-check, not an isochrone posterior |
| 20 | `python scripts/statistical_validation.py` | Assemble measured vetting facts | Non-probabilistic summary; FPP remains null |
| 21 | `python scripts/asteroseismic_prepare.py` | Inventory raw seismic inputs and hashes | Requires re-downloadable SPOC files |
| 22 | `python scripts/asteroseismic_search.py` | Preliminary preregistered diagnostics | No adopted seismic measurement |
| 23 | `python scripts/asteroseismic_injection_recovery.py` | Calibrate null sensitivity | Shows the null is non-constraining |
| 24 | `python scripts/audit_science_consistency.py` | Check science and claim boundaries | Required release gate |
| 25 | `python scripts/audit_manuscript_math.py` | Recalculate values and bind manuscript hash | Required release gate |

Some asteroseismic cross-checks use additional `asteroseismic_*pysyd.py` helper
scripts. Their outputs remain preliminary and do not supersede the release
gate.

## Current Adopted Result

| Quantity | Value and interpretation |
|---|---|
| Period | 9.2224171 d, fixed to official TOI ephemeris |
| `Rp/Rstar` | 0.05472 +/- 0.00049 |
| `a/Rstar` | 10.60 +/- 0.45 |
| Impact parameter | 0.705 +/- 0.032 |
| Model depth | approximately 3094 ppm at marginal posterior medians |
| Area ratio | 2994 ppm |
| Duration | 5.233 h |
| Candidate radius | 15.47 +/- 0.66 Rearth, catalog conditional |
| Circular transit density | 0.188 (+0.025/-0.020) rho_sun, for `q=0` |
| Catalog density | 0.072 (+0.015/-0.013) rho_sun |
| Density interpretation | ratio about 2.6; model conditional, not a calibrated significance |
| Formal FPP | not reported |

The alternative 13-h-total fit gives
`Rp/Rstar=0.05567 (+0.00039/-0.00040)` and
`a/Rstar=10.17 (+0.32/-0.29)`. Its 1.95-half-width radius-ratio shift shows
that the adopted statistical interval does not include fit-window choice.

## Quarantined or Nonadopted Branches

- `scripts/transit_model_120s_density_locked.py`: explicit comparison only.
- `scripts/transit_model_120s_eccentric.py`: exploratory, prior-conditioned,
  and not converged sufficiently for an eccentricity result.
- `scripts/ttv_analysis.py`: provenance only; no TTV detection is adopted.
- `scripts/stellar_activity.py`: provenance only; no rotation period is adopted.
- `scripts/triceratops_validation.py`: method development only and requires an
  explicit acknowledgement flag; no output supports a release FPP.
- `data/toi3492_characterization_qa.tex`: noncanonical and excluded.

## Manuscript and Package Build

Compile the canonical manuscript:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error toi3492_characterization.tex
bibtex toi3492_characterization
pdflatex -interaction=nonstopmode -halt-on-error toi3492_characterization.tex
pdflatex -interaction=nonstopmode -halt-on-error toi3492_characterization.tex
```

Then build release artifacts:

```powershell
python scripts/generate_release_manifest.py
python -m pytest -q
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

`build_release_package.py` verifies manifest hashes, safe and unique ZIP paths,
ZIP CRC, embedded hashes, and the extracted archive's test suite. Independently
compare `toi3492_reproducible_release_v1.0.1.zip` with its adjacent `.sha256`
sidecar before upload.

## External Limitations

- No radial-velocity mass or orbit.
- No high-resolution imaging contrast curve.
- No calibrated PRF source-localization likelihood.
- No independent spectroscopic atmospheric-parameter solution.
- No coherent stellar isochrone posterior.
- No calibrated population FPP.
- No completed eccentric-phase secondary-eclipse scan.
