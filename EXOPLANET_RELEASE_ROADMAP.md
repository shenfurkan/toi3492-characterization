# Exoplanet Candidate Analysis and Release Roadmap

Version: 2.0

Last updated: 2026-07-23

## 1. Purpose and Authority

This document defines reusable analysis classes, dependency order, evidence
requirements, stop rules, and release practice for exoplanet-candidate studies.
It is a methodology template, not a source of target-specific scientific facts.

> This roadmap is never authoritative for a target-specific number, threshold,
> model branch, seed, cadence, sector, event, or scientific result.

For each target, authority must follow this order:

1. Immutable raw inputs and independently obtained follow-up data.
2. A target-specific protocol frozen before the corresponding real-data result.
3. Verified gate artifacts produced from that protocol.
4. The target-specific claim charter and dated decision log.
5. The canonical manuscript and machine-readable release status.
6. Project documentation and this reusable roadmap.

When records disagree, the higher item wins. A polished manuscript, archive,
test report, DOI, peer review, catalog entry, or TOI designation cannot override
a failed scientific gate.

## 2. Core Principle

The objective is not to obtain `PASS`, a planet interpretation, or a preferred
parameter value. The objective is to close every intended claim with one of the
following outcomes:

- supported by a valid artifact chain;
- supported conditionally with propagated uncertainty;
- not claimed;
- removed because the evidence is insufficient;
- blocked by external observations;
- failed with an explicit limitation.

A complete analysis may conclude that a persistent signal remains an
unvalidated candidate. That is a valid scientific result.

## 3. Mandatory Vocabulary

| Term | Required meaning |
|---|---|
| Signal | A measured feature in the data; no source or physical nature implied |
| Transit-like | Morphologically consistent with a transit but not necessarily planetary or on-target |
| Candidate | A signal that has not passed validation or confirmation requirements |
| On-target | Source localization supports the catalog target at the stated calibrated confidence |
| Validated | A complete, applicable validation framework passes a frozen threshold |
| Confirmed | Independent dynamical or equivalent evidence establishes the companion nature required by the claim |
| Adopted | Passed all gates required for its final scientific use |
| Diagnostic | Useful for scale or sensitivity but not a final result |
| Nonadopted | A valid calculation intentionally excluded from final inference |
| Invalid | A calculation that failed numerical, provenance, or implementation validity |
| Conditional | True only under explicitly named host, stellar, orbital, or dilution assumptions |
| Upper limit | A sensitivity-calibrated bound, not merely a nondetection |
| Nondetection | No accepted detection; does not imply a strong upper limit |

Forbidden shortcuts:

- `validated` cannot mean “passed several vetting checks.”
- `confirmed` cannot mean “visible in multiple sectors.”
- `on-target` cannot mean “nearest catalog source.”
- a low false-positive probability cannot by itself establish mass.
- a posterior median cannot be called measured when the chain fails convergence.
- a ratio cannot be described as a sigma significance.

## 4. Readiness Gates

Every target should publish a machine-readable state for these separate gates:

| Gate | Minimum meaning |
|---|---|
| Archive-ready | Inputs, provenance, licenses, and offline verification are internally complete |
| Candidate-paper-ready | Signal and limitations support a coherent candidate-level paper |
| Central-claim-ready | The paper's main physical inference passes all dependent model gates |
| Validation-ready | Population and source-localization validation inputs are complete |
| Confirmation-ready | Required independent dynamical or equivalent evidence is complete |

Passing a stronger gate normally implies the weaker scientific gates required by
that claim, but not necessarily archive publication. Packaging and scientific
evidence are distinct dimensions.

## 5. Standard Status Codes

Use explicit status values rather than ambiguous words such as “done” or
“stable.”

| Status | Meaning |
|---|---|
| `NOT_STARTED` | No frozen protocol or result |
| `PROTOCOL_ONLY` | Method frozen; no real-data result |
| `RUNNING` | Frozen protocol is being executed |
| `PASS` | All binding checks passed |
| `CONDITIONAL_PASS_WITH_PROPAGATION` | A quantified issue is carried downstream exactly once |
| `FAIL` | Gate failed; dependent claims remain closed |
| `FAIL_CLAIM_REMOVED` | Gate failed and the dependent claim was removed |
| `NOT_CLAIMED` | Strong result is outside the declared scope |
| `REMOVED` | Analysis or manuscript section is excluded from the canonical work |
| `BLOCKED_EXTERNAL` | Required observation is unavailable |
| `DIAGNOSTIC_ONLY` | Calculation is retained only for context or sensitivity |
| `NOT_ADOPTED` | Valid calculation is not part of final inference |
| `INVALID` | Numerical, code, data, or provenance validity failed |
| `QUARANTINED` | Preserved but prohibited from active use |
| `SUPERSEDED` | Replaced by a later, explicitly linked artifact |

