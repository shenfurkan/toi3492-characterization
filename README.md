# TOI-3492.01 Photometric Characterization

This repository is the codebase for a photometric characterization of the TESS transit candidate **TOI-3492.01** (TIC 81077799). It is also the repository for a methodology paper about doing this kind of analysis reproducibly. TOI-3492.01 is the case study, and the pipeline is the contribution.

The primary publication target is PASP or MNRAS. This file, read together with the manuscript (`toi3492_characterization.tex`) and the documentation under `docs/`, describes the project.

## The target

TOI-3492.01 is a transit candidate identified by the TESS automated pipeline and listed as a Planet Candidate (PC disposition) in the NASA Exoplanet Archive. The host star, TIC 81077799, sits at roughly 202 parsecs and has a TESS magnitude of 8.45. Its effective temperature is around 6332 K, its surface gravity log g ≈ 3.71, and its radius is about 2.59 solar radii. This combination (hot, low surface gravity, inflated radius) makes it a subgiant. The stellar density implied by the transit duration and shape should be consistent with the density derived from the stellar parameters independently. As described below, they are not consistent under a simple circular orbit interpretation.

The candidate transits every 9.2224171 days with a depth of roughly 3100 ppm and a duration of about 5.3 hours. The catalog radius estimate is around 15.7 Earth radii and the equilibrium temperature is near 1477 K. None of these parameters have been independently confirmed. There is no radial velocity mass measurement. The object is unvalidated and unconfirmed.

The TESS observations cover six sectors: 37, 63, 64, 90, 99, and 100. Both 120-second and 20-second cadence SPOC products exist for most sectors. Eighteen transit windows were expected across those sectors; sixteen were usable after accounting for data gaps and quality flags. Note that sixteen transits from six sectors are not sixteen independent observations, as they come from the same pixels, instrument, and reduction pipeline, meaning systematic errors are correlated.

## What this paper is actually arguing

The main argument of the paper is methodological.

The first problem is model selection. When phase-folding a multi-sector TESS light curve and fitting a transit, choices must be made about the window width around the transit, the polynomial order for the out-of-transit baseline, and the handling of different noise properties across sectors. Usually, a single "best" model is presented. This project evaluates a grid of 576 combinations of window widths (13, 16, 20, 26, and 32 hours) and polynomial orders (0, 1, 2) across all sectors. Rather than picking one arbitrarily, it carries 24 branches forward into all subsequent analysis, making the model-selection uncertainty part of the output.

The second problem is noise modeling. Photometric residuals from TESS data often have correlated noise structures. The standard response is to fit a Gaussian process. The project tests four kernels: pure white noise (K0), an Ornstein-Uhlenbeck process (K1), a Matérn-3/2 kernel (K2), and a stochastically driven harmonic oscillator (K3). None of the 576 branch-kernel combinations passed the stationarity gate for the complex kernels. The white-noise model was rerun across all 24 branches in a remediation phase (Phase 6R), and the residuals still showed detectable excess correlation. The formal result is a failure.

The third problem is post-hoc adjustment of thresholds. This project preregisters its thresholds (the beta limit of 1.2, the stationarity tolerance, the kernel candidate set, the window/polynomial grid) in JSON protocol files before running the relevant analysis. Those files are version-controlled and their hashes are recorded.

## How the pipeline actually works

Starting from the raw SPOC data products, the pipeline proceeds through a sequence of phases, each with its own pass/fail gate.

First, all eighteen SPOC files are downloaded from MAST via `lightkurve` and cross-checked against a manifest. Time systems are verified, and the conversion from raw timestamps is confirmed. Quality flags are applied using the standard TESS bitmask. A complete cadence ledger is built for both cadences.

Each expected transit window is located and checked for adequate coverage. A window that sits in a data gap, or where the TESS momentum dump lands in the middle of the transit, is flagged and excluded. Of the eighteen expected windows, sixteen survive this check. The excluded two are absent from the analysis.

Before transit fitting happens, each sector goes through a quality audit: background flux levels, pointing metric scatter, CBV contamination relative to the raw SAP flux, and a comparison against several control stars observed in the same sectors. This audit is Phase 3 and it passes.

Phase 4 compares four detrending approaches: simple polynomial detrending over the out-of-transit baseline, CBV-corrected flux from the SPOC pipeline, PDC-SAP flux as delivered, and a local window-polynomial approach. None of these is perfect, but they agree well on the transit depth in most sectors. The Phase-4 uncertainty is propagated as an additional error budget term.

After Phase 4 comes the window/polynomial grid search (Phase 5), the 576-fold kernel screening (Phase 6), and the Phase 6R remediation. The combined result is that neither a single detrending model nor a single noise model was formally adopted.

