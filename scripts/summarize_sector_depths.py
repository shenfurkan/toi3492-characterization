"""Generate tested weighted-constant statistics for 120-s sector depths."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2


ROOT = Path(__file__).resolve().parent.parent


def calculate_sector_statistics(frame):
    depth = frame["depth_ppm"].to_numpy(float)
    error = frame["depth_err_ppm"].to_numpy(float)
    weight = 1.0 / error**2
    weighted_mean = float(np.sum(weight * depth) / np.sum(weight))
    formal_error = float(np.sqrt(1.0 / np.sum(weight)))
    chi_square = float(np.sum(((depth - weighted_mean) / error) ** 2))
    dof = int(len(depth) - 1)
    scale = float(np.sqrt(chi_square / dof))
    return {
        "weighted_mean_depth_ppm": weighted_mean,
        "weighted_mean_formal_error_ppm": formal_error,
        "chi_square": chi_square,
        "degrees_of_freedom": dof,
        "p_value": float(chi2.sf(chi_square, dof)),
        "unit_reduced_chi_square_error_scale": scale,
        "weighted_mean_scaled_error_ppm": formal_error * scale,
    }


def main():
    source = ROOT / "outputs" / "toi3492_120s_sector_depths.csv"
    result = {
        "source": str(source.relative_to(ROOT)).replace("\\", "/"),
        "method": "inverse-variance weighted constant-depth model using formal sector errors",
        "n_sectors": 6,
        **calculate_sector_statistics(pd.read_csv(source)),
        "interpretation": "The formal sector errors reject a constant depth; the scaled error is descriptive and does not replace a hierarchical sector model.",
    }
    output = ROOT / "outputs" / "sector_depth_statistics.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
