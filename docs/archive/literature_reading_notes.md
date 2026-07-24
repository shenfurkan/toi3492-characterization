# Historical Literature Reading Notes

> Archived on 2026-07-23. These are first-pass reading notes, not current project
> status or scientific authority. Active literature tracking is maintained in
> `../literature_matrix.md`.

Purpose: extract methodology from open-access papers before writing the TOI-3492.01 article. These notes should summarize methods and structure, not copy wording.

## Downloaded Core Papers

| File | Pages | Main Use |
|---|---:|---|
| `literature/Chontos2024_TESSKeck_Subgiants.pdf` | 22 | Evolved/subgiant host methodology and population framing |
| `literature/Wittenmyer2021_TOI1842b_EvolvingSubgiant.pdf` | 28 | Warm Saturn around evolving subgiant; comparison object |
| `literature/Thomas2025_TOI5108_TOI5786_SubSaturns.pdf` | 25 | Recent TESS sub-Saturn characterization style |
| `literature/LilloBox2024_AstraLux_TESS_Companions.pdf` | 10 | High-resolution imaging and contaminant treatment |
| `literature/Ross2023_DEATHSTAR_TESS_FalsePositives.pdf` | 17 | Nearby eclipsing-binary false-positive methodology |

## Extraction Template

For each paper, fill in:

- Claim level: discovery, confirmation, validation, or candidate analysis.
- Data: TESS sectors, ground photometry, spectroscopy, RVs, imaging.
- Stellar characterization: TIC, Gaia, spectroscopy, isochrones, asteroseismology.
- Photometry treatment: detrending, aperture choice, sector handling.
- Transit modeling: model code, priors, eccentricity treatment, limb darkening.
- False-positive vetting: odd/even, secondary, centroid, Gaia, imaging, RV, statistical validation.
- Figures: which figures are essential.
- Tables: which tables are essential.
- Language lessons: how they avoid or support strong claims.
- Direct implication for TOI-3492.01.

## Paper 1: Chontos et al. 2024, TESS-Keck Survey XXI

Status: downloaded, first-pass method scan complete.

Initial use:

- Compare the evolved-host discussion with a professional TESS subgiant-systems survey.
- Learn how they present homogeneous stellar and planet parameters.
- Learn how they discuss demographics of planets around evolved stars.

Notes to extract:

- Stellar classification criteria for subgiants.
- What minimum follow-up is used for confirmation.
- What tables are included for host and planet properties.
- How they treat RVs and outer companions.

First-pass method observations:

- The paper combines TESS photometry, spectroscopy, radial velocities, broadband photometry, and Gaia parallax.
- It explicitly uses false-positive screening before final modeling.
- It separates TESS photometry, HIRES radial velocities, HARPS-N radial velocities, spectroscopic stellar parameters, and broadband/Gaia constraints into distinct subsections.
- Implication for TOI-3492.01: the paper must clearly state that there is no RV confirmation and that the stellar characterization is TIC/Gaia-catalog-level unless improved.

## Paper 2: Wittenmyer et al. 2021, TOI-1842b

Status: downloaded, first-pass method scan complete.

Initial use:

- Closest conceptual analog: warm Saturn around an evolving subgiant.
- Useful for discussion of evolved-star irradiation and follow-up value.

Notes to extract:

- How TESS photometry and follow-up are combined.
- How they discuss re-inflation/evolved-host context.
- Figure/table structure for a single-object characterization paper.

First-pass method observations:

- The observations section explicitly separates TESS photometry, ground-based photometry, and spectroscopic observations.
- The paper states that follow-up observations were used to establish planetary nature.
- Radial velocities are tabulated and used as a central confirmation ingredient.
- Implication for TOI-3492.01: the same claim strength cannot be used because RV and ground-based follow-up are currently lacking.

## Paper 3: Thomas et al. 2025, TOI-5108 b and TOI-5786 b

Status: downloaded, first-pass method scan complete.

Initial use:

- Recent sub-Saturn characterization example.
- Useful for final parameter table style and sub-Saturn discussion.

Notes to extract:

- How they introduce sub-Saturns.
- Which derived parameters are included.
- How they combine TESS, ground photometry, and RVs.

First-pass method observations:

- The paper has a clear Observations section beginning with TESS photometry.
- It uses TESS plus ground-based time-series photometry, high-angular-resolution imaging, and radial velocities.
- The methods include instrumental/systematics treatment in transit fitting.
- Implication for TOI-3492.01: a table listing what follow-up exists and what is absent should be added.

## Paper 4: Lillo-Box et al. 2024, AstraLux-TESS

Status: downloaded, first-pass method scan complete.

Initial use:

- High-resolution imaging and nearby-source contamination methodology.
- Useful to justify why Gaia/high-res imaging limitations matter.

Notes to extract:

- How nearby companions bias planet radii.
- How contrast curves and Gaia companions are used.
- How to phrase the absence of high-resolution imaging.

First-pass method observations:

- The paper emphasizes that chance-aligned sources and blended companions can cause false positives or bias planet radii.
- It frames high-spatial-resolution imaging as a key step in statistical validation.
- It provides a methodology for detecting additional nearby companions and estimating their relevance.
- Implication for TOI-3492.01: Gaia and/or high-resolution imaging limitations must be explicit, especially because the transit is shallow and TESS pixels are large.

## Paper 5: Ross et al. 2023, DEATHSTAR

Status: downloaded, first-pass method scan complete.

Initial use:

- TESS false-positive source localization through archival images.
- Useful for the false-positive limitations section.

Notes to extract:

- How off-target eclipsing binaries are identified.
- How they distinguish confirmed on-target transits from false positives.
- What data products are needed for source localization.

First-pass method observations:

- The paper is directly about confirming on-target TESS transits and identifying false-positive sources.
- It emphasizes that TESS false positives often arise because the true source is offset from the target star.
- It uses archival ground-based time-series imaging to identify nearby eclipsing binaries.
- Updated implication for TOI-3492.01 (2026-07-14): odd/even and secondary
  tests remain insufficient for validation. Gaia neighbor inspection, SPOC DV
  centroids, first-pass TESS difference images, and source-specific aperture
  geometry have now been completed. They provide qualitative source evidence,
  but calibrated PRF localization, high-resolution imaging, and a contrast
  curve remain absent, so no target-localization or validation claim is made.
