"""Build a recursive, policy-driven release inventory without packaging files."""

from __future__ import annotations

import fnmatch
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "data" / "release_manifest_policy.json"
OUTPUT = ROOT / "provenance" / "RECURSIVE_RELEASE_MANIFEST.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.lstrip("./"))


def is_included(path: str, include: list[str]) -> bool:
    return any(path == item or path.startswith(item.rstrip("/") + "/") for item in include)


def status_for(path: str, policy: dict) -> str:
    if any(matches(path, pattern) for pattern in policy["historical_only"]):
        return "historical"
    if any(matches(path, pattern) for pattern in policy["external_only"]):
        return "external_only"
    return "release_required"


def main() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    records = []
    excluded = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        if not is_included(relative, policy["include"]):
            continue
        status = status_for(relative, policy)
        if status != "historical" and any(
                matches(relative, pattern) for pattern in policy["exclude_globs"]):
            excluded.append(relative)
            continue
        records.append(
            {
                "path": relative,
                "status": status,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    records.sort(key=lambda item: item["path"])
    output = {
        "schema_version": "1.0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "policy": "data/release_manifest_policy.json",
        "release_authorized": False,
        "summary": {
            "included_records": len(records),
            "release_required_records": sum(item["status"] == "release_required" for item in records),
            "external_only_records": sum(item["status"] == "external_only" for item in records),
            "historical_records": sum(item["status"] == "historical" for item in records),
            "excluded_records": len(excluded),
        },
        "records": records,
        "excluded_paths": sorted(excluded),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(json.dumps(output["summary"], indent=2))


if __name__ == "__main__":
    main()
