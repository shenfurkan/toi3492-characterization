"""Multi-mission catalog identifier parsing and provenance sidecar generation.

Identifier parsers support TESS (TOI/TIC), Kepler (KOI), K2 (EPIC), PLATO
(PIC), and CHEOPS target designations. The provenance generator is a pure
function so it can be unit-tested offline and reused by the ingest engine.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

MISSIONS = ("tess", "kepler", "k2", "plato", "cheops")
INGEST_FETCHER = "exonym-ingest/1.0.0"

_PATTERNS = (
    ("toi", "tess", re.compile(r"^(?:TOI)[\s._-]*(\d{1,7}(?:\.\d{1,2})?)$", re.IGNORECASE)),
    ("tic", "tess", re.compile(r"^(?:TIC)[\s._:-]*(\d{5,12})$", re.IGNORECASE)),
    ("koi", "kepler", re.compile(r"^(?:K)[\s_-]*(\d{1,7})\.(\d{1,2})$", re.IGNORECASE)),
    ("epic", "k2", re.compile(r"^(?:EPIC)[\s._-]*(\d{6,10})$", re.IGNORECASE)),
    ("pic", "plato", re.compile(r"^(?:PIC)[\s._-]*(\d{4,10})$", re.IGNORECASE)),
    ("cheops", "cheops", re.compile(r"^(?:CHEOPS)[\s._-]*([A-Za-z0-9._-]+)$", re.IGNORECASE)),
)


class IdentifierError(ValueError):
    """Raised when a catalog identifier cannot be parsed."""


def parse_identifier(identifier: str) -> Dict[str, str]:
    """Parse a mission-aware catalog identifier.

    Returns a dict with ``kind`` (toi/tic/koi/epic/pic/cheops), ``mission``,
    and ``value``. Raises :class:`IdentifierError` for unrecognized input.
    """
    text = str(identifier).strip()
    if not text:
        raise IdentifierError("empty identifier")
    for kind, mission, pattern in _PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        value = match.group(1)
        if kind == "koi":
            value = "{0}.{1}".format(match.group(1), match.group(2))
        return {"kind": kind, "mission": mission, "value": value}
    raise IdentifierError("unrecognized catalog identifier: {0}".format(identifier))


def mission_for_identifier(identifier: str) -> str:
    """Return the mission for an identifier, raising on unknown input."""
    return parse_identifier(identifier)["mission"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_provenance(
    product_path: Path,
    source_uri: str,
    fetched_by: str = INGEST_FETCHER,
    download_timestamp_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a provenance sidecar record for a downloaded product (pure)."""
    if download_timestamp_utc is None:
        download_timestamp_utc = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
    return {
        "source_uri": source_uri,
        "download_timestamp_utc": download_timestamp_utc,
        "sha256": _sha256(Path(product_path)),
        "fetched_by": fetched_by,
    }


def write_provenance_sidecar(
    product_path: Path,
    source_uri: str,
    fetched_by: str = INGEST_FETCHER,
    download_timestamp_utc: Optional[str] = None,
) -> Path:
    """Write ``<product>.provenance.json`` next to the product and return it.

    The sidecar naming matches the acquisition gate convention in
    ``exonym.gatekeeper`` (``<stem>.provenance.json``).
    """
    product_path = Path(product_path)
    sidecar = product_path.with_name(product_path.stem + ".provenance.json")
    sidecar.write_text(
        json.dumps(
            make_provenance(product_path, source_uri, fetched_by, download_timestamp_utc),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return sidecar
