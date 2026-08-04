# toi-3495.01

## State

- Lifecycle: `active`
- Workflow phase: `intake`
- Scientific disposition: `unknown`
- Publication: `none`

Intake started. The TOI identifier is registered, but the canonical TIC
identifier and ephemeris must be verified from a primary catalog and recorded
in `docs/` before data acquisition or scientific interpretation.

## First Pass

1. Verify the canonical TOI/TIC metadata from a primary catalog and record the
   source, retrieval date, and ephemeris in `docs/`.
2. Write a feasibility decision before a full data download.
3. Place source products in `data/raw/` and record their provenance.
4. Freeze target-specific decisions in `protocols/` before producing outputs.

Use `python -m exoplanet_pipeline status toi-3495.01` to inspect the workspace
layout.
