import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from astroquery.gaia import Gaia


ROOT = Path(__file__).parent.parent
METADATA_PATH = ROOT / "outputs" / "official_toi_metadata.json"
CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
OUT_CSV = ROOT / "outputs" / "gaia_dr3_neighbors.csv"
OUT_JSON = ROOT / "outputs" / "gaia_contamination_check.json"
OUT_FIG = ROOT / "figures" / "toi3492_gaia_neighbors.png"


def _as_float(value):
    try:
        if value is None:
            return None
        value = float(value)
        if not np.isfinite(value):
            return None
        return value
    except Exception:
        return None


def _json_clean(value):
    if isinstance(value, dict):
        return {str(k): _json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    if pd.isna(value):
        return None
    return value


def _load_inputs():
    metadata = json.loads(METADATA_PATH.read_text())
    config = json.loads(CONFIG_PATH.read_text())
    coords = metadata["coordinates"]
    transit = config["transit_corrected_120s"]
    return {
        "ra_deg": float(coords["ra_deg"]),
        "dec_deg": float(coords["dec_deg"]),
        "tic_contamination_ratio_exofop": _as_float(metadata["target"].get("tic_contamination_ratio_exofop")),
        "observed_depth_ppm": float(transit["depth_ppm"]),
        "target_name": metadata["target"]["display"],
        "tic_id": int(metadata["target"]["tid"]),
    }


def _query_gaia(ra_deg, dec_deg, radius_arcsec=120.0):
    radius_deg = radius_arcsec / 3600.0
    Gaia.ROW_LIMIT = -1
    query = f"""
    SELECT
        source_id,
        ra,
        dec,
        DISTANCE(
            POINT('ICRS', ra, dec),
            POINT('ICRS', {ra_deg:.10f}, {dec_deg:.10f})
        ) * 3600.0 AS separation_arcsec,
        parallax,
        parallax_error,
        pmra,
        pmra_error,
        pmdec,
        pmdec_error,
        phot_g_mean_mag,
        phot_bp_mean_mag,
        phot_rp_mean_mag,
        ruwe,
        astrometric_excess_noise,
        duplicated_source,
        non_single_star
    FROM gaiadr3.gaia_source
    WHERE 1 = CONTAINS(
        POINT('ICRS', ra, dec),
        CIRCLE('ICRS', {ra_deg:.10f}, {dec_deg:.10f}, {radius_deg:.10f})
    )
    """
    job = Gaia.launch_job_async(query, dump_to_file=False)
    table = job.get_results()
    return table.to_pandas().sort_values("separation_arcsec").reset_index(drop=True)


def _required_flux_ratios(depth_ppm):
    depth = depth_ppm * 1e-6
    total_eclipse_ratio = depth / (1.0 - depth)
    half_eclipse_ratio = depth / (0.5 - depth)
    return {
        "observed_depth_fraction": depth,
        "full_eclipse_flux_ratio_required": total_eclipse_ratio,
        "full_eclipse_delta_g_limit_mag": -2.5 * np.log10(total_eclipse_ratio),
        "half_eclipse_flux_ratio_required": half_eclipse_ratio,
        "half_eclipse_delta_g_limit_mag": -2.5 * np.log10(half_eclipse_ratio),
    }


def _add_contamination_columns(df, ra_deg, dec_deg, observed_depth_ppm):
    if df.empty:
        raise RuntimeError("Gaia query returned no sources.")

    target_index = int(df["separation_arcsec"].idxmin())
    df["is_target_match"] = False
    df.loc[target_index, "is_target_match"] = True

    target_g = float(df.loc[target_index, "phot_g_mean_mag"])
    df["delta_g_mag"] = df["phot_g_mean_mag"] - target_g
    df["flux_ratio_vs_target"] = np.where(
        np.isfinite(df["delta_g_mag"]),
        10.0 ** (-0.4 * df["delta_g_mag"]),
        np.nan,
    )

    neighbor = ~df["is_target_match"]
    df["max_depth_if_fully_eclipsed_ppm"] = np.nan
    df["max_depth_if_50pct_eclipsed_ppm"] = np.nan
    ratio = df.loc[neighbor, "flux_ratio_vs_target"]
    df.loc[neighbor, "max_depth_if_fully_eclipsed_ppm"] = ratio / (1.0 + ratio) * 1e6
    df.loc[neighbor, "max_depth_if_50pct_eclipsed_ppm"] = 0.5 * ratio / (1.0 + ratio) * 1e6
    df["can_mimic_full_eclipse"] = neighbor & (df["max_depth_if_fully_eclipsed_ppm"] >= observed_depth_ppm)
    df["can_mimic_50pct_eclipse"] = neighbor & (df["max_depth_if_50pct_eclipsed_ppm"] >= observed_depth_ppm)

    cos_dec = np.cos(np.radians(dec_deg))
    df["delta_ra_arcsec"] = (df["ra"] - ra_deg) * cos_dec * 3600.0
    df["delta_dec_arcsec"] = (df["dec"] - dec_deg) * 3600.0
    return df


def _aperture_summary(df, observed_depth_ppm):
    rows = []
    neighbor = ~df["is_target_match"]
    for radius in [21.0, 42.0, 60.0, 120.0]:
        in_radius = neighbor & (df["separation_arcsec"] <= radius)
        flux_ratio_sum = float(np.nansum(df.loc[in_radius, "flux_ratio_vs_target"]))
        dilution_fraction = flux_ratio_sum / (1.0 + flux_ratio_sum)
        rows.append(
            {
                "radius_arcsec": radius,
                "n_neighbors": int(in_radius.sum()),
                "neighbor_flux_ratio_sum_gband": flux_ratio_sum,
                "dilution_fraction_gband": dilution_fraction,
                "target_transit_depth_corrected_ppm": observed_depth_ppm * (1.0 + flux_ratio_sum),
                "radius_correction_factor_if_on_target": float(np.sqrt(1.0 + flux_ratio_sum)),
            }
        )
    return rows


def _row_for_json(row):
    out = {}
    for key, value in row.items():
        if key == "source_id" and value is not None and not pd.isna(value):
            out[key] = str(int(value))
        else:
            out[key] = value
    return out


def _make_plot(df):
    fig, ax = plt.subplots(figsize=(7, 7))
    neighbors = ~df["is_target_match"]
    sizes = np.clip(80.0 * np.sqrt(df.loc[neighbors, "flux_ratio_vs_target"].fillna(0.0)), 10, 180)
    scatter = ax.scatter(
        df.loc[neighbors, "delta_ra_arcsec"],
        df.loc[neighbors, "delta_dec_arcsec"],
        c=df.loc[neighbors, "delta_g_mag"],
        s=sizes,
        cmap="viridis_r",
        alpha=0.8,
        edgecolor="black",
        linewidth=0.3,
        label="Gaia DR3 neighbors",
    )
    target = df[df["is_target_match"]].iloc[0]
    ax.scatter([target["delta_ra_arcsec"]], [target["delta_dec_arcsec"]], marker="*", s=220, color="tab:red", label="target match")
    for radius, style in [(21.0, "--"), (42.0, ":"), (60.0, "-.")]:
        circle = plt.Circle((0, 0), radius, fill=False, color="tab:gray", linestyle=style, linewidth=1.0)
        ax.add_patch(circle)
        ax.text(radius / np.sqrt(2), radius / np.sqrt(2), f"{radius:.0f}\"", color="tab:gray", fontsize=8)
    ax.axhline(0, color="lightgray", linewidth=0.8)
    ax.axvline(0, color="lightgray", linewidth=0.8)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Delta RA cos(dec) (arcsec)")
    ax.set_ylabel("Delta Dec (arcsec)")
    ax.set_title("TOI-3492.01 Gaia DR3 Neighbor Field")
    ax.invert_xaxis()
    ax.grid(alpha=0.2)
    ax.legend(loc="upper right")
    if len(df.loc[neighbors]) > 0:
        cbar = fig.colorbar(scatter, ax=ax, shrink=0.82)
        cbar.set_label("Delta G relative to target (mag)")
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=180)
    plt.close(fig)


