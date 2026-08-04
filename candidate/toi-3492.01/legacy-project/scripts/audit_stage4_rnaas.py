"""Structural and claim-boundary audit for the Stage-4 RNAAS source."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "toi3492_rnaas.tex"
REFERENCES = ROOT / "references.bib"
BBL = ROOT / "toi3492_rnaas.bbl"
OUTPUT = ROOT / "outputs" / "stage4_rnaas_audit.json"


def approximate_word_count(source):
    text = re.sub(r"%.*", "", source)
    text = re.sub(r"\\(begin|end)\{[^}]+\}", " ", text)
    text = re.sub(r"\\cite[a-zA-Z*]*\{[^}]*\}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+(?:\[[^]]*\])?(?:\{([^{}]*)\})?", r" \1 ", text)
    return len(re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)?|\d+(?:\.\d+)?", text))


def cited_keys(source):
    keys = set()
    for group in re.findall(r"\\cite[a-zA-Z*]*\{([^}]*)\}", source):
        keys.update(key.strip() for key in group.split(",") if key.strip())
    return keys


def has_positive_claim(source, pattern):
    """Treat an explicit nearby negation as a limitation, not a strong claim."""
    for match in re.finditer(pattern, source, re.I):
        preceding = source[max(0, match.start() - 60):match.start()].lower()
        if "not " not in preceding and "no " not in preceding:
            return True
    return False


def main():
    source = SOURCE.read_text(encoding="utf-8")
    bibliography = REFERENCES.read_text(encoding="utf-8")
    source_words = approximate_word_count(source)
    bibliography_words = approximate_word_count(
        BBL.read_text(encoding="utf-8") if BBL.exists() else ""
    )
    words = source_words + bibliography_words
    keys = cited_keys(source)
    available = set(re.findall(r"@\w+\{([^,]+),", bibliography))
    email_match = re.search(r"\\email\{([^}]+)\}", source)
    email = email_match.group(1).strip() if email_match else ""
    forbidden = {
        "claims_validated": has_positive_claim(source, r"\b(we )?validate(?:d)?\b"),
        "claims_confirmed": has_positive_claim(source, r"\b(we )?confirm(?:ed)?\b"),
        "claims_on_target": has_positive_claim(source, r"\bon-target\b"),
        "claims_measured_mass": has_positive_claim(source, r"\bmeasured mass\b"),
        "claims_measured_eccentricity": has_positive_claim(source, r"\bmeasured eccentricity\b"),
    }
    checks = {
        "rnaas_documentclass": "\\documentclass[rnaas]{aastex701}" in source,
        "abstract_present": "\\begin{abstract}" in source and "\\end{abstract}" in source,
        "one_or_fewer_figures": len(re.findall(r"\\begin\{figure", source)) <= 1,
        "no_tables": "\\begin{table" not in source and "\\begin{deluxetable" not in source,
        "word_limit": words <= 1500,
        "citation_keys_resolve": not (keys - available),
        "corresponding_author_email": "@" in email and "example.com" not in email,
        "no_forbidden_strong_claim": not any(forbidden.values()),
    }
    report = {
        "schema_version": "1.0",
        "source": SOURCE.name,
        "approximate_word_count": words,
        "source_word_count": source_words,
        "bibliography_word_count": bibliography_words,
        "figure_count": len(re.findall(r"\\begin\{figure", source)),
        "table_count": len(re.findall(r"\\begin\{(?:table|deluxetable)", source)),
        "cited_keys": sorted(keys),
        "missing_citation_keys": sorted(keys - available),
        "corresponding_author_email_present": bool(email),
        "forbidden_phrase_flags": forbidden,
        "checks": checks,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "compile_note": "This audit does not replace compilation with the official aastex701.cls or PDF visual inspection.",
    }
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Stage-4 RNAAS audit: {} ({} approximate words)".format(report["status"], words))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
