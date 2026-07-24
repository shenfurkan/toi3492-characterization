# Historical Methodology Notes

> Archived on 2026-07-23. This document describes a superseded analysis story in
> which the folded/binned reference fit, density comparison, eccentric branch,
> and asteroseismology had a more prominent role. It must not be used as current
> claim or release authority.

Last synchronized: 2026-07-14.

These notes map standard exoplanet methods to the current TOI-3492.01 analysis.
They are working summaries, not substitutes for the cited literature or the
canonical manuscript.

## Principal References

- Perryman, *The Exoplanet Handbook*, 2nd edition: transit detection, fitting,
  geometry, false-positive diagnostics, timing, activity, and stellar context.
- Kovacs et al. (2002): Box Least-Squares period search.
- Seager & Mallen-Ornelas (2003): transit geometry and density relations.
- Foreman-Mackey et al. (2013): ensemble MCMC.
- Parviainen & Aigrain (2015) and Husser et al. (2013): LDTk and PHOENIX
  specific intensities.
- Morton (2012, 2016) and Giacalone et al. (2021): population validation
  frameworks and their data requirements.
- Chontos et al., Grunblatt et al., Saunders et al., and Wittenmyer et al.:
  evolved-host giant-planet context.

## Transit Detection and Data Treatment

The adopted analysis uses the six 120-s SPOC PDCSAP products. Each sector is
normalized independently, strong positive outliers are removed, and no
transit-suppressing flattening is applied near the expected events. Products at
20-s cadence are used only as same-pixel consistency data and are not combined
with the adopted likelihood.

The BLS search is targeted at a known candidate. Recovering a maximum near the
official 9.2224171-d period demonstrates pipeline consistency but does not
independently establish the official period or epoch precision. Reported BLS
maxima are limited to their actual grid spacing.

## Adopted Transit Model

`scripts/transit_model_120s_corrected.py` fits five parameters:

- `Rp/Rstar`;
- `a/Rstar`;
- impact parameter `b`;
- multiplicative baseline `c`;
- log-uniform white-noise floor.

The period and epoch are fixed to official values, eccentricity is fixed to
zero as a descriptive working model, and quadratic limb darkening is fixed to
the adopted atmosphere-model prediction. No stellar-density prior is applied.
The 8-minute inference bins are exposure-integrated in the transit model.

The adopted chain uses 48 walkers, 1200 burn-in steps, and 6000 production
steps. After discarding 750 production steps, it contains 252,000 flat samples
and exceeds the conservative 50-autocorrelation-time reporting heuristic.

## Current Parameters and Physical Scale

| Quantity | Current value |
|---|---:|
| `Rp/Rstar` | 0.05472 +/- 0.00049 |
| `a/Rstar` | 10.60 +/- 0.45 |
| Impact parameter | 0.705 +/- 0.032 |
| Model depth at marginal medians | approximately 3094 ppm |
| Area ratio | 2994 ppm |
| Transit duration | 5.233 h |
| Candidate radius | 15.47 +/- 0.66 Rearth |
| Physical semimajor axis | 0.0927 AU |
| Incident flux | 1135 Searth |
| Equilibrium temperature | 1616 K |

Physical radius, semimajor axis, irradiation, and equilibrium temperature are
conditional on the TIC single-star parameters. The 3094-ppm model depth differs
from the area ratio because the transit chord samples a limb-darkened intensity
profile.

## Density and Eccentricity Interpretation

For relative-orbit semimajor axis `a` and companion-to-star mass ratio
`q=Mc/Mstar`, the exact circular relation is

```text
rho_star = 3*pi*(a/Rstar)^3 / (G*P^2*(1+q)).
```

The quoted transit densities use `q=0`. The adopted fit gives
`rho_star,phot = 0.188 (+0.025/-0.020) rho_sun`, compared with the catalog
mass-radius density `0.072 (+0.015/-0.013) rho_sun`. Their ratio of about 2.6 is
a model-conditional diagnostic, not a calibrated significance.

The exploratory eccentric branch is prior conditioned and does not meet the
reporting convergence rule. It illustrates how eccentricity can reconcile a
higher-density transit branch, but it is not an eccentricity measurement or a
model-selection result. Radial velocities and improved stellar parameters are
required.

