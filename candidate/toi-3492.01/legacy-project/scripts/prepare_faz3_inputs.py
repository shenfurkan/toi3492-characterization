"""Prepare the external inputs for the Faz 3 systematics audit.

The download set is deliberately bounded to one official SPOC CBV file and
one 120-s SPOC control-star light curve for each target sector.  CBV URLs are
selected from the STScI sector curl scripts using the camera/CCD recorded by
Faz 1.  Existing files are reused only after their prior hash (when available)
and FITS headers validate.
"""

import hashlib
import json
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from astropy.coordinates import SkyCoord
from astropy.io import fits
import astropy.units as u
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


ROOT = Path(__file__).resolve().parent.parent
FAZ1_PATH = ROOT / "outputs" / "faz1_product_inventory.json"
OUTPUT_PATH = ROOT / "outputs" / "faz3_input_inventory.json"
CBV_DIR = ROOT / "data" / "faz3" / "cbv"
CONTROL_DIR = ROOT / "data" / "faz3" / "control_tic81400324"

TARGET_TIC = 81077799
TARGET_TMAG = 8.4504
CONTROL_TIC = 81400324
CONTROL_TMAG = 9.1105
SECTORS = (37, 63, 64, 90, 99, 100)
MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
REQUEST_TIMEOUT = (30, 180)
CBV_SCRIPT_TEMPLATE = (
    "https://archive.stsci.edu/missions/tess/download_scripts/sector/"
    "tesscurl_sector_{sector}_cbv.sh"
)
MAST_DOWNLOAD = "https://mast.stsci.edu/api/v0.1/Download/file?"

LC_REQUIRED_COLUMNS = {
    "TIME",
    "CADENCENO",
    "PDCSAP_FLUX",
    "PDCSAP_FLUX_ERR",
    "SAP_FLUX",
    "SAP_FLUX_ERR",
    "SAP_BKG",
    "QUALITY",
    "POS_CORR1",
    "POS_CORR2",
    "MOM_CENTR1",
    "MOM_CENTR2",
}


def relative(path):
    return str(path.relative_to(ROOT)).replace("\\", "/")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def request_session():
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    session.headers["User-Agent"] = "TOI-3492-Faz3-input-preparation/1"
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def download(session, url, destination):
    temporary = destination.with_suffix(destination.suffix + ".part")
    if temporary.exists():
        temporary.unlink()
    try:
        with session.get(url, stream=True, timeout=REQUEST_TIMEOUT) as response:
            response.raise_for_status()
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > MAX_DOWNLOAD_BYTES:
                raise RuntimeError(
                    f"Refusing oversized download ({declared} bytes): {url}"
                )
            size = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=CHUNK_BYTES):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError(f"Download exceeded size bound: {url}")
                    handle.write(chunk)
        if size == 0:
            raise RuntimeError(f"Empty download: {url}")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def target_products(faz1):
    if faz1.get("gate_pass") is not True:
        raise RuntimeError("Faz 1 gate is not PASS")
    products = {}
    for item in faz1["products"]:
        if item["product_type"] != "lc" or item["cadence_seconds"] != 120:
            continue
        sector = int(item["sector"])
        if sector not in SECTORS:
            continue
        path = ROOT / item["relative_path"]
        if not path.is_file() or sha256_file(path) != item["actual_sha256"]:
            raise RuntimeError(f"Active target LC failed Faz 1 hash check: {path}")
        products[sector] = item
    if tuple(sorted(products)) != SECTORS:
        raise RuntimeError(f"Expected target sectors {SECTORS}, found {sorted(products)}")
    return products


def read_target_identity(products):
    values = []
    for sector in SECTORS:
        path = ROOT / products[sector]["relative_path"]
        with fits.open(path, mode="readonly", memmap=True) as hdul:
            header = hdul[0].header
            values.append(
                (
                    int(header["TICID"]),
                    float(header["RA_OBJ"]),
                    float(header["DEC_OBJ"]),
                    float(header["TESSMAG"]),
                )
            )
    if any(value[0] != TARGET_TIC for value in values):
        raise RuntimeError("Target FITS TIC identity is inconsistent")
    coordinates = np.asarray([[value[1], value[2]] for value in values])
    magnitudes = np.asarray([value[3] for value in values])
    if np.ptp(coordinates, axis=0).max() > 1e-8 or np.ptp(magnitudes) > 1e-5:
        raise RuntimeError("Target FITS coordinates or TESS magnitudes are inconsistent")
    if abs(float(magnitudes[0]) - TARGET_TMAG) > 1e-3:
        raise RuntimeError("Target FITS TESS magnitude does not match preregistration")
    return {
        "tic_id": TARGET_TIC,
        "ra_deg": float(coordinates[0, 0]),
        "dec_deg": float(coordinates[0, 1]),
        "tmag": float(magnitudes[0]),
    }


