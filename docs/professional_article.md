# Independent TESS Photometric Characterization of the Giant-Planet-Size Candidate TOI-3492.01

Author: Furkan Şen

Affiliation: Department of Astronomy and Space Sciences, Ankara University

Target: TOI-3492.01 / TIC 81077799

## Abstract

Short-period giant-planet candidates around evolved stars are useful probes of orbital migration and tidal evolution. TOI-3492.01 (TIC 81077799) is a TESS Object of Interest with period P = 9.2224171 d around an evolved F-type subgiant (Rstar = 2.59 Rsun, Teff = 6332 K; Stassun et al. 2019). This work analyzes six public 120 s SPOC TESS light curves. An MCMC transit fit gives Rp/Rstar = 0.05628 +/- 0.00046, a/Rstar = 9.21 +/- 0.29, and b = 0.789 +/- 0.016, implying a candidate radius Rp = 15.92 +/- 0.68 Rearth (1.42 Rjup). The signal appears in all six sectors. Public SPOC DV products independently recover the official-period signal at depth 3128 +/- 30 ppm, Rp = 15.7 +/- 0.7 Rearth, MES = 99.4, and a centroid offset of 0.90 sigma. Odd/even depths, the non-detection of a secondary eclipse, Gaia DR3 neighbor checks, and first-pass TESS difference images support an on-target planet-candidate interpretation. The fitted a/Rstar is 2.6 sigma above the TIC-density prediction; LDTk/Claret limb darkening and an exploratory eccentric fit do not resolve this tension. TOI-3492.01 is therefore a plausible giant-planet-size transiting candidate, not a confirmed or validated planet.

Keywords: exoplanets; transit photometry; TESS; planet candidates; evolved stars; giant planets

## 1. Introduction

The Transiting Exoplanet Survey Satellite (TESS; Ricker et al. 2015) has identified thousands of transiting planet candidates around bright, nearby stars. Among the most astrophysically informative subsets are short-period giant candidates around evolved hosts. As a star departs the main sequence and expands, any surviving close-in companion becomes detectable through a deeper transit signal, while tidal interactions and increased irradiation reshape the system architecture (Seager & Mallen-Ornelas 2003). Systematic characterization of such candidates therefore constrains theories of hot-Jupiter formation and orbital migration around intermediate- and high-mass stars.

TOI-3492.01 is a TESS Object of Interest associated with TIC 81077799. The official TOI ephemeris gives P = 9.2224171 d and a transit depth of approximately 3110 ppm. Stellar parameters from TIC v8 (Stassun et al. 2019) indicate a large, low-density evolved F-type host (Rstar ~ 2.6 Rsun, log g ~ 3.71) rather than a solar-radius dwarf, making the candidate physical radius substantially larger than a naive main-sequence assumption would imply. This work presents an independent photometric analysis of the available public TESS light curves and characterizes the transit signal with a full MCMC parameter estimation.

**Scope limitation:** This is a photometric-only characterization. No radial-velocity mass measurement, high-resolution imaging, or independent spectroscopic stellar parameters are available for this target. TIC 81077799 has never been observed by any major spectroscopic survey, and MAST/STScI network access was blocked during analysis, preventing an independent 20 s cadence check. TOI-3492.01 is therefore reported as a strong transiting planet candidate with robust false-positive vetting, not as a confirmed or validated planet.

## 2. Data and Corrected Light-Curve Construction

Public TESS SPOC light curves were retrieved from MAST with `lightkurve`. TIC 81077799 has nine SPOC products in the local search inventory: 120 s products in Sectors 37, 63, 64, 90, 99, and 100, plus additional 20 s products in Sectors 90, 99, and 100. The corrected analysis uses only the six 120 s products. This avoids duplicate weighting of sectors with both 20 s and 120 s products.

The corrected reference light curve is `toi3492_120s_reference.csv`. It contains 102,502 finite 120 s measurements. Each sector was normalized independently using out-of-transit flux near the official ephemeris. Strong positive outliers were removed while preserving transit-like negative excursions. No transit-suppressing flattening was applied near the expected transit windows.

