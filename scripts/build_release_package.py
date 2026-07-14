"""Create the full reproducible Zenodo-ready release archive."""

import hashlib
import json
import subprocess
import sys
import tempfile
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
    archive = ROOT / "toi3492_reproducible_release_v1.0.1.zip"
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
        names = packaged.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("Release ZIP contains duplicate paths")
        for name in names:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError(f"Unsafe ZIP path: {name}")
        bad_entry = packaged.testzip()
        if bad_entry is not None:
            raise RuntimeError(f"ZIP CRC failure: {bad_entry}")
        embedded = json.loads(
            packaged.read("provenance/SHA256SUMS.json").decode("utf-8")
        )
        if embedded != files:
            raise RuntimeError("Embedded release manifest differs from source manifest")
        for relative, expected_hash in embedded.items():
            actual_hash = hashlib.sha256(packaged.read(relative)).hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(f"ZIP hash mismatch for {relative}")
        with tempfile.TemporaryDirectory(prefix="toi3492-release-") as temporary:
            extracted = Path(temporary)
            packaged.extractall(extracted)
            subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=extracted,
                check=True,
                timeout=240,
            )
    archive_hash = sha256(archive)
    sidecar = archive.with_suffix(archive.suffix + ".sha256")
    sidecar.write_text(f"{archive_hash}  {archive.name}\n")
    print(f"Wrote {archive}")
    print(f"Wrote {sidecar}")


if __name__ == "__main__":
    main()
