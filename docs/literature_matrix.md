# Literature Matrix

This file tracks open-access papers used to learn methodology. The purpose is to extract structure and procedure, not copy text.

Project-state note (2026-07-14): this is a literature tracker, not a source of
canonical TOI-3492.01 values. Current results and claim gates are in
`../toi3492_characterization.tex`, `../REVIEW_NOTES.md`, and
`../outputs/release_status.json`.

## Reading Questions For Every Paper

- What data did they use?
- How did they clean/detrend photometry?
- How did they characterize the star?
- What transit model did they use?
- Did they fit eccentricity or fix circularity?
- What false-positive checks did they perform?
- Did they use Gaia, high-resolution imaging, centroiding, RVs, or statistical validation?
- What figures and tables did they include?
- How did they phrase limitations?

## Core Papers

| Priority | Paper | arXiv | Why It Matters | Status |
|---|---|---:|---|---|
| 1 | Chontos et al., TESS-Keck Survey XXI: subgiant systems | 2402.07893 | Best evolved-host comparison; TESS + RV + homogeneous stellar/planet analysis | downloaded |
| 2 | Wittenmyer et al., TOI-1842b | 2112.00198 | Warm Saturn around evolving subgiant; closest conceptual analog | downloaded |
| 3 | Baliwal et al., TOI-6651b | 2408.17179 | Dense sub-Saturn around subgiant; shows TESS + RV characterization | selected |
| 4 | Thomas et al., TOI-5108 b and TOI-5786 b | 2501.03803 | Recent sub-Saturn characterization with TESS and follow-up | downloaded |
| 5 | Lillo-Box et al., AstraLux-TESS | 2404.06316 | High-resolution imaging and contamination methodology | downloaded |
| 6 | Ross et al., DEATHSTAR | 2312.08373 | Nearby eclipsing-binary false-positive search for TESS candidates | downloaded |
| 7 | Kunimoto et al., LEO-Vetter | 2509.10619 | Flux-level and pixel-level TESS vetting framework | selected |
| 8 | Gomez Barrientos et al., TRICERATOPS+ | 2508.02782 | Statistical validation / false-positive probability methodology | selected |
| 9 | Fairnington et al., warm sub-Saturn eccentricities | 2505.04106 | Supports caution about eccentricity and photoeccentric interpretation | selected |
| 10 | Im et al., Kepler-1624b TTV non-detection | 2511.17709 | Model for cautious weak/no TTV language | selected |

## Method Extraction Notes

### Chontos et al. 2024: TESS-Keck Survey XXI

To extract:

- How they define subgiant host sample.
- Stellar parameter methodology.
- Joint photometry/RV model structure.
- Tables used for stellar and planet parameters.
- How they discuss planets around evolved stars.

### Wittenmyer et al. 2021: TOI-1842b

To extract:

- Warm Saturn around evolved star framing.
- How TESS detection is combined with ground-based confirmation.
- How they discuss atmospheric/follow-up value.
- Figure/table structure.

### Lillo-Box et al. 2024: AstraLux-TESS

To extract:

- Why nearby companions matter for TESS.
- How contrast limits and Gaia companions are discussed.
- How to phrase lack of high-resolution imaging as a limitation.

### Ross et al. 2023: DEATHSTAR

To extract:

- How archival images are used to find nearby eclipsing binaries.
- What types of TESS false positives are emphasized.
- How to phrase on-target versus off-target transit evidence.

## Implementation Status For The Paper

| Literature-driven need | Current implementation | Remaining limitation |
|---|---|---|
| Gaia neighbor census | Complete through 120 arcsec with mimic-capable source counts | Gaia-band census is not a TESS PRF likelihood |
| Centroid and source-localization statement | SPOC DV centroids, first-pass difference images, and source-specific aperture geometry are reported | No calibrated PRF localization or high-resolution contrast curve |
| Sector consistency | Six-sector depths and heterogeneity statistics are reported | No hierarchical sector-depth excess-scatter model |
| MCMC diagnostics | Adopted chain exceeds 50 autocorrelation times and raw/flat chains are bound by tests | Native-cadence robustness chains remain unconverged and nonadopted |
| RV limitation | No mass or confirmation claim is made; dedicated RV follow-up is requested | No target-specific RV time series or orbital solution |
| Eccentricity context | Photoeccentric relation and a prior-conditioned sensitivity branch are documented | No measured eccentricity or model selection |
| Statistical validation | Direct vetting measurements are reported conservatively | No calibrated population FPP is reported |

Future reading should be prioritized only when it changes a method, caveat, or
claim gate. It should not be used to promote this photometry-only candidate to a
validated or confirmed object.
