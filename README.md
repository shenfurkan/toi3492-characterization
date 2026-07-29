# TOI-3492.01 Photometric Characterization

This repository is the full working codebase for a photometric characterization of the TESS transit candidate **TOI-3492.01** (TIC 81077799). It is also, probably more importantly, the repository for a methodology paper — one that is fundamentally about how to do this kind of analysis reproducibly and honestly, rather than about this particular planet candidate. TOI-3492.01 is the case study. The pipeline is the contribution.

The primary publication target is PASP or MNRAS. This file, read together with the manuscript (`toi3492_characterization.tex`) and the documentation under `docs/`, should give you a complete picture of what the project has done, what it has found, and — just as importantly — what it has not found and does not claim.

---

## The target

TOI-3492.01 is a transit candidate identified by the TESS automated pipeline and currently listed as a Planet Candidate (PC disposition) in the NASA Exoplanet Archive. The host star, TIC 81077799, sits at roughly 202 parsecs and has a TESS magnitude of 8.45 — fairly bright for a TESS target, which is part of what makes the photometric analysis tractable. Its effective temperature is around 6332 K, its surface gravity log g ≈ 3.71, and its radius is about 2.59 solar radii. That combination — hot, low surface gravity, inflated radius — puts it squarely in subgiant territory. It is not quite a main-sequence star anymore, and that matters for interpreting the transit geometry, because the stellar density implied by the transit duration and shape (the photometric density, which comes from the fitted $a/R_*$) should be consistent with the density you get from the stellar parameters independently. As described below, they are not, at least not under a simple circular orbit interpretation, and the project is honest about that.

The candidate itself transits every 9.2224171 days with a depth of roughly 3100 ppm and a duration of about 5.3 hours. The catalog radius estimate is around 15.7 Earth radii and the equilibrium temperature comes in near 1477 K, which puts it in the warm sub-Saturn to warm Jupiter regime. None of these parameters have been independently confirmed. There is no radial velocity mass measurement. The object is unvalidated and unconfirmed, and that is exactly how the analysis describes it throughout.

The TESS observations cover six sectors: 37, 63, 64, 90, 99, and 100, spanning several years. Both 120-second and 20-second cadence SPOC products exist for most sectors. Eighteen transit windows were expected across those sectors; sixteen were usable after accounting for data gaps and quality flags. That is a reasonable number of transits for a photometric study, though it is worth noting that "sixteen transits from six sectors" is not the same as "sixteen independent observations" — they all come from the same pixels, the same instrument, and the same reduction pipeline, so systematic errors are correlated in ways that pure count statistics do not capture.

---

## What this paper is actually arguing

Most TESS photometric candidate papers follow a fairly standard structure: download the data, fit a transit model, check a few false-positive diagnostics, and report the parameters. This project does all of that, but the main argument of the paper is methodological rather than observational. The claim is that the standard approach has some problems that are worth taking seriously.

The first problem is model selection. When you phase-fold a multi-sector TESS light curve and fit a transit, you have to make choices about how wide a window around transit to use, what polynomial order to use for the out-of-transit baseline, and how to handle the fact that different sectors may have different noise properties. These choices are usually made informally and a single "best" model is presented as if it were the obvious choice. This project instead evaluates a grid of 576 combinations of window widths (13, 16, 20, 26, and 32 hours) and polynomial orders (0, 1, 2) across all sectors, and documents that no single combination is clearly superior. Rather than picking one arbitrarily, it carries 24 branches forward into all subsequent analysis, so the model-selection uncertainty is part of the output rather than buried in a judgment call the reader cannot scrutinize.