def main():
    inputs = _load_inputs()
    radius_arcsec = 120.0
    print(f"Querying Gaia DR3 within {radius_arcsec:.0f} arcsec of TIC {inputs['tic_id']}...")
    df = _query_gaia(inputs["ra_deg"], inputs["dec_deg"], radius_arcsec=radius_arcsec)
    df = _add_contamination_columns(df, inputs["ra_deg"], inputs["dec_deg"], inputs["observed_depth_ppm"])
    df.to_csv(OUT_CSV, index=False)
    _make_plot(df)

    target = df[df["is_target_match"]].iloc[0]
    target_ruwe = _as_float(target.get("ruwe"))
    if target_ruwe is None:
        ruwe_interpretation = "RUWE unavailable in Gaia result."
    elif target_ruwe <= 1.4:
        ruwe_interpretation = "RUWE is below the common 1.4 caution threshold."
    else:
        ruwe_interpretation = "RUWE is above the common 1.4 caution threshold; unresolved multiplicity or astrometric issues remain possible."

    neighbors = df[~df["is_target_match"]]
    full_mimics = neighbors[neighbors["can_mimic_full_eclipse"]]
    half_mimics = neighbors[neighbors["can_mimic_50pct_eclipse"]]
    brightest_neighbor = neighbors.sort_values("phot_g_mean_mag").head(1)
    nearest_neighbor = neighbors.sort_values("separation_arcsec").head(1)
    exofop_ratio = inputs["tic_contamination_ratio_exofop"]

    result = {
        "source": "Gaia DR3 gaiadr3.gaia_source via astroquery.gaia",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "target": {
            "name": inputs["target_name"],
            "tic_id": inputs["tic_id"],
            "ra_deg": inputs["ra_deg"],
            "dec_deg": inputs["dec_deg"],
        },
        "query": {"radius_arcsec": radius_arcsec, "n_sources_returned": int(len(df))},
        "observed_transit": {"depth_ppm": inputs["observed_depth_ppm"]},
        "target_match": _row_for_json(target.to_dict()),
        "target_ruwe_interpretation": ruwe_interpretation,
        "contaminant_brightness_thresholds": _required_flux_ratios(inputs["observed_depth_ppm"]),
        "neighbor_summary": {
            "n_neighbors_within_120_arcsec": int(len(neighbors)),
            "n_neighbors_that_could_mimic_if_fully_eclipsed": int(len(full_mimics)),
            "n_neighbors_that_could_mimic_if_50pct_eclipsed": int(len(half_mimics)),
            "brightest_neighbor": _row_for_json(brightest_neighbor.iloc[0].to_dict()) if len(brightest_neighbor) else None,
            "nearest_neighbor": _row_for_json(nearest_neighbor.iloc[0].to_dict()) if len(nearest_neighbor) else None,
            "full_eclipse_mimic_candidates": [_row_for_json(r) for r in full_mimics.head(20).to_dict(orient="records")],
            "half_eclipse_mimic_candidates": [_row_for_json(r) for r in half_mimics.head(20).to_dict(orient="records")],
        },
        "aperture_flux_summary_gband": _aperture_summary(df, inputs["observed_depth_ppm"]),
        "exofop_tic_contamination_ratio": {
            "value": exofop_ratio,
            "depth_correction_factor_if_ratio_is_flux_contamination": None if exofop_ratio is None else 1.0 + exofop_ratio,
            "radius_correction_factor_if_ratio_is_flux_contamination": None if exofop_ratio is None else float(np.sqrt(1.0 + exofop_ratio)),
        },
        "outputs": {
            "neighbor_csv": OUT_CSV.name,
            "summary_json": OUT_JSON.name,
            "field_plot": OUT_FIG.name,
        },
        "notes": [
            "This is a Gaia-band neighbor and astrometric sanity check, not a TESS pixel-level centroid validation.",
            "Gaia G-band flux ratios are approximate for TESS contamination because the bandpasses differ.",
            "A nearby source bright enough to mimic the observed depth is a flag for follow-up, not proof of a false positive.",
        ],
    }

    OUT_JSON.write_text(json.dumps(_json_clean(result), indent=2))
    print(f"Wrote {OUT_CSV.name}")
    print(f"Wrote {OUT_JSON.name}")
    print(f"Wrote {OUT_FIG.name}")
    print(ruwe_interpretation)
    print(
        "Potential fully eclipsed Gaia-neighbor mimics: "
        f"{len(full_mimics)} within {radius_arcsec:.0f} arcsec"
    )


if __name__ == "__main__":
    main()
