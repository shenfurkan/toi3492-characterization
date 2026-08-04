# Protocols

Target-neutral protocol requirements for candidate research.

## Rules

1. A protocol is frozen in the candidate's `protocols/` directory before
   result-bearing execution.
2. The protocol must state inputs and hashes, model family, parameterization,
   priors, bounds, transforms, data splits and leakage controls, random seed
   policy, numerical diagnostics, acceptance thresholds, stop rules, required
   artifacts, and the claims opened or closed by each outcome.
3. Material thresholds cannot be selected from the target result they will
   judge. Prior exposure must be disclosed.
4. A protocol change after result exposure requires a new version, an explicit
   amendment note, and synthetic or external calibration before new execution.
5. Shared `protocols/templates/` documents are generic; candidate-specific
   copies live in `candidate/<candidate-id>/protocols/`.

Use `templates/protocol.md`, `templates/run-record.md`, and
`templates/gate-review.md` from `docs/templates/` or `protocols/templates/`.
