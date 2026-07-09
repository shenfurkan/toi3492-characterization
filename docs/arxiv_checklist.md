# arXiv Readiness Checklist

Last updated: 2026-07-08 (post LDTk/Claret 2017 LD revision and eccentric fit test)

## Literature Novelty — VERIFIED 2026-07-08

- [x] NASA ADS: zero results for "TOI-3492" OR "TIC 81077799"
- [x] arXiv: zero results for "TOI-3492"
- [x] ExoFOP: target listed with TFOPWG PC (Planet Candidate) disposition; no prior publications; no spectroscopy; no confirmed planets
- [x] No prior publication claims this candidate — the current manuscript is novel

## Scientific Claim

- [x] The target is described as a planet candidate, not a confirmed planet.
- [x] The abstract uses conservative candidate language and does not claim formal validation.
- [x] The discussion states that RV and centroid validation remain needed.
- [x] a/Rstar tension (2.6 sigma) is stated in abstract, discussion, and conclusions.
- [x] Eccentric fit tested — reduces tension formally to 0.5 sigma but produces unphysical grazing transit (b~0.97, T14~2.9h) and poor MCMC convergence. Circular model confirmed as preferred.
- [x] Limb-darkening is now from Claret 2017 via LDTk (u1=0.393, u2=0.150), replacing the old fallback formula.
- [x] TTV analysis is described as legacy/SNR-limited with no detection claim.

## Manuscript Files

- [x] `arxiv_main.tex` — authoritative; peer-review clean; 17 pages; zero LaTeX errors
- [x] `arxiv_main.pdf` — compiled 2026-07-09, 17 pages, ~1.6 MB
- [x] `references.bib` — expanded with evolved-star and high-resolution-imaging context references (Perryman2018 and Ivezic2019 retained but uncited)
- [x] `professional_article.md` — claim-language synced with `arxiv_main.tex` (2026-07-09)
- [x] `reproducibility_order.md` — updated with current parameter values

## Figures Required For Upload (9 total)

- [x] `toi3492_120s_reference_fold.png`          — Figure 1: Corrected 120 s fold
- [x] `toi3492_transit_fit_120s_corrected.png`   — Figure 2: Transit model fit
- [x] `toi3492_corner_120s_corrected.png`        — Figure 3: MCMC posterior corner plot
- [x] `toi3492_false_positive_120s.png`          — Figure 4: Odd/even + secondary eclipse
- [x] `toi3492_gaia_neighbors.png`               — Figure 5: Gaia DR3 neighbor field
- [x] `toi3492_dilution_robustness.png`          — Figure 6: Dilution robustness
- [x] `toi3492_tess_difference_images.png`       — Figure 7: First-pass difference images
- [x] `toi3492_stellar_rotation.png`             — Figure 8: Stellar variability periodogram
- [x] `toi3492_ttv_plot.png`                     — Figure 9: Corrected TTV diagnostic

**Do NOT submit**: `toi3492_stitched_full.png` — legacy product; no longer referenced.

## Analysis Checks Completed

- [x] Gaia DR3 neighbor/RUWE/contamination check.
- [x] Sector-by-sector transit-depth consistency check.
- [x] Corrected odd/even and secondary-eclipse checks.
- [x] MCMC acceptance-fraction summary (0.595).
- [x] Formal MCMC autocorrelation summary (40.2-43.8 steps; > 50 tau).
- [x] First-pass TESS difference-image source-localization check.
- [x] Limb-darkening coefficients properly computed from Claret 2017 via LDTk.
- [x] Exploratory eccentric-orbit fit (free e, omega) — no viable solution found.
- [x] Literature novelty search — confirmed zero prior publications.
- [x] Simplified Morton-style FPP estimate added (~0.01%) but not treated as formal validation.
- [x] TRICERATOPS screening run completed (`N=100000`, search radius 4 TESS pixels): FPP numerically 0.0, scenario table dominated by PTP=0.999997 under run assumptions.
- [x] SPOC DV centroid/dashboard metrics extracted from local MAST DVT/DVR products.
- [ ] Independent PRF-level centroid validation or high-resolution imaging.
- [ ] TESS-band aperture-contamination model (requires TPF data — future work).

## Compilation — VERIFIED

- [x] MiKTeX v25.12 installed and working.
- [x] Compile command: `pdflatex -interaction=nonstopmode arxiv_main.tex`
- [x] Full cycle (pdflatex → bibtex → pdflatex → pdflatex) produces zero errors, zero warnings, zero undefined citations.
- [x] All BibTeX keys in `arxiv_main.tex` resolve to entries in `references.bib`.
- [x] All `\includegraphics` references match existing PNG files.

## Package Rules

- [x] Finalize and review `professional_article.md` — completed 2026-07-08.
- [ ] Include only LaTeX source, bibliography, and 8 figures in the arXiv package.
- [ ] Do not upload PDFs from class resources.
- [ ] Do not upload large chain files, CSV data, caches, or local logs.
- [ ] Compile locally before submission — verified clean.
- [x] Confirm all citations resolve — verified.

## Unfixable Limitations (Acknowledged in Manuscript)

- No radial-velocity mass measurement (star is bright, Tmag=8.45, RV follow-up feasible but not done).
- SPOC DV dashboard centroid is reassuring; no independent PRF-level centroid modeling.
- No TESS-band aperture-contamination model (Gaia G-band proxy only).
- Circular orbit assumed (eccentric fit does not produce a viable alternative).
- Candidate not confirmed by radial velocities; TRICERATOPS screening is strongly reassuring, but no high-resolution imaging contrast curve is available and the a/Rstar tension complicates any final validation claim.
- Corrected per-transit timing SNR-limited; not completed.