![Figure 1. Corrected 120 s reference fold.](toi3492_120s_reference_fold.png)

Figure 1. Corrected 120 s SPOC reference light curve folded on the official ephemeris. The red dashed lines mark the official transit-duration window. This product is the photometric basis for the corrected transit fit.

## 3. Host-Star Properties

TIC v8 stellar parameters were queried using `astroquery`. The adopted parameters are listed in Table 1. The star is physically inconsistent with a solar-radius dwarf assumption: its radius, surface gravity, and density indicate an evolved subgiant-like host.

Table 1. Adopted stellar parameters for TIC 81077799.

| Parameter | Value |
|---|---:|
| Teff | 6332 +/- 134 K |
| log g | 3.7075 +/- 0.0835 |
| Rstar | 2.5926 +/- 0.1094 Rsun |
| Mstar | 1.25 +/- 0.19 Msun |
| rho_star | 0.0717 +/- 0.0140 rho_sun |
| TESS magnitude | 8.450 |
| Distance | 201.96 +/- 1.27 pc |

The density computed directly from the TIC mass and radius agrees with the tabulated value, rho_star approximately 0.072 rho_sun. The implied luminosity is approximately 9.7 Lsun. This evolved-host interpretation is central to the physical scale of the candidate: the same radius ratio implies a much larger companion around a 2.6 Rsun star than it would around a main-sequence solar-radius star.

Quadratic limb-darkening coefficients in the TESS band were computed using LDTk (Parviainen & Aigrain 2015) based on Claret (2017) PHOENIX stellar model grids at Teff = 6332 K, log g = 3.71, [Fe/H] = 0.0. The resulting coefficients are u1 = 0.393 +/- 0.002 and u2 = 0.150 +/- 0.002. This measurement supersedes the previous approximate fallback formula that gave u1 ~ 0.406, u2 ~ 0.157.

Four major spectroscopic archives (APOGEE DR17, LAMOST DR10, GALAH DR3, RAVE DR6) for independent Teff and log g measurements of TIC 81077799. A programmatic 5-arcsec cone search via astroquery.sdss and astroquery.vizier returned zero matches across all four catalogs. The non-detection by LAMOST is expected given the star's southern declination (delta = -53.7 deg), but the absence from APOGEE, GALAH, and RAVE indicates that TIC 81077799 has never been observed by any major spectroscopic survey. The only available stellar parameters are therefore photometric: TIC v8 (Stassun et al. 2019) and Gaia GSP-Phot (Gaia Collaboration 2023). The TIC v8 values are adopted throughout this work. This lack of spectroscopic coverage means that the a/Rstar tension cannot be resolved with existing public data and would require new dedicated spectroscopy.

## 4. Ephemeris and Period Recovery

The official TOI ephemeris is P = 9.2224171 d and T0 = 2314.521155 BTJD.

Using only the 120 s SPOC products, BLS recovered the official period near 9.222 d in all tested 120 s modes, confirming the TOI ephemeris.

Table 2. Ephemeris and search diagnostics.

| Quantity | Value |
|---|---:|
| Official period | 9.2224171 +/- 0.0000098 d |
| Official T0 | 2314.521155 +/- 0.000615 BTJD |
| 120 s BLS period | 9.222136 d |
| Robust 120 s depth at official ephemeris | 2694 +/- 26 ppm |
| Official TOI depth | 3109.8 +/- 36.9 ppm |

The robust depth in Table 2 is a simple diagnostic using fixed in/out windows. The adopted physical parameters come from the transit model described below.

## 5. Transit Modeling

The corrected 120 s light curve was phase-folded on the official ephemeris and fitted with an analytic transit model using `batman`. The fitted parameters were Rp/Rstar, a/Rstar, impact parameter b, and a baseline term. The orbital period and reference epoch were fixed to the official TOI values. Eccentricity was fixed to e = 0 in the working model, not because circularity is proven, but because transit photometry alone does not robustly constrain eccentricity for this target. Limb darkening was fixed to the adopted TESS-band coefficients.