`PENDING`, `READY_PARALLEL`, and `PARTIAL_READY` may be planning states, but they
are not acceptable final closure states.

## 6. Required Contract for Every Work Package

Every scientific work package must state:

1. Purpose.
2. Applicability and any justified `N/A` decision.
3. Upstream dependencies.
4. Inputs with paths, identifiers, versions, units, and hashes.
5. Decisions and numerical thresholds frozen before real-data execution.
6. Model family, priors, bounds, transforms, seeds, and software environment.
7. Required outputs and schema.
8. Gate checks.
9. Independent verifier or recomputation path.
10. Failure closure and stop rule.
11. Claims opened and claims that remain closed.

Qualitative words such as “acceptable,” “consistent,” “well converged,” or
“nominal coverage” must be converted to target-specific numerical rules before
the relevant real-data result is examined.

## 7. Claim Charter Before Analysis

Before expensive analysis, write a claim charter covering at least:

- existence and persistence of the signal;
- ephemeris;
- source location;
- transit geometry;
- companion radius;
- stellar properties;
- density comparison;
- eccentricity;
- false-positive probability;
- validation;
- mass and confirmation;
- atmosphere or population context;
- asteroseismology or other optional stellar diagnostics.

Each claim must be labeled `required`, `optional`, `not_claimed`, `removed`, or
`blocked_external`. Record the evidence class, dependent gates, permitted
wording, and forbidden wording.

Gate:

- every abstract, title, table, figure, and conclusion claim maps to the charter;
- no strong claim is allowed to depend on an undefined future analysis;
- the default decision under ambiguity is the weaker claim.

## 8. Raw Data and Identity Freeze

Freeze target identity before modeling:

- catalog identifiers and coordinates;
- proper motion and epoch;
- official candidate metadata and retrieval date;
- mission processing version;
- light-curve and pixel products;
- cadence and exposure duration;
- time standard and reference epoch;
- aperture, camera, detector, and sector metadata;
- source archive identifiers, file sizes, and hashes.

Preserve native columns including time, flux, errors, quality flags, background,
centroids, pointing corrections, crowding, throughput, and cadence number.

Gate:

- every expected input is present or explicitly missing;
- time conversion agrees with product headers within a frozen tolerance;
- each raw input can be retrieved independently or is archived lawfully;
- no undocumented, hand-edited input enters the likelihood.

## 9. Cadence and Event Ledgers

Create a row-level cadence ledger and an event ledger before using event depth or
shape to select data.

The cadence ledger should include:

- native and converted time;
- flux/error product lineage;
- quality and telemetry values;
- inclusion masks;
- one or more reason codes for exclusion;
- event, sector, camera, and detector identifiers.

The event ledger should include every expected event, including:

- fully covered events;
- partial events;
- events in data gaps;
- quality-rejected events;
- ingress and egress coverage;
- usable baseline on both sides;
- relevant spacecraft operations.

Gate:

- classification is blind to the measured event depth;
- every excluded cadence and event has a reason;
- all downstream artifacts use the same physical event identifiers;
- faster and slower products of the same pixels are not counted as independent
  events.

## 10. Instrumental Reliability

An astrophysical false-positive calculation is conditional on the signal being
astrophysical. Instrumental reliability must be tested separately.

Required checks where applicable:

- quality-bit transitions;
- momentum dumps and pointing interruptions;
- thermal recovery and scattered light;
- Earth/Moon crossings and background excursions;
- cosmic rays and discontinuities;
- centroid and pointing motion;
- SAP, corrected pipeline flux, and custom aperture products;
- cotrending and systematics basis vectors;
- nearby control stars and detector-column duplicates;
- event-by-event difference images and pixel light curves;
- spacecraft-orbit and operational aliases;
- leave-one-event and leave-one-sector recovery.

Gate:

- at least two justified reductions recover the signal when available;
- no documented operation alone explains the accepted events;
- pixel behavior remains consistent with at least one allowed source;
- detection reliability is calibrated independently of population FPP.

## 11. Build a Native-Cadence Model Early

A folded or binned fit is useful for visualization and scale checks, but it must
not become the main physical result before a native-cadence model exists.

