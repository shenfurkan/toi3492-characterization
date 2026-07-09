import json
import re
from datetime import datetime, timezone
from pathlib import Path

import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).parent.parent
METADATA_PATH = ROOT / "outputs" / "official_toi_metadata.json"
CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
OUT_JSON = ROOT / "outputs" / "tess_source_localization_120s.json"
OUT_CSV = ROOT / "outputs" / "toi3492_120s_difference_centroids.csv"
OUT_FIG = ROOT / "figures" / "toi3492_tess_difference_images.png"
TARGET = "TIC 81077799"
TESS_PIXEL_SCALE_ARCSEC = 21.0


def _parse_sector(mission):
    match = re.search(r"Sector\s+(\d+)", str(mission))
    return int(match.group(1)) if match else -1


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


def _phase_hours(time, period, t0):
    return (((time - t0 + 0.5 * period) % period) - 0.5 * period) * 24.0


def _centroid(image, floor_fraction=0.10):
    positive = np.where(np.isfinite(image) & (image > 0), image, 0.0)
    peak = float(np.nanmax(positive)) if np.any(positive > 0) else 0.0
    if peak <= 0:
        return None
    weights = np.where(positive >= floor_fraction * peak, positive, 0.0)
    total = float(np.nansum(weights))
    if total <= 0:
        return None
    yy, xx = np.indices(image.shape)
    return {
        "x_pix": float(np.nansum(weights * xx) / total),
        "y_pix": float(np.nansum(weights * yy) / total),
        "weight_sum": total,
        "peak_difference_flux": peak,
        "n_weighted_pixels": int(np.sum(weights > 0)),
    }


def _load_inputs():
    metadata = json.loads(METADATA_PATH.read_text())
    config = json.loads(CONFIG_PATH.read_text())
    transit = config["transit_corrected_120s"]
    return {
        "ra_deg": float(metadata["coordinates"]["ra_deg"]),
        "dec_deg": float(metadata["coordinates"]["dec_deg"]),
        "period": float(transit["period"]),
        "t0": float(transit["t0"]),
        "duration_hr": float(transit["duration_hrs"]),
    }


def _analyze_tpf(tpf, sector, inputs):
    time = np.asarray(tpf.time.value, dtype=float)
    flux = np.asarray(tpf.flux.value, dtype=float)
    finite = np.isfinite(time) & np.isfinite(np.nanmedian(flux, axis=(1, 2)))
    time = time[finite]
    flux = flux[finite]

    hours = _phase_hours(time, inputs["period"], inputs["t0"])
    in_mask = np.abs(hours) < 0.5 * inputs["duration_hr"]
    out_mask = (np.abs(hours) > 1.2 * inputs["duration_hr"]) & (np.abs(hours) < 2.5 * inputs["duration_hr"])
    if in_mask.sum() < 20 or out_mask.sum() < 20:
        raise RuntimeError(f"Sector {sector} has too few in/out cadences for a difference image.")

    in_image = np.nanmedian(flux[in_mask], axis=0)
    out_image = np.nanmedian(flux[out_mask], axis=0)
    diff_image = out_image - in_image
    centroid = _centroid(diff_image)
    if centroid is None:
        raise RuntimeError(f"Sector {sector} difference image has no positive centroid signal.")

    target_x, target_y = tpf.wcs.world_to_pixel_values(inputs["ra_deg"], inputs["dec_deg"])
    target_x = float(np.asarray(target_x))
    target_y = float(np.asarray(target_y))
    dx = centroid["x_pix"] - target_x
    dy = centroid["y_pix"] - target_y
    offset_pix = float(np.sqrt(dx**2 + dy**2))
    return {
        "sector": int(sector),
        "n_cadences": int(len(time)),
        "n_in": int(in_mask.sum()),
        "n_out": int(out_mask.sum()),
        "target_x_pix": target_x,
        "target_y_pix": target_y,
        "difference_centroid_x_pix": centroid["x_pix"],
        "difference_centroid_y_pix": centroid["y_pix"],
        "dx_pix": float(dx),
        "dy_pix": float(dy),
        "offset_pix": offset_pix,
        "offset_arcsec": offset_pix * TESS_PIXEL_SCALE_ARCSEC,
        "weighted_pixels": centroid["n_weighted_pixels"],
        "difference_weight_sum": centroid["weight_sum"],
        "peak_difference_flux": centroid["peak_difference_flux"],
        "diff_image": diff_image,
    }


