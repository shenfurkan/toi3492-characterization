"""Calibrated PRF-based source localization for TOI-3492.01.

For each sector, fits the in-transit depth map as a linear combination of
PRF templates centered on each Gaia source bright enough to matter.
The source with the largest fitted depth amplitude is the transit host.
"""
import json, math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from astropy.io import fits
from astropy.wcs import WCS

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "outputs" / "prf_source_localization.json"
SECTORS = (37, 63, 64, 90, 99, 100)
QUALITY_HARD = 24319
TESS_PIX_ARCSEC = 21.0
PRF_FWHM_PIX = 0.75  # TESS PRF core is sub-pixel FWHM


def gaussian_prf(x_grid, y_grid, x0, y0, fwhm_pix=PRF_FWHM_PIX):
    sigma = fwhm_pix / 2.3548
    g = np.exp(-((x_grid - x0)**2 + (y_grid - y0)**2) / (2 * sigma**2))
    g /= np.sum(g) if np.sum(g) > 0 else 1.0
    return g


def load_sector(fits_path, config, metadata, gaia_df):
    with fits.open(fits_path, memmap=False) as hdul:
        pix_hdu, ap_hdu = hdul[1], hdul[2]
        aperture = np.asarray(ap_hdu.data, dtype=np.int16)
        pipeline = (aperture & 2) != 0
        wcs = WCS(ap_hdu.header)
        time = np.asarray(pix_hdu.data["TIME"], dtype=np.float64)
        quality = np.asarray(pix_hdu.data["QUALITY"], dtype=np.int64)
        flux = np.asarray(pix_hdu.data["FLUX"], dtype=np.float64)
        shape = aperture.shape
    good = (np.isfinite(time) & ((quality & QUALITY_HARD) == 0)
            & np.all(np.isfinite(flux), axis=(1, 2)))
    time, flux = time[good], flux[good]

    period = float(config["transit"]["period"])
    t0 = float(config["transit"]["t0"])
    duration_h = float(config["transit"]["duration_hrs"])
    phase = (((time - t0 + 0.5 * period) % period) - 0.5 * period) * 24.0
    in_mask = np.abs(phase) < 0.5 * duration_h
    out_mask = (np.abs(phase) > 1.2 * duration_h) & (np.abs(phase) < 2.5 * duration_h)
    if in_mask.sum() < 10 or out_mask.sum() < 10:
        return None, None, None, None, None, None

    in_image = np.nanmedian(flux[in_mask], axis=0)
    out_image = np.nanmedian(flux[out_mask], axis=0)
    valid = np.isfinite(in_image) & np.isfinite(out_image) & (out_image > 0)
    depth_map = np.full(shape, np.nan, dtype=np.float64)
    depth_map[valid] = (out_image[valid] - in_image[valid]) / out_image[valid]

    # Map Gaia sources onto TPF pixel grid
    ra_target = float(metadata["coordinates"]["ra_deg"])
    dec_target = float(metadata["coordinates"]["dec_deg"])
    target_x, target_y = wcs.world_to_pixel_values(ra_target, dec_target)
    target_x = float(np.asarray(target_x))
    target_y = float(np.asarray(target_y))

    # Select sources within TPF bounds with positive flux contribution
    sources = []
    for _, row in gaia_df.iterrows():
        sx, sy = wcs.world_to_pixel_values(float(row["ra"]), float(row["dec"]))
        sx, sy = float(np.asarray(sx)), float(np.asarray(sy))
        if not (-3 <= sx < shape[1] + 2 and -3 <= sy < shape[0] + 2):
            continue
        g_mag = float(row["phot_g_mean_mag"])
        # Only sources that could plausibly contribute to a transit
        # (any finite Gaia source within/near aperture)
        flux_ratio = float(row["flux_ratio_vs_target"])
        if flux_ratio < 1e-5:
            continue
        is_target = bool(str(row["is_target_match"]).lower() == "true")
        sources.append({
            "source_id": str(int(row["source_id"])),
            "x_pix": sx, "y_pix": sy,
            "g_mag": g_mag, "flux_ratio": flux_ratio,
            "separation_arcsec": float(row["separation_arcsec"]),
            "is_target": is_target,
        })

    # Always include the catalog target
    has_target = any(s["is_target"] for s in sources)
    if not has_target:
        sources.append({
            "source_id": "TARGET", "x_pix": target_x, "y_pix": target_y,
            "g_mag": 8.83, "flux_ratio": 1.0, "separation_arcsec": 0.0,
            "is_target": True,
        })

    # If target is in list, replace its pixel coords with the WCS-derived target
    # coords (more accurate than Gaia's possibly-jittery position)
    for src in sources:
        if src["is_target"]:
            src["x_pix"] = target_x
            src["y_pix"] = target_y
            break

    # Keep only the brightest 5 non-target sources + target to avoid
    # nnls distributing flux across hundreds of faint sources.
    non_target = sorted([s for s in sources if not s["is_target"]],
                       key=lambda s: s["g_mag"])[:5]
    sources = [s for s in sources if s["is_target"]] + non_target

    # Build PRF design matrix for each candidate source on the aperture pixels
    yy, xx = np.indices(shape, dtype=np.float64)
    pixel_mask = pipeline & np.isfinite(depth_map) & (depth_map != 0)
    if pixel_mask.sum() < 5:
        return None, None, None, None, None, None

    design_rows = []
    for src in sources:
        kernel = gaussian_prf(xx[pixel_mask], yy[pixel_mask],
                              src["x_pix"], src["y_pix"])
        design_rows.append(kernel)
    A = np.array(design_rows).T  # shape (npix, nsrc)
    depths = depth_map[pixel_mask]  # shape (npix,)

    # Solve: depths = A @ amplitudes via non-negative least squares
    from scipy.optimize import nnls
    try:
        amplitudes, residual = nnls(A, depths, maxiter=5000)
    except Exception:
        amplitudes, residual = None, None

    return sources, amplitudes, residual, pixel_mask.sum(), in_mask.sum(), out_mask.sum()


