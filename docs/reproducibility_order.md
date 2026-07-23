# TOI-3492.01 Reproducibility Order

Last synchronized: 2026-07-22.

The previous `v1.0.1` package state is superseded. Do not treat the commands or
stored audit results below as current PASS evidence. The run order remains a
reference for the final verification stage after `currentproblem.md` is
completed.

## Authority and Scope

- Canonical manuscript: `toi3492_characterization.tex`.
- Historical diagnostic configuration: `data/config_corrected_120s.json`.
- Machine-readable claim gate: `outputs/release_status.json`.
- Mathematical audit: stale until regenerated for the final TeX source.
- Active baseline/window treatment: no single adopted cell; use the 24-branch
  Phase 5B handoff in `data/toi3492_faz5b_handoff_draws.npz`.
- Original Phase 5 remains `FAIL`; Phase 5B is `CONDITIONAL_CONTINUE`, not a
  retroactive pass.
- Formal FPP: not reported.

The existing reference data and outputs are remediation inputs. Raw SPOC FITS
files and live catalog queries remain regeneration inputs.

## Fast Offline Verification

Run this before any regeneration:

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python scripts/run_faz5b_remediation.py --verify-only
python -m pytest -q
```

Do not use historical pass counts as current evidence. The command must exit
successfully on the current source and every manifest hash must match.

The deselected integration test requires the 18 re-downloadable raw SPOC
products. If those files are present, run:

```powershell
python -m pytest -q -m integration -o addopts=""
```

## Regeneration Order

Do not overwrite frozen release outputs casually. Regeneration can involve
network services, stochastic chains, and substantial runtime. Preserve seeds
and compare regenerated products with the frozen artifacts.

The completed active remediation order through Phase 5B is:

| Step | Command | Gate |
|---:|---|---|
| 1 | `python scripts/verify_faz1_inventory.py` | Phase 1 `PASS` |
| 2 | `python scripts/verify_faz2_transit_inventory.py` | Phase 2 `PASS` |
| 3 | `python scripts/prepare_faz3_inputs.py` then `python scripts/verify_faz3_quality_audit.py` | Phase 3 `PASS` |
| 4 | `python scripts/run_faz4_reductions.py` | Phase 4 `CONDITIONAL_PASS` |
| 5 | `python scripts/run_faz5_window_grid.py` | Immutable original Phase 5 `FAIL`; do not overwrite |
| 6 | `python scripts/run_faz5b_remediation.py --verify-only` | Verify Phase 5B `CONDITIONAL_CONTINUE` without refitting |
| 7 | `python scripts/run_faz6_noise_models.py --verify-only` | Verify the complete 576-fold kernel screen |
| 8 | `python scripts/run_faz6_joint_diagnostics.py --verify-only` | Verify the V2 joint stationarity failure |
| 9 | `python scripts/audit_faz6_gate.py --verify-only` | Verify the authoritative `FAIL_STATIONARITY` gate |

The Phase 5B producer is no-clobber. Its default fitting mode is only for a
fresh artifact location; use `--verify-only` for the frozen result.

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

## Historical Diagnostic Result

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

These values are historical diagnostic quantities, not the active native-cadence
posterior. The alternative 13-h-total fit gives
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
- Former QA manuscript: noncanonical, excluded, and retained only in
  `toi3492_legacy_material_20260722.zip`.

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
