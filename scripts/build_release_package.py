"""Create the full reproducible Zenodo-ready release archive."""

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


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
            output.write(path, relative)
        output.write(manifest_path, "provenance/SHA256SUMS.json")
        output.write(run_path, "provenance/run.json")
    print(f"Wrote {archive}")


if __name__ == "__main__":
    main()
