"""Backward-compatibility wrapper launcher for final calculation verification suite.

Delegates execution to the modular package: scripts.verification.runner
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure ROOT is on sys.path so scripts.verification can be imported
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verification.runner import run_all_verifications


def main() -> int:
    return run_all_verifications()


if __name__ == "__main__":
    raise SystemExit(main())