The early reference model should use:

- native timestamps;
- exposure integration;
- event or sector baseline terms;
- sector-specific noise scales where justified;
- a declared treatment of timing offsets;
- explicit limb-darkening assumptions;
- multiple numerical starts;
- full posterior samples when used for uncertainty.

Folded/binned results must be labeled `DIAGNOSTIC_ONLY` until their relation to
the adopted native-cadence posterior is demonstrated.

Gate:

- the model recovers injected transits without unacceptable bias;
- parameter covariance is finite and identifiable;
- convergence and residual checks pass their frozen rules;
- no physical claim depends only on a visually clean folded curve.

## 12. Reduction-Family Comparison

Compare a bounded family of scientifically justified reductions, for example
pipeline-corrected, less-corrected plus cotrending, and pixel-level extractions.

Freeze before comparison:

- aperture definitions;
- crowding and throughput treatment;
- normalization intervals;
- cotrending basis selection;
- injection design;
- predictive score and acceptance rules;
- geometry-shift tolerance;
- uncertainty-propagation rule.

Rules:

- do not apply a crowding correction twice;
- do not multiply reductions from the same pixels as independent likelihoods;
- do not choose a reduction because it gives the preferred radius or density;
- carry accepted reduction uncertainty at draw level or once as a quantified
  systematic;
- never add the same reduction systematic twice.

Gate outcomes:

- `PASS` if required reductions pass and their differences are below the frozen
  tolerance;
- `CONDITIONAL_PASS_WITH_PROPAGATION` if required reductions pass but quantified
  differences must be carried;
- `FAIL` if required reductions, injection recovery, or propagation rules fail.

## 13. Window and Baseline Uncertainty

Transit geometry can change with the amount of surrounding data and baseline
flexibility. Test this before adopting precise geometry.

Freeze:

- total window grid;
- baseline family and priors;
- common validation cadences;
- held-out block definition;
- predictive metric;
- single-model superiority rule;
- unresolved-model averaging rule;
- geometry-coverage or influence gate.

Rules:

- compare models on the same held-out support;
- retain unresolved plausible models rather than forcing a winner;
- represent masks, windows, and baselines as correlated specification branches,
  not independent observations;
- if model spread is already present in mixture draws, do not add scalar padding
  for it again;
- keep a failed original gate immutable when a later handoff permits conditional
  continuation.

Gate:

- a single model may be adopted only if it passes the frozen superiority rule;
- otherwise, all retained models must be explicitly marginalized;
- final intervals must cover the preregistered model-sensitivity requirement.

## 14. Correlated-Noise Screening

Compare white noise with a small, physically motivated correlated-noise family.
A large post-hoc kernel zoo is prohibited.

Freeze:

- candidate kernels;
- parameterization, transforms, bounds, and priors;
- sector pooling structure;
- training and held-out units;
- mask/window branch universe;
- predictive improvement threshold;
- hyperparameter boundary rule;
- identifiability rule;
- mask/reduction interaction rule;
- computational fallback.

Predictive improvement alone is not enough. An eligible noise model should:

- improve held-out prediction by the frozen criterion;
- avoid pathological bound concentration;
- remain identifiable;
- behave consistently across justified masks and reductions;
- preserve injected transit shape;
- pass the final joint transit/noise diagnostics.

If no complex model is eligible, do not automatically declare white noise
adequate. The white model must pass its own residual and geometry gates.

## 15. Numerical Validity

Software completion and optimizer success flags are not scientific validity.

For every branch and start, record:

- initial and final parameters;
- actual parameter movement;
- initial and final objective;
- optimizer status and message;
- bound distances;
- gradient or KKT diagnostics where applicable;
- Hessian rank and conditioning where used;
- cross-start objective and parameter spread;
- independent solver or sampler comparison.

Gate:

- every required start must move unless a stationary initial point is
  independently certified;
- objective improvement must be finite and meaningful;
- all required starts must agree within frozen tolerances;
- a library `success` bit cannot be the sole stationarity gate;
- covariance or Laplace draws require valid local geometry;
- failed numerical results are marked `INVALID`, not reinterpreted as science.

## 16. Preregistration and Amendments

Every real-data analysis should have a machine-readable, hash-bound protocol
frozen before its result is examined.

The protocol must contain:

- known previous results and disclosures;
- upstream file and code hashes;
- exact model and branch universe;
- priors, bounds, transforms, and seeds;
- thresholds and their calibration source;
- optimizer/sampler settings;
- required artifacts;
- no-clobber behavior;
- one bounded fallback where justified;
- downstream opening and stop rules.

