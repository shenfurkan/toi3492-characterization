# Transit Fitting Protocol :: toi-7105.01

Target: 7105.01 / 119565548 | Frozen: 2026-08-04T00:00:00Z | Phase: analysis

## Prior Specification

Document the model family, parameterization, priors, bounds, and transforms
before any result-bearing execution:

- Orbital period and epoch prior sources
- Radius ratio, impact parameter, and scaled semimajor-axis priors
- Limb-darkening treatment and its stellar parameter inputs
- Detrending window and baseline polynomial selection
- Noise model (white or correlated) and jitter treatment

## Sampling and Numerical Execution

- Optimizer/sampler and start configuration
- Convergence diagnostics (R-hat, integrated autocorrelation time)
- Random seed policy and worker layout

## Synthetic Calibration

- Calibration classes and truth distributions
- Coverage and bias metrics
- Failure thresholds and stop rules

## Required Artifacts

List every output artifact with its schema and no-clobber rule.

## Binding Gates

| Gate ID | Metric | Threshold | PASS effect | FAIL effect |
|---|---|---|---|---|
| | | | | |
