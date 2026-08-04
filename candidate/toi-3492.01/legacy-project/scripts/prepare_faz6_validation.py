"""Freeze the common Phase-6 out-of-transit validation cadence keys."""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

import run_faz5_window_grid as phase5
import run_faz5b_remediation as phase5b


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "faz6_common_validation_keys.csv"
EXPECTED_COUNT = 2233


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_validation_frame():
    protocol = phase5b.load_json(phase5b.PROTOCOL_PATH)
    phase2 = phase5b.load_json(phase5b.PHASE2_PATH)
    phase4 = phase5b.load_json(phase5b.PHASE4_PATH)
    _, reference, _, checks, _, events = phase5b.load_cadence_masks(
        protocol, phase2, phase4
    )
    if not all(checks.values()):
        raise RuntimeError("Phase-5B cadence masks are not valid")
    prereg = phase5b.load_json(phase5.PREREG_PATH)
    t14_hours = float(phase2["ephemeris_and_windows"]["t14_hours"])
    inner_days = 0.75 * t14_hours / 24.0
    outer_days = float(
        prereg["blocked_predictive_comparison"][
            "common_score_outer_boundary_hours"
        ]
    ) / 24.0
    minimum_side = int(
        prereg["blocked_predictive_comparison"][
            "minimum_cadences_per_common_side"
        ]
    )
    frames = []
    excluded = []
    for event in events:
        frame = phase5.event_rows(reference, event, outer_days)
        oot = frame.loc[
            (np.abs(frame["x_days"]) >= inner_days)
            & (np.abs(frame["x_days"]) <= outer_days)
        ].copy()
        left_count = int((oot["x_days"] < 0).sum())
        right_count = int((oot["x_days"] > 0).sum())
        if left_count < minimum_side or right_count < minimum_side:
            excluded.append(event["physical_event_id"])
            continue
        oot["side"] = np.where(oot["x_days"] < 0, "left", "right")
        frames.append(
            oot[
                [
                    "sector",
                    "cadenceno",
                    "time_btjd",
                    "event_id",
                    "epoch",
                    "side",
                    "x_days",
                ]
            ]
        )
    result = pd.concat(frames, ignore_index=True)
    result.sort_values(["sector", "cadenceno"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    if len(result) != EXPECTED_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_COUNT} common validation cadences, found {len(result)}"
        )
    if excluded != ["S100-E193"]:
        raise RuntimeError(f"Unexpected Phase-6 validation exclusions: {excluded}")
    if result.duplicated(["sector", "cadenceno"]).any():
        raise RuntimeError("Phase-6 validation cadence keys are not unique")
    return result


def verify_existing():
    expected = build_validation_frame()
    stored = pd.read_csv(OUTPUT_PATH)
    exact_columns = ["sector", "cadenceno", "event_id", "epoch", "side"]
    pd.testing.assert_frame_equal(
        stored[exact_columns], expected[exact_columns], check_exact=True
    )
    for column in ("time_btjd", "x_days"):
        if not np.allclose(
            stored[column].to_numpy(float),
            expected[column].to_numpy(float),
            rtol=0.0,
            atol=1e-12,
        ):
            raise AssertionError("Stored {} values exceed 1e-12 day".format(column))
    print(
        f"Verified {OUTPUT_PATH.relative_to(ROOT).as_posix()}: "
        f"rows={len(stored)}, sha256={sha256_file(OUTPUT_PATH)}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if not OUTPUT_PATH.is_file():
            raise FileNotFoundError(OUTPUT_PATH)
        verify_existing()
        return
    if OUTPUT_PATH.exists():
        raise FileExistsError(
            "Phase-6 validation keys are no-clobber; use --verify-only"
        )
    frame = build_validation_frame()
    temporary = OUTPUT_PATH.with_name(OUTPUT_PATH.name + ".tmp")
    frame.to_csv(
        temporary,
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    )
    temporary.replace(OUTPUT_PATH)
    print(
        f"Wrote {OUTPUT_PATH.relative_to(ROOT).as_posix()}: "
        f"rows={len(frame)}, sha256={sha256_file(OUTPUT_PATH)}"
    )


if __name__ == "__main__":
    main()