The second problem is noise modeling. Even after detrending, photometric residuals from TESS data are often not white. There are correlated noise structures — instrumental or astrophysical — that survive the standard pipeline and can affect parameter estimates if not accounted for. The standard response is to fit a Gaussian process, but which kernel? The project tests four: pure white noise (K0), an Ornstein-Uhlenbeck process (K1), a Matérn-3/2 kernel (K2), and a stochastically driven harmonic oscillator (K3). Complex kernels require passing a stationarity test first, because fitting a non-stationary GP to stationary data or vice versa gives misleading results. As it turned out, none of the 576 branch-kernel combinations passed the stationarity gate for the complex kernels. The white-noise model was rerun across all 24 branches in a remediation phase (Phase 6R), and the residuals still showed detectable excess correlation — a weighted beta statistic of 1.294 at 80-minute binning, against a preregistered threshold of 1.2. The formal result is a failure. That failure is reported in the paper, not hidden.

The third problem is post-hoc adjustment of thresholds. If you decide whether a model passes or fails only after seeing the results, you can always find a threshold at which your preferred answer comes out. This project preregisters its thresholds — the beta limit of 1.2, the stationarity tolerance, the kernel candidate set, the window/polynomial grid — in JSON protocol files before running the relevant analysis. Those files are version-controlled and their hashes are recorded. If the threshold had been 1.3 instead of 1.2, Phase 6R would have passed. But it was 1.2, that was the choice made before running, and the result is what it is.

---

## How the pipeline actually works

Starting from the raw SPOC data products, the pipeline proceeds through a sequence of phases, each with its own pass/fail gate.

The first thing that happens is a complete inventory of the expected data products. All eighteen SPOC files are downloaded from MAST via `lightkurve` and cross-checked against a manifest. Time systems are verified — the analysis works in BTJD throughout (BJD in TDB minus 2457000), and the conversion from raw timestamps is confirmed before any science computation touches the data. Quality flags are applied using the standard TESS bitmask. A complete cadence ledger is built for both cadences.

Each expected transit window is then located and checked for adequate coverage. A window that sits in a data gap, or where the TESS momentum dump lands in the middle of the transit, is flagged and excluded. Of the eighteen expected windows, sixteen survive this check. The excluded two are not filled in, interpolated over, or handled in any way — they are simply absent from the analysis, and the impact of their absence is noted.

Before any transit fitting happens, each sector is put through a quality audit: background flux levels, pointing metric scatter, CBV contamination relative to the raw SAP flux, and a comparison against several control stars observed in the same sectors. The control star comparison is useful because it distinguishes between noise that is intrinsic to the target (astrophysical variability, shot noise) and noise that is shared across the focal plane (instrumental systematics, scattered light episodes). If a control star shows a similar structure to the target at a similar time, the feature is probably not real. This audit is Phase 3 and it passes — the photometric environment across the six sectors is stable enough to proceed.

Phase 4 compares four different detrending approaches on the same data: simple polynomial detrending over the out-of-transit baseline, CBV-corrected flux from the SPOC pipeline, PDC-SAP flux as delivered, and a local window-polynomial approach. None of these is perfect. They agree well on the transit depth in most sectors, but there is a residual systematic difference between reductions at the level of a few tens of ppm in depth, which is not negligible relative to the overall depth uncertainty. Rather than picking one reduction and discarding the others, the Phase-4 uncertainty is propagated as an additional error budget term into everything downstream.

After Phase 4 comes the window/polynomial grid search described above (Phase 5), the 576-fold kernel screening (Phase 6), and the Phase 6R remediation. All of that is covered in the previous section. The combined result of those phases is that neither a single detrending model nor a single noise model was formally adopted — the analysis ends with 24 branches and a documented residual correlation problem. This is not a pipeline failure in any code sense; it is an honest characterization of what the data support.

In parallel with all of the noise analysis, there is a descriptive transit fit. The 120-second reference light curve is phase-folded on the official ephemeris and a circular analytic transit model is fit using `batman` for the model and `emcee` for posterior sampling. Five parameters are free: $R_p/R_*$, $a/R_*$, impact parameter $b$, a flux baseline offset, and a white-noise jitter term added in quadrature to the photon noise. Limb-darkening is fixed — quadratic coefficients from the PHOENIX specific-intensity library, interpolated at the TIC stellar parameters (T_eff = 6332 K, log g = 3.71, [Fe/H] = 0.0 assumed because the TIC value is null) using `ldtk`. The chain runs 48 walkers through 1200 burn-in steps and 6000 production steps, discarding the first 750 flattened steps. Every parameter exceeds 50 integrated autocorrelation times, which is the standard `emcee` convergence heuristic. This is described as a well-converged descriptive reference fit, not as adopted final parameters, because it uses phase-folded binned data rather than the native-cadence time series, and because the noise model under which it is run has not passed the Phase 6 gates.