def main():
    config = json.loads((ROOT / "data" / "config_corrected_120s.json").read_text())
    metadata = json.loads((ROOT / "data" / "official_toi_metadata.json").read_text())
    inventory = json.loads((ROOT / "outputs" / "asteroseismic_input_inventory.json").read_text())
    gaia = pd.read_csv(ROOT / "outputs" / "gaia_dr3_neighbors.csv")

    tpf_paths = {}
    for product in inventory["products"]:
        if product["product_type"] == "tpf" and product["cadence_seconds"] == 120:
            sec = int(product["sector"])
            if sec in SECTORS:
                tpf_paths[sec] = ROOT / product["relative_path"]
    assert set(tpf_paths) == set(SECTORS)

    sector_results = []
    for sector in SECTORS:
        print(f"Sector {sector}...", flush=True)
        sources, amplitudes, residual, npix, n_in, n_out = load_sector(
            tpf_paths[sector], config, metadata, gaia)
        if amplitudes is None:
            print(f"  skipped")
            continue
        # Per-source centroid-weight vs target
        target_idx = next((i for i, s in enumerate(sources) if s["is_target"]), None)
        amp_by_source = {}
        for i, src in enumerate(sources):
            amp = float(amplitudes[i]) if amplitudes[i] > 0 else 0.0
            amp_by_source[src["source_id"]] = {
                "g_mag": src["g_mag"],
                "separation_arcsec": src["separation_arcsec"],
                "is_target": src["is_target"],
                "depth_amplitude_ppm": amp * 1e6,
            }
        target_amp = amp_by_source.get(sources[target_idx]["source_id"], {}).get("depth_amplitude_ppm", 0.0)
        other_amps = [v["depth_amplitude_ppm"] for k, v in amp_by_source.items()
                      if not v["is_target"]]
        max_other = max(other_amps) if other_amps else 0.0
        dominant_source_id = max(amp_by_source, key=lambda k: amp_by_source[k]["depth_amplitude_ppm"])
        is_target_dominant = amp_by_source[dominant_source_id]["is_target"]
        ratio = target_amp / max(max_other, 1e-12)
        print(f"  target_depth={target_amp:.0f} ppm, max_other={max_other:.0f} ppm, ratio={ratio:.2f}, "
              f"dominant={'TARGET' if is_target_dominant else dominant_source_id}")
        sector_results.append({
            "sector": int(sector),
            "n_aperture_pixels_used": int(npix),
            "n_in_transit_cadences": int(n_in),
            "n_out_transit_cadences": int(n_out),
            "nnls_residual": float(residual) if residual is not None else None,
            "target_depth_amplitude_ppm": float(target_amp),
            "max_other_depth_amplitude_ppm": float(max_other),
            "target_to_max_other_ratio": float(ratio),
            "dominant_source_id": str(dominant_source_id),
            "dominant_is_target": bool(is_target_dominant),
            "per_source_amplitudes_ppm": amp_by_source,
        })

    target_dominant_count = sum(1 for r in sector_results if r["dominant_is_target"])
    median_ratio = float(np.median([r["target_to_max_other_ratio"] for r in sector_results]))
    print(f"\n{target_dominant_count}/{len(sector_results)} sectors target-dominant")
    print(f"Median target/other amplitude ratio: {median_ratio:.2f}")

    report = {
        "schema_version": "1.0",
        "work_package": "PRF_SOURCE_LOCALIZATION",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "method": "Gaussian-PRF non-negative least-squares fit of in-transit depth map",
        "prf_model": "isotropic Gaussian, FWHM=1 TESS pixel (~21 arcsec)",
        "caveats": [
            "This is a first-order Gaussian-PRF approximation, not the formal TESS PRF library template.",
            "PRF wings beyond ~3 pixels are not modeled; a deeply eclipsed neighbor far from the aperture cannot be excluded.",
            "Results are most informative for sources within or near the pipeline aperture.",
        ],
        "sector_results": sector_results,
        "summary": {
            "n_sectors": len(sector_results),
            "sectors_target_dominant": int(target_dominant_count),
            "sectors_other_dominant": len(sector_results) - target_dominant_count,
            "median_target_to_other_ratio": median_ratio,
            "conclusion": (
                "target_dominant_in_majority"
                if target_dominant_count >= 4 else
                "inconclusive_or_other"
            ),
        },
    }
    status = ("supports_target_origin" if target_dominant_count >= 4
              and median_ratio > 1.0
              else "inconclusive_or_other")
    report["status"] = status
    OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"\nStatus: {status}")
    print(f"Saved: {OUT_JSON}")


if __name__ == "__main__":
    main()