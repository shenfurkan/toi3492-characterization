# Methodology Notes

These notes summarize the targeted course-PDF reading used to support the TOI-3492.01 paper. They are paraphrased working notes, not full PDF conversions.

## Main Source

Michael Perryman, *The Exoplanet Handbook*, 2nd edition, Cambridge University Press, 2018.

## Why Targeted Extraction Instead of Full Conversion

Full PDF-to-Markdown conversion is not currently useful. The exoplanet book is nearly 1000 PDF pages, and a full text conversion would be noisy, hard to cite, and much larger than needed. The paper only needs methodological support for transit detection, transit fitting, false-positive vetting, TTV interpretation, and host-star characterization.

## Relevant Method Points

### Transit Detection and Detrending

Source: Perryman section 6.12.

Transit searches require cleaning and detrending photometric time series before searching for repeated, box-like dimming events. Algorithms related to Box Least Squares are standard for identifying transit-like periodic signals. The current project follows this pattern by using TESS SPOC light curves, removing NaN values and outliers, separating products by cadence, and running a 120 s-only BLS check before physical modeling.

### Light-Curve Fitting

Sources: Perryman sections 6.12.4 and 6.13.3.

Standard transit fitting uses parameters such as mid-transit time, period, inclination, eccentricity, argument of periastron, scaled semimajor axis, planet-to-star radius ratio, and limb-darkening coefficients. MCMC methods are commonly used to sample the posterior distribution and quantify correlated uncertainties.

Project mapping:

- `transit_model_120s_corrected.py` fits `Rp/Rstar`, `a/Rstar`, impact parameter, and baseline.
- Period and epoch are fixed to the official TOI ephemeris after the 120 s BLS check recovers the official period.
- Eccentricity is fixed to zero in the adopted model.
- Limb darkening is fixed to adopted TESS-band quadratic coefficients.
- The density-locked comparison fit is used as a caveat check; the free-geometry corrected fit better matches the transit morphology but has a/Rstar tension with the TIC-density prediction.

### Transit Geometry and Physical Quantities

Sources: Perryman sections 6.13.1-6.13.7.

The principal transit observables include transit depth, duration, impact parameter, and the shape of ingress/egress. To first order, the transit depth is approximately `(Rp/Rstar)^2`, while the physical planet radius requires an independent stellar radius. The scaled semimajor axis is related to the stellar density for a circular orbit, making `a/Rstar` a useful consistency check.

Project mapping:

- The corrected fitted depth is `3167 ppm`.
- The corrected fitted radius ratio is `Rp/Rstar = 0.05628`.
- With `Rstar = 2.5926 Rsun`, this gives `Rp = 15.92 Rearth`.
- The fitted `a/Rstar = 9.21 +/- 0.29` is higher than the Keplerian prediction `a/Rstar = 7.69 +/- 0.50`; this is a limitation and a possible clue that the catalog stellar parameters need spectroscopy, not a validation claim.

### Circular Versus Eccentric Treatment

Sources: Perryman sections 6.13.5-6.13.6.

Transit photometry alone can be degenerate in eccentricity, impact parameter, scaled semimajor axis, and limb darkening. For this project, the circular solution is not claimed to prove that the orbit is circular. It is adopted because the free-eccentricity fit produced a boundary solution and the simpler circular model is the most stable working photometric description.

Correct wording:

- Use: "A circular model is adopted as the current working photometric solution, while noting the a/Rstar tension with the TIC-density prediction."
- Avoid: "The orbit is circularized" unless supported by a tidal analysis or radial velocities.

### Limb Darkening

Source: Perryman section 6.14.1.

Limb darkening changes the transit shape and depends on stellar properties and observing bandpass. Quadratic coefficients are widely used in transit modeling. The current fit fixes TESS-band coefficients computed from Claret (2017) PHOENIX grids with LDTk.

Project mapping:

- Adopted values: `u1 = 0.393`, `u2 = 0.150`.
- Source: Claret 2017 PHOENIX model grids via LDTk.
- Sensitivity result: re-running the corrected MCMC changed fitted parameters by less than `0.1 sigma`, so limb darkening is not responsible for the a/Rstar tension.

### False-Positive Vetting

Source: Perryman section 6.12.5.

Common transit-candidate vetting checks include comparing odd and even transits, searching for secondary eclipses, checking for ellipsoidal variations, and examining centroid shifts or crowded-aperture contamination.

Project mapping:

- Odd/even test: rerun on the corrected 120 s reference light curve; odd/even depths agree to 0.24 sigma.
- Secondary eclipse search: rerun on the corrected 120 s reference light curve; phase-0.5 depth is 9 +/- 15 ppm.
- Ellipsoidal/phase-curve check: not yet done.
- Gaia neighbor/RUWE check: completed; target RUWE is 0.985 and no Gaia source inside 42 arcsec can mimic the full transit depth, but the wider 120 arcsec field is crowded.
- First-pass TESS difference-image check: completed; sector centroids are within about one TESS pixel of the target.
- Formal centroid/source-localization validation: not yet done.
- Conclusion: current tests reduce obvious eclipsing-binary and close-contamination scenarios but do not validate the planet.

