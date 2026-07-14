"""Freeze the independent pySYD block cross-check as a compact JSON file."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
PYSYD_DIR = ROOT / "outputs" / "pysyd"
OUT = ROOT / "outputs" / "asteroseismic_pysyd_crosscheck.json"


def records(path):
    frame = pd.read_csv(path)
    return json.loads(frame.to_json(orient="records"))


def main():
    estimates = records(PYSYD_DIR / "estimates.csv")
    global_fit = records(PYSYD_DIR / "global.csv")
    payload = {
        "status": "independent_pipeline_crosscheck_not_a_detection",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "pipeline": "pySYD 6.10.5",
        "input": "preregistered 120-s PDCSAP reductions, analyzed by observing block",
        "search_range_uhz": [400.0, 1600.0],
        "mc_iterations": 1,
        "random_seed": 349201,
        "search_estimates": estimates,
        "global_fits": global_fit,
        "interpretation": (
            "No candidate passes all preregistered detection gates. The S63+64 "
            "and S99+100 search-stage estimates lie near the circular-density "
            "scaling, but their global fits are mutually inconsistent and the "
            "signals fail the required reduction, false-alarm, and replication "
            "controls."
        ),
        "limitations": [
            "One iteration is an initial cross-check, not an uncertainty analysis.",
            "pySYD does not by itself establish a calibrated target-level false-alarm probability.",
            "The block results fail the preregistered replication gate, so additional Monte Carlo fitting is not warranted."
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="ascii")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
