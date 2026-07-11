"""Generate a SHA-256 manifest and run metadata for the archival release."""

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = ROOT / "provenance"

REQUIRED = [
    "README.md",
    "REVIEW_NOTES.md",
    "LICENSE",
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
    "outputs/mcmc_diagnostics_120s_corrected.json",
    "outputs/false_positive_tests_120s.json",
    "outputs/gaia_contamination_check.json",
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
    "figures/toi3492_120s_reference_fold.png",
    "figures/toi3492_transit_fit_120s_corrected.png",
    "figures/toi3492_corner_120s_corrected.png",
    "figures/toi3492_false_positive_120s.png",
    "figures/toi3492_gaia_neighbors.png",
    "figures/toi3492_tess_difference_images.png",
    "figures/toi3492_20s_reference_fold.png",
    "figures/toi3492_20s_vs_120s_depth.png",
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing release artifacts: {missing}")
    PROVENANCE.mkdir(exist_ok=True)
    hashes = {name: sha256(ROOT / name) for name in REQUIRED}
    (PROVENANCE / "SHA256SUMS.json").write_text(json.dumps(hashes, indent=2))
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_review_start": commit,
        "python": sys.version,
        "platform": platform.platform(),
        "primary_mcmc_seed": 42,
        "stellar_posterior_seed": 3492,
        "publication_test_command": "python -m pytest -q",
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