In parallel with the noise analysis, there is a descriptive transit fit. The 120-second reference light curve is phase-folded on the official ephemeris and a circular analytic transit model is fit using `batman` and `emcee`. Five parameters are free: $R_p/R_*$, $a/R_*$, impact parameter $b$, a flux baseline offset, and a white-noise jitter term added in quadrature to the photon noise. Limb-darkening is fixed using quadratic coefficients from the PHOENIX specific-intensity library. The chain runs 48 walkers through 1200 burn-in steps and 6000 production steps, discarding the first 750 flattened steps.

A native-cadence joint fit across all six sectors is also run, sharing geometry parameters across sectors while allowing per-sector radius ratios, baselines, and jitter floors. That chain does not converge under the production run settings (the autocorrelation time rule fails), so it is kept as a historical robustness diagnostic. The per-sector radius ratios from that fit scatter between about 0.053 and 0.056 across the six sectors.

The descriptive fit is designed to check the stellar density. The fitted $a/R_*$ determines the photometric stellar density under the circular orbit assumption, coming out around 0.18 solar units. The stellar density inferred from the stellar parameters is around 0.072 solar units. These are discrepant by roughly 4 sigma. The project notes the discrepancy and treats it as a limiting factor on geometric interpretation.

The stellar characterization is handled separately. A blackbody SED fit using `emcee` over 2MASS JHKs and AllWISE W1 through W4 photometry recovers a stellar radius of about 2.51 solar radii and a temperature near 6447 K. An equal-brightness unresolved binary branch is also computed. The SED result is logged as an approximate consistency cross-check.

An asteroseismic feasibility assessment was run using the ATL methodology and the `pysyd` pipeline, but the expected signal-to-noise for solar-like oscillations is below detectable levels given the available TESS data.

## False-positive vetting

The false-positive analysis uses three lines of evidence.

The Gaia DR3 census queries all sources within 120 arcseconds of the target. There are 501 of them. The target itself has a RUWE of 0.985. Of the 501 neighbors, 10 are bright enough that if they were completely eclipsed they could produce the observed transit signal through dilution. Seven of those could do it at 50% eclipse depth. The nearest Gaia source to the target is matched at 0.006 arcseconds, which is the target itself. The brightest neighbor in the field is about 106 arcseconds away at G = 11.6 mag.

The TRICERATOPS false-positive probability tool was run on the phase-folded 120-second light curve, querying within 10 TESS pixel radii and using 1000 Monte Carlo draws. The returned FPP is numerically NaN. This is a consequence of internal normalization in TRICERATOPS 1.0.20. The NFPP is exactly 0.0.

The PRF source-localization analysis fits a simplified Gaussian PRF to the per-pixel in-transit depth map in each sector. The target contributes a fitted depth amplitude of around 500 ppm in most sectors. Brighter sources at separations above 100 arcseconds show larger fitted amplitudes, an artifact of the simplified PRF model. 

Secondary eclipse, odd-even depth, and phase-curve searches were run as ancillary checks. No secondary eclipse is detected at phase 0.5. The odd and even transit depths are consistent within their uncertainties. No coherent harmonic signal is found in the out-of-transit baseline. The formal WP-09A sector heterogeneity test passes.

## What is not claimed and why

There is no mass measurement. The catalog mass from TIC v8 is 1.25 solar masses with an uncertainty of 0.19 solar masses, which is an input.

There is no eccentricity measurement. An eccentric transit model was run as an exploratory diagnostic, but the photometric data alone cannot distinguish between a circular orbit with an inflated host star and an eccentric orbit transiting near pericenter.

There is no TTV detection. A TTV analysis was run and the result is null.

There is no validation. TRICERATOPS returned a numerically inconclusive FPP. There is no high-resolution imaging contrast curve. The candidate is unvalidated and unconfirmed.

There is no formally adopted noise model. Phase 6 failed stationarity under every complex kernel, and Phase 6R failed the residual correlation threshold. 

The injection-recovery Stage 3 analysis has not been successfully executed. Three protocol revisions were attempted; all are closed with no scientific output.

## Adapting this to another target

The pipeline was written specifically for TOI-3492.01, but the overall structure (quality audit, reduction comparison, grid-based window/polynomial selection, multi-kernel GP screening, descriptive transit fit, false-positive vetting) applies to any TESS planetary candidate with enough sectors and transit events. See `docs/potansiyel.md` for a worked-through candidate selection and feasibility analysis for the next target.

### Target selection criteria

Before running the pipeline on a new target, the following should hold:

- Multiple TESS sectors exist, with enough transit windows that at least 12-15 survive the quality and coverage cuts.
- The star is bright enough (TESS magnitude < ~12) that photon noise does not dominate over systematics in 120-second cadence.
- No published paper or active TFOP working group is in late-stage follow-up on the same candidate. Check ExoFOP, NASA Exoplanet Archive, and arXiv before committing.
- Gaia DR3 RUWE is below 1.4 and `non_single_star = 0`. A high `rv_amplitude_robust` in Gaia (above ~1 km/s) should be investigated with reconnaissance spectroscopy before investing in photometric analysis.

