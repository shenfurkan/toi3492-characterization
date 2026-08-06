# EXONYM

EXONYM is a candidate-isolated research framework for organizing, screening, and documenting exoplanet-candidate work. It couples a Python package and command-line interface with per-candidate workspaces, provenance records, workflow gates, and reproducibility bundles.

The project is designed around a simple rule: shared software must remain target-neutral, while every identifier, measurement, data product, decision, and scientific claim for a target belongs in that target's workspace.

## Status and scope

Package metadata currently identifies EXONYM as version `1.0.0`. It is research software under active development. Use it to structure candidate investigations and preserve evidence; do not treat it as a planet-validation service, a substitute for independent follow-up, or a basis for publication by itself.

EXONYM currently supports:

- Candidate-local workspace creation and lifecycle tracking.
- TESS SPOC light-curve and target-pixel-product ingestion with provenance sidecars.
- Checklist-driven progression through a seven-phase workflow.
- Targeted and blind Box Least Squares (BLS) screening.
- Catalog-prior retrieval, archival-vetting queries, diagnostic plotting, and several exploratory analysis commands.
- Schema validation, target-isolation auditing, and candidate-local reproducibility bundles.

EXONYM does not currently provide a complete end-to-end validation pipeline. In particular, a passing workflow gate, a recovered BLS period, a low numerical FPP, or a catalog match is not a planetary validation or discovery claim. The scientific-use boundaries below are part of the public contract of the project.

## Design principles

### Target isolation

No target-specific data, identifiers, aliases, sector selections, ephemerides, or constants may appear outside `candidate/`. Shared code, tests, schemas, templates, policies, and documentation must stay target-neutral.

Run this after any structural or scientific-workflow change:

```powershell
exonym verify
```

The audit checks for forbidden top-level research directories, research payloads outside candidate workspaces, catalog identifiers and registered aliases in neutral-zone text, hard-coded ephemeris and sector literals in shared Python source, and reparse points such as symlinks or Windows junctions. Isolation-policy exceptions must identify the exact path, line, rule, rationale, and expiration date; expired exceptions do not suppress a violation.

### Evidence before advancement

Candidate work proceeds through explicit gates. EXONYM records what passed, when it passed, and which candidate-local document or artifact supplied the evidence. A gate is a workflow control, not a scientific conclusion.

### Candidate-local provenance

Raw data, downloaded catalog information, run outputs, claims, decisions, figures, manuscripts, and release bundles are stored under the candidate workspace. The shared library contains no target data.

### Reproducible resources

Source checkouts can use the editable root `templates/` and `schemas/` directories. Installed distributions carry packaged copies of the required templates and schemas, so `init` and `verify` can operate without a source checkout.

## Repository layout

```text
src/exonym/                 Target-neutral Python package and CLI
src/exonym/_resources/      Packaged schemas and workspace templates
candidate/<candidate-id>/   Isolated research workspace for one candidate
schemas/                    Editable source schemas
templates/                  Editable source workspace templates
tests/                      Synthetic, target-neutral tests
policy/                     Isolation policy and exception registry
protocols/, methods/, docs/ Target-neutral project guidance
requirements-lock.txt       Pinned dependency list used by freeze
```

An initialized workspace contains these main areas:

```text
candidate/<candidate-id>/
  candidate.json            Identity, lifecycle, workflow, and publication state
  config/                   Candidate-local configuration and signal priors
  data/                     Raw, processed, interim, and external data
  docs/                     Phase checklists and research notes
  decisions/                Novelty and review decisions
  provenance/               Supporting provenance material
  outputs/, figures/        Analysis products and diagnostics
  claims/                   Structured scientific assertions
  gates/, lifecycle/        Gate records and state-change event log
  releases/                 Frozen reproducibility bundles
```

Candidate identifiers are lowercase, path-safe names containing letters, digits, dots, hyphens, or underscores. Do not use a Windows reserved name. Create and update workspaces through the CLI rather than moving files into the shared repository tree.

## Installation

EXONYM currently requires Python `3.9.*`.

From a source checkout, install the core package and test tools with:

```powershell
python -m pip install -e ".[test]"
```

Install the optional screening and asteroseismology dependencies when those commands are needed:

```powershell
python -m pip install -e ".[test,screening,asteroseismology]"
```

Use `exonym --help` to see the installed command surface. `python -m exonym` is equivalent to the `exonym` command. If you supply a repository root, place the global `--root` option before the subcommand:

```powershell
exonym --root <workspace-root> verify
```

## Getting started

The following sequence uses placeholders only. Replace them with candidate-local values after establishing the canonical catalog identity.