The corrected free-geometry fit is compared against the stellar-density expectation using Kepler's Third Law. For a circular orbit and the TIC mass and radius, the expected value is a/Rstar = 7.69 +/- 0.50. The fitted value is a/Rstar = 9.21 +/- 0.29, which is approximately 2.6 sigma higher. A density-locked comparison fit gives a similar large radius (Rp/Rstar ~ 0.0584) but a poorer description of the ingress/egress morphology, requiring a near-grazing impact parameter b ~ 0.86. The circular free-geometry fit is therefore used as the current photometric description, while treating the density tension as a key caveat.

An exploratory eccentric fit was also performed with free eccentricity e and argument of periastron omega, using an e*sin(omega)/e*cos(omega) parameterization and 50 walkers over 3000 production steps. The eccentric fit formally reduces the a/Rstar tension to approximately 0.5 sigma (fitted a/Rstar ~ 8.02), but does so at the expense of an extremely grazing impact parameter (b ~ 0.97), a transit duration of only ~2.9 h (inconsistent with the data), and poor MCMC convergence (autocorrelation times exceeding 100 production steps). These diagnostics confirm that transit photometry alone does not robustly constrain eccentricity for this target, and the circular model remains the preferred description of the data.

![Figure 2. Corrected 120 s transit model.](toi3492_transit_fit_120s_corrected.png)

Figure 2. Corrected 120 s phase-folded transit fit for TOI-3492.01. The model uses the official ephemeris, a circular orbit, fixed approximate TESS-band limb darkening, and the corrected 120 s reference light curve.

![Figure 3. MCMC posterior distributions.](toi3492_corner_120s_corrected.png)

Figure 3. Posterior distributions for Rp/Rstar, a/Rstar, impact parameter, and baseline in the corrected 120 s fit.

## 6. Results

The corrected model parameters and derived quantities are summarized in Table 3.

Table 3. Corrected 120 s transit and derived candidate parameters.

| Parameter | Value |
|---|---:|
| Period, P | 9.2224171 d fixed |
| Reference epoch, T0 | 2314.521155 BTJD fixed |
| Rp/Rstar | 0.05628 +/- 0.00046 |
| a/Rstar | 9.209 +/- 0.290 |
| Inclination | 85.09 +/- 0.25 deg |
| Impact parameter, b | 0.789 +/- 0.016 |
| Eccentricity | 0 fixed |
| Model transit depth | 3167 ppm |
| Transit duration, T14 | 5.40 h |
| Rp | 15.92 +/- 0.68 Rearth |
| Rp | 1.42 +/- 0.06 Rjup |
| Semimajor axis, a | 0.1110 AU |
| Stellar luminosity | 9.7 Lsun |
| Incident flux | 790 Searth |
| Equilibrium temperature | 1475 K |
| MCMC acceptance fraction | 0.594 |
| MCMC autocorrelation time | 40.2-43.8 steps |
| Production length / tau | 57.1-62.2 |

The result Rp = 15.92 +/- 0.68 Rearth places the object in the giant-planet-size regime if the signal is planetary and on target, consistent with the official TOI radius scale.

The MCMC run saved both the flat posterior samples and the raw production chain. The estimated integrated autocorrelation times are 40.2-43.8 production steps for the four fitted parameters, and the 2500-step production run spans at least 57 autocorrelation times for every fitted parameter. This satisfies the conservative 50-tau reporting heuristic used here.

## 7. Sector and Event Robustness

The corrected 120 s reference-light-curve build measured robust transit depths independently by sector. All six 120 s sectors show a deep transit at the official ephemeris, so the corrected large-radius result is not driven by a single sector.

Table 4. Sector-by-sector robust transit depths.