Amendment rules:

1. Never edit an old protocol in place after seeing its result.
2. Preserve old protocols and all failed artifacts.
3. State which result was already known.
4. Explain whether the change fixes a code defect, numerical method, or scientific
   model family.
5. Freeze the amendment before new real-data execution.
6. A numerical repair cannot silently become a new scientific model search.
7. After the registered fallback fails, weaken or remove the claim unless a
   dated scope amendment explicitly opens a new method-development phase.

An amendment cannot retroactively turn a failed gate into a pass.

## 17. Residual Diagnostics

Residual checks must target time scales relevant to transit ingress, egress,
duration, baseline, and stellar variability.

Freeze:

- residual definition;
- in-transit and out-of-transit support;
- ACF lag grid and confidence rule;
- time-averaging/bin grid;
- beta definition and white-noise expectation;
- sector/event weighting;
- gap handling;
- periodogram range and multiple-testing rule;
- whether each diagnostic is a gate or context only.

Gate:

- all required diagnostics exist for every retained model branch;
- beta, ACF, and periodogram roles match the frozen protocol;
- residual correlation above the threshold blocks precise adopted geometry;
- a diagnostic cannot be promoted to a gate or demoted from a gate after seeing
  whether it passes;
- residual failure triggers a model revision or claim reduction, not threshold
  relaxation.

## 18. Activity and Event Timing

Separate stellar activity and timing variation from geometry before final
inference.

Activity checks may include:

- rotation-period searches with window and alias controls;
- flare detection and masking;
- spot-crossing searches;
- depth correlation with local variability;
- activity indicators from spectroscopy where available.

Timing checks should include:

- event-level midpoint posteriors;
- linear ephemeris refit;
- cycle-count audit;
- timing-residual covariance;
- alternative ephemerides;
- future-window propagation in the correct time standard.

Gate:

- claimed periodicity must replicate across appropriate observing blocks;
- timing offsets enter the final geometry if they can smear the folded shape;
- no TTV or rotation claim is made from a single alias-prone peak;
- follow-up windows include cycle-count ambiguity and covariance.

## 19. Sector and Event Hierarchy

Formal inconsistency between sectors does not identify an astrophysical cause.
Use a hierarchy to separate measurement noise, event variation, sector
variation, reduction effects, and shared geometry.

Freeze:

- shared and varying parameters;
- excess-scatter distribution;
- outlier model;
- sector/event covariance;
- reduction-family handoff;
- simulation-based calibration and posterior-predictive checks;
- influence thresholds.

Gate:

- the hierarchy passes calibration and predictive checks;
- no sector or event is removed because its result is inconvenient;
- formal, bootstrap, and model-based uncertainties are labeled separately;
- cause is not called astrophysical until instrumental and model alternatives
  are adequately excluded;
- sector/reduction uncertainty reaches the final posterior exactly once.

## 20. Stellar Posterior and Limb Darkening

Build a coherent stellar posterior before highlighting transit-density or
photoeccentric effects.

Inputs may include:

- spectroscopy;
- parallax with stated zero-point treatment;
- passband-integrated photometry;
- extinction and distance priors;
- atmosphere grids;
- evolutionary/isochrone grids;
- multiplicity and unresolved-companion branches.

Requirements:

- use passband integrations rather than monochromatic blackbody shortcuts for
  final stellar inference;
- preserve mass-radius-age-metallicity covariance;
- compare justified atmosphere/evolution grids;
- marginalize unknown metallicity rather than silently fixing it;
- propagate stellar draws into limb-darkening coefficients;
- do not use transit density as a stellar prior and later treat the two as
  independent evidence.

A blackbody SED can be a radius-scale diagnostic but is not a final isochrone
mass, age, or covariance solution.

Gate:

- input photometry and passbands are traceable;
- model-grid sensitivity is quantified;
- posterior predictive SED checks pass;
- limb-darkening uncertainty is propagated into transit inference;
- final physical quantities use joint stellar draws.

## 21. Source Localization, Dilution, and Host Branches

TESS pixels can contain multiple sources. A Gaia neighbor census is necessary
but not sufficient for on-target localization.

Required work where applicable:

- current catalog census with proper-motion propagation;
- event-level and sector-level difference imaging;
- calibrated PRF or equivalent source likelihood;
- aperture and pixel-light-curve tests;
- archival imaging;
- high-resolution contrast curves;
- ground-based transit-time imaging;
- alternate-host and unresolved-companion branches.

