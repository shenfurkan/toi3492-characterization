# TOI-3492.01 Photometric Characterization

Photometric characterization pipeline for the TESS transit candidate **TOI-3492.01** (TIC 81077799). The pipeline covers data quality auditing, multi-approach detrending, grid-based model selection, Gaussian process noise screening, MCMC transit fitting, and false-positive vetting. The methodology is reproducible and preregistered.

## The target

TOI-3492.01 is a transit candidate identified by the TESS automated pipeline and listed as a Planet Candidate (PC disposition) in the NASA Exoplanet Archive. The host star, TIC 81077799, sits at roughly 202 parsecs and has a TESS magnitude of 8.45. Its effective temperature is around 6332 K, its surface gravity log g ≈ 3.71, and its radius is about 2.59 solar radii. This combination (hot, low surface gravity, inflated radius) makes it a subgiant. The stellar density implied by the transit duration and shape should be consistent with the density derived from the stellar parameters independently. As described below, they are not consistent under a simple circular orbit interpretation.

The candidate transits every 9.2224171 days with a depth of roughly 3100 ppm and a duration of about 5.3 hours. The catalog radius estimate is around 15.7 Earth radii and the equilibrium temperature is near 1477 K. None of these parameters have been independently confirmed. There is no radial velocity mass measurement. The object is unvalidated and unconfirmed.

The TESS observations cover six sectors: 37, 63, 64, 90, 99, and 100. Both 120-second and 20-second cadence SPOC products exist for most sectors. Eighteen transit windows were expected across those sectors; sixteen were usable after accounting for data gaps and quality flags. Note that sixteen transits from six sectors are not sixteen independent observations, as they come from the same pixels, instrument, and reduction pipeline, meaning systematic errors are correlated.

## What this paper is actually arguing

The main argument of the paper is methodological.

The first problem is model selection. When phase-folding a multi-sector TESS light curve and fitting a transit, choices must be made about the window width around the transit, the polynomial order for the out-of-transit baseline, and the handling of different noise properties across sectors. Usually, a single "best" model is presented. This project evaluates a grid of 576 combinations of window widths (13, 16, 20, 26, and 32 hours) and polynomial orders (0, 1, 2) across all sectors. Rather than picking one arbitrarily, it carries 24 branches forward into all subsequent analysis, making the model-selection uncertainty part of the output.

The second problem is noise modeling. Photometric residuals from TESS data often have correlated noise structures. The standard response is to fit a Gaussian process. The project tests four kernels: pure white noise (K0), an Ornstein-Uhlenbeck process (K1), a Matérn-3/2 kernel (K2), and a stochastically driven harmonic oscillator (K3). None of the 576 branch-kernel combinations passed the stationarity gate for the complex kernels. The white-noise model was rerun across all 24 branches in a remediation phase (Phase 6R), and the residuals still showed detectable excess correlation — a weighted beta statistic of 1.294 at 80-minute binning, against a preregistered threshold of 1.2. The formal result is a failure.

The third problem is post-hoc adjustment of thresholds. This project preregisters its thresholds (the beta limit of 1.2, the stationarity tolerance, the kernel candidate set, the window/polynomial grid) in protocol files before running the relevant analysis. Those files are version-controlled and their hashes are recorded.

## How the pipeline actually works

Starting from the raw SPOC data products, the pipeline proceeds through a sequence of phases, each with its own pass/fail gate.

First, all eighteen SPOC files are downloaded from MAST and cross-checked against a manifest. Time systems are verified — the analysis works in BTJD throughout (BJD in TDB minus 2457000). Quality flags are applied using the standard TESS bitmask. A complete cadence ledger is built for both cadences.

Each expected transit window is located and checked for adequate coverage. A window that sits in a data gap, or where a TESS momentum dump lands in the middle of the transit, is flagged and excluded. Of the eighteen expected windows, sixteen survive this check.

Before transit fitting happens, each sector goes through a quality audit: background flux levels, pointing metric scatter, CBV contamination relative to the raw SAP flux, and a comparison against control stars observed in the same sectors. The control star comparison distinguishes noise intrinsic to the target from noise shared across the focal plane. This audit is Phase 3 and it passes.

Phase 4 compares four detrending approaches: simple polynomial detrending over the out-of-transit baseline, CBV-corrected flux from the SPOC pipeline, PDC-SAP flux as delivered, and a local window-polynomial approach. None of these is perfect. They agree well on the transit depth in most sectors, but there is a residual systematic difference between reductions at the level of a few tens of ppm in depth. The Phase-4 uncertainty is propagated as an additional error budget term.