def _make_plot(rows):
    n = len(rows)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.4 * ncols, 4.1 * nrows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, row in zip(axes.ravel(), rows):
        image = row["diff_image"]
        vmax = np.nanpercentile(np.abs(image), 99)
        vmax = vmax if np.isfinite(vmax) and vmax > 0 else np.nanmax(np.abs(image))
        ax.imshow(image, origin="lower", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        ax.scatter(row["target_x_pix"], row["target_y_pix"], marker="+", s=160, color="black", linewidths=2, label="target")
        ax.scatter(row["difference_centroid_x_pix"], row["difference_centroid_y_pix"], marker="x", s=120, color="yellow", linewidths=2, label="diff centroid")
        ax.set_title(f"Sector {row['sector']} offset={row['offset_arcsec']:.1f} arcsec")
        ax.set_xlabel("TPF x pixel")
        ax.set_ylabel("TPF y pixel")
        ax.axis("on")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="upper right")
    fig.suptitle("TOI-3492.01 120s TESS Difference Images", y=0.995)
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=180)
    plt.close(fig)


def main():
    inputs = _load_inputs()
    search = lk.search_targetpixelfile(TARGET, author="SPOC")
    rows = []
    print("Downloading and analyzing 120s SPOC target-pixel files...")
    for i, entry in enumerate(search.table):
        exptime = float(entry.get("exptime", np.nan))
        if abs(exptime - 120.0) > 1.0:
            continue
        sector = _parse_sector(entry.get("mission", ""))
        print(f"  Sector {sector}")
        tpf = search[i].download(quality_bitmask="default")
        rows.append(_analyze_tpf(tpf, sector, inputs))

    if not rows:
        raise RuntimeError("No 120s SPOC target-pixel files were found.")
    rows = sorted(rows, key=lambda row: row["sector"])
    _make_plot(rows)

    table_rows = []
    for row in rows:
        clean = {k: v for k, v in row.items() if k != "diff_image"}
        table_rows.append(clean)
    df = pd.DataFrame(table_rows)
    df.to_csv(OUT_CSV, index=False)

    median_offset = float(np.nanmedian(df["offset_arcsec"]))
    max_offset = float(np.nanmax(df["offset_arcsec"]))
    result = {
        "source": "First-pass TESS 120s SPOC target-pixel difference-image centroid check",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "target": TARGET,
            "period_days": inputs["period"],
            "t0_btjd": inputs["t0"],
            "duration_hours": inputs["duration_hr"],
            "pixel_scale_arcsec_assumed": TESS_PIXEL_SCALE_ARCSEC,
        },
        "summary": {
            "n_sectors": int(len(df)),
            "median_difference_centroid_offset_arcsec": median_offset,
            "max_difference_centroid_offset_arcsec": max_offset,
            "median_difference_centroid_offset_pix": float(np.nanmedian(df["offset_pix"])),
            "max_difference_centroid_offset_pix": float(np.nanmax(df["offset_pix"])),
        },
        "sector_results": table_rows,
        "outputs": {
            "centroid_csv": OUT_CSV.name,
            "summary_json": OUT_JSON.name,
            "difference_image_plot": OUT_FIG.name,
        },
        "notes": [
            "This is a simple difference-image centroid check, not a formal SPOC data-validation centroid analysis.",
            "Offsets are measured between the positive difference-image centroid and the target coordinate projected into each TPF WCS.",
            "TESS pixels are large, so sub-pixel offsets should be interpreted cautiously and compared with Gaia neighbors and aperture masks.",
        ],
    }
    OUT_JSON.write_text(json.dumps(_json_clean(result), indent=2))
    print(f"Wrote {OUT_CSV.name}")
    print(f"Wrote {OUT_JSON.name}")
    print(f"Wrote {OUT_FIG.name}")
    print(f"Median offset: {median_offset:.2f} arcsec; max offset: {max_offset:.2f} arcsec")


if __name__ == "__main__":
    main()