| Sector | Depth | Uncertainty |
|---:|---:|---:|
| 37 | 2490 ppm | 71 ppm |
| 63 | 2688 ppm | 61 ppm |
| 64 | 2788 ppm | 60 ppm |
| 90 | 2874 ppm | 60 ppm |
| 99 | 2770 ppm | 76 ppm |
| 100 | 2516 ppm | 59 ppm |

The weighted mean sector depth is about 2692 ppm, with sector-to-sector scatter larger than the formal uncertainties. These sector depths are robust fixed-window diagnostics rather than full limb-darkened model depths, so they are expected to differ somewhat from the fitted model depth. The sector-to-sector scatter is treated as evidence for residual systematics or sector-dependent effects, not as a reason to return to the old shallow interpretation.

## 8. False-Positive and Contamination Checks

The following checks are designed to identify obvious false-positive scenarios. They are reassuring, but they do not constitute full statistical validation.

### 8.1 Odd/Even Transit Depths

Odd and even transit events were measured separately using robust median in-transit and out-of-transit windows on the corrected 120 s reference light curve.

Table 5. Corrected odd/even transit-depth comparison.

| Quantity | Value |
|---|---:|
| Usable events | 16 |
| Odd depth | 2686 +/- 40 ppm |
| Even depth | 2673 +/- 35 ppm |
| Difference | 13 ppm |
| Significance | 0.24 sigma |

No significant odd/even depth difference is detected.

### 8.2 Secondary Eclipse

A search at orbital phase 0.5 gives no significant secondary eclipse.

Table 6. Corrected secondary-eclipse search.

| Quantity | Value |
|---|---:|
| Secondary depth | 9 +/- 15 ppm |
| Significance | 0.63 sigma |
| 3-sigma upper limit | 54 ppm |

![Figure 4. Corrected false-positive diagnostics.](toi3492_false_positive_120s.png)

Figure 4. Corrected 120 s odd/even transit-depth comparison and secondary-eclipse search. These checks do not reveal an obvious eclipsing-binary false positive.

### 8.3 SPOC Data Validation Products

The public SPOC DV products available locally from MAST were parsed: eight DVT FITS files and eight DVR PDF reports. The strongest multi-sector product, S1-S96 TCE 1, matches the official TOI ephemeris and reports P = 9.22240805 d, depth = 3128.3 ppm, Rp = 15.66 Rearth, and MES = 99.4. The corresponding DVR dashboard rounds this to depth = 3128 +/- 30 ppm, Rp = 15.7 +/- 0.7 Rearth, and SNR = 106. The dashboard centroid offset is 2.25 +/- 2.50 arcsec, or 0.90 sigma, and the multi-sector offset is 2.07 +/- 2.79 arcsec, or 0.74 sigma.

These public SPOC DV products independently support the corrected several-thousand-ppm depth and place the source near the target position. Single-sector DV products can prefer aliases or lower-SNR TCEs, so the multi-sector official-period products are the relevant comparison. This is strong archival vetting evidence, not RV confirmation.

Table 7. SPOC DV official-period consistency checks.

| Product | Relation | Period (d) | Depth (ppm) | MES |
|---|---|---:|---:|---:|
| S1-S65 | official P | 9.222417 | 3109.8 | 81.0 |
| S1-S96 | official P | 9.222408 | 3128.3 | 99.4 |
| S37 | official P | 9.222977 | 3043.0 | 42.6 |
| S64 | official P | 9.222730 | 3200.8 | 56.5 |
| S90 | official P | 9.223049 | 3179.8 | 58.7 |
| S100 | official P | 9.221581 | 3028.2 | 48.8 |
| S99 | 2P alias | 18.444263 | 3111.7 | 44.9 |

### 8.4 Gaia DR3 Neighbor Field

A Gaia DR3 query within 120 arcsec of the official TOI coordinates identifies the target as Gaia DR3 source 5347362071701193344, separated by 0.006 arcsec from the TOI coordinate. The target has RUWE = 0.985, below the common 1.4 caution threshold. The Gaia duplicated-source flag is true and is retained as a caution, while the RUWE value and non-single-star flag are reassuring.

