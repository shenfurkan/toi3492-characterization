# TOI-3492.01 Reproducibility Order

Last synchronized: 2026-07-23.

This document distinguishes artifact verification from scientific regeneration
and final release verification. Historical pass counts are never current
evidence after source changes.

## Authority and Current Scope

- Canonical manuscript: `toi3492_characterization.tex`.
- Original gates: `currentproblem.md`.
- Recovery plan and execution log: `currentproblemstage2.md`.
- Plain-language review and approved bounded continuation context: `analiz.md`.
- Original Phase 5: immutable `FAIL`.
- Phase 5B: 24-branch `CONDITIONAL_CONTINUE` handoff.
- Phase 6: authoritative `FAIL_STATIONARITY`.
- Phase 6R calculation: `FAIL_RESIDUAL_CORRELATION` after 24/24 stationarity.
- WP-09A: `PASS`, formal heterogeneity only; no astrophysical cause assigned.
- Folded/binned fit: descriptive historical reference, not an adopted final
  native-cadence posterior.
- Formal FPP, measured eccentricity, mass, validation, and confirmation: not
  reported.

`outputs/release_status.json` is synchronized through S3-03. It remains a
working-state record rather than final release evidence.

## Safe Artifact Verification

These commands verify existing no-clobber artifacts where the script exposes a
verification mode:

```powershell
python scripts/run_faz5b_remediation.py --verify-only
python scripts/run_faz6_noise_models.py --verify-only
python scripts/run_faz6_joint_diagnostics.py --verify-only
python scripts/audit_faz6_gate.py --verify-only
python scripts/run_wp09a_formal_sector_audit.py --verify-only
python scripts/build_stage3_input_manifest.py --verify-only
python scripts/run_stage3_phase6_postmortem.py --verify-only
python scripts/build_stage3_model_architecture_decision.py --verify-only
python -m pytest -q
```

`scripts/run_faz6r.py` does not expose `--verify-only`. Do not rerun it as an
artifact check. S3-02 verifies its frozen files and reconstructs residual
diagnostics from the saved MAP endpoints without optimization or new draws.

The current development run is 165 passed. Always report current command output
rather than copying an old count. Passing tests do not make stale audits or
manifest hashes current.

## Completed Scientific Chain

| Step | Command or artifact | Recorded result |
|---:|---|---|
| 1 | `scripts/verify_faz1_inventory.py` | Phase 1 `PASS` |
| 2 | `scripts/verify_faz2_transit_inventory.py` | Phase 2 `PASS` |
| 3 | `scripts/verify_faz3_quality_audit.py` | Phase 3 `PASS` |
| 4 | `scripts/run_faz4_reductions.py` | Phase 4 `CONDITIONAL_PASS` |
| 5 | `outputs/faz5_window_polynomial_grid.json` | Original Phase 5 `FAIL` |
| 6 | `outputs/faz5b_remediation.json` | Phase 5B `CONDITIONAL_CONTINUE` |
| 7 | `outputs/faz6_kernel_comparison.json` | 576/576 folds; no eligible complex kernel |
| 8 | `outputs/faz6_gate_audit.json` | Phase 6 `FAIL_STATIONARITY` |
| 9 | `outputs/faz6r_result.json` | Phase 6R `FAIL_RESIDUAL_CORRELATION` |
| 10 | `outputs/wp09a_formal_sector_audit.json` | WP-09A `PASS` |
| 11 | `data/stage3_input_manifest.json` | S3-01 immutable inputs `PASS` |
| 12 | `outputs/stage3_phase6_postmortem.json` | S3-02 existing-artifact post-mortem `PASS`; no fit |
| 13 | `data/stage3_model_architecture_decision.json` | S3-03 single-candidate architecture `PASS`; before synthetic |

Do not overwrite these artifacts to make a failed gate pass. New scientific
work must use new filenames, schemas, protocols, and hashes.

## Regeneration Rules

1. Do not regenerate a frozen phase merely to reproduce an old number.
2. Record exact input, code, configuration, environment, and random-state hashes.
3. Run synthetic/unit calibration before a new real-data model.
4. Preserve failed attempts and label them invalid, diagnostic, or nonadopted.
5. Never multiply cadence masks or reductions as independent observations.
6. Never count 20-s and 120-s products as independent transit events.
7. Keep Phase 4 reduction uncertainty and Phase 5B model uncertainty from being
   added twice.
8. The dated Stage-3 scope amendment is approved, but a new real-data model still
   requires synthetic/numerical gates and separate S3-06 protocol approval.

## Diagnostic Utilities

These scripts remain useful but do not by themselves produce adopted final
parameters:

| Script | Role |
|---|---|
| `build_120s_reference_lightcurve.py` | Rebuild descriptive reference products |
| `alias_120s_analysis.py` | Check recovery near the official ephemeris |
| `check_20s_independent.py` | Same-pixel cadence consistency check |
| `transit_model_120s_corrected.py` | Folded/binned descriptive reference fit |
| `transit_stability_checks.py` | Bin and window sensitivity diagnostic |
| `transit_window_comparison.py` | Nonadopted window sensitivity fit |
| `transit_fit_robust.py` | Historical unconverged native-cadence fits |
| `robust_density_comparison.py` | Historical model-conditional density diagnostic |
| `false_positive_tests_120s.py` | Odd/even and fixed-phase secondary diagnostics |
| `phase_curve_search.py` | Systematics-limited harmonic diagnostic |
| `tess_source_localization_120s.py` | Qualitative, not calibrated PRF localization |
| `dilution_robustness.py` | Conditional dilution sensitivity |
| `statistical_validation.py` | Non-probabilistic vetting summary; FPP remains null |

The asteroseismology scripts and outputs are provenance only. They are not part
of the active canonical manuscript or final release claim chain.

## Quarantined or Nonadopted Branches

- `transit_model_120s_density_locked.py`: explicit historical comparison only.
- `transit_model_120s_eccentric.py`: exploratory and not an eccentricity result.
- `ttv_analysis.py`: no adopted TTV detection.
- `stellar_activity.py`: no adopted rotation period.
- `triceratops_validation.py`: method development only; no release FPP.
- Phase 6 V1 result: invalid because all 72 optimizer attempts were no-ops.
- Phase 6 V2: valid failure record; beta was not computed.
- Phase 6R: negative calculation with incomplete standalone preregistration and
  audit provenance.

## Final Manuscript Verification

Only after scientific freeze:

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
```

Compile through the complete bibliography cycle required by the final document
class. Inspect the resulting PDF page by page. The final audit must record the
exact hash of the TeX source that produced the inspected PDF.

## Final Package Build

Only after the manuscript, audits, and tests pass:

```powershell
python scripts/generate_release_manifest.py
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

Use the package filenames generated for the newly assigned release version. Do
not reuse superseded fixed filenames from historical documentation. Extract each
archive into an empty directory, verify hashes and CRC, rerun the documented
offline suite, and compile the staged arXiv source.

## External Limits

- No target-specific radial-velocity mass or orbit.
- No high-resolution imaging contrast curve.
- No calibrated PRF source-localization likelihood.
- No independent spectroscopic atmospheric-parameter solution.
- No coherent final stellar isochrone posterior.
- No calibrated population FPP.

These limits constrain claims, not whether a properly scoped TESS photometric
characterization can be completed.
