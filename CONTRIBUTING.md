# Contributing

## Scope

Contributions may improve analysis code, verification, documentation, data
lineage, protocols, manuscripts, or release engineering. Scientific history and
frozen artifacts must remain auditable.

## Before Work

1. Read `docs/lab/README.md` and `docs/lab/GOVERNANCE.md`.
2. Read `docs/reproducibility_order.md` before running scripts.
3. Inspect `git status` and do not overwrite unrelated work.
4. Classify the change C0-C6.
5. For data, protocol, claim, release, or security changes, create the required
   record before implementation.

## Frozen Evidence

Do not overwrite frozen protocols, manifests, results, gates, audits, or release
receipts. Use a new versioned file and explicit supersession link.

Do not weaken tests or thresholds merely to make a current result pass. A gate
change is a scientific protocol change and requires review.

## Development

1. Keep changes minimal and scoped.
2. Add tests for behavior changes.
3. Record data and environment dependencies.
4. Keep optional/network method development isolated from the verified core.
5. Never treat correlated reductions, masks, or cadence products as independent
   evidence without a documented justification.

## Verification

Run the commands applicable to the change. At minimum:

```powershell
python -m compileall scripts tests
python -m pytest -q
```

For scientific artifacts or claims, also run the applicable independent
verification and manuscript audits. Report exact failures; do not hide known
baseline failures.

## Review Request

Every review request should state:

1. Change class and purpose.
2. Scientific claims or release objects affected.
3. Protocol/data/source hashes affected.
4. Tests and audits run with exact results.
5. New warnings, limitations, or stale evidence.
6. Required reviewer roles.

Use `.github/PULL_REQUEST_TEMPLATE.md` where applicable.

## Commit and Release Rules

Commit only intended files. Do not commit secrets. Do not tag, publish, deposit,
or claim a DOI without explicit release authorization and a passing
release-object gate.

## Conduct

Review findings should be factual, reproducible, and non-blaming. Negative
results, failed gates, and uncertainty are valid scientific outcomes.
