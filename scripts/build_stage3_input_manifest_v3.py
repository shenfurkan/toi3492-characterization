"""Build a fresh S3-01 input manifest for the v3 amendment."""

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
V2_PATH = ROOT / "data" / "stage3_input_manifest.json"
OUTPUT_PATH = ROOT / "data" / "stage3_input_manifest_v3.json"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refresh_records(value):
    if isinstance(value, list):
        return [refresh_records(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: refresh_records(item) for key, item in value.items()}
    relative = result.get("path")
    if isinstance(relative, str) and "sha256" in result and "size_bytes" in result:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        result["size_bytes"] = path.stat().st_size
        result["sha256"] = sha256(path)
    return result


def build():
    manifest = copy.deepcopy(json.loads(V2_PATH.read_text(encoding="utf-8")))
    manifest["schema_version"] = "2.0"
    manifest["work_package"] = "S3-01_V3_INPUT_MANIFEST_AMENDMENT"
    manifest["generated_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["supersedes"] = "data/stage3_input_manifest.json"
    manifest["supersedes_sha256"] = sha256(V2_PATH)
    manifest["status"] = "PASS"
    manifest["input_groups"] = refresh_records(manifest["input_groups"])
    manifest["checks"]["v3_manifest_refreshed"] = True
    return manifest


def comparable(value):
    result = copy.deepcopy(value)
    result.pop("generated_utc", None)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = build()
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.verify_only:
        stored = json.loads(OUTPUT_PATH.read_text(encoding="utf-8")) if OUTPUT_PATH.is_file() else None
        if stored is None or comparable(stored) != comparable(manifest):
            raise AssertionError("v3 input manifest is stale")
        print("STAGE-3 S3-01 v3 INPUT MANIFEST: PASS (verified)")
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError("v3 input manifest is no-clobber; use --verify-only")
    OUTPUT_PATH.write_text(encoded, encoding="utf-8")
    print("STAGE-3 S3-01 v3 INPUT MANIFEST: PASS")


if __name__ == "__main__":
    main()