After Phase 4 comes the window/polynomial grid search (Phase 5), the 576-fold kernel screening (Phase 6), and the Phase 6R remediation. The combined result is that neither a single detrending model nor a single noise model was formally adopted.

In parallel with the noise analysis, there is a descriptive transit fit. The 120-second reference light curve is phase-folded on the official ephemeris and a circular analytic transit model is fit using `batman` and `emcee`. Five parameters are free: $R_p/R_*$, $a/R_*$, impact parameter $b$, a flux baseline offset, and a white-noise jitter term added in quadrature to the photon noise. Limb-darkening is fixed using quadratic coefficients from the PHOENIX specific-intensity library. The chain runs 48 walkers through 1200 burn-in steps and 6000 production steps, discarding the first 750 flattened steps. Every parameter exceeds 50 integrated autocorrelation times.

A native-cadence joint fit across all six sectors is also run, sharing geometry parameters across sectors while allowing per-sector radius ratios, baselines, and jitter floors. That chain does not converge under the production run settings, so it is kept as a historical robustness diagnostic. The per-sector radius ratios scatter between about 0.053 and 0.056 across the six sectors.

The descriptive fit is designed to check the stellar density. The fitted $a/R_*$ determines the photometric stellar density under the circular orbit assumption, coming out around 0.18 solar units. The stellar density inferred from the stellar parameters is around 0.072 solar units. These are discrepant by roughly 4 sigma. This could indicate an eccentric orbit, incorrect stellar parameters, or transit dilution from a background star. The project notes the discrepancy and treats it as a limiting factor on geometric interpretation.

The stellar characterization is handled separately. A blackbody SED fit over 2MASS JHKs and AllWISE W1 through W4 photometry recovers a stellar radius of about 2.51 solar radii and a temperature near 6447 K. An equal-brightness unresolved binary branch is also computed. No MIST isochrone grid was run, so no coherent mass-radius covariance or age is derived.

An asteroseismic feasibility assessment was run, but the expected signal-to-noise for solar-like oscillations is below detectable levels given the available TESS data — ATL detection probability of about 12% at 120 seconds.

## False-positive vetting

The false-positive analysis uses three lines of evidence.

The Gaia DR3 census queries all sources within 120 arcseconds of the target. There are 501 of them. The target itself has a RUWE of 0.985. Of the 501 neighbors, 10 are bright enough that if completely eclipsed they could produce the observed transit signal through dilution. Seven of those could do it at 50% eclipse depth. The nearest Gaia source is the target itself at 0.006 arcseconds. The brightest neighbor in the field is about 106 arcseconds away at G = 11.6 mag.

The TRICERATOPS false-positive probability tool was run on the phase-folded 120-second light curve, querying within 10 TESS pixel radii and using 1000 Monte Carlo draws. The returned FPP is numerically NaN. This is a consequence of internal normalization in TRICERATOPS 1.0.20: when the stellar density model and transit geometry are sufficiently inconsistent, the scenario probability sum goes to zero numerically. The NFPP is exactly 0.0. No calibrated population FPP is reported.

The PRF source-localization analysis fits a simplified Gaussian PRF to the per-pixel in-transit depth map in each sector. The target contributes a fitted depth amplitude of around 500 ppm in most sectors. Brighter sources at separations above 100 arcseconds show larger fitted amplitudes, an artifact of the simplified PRF model. The PRF analysis is qualitative and does not appear as a formal false-positive exclusion.

Secondary eclipse, odd-even depth, and phase-curve searches were run as ancillary checks. No secondary eclipse is detected at phase 0.5. The odd and even transit depths are consistent within their uncertainties. No coherent harmonic signal is found in the out-of-transit baseline. The formal WP-09A sector heterogeneity test passes.

## What is not claimed and why

There is no mass measurement. No radial velocity data exist for this target. The catalog mass from TIC v8 is 1.25 solar masses with an uncertainty of 0.19 solar masses, which is an input.

There is no eccentricity measurement. An eccentric transit model was run as an exploratory diagnostic, but the photometric data alone cannot distinguish between a circular orbit with an inflated host star and an eccentric orbit transiting near pericenter.

There is no TTV detection. A TTV analysis was run and the result is null.

