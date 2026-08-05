"""Target-neutral multi-archive vetting engine.

Queries Gaia EDR3/DR3 astrometry and NASA ExoFOP imaging/spectroscopy metadata
to assess target binarity (Gaia RUWE > 1.4), visual crowding/contamination within
a search radius, and existing ground-based follow-up observations.

All target identifiers and positions are read dynamically from workspace data
or external archival APIs; no target constants exist in this module.
"""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .inputs import load_stellar_parameters, load_tpf_cubes
from .workspace import CandidateWorkspace


class ArchivalVettingService:
    """Service for querying astronomical archives (Gaia, ExoFOP) and evaluating candidate vetting metrics."""

    def __init__(
        self,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor

    def _http_get_json(self, url: str) -> Optional[Any]:
        """Perform an HTTP GET request with retry logic and timeout handling."""
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "exonym-archive/1.0.0 (astronomy-research-framework)",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    if response.status == 200:
                        raw_data = response.read().decode("utf-8", errors="replace")
                        try:
                            return json.loads(raw_data)
                        except json.JSONDecodeError:
                            return None
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff_factor * (2**attempt))
        return None

    def query_gaia_astrometry(
        self, ra: float, dec: float, radius_arcsec: float = 10.0
    ) -> Dict[str, Any]:
        """Cone search Gaia DR3/EDR3 for celestial sources around target coordinates.

        Extracts RUWE (Renormalised Unit Weight Error) for target star and counts
        detected nearby sources within radius_arcsec. Flags suspected_binary if RUWE > 1.4.
        """
        results: Dict[str, Any] = {
            "target_ra_deg": float(ra),
            "target_dec_deg": float(dec),
            "search_radius_arcsec": float(radius_arcsec),
            "ruwe": None,
            "suspected_binary": False,
            "nearby_sources_count": 0,
            "sources": [],
            "source": "gaia-dr3",
        }

        if ra == 0.0 and dec == 0.0:
            return results

        astroquery_success = False
        try:
            from astroquery.gaia import Gaia
            import astropy.units as u
            from astropy.coordinates import SkyCoord

            coord = SkyCoord(ra=ra, dec=dec, unit=(u.deg, u.deg), frame="icrs")
            radius_deg = u.Quantity(radius_arcsec / 3600.0, u.deg)
            job = Gaia.cone_search_async(coord, radius=radius_deg, verbose=False)
            table = job.get_results()

            if table is not None and len(table) > 0:
                astroquery_success = True
                results["nearby_sources_count"] = len(table)
                sources = []
                target_ruwe = None
                min_sep = float("inf")

                for row in table:
                    source_id = (
                        str(row["source_id"]) if "source_id" in row.colnames else "unknown"
                    )
                    sep_arcsec = float(row["dist"]) * 3600.0 if "dist" in row.colnames else 0.0
                    ruwe_val = None
                    if "ruwe" in row.colnames and not math.isnan(row["ruwe"]):
                        ruwe_val = float(row["ruwe"])
                    g_mag = None
                    if "phot_g_mean_mag" in row.colnames and not math.isnan(row["phot_g_mean_mag"]):
                        g_mag = float(row["phot_g_mean_mag"])

                    source_dict = {
                        "source_id": source_id,
                        "separation_arcsec": round(sep_arcsec, 4),
                        "ruwe": round(ruwe_val, 4) if ruwe_val is not None else None,
                        "phot_g_mean_mag": round(g_mag, 4) if g_mag is not None else None,
                    }
                    sources.append(source_dict)

                    if sep_arcsec < min_sep:
                        min_sep = sep_arcsec
                        target_ruwe = ruwe_val

                results["sources"] = sources
                if target_ruwe is not None:
                    results["ruwe"] = round(target_ruwe, 4)
                    results["suspected_binary"] = bool(target_ruwe > 1.4)
        except Exception:
            astroquery_success = False

        if not astroquery_success:
            tap_query = (
                f"SELECT source_id, ra, dec, phot_g_mean_mag, ruwe, "
                f"DISTANCE(POINT('ICRS', ra, dec), POINT('ICRS', {ra}, {dec}))*3600.0 AS sep_arcsec "
                f"FROM gaiadr3.gaia_source "
                f"WHERE 1=CONTAINS(POINT('ICRS', ra, dec), CIRCLE('ICRS', {ra}, {dec}, {radius_arcsec/3600.0})) "
                f"ORDER BY sep_arcsec ASC"
            )
            url = (
                "https://gaia.gec.asiaa.sinica.edu.tw/tap-server/tap/sync?"
                f"REQUEST=doQuery&LANG=ADQL&FORMAT=json&QUERY={urllib.parse.quote(tap_query)}"
            )
            data = self._http_get_json(url)
            if data and isinstance(data, dict) and "data" in data:
                rows = data.get("data", [])
                results["nearby_sources_count"] = len(rows)
                sources = []
                target_ruwe = None
                for i, row in enumerate(rows):
                    sid = str(row[0]) if len(row) > 0 else "unknown"
                    gmag = float(row[3]) if len(row) > 3 and row[3] is not None else None
                    ruwe_val = float(row[4]) if len(row) > 4 and row[4] is not None else None
                    sep_val = float(row[5]) if len(row) > 5 and row[5] is not None else 0.0

                    sources.append(
                        {
                            "source_id": sid,
                            "separation_arcsec": round(sep_val, 4),
                            "ruwe": round(ruwe_val, 4) if ruwe_val is not None else None,
                            "phot_g_mean_mag": round(gmag, 4) if gmag is not None else None,
                        }
                    )
                    if i == 0 and ruwe_val is not None:
                        target_ruwe = ruwe_val

                results["sources"] = sources
                if target_ruwe is not None:
                    results["ruwe"] = round(target_ruwe, 4)
                    results["suspected_binary"] = bool(target_ruwe > 1.4)

        return results

    def query_exofop_metadata(self, tic_id: str) -> Dict[str, Any]:
        """Query NASA ExoFOP JSON API for imaging and spectroscopy records for a target TIC.

        API endpoints:
        - https://exofop.ipac.caltech.edu/tess/target.php?id=<TIC_ID>&json
        - https://exofop.ipac.caltech.edu/tess/api.php?target=<TIC_ID>&json
        """
        tic_clean = str(tic_id).strip().lstrip("TIC").strip()
        results: Dict[str, Any] = {
            "tic_id": tic_clean,
            "has_imaging": False,
            "has_spectroscopy": False,
            "imaging_records_count": 0,
            "spectroscopy_records_count": 0,
            "imaging_types": [],
            "spectroscopy_types": [],
            "target_coordinates": None,
            "source": "nasa-exofop",
        }

        if not tic_clean:
            return results

        # Try target.php first (primary JSON endpoint)
        url_target = f"https://exofop.ipac.caltech.edu/tess/target.php?id={tic_clean}&json"
        payload = self._http_get_json(url_target)

        if not payload or not isinstance(payload, dict):
            url_api = f"https://exofop.ipac.caltech.edu/tess/api.php?target={tic_clean}&json"
            payload = self._http_get_json(url_api)

        if payload and isinstance(payload, dict):
            coords = payload.get("coordinates") or payload.get("target_coordinates")
            if isinstance(coords, dict):
                ra_val = coords.get("ra") or coords.get("ra_deg")
                dec_val = coords.get("dec") or coords.get("dec_deg")
                if ra_val is not None and dec_val is not None:
                    try:
                        results["target_coordinates"] = {
                            "ra_deg": float(ra_val),
                            "dec_deg": float(dec_val),
                        }
                    except (TypeError, ValueError):
                        pass

            imaging = payload.get("imaging") or payload.get("high_res_imaging") or []
            if isinstance(imaging, list):
                results["imaging_records_count"] = len(imaging)
                results["has_imaging"] = len(imaging) > 0
                types = set()
                for rec in imaging:
                    if isinstance(rec, dict):
                        itype = (
                            rec.get("itype")
                            or rec.get("type")
                            or rec.get("technique")
                            or rec.get("iinst")
                            or rec.get("instrument")
                        )
                        if itype:
                            types.add(str(itype).strip())
                results["imaging_types"] = sorted(list(types))

            spectroscopy = (
                payload.get("spectroscopy")
                or payload.get("high_res_spectroscopy")
                or payload.get("spectra")
                or []
            )
            if isinstance(spectroscopy, list):
                results["spectroscopy_records_count"] = len(spectroscopy)
                results["has_spectroscopy"] = len(spectroscopy) > 0
                stypes = set()
                for rec in spectroscopy:
                    if isinstance(rec, dict):
                        stype = (
                            rec.get("stype")
                            or rec.get("type")
                            or rec.get("technique")
                            or rec.get("sinst")
                            or rec.get("instrument")
                            or rec.get("observation_type")
                        )
                        if stype:
                            stypes.add(str(stype).strip())
                results["spectroscopy_types"] = sorted(list(stypes))

        return results

    def synthesize_archival_report(
        self, workspace: CandidateWorkspace, radius_arcsec: float = 10.0
    ) -> Dict[str, Any]:
        """Synthesize Gaia astrometry and ExoFOP metadata for a candidate workspace."""
        identifiers = workspace.metadata.get("identifiers", {})
        tic_id = identifiers.get("tic")
        toi_id = identifiers.get("toi")
        candidate_id = workspace.candidate_id

        exofop_data: Dict[str, Any] = {}
        if tic_id:
            exofop_data = self.query_exofop_metadata(str(tic_id))

        ra_deg: Optional[float] = None
        dec_deg: Optional[float] = None

        params = load_stellar_parameters(workspace)
        if "ra_deg" in params and "dec_deg" in params:
            ra_deg = float(params["ra_deg"])
            dec_deg = float(params["dec_deg"])

        if ra_deg is None or dec_deg is None:
            cubes = load_tpf_cubes(workspace)
            for cube in cubes:
                header = cube.get("header", {})
                if "RA_OBJ" in header and "DEC_OBJ" in header:
                    try:
                        ra_deg = float(header["RA_OBJ"])
                        dec_deg = float(header["DEC_OBJ"])
                        break
                    except (TypeError, ValueError):
                        pass

        if (ra_deg is None or dec_deg is None) and exofop_data.get("target_coordinates"):
            coords = exofop_data["target_coordinates"]
            ra_deg = coords.get("ra_deg")
            dec_deg = coords.get("dec_deg")

        if ra_deg is None or dec_deg is None:
            ra_deg = 0.0
            dec_deg = 0.0

        gaia_data = self.query_gaia_astrometry(ra_deg, dec_deg, radius_arcsec=radius_arcsec)

        ruwe_val = gaia_data.get("ruwe")
        is_hidden_binary = bool(gaia_data.get("suspected_binary", False))
        nearby_count = gaia_data.get("nearby_sources_count", 0)
        has_nearby_contaminants = bool(nearby_count > 1)
        has_imaging = bool(exofop_data.get("has_imaging", False))
        has_spectroscopy = bool(exofop_data.get("has_spectroscopy", False))
        has_ground_based_followup = bool(has_imaging or has_spectroscopy)

        ruwe_str = f"{ruwe_val:.4f}" if isinstance(ruwe_val, float) else "N/A"
        evidence_binary = (
            f"Gaia RUWE ({ruwe_str}) > 1.4 indicates suspected unresolved binary / astrometric wobble"
            if is_hidden_binary
            else f"Gaia RUWE ({ruwe_str}) <= 1.4 indicates consistent single-star astrometry"
        )

        evidence_crowding = (
            f"{nearby_count} celestial sources detected within {radius_arcsec}\" radius (visual crowding/contamination)"
            if has_nearby_contaminants
            else f"Single star detected within {radius_arcsec}\" radius"
        )

        imaging_types_str = ", ".join(exofop_data.get("imaging_types", [])) or "Registered"
        spectroscopy_types_str = ", ".join(exofop_data.get("spectroscopy_types", [])) or "Registered"
        followup_parts = []
        if has_imaging:
            followup_parts.append(f"High-res imaging ({imaging_types_str})")
        if has_spectroscopy:
            followup_parts.append(f"Spectroscopy ({spectroscopy_types_str})")
        evidence_followup = (
            "Ground-based follow-up on ExoFOP: " + "; ".join(followup_parts)
            if has_ground_based_followup
            else "No high-resolution ground-based follow-up registered on ExoFOP"
        )

        timestamp_utc = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

        return {
            "candidate_id": candidate_id,
            "tic_id": str(tic_id) if tic_id else None,
            "toi_id": str(toi_id) if toi_id else None,
            "target_coordinates": {
                "ra_deg": round(ra_deg, 6),
                "dec_deg": round(dec_deg, 6),
            },
            "scientific_assessment": {
                "1_is_hidden_binary": {
                    "answer": is_hidden_binary,
                    "ruwe": ruwe_val,
                    "threshold": 1.4,
                    "evidence": evidence_binary,
                },
                "2_has_nearby_contaminants": {
                    "answer": has_nearby_contaminants,
                    "search_radius_arcsec": float(radius_arcsec),
                    "nearby_sources_count": nearby_count,
                    "evidence": evidence_crowding,
                },
                "3_has_ground_based_followup": {
                    "answer": has_ground_based_followup,
                    "has_high_res_imaging": has_imaging,
                    "has_spectroscopy": has_spectroscopy,
                    "evidence": evidence_followup,
                },
            },
            "gaia_astrometry": gaia_data,
            "exofop_metadata": exofop_data,
            "timestamp_utc": timestamp_utc,
        }


def run_archival_vetting(
    workspace: CandidateWorkspace,
    radius_arcsec: float = 10.0,
    service: Optional[ArchivalVettingService] = None,
) -> Path:
    """Run multi-archive vetting on candidate workspace and write output report JSON.

    Returns the absolute path to outputs/archival_vetting_report.json.
    """
    if service is None:
        service = ArchivalVettingService()

    report = service.synthesize_archival_report(workspace, radius_arcsec=radius_arcsec)
    outputs_dir = workspace.path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    report_path = outputs_dir / "archival_vetting_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report_path