```powershell
# Create an isolated workspace.
exonym --root <workspace-root> init candidate-id --toi <TOI-NUMBER> --tic <TIC-NUMBER> --mission tess

# Check the newly created workspace and the repository boundary.
exonym --root <workspace-root> verify
exonym --root <workspace-root> track candidate-id

# Retrieve SPOC light curves or target-pixel products as appropriate.
exonym --root <workspace-root> ingest candidate-id --products lc
exonym --root <workspace-root> ingest candidate-id --products tp

# Retrieve catalog priors, then run a signal-directed BLS screening search.
exonym --root <workspace-root> fetch-priors candidate-id
exonym --root <workspace-root> search candidate-id --signal <signal-suffix>

# Review the candidate-local evidence and advance only when the current gate passes.
exonym --root <workspace-root> advance candidate-id
```

`init` writes `candidate.json`, creates the standard directories, and copies the workspace templates. Do not hand-edit lifecycle state in `candidate.json`. Use `set-state` so EXONYM validates and logs the change:

```powershell
exonym --root <workspace-root> set-state candidate-id --state paused --reason "Waiting for documented evidence"
```

Changing a stopped, published, or archived candidate requires a non-empty reason. A stopped candidate cannot advance until it has been deliberately reopened through this audited state-change path.

## Workflow and gates

The workflow is sequential:

```text
intake -> feasibility -> acquisition -> vetting -> followup -> analysis -> review
```

`exonym advance <candidate-id>` evaluates the candidate's current phase. It writes a gate record under `gates/` and appends lifecycle events only after all required conditions pass.

| Current phase | Required evidence before advancement |
| --- | --- |
| `intake` | All mandatory items in `docs/01_intake_manifest.md` are complete. |
| `feasibility` | All mandatory items in `docs/02_feasibility_report.md` are complete, and a current eligible novelty audit exists. |
| `acquisition` | Every raw FITS product has a matching `<stem>.provenance.json` sidecar. |
| `vetting` | All mandatory items in `docs/03_spoc_dv_vetting.md` are complete. |
| `followup` | All mandatory items in `docs/04_tfop_sg_followup.md` are complete. |
| `analysis` | A candidate-local FPP claim is below the workflow threshold. |
| `review` | All mandatory items in `decisions/review_gate.md` are complete, and a current eligible novelty audit exists. Passing this phase locks the lifecycle to `published`. |

Every required checklist item must use the form below:

```markdown
- [ ] [MANDATORY] Describe the evidence required for this candidate.
```

`exonym track <candidate-id>` reports checklist completion and the current phase. It does not replace review of the underlying evidence.

### Novelty audit

The feasibility and review gates require `decisions/novelty_audit.json`. The record is schema-validated and must include the candidate ID, retrieval time, expiration time, decision basis, and hash-backed evidence entries. Its status must be `eligible` and its freshness window must still be valid.

This gate prevents an undocumented or stale originality decision from being treated as current. It does not automatically search the literature, interpret follow-up saturation, or decide whether a result is novel enough for a journal. Researchers must perform that assessment using primary sources, record the evidence, and update it before the review gate expires.

## Command reference

### Workspace and governance commands

| Command | Purpose |
| --- | --- |
| `init` | Create a candidate-local workspace and clone required templates. |
| `list` | List registered workspaces, optionally filtered by phase, tag, or mission. |
| `status` | Print one candidate's metadata and standard workspace paths. |
| `track` | Render the checklist and phase-progress dashboard. |
| `advance` | Validate the current gate and promote the candidate by one phase. |
| `set-state` | Change lifecycle state with event logging. |
| `tag` | Add metadata tags to a candidate record. |
| `freeze` | Build a candidate-local reproducibility bundle. |
| `verify` | Run isolation and schema validation, or schema validation alone with `--schemas-only`. |

### Data and screening commands

| Command | Purpose | Notes |
| --- | --- | --- |
| `ingest` | Request TESS SPOC light curves, target-pixel products, or both. | Writes raw products and provenance sidecars. Network access and product availability are required. |
| `fetch-priors` | Retrieve catalog transit priors into `config/signals/`. | Review catalog values, units, time system, source, and retrieval date before use. |
| `search` | Run a blind or signal-directed BLS screening search. | `--signal` requires a matching candidate-local transit-config file. |
| `vet` | Run the optional TRICERATOPS FPP screening command. | Requires the `screening` extra and independent scientific review. |
| `archive` | Query available Gaia and ExoFOP archival evidence. | An unavailable or unvalidated query result is unknown evidence, not an absence of follow-up. |
| `plot` | Create diagnostic candidate-local figures. | Inspect the source and inputs recorded by the output. |

### Exploratory analysis commands

| Command | Current purpose |
| --- | --- |
| `fit` | MCMC transit fitting with optional eccentric-orbit parameters. |
| `ttv` | Transit-timing variation screening. |
| `phasecurve` | Phase-curve and secondary-eclipse screening. |
| `activity` | Stellar-activity and rotation-periodogram screening. |
| `dilution` | Aperture and dilution sensitivity checks. |
| `localization` | Target-pixel PRF source-localization analysis. |
| `sed` | Stellar atmosphere fitting from available broadband information. |
| `asteroseismology` | Oscillation and seismic-scaling analysis when its optional dependencies are installed. |

