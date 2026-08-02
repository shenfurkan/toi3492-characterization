"""Verify the current Stage-4 RNAAS source and its scientific claim boundary."""

import json
import re
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "toi3492_rnaas.tex"
PDF = ROOT / "toi3492_rnaas.pdf"
LOG = ROOT / "toi3492_rnaas.log"
RNAAS_AUDIT = ROOT / "outputs" / "stage4_rnaas_audit.json"
OUTPUT = ROOT / "outputs" / "stage4_rnaas_release_audit.json"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = SOURCE.read_text(encoding="utf-8")
    rnaas = _load(RNAAS_AUDIT)
    log = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
    required_phrases = (
        "descriptive reference",
        "unvalidated, unconfirmed transit-like candidate",
        "not calibrated PRF localization",
        "do not support a formal false-positive probability",
        "56.29 arcsec",
        "TRICERATOPS-derived",
        "50\\tau",
    )
    checks = {
        "rnaas_structural_audit": rnaas.get("status") == "PASS",
        "compiled_pdf_present": PDF.exists() and PDF.stat().st_size > 0,
        "final_log_has_no_latex_error": "LaTeX Error:" not in log,
        "final_log_has_no_undefined_citations": "Citation `" not in log,
        "required_limitation_language": all(
            phrase in re.sub(r"\s+", " ", source) for phrase in required_phrases
        ),
        "one_figure_no_table": rnaas.get("figure_count") == 1 and rnaas.get("table_count") == 0,
    }
    report = {
        "schema_version": "1.0",
        "work_package": "S4-03_RNAAS_RELEASE_AUDIT",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source": SOURCE.name,
        "source_sha256": _sha256(SOURCE),
        "pdf": PDF.name,
        "pdf_sha256": _sha256(PDF),
        "scientific_scope": "Candidate assessment only; no experimental noise-model result is adopted.",
        "submission_readiness": (
            "RNAAS source, bibliography, single figure, and compiled PDF are ready "
            "for portal submission. Portal metadata entry and author submission remain manual steps."
        ),
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Stage-4 RNAAS release audit: {}".format(report["status"]))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