There is no validation. TRICERATOPS returned a numerically inconclusive FPP. There is no high-resolution imaging contrast curve. The candidate is unvalidated and unconfirmed.

There is no formally adopted noise model. Phase 6 failed stationarity under every complex kernel, and Phase 6R failed the residual correlation threshold.

The injection-recovery Stage 3 analysis has not been successfully executed. Three protocol revisions were attempted; all are closed with no scientific output. This is the primary remaining gap in the methodology paper.

## Adapting this to another target

The pipeline was written specifically for TOI-3492.01, but the overall structure (quality audit, reduction comparison, grid-based window/polynomial selection, multi-kernel GP screening, descriptive transit fit, false-positive vetting) applies to any TESS planetary candidate with enough sectors and transit events.

Before running the pipeline on a new target, a few things should hold. Multiple TESS sectors must exist with enough transit windows that at least 12-15 survive the quality and coverage cuts. The star should be bright enough (TESS magnitude below roughly 12) that photon noise does not dominate over systematics in 120-second cadence. No published paper or active TFOP working group should be in late-stage follow-up on the same candidate. Gaia DR3 RUWE should be below 1.4. A high Gaia `rv_amplitude_robust` (above roughly 1 km/s) should be investigated with reconnaissance spectroscopy before investing further.

Before building out the full pipeline for a new target, run a quick feasibility check first: inventory the available SPOC, QLP, and TESS-SPOC products; recover the signals independently in each sector with BLS or TLS; try multiple apertures and detrending methods; for candidates with ambiguous periods test both P and 2P; run odd/even, secondary eclipse, centroid, and difference-image checks; compute the eclipse depth required for each Gaia neighbor to produce the observed signal through dilution; extract event-level transit times. Produce a one-page go/no-go summary before committing further time.

Stop and reassess if any of the following appear: signals are present only in a single sector; the signal amplitude depends strongly on aperture or detrending choice; the difference-image centroid points away from the target toward a Gaia neighbor; odd/even depth or timing asymmetry is consistent with an eclipsing binary; transit durations are inconsistent with a common stellar density; Gaia RV amplitude is confirmed at km/s level in new reconnaissance spectra; a group with imaging or spectroscopic follow-up is already near publication on the same target.

The target-specific constants (ephemeris, stellar parameters, limb-darkening coefficients, TIC record) are read from config files in the data directory. These files are not tracked in git and must be created for each new target. Several scripts also hardcode the target name, period, T0, and transit duration at the top of the file and must be updated directly. T0 in BTJD is BJD_TDB minus 2457000.

The sector structure assumes exactly six sectors. Scripts that do per-sector audits, depth comparisons, or the Phase-5B branch structure have that count baked in. If the target has a different number of sectors, those assumptions must be found and updated.

Limb-darkening coefficients are recomputed from the stellar parameters each time the transit model script is run fresh, so only the stellar T_eff, log g, and metallicity need to be correct. If the TIC metallicity is null (common), the analysis uses [Fe/H] = 0.0 with 0.15 dex uncertainty as an interpolation width.

The Phase-5 window grid (13, 16, 20, 26, 32 hours) brackets the transit duration of TOI-3492.01. For a target with a significantly shorter or longer transit, the grid should be adjusted. The beta threshold of 1.2 in Phase 6R is a scientific judgment and must be set before running, not adjusted afterwards to make a failed phase pass.

For multi-planet systems, the pipeline handles one transit signal at a time. Running it on a system with multiple candidates requires either independent instances per candidate or extending the joint-fit code to handle multiple periods.

The Stage 3 injection-recovery framework is a research prototype. Three protocol revisions for TOI-3492.01 are closed with no scientific use. For a new target, a fresh protocol must be written, independently reviewed before execution, and the synthetic calibration run before any real-data model.

## Software

The core dependencies are `lightkurve` for MAST data access and TESS light curve handling, `batman-package` for the analytic transit model, `emcee` for affine-invariant MCMC, `celerite` for Gaussian process fitting, `ldtk` for limb-darkening coefficients from PHOENIX model atmospheres, `corner` for posterior visualization, `astropy` and `astroquery` for coordinate handling and catalog queries, and standard scientific Python (`numpy`, `scipy`, `pandas`, `matplotlib`). All versions are pinned in the project configuration. `triceratops` and `pysyd` are optional extras. Python 3.9.x is required.

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

## License

GNU General Public License v3.0, see LICENSE for details.
