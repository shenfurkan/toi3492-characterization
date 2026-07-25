# TOI-3492.01: Photometric Characterization of an Unvalidated TESS Exoplanet Candidate

This repository contains the open-source analysis code, photometric reduction pipeline, transit modeling scripts, and verification suites for the independent characterization of **TOI-3492.01** (TIC 81077799).

The analysis processes 120-second and 20-second cadence data from TESS Sectors 37, 63, 64, 90, 99, and 100 to evaluate transit parameters, residual noise properties, and false-positive scenarios.

---

## 🔭 Scientific Overview

- **Target Star:** TIC 81077799 (TOI-3492)
- **Candidate:** TOI-3492.01
- **Period:** $P \approx 9.2224171 \text{ days}$
- **TESS Sectors Analyzed:** Sectors 37, 63, 64, 90, 99, and 100
- **Primary Objectives:**
  - Independent 6-sector TESS SPOC light curve normalization and phase folding.
  - Markov Chain Monte Carlo (MCMC) transit fitting ($R_p/R_*$, $a/R_*$, impact parameter $b$, limb-darkening parameters).
  - Residual noise modeling, stationarity audits, and autocorrelation analysis.
  - False positive vetting (TRICERATOPS probability screening, Gaia DR3 neighbor dilution checks, and difference-image centroid localization).

---

## 📁 Repository Structure

```
toi3492-characterization/
├── scripts/                 # Core analysis, fitting, and data processing scripts
│   └── verification/        # Automated scientific verification checkers
├── tests/                   # Pytest test suite verifying pipeline components
├── data/                    # Protocol manifests and JSON input configurations
├── outputs/                 # Summary JSON/CSV audit outputs and execution logs
├── pyproject.toml           # Package configuration and dependencies
└── LICENSE                  # GNU General Public License v3.0 (GPL-3.0)
```

---

## ⚙️ Key Pipeline Modules

| Module | Description |
|:---|:---|
| `scripts/build_120s_reference_lightcurve.py` | Normalizes and stitches the 6-sector 120s TESS SPOC reference light curve |
| `scripts/transit_model_120s_corrected.py` | Phase-folded MCMC transit parameter fitting (`batman`, `emcee`) |
| `scripts/faz6_noise_core.py` | Correlated noise core modeling and residual stationarity auditing |
| `scripts/triceratops_validation.py` | False Positive Probability (FPP) calculation using TRICERATOPS |
| `scripts/gaia_contamination_check.py` | Gaia DR3 neighbor query and aperture dilution assessment |
| `scripts/audit_science_consistency.py` | Automated offline science consistency and claim-boundary audit |

---

## 🚀 Quick Start

### Prerequisites
- Python **3.9.x**

### Installation

```bash
# Clone repository
git clone https://github.com/shenfurkan/toi3492-characterization.git
cd toi3492-characterization

# Install package with test dependencies
pip install -e ".[test]"
```

### Running Tests and Audits

```bash
# Run pytest test suite
pytest

# Run offline scientific consistency audit
python scripts/audit_science_consistency.py
```

---

## 📜 License

This project is open-source software licensed under the **GNU General Public License v3.0 (GPLv3)**. See the [LICENSE](LICENSE) file for details.
