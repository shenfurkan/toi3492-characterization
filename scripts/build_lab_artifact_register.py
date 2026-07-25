"""Build a machine-readable inventory of repository artifacts and ownership paths."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "outputs" / "lab_artifact_register.json"
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "papers",
    "literature",
    "AstrophysicsResources",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return {line.replace("\\", "/") for line in result.stdout.splitlines() if line}


def classification(relative: str) -> tuple[str, str, bool]:
    path = Path(relative)
    parts = path.parts
    if relative.endswith(".zip.sha256"):
        return "release_receipt", "release_receipt", False
    if relative.endswith(".backup") or "backup" in path.name:
        return "historical_backup", "provenance_only", False
    if parts and parts[0] in {"papers", "literature", "AstrophysicsResources"}:
        return "reference_material", "external_only", False
    if parts and parts[0] == "data":
        if "asteroseismology" in parts or "spoc_dv" in parts or relative.endswith(".fits"):
            return "external_raw_input", "external_archive", False
        return "compact_scientific_input", "release_required", True
    if parts and parts[0] == "outputs":
        return "derived_result_or_gate", "release_required", True
    if parts and parts[0] in {"scripts", "tests", "docs", ".github"}:
        return "source_or_operational_record", "release_required", True
    if relative.startswith("provenance/"):
        return "provenance_record", "release_required", True
    if path.suffix in {".png", ".pdf"}:
        return "publication_figure_or_pdf", "release_required", True
    return "root_metadata_or_document", "release_required", True


def main() -> None:
    tracked = git_lines("ls-files")
    status = git_lines("status", "--short", "--untracked-files=all")
    ignored_result = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    ignored = {line.replace("\\", "/") for line in ignored_result.stdout.splitlines() if line}
    manifest_path = ROOT / "provenance" / "SHA256SUMS.json"
    release_manifest = (
        set(json.loads(manifest_path.read_text(encoding="utf-8")))
        if manifest_path.is_file()
        else set()
    )

    records = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(part in EXCLUDED_DIRS for part in path.relative_to(ROOT).parts):
            continue
        category, disposition, release_required = classification(relative)
        records.append(
            {
                "path": relative,
                "category": category,
                "disposition": disposition,
                "release_required": release_required,
                "tracked_by_git": relative in tracked,
                "modified_or_untracked": any(
                    line[3:].replace("\\", "/") == relative
                    or line[3:].replace("\\", "/").endswith(" -> " + relative)
                    for line in status
                ),
                "ignored_by_git": relative in ignored,
                "covered_by_current_release_manifest": relative in release_manifest,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    records.sort(key=lambda record: record["path"])
    release_required = [record for record in records if record["release_required"]]
    unresolved = [
        record["path"]
        for record in release_required
        if not record["tracked_by_git"]
        and not record["ignored_by_git"]
        and not record["covered_by_current_release_manifest"]
    ]
    output = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Repository artifact ownership and release coverage inventory",
        "source_of_scientific_values": False,
        "summary": {
            "total_files": len(records),
            "release_required_files": len(release_required),
            "git_tracked_files": sum(record["tracked_by_git"] for record in records),
            "ignored_files": sum(record["ignored_by_git"] for record in records),
            "release_required_not_tracked_or_ignored": len(unresolved),
        },
        "unresolved_release_coverage": unresolved,
        "records": records,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