For the corrected 3167 ppm transit depth, a fully eclipsed contaminating source would need to be within Delta G = 6.24 mag of the target. A 50 percent eclipsing-binary contaminant would need to be within Delta G = 5.49 mag. The nearest Gaia neighbor is at 7.37 arcsec and is too faint, Delta G = 10.65, to mimic the signal.

Table 8. Gaia-band contamination summary.

| Radius | Neighbors | Full-eclipse mimics | 50 percent EB mimics | Flux-ratio sum |
|---:|---:|---:|---:|---:|
| 21 arcsec | 14 | 0 | 0 | 0.00451 |
| 42 arcsec | 58 | 0 | 0 | 0.01247 |
| 60 arcsec | 120 | 1 | 0 | 0.02586 |
| 120 arcsec | 500 | 9 | 7 | 0.24038 |

No Gaia source inside 42 arcsec is bright enough to mimic the full signal as a fully eclipsed contaminant. One source at 56.29 arcsec could mimic the depth only if nearly fully eclipsed, and several wider-field sources out to 120 arcsec could mimic it in principle. Gaia therefore does not identify a close bright contaminant that obviously explains the signal, but it does not replace formal TESS-band source localization.

![Figure 5. Gaia DR3 neighbor field.](toi3492_gaia_neighbors.png)

Figure 5. Gaia DR3 neighbor field around TIC 81077799. Circles mark approximate 21, 42, and 60 arcsec radii. This is a Gaia-band crowding diagnostic, not a formal TESS centroid validation.

### 8.5 Dilution Robustness

The effect of aperture dilution was quantified using SPOC CROWDSAP, the ExoFOP TIC contamination ratio, and Gaia G-band neighbor flux sums. The mean SPOC CROWDSAP is 0.9765, which changes the observed 3167 ppm depth to 3244 ppm and the radius from 15.92 Rearth to 16.11 Rearth. The ExoFOP contamination ratio gives Rp = 16.07 Rearth, and the Gaia 42 arcsec summed-flux scenario gives Rp = 16.02 Rearth.

The correction is therefore about 1 percent in radius and does not affect the giant-planet-size interpretation. Even a conservative 10 percent contaminating-flux-to-target-flux ratio would give Rp = 16.70 Rearth. This does not replace high-resolution imaging or a TESS-band PRF aperture model.

![Figure 6. Dilution robustness.](toi3492_dilution_robustness.png)

Figure 6. Dilution robustness for TOI-3492.01. The nominal CROWDSAP/ExoFOP/Gaia-42 arcsec corrections are small compared with the giant-planet-size radius scale.

### 8.6 First-Pass TESS Difference Images

A first-pass source-localization check was performed using the six 120 s SPOC target-pixel files. For each sector, median in-transit pixel fluxes were subtracted from median out-of-transit pixel fluxes at the official ephemeris. The positive difference-image centroid was compared with the target coordinate projected into the TPF WCS.

Table 9. First-pass TESS difference-image centroid offsets.

| Sector | Offset |
|---:|---:|
| 37 | 14.2 arcsec |
| 63 | 9.4 arcsec |
| 64 | 0.9 arcsec |
| 90 | 7.7 arcsec |
| 99 | 15.1 arcsec |
| 100 | 22.2 arcsec |

The median offset is 11.8 arcsec, and the largest offset is 22.2 arcsec, about one TESS pixel. This is encouraging and does not point obviously to the wider Gaia neighbors. It is a first-pass diagnostic independent of the SPOC DV dashboard centroid check, not PRF-level validation.

![Figure 7. First-pass TESS difference images.](toi3492_tess_difference_images.png)

Figure 7. First-pass 120 s TESS difference images. Black plus signs mark the target coordinate in each TPF, and yellow crosses mark the positive difference-image centroid.

## 9. Stellar Variability and Transit Timing

The legacy stellar-variability analysis found weak sector-dependent periodicity with a weighted mean near 4.4 +/- 1.4 d. This should be interpreted only as tentative activity-related variability or residual systematics, not as a precise stellar rotation period.