### Stellar Activity and Rotation

Sources: Perryman sections 6.14.2 and 8.3.

Star spots and rotational variability can affect transit depths, transit timings, and radial-velocity follow-up. Photometric modulation can be used as a tentative activity diagnostic, but periodogram peaks may be ambiguous and sector-dependent.

Project mapping:

- `stellar_activity.py` finds a weak weighted mean period near `4.4 +/- 1.4 d`.
- The manuscript should call this tentative activity-related variability, not a precise rotation period.

### Transit Timing Variations

Source: Perryman section 6.20.

TTVs can reveal additional planets or dynamical perturbations, but reliable timing requires sufficiently precise individual transit times. Star spots, binning, sampling, and low SNR can mimic or distort timing signals.

Project mapping:

- The phase-folded signal is robust enough for a global transit fit.
- Legacy individual-transit timing used a superseded light-curve treatment.
- Corrected 120 s per-transit timing has been redone and is SNR-limited.
- No TTV detection should be claimed.

### Host-Star Properties

Source: Perryman section 8.2.

Accurate host-star radii are essential for transiting planets because the physical planet radius scales directly with stellar radius. For this target, recognizing TIC 81077799 as an evolved, low-density star is central to the interpretation.

Project mapping:

- TIC v8 gives `Rstar = 2.5926 Rsun`, `Mstar = 1.25 Msun`, and `rho_star = 0.0717 rho_sun`.
- The low density and large radius indicate an evolved subgiant-like host.
- Treating the star as solar-radius would underestimate the planet radius.

## Statistics Source

Ivezic et al., *Statistics, Data Mining, and Machine Learning in Astronomy*.

Relevant section: 5.8, Numerical Methods for Complex Problems / MCMC.

MCMC chains are used to sample posterior distributions. Burn-in samples should be discarded, and convergence or stationarity should be checked using practical diagnostics such as chain behavior, acceptance fraction, autocorrelation estimates, or multiple-chain comparisons. The corrected 120 s fit now saves the raw production chain and reports acceptance fraction plus integrated autocorrelation time.

## Methodology To-Do: Referee-Facing Standard Practice

Question: is the analysis following standard exoplanet practice closely enough for the claim being made?

| Area | Main reference model | Current status | What is missing | What would satisfy a referee |
|---|---|---|---|---|
| Transit detection and fitting | Perryman; Kovacs; Seager | Done: 120 s-only light curve, official-period recovery, batman + emcee MCMC | None for candidate-level photometric characterization | Keep pipeline order reproducible |
| False-positive probability | Morton 2012; Morton 2016; TRICERATOPS | Done: simplified Morton-style FPP gives about `0.01%`; the adopted 100k TRICERATOPS screening run gives FPP numerically `0.0`, with the scenario table dominated by PTP=`0.999997` under run assumptions | VESPA not run; no high-resolution imaging contrast curve; a/Rstar tension remains | Phrase as "passes strong false-positive checks," not "confirmed planet" |
| Evolved-star context | Chontos; Grunblatt; Wittenmyer | Partly done: target framed as a short-period giant-size candidate around a subgiant-like host | More comparison to confirmed evolved-star systems could be added | Cite short-period giant scarcity around subgiants and compare cautiously to TOI-1842b |
| Contamination and imaging | Lillo-Box; Ross | Done: Gaia DR3, RUWE, first-pass TESS difference images, SPOC DV dashboard centroid extraction | No high-resolution imaging, no independent PRF-level centroid modeling, no TESS-band aperture model | Add AO/speckle/lucky imaging or independent PRF/source-localization analysis |
| Stellar parameters and a/Rstar | Perryman; Seager | Done: TIC-density prediction compared to transit a/Rstar; eccentric and density-locked tests performed | No spectroscopy or isochrone-based stellar refinement | Obtain spectroscopy; recompute stellar density and test whether the transit-density tension remains |
| Confirmation | Chontos; Wittenmyer | Not done: no RV mass | Radial velocities absent | Keep official status as planet candidate until RV confirmation or accepted formal validation |

Required language rule:

- Use: "TOI-3492.01 is a giant-planet-size transiting candidate whose signal passes strong false-positive checks."
- Use: "A simplified Morton-style FPP estimate gives about `0.01%`; a TRICERATOPS screening run returns FPP numerically consistent with zero under the run assumptions."
- Avoid: "confirmed planet," "validated planet," "genuine planet," or "statistically validating the planetary nature."