def cbv_metadata(path, sector, camera, ccd):
    with fits.open(path, mode="readonly", memmap=True) as hdul:
        primary = hdul[0].header
        if int(primary.get("SECTOR", -1)) != sector:
            raise ValueError("CBV sector mismatch")
        extension_names = [str(hdu.header.get("EXTNAME", "")) for hdu in hdul]
        matches = []
        scale_extensions = []
        for index, hdu in enumerate(hdul[1:], start=1):
            name = str(hdu.header.get("EXTNAME", ""))
            lower = name.lower()
            if "cbv." in lower:
                scale_extensions.append(name)
            if (
                "single-scale" in lower
                and int(hdu.header.get("CAMERA", -1)) == camera
                and int(hdu.header.get("CCD", -1)) == ccd
            ):
                matches.append((index, hdu))
        if len(matches) != 1:
            raise ValueError(
                f"Expected one SingleScale extension for {camera}-{ccd}, found {len(matches)}"
            )
        index, hdu = matches[0]
        columns = list(hdu.columns.names)
        vector_columns = [
            name for name in columns if re.fullmatch(r"VECTOR_\d+", str(name))
        ]
        if "CADENCENO" not in columns or "TIME" not in columns:
            raise ValueError("CBV SingleScale extension lacks cadence keys")
        if len(vector_columns) < 8:
            raise ValueError("CBV SingleScale extension has fewer than eight vectors")
        if len(scale_extensions) < 2:
            raise ValueError("CBV FITS does not preserve the available scale extensions")
        return {
            "sector": sector,
            "camera": camera,
            "ccd": ccd,
            "data_release": int(primary.get("DATA_REL", -1)),
            "pipeline_version": str(primary.get("PROCVER", "")),
            "hdu_names": extension_names,
            "scale_extensions": scale_extensions,
            "single_scale_hdu_index": index,
            "single_scale_extension": str(hdu.header.get("EXTNAME", "")),
            "single_scale_row_count": int(hdu.header.get("NAXIS2", len(hdu.data))),
            "single_scale_vector_count": len(vector_columns),
            "single_scale_vector_columns": vector_columns,
        }


def control_metadata(path, sector, camera, ccd):
    with fits.open(path, mode="readonly", memmap=True) as hdul:
        primary = hdul[0].header
        table = hdul[1]
        columns = set(table.columns.names)
        missing = sorted(LC_REQUIRED_COLUMNS - columns)
        timedel_seconds = float(table.header.get("TIMEDEL", np.nan)) * 86400.0
        checks = {
            "tic_id": int(primary.get("TICID", -1)) == CONTROL_TIC,
            "sector": int(primary.get("SECTOR", -1)) == sector,
            "camera": int(primary.get("CAMERA", -1)) == camera,
            "ccd": int(primary.get("CCD", -1)) == ccd,
            "cadence_120s": np.isfinite(timedel_seconds)
            and abs(timedel_seconds - 120.0) < 1e-6,
            "tmag": abs(float(primary.get("TESSMAG", np.nan)) - CONTROL_TMAG) < 1e-3,
            "required_columns": not missing,
        }
        if not all(checks.values()):
            raise ValueError(f"Control LC validation failed: {checks}; missing={missing}")
        return {
            "tic_id": int(primary["TICID"]),
            "sector": int(primary["SECTOR"]),
            "camera": int(primary["CAMERA"]),
            "ccd": int(primary["CCD"]),
            "cadence_seconds": timedel_seconds,
            "tmag": float(primary["TESSMAG"]),
            "ra_deg": float(primary["RA_OBJ"]),
            "dec_deg": float(primary["DEC_OBJ"]),
            "data_release": int(primary.get("DATA_REL", -1)),
            "pipeline_version": str(primary.get("PROCVER", "")),
            "row_count": int(table.header.get("NAXIS2", len(table.data))),
            "required_columns": sorted(LC_REQUIRED_COLUMNS),
            "validation_checks": checks,
        }


def prior_products(prior, kind):
    if not prior:
        return {}
    return {int(item["sector"]): item for item in prior.get(kind, [])}


def valid_existing(path, expected_hash, validator):
    if not path.is_file():
        return None
    actual_hash = sha256_file(path)
    if expected_hash is not None and actual_hash != expected_hash:
        return None
    try:
        metadata = validator(path)
    except (OSError, KeyError, TypeError, ValueError):
        return None
    return actual_hash, metadata


