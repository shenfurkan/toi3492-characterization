# Target Selection Perspectives

A neutral rubric for comparing candidate targets before committing research
effort. Every value must be measured or verified for the specific target and
recorded in that target's workspace; this document defines only the
perspectives.

1. **Photometric robustness**: period stability, transit depth, sector
   coverage, baseline duration, cadence availability.
2. **Stellar characterization**: host brightness for follow-up feasibility,
   stellar parameters, distance, activity.
3. **Dynamical radial-velocity feasibility**: predicted planet mass and
   expected RV semi-amplitude; whether a ground-based mass measurement is
   viable.
4. **Atmospheric potential**: transmission spectroscopy metric and its
   community thresholds.
5. **False-positive and blend risks**: radius regime, background-source
   density, catalog contamination, centroid constraints.
6. **Strategic and publication value**: community competition, ExoFOP file
   count, available collaborations, novelty.

## Decision Contract

- Rankings and scores are records: they belong in
  `candidate/_campaigns/<campaign-id>/` or per-target workspaces, with the
  measurement date and source.
- A decision is never reused after the catalog state changes without a
  documented re-check date.
- The rubric itself contains no target values.
