"""Single repository-bound import bridge for frozen Phase-5/6 modules.

The canonical Stage-3 package deliberately reuses the frozen Phase-5/6
analysis modules that live in ``scripts/``. The frozen execution environment
is repository-bound: this bridge is the only place that adds ``scripts/`` to
``sys.path``. If the repository layout changes, imports fail loudly here
instead of producing confusing ImportErrors elsewhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"


def ensure_legacy_imports():
    """Make the frozen scripts/ modules importable; return their directory."""
    if not SCRIPTS.is_dir():
        raise RuntimeError(
            "Stage-3 repository layout is broken: {} is missing".format(SCRIPTS)
        )
    path = str(SCRIPTS)
    if path not in sys.path:
        sys.path.insert(0, path)
    return SCRIPTS