A native-cadence joint fit across all six sectors is also run, sharing geometry parameters across sectors while allowing per-sector radius ratios, baselines, and jitter floors. That chain does not converge under the production run settings — the autocorrelation time rule fails — so it is kept as a historical robustness diagnostic rather than promoted to adopted parameters. The per-sector radius ratios from that fit are still informative: they scatter between about 0.053 and 0.056 across the six sectors, with no obvious outliers, which is consistent with a stable astrophysical signal rather than a sector-specific instrumental artefact.

One specific thing the descriptive fit is designed to check is the stellar density. The fitted $a/R_*$ determines the photometric stellar density (via Kepler's third law) under the circular orbit assumption. That density comes out around 0.18 solar units. The stellar density inferred from the stellar parameters — mass and radius from TIC v8 — is around 0.072 solar units. These are discrepant by roughly 4 sigma in a naive comparison. This could mean the orbit is eccentric (a larger $a/R_*$ than the circular value would give, explained by the transit occurring near pericenter), it could mean the stellar parameters are off, or it could mean the transit is diluted (the signal is coming from a fainter background star, so the real depth is larger and the real radius ratio is larger, which geometrically requires a different $a/R_*$). The project does not adjudicate between these explanations — it notes the discrepancy explicitly and treats it as a limiting factor on any geometric interpretation.

The stellar characterization is handled separately. A blackbody SED fit using `emcee` over 2MASS JHKs and AllWISE W1 through W4 photometry recovers a stellar radius of about 2.51 solar radii and a temperature near 6447 K, broadly consistent with the TIC. An equal-brightness unresolved binary branch is also computed: if the observed SED comes from two identical components rather than one, each component has a radius around 1.77 solar radii. No MIST isochrone grid was run (unavailable in the offline environment used for this analysis), so no coherent mass-radius covariance or age is derived. The SED result is logged as an approximate consistency cross-check, not an independent stellar solution.

An asteroseismic feasibility assessment was run using the ATL (Asteroseismic Target List) methodology and the `pysyd` pipeline, but the expected signal-to-noise for solar-like oscillations at the target's parameters is below detectable levels given the available TESS data — ATL detection probability of about 12% at 120 seconds. No oscillation signal is claimed and the asteroseismic scripts are not part of the core analysis chain.

---

## False-positive vetting

The false-positive analysis brings in three different lines of evidence.

The Gaia DR3 census queries all sources within 120 arcseconds of the target. There are 501 of them. The target itself has a RUWE of 0.985, comfortably below the 1.4 threshold that often indicates an unresolved binary companion perturbing the Gaia astrometric solution. Of the 501 neighbors, 10 are bright enough that if they were completely eclipsed (100% depth) they could produce the observed transit signal through dilution. Seven of those could do it at 50% eclipse depth. The nearest Gaia source to the target is matched at 0.006 arcseconds — that is the target itself. The brightest neighbor in the field is about 106 arcseconds away at G = 11.6 mag, well outside the aperture for most sector configurations.

The TRICERATOPS false-positive probability tool was run on the phase-folded 120-second light curve, querying within 10 TESS pixel radii and using 1000 Monte Carlo draws. The returned FPP is numerically NaN. This is not a code crash — it is a consequence of internal normalization in the version of TRICERATOPS used (1.0.20): when the stellar density model and transit geometry are sufficiently inconsistent, the scenario probability sum can go to zero or round to it numerically, producing a NaN FPP. The NFPP (Nearby False Positive Probability) is exactly 0.0. No calibrated population FPP is reported anywhere in the paper; the TRICERATOPS run is logged as a method-development attempt and explicitly quarantined from the claim chain.

The PRF source-localization analysis fits a simplified Gaussian PRF (FWHM approximately one TESS pixel, about 21 arcsec) to the per-pixel in-transit depth map in each sector, using non-negative least squares. The target contributes a fitted depth amplitude of around 500 ppm in most sectors. Brighter sources at separations above 100 arcseconds — well outside any reasonable aperture — show larger fitted amplitudes, which is an artifact of the simplified PRF model not capturing the actual pixel response function shape. The SPOC difference-image centroid results and the source-specific aperture geometry are also recorded and broadly consistent with an on-target signal, but neither constitutes a calibrated centroid localization likelihood. The PRF analysis is described as qualitative and does not appear as a formal false-positive exclusion in the paper.

Secondary eclipse, odd-even depth, and phase-curve searches were all run as ancillary checks. No secondary eclipse is detected at phase 0.5. The odd and even transit depths are consistent within their uncertainties. No coherent harmonic signal is found in the out-of-transit baseline, though the analysis notes that the phase-curve search is systematics-limited and a weak signal could be hidden. The formal WP-09A sector heterogeneity test passes: the six-sector depth variation is not statistically significant at the level that would suggest different sources of the signal in different sectors.

---

## What is not claimed and why

It is worth being explicit about this because several things that are routinely claimed in TESS photometric candidate papers are not claimed here.

There is no mass measurement. No radial velocity data exist for this target. The catalog mass from TIC v8 is 1.25 solar masses with an uncertainty of 0.19 solar masses — that is the input for computing some auxiliary quantities, not a result of this analysis.

There is no eccentricity measurement. An eccentric transit model was run as an exploratory diagnostic, but the photometric data alone cannot distinguish between a circular orbit with an inflated host star and an eccentric orbit that happens to transit near pericenter. The photometric density discrepancy noted above is consistent with eccentricity but does not require it.

There is no TTV detection. A TTV analysis was run and the result is null — no individual transit timing variation was recovered at significant level. This is not surprising given the cadence and baseline.

There is no validation. TRICERATOPS returned a numerically inconclusive FPP. There is no high-resolution imaging contrast curve. There is no spectroscopic analysis beyond the TIC stellar parameters. The candidate is described as unvalidated and unconfirmed throughout, and that is the only accurate description of its current state.

There is no formally adopted noise model. Phase 6 failed stationarity under every complex kernel. Phase 6R failed the residual correlation threshold. The white-noise model was used for the descriptive transit fit, but it was used knowing it fails its own gate. This is documented, not hidden.

The injection-recovery Stage 3 analysis, which would calibrate what fraction of transit signals the pipeline recovers as a function of depth, duration, and period, has not been successfully executed. Three protocol revisions were attempted; all are closed with no scientific output. This is the primary remaining gap in the methodology paper.

---

## Adapting this to another target

The pipeline was written specifically for TOI-3492.01, but the overall structure — quality audit, reduction comparison, grid-based window/polynomial selection, multi-kernel GP screening, descriptive transit fit, false-positive vetting — is general and could be applied to any TESS planetary candidate with enough sectors and transit events to make the analysis worthwhile.

If you want to run this on a different target, there are two categories of things to change: target-specific constants, and design decisions.

The target-specific constants are scattered across a few places. The two JSON files that act as the primary configuration are `data/official_toi_metadata.json` (which holds the ephemeris and coordinates as retrieved from the NASA Exoplanet Archive) and `data/config_corrected_120s.json` (which holds the stellar parameters, the computed limb-darkening coefficients, and the adopted transit solution). Both of those need to be replaced with values for your target. The TIC v8 record in `data/tic_v8_target.json` also needs to be updated — you can retrieve it with `astroquery.mast.Catalogs.query_criteria(catalog='Tic', ID=<your_tic_id>)`. These files are read by most scripts via the `load_config()` utility in `scripts/utils.py`, so updating them propagates through most of the pipeline automatically.

However, several scripts also hardcode constants at the top of the file in addition to or instead of reading from config. The most important ones are `build_120s_reference_lightcurve.py`, which has `TARGET = "TIC 81077799"`, `OFFICIAL_PERIOD`, `OFFICIAL_T0_BTJD`, and `OFFICIAL_DURATION_HR` all hardcoded; and `transit_model_120s_corrected.py` and `check_20s_independent.py`, which do the same. T0 in BTJD is BJD_TDB minus 2457000 — a simple subtraction, but worth double-checking against the archive value for your target rather than trusting a conversion from an intermediate.

The sector structure is worth thinking about. This analysis assumed exactly six sectors. Scripts that do per-sector audits, depth comparisons, or the Phase-5B branch structure have that count baked into their logic in various places. If your target has two sectors or twelve, you will need to find and update those assumptions. The `lightkurve` download step itself is flexible — it queries MAST and retrieves whatever is available — but the downstream accounting is not.

Limb-darkening coefficients will change with every target because they depend on the stellar parameters. The config includes the LDTk-computed quadratic coefficients, but `transit_model_120s_corrected.py` recomputes them from the stellar parameters in the config if you run it fresh, so in practice you just need the stellar T_eff, log g, and metallicity to be correct in the config and the coefficients will follow. If the TIC metallicity for your target is also null (which is common), the analysis uses [Fe/H] = 0.0 with a 0.15 dex uncertainty as an interpolation width, as it does here. That is a reasonable assumption for a solar-neighborhood star but adds a small systematic that should be acknowledged.

The design decisions are separate from the constants, and they deserve more thought than a find-and-replace pass. The Phase-5 window grid (13, 16, 20, 26, 32 hours) was chosen to bracket the transit duration of TOI-3492.01 (about 5.3 hours) by a generous margin while staying narrow enough that the out-of-transit baseline is not dominated by stellar variability. For a target with a much shorter or longer transit, the grid should be chosen accordingly. The beta threshold of 1.2 in Phase 6R is a scientific judgment about how much residual correlation is acceptable before the noise model is considered inadequate. It is documented in `data/faz6_preregistered_kernels.json`. Whether 1.2 is the right number for a different target is something you should decide before running, not after. If you change it retroactively to make a failed phase pass, you have not improved the analysis — you have invalidated the gate.

The MCMC settings (48 walkers, 1200 burn-in, 6000 production) work well for this target. For a noisier or fainter target where the posterior surface is more complex, you may need more walkers or longer chains. The convergence diagnostics are written to `outputs/mcmc_diagnostics_120s_corrected.json` after every run — check that every parameter exceeds 50 autocorrelation times before treating the posterior as reliable.

Output filenames throughout the codebase contain `toi3492` or refer to `TOI-3492`. If you are running the pipeline on a different target in a fresh clone, you can leave those names as-is and just overwrite the outputs as you go. If you are running multiple targets side by side in the same repository, you should update the output paths at the top of each script, or things will collide in confusing ways.

The Stage 3 injection-recovery framework should be treated as a research prototype regardless of which target you are working on. It is not yet in a state where it can be handed off to someone new and run without deep familiarity with the protocol design. For a new target, you would need to design a fresh protocol, get it independently reviewed before execution, and run the synthetic calibration before any real-data model — in that order, without shortcuts.

---

## Software

The core dependencies are `lightkurve` for MAST data access and TESS light curve handling, `batman-package` for the analytic transit model, `emcee` for affine-invariant MCMC, `celerite` for Gaussian process fitting and likelihood evaluation, `ldtk` for limb-darkening coefficients from PHOENIX model atmospheres, `corner` for posterior visualization, `astropy` and `astroquery` for coordinate handling and catalog queries, and standard scientific Python (`numpy`, `scipy`, `pandas`, `matplotlib`). All versions are pinned in `pyproject.toml`. The `triceratops` false-positive screening tool is an optional extra, as is `pysyd` for asteroseismic analysis. Python 3.9.x is required.

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

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.