def select_cbv_url(script_text, sector, camera, ccd):
    pattern = re.compile(
        rf"https://[^\s]+/s{sector:04d}/[^\s]+/{camera}-{ccd}/"
        rf"tess[^\s]+-s{sector:04d}-{camera}-{ccd}-[^\s]+-s_cbv\.fits"
    )
    matches = sorted(set(pattern.findall(script_text)))
    if len(matches) != 1:
        raise RuntimeError(
            f"Curl script yielded {len(matches)} CBVs for S{sector} camera/CCD {camera}-{ccd}"
        )
    return matches[0]


def control_product(target_product):
    filename = target_product["product_id"]
    target_token = f"{TARGET_TIC:016d}"
    control_token = f"{CONTROL_TIC:016d}"
    if target_token not in filename:
        raise RuntimeError(f"Target TIC token absent from product name: {filename}")
    filename = filename.replace(target_token, control_token, 1)
    data_uri = f"mast:TESS/product/{filename}"
    url = MAST_DOWNLOAD + urllib.parse.urlencode({"uri": data_uri})
    return filename, data_uri, url


def main():
    faz1 = json.loads(FAZ1_PATH.read_text(encoding="utf-8"))
    target = target_products(faz1)
    target_identity = read_target_identity(target)
    prior = None
    if OUTPUT_PATH.is_file():
        prior = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    prior_cbv = prior_products(prior, "cbv_products")
    prior_control = prior_products(prior, "control_products")

    CBV_DIR.mkdir(parents=True, exist_ok=True)
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    session = request_session()
    network_requests = []
    cbv_inventory = []
    control_inventory = []

    for sector in SECTORS:
        metadata = target[sector]["metadata"]
        camera = int(metadata["camera"])
        ccd = int(metadata["ccd"])
        previous = prior_cbv.get(sector, {})
        previous_path = ROOT / previous.get("relative_path", "__missing__")
        validation = None
        if previous:
            validation = valid_existing(
                previous_path,
                previous.get("sha256"),
                lambda path, s=sector, c=camera, d=ccd: cbv_metadata(path, s, c, d),
            )
        if validation is not None:
            path = previous_path
            cbv_url = previous["url"]
            script_url = previous["curl_script_url"]
            state = "reused_hash_and_header_validated"
            digest, fits_info = validation
        else:
            script_url = CBV_SCRIPT_TEMPLATE.format(sector=sector)
            try:
                response = session.get(script_url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Cannot resolve official CBV for sector {sector}: {exc}"
                ) from exc
            network_requests.append(script_url)
            cbv_url = select_cbv_url(response.text, sector, camera, ccd)
            path = CBV_DIR / cbv_url.rsplit("/", 1)[-1]
            local_validation = valid_existing(
                path,
                previous.get("sha256") if previous else None,
                lambda candidate, s=sector, c=camera, d=ccd: cbv_metadata(
                    candidate, s, c, d
                ),
            )
            if local_validation is None:
                try:
                    download(session, cbv_url, path)
                    network_requests.append(cbv_url)
                    fits_info = cbv_metadata(path, sector, camera, ccd)
                except (requests.RequestException, OSError, ValueError) as exc:
                    raise RuntimeError(
                        f"Official CBV preparation failed for sector {sector}: {exc}"
                    ) from exc
                digest = sha256_file(path)
                state = "downloaded"
            else:
                digest, fits_info = local_validation
                state = "reused_header_validated"
        cbv_inventory.append(
            {
                "sector": sector,
                "camera": camera,
                "ccd": ccd,
                "curl_script_url": script_url,
                "url": cbv_url,
                "relative_path": relative(path),
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "state": state,
                "fits": fits_info,
            }
        )
        print(f"S{sector:03d} CBV: {state} {path.name}")

        filename, data_uri, url = control_product(target[sector])
        control_path = CONTROL_DIR / filename
        previous = prior_control.get(sector, {})
        validation = valid_existing(
            control_path,
            previous.get("sha256") if previous else None,
            lambda candidate, s=sector, c=camera, d=ccd: control_metadata(
                candidate, s, c, d
            ),
        )
        if validation is None:
            try:
                download(session, url, control_path)
                network_requests.append(url)
                control_info = control_metadata(control_path, sector, camera, ccd)
            except (requests.RequestException, OSError, ValueError) as exc:
                raise RuntimeError(
                    f"Control TIC {CONTROL_TIC} preparation failed for sector {sector}: {exc}"
                ) from exc
            control_hash = sha256_file(control_path)
            control_state = "downloaded"
        else:
            control_hash, control_info = validation
            control_state = (
                "reused_hash_and_header_validated"
                if previous
                else "reused_header_validated"
            )
        control_inventory.append(
            {
                "tic_id": CONTROL_TIC,
                "sector": sector,
                "camera": camera,
                "ccd": ccd,
                "cadence_seconds": 120,
                "product_id": filename,
                "dataURI": data_uri,
                "url": url,
                "relative_path": relative(control_path),
                "size_bytes": control_path.stat().st_size,
                "sha256": control_hash,
                "state": control_state,
                "fits": control_info,
            }
        )
        print(f"S{sector:03d} control: {control_state} {filename}")

    control_coordinates = np.asarray(
        [[item["fits"]["ra_deg"], item["fits"]["dec_deg"]] for item in control_inventory]
    )
    control_magnitudes = np.asarray([item["fits"]["tmag"] for item in control_inventory])
    if np.ptp(control_coordinates, axis=0).max() > 1e-8:
        raise RuntimeError("Control-star coordinates differ between sectors")
    if np.ptp(control_magnitudes) > 1e-5:
        raise RuntimeError("Control-star TESS magnitudes differ between sectors")
    target_coord = SkyCoord(
        target_identity["ra_deg"] * u.deg, target_identity["dec_deg"] * u.deg
    )
    control_coord = SkyCoord(
        control_coordinates[0, 0] * u.deg, control_coordinates[0, 1] * u.deg
    )
    separation = target_coord.separation(control_coord)
    magnitude_difference = float(control_magnitudes[0] - target_identity["tmag"])

    checks = {
        "faz1_gate_pass": faz1.get("gate_pass") is True,
        "exactly_six_cbv_products": len(cbv_inventory) == 6,
        "one_cbv_per_sector": sorted(item["sector"] for item in cbv_inventory)
        == list(SECTORS),
        "all_cbv_headers_match_target_detector": all(
            item["fits"]["camera"] == item["camera"]
            and item["fits"]["ccd"] == item["ccd"]
            for item in cbv_inventory
        ),
        "all_cbv_files_contain_multiple_scales": all(
            len(item["fits"]["scale_extensions"]) >= 2 for item in cbv_inventory
        ),
        "exactly_six_control_products": len(control_inventory) == 6,
        "control_is_not_target": all(
            item["fits"]["tic_id"] == CONTROL_TIC != TARGET_TIC
            for item in control_inventory
        ),
        "control_120s_all_sectors": all(
            abs(item["fits"]["cadence_seconds"] - 120.0) < 1e-6
            for item in control_inventory
        ),
        "control_camera_ccd_matches_target": all(
            item["fits"]["camera"] == item["camera"]
            and item["fits"]["ccd"] == item["ccd"]
            for item in control_inventory
        ),
        "control_tmag_matches_preregistration": abs(
            float(control_magnitudes[0]) - CONTROL_TMAG
        )
        < 1e-3,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Faz 3 input gate failed: {checks}")

    payload = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "input_policy": {
            "bounded_sectors": list(SECTORS),
            "cbv_source": "STScI sector curl scripts; exact target camera/CCD only",
            "control_source": "exact SPOC 120-s MAST products paired to active target product IDs",
            "legacy_zip_inspected": False,
            "target_data_substituted_for_control": False,
            "network_used": bool(network_requests),
            "network_request_count": len(network_requests),
            "network_requests": network_requests,
            "failure_policy": "network or validation failure raises and no successful inventory is published",
        },
        "target": target_identity,
        "control": {
            "tic_id": CONTROL_TIC,
            "preregistered_tmag": CONTROL_TMAG,
            "measured_header_tmag": float(control_magnitudes[0]),
            "ra_deg": float(control_coordinates[0, 0]),
            "dec_deg": float(control_coordinates[0, 1]),
            "magnitude_difference_control_minus_target": magnitude_difference,
            "angular_separation_deg": float(separation.deg),
            "angular_separation_arcmin": float(separation.arcminute),
            "angular_separation_arcsec": float(separation.arcsecond),
        },
        "cbv_products": cbv_inventory,
        "control_products": control_inventory,
        "gate": {"checks": checks, "gate_pass": all(checks.values())},
        "gate_pass": all(checks.values()),
    }
    temporary = OUTPUT_PATH.with_suffix(OUTPUT_PATH.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    temporary.replace(OUTPUT_PATH)
    print(
        f"Control separation={separation.arcminute:.4f} arcmin, "
        f"delta Tmag={magnitude_difference:+.4f}"
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
