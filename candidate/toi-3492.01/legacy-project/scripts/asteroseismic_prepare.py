"""Freeze original SPOC products for the TOI-3492 asteroseismic search.

The downloaded FITS files are intentionally ignored by Git. Their MAST URIs,
selected header metadata, sizes, and SHA-256 hashes are written to a tracked
JSON inventory so the inputs can be retrieved and verified independently.
"""

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import lightkurve as lk
import numpy as np
from astropy.io import fits


ROOT = Path(__file__).resolve().parent.parent
TARGET = "TIC 81077799"
TIC_ID = 81077799
SECTORS = {37, 63, 64, 90, 99, 100}
CADENCES = {20, 120}
RAW_DIR = ROOT / "data" / "asteroseismology" / "raw"
OUT_INVENTORY = ROOT / "outputs" / "asteroseismic_input_inventory.json"
MAST_DOWNLOAD = "https://mast.stsci.edu/api/v0.1/Download/file?"


def parse_sector(mission):
    match = re.search(r"Sector\s+(\d+)", str(mission))
    return int(match.group(1)) if match else -1


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(uri, destination):
    if destination.is_file():
        return False
    url = MAST_DOWNLOAD + urllib.parse.urlencode({"uri": uri})
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            with temporary.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def fits_metadata(path):
    with fits.open(path, memmap=True) as hdul:
        primary = hdul[0].header
        table = hdul[1].header if len(hdul) > 1 else {}
        return {
            "sector": int(primary.get("SECTOR", -1)),
            "camera": int(primary.get("CAMERA", -1)),
            "ccd": int(primary.get("CCD", -1)),
            "data_rel": int(primary.get("DATA_REL", -1)),
            "procver": str(primary.get("PROCVER", "")),
            "timesys": str(table.get("TIMESYS", primary.get("TIMESYS", ""))),
            "bjdrefi": int(table.get("BJDREFI", primary.get("BJDREFI", 0))),
            "bjdreff": float(table.get("BJDREFF", primary.get("BJDREFF", 0.0))),
            "crowdsap": _finite_or_none(table.get("CROWDSAP")),
            "flfrcsap": _finite_or_none(table.get("FLFRCSAP")),
            "timedel_days": _finite_or_none(table.get("TIMEDEL")),
            "naxis2": int(table.get("NAXIS2", 0)),
        }


def _finite_or_none(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def selected_products(include_tpf):
    searches = [("lc", lk.search_lightcurve(TARGET, mission="TESS", author="SPOC"))]
    if include_tpf:
        searches.append(
            ("tpf", lk.search_targetpixelfile(TARGET, mission="TESS", author="SPOC"))
        )

    products = []
    for product_type, search in searches:
        for row in search.table:
            sector = parse_sector(row.get("mission", ""))
            exptime = int(round(float(row.get("exptime", np.nan))))
            if sector not in SECTORS or exptime not in CADENCES:
                continue
            products.append(
                {
                    "product_type": product_type,
                    "sector": sector,
                    "cadence_seconds": exptime,
                    "filename": str(row["productFilename"]),
                    "mast_uri": str(row["dataURI"]),
                }
            )
    return sorted(
        products,
        key=lambda item: (
            item["product_type"],
            item["sector"],
            item["cadence_seconds"],
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-tpf",
        action="store_true",
        help="Also download target-pixel FITS products (substantially larger)",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_INVENTORY.parent.mkdir(parents=True, exist_ok=True)

    products = selected_products(args.include_tpf)
    expected = 18 if args.include_tpf else 9
    if len(products) != expected:
        raise RuntimeError(f"Expected {expected} products, found {len(products)}")

    inventory = []
    for index, product in enumerate(products, start=1):
        path = RAW_DIR / product["filename"]
        state = "downloaded" if download(product["mast_uri"], path) else "existing"
        print(f"[{index}/{len(products)}] {state}: {path.name}")
        inventory.append(
            {
                **product,
                "relative_path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "fits": fits_metadata(path),
            }
        )

    payload = {
        "target": TARGET,
        "tic_id": TIC_ID,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "query": "TESS SPOC light curves and target-pixel files",
        "includes_tpf": args.include_tpf,
        "products": inventory,
    }
    OUT_INVENTORY.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    print(f"Wrote {OUT_INVENTORY} with {len(inventory)} products")


if __name__ == "__main__":
    main()
