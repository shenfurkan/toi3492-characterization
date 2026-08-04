"""Verification checks for reference lightcurve data."""

from __future__ import annotations

import pandas as pd

from ..core import ROOT, SECTORS, Verification


def verify_reference_lightcurve(audit: Verification) -> None:
    data = pd.read_csv(ROOT / "data" / "toi3492_120s_reference.csv")
    expected_columns = ["time", "flux", "flux_err", "sector", "exptime"]
    audit.check("reference_lightcurve", "schema", list(data.columns) == expected_columns,
                str(list(data.columns)))
    audit.check("reference_lightcurve", "finite_positive", bool(
        data.notna().all().all() and (data["flux_err"] > 0).all()
    ), f"rows={len(data)}")
    audit.check("reference_lightcurve", "ordered_120s_six_sectors", bool(
        data["time"].is_monotonic_increasing
        and set(data["sector"]) == set(SECTORS)
        and set(data["exptime"]) == {120.0}
    ), f"sectors={sorted(data['sector'].unique())}")
    sector_depths = pd.read_csv(ROOT / "outputs" / "toi3492_120s_sector_depths.csv")
    counts = data.groupby("sector").size().to_dict()
    expected_counts = dict(zip(sector_depths["sector"], sector_depths["n_points"]))
    audit.check("reference_lightcurve", "per_sector_counts", counts == expected_counts,
                f"{counts}")
