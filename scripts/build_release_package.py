"""Create the full reproducible Zenodo-ready release archive."""

import hashlib
import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    manifest_path = ROOT / "provenance" / "SHA256SUMS.json"
    run_path = ROOT / "provenance" / "run.json"
    if not manifest_path.is_file() or not run_path.is_file():
        raise FileNotFoundError(
            "Run scripts/generate_release_manifest.py before packaging"
        )
    files = json.loads(manifest_path.read_text())
    archive = ROOT / "toi3492_reproducible_release_v1.0.0.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for relative, expected_hash in files.items():
            path = ROOT / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            actual_hash = sha256(path)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Manifest hash mismatch for {relative}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            output.write(path, relative)
        output.write(manifest_path, "provenance/SHA256SUMS.json")
        output.write(run_path, "provenance/run.json")
    with zipfile.ZipFile(archive) as packaged:
        embedded = json.loads(
            packaged.read("provenance/SHA256SUMS.json").decode("utf-8")
        )
        if embedded != files:
            raise RuntimeError("Embedded release manifest differs from source manifest")
        for relative, expected_hash in embedded.items():
            actual_hash = hashlib.sha256(packaged.read(relative)).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(f"ZIP hash mismatch for {relative}")
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()