![Figure 8. Stellar variability diagnostic.](toi3492_stellar_rotation.png)

Figure 8. Lomb-Scargle stellar-variability diagnostic. The reported period is tentative and should not be interpreted as a precise rotation period.

Individual transit timing was attempted on the corrected 120 s light curve, but the result is SNR-limited. No TTV detection is claimed.

![Figure 9. Corrected 120 s transit-timing diagnostic.](toi3492_ttv_plot.png)

Figure 9. Corrected 120 s transit-timing diagnostic. The result is retained only as a record of an SNR-limited timing attempt; no TTV detection is claimed.

## 10. Discussion

The 120~s-only analysis recovers a depth and radius consistent with the official TOI scale: the signal is several thousand ppm deep, and the inferred companion radius is about 16 Rearth if the signal is on target and planetary.

Limb-darkening coefficients were computed from Claret (2017) PHOENIX model grids using the LDTk package, giving u1 = 0.393 and u2 = 0.150 at the adopted stellar parameters. Re-running the MCMC with these properly interpolated coefficients changed the fitted parameters by less than 0.1 sigma in all cases (e.g., a/Rstar shifted from 9.23 to 9.22), confirming that the fixed approximate coefficients used previously were not responsible for the density tension.

The vetting checks are encouraging. The signal is recovered in all six 120 s sectors, public SPOC DV products recover the same deep official-period signal with a sub-sigma centroid offset, odd and even events have consistent depths, no secondary eclipse is detected at phase 0.5, Gaia DR3 does not reveal a close bright contaminant capable of explaining the signal, and first-pass TESS difference images place the signal within about one TESS pixel of the target. These results support continued follow-up and a plausible planet-candidate interpretation.

The most important caveat is the a/Rstar tension. The free photometric fit prefers a/Rstar = 9.21 +/- 0.29, while the TIC-density prediction is 7.69 +/- 0.50. This does not invalidate the signal, but it prevents a fully self-consistent validation claim. Two possible resolutions were explored. First, an eccentric-orbit fit with free eccentricity can formally reduce the tension to approximately 0.5 sigma (a/Rstar ~ 8.0, e ~ 0.26), but this solution drives the impact parameter to a near-grazing value (b ~ 0.97), produces a transit duration (~2.9 h) inconsistent with the data, and yields poorly converged MCMC chains. The eccentric fit is therefore not a viable resolution. Second, the density-locked fit forces a/Rstar = 7.69 but requires Rp/Rstar ~ 0.058 (depth ~ 3400 ppm) and b ~ 0.86, giving a poorer description of the ingress/egress shape. The circular free-geometry fit remains the most faithful photometric description of the data.

Possible explanations for the remaining tension include stellar-parameter uncertainty in TIC v8, residual TESS systematics, or limitations of the simplified photometric model. Because transit photometry alone cannot distinguish among these possibilities robustly for this target, the density tension should be stated clearly in any abstract, discussion, or conclusion.

The current work therefore supports a conservative interpretation: TOI-3492.01 is a plausible giant-planet-size transiting candidate around an evolved star. It is not confirmed, not validated, and should not be used for planet-population interpretation without additional follow-up.

## 11. Limitations and Future Work

Important limitations remain:

1. No radial-velocity mass measurement is available.
2. The SPOC DV centroid dashboard is reassuring, but independent PRF-level source-localization modeling has not been performed.
3. The Gaia contamination estimate uses Gaia G-band flux ratios, not a full TESS-band aperture-contamination model.
4. Limb-darkening coefficients were computed from Claret (2017) model grids and are accurate for the TESS band, but uncertainties in the stellar parameters propagate to small LD uncertainties.
5. Corrected per-transit timing is SNR-limited; no TTV detection is claimed.
6. The stellar variability result is tentative and should not be over-interpreted.
7. A TRICERATOPS screening run is strongly reassuring, but no RV mass or high-resolution imaging contrast curve is available. The a/Rstar tension remains ~2.6 sigma after both improved limb-darkening and an exploratory eccentric fit, and would complicate any final validation claim.

