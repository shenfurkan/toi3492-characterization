"""Generate a SHA-256 manifest and run metadata for the archival release."""

import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata as importlib_metadata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = ROOT / "provenance"

REQUIRED = [
    "README.md",
    "REVIEW_NOTES.md",
    "EXOPLANET_RELEASE_ROADMAP.md",
    "LICENSE",
    "LICENSES.md",
    "CITATION.cff",
    "pyproject.toml",
    "requirements-lock.txt",
    "references.bib",
    "toi3492_characterization.tex",
    "toi3492_characterization.pdf",
    "data/official_toi_metadata.json",
    "data/config_corrected_120s.json",
    "data/toi3492_120s_reference.csv",
    "data/toi3492_20s_reference.csv",
    "data/toi3492_chains_120s_corrected.npy",
    "data/toi3492_raw_chain_120s_corrected.npy",
    "data/toi3492_chains_robust_120s.npy",
    "data/toi3492_chains_robust_20s.npy",
    "data/stellar_photometry.json",
    "data/stellar_sed_chain.npy",
    "outputs/mcmc_diagnostics_120s_corrected.json",
    "outputs/false_positive_tests_120s.json",
    "outputs/gaia_contamination_check.json",
    "outputs/gaia_dr3_neighbors.csv",
    "outputs/gaia_stellar_crosscheck.json",
    "outputs/spoc_dv_summary.json",
    "outputs/spoc_vs_local_comparison.json",
    "outputs/statistical_validation_120s.json",
    "outputs/transit_fit_120s_eccentric.json",
    "outputs/transit_stability_checks.json",
    "outputs/toi3492_120s_sector_depths.csv",
    "outputs/cadence_independent_depth_check.json",
    "outputs/alias_20s_results.json",
    "outputs/toi3492_20s_sector_depths.csv",
    "outputs/tess_source_localization_120s.json",
    "outputs/toi3492_120s_difference_centroids.csv",
    "outputs/asteroseismic_input_inventory.json",
    "outputs/asteroseismic_feasibility.json",
    "outputs/asteroseismic_preliminary_search.json",
    "outputs/asteroseismic_injection_recovery.json",
    "outputs/asteroseismic_pysyd_crosscheck.json",
    "outputs/transit_fit_robust_120s.json",
    "outputs/transit_fit_robust_20s.json",
    "outputs/robust_density_comparison.json",
    "outputs/phase_curve_search_120s.json",
    "outputs/source_specific_aperture_check.json",
    "outputs/stellar_sed_posterior.json",
    "outputs/dilution_corrected_transit_params.json",
    "outputs/dilution_worst_case_scenarios.json",
    "outputs/dilution_summary_120s.csv",
    "outputs/release_status.json",
    "provenance/environment.json",
    "figures/toi3492_120s_reference_fold.png",
    "figures/toi3492_transit_fit_120s_corrected.png",
    "figures/toi3492_corner_120s_corrected.png",
    "figures/toi3492_false_positive_120s.png",
    "figures/toi3492_gaia_neighbors.png",
    "figures/toi3492_tess_difference_images.png",
    "figures/toi3492_20s_reference_fold.png",
    "figures/toi3492_20s_vs_120s_depth.png",
    "figures/toi3492_asteroseismic_preliminary.png",
    "figures/toi3492_dilution_robustness.png",
]

# The release claims full reproducibility, so freeze every Python pipeline and
# its executable tests rather than only the generated scientific artifacts.
REQUIRED.extend(
    sorted(
        str(path.relative_to(ROOT)).replace("\\", "/")
        for directory in (ROOT / "scripts", ROOT / "tests")
        for path in directory.glob("*.py")
    )
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    PROVENANCE.mkdir(exist_ok=True)
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "installed_distributions": {
            dist.metadata["Name"]: dist.version
            for dist in sorted(
                importlib_metadata.distributions(),
                key=lambda item: (item.metadata["Name"] or "").lower(),
            )
            if dist.metadata["Name"]
        },
        "reproducibility_note": "Package versions describe the review machine; stochastic numerical equivalence is assessed by scientific tolerances, not guaranteed byte identity.",
    }
    (PROVENANCE / "environment.json").write_text(json.dumps(environment, indent=2))
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing release artifacts: {missing}")
    hashes = {name: sha256(ROOT / name) for name in REQUIRED}
    (PROVENANCE / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2))
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    git_status = subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_review_start": commit,
        "git_worktree_dirty": bool(git_status),
        "git_status_short": git_status,
        "source_state_note": "The release ZIP is the authoritative dirty-worktree source snapshot; every declared source is hashed even when ignored or untracked by Git.",
        "python": sys.version,
        "platform": platform.platform(),
        "primary_mcmc_seed": 42,
        "stellar_posterior_seed": 3492,
        "publication_test_command": "python -m pytest -q",
        "raw_integration_test_command": "python -m pytest -q -m integration -o addopts=\"\"",
        "environment_file": "provenance/environment.json",
        "input_hashes": {
            key: value
            for key, value in hashes.items()
            if key.startswith("data/")
        },
    }
    (PROVENANCE / "run.json").write_text(json.dumps(metadata, indent=2))
    print(f"Wrote {PROVENANCE / 'SHA256SUMS.json'}")
    print(f"Wrote {PROVENANCE / 'run.json'}")


if __name__ == "__main__":
    main()
