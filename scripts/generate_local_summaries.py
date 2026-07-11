"""Regenerate deterministic summary tables from the frozen light curve."""

from pathlib import Path

import pandas as pd

from build_120s_reference_lightcurve import (
    OFFICIAL_PERIOD,
    OFFICIAL_T0_BTJD,
    robust_depth,
)


ROOT = Path(__file__).resolve().parent.parent


def main():
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    rows = []
    for sector, group in data.groupby("sector", sort=True):
        depth, error, n_in, n_out = robust_depth(
            group["time"].to_numpy(),
            group["flux"].to_numpy(),
            OFFICIAL_PERIOD,
            OFFICIAL_T0_BTJD,
        )
        rows.append(
            {
                "sector": int(sector),
                "n_points": len(group),
                "depth_ppm": depth,
                "depth_err_ppm": error,
                "n_in": n_in,
                "n_out": n_out,
            }
        )
    output = ROOT / "outputs" / "toi3492_120s_sector_depths.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    print(f"Wrote {output.name}")


if __name__ == "__main__":
    main()