### Seven-day kill test

Before building out the full pipeline for a new target, run a quick feasibility check:

1. Inventory SPOC, QLP, and TESS-SPOC products via `lightkurve`.
2. Recover the signals independently in each sector with BLS or TLS.
3. Try multiple apertures and detrending methods and check that the signal is not detrending-dependent.
4. For candidates with ambiguous periods, test `P` and `2P` (odd/even event separation, likelihood comparison).
5. Run odd/even, secondary eclipse, centroid, and difference-image checks.
6. Compute the eclipse depth required for each Gaia neighbor to produce the observed signal through dilution.
7. Extract event-level transit times and check for obvious TTVs or sector-to-sector depth variation.
8. Run a preliminary stellar SED or isochrone fit.
9. Produce a one-page go/no-go summary before committing further time.

### Stop conditions

Stop and reassess if any of the following appear:

- Signals are present only in a single sector.
- The signal amplitude depends strongly on aperture or detrending choice.
- Difference-image centroid points away from the target star toward a Gaia neighbor.
- Odd/even depth or timing asymmetry is consistent with an eclipsing binary.
- Transit durations are inconsistent with a common stellar density for a multi-candidate system.
- Gaia `rv_amplitude_robust` is confirmed at km/s level in new reconnaissance spectra.
- A group with imaging or spectroscopic follow-up is already near publication on the same target.

### Config files to update

| File | What to replace |
|---|---|
| `data/official_toi_metadata.json` | Ephemeris and coordinates from NASA Exoplanet Archive |
| `data/config_corrected_120s.json` | Stellar parameters, limb-darkening coefficients, transit solution |
| `data/tic_v8_target.json` | TIC v8 record, retrievable with `astroquery.mast.Catalogs.query_criteria(catalog='Tic', ID=<tic_id>)` |

Several scripts also hardcode constants at the top of the file: `build_120s_reference_lightcurve.py`, `transit_model_120s_corrected.py`, and `check_20s_independent.py`. T0 in BTJD is BJD_TDB minus 2457000.

### Structural assumptions to revisit

The sector structure assumes exactly six sectors. Scripts that do per-sector audits, depth comparisons, or the Phase-5B branch structure have that count baked in. The `lightkurve` download step queries MAST and retrieves whatever is available, but the downstream accounting expects six sectors.

Limb-darkening coefficients are target-specific. The config includes LDTk-computed quadratic coefficients, but `transit_model_120s_corrected.py` recomputes them from the stellar parameters if run fresh. If the TIC metallicity for the target is null (common), the analysis uses [Fe/H] = 0.0 with 0.15 dex uncertainty as an interpolation width.

The Phase-5 window grid (13, 16, 20, 26, 32 hours) was chosen to bracket the transit duration of TOI-3492.01 (~5.3 hours). For a target with a significantly shorter or longer transit, the grid should be adjusted before running. The beta threshold of 1.2 in Phase 6R is documented in `data/faz6_preregistered_kernels.json` and must be set before running Phase 6R, not adjusted afterwards.

For multi-planet systems, the pipeline as written handles one transit signal at a time. Running it on a system with two or three candidates requires either running independent instances per candidate or extending the joint-fit scripts to handle multiple periods simultaneously.

Output filenames throughout the codebase contain `toi3492` or refer to `TOI-3492`. If running multiple targets side by side in the same repository, update the output paths at the top of each script to avoid collisions.

### Stage 3 injection-recovery

The Stage 3 injection-recovery framework is a research prototype. Three protocol revisions for TOI-3492.01 are closed with no scientific use. For a new target, a fresh protocol must be written, independently reviewed before execution, and the synthetic/numerical calibration run before any real-data model. The authority chain for Stage 3 authorization is described in `protocols/stage3/index.json` and `docs/lab/GOVERNANCE.md`.

## Software

The core dependencies are `lightkurve`, `batman-package`, `emcee`, `celerite`, `ldtk`, `corner`, `astropy`, `astroquery`, `numpy`, `scipy`, `pandas`, and `matplotlib`. All versions are pinned in `pyproject.toml`. Python 3.9.x is required.

```bash
git clone https://github.com/shenfurkan/toi3492-characterization.git
cd toi3492-characterization
pip install -e ".[test]"

# optional extras
pip install -e ".[screening]"        # TRICERATOPS
pip install -e ".[asteroseismology]" # pySYD
```

```bash
python -m pytest                             # unit test suite
python scripts/audit_science_consistency.py  # offline science consistency audit
python scripts/audit_manuscript_math.py      # verify all numbers in the manuscript
```
