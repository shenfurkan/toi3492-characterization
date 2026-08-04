"""File tree snapshot hashing and provenance tracking."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

EXCLUDED_SNAPSHOT_PATHS = {
    "outputs/final_calculation_verification_report.json",
    "outputs/final_calculation_verification.log",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_snapshot() -> tuple[dict[str, str], str]:
    """Capture sha256 checksums of all file assets in data, outputs, and scripts."""
    entries: dict[str, str] = {}
    for directory in (ROOT / "data", ROOT / "outputs", ROOT / "scripts"):
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in EXCLUDED_SNAPSHOT_PATHS or "__pycache__" in relative:
                continue
            entries[relative] = _sha256(path)
    digest = hashlib.sha256()
    for relative, value in entries.items():
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return entries, digest.hexdigest()
