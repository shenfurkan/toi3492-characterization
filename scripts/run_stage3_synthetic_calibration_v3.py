"""Superseded Stage-3 v3 launcher retained only for provenance."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from stage3_quarantine import (
    LegacyStage3QuarantineError,
    refuse_superseded_execution,
)


def main():
    try:
        refuse_superseded_execution(
            "scripts/run_stage3_synthetic_calibration_v3.py",
            3,
            "SUPERSEDED_IMPLEMENTATION_DEFECTS",
        )
    except LegacyStage3QuarantineError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