Rules:

- off-aperture coordinates do not automatically exclude PRF-wing contamination;
- nondetection requires a documented sensitivity curve;
- every mimic-capable source must be included or explicitly excluded;
- while multiple hosts remain allowed, report host-conditional radii rather than
  one unconditional companion radius;
- distinguish pipeline crowding treatment from residual dilution uncertainty.

Gate:

- source likelihood is calibrated with injection/recovery;
- contrast limits cover the separation and magnitude range relevant to FPP;
- `on-target` wording is prohibited until its gate passes.

## 22. End-to-End Injection, Coverage, and Convergence

Inject signals through the same aperture, detrending, masking, search, fitting,
and selection path used for real data.

Freeze:

- injection parameter distribution;
- null simulations;
- event and sector sampling;
- number of trials and random seeds;
- recovery definition;
- bias and coverage tolerances;
- multiple-testing correction;
- sampler convergence thresholds.

Adopted posterior requirements should include, as applicable:

- multiple independent chains;
- rank-normalized convergence statistics;
- effective sample size;
- Monte Carlo standard error;
- chain-length-to-autocorrelation ratio;
- trace and energy diagnostics;
- mode and boundary review.

Gate:

- injected depth, duration, timing, and geometry are recovered without forbidden
  bias;
- credible intervals achieve calibrated coverage;
- all final chains pass convergence rules;
- failed-chain intervals never enter final tables;
- a nondetection is constraining only if injection/recovery shows adequate
  sensitivity.

## 23. Posterior Predictive and Influence Analysis

Test whether the adopted model can reproduce important features of the data and
whether a small subset drives the result.

Include where applicable:

- replicated transit shapes and residual structure;
- per-sector and per-event depth distributions;
- leave-one-event-out results;
- leave-one-sector-out results;
- leave-one-reduction-family-out results;
- prior and bound sensitivity;
- model-branch influence;
- grazing, multimodal, and alternate-host modes.

Gate:

- no single event, sector, reduction, or branch controls the central claim beyond
  the frozen tolerance;
- posterior predictive failures are explained, modeled, or propagated;
- multimodal solutions remain visible rather than being summarized by one
  misleading median.

## 24. Photometric False-Positive Controls

Photometric vetting should cover relevant alternatives without pretending that
each nondetection is a validation probability.

Possible controls:

- odd/even depth and timing differences;
- secondary-eclipse search over all relevant orbital phases;
- phase-curve harmonics;
- model-shift uniqueness;
- transit-shape and V-shape diagnostics;
- nearby-source and alternative-aperture events;
- detector and period duplicates;
- background eclipsing binary scenarios;
- hierarchical or grazing stellar binaries.

Freeze search ranges, templates, significance metrics, trial factors, and
upper-limit calibration before inspecting the strongest feature.

Gate:

- every claimed upper limit is supported by injection/recovery;
- multiple-testing effects are included;
- unphysical high-significance harmonics are treated as residual systematics,
  not planetary phase curves;
- incomplete sensitivity is reported as `inconclusive`, not `clean`.

## 25. FPP, Validation, and Confirmation

Population FPP is distinct from instrumental reliability, source localization,
and dynamical confirmation.

Before reporting FPP, freeze and verify:

- target identity and stellar posterior;
- sky-source hypothesis set;
- contrast curve and catalog completeness;
- transit and secondary constraints;
- population priors and survey selection assumptions;
- instrumental false-alarm treatment;
- Monte Carlo convergence and zero-count handling;
- sensitivity to priors and validation threshold.

The scenario set should include all relevant cases, such as:

- background or foreground eclipsing binary;
- hierarchical eclipsing binary;
- target eclipsing binary or grazing stellar binary;
- background transiting planet;
- planet transiting an unresolved companion;
- brown dwarf or low-mass star with planet-like radius;
- relevant instrumental false alarms.

Rules:

- justify omitted scenarios;
- do not interpret zero Monte Carlo samples as zero probability;
- do not apply a multiplicity boost outside its validated assumptions;
- for large-radius companions, validation of transit origin does not establish
  planetary mass;
- do not report a calibrated FPP when source/contrast inputs are incomplete.

Confirmation requires evidence appropriate to the claim. RV confirmation should
address host attribution, blends and line profiles, activity, aliases, instrument
offsets, jitter, trends, and a mass criterion. TTV confirmation requires
dynamical identifiability, alternate solutions, and stability.

