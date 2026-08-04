# EXONYM

**Candidate-Isolated Factory for Reproducible TESS & Multi-Mission Exoplanet Research**

`EXONYM` (v0.3.0) is a factory-style, evidence-first research workspace and command-line system designed for exoplanet candidate management, automated data acquisition, vetting, quality verification gating, statistical validation, and reproducible release packaging.

---

## Table of Contents

- [The Core Invariant](#the-core-invariant)
- [Architecture & Target Isolation](#architecture--target-isolation)
- [Repository Layout](#repository-layout)
- [Candidate Workspace Layout](#candidate-workspace-layout)
- [Installation & Environment Setup](#installation--environment-setup)
- [CLI Command Matrix](#cli-command-matrix)
- [Command Reference](#command-reference)
  - [`exonym init`](#exonym-init)
  - [`exonym ingest`](#exonym-ingest)
  - [`exonym list`](#exonym-list)
  - [`exonym status`](#exonym-status)
  - [`exonym track`](#exonym-track)
  - [`exonym advance`](#exonym-advance)
  - [`exonym tag`](#exonym-tag)
  - [`exonym freeze`](#exonym-freeze)
  - [`exonym verify`](#exonym-verify)
- [Workflow Phases & Quality Verification Gates (QVG)](#workflow-phases--quality-verification-gates-qvg)
- [Vetting Engine & Quantitative Tests](#vetting-engine--quantitative-tests)
- [JSON Schema System](#json-schema-system)
- [Reproducibility Freeze Engine](#reproducibility-freeze-engine)
- [End-to-End Walkthrough](#end-to-end-walkthrough)
- [Development & Testing](#development--testing)
- [Governance & Policy](#governance--policy)
- [License](#license)

---

## The Core Invariant

> **No target-specific research, data, or code is permitted outside `candidate/`.**  
> Archiving is a lifecycle state in `candidate/<candidate-id>/candidate.json`, never a top-level directory move or file relocation.

`EXONYM` strictly enforces target isolation. Every byte outside `candidate/` must be demonstrably target-neutral shared infrastructure.

Run the repository isolation and schema integrity audit at any time:

```powershell
exonym verify
```

### Enforced Isolation Rules

1. **Path Ownership**: Top-level `archive/` or `data/` directories are forbidden.
2. **Payload Protection**: Research payload file extensions (`.fits`, `.fit`, `.fz`, `.csv`, `.tsv`, `.parquet`, `.npy`, `.npz`, `.h5`, `.hdf5`, `.pkl`, `.joblib`, `.pdf`, `.tex`, `.zip`, `.tar`, `.gz`, `.ipynb`, `.png`, `.jpg`, `.jpeg`, `.log`) are forbidden outside `candidate/`.
3. **Alias Leak Prevention**: Catalog identifiers (TOI, TIC, KOI, EPIC, PIC, CHEOPS) and registered alias strings from `candidate.json` records must never leak into neutral-zone code or documentation.
4. **AST Constant Scan**: Python files under `src/` are statically analyzed via AST to prohibit hardcoded sector numbers, ephemeris values, or non-trivial numeric literals assigned to transit/ephemeris variables.
5. **Symlink Rejection**: Reparse points, junctions, and symlinks are prohibited across the entire repository tree.

---

## Architecture & Target Isolation

The architecture cleanly bifurcates target-neutral infrastructure from target-specific research:

```
[ Root Workspace ]
  ├── Shared Target-Neutral System (src/, schemas/, templates/, protocols/, methods/, docs/, policy/)
  └── Candidate-Isolated Research Workspaces (candidate/<candidate-id>/)
        ├── Metadata & Identity (candidate.json)
        ├── Raw & Processed Data (data/raw/, data/processed/)
        ├── Gate Checklists & Audit Logs (docs/, gates/, decisions/)
        ├── Claims Assertion (claims/)
        └── Frozen Reproducibility Releases (releases/<version>/)
```

---

## Repository Layout

| Path | Description |
| --- | --- |
| `candidate/` | Candidate research workspaces (`candidate/<candidate-id>/`) containing target identity, raw/processed data, gate sign-offs, and claims. |
| `src/exonym/` | Target-neutral Python library providing workspace management, gatekeeping, catalog parsing, ingestion, vetting, telemetry, and isolation auditing. |
| `schemas/` | Machine-validated JSON Schema files (Draft 2020-12) for candidate records, data provenance sidecars, and scientific claims assertions. |
| `templates/` | Global Markdown gate documents cloned into every newly provisioned candidate workspace. |
| `tests/` | Shared unit and integration test suite using synthetic data fixtures exclusively. |
| `docs/` | System governance policies, workflow lifecycle definitions, and documentation templates. |
| `protocols/` | Target-neutral protocol requirements and analysis standards. |
| `methods/` | Target-neutral algorithms, feasibility metrics, and vetting method guidance. |
| `policy/` | Policy enforcement rules and exception registry (`policy/isolation-exceptions.json`). |
| `resources/` | Metadata-only general reference resources. |
| `pyproject.toml` | Build metadata, CLI entry points, and python package dependencies. |
| `requirements-lock.txt` | Fully pinned production dependency lockfile. |

---

## Candidate Workspace Layout

When a new candidate is initialized (`exonym init <id>`), `EXONYM` provisions the following directory tree under `candidate/<id>/`:

```
candidate/<candidate-id>/
├── candidate.json        # Schema v2 candidate identity record
├── README.md             # Candidate summary & first-pass instructions
├── config/               # Target-specific algorithm configuration
├── data/
│   ├── raw/              # SPOC FITS products & .provenance.json sidecars
│   ├── external/         # External catalog cross-match data
│   ├── interim/          # Un-binned light curves & intermediate arrays
│   └── processed/        # Phase-folded & detrended light curve products
├── docs/                 # Cloned gate documents (intake, feasibility, vetting, followup)
├── protocols/            # Target-specific protocol declarations
├── gates/                # Audit records generated by exonym advance (gate-*.json)
├── claims/               # Scientific assertions (FPP, period, radius, mass)
├── decisions/            # Peer review sign-offs (review_gate.md)
├── lifecycle/            # Lifecycle event logs (events.jsonl)
├── provenance/           # Execution provenance sidecars
├── outputs/              # Analysis summary text & report outputs
├── figures/              # Diagnostic vetting plots & corner plots
├── literature/           # Target-specific reference notes
├── manuscripts/          # Draft manuscript TeX/Markdown source
├── releases/             # Frozen reproducibility bundles (exonym freeze)
├── scripts/              # Target-specific pipeline runner scripts
├── tests/                # Target-specific unit and regression tests
├── tracking/             # Telemetry tracking state
└── scratch/              # Temporary scratch work
```

---

## Installation & Environment Setup

### System Requirements

- **Python**: `3.9.*` (`==3.9.*` required by package metadata)
- **Setuptools**: `>= 68.0`

### Installation Options

#### 1. Core Installation

```powershell
pip install -e .
```

#### 2. Test & Schema Dependencies

```powershell
pip install -e ".[test]"
```

#### 3. Full Suite (Screening & Asteroseismology Extras)

```powershell
pip install -e ".[test,screening,asteroseismology]"
```

### Dependency Stack

| Package | Version | Purpose |
| --- | --- | --- |
| `numpy` | `1.26.4` | Numerical array operations |
| `scipy` | `1.13.1` | Scientific computing & signal processing |
| `pandas` | `2.3.3` | Dataframe manipulation |
| `matplotlib` | `3.9.4` | Diagnostic plotting |
| `astropy` | `6.0.1` | Astronomical utilities & FITS I/O |
| `astroquery` | `0.4.11` | MAST / Exoplanet Archive queries |
| `lightkurve` | `2.6.0` | TESS/Kepler light curve processing |
| `batman-package` | `2.5.3` | Transit light curve modeling |
| `celerite` | `0.4.3` | Gaussian process stellar variability modeling |
| `emcee` | `3.1.6` | MCMC ensemble sampler |
| `corner` | `2.3.0` | Posterior distribution visualization |
| `ldtk` | `1.8.6` | Limb darkening toolkit |
| `jsonschema` | `4.25.1` | JSON Schema draft 2020-12 validator |
| `pytest` | `8.4.2` | Test framework |
| `triceratops` | `1.0.20` | False Positive Probability (FPP) screening |

---

## CLI Command Matrix

| Command | Syntax | Core Function |
| --- | --- | --- |
| `init` | `exonym init <id> --toi <toi> --tic <tic> [--mission <m>] [--tag <t>]` | Provision a candidate workspace & clone global templates |
| `ingest` | `exonym ingest <id> [--sectors S1 S2 ...] [--exptime <sec>]` | Fetch SPOC light curves from MAST & generate `.provenance.json` |
| `list` | `exonym list [--phase <p>] [--tag <t>] [--mission <m>]` | Query and filter registered candidate workspaces |
| `status` | `exonym status <id>` | Display identity metadata and workspace directory paths |
| `track` | `exonym track <id>` | Render the terminal ANSI Quality Verification Gate (QVG) dashboard |
| `advance` | `exonym advance <id>` | Audit current gate requirements and promote workflow phase |
| `tag` | `exonym tag <id> <tag...>` | Attach metadata tags to a candidate record |
| `freeze` | `exonym freeze <id> [--version <v>]` | Build a sealed reproducibility bundle under `releases/<version>/` |
| `search` | `exonym search <id> [--period-min <d>] [--period-max <d>]` | Run a BLS transit search and save `outputs/bls_search_results.json` |
| `plot` | `exonym plot <id>` | Generate diagnostic figures under `figures/` (uses BLS result when present) |
| `verify` | `exonym verify [--schemas-only]` | Run the repository target-isolation scan & JSON schema validation |

---

## Command Reference

### `exonym init`

Provision a new candidate workspace inside `candidate/<id>/` and clone global gate documents.

```powershell
exonym init candidate-alpha --toi <toi> --tic <tic> --mission tess --tag planet-candidate --tag priority-1
```

- **Arguments**:
  - `<candidate_id>`: Lowercase identifier matching `^[a-z0-9][a-z0-9._-]*$`.
  - `--toi`: TOI identifier without the `TOI` prefix (e.g., `<toi>`).
  - `--tic`: Positive integer TIC catalog identifier.
  - `--mission`: Mission origin (`tess`, `kepler`, `k2`, `plato`, `cheops`).
  - `--tag`: Metadata tag (repeatable).

---

### `exonym ingest`

Download SPOC 2-minute or 20-second light curve FITS products from MAST via `lightkurve`, save them into `candidate/<id>/data/raw/`, and write SHA-256 provenance sidecars.

```powershell
exonym ingest candidate-alpha --sectors 14 15 16 26 --exptime 120
```

- **Provenance Sidecar**: Every downloaded `<product>.fits` generates a `<product>.provenance.json` containing `source_uri`, `download_timestamp_utc`, `sha256`, and `fetched_by`.

---

### `exonym list`

Filter registered candidates across the repository.

```powershell
exonym list --phase vetting --mission tess --tag priority-1
```

- **Output**: Pretty-printed JSON array of candidate metadata records matching the criteria.

---

### `exonym status`

View detailed state and workspace layout for a target.

```powershell
exonym status candidate-alpha
```

---

### `exonym track`

Display the ANSI progress telemetry dashboard parsing checklist completion in phase gate markdown files.

```powershell
exonym track candidate-alpha
```

**Dashboard Output Example**:

```
+------------------------------------------------------------------+
| EXONYM CANDIDATE TELEMETRY DASHBOARD :: Target: candidate-alpha  |
+------------------------------------------------------------------+
| Lifecycle State    : ACTIVE                                      |
| Workflow Phase     : VETTING (Phase 4 of 7)                      |
| Scientific Disp.   : CANDIDATE                                   |
| Progress           : [===================-------------------] 48.0%  |
+------------------------------------------------------------------+
| DOCUMENT MANIFEST:                                               |
| [X] docs/01_intake_manifest.md                                   |
|     (100% - 4/4 tasks completed)                                 |
| [X] docs/02_feasibility_report.md                                |
|     (100% - 5/5 tasks completed)                                 |
| [!] docs/03_spoc_dv_vetting.md                                   |
|     ( 60% - 3/5 tasks completed)                                 |
|     [ ] [MANDATORY] Centroid difference image offset < 3.0 sigma |
| [ ] docs/04_tfop_sg_followup.md                                  |
|     (  0% - 0/4 tasks completed)                                 |
| [ ] decisions/review_gate.md                                     |
|     (  0% - 0/3 tasks completed)                                 |
+------------------------------------------------------------------+
```

---

### `exonym advance`

Promote a candidate candidate to the next sequential workflow phase after verifying all mandatory checklist items and programmatic gate checks.

```powershell
exonym advance candidate-alpha
```

- **Behavior**: Upon passing, appends a sign-off record to `candidate/<id>/gates/gate-<index>-<phase>.json` and records a lifecycle event in `candidate/<id>/lifecycle/events.jsonl`.
- **Review Locking**: Advancing from `review` automatically transitions the candidate lifecycle state to `published`.

---

### `exonym tag`

Attach metadata tags to an existing candidate.

```powershell
exonym tag candidate-alpha ultra-short-period sub-neptune
```

---

### `exonym freeze`

Create a content-addressed, sealed reproducibility release package under `candidate/<id>/releases/<version>/`.

```powershell
exonym freeze candidate-alpha --version release-v1.0
```

Generates:
- `requirements.lock.txt`: Exact Pinned Python dependencies.
- `environment.lock.yml`: Conda environment definition.
- `Dockerfile`: Container image specification (`python:3.9-slim`).
- `Apptainer.def`: HPC Singularity/Apptainer definition file.
- `manifest.json`: SHA-256 hashes of all release files, target `candidate.json`, and git commit hash.

---

### `exonym search`

Run a Box Least Squares (BLS) transit period search over the candidate's light curve data and save the winning signal to `candidate/<id>/outputs/bls_search_results.json`.

```powershell
exonym search candidate-alpha --period-min 1.0 --period-max 10.0
```

- **Data source**: FITS products under `data/processed/` (preferred) or `data/raw/` are median-binned and normalized before the search. When no readable light curve exists, a synthetic demonstration grid is analyzed and the payload is explicitly marked `"source": "synthetic-demo"`; real-data runs are marked `"source": "candidate-data"`.

Output schema:

```json
{
  "best_period": 4.20155,
  "best_epoch": 2459005.0,
  "best_depth_ppm": 5000.0,
  "best_duration_hours": 3.0,
  "snr": 28.41,
  "source": "candidate-data",
  "n_points": 4000
}
```

---

### `exonym plot`

Generate headless diagnostic vetting figures under `candidate/<id>/figures/`:

```powershell
exonym plot candidate-alpha
```

- Produces `phase_folded_lc.png` and `centroid_offset.png` at 300 dpi.
- When `outputs/bls_search_results.json` exists, the phase fold automatically uses its best period and epoch.
- Real candidate light curves are plotted when available; otherwise a deterministic synthetic grid is rendered (fixed RNG seed, reproducible).

---

### `exonym verify`

Run the isolation audit and validate all workspace JSON files against JSON Schemas.

```powershell
exonym verify
```

To run schema validation only:

```powershell
exonym verify --schemas-only
```

---

## Workflow Phases & Quality Verification Gates (QVG)

`EXONYM` enforces a strict 7-phase sequential workflow state machine. Phase promotion is blocked until all mandatory conditions are satisfied.

```
0. intake  ──►  1. feasibility  ──►  2. acquisition  ──►  3. vetting  ──►  4. followup  ──►  5. analysis  ──►  6. review (Locked)
```

| Phase Index | Phase Name | Primary Gate Artifact | Gate Validation Requirement |
| --- | --- | --- | --- |
| **Phase 0** | `intake` | `docs/01_intake_manifest.md` | Canonical catalog identity (TOI/TIC) verified; no directory name collisions. |
| **Phase 1** | `feasibility` | `docs/02_feasibility_report.md` | Stellar contamination, transit SNR, and sector coverage feasibility signed off. |
| **Phase 2** | `acquisition` | `data/raw/` | Every raw FITS file in `data/raw/` must have a valid `.provenance.json` sidecar. |
| **Phase 3** | `vetting` | `docs/03_spoc_dv_vetting.md` | Odd-even depth asymmetry, difference-image centroiding, and ephemeris checks completed. |
| **Phase 4** | `followup` | `docs/04_tfop_sg_followup.md` | TFOP Working Group SG1–SG5 ground-based observational follow-up recorded. |
| **Phase 5** | `analysis` | `claims/` | At least one valid JSON claim assertion in `claims/` with parameter `fpp` < `0.01`. |
| **Phase 6** | `review` | `decisions/review_gate.md` | Peer review signed off; lifecycle permanently transitions to `published`. |

---

## Vetting Engine & Quantitative Tests

`EXONYM` includes built-in statistical vetting modules under `src/exonym/vetting/` and light curve analysis helpers under `src/exonym/lightcurve.py`.

### 1. Difference-Image Centroid Offset Test (`src/exonym/vetting/centroid.py`)

Evaluates whether the observed transit signal originates on the target star or an offset background eclipsing binary (BEB):

$$Z_{\text{centroid}} = \frac{\sqrt{(\Delta \alpha \cos \delta)^2 + (\Delta \delta)^2}}{\sigma_{\text{centroid}}}$$

- **Pass Threshold**: $Z_{\text{centroid}} < 3.0\,\sigma$ (consistent with on-target transit).
- **Fail Threshold**: $Z_{\text{centroid}} \ge 3.0\,\sigma$ (indicates background blend).

```python
from exonym.vetting.centroid import centroid_gate

passed, z_score = centroid_gate(
    ra_offset_arcsec=0.12,
    dec_offset_arcsec=0.08,
    dec_deg=28.4,
    sigma_arcsec=0.07
)
# Returns (True, 0.178...)
```

---

### 2. Odd-Even Transit Depth Asymmetry Test (`src/exonym/vetting/oddeven.py`)

Tests for secondary eclipsing binary scenarios with double the assumed orbital period by comparing odd and even transit depths:

$$Z_{\text{odd-even}} = \frac{|d_{\text{odd}} - d_{\text{even}}|}{\sqrt{\sigma_{\text{odd}}^2 + \sigma_{\text{even}}^2}}$$

- **Pass Threshold**: $Z_{\text{odd-even}} < 3.0\,\sigma$ (consistent with planetary candidate).

```python
from exonym.vetting.oddeven import odd_even_gate

passed, z_score = odd_even_gate(
    depth_odd=1250.0,
    sigma_odd=45.0,
    depth_even=1240.0,
    sigma_even=42.0
)
# Returns (True, 0.162...)
```

---

### 3. Statistical False Positive Probability (FPP) Gate (`src/exonym/vetting/tricera_parse.py`)

Parses TRICERATOPS output JSON reports to assert statistical validation:

- **Pass Threshold**: $\text{FPP} < 0.01$ ($1\%$).

```python
from exonym.vetting.tricera_parse import fpp_gate

passed, fpp = fpp_gate({"fpp": 0.0034})
# Returns (True, 0.0034)
```

---

### 4. Phase Folding & Robust Depth Estimation (`src/exonym/lightcurve.py`)

- `phase_hours(time_btjd, period_days, epoch_btjd)`: Computes signed phase hours from transit center.
- `robust_transit_depth(...)`: Calculates median in/out transit depth and standard error in ppm.
- `bin_phase_folded_flux(...)`: Median-bins folded light curves into uniform time windows (default 8 minutes).

---

## JSON Schema System

All data records in `EXONYM` are machine-validated against JSON Schemas located in `schemas/`:

### 1. Candidate Record Schema (`schemas/candidate.schema.json`)

Validates `candidate/<id>/candidate.json`.

```json
{
  "schema_version": 2,
  "candidate_id": "candidate-alpha",
  "identifiers": {
    "toi": "1234.01",
    "tic": "987654321",
    "aliases": ["candidate-alpha"],
    "mission": "tess",
    "tags": ["planet-candidate"]
  },
  "lifecycle": {
    "state": "active",
    "state_since": "2026-08-04T12:00:00Z",
    "reason": "Initial intake"
  },
  "workflow": { "phase": "intake" },
  "scientific_disposition": "unknown",
  "publication": "none",
  "created_at": "2026-08-04T12:00:00Z"
}
```

- **Allowed Lifecycle States**: `active`, `paused`, `stopped`, `published`, `archived`.
- **Allowed Workflow Phases**: `intake`, `feasibility`, `acquisition`, `vetting`, `followup`, `analysis`, `review`.
- **Allowed Dispositions**: `unknown`, `candidate`, `unvalidated_candidate`, `false_positive`, `validated`, `confirmed`, `inconclusive`.
- **Allowed Publication States**: `none`, `draft`, `submitted`, `published`.

---

### 2. Provenance Sidecar Schema (`schemas/provenance.schema.json`)

Validates `<product>.provenance.json` sidecars in `data/raw/`. Requires `source_uri`, `download_timestamp_utc`, 64-character hex `sha256`, and `fetched_by`.

---

### 3. Claim Assertion Schema (`schemas/claim.schema.json`)

Validates scientific assertion files under `candidate/<id>/claims/*.json`.

```json
{
  "parameter": "fpp",
  "value": 0.0025,
  "uncertainty_upper": 0.0005,
  "uncertainty_lower": 0.0005,
  "unit": "dimensionless",
  "method": "TRICERATOPS v1.0.20"
}
```

Supported parameters: `period_days`, `radius_earth`, `mass_earth`, `fpp`.

---

## Reproducibility Freeze Engine

Executing `exonym freeze <id>` packages all code dependencies, target identity records, and manifests into `candidate/<id>/releases/<version>/`:

```
candidate/candidate-alpha/releases/release-v1.0/
├── requirements.lock.txt   # Pinned Python package dependencies
├── environment.lock.yml    # Conda environment manifest
├── Dockerfile              # Containerization instructions (Python 3.9-slim)
├── Apptainer.def           # HPC Singularity definition file
└── manifest.json           # Content-addressed manifest with SHA-256 checksums
```

`manifest.json` snippet:

```json
{
  "schema": "exonym-freeze-1",
  "version": "release-v1.0",
  "candidate_id": "candidate-alpha",
  "frozen_at": "2026-08-04T12:00:00Z",
  "git_commit": "a1b2c3d4e5f6...",
  "candidate_json_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "files": [
    {
      "path": "Dockerfile",
      "sha256": "...",
      "size_bytes": 284
    }
  ]
}
```

---

## End-to-End Walkthrough

Here is a complete workflow demonstrating candidate provisioning through publication freeze:

### Step 1: Initialize Candidate Workspace

```powershell
exonym init candidate-demo --toi <toi> --tic <tic> --mission tess --tag target-high-priority
```

### Step 2: Download & Ingest SPOC Data

```powershell
exonym ingest candidate-demo --sectors 14 15 16 --exptime 120
```

### Step 3: Complete Gate Checklists

Mark all `[MANDATORY]` checkboxes in `candidate/candidate-demo/docs/01_intake_manifest.md` and `docs/02_feasibility_report.md`.

### Step 4: Advance Through Workflow Gates

```powershell
exonym advance candidate-demo  # Promotes intake -> feasibility
exonym advance candidate-demo  # Promotes feasibility -> acquisition
exonym advance candidate-demo  # Promotes acquisition -> vetting
```

### Step 5: Record Scientific Claim Assertion

Create `candidate/candidate-demo/claims/fpp_assertion.json`:

```json
{
  "parameter": "fpp",
  "value": 0.0042,
  "uncertainty_upper": 0.0010,
  "uncertainty_lower": 0.0010,
  "unit": "dimensionless",
  "method": "TRICERATOPS screening"
}
```

### Step 6: Advance through Analysis & Review

```powershell
exonym advance candidate-demo  # Promotes vetting -> followup
exonym advance candidate-demo  # Promotes followup -> analysis (verifies claims/ FPP < 0.01)
exonym advance candidate-demo  # Promotes analysis -> review (locks lifecycle to published)
```

### Step 7: Freeze Reproducible Package

```powershell
exonym freeze candidate-demo --version v1.0.0
```

---

## Development & Testing

### Running Tests

Execute the shared test suite:

```powershell
python -m pytest
```

Shared unit tests utilize synthetic fixtures. Target-specific unit tests live inside `candidate/<id>/tests/` and run separately.

> **Testing Cadence Policy**: To prevent unnecessary operational red tape, automated test execution (`pytest`) is skipped for non-code tasks where no Python files (`src/`, `tests/`) were modified. As a manuscript or target campaign takes shape as a draft, test execution frequency increases to ensure full baseline stability.

### Running Isolation Verification Audit

Verify that zero target-specific data or identifiers leak outside `candidate/`:

```powershell
exonym verify
```

---

## Governance & Policy

- **`CONTRIBUTING.md`**: Contribution guidelines, pull request procedures, and style rules.
- **`SECURITY.md`**: Security vulnerability reporting process.
- **`CODEOWNERS`**: Code ownership allocations across subsystems.
- **`policy/isolation-exceptions.json`**: Exception registry for isolation rules (requires formal review before addition).

---

## License

`EXONYM` is released under the **GNU General Public License v3.0**. See the [`LICENSE`](file:///d:/Exonym/LICENSE) file for details.