## Fit-Window Sensitivity

The adopted selection is `|t-Tc| < 13 h`, or 26 h total. A separate full MCMC
using `|t-Tc| < 6.5 h`, or 13 h total, converges and gives
`Rp/Rstar=0.05567 (+0.00039/-0.00040)` and
`a/Rstar=10.17 (+0.32/-0.29)`. The `Rp/Rstar` shift is 1.95 adopted posterior
half-widths. Therefore, the adopted statistical intervals do not include
fit-window choice.

## Limb Darkening

The adopted TESS-band coefficients are `u1=0.393` and `u2=0.150`, predicted by
LDTk using the PHOENIX specific-intensity library at the adopted `Teff`,
`log g`, and an assumed `[Fe/H]=0.0 +/- 0.15`. TIC v8 has no metallicity value
for this target, so the metallicity range is an interpolation input, not a
measurement.

For the quadratic law, `I(mu)` is the emergent specific intensity and `mu` is
the cosine of the angle between the local surface normal and the line of sight.
An alternative atmosphere prescription has not been marginalized and remains a
follow-up control.

## False-Positive and Source Diagnostics

- Odd/even depths are 2724 +/- 38 and 2705 +/- 33 ppm, a 0.39-sigma difference.
- The local phase-0.5 secondary depth is 8 +/- 15 ppm, or 0.55 sigma.
- The all-phase regression is systematics limited; its strongest harmonic has
  the wrong sign for planetary light and supports no albedo or mass inference.
- No secondary-eclipse phase scan allowed by eccentric orbits was performed.
- Gaia finds no source inside 42 arcsec bright enough to mimic the full event,
  but wider sources remain possible.
- SPOC DV centroids, custom difference images, and aperture geometry are
  encouraging qualitative evidence, not calibrated PRF localization.
- PDCSAP already applies pipeline crowding treatment; CROWDSAP is not applied a
  second time.
- No high-resolution imaging contrast curve is available.

These checks reveal no obvious false-positive source but do not form a
population scenario model. No calibrated FPP is reported, and no statistical
validation claim is supported.

## Activity and Timing

`scripts/stellar_activity.py` and `scripts/ttv_analysis.py` are retained for
provenance only. Sector-dependent periodogram structure does not support an
adopted rotation period, and corrected event timing is signal-to-noise limited.
No rotation or TTV result appears in the canonical manuscript.

## Stellar and Asteroseismic Context

TIC v8 gives `Rstar=2.5926 R_sun`, `Mstar=1.25 M_sun`, and
`rho_star=0.0717 rho_sun`, consistent with an evolved subgiant-like host despite
the catalog `lumclass=DWARF` field. Gaia model values and an approximate
blackbody SED fit support the evolved radius scale but do not replace
independent spectroscopy and a coherent isochrone posterior.

The preliminary asteroseismic search found no replicated solution. Required
false-alarm and control-star gates remain incomplete, and injection/recovery
shows the null is not sensitive enough to select between the catalog-like and
circular-transit densities.

## Referee-Facing Status

| Area | Current evidence | Missing for a stronger claim |
|---|---|---|
| Transit characterization | Converged adopted circular reference fit and persistent six-sector signal | Marginalized window, timing, hierarchy, and correlated-noise model |
| Density diagnostic | Transit point estimate exceeds catalog-model density | Spectroscopy, isochrones, RVs, and converged alternative orbital models |
| Source localization | Gaia, SPOC DV, custom difference centroids, and aperture geometry | Calibrated PRF likelihood and contrast curve |
| False-positive probability | No calibrated FPP reported | Complete scenario population model and required imaging/localization inputs |
| Confirmation | No mass measurement | Target-specific radial velocities |
| Asteroseismology | Preliminary non-constraining null | Completed preregistered false-alarm and control gates plus greater sensitivity |

## Required Language

- Use: "unvalidated and unconfirmed giant-planet-sized transiting candidate."
- Use: "model-conditional density discrepancy that motivates follow-up."
- Use: "no calibrated population false-positive probability is reported."
- Avoid: "confirmed planet," "validated planet," "measured eccentricity,"
  "on-target planet," or a numerical FPP from historical screening scripts.