## 26. Derived Quantities and Physical Interpretation

Calculate final quantities draw by draw from adopted joint posterior samples.

Requirements:

- propagate covariance rather than combining marginal errors independently;
- distinguish area ratio from limb-darkened model depth;
- propagate stellar, dilution, host, timing, reduction, baseline, and noise
  uncertainty;
- state orbital assumptions for density, irradiation, and equilibrium
  temperature;
- separate catalog-conditional values from direct measurements;
- independently recompute table values and units;
- do not describe a density ratio as a sigma significance;
- do not infer eccentricity from a density mismatch without a coherent stellar
  posterior and an adopted transit model.

Gate:

- every final number points to one adopted artifact and transformation;
- an independent verifier reproduces it within a frozen tolerance;
- no informative prior is hidden from the manuscript;
- all conditionals appear in tables, captions, abstract, and conclusions.

## 27. Follow-Up Triage

Convert each unresolved claim into a specific observation and decision.

| Question | Preferred observation | Decision enabled |
|---|---|---|
| Which sky source dims? | Time-series imaging during transit | Source attribution |
| Is there an unresolved companion? | Speckle or AO imaging | Dilution and host scenarios |
| Is the object stellar? | Reconnaissance spectroscopy | Binary rejection and stellar parameters |
| Is the ephemeris expiring? | Transit recovery | Future scheduling |
| What is the mass or eccentricity? | Precision radial velocity | Dynamical inference |
| Is a chromatic blend possible? | Multiband transit photometry | Blend discrimination |
| Are timing variations informative? | Continued high-cadence transits | Dynamical leverage |

Every observing request should state:

- predicted window and time system;
- required precision and cadence;
- instrument class;
- target and field coverage;
- decision enabled by detection;
- interpretation of nondetection;
- intended public archive.

Triage order:

1. Recover an expiring ephemeris.
2. Resolve source ambiguity before precision planetary characterization.
3. Obtain reconnaissance spectra before large precision-RV commitments when a
   stellar binary remains plausible.
4. Obtain contrast information before population validation.
5. If follow-up is unavailable, close the affected claim as `BLOCKED_EXTERNAL`.

Simulation cannot substitute for missing external observations.

## 28. Special Candidate Classes

The general workflow must be adapted explicitly for the signal class.

### Single transit

Freeze duration-based period priors, completeness, edge/gap treatment, and
follow-up-window propagation. Do not quote a unique period without independent
information.

### Duotransit

Preserve all integer-cycle aliases. Report alias weights and future windows.
Do not select the alias that gives the preferred physical interpretation.

### Long-period or few-event candidate

Event-level systematics and uniqueness dominate. Require event-by-event pixel,
quality, and difference-image evidence.

### Multiplanet candidate

Model shared stellar parameters and possible TTVs. Apply multiplicity boosts
only when their survey assumptions are valid.

### Giant-radius candidate

Treat brown-dwarf and low-mass-star scenarios explicitly. Radius alone cannot
establish planetary nature.

### Evolved host

Prioritize coherent stellar modeling, granulation/activity noise, dilution, and
astrodensity assumptions. Catalog products with small internal errors may still
be mutually inconsistent.

### Active or pulsating host

Separate stellar variability from transit-relevant time scales using a model
validated by injection. A periodogram peak is not automatically rotation.

## 29. Stop Rules and Scope Reduction

Stop rules prevent result hunting.

1. Freeze one primary method and at most a bounded, materially distinct fallback
   before real-data execution.
2. Do not search seeds, windows, kernels, priors, masks, or thresholds until a
   preferred result appears.
3. Do not remove an inconvenient event or branch without a result-blind rule.
4. Do not relax a threshold after observing the value.
5. Do not relabel a numerical repair as an independent scientific confirmation.
6. Preserve every valid failure and invalid attempt.
7. If the registered fallback fails, weaken or remove the dependent claim.
8. A new method-development phase requires a dated scope amendment that discloses
   all previous real-data results and freezes new stop rules.
9. The new phase cannot retroactively pass the old phase.
10. Packaging must stop while scientific scope remains unresolved.

Scope reduction is not failure concealment. A candidate-level paper is complete
when every stronger claim is explicitly removed, not claimed, or blocked, and
the remaining paper is internally consistent.

## 30. Manuscript and Claim Audit

Write the manuscript to the strongest passed gate, not to the intended target
gate.

Audit separately:

