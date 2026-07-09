# SPOC DV Extraction Summary

DVT FITS files: 8
DVR PDFs: 8
Machine-readable TCE rows: 11

## Key Result

The best multi-sector SPOC DV TCE matching the official TOI ephemeris is S1-S96 TCE 1: P=9.22240805 d, depth=3128.3 ppm, Rp=15.66 Rearth, MES=99.4.
The corresponding DVR dashboard reports rounded values depth=3128+/-30 ppm, Rp=15.7+/-0.7 Rearth, SNR=106.0.
The DVR dashboard reports a joint centroid offset distance of 2.25+/-2.50 arcsec (0.90 sigma).

## TCE Inventory

| Product | Kind | TCE | Relation | Period (d) | Depth (ppm) | Rp (Rearth) | MES |
|---|---|---:|---|---:|---:|---:|---:|
| S1-S65 | multi_sector | 1 | official_period | 9.222417 | 3109.8 | 15.65 | 81.0 |
| S1-S65 | multi_sector | 2 | other_tce | 1.628522 | 191.2 | 4.06 | 11.4 |
| S1-S96 | multi_sector | 1 | official_period | 9.222408 | 3128.3 | 15.66 | 99.4 |
| S1-S96 | multi_sector | 2 | other_tce | 1.628550 | 180.8 | 4.06 | 12.4 |
| S37 | single_sector | 1 | official_period | 9.222977 | 3043.0 | 15.39 | 42.6 |
| S63 | single_sector | 1 | other_tce | 8.686164 | 1093.5 | 9.59 | 24.7 |
| S64 | single_sector | 1 | official_period | 9.222730 | 3200.8 | 15.84 | 56.5 |
| S64 | single_sector | 2 | other_tce | 1.627722 | 211.7 | 4.70 | 7.5 |
| S90 | single_sector | 1 | official_period | 9.223049 | 3179.8 | 15.81 | 58.7 |
| S99 | single_sector | 1 | two_p_alias | 18.444263 | 3111.7 | 15.71 | 44.9 |
| S100 | single_sector | 1 | official_period | 9.221581 | 3028.2 | 15.56 | 48.8 |

## Interpretation

These SPOC DV products independently support the corrected several-thousand-ppm depth scale for the official-period TCEs. Single-sector DV products can prefer aliases or unrelated lower-SNR TCEs, so the multi-sector official-period products should be emphasized. This remains vetting evidence, not RV confirmation.
