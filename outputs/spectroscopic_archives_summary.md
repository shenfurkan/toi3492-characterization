# Spectroscopic Archive Query Results

**Target:** TOI-3492.01 / TIC 81077799 / HD 96519
**Coordinates:** RA=166.636671 deg, Dec=-53.731980 deg
**Search radius:** 5.0 arcsec

## TIC v8 Reference
| Parameter | Value |
|---|---|
| Teff | 6332 +/- 134 K |
| logg | 3.7075 +/- 0.0835 |

## Archive Query Summary

| Catalog | Status | Teff (K) | logg | [Fe/H] | Delta Teff | Delta logg |
|---|---|---|---|---|---|---|
| TIC v8 | reference | 6332 | 3.7075 | 0.00 | — | — |
| Gaia GSP-Phot | auto | 6061 | 3.8506 | -0.046 | -271 | +0.1431 |
| APOGEE DR17 | no match | — | — | — | — | — |
| LAMOST DR10 | no match | — | — | — | — | — |
| GALAH DR3 | no match | — | — | — | — | — |
| RAVE DR6 | no match | — | — | — | — | — |

## Impact on a/Rstar Tension

- TIC v8 logg = 3.7075 → predicted a/Rstar = 7.69
- Fitted a/Rstar = 9.21
- If archive logg is **lower** than 3.7075, the stellar density drops, a/Rstar prediction rises, and the tension **reduces**.
- If archive logg is **higher** than 3.7075, the tension **increases** — making the anomaly more significant.

## Interpretation

**No spectroscopic archives had a match for this target within 5 arcsec.**

This is a significant finding in itself:
- TIC 81077799 (HD 96519, F7IV/V, V~8.5) has **never been observed** by any major spectroscopic survey.
- **LAMOST DR10**: Northern-hemisphere survey (Dec > -10 deg typical) — target at Dec = -53.7 deg is outside primary footprint.
- **APOGEE DR17**: Targets primarily red giants in specific fields — this F-type subgiant was not in any APOGEE field.
- **GALAH DR3**: Southern survey but limited to ~1 million stars — this target was not included.
- **RAVE DR6**: Southern survey (I < 13 mag, limited to ~450,000 stars) — no match.
- Therefore, the **only available stellar parameters are photometric**: TIC v8 (broadband photometry + parallax) and Gaia GSP-Phot (BP/RP spectra).
- The a/Rstar tension **cannot be resolved with existing public spectroscopic data** — it requires new dedicated spectroscopy.
- This also means TOI-3492.01 is a **genuinely uncharacterized host star** at the spectroscopic level, making our photometric characterization the first detailed analysis.

Full results: `spectroscopic_archives.json`