Run `exonym <command> --help` for command-specific options. Commands that access public archives can fail because a service is unavailable, a product is missing, or an input cannot be validated. Treat those outcomes as evidence states to document, not as a negative scientific finding.

## Data, provenance, and signal configuration

TESS ingestion writes raw products below `data/raw/` and records a JSON provenance sidecar for each FITS file. The acquisition gate expects this naming convention:

```text
<stem>.provenance.json
```

For example, the sidecar belongs beside the product and uses its stem, rather than appending `.provenance.json` after the full FITS filename. The provenance schema records the source URI, download time, file hash, and retrieval tool.

`fetch-priors` writes catalog-derived signal configurations under `config/signals/`. A signal-directed search reads the selected configuration and writes a signal-specific BLS result. Catalog priors guide a recovery search; they are not a substitute for checking data quality, transit timing, aliases, or physical plausibility.

## Scientific-use boundaries

EXONYM supports research judgment. It does not automate that judgment away.

- A BLS result identifies a periodic box-shaped signal under the selected preprocessing and search settings. It does not establish a false-alarm probability, recoverability across an observing population, or a new planetary discovery.
- TRICERATOPS output is screening evidence. A low FPP can be a useful input to validation only when the underlying light curve, stellar characterization, contamination constraints, follow-up evidence, assumptions, and uncertainty treatment have been independently reviewed.
- The analysis gate's FPP condition is a procedural rule. It must never be reported as proof that a candidate is validated.
- Gaia, ExoFOP, and other archival queries can be incomplete, stale, unavailable, or unvalidated. Record their status and preserve the underlying evidence before drawing a crowding, binarity, follow-up, or originality conclusion.
- Some analysis paths can emit explicitly labeled synthetic demonstration output when usable candidate data are absent. Synthetic output is for software demonstration and tests only. It must not support a gate sign-off, claim, manuscript result, or public scientific statement.
- The package includes a `celerite` dependency, but the public CLI does not currently run a documented Gaussian-process noise-model workflow. Do not describe OU, Matérn, SHO, or GP-derived inferences as EXONYM results until an implemented model, configuration, diagnostics, provenance record, and validation tests exist.
- Transit fitting, TTV, phase-curve, activity, dilution, SED, localization, and asteroseismic commands are exploratory tools. Review their inputs, assumptions, uncertainties, and physical-sanity flags before using any output outside the workspace.

A publication-quality study needs its own methods section, input-data description, uncertainty treatment, validation plan, literature review, and independent scientific review. EXONYM can preserve those materials; it cannot replace them.

## Schemas and validation

EXONYM validates candidate-local JSON artifacts against JSON Schema Draft 2020-12 definitions:

| Schema | Covers |
| --- | --- |
| `candidate.schema.json` | Candidate identity, lifecycle, workflow, scientific disposition, and publication metadata. |
| `provenance.schema.json` | Downloaded-product provenance sidecars. |
| `claim.schema.json` | Candidate-local parameter claims, including FPP claims. |
| `novelty-audit.schema.json` | Current, evidence-backed originality decisions used by feasibility and review gates. |

Run the full audit with:

```powershell
exonym verify
```

Run only schema validation with:

```powershell
exonym verify --schemas-only
```

Schema validity confirms structure. It does not establish that a scientific value, source interpretation, or method choice is correct.

## Reproducibility bundles

`exonym freeze <candidate-id>` creates a release directory beneath that candidate's `releases/` folder. It copies the repository lockfile, creates environment and container definitions, and writes a manifest with file hashes, the candidate metadata hash, and the current Git commit when available.

```powershell
exonym --root <workspace-root> freeze candidate-id --version <release-version>
```

`freeze` requires `requirements-lock.txt` at the repository root. A frozen bundle captures the software and candidate-local materials available at the time of the command. It is not a journal archive, a long-term data repository, or a guarantee that third-party data services and dependencies will remain available.

## Development and verification

Run the complete shared test suite after code, schema, template, or test changes:

```powershell
python -m pytest -q
python -m compileall -q src tests
exonym verify
exonym verify --schemas-only
```

The shared tests use synthetic fixtures and check software behavior. They do not validate any real candidate or replace inspection of candidate-local inputs and outputs.

Before contributing a change:

- Keep target-specific material inside `candidate/<candidate-id>/`.
- Pass target-specific values through configuration or function arguments, never shared-source constants.
- Add or update tests for shared-code behavior.
- Run the full verification commands after structural changes.
- Make gate, schema, and lifecycle changes explicit and documented in the affected candidate workspace.
- Do not hand-edit `candidate.json` for a lifecycle transition; use `set-state` so the event is logged.

See `CONTRIBUTING.md` and `SECURITY.md` for project contribution and security-reporting guidance.

## License

This checkout does not currently include a `LICENSE` file, although the package metadata refers to one. Do not redistribute EXONYM as an open-source package until the project owner supplies and includes the intended license text.
