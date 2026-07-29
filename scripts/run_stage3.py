"""Canonical Stage-3 command-line entry point."""

import os
import sys
from pathlib import Path

for _thread_variable in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_variable, "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from toi3492.stage3.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
