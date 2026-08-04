"""Interface to TRICERATOPS FPP reports.

Parses a TRICERATOPS output JSON file and applies the statistical validation
gate: FPP below the preregistered threshold.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple

FPP_THRESHOLD = 0.01


def load_fpp_report(path: Path) -> Dict[str, Any]:
    """Load a TRICERATOPS output report (JSON dict)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("TRICERATOPS report must be a JSON object")
    return data


def extract_fpp(report: Dict[str, Any]) -> float:
    """Return the FPP value from a report, probing common key layouts."""
    for key in ("fpp", "FPP", "fpp_value"):
        value = report.get(key)
        if value is not None:
            return float(value)
    for key in ("fpp_specific", "FPP_specific", "fpp_specific_value"):
        value = report.get(key)
        if value is not None:
            return float(value)
    raise ValueError("no FPP value found in report")


def fpp_gate(
    report_or_value: Dict[str, Any],
    threshold: float = FPP_THRESHOLD,
) -> Tuple[bool, float]:
    """Return (pass, fpp). Pass means FPP is below the threshold."""
    if isinstance(report_or_value, dict):
        fpp = extract_fpp(report_or_value)
    else:
        fpp = float(report_or_value)
    return fpp < threshold, fpp
