"""Run the modular final calculation verification suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow direct execution from the repository root.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verification.runner import run_all_verifications


def main() -> int:
    return run_all_verifications()


if __name__ == "__main__":
    raise SystemExit(main())