The highest-priority next steps are an independent 20 s cadence check when MAST access is available, independent PRF-level source localization or high-resolution imaging, and radial-velocity or other follow-up observations if confirmation is desired.

## 12. Conclusions

Public TESS photometry of TOI-3492.01 / TIC 81077799 was independently analyzed, yielding the following:

1. TIC 81077799 is an evolved, low-density subgiant-like star with Rstar = 2.5926 +/- 0.1094 Rsun.
2. A 120 s-only BLS analysis recovers the official TOI period of P = 9.2224171 d.
3. The corrected 120 s transit model gives Rp/Rstar = 0.05628 +/- 0.00046 and depth = 3167 ppm.
4. Combining the fitted radius ratio with the TIC stellar radius gives Rp = 15.92 +/- 0.68 Rearth.
5. All six 120 s sectors show a deep transit-like signal.
6. Corrected odd/even, secondary-eclipse, SPOC DV centroid, Gaia, and first-pass TESS difference-image checks do not reveal an obvious false-positive source.
7. The free-geometry fit has a/Rstar = 9.21 +/- 0.29, which is 2.6 sigma higher than the TIC-density prediction of 7.69 +/- 0.50. An exploratory eccentric fit and re-analysis with properly interpolated limb-darkening coefficients did not resolve this tension.
8. The object should be described as a plausible giant-planet-size transiting candidate with strong false-positive checks, not as a confirmed planet.

TOI-3492.01 is therefore a promising candidate for follow-up, but additional validation is required before its planetary nature can be established.

## Reproducibility

The exact rerun order is documented in `reproducibility_order.md`. The current numerical parameters are stored in the top-level `transit` block and under `transit_corrected_120s` in `config_corrected_120s.json`.

Table 10. Main scripts and roles.

| Script | Role |
|---|---|
| `stellar_params.py` | Query TIC v8 and estimate stellar parameters and limb darkening. |
| `alias_120s_analysis.py` | Verify the official period using 120 s SPOC products. |
| `build_120s_reference_lightcurve.py` | Build the corrected 120 s reference light curve. |
| `transit_model_120s_corrected.py` | Run the adopted corrected transit model and MCMC diagnostics. |
| `transit_model_120s_density_locked.py` | Run the density-locked comparison model. |
| `false_positive_tests_120s.py` | Run corrected odd/even and secondary-eclipse checks. |
| `gaia_contamination_check.py` | Run Gaia DR3 neighbor/RUWE contamination check. |
| `tess_source_localization_120s.py` | Run first-pass TESS difference-image source-localization check. |
| `spoc_dv_extract.py` | Parse SPOC DVT/DVR products and compare DV metrics with the corrected 120 s solution. |
| `verify_final.py` | Print a corrected-config sanity check. |

The obsolete scripts `download_and_clean.py`, `transit_modeling.py`, `false_positive_tests.py`, and `period_harmonic_check.py` are not part of the current workflow and should not be regenerated for current depth or radius claims.

## References

- Astropy Collaboration et al. 2013, A&A, 558, A33
- Astropy Collaboration et al. 2018, AJ, 156, 123
- Claret, A. 2017, A&A, 600, A30
- Foreman-Mackey, D., Hogg, D. W., Lang, D., & Goodman, J. 2013, PASP, 125, 306
- Hippke, M., & Heller, R. 2019, A&A, 623, A39
- Kovacs, G., Zucker, S., & Mazeh, T. 2002, A&A, 391, 369
- Kreidberg, L. 2015, PASP, 127, 1161
- Lightkurve Collaboration et al. 2018, Astrophysics Source Code Library, ascl:1812.013
- Ricker, G. R. et al. 2015, JATIS, 1, 014003
- Seager, S., & Mallen-Ornelas, G. 2003, ApJ, 585, 1038
- Stassun, K. G. et al. 2019, AJ, 158, 138
- Virtanen, P. et al. 2020, Nature Methods, 17, 261