- title;
- abstract;
- result tables;
- figure captions;
- discussion;
- conclusions;
- data/software availability;
- supplementary machine-readable files.

Requirements:

- each final number maps to one adopted artifact;
- each qualitative claim maps to the claim charter;
- failed, diagnostic, and nonadopted results are labeled consistently;
- no unsupported `validated`, `confirmed`, `on-target`, `measured mass`, or
  `measured eccentricity` wording remains;
- model-conditional quantities state all major conditions;
- nondetections state their calibrated sensitivity or lack of it;
- the mathematical audit is bound to the exact final TeX hash;
- a second reader performs an independent claim-boundary review.

Gate:

- unsupported strong claims: zero;
- final numbers from unconverged chains: zero;
- untraceable numbers: zero;
- hidden informative priors or bounds: zero;
- manuscript/artifact status disagreements: zero.

## 31. Reproducibility Beyond File Integrity

Archive integrity, pipeline rerun, and independent scientific reproduction are
different achievements and must be labeled separately.

Every raw input should record:

- stable identifier and exact query;
- retrieval time and processing release;
- size, hash, and license;
- time standard and units;
- remote-service snapshot where practical.

Every derived artifact should record:

- input, script, configuration, and environment hashes;
- command and working assumptions;
- random-state policy;
- byte-deterministic, seeded-stochastic, tolerance-reproducible, or external
  classification;
- adopted, diagnostic, failed, invalid, or superseded status.

A random seed does not ensure byte identity across BLAS, compiler, GPU, or
multiprocessing implementations. Define semantic tolerances.

## 32. Release Engineering

Scientific freeze must precede release packaging.

Final order:

1. Freeze canonical manuscript values and claim scope.
2. Run claim and mathematical audits on final source.
3. Compile and visually inspect the final PDF.
4. Run complete offline tests and available integration tests.
5. Generate a new manifest from the exact release source.
6. Build arXiv and reproducibility packages from empty staging directories.
7. Reject undeclared files, duplicate paths, absolute paths, and path traversal.
8. Verify ZIP CRC and every embedded hash.
9. Extract elsewhere and run the documented offline suite.
10. Compile the staged arXiv source through the bibliography cycle.
11. Generate and independently verify the whole-archive checksum.
12. Deposit the exact tested files.
13. Download the public deposit and verify it independently.
14. Publish DOI metadata only after the DOI resolves to the verified record.

Do not create release ZIPs after every scientific phase. Build packages only at
an intentional checkpoint, scientific freeze, or final release.

## 33. Publication Identity and Stewardship

Keep one version identity across package filename, project metadata, citation
metadata, Git tag, schemas, archive metadata, and manuscript.

Rules:

- preserve public versions immutably;
- distinguish version DOI, concept DOI, arXiv identifier, and journal DOI;
- maintain a license matrix for code, manuscript, figures, derived data, and
  upstream products;
- keep machine-readable schemas versioned;
- maintain a changelog separating scientific and packaging changes;
- monitor catalog dispositions, new sectors, ephemeris expiry, literature, and
  follow-up;
- define correction, replacement, and retraction criteria;
- never claim that archive inclusion, peer review, or citation count validates a
  candidate.

## 34. Required Machine-Readable Status

The release status should include at least:

- schema and project version;
- target and as-of date;
- strongest supported gate;
- each readiness gate as a boolean or explicit status;
- safe and unsafe claims;
- incomplete material controls;
- work-package statuses;
- authoritative artifact paths and hashes;
- external blockers;
- stale audit or manifest flags;
- selected scope path and dated decision record.

The manuscript, status JSON, claim charter, tests, and release metadata must tell
the same story.

## 35. Required Templates

### Claim charter

| Claim ID | Claim | Evidence class | Required gates | Status | Artifact | Permitted wording |
|---|---|---|---|---|---|---|
| C-001 | Example claim | Direct / conditional / sensitivity | WP identifiers | Status code | Path and hash | Exact phrase |

### Protocol manifest

```json
{
  "schema_version": "TARGET_DEFINED",
  "target": "TARGET_ID",
  "work_package": "WP_ID",
  "frozen_utc": "ISO-8601",
  "previous_results_disclosed": [],
  "upstream": [{"path": "...", "sha256": "..."}],
  "software_environment": "ENVIRONMENT_ID",
  "model_family": [],
  "priors_bounds_transforms": {},
  "seeds": [],
  "thresholds": {},
  "fallback": null,
  "required_artifacts": [],
  "pass_rule": "TARGET_SPECIFIC",
  "failure_closure": "TARGET_SPECIFIC"
}
```

### Artifact registry

| Artifact | Hash | Producer | Inputs | Status | Claim use | Verifier |
|---|---|---|---|---|---|---|
| Path | SHA-256 | Script/config | Input hashes | Adopted/diagnostic/etc. | Claim IDs | Command |

### Release closure matrix

| Claim | Final closure | Final artifact | Manuscript locations | External blocker |
|---|---|---|---|---|
| Claim text | Supported/not claimed/removed/blocked | Path and hash | Section/table/figure | Observation |

## 36. Minimum Astrophysical Release Statement

Every candidate release should answer:

1. What was detected and by which search?
2. Was the search blind, targeted, or follow-up of a known candidate?
3. How many physical events and observing blocks support the signal?
4. Which source positions remain allowed?
5. Which instrumental and astrophysical false positives remain allowed?
6. Which stellar model and host assignment condition the radius?
7. Which orbital assumptions condition density, irradiation, and temperature?
8. Which chains converge and which are diagnostic only?
9. Which nondetections are sensitivity-calibrated?
10. Which exact observation would most likely change the disposition?
11. Which claim gate is passed, on what date, and by which artifact?

## 37. Lessons Generalized from TOI-3492.01

These lessons are methodological, not target-specific results:

1. A converged folded/binned chain can still be inadequate for a central
   astrodensity claim.
2. Build the native-cadence, sector-aware robustness model early.
3. Visible events in every sector do not imply constant depth.
4. Reduction, cadence mask, window, and baseline choices are correlated model
   specifications, not independent observations.
5. Carry unresolved specifications explicitly rather than forcing one winner.
6. Do not count the same model spread twice.
7. Predictive improvement does not override boundary, identifiability, or mask
   interaction failures.
8. Failure to select a complex kernel does not prove white noise is adequate.
9. Residual correlation on ingress/egress time scales can block precise geometry
   even after optimizer stationarity passes.
10. An optimizer success flag must be checked against parameter movement and
    objective improvement.
11. Numerical remediation, scientific model revision, and result search are
    different activities and need different protocols.
12. A post-result amendment must preserve the failed original gate.
13. Same-pixel fast and slow cadence products are consistency checks, not
    independent events.
14. Pipeline-corrected photometry must not receive a second crowding correction.
15. An unphysical high-significance phase harmonic may indicate residual
    systematics rather than a planetary phase curve.
16. Catalog sources outside an aperture can still contaminate through PRF wings.
17. Catalog stellar products can be mutually inconsistent despite small internal
    uncertainties.
18. A blackbody SED may check scale but cannot provide a coherent isochrone mass,
    age, and covariance.
19. Asteroseismic nondetection is not constraining without adequate injection and
    recovery sensitivity.
20. Formal sector heterogeneity does not identify its astrophysical cause.
21. A polished archive does not validate or confirm a candidate.
22. Raw-data integration tests and compact offline release tests must be labeled
    separately.
23. Manifest hashes are final only after the last scientific and manuscript
    change.
24. A release builder should enforce hashes rather than merely store them.
25. Missing optional tooling should trigger a bounded fallback, not an indefinite
    retry loop.
26. Documentation status must be synchronized with result artifacts before
    publication.

## 38. Start Sequence for a New Target

Use this order:

1. Create the target-specific claim charter and status schema.
2. Freeze official metadata and target identity.
3. Inventory and hash raw products.
4. Build cadence and event ledgers.
5. Audit instrumental systematics and source field.
6. Build minimally processed reduction families.
7. Recover the signal and aliases.
8. Build an early native-cadence reference model.
9. Freeze and test window/baseline uncertainty.
10. Freeze and test correlated-noise models.
11. Validate numerical behavior and residuals.
12. Build timing, activity, and sector hierarchy.
13. Build a coherent stellar posterior and limb-darkening distribution.
14. Calibrate source localization, dilution, and host branches.
15. Run end-to-end injection, coverage, and convergence tests.
16. Produce the final native-cadence posterior.
17. Run false-positive, FPP, and confirmation work only where inputs permit.
18. Compute derived quantities from joint draws.
19. Decide the strongest passed claim gate.
20. Write the manuscript to that gate.
21. Run stale-claim and mathematical audits.
22. Compile, test, manifest, package, extract, and verify.
23. Deposit, download, and verify before publishing identifiers.

The workflow is complete only when evidence gates, manuscript wording,
machine-readable status, tests, and release metadata agree.
