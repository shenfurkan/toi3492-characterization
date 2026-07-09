import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from astropy.io import fits

try:
    from pdfminer.high_level import extract_text
except Exception:  # pragma: no cover - optional dependency guard
    extract_text = None


ROOT = Path(__file__).parent.parent
DV_BASE = ROOT / "data" / "spoc_dv" / "mastDownload" / "TESS"
OUT = ROOT / "outputs"

CONFIG_PATH = ROOT / "data" / "config_corrected_120s.json"
OFFICIAL_TOI_PATH = OUT / "official_toi_metadata.json"

INVENTORY_JSON = OUT / "spoc_dv_inventory.json"
TRANSIT_CSV = OUT / "spoc_dv_transit_metrics.csv"
PDF_CSV = OUT / "spoc_dv_pdf_metrics.csv"
COMPARISON_JSON = OUT / "spoc_vs_local_comparison.json"
SUMMARY_JSON = OUT / "spoc_dv_summary.json"
SUMMARY_MD = OUT / "spoc_dv_summary.md"


def as_builtin(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isfinite(value):
            return float(value)
        return None
    if isinstance(value, (np.ndarray,)):
        return [as_builtin(v) for v in value.tolist()]
    if value is None:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def load_json(path):
    return json.loads(path.read_text())


def sector_span(path):
    text = path.name
    match = re.search(r"-s(\d{4})-s(\d{4})-", text)
    if not match:
        match = re.search(r"-s(\d{4})-s(\d{4})-", path.parent.name)
    if match:
        start = int(match.group(1))
        stop = int(match.group(2))
        label = f"S{start}" if start == stop else f"S{start}-S{stop}"
        kind = "single_sector" if start == stop else "multi_sector"
        return start, stop, label, kind
    return None, None, "unknown", "unknown"


def relation_to_official(period_days, official_period_days):
    if period_days is None:
        return "unknown"
    period = float(period_days)
    p0 = float(official_period_days)
    rel_one = abs(period - p0) / p0
    rel_two = abs(period - 2.0 * p0) / (2.0 * p0)
    rel_half = abs(period - 0.5 * p0) / (0.5 * p0)
    if rel_one < 0.005:
        return "official_period"
    if rel_two < 0.005:
        return "two_p_alias"
    if rel_half < 0.005:
        return "half_p_alias"
    return "other_tce"


def hget(header, key):
    return as_builtin(header.get(key))


def parse_dvt_files(config, official):
    dvt_files = sorted(DV_BASE.rglob("*dvt.fits"))
    official_period = official["official_planet_candidate_parameters"]["period_days"]
    inventory = []
    rows = []

    for path in dvt_files:
        start, stop, label, kind = sector_span(path)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with fits.open(path) as hdul:
                primary = hdul[0].header
                hdus = []
                for i, hdu in enumerate(hdul):
                    hdus.append(
                        {
                            "index": i,
                            "name": hdu.name,
                            "extname": hget(hdu.header, "EXTNAME"),
                            "extver": hget(hdu.header, "EXTVER"),
                            "naxis1": hget(hdu.header, "NAXIS1"),
                            "naxis2": hget(hdu.header, "NAXIS2"),
                            "columns": list(hdu.columns.names) if getattr(hdu, "columns", None) is not None else [],
                        }
                    )

                inventory.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "sector_start": start,
                        "sector_stop": stop,
                        "product_label": label,
                        "product_kind": kind,
                        "num_tces": hget(primary, "NUMTCES"),
                        "target_id": hget(primary, "TICID") or hget(primary, "TIC_ID"),
                        "tessmag": hget(primary, "TESSMAG") or hget(primary, "TMAG"),
                        "stellar_radius_rsun": hget(primary, "RADIUS"),
                        "hdus": hdus,
                    }
                )

                for hdu in hdul[1:]:
                    if not hdu.name.upper().startswith("TCE_"):
                        continue
                    hdr = hdu.header
                    tce_index = int(hdu.name.split("_")[-1])
                    period = hget(hdr, "TPERIOD")
                    epoch = hget(hdr, "TEPOCH")
                    row = {
                        "file": str(path.relative_to(ROOT)),
                        "product_label": label,
                        "product_kind": kind,
                        "sector_start": start,
                        "sector_stop": stop,
                        "tce_index": tce_index,
                        "relation_to_official": relation_to_official(period, official_period),
                        "period_days": period,
                        "epoch_btjd": epoch,
                        "depth_ppm": hget(hdr, "TDEPTH"),
                        "duration_hours": hget(hdr, "TDUR"),
                        "ingress_duration_hours": hget(hdr, "INDUR"),
                        "impact_parameter": hget(hdr, "IMPACT"),
                        "inclination_deg": hget(hdr, "INCLIN"),
                        "a_rs": hget(hdr, "DRRATIO"),
                        "rp_rs": hget(hdr, "RADRATIO"),
                        "rp_earth": hget(hdr, "PRADIUS"),
                        "max_mes": hget(hdr, "MAXMES"),
                        "max_ses": hget(hdr, "MAXSES"),
                    }
                    if period is not None:
                        row["period_delta_days_vs_official"] = float(period) - official_period
                        row["period_ratio_vs_official"] = float(period) / official_period
                    rows.append(row)

    return inventory, rows


def numbers_from_line(line):
    return [float(x) for x in re.findall(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", line)]


def value_after(block, label):
    for line in block:
        if label.lower() in line.lower():
            nums = numbers_from_line(line)
            if nums:
                return nums[0]
    return None


def value_err_after(block, label):
    for line in block:
        if label.lower() in line.lower():
            nums = numbers_from_line(line)
            if len(nums) >= 2:
                return nums[0], nums[1]
            if len(nums) == 1:
                return nums[0], None
    return None, None


def statistic_after(block, label):
    for i, line in enumerate(block):
        if label.lower() not in line.lower():
            continue
        window = block[i + 1 : i + 12]
        value = None
        sig_percent = None
        for candidate in window:
            low = candidate.lower()
            if (
                " statistic" in low
                and label.lower() not in low
                and not low.startswith("value")
                and not low.startswith("significance")
            ):
                break
            if candidate.lower().startswith("value"):
                nums = numbers_from_line(candidate)
                if nums:
                    value = nums[0]
            if candidate.lower().startswith("significance"):
                nums = numbers_from_line(candidate)
                if nums:
                    sig_percent = nums[0]
            if value is not None and sig_percent is not None:
                break
        return value, sig_percent
    return None, None


def parse_offset_group(block, label, prefix):
    out = {}
    for i, line in enumerate(block):
        if label.lower() not in line.lower():
            continue
        window = []
        for candidate in block[i + 1 : i + 12]:
            low_candidate = candidate.lower()
            if prefix == "joint" and "multi-sector offsets relative" in low_candidate:
                break
            if prefix == "multi_sector" and (
                "shorter period" in low_candidate
                or "longer period" in low_candidate
                or "false alarm" in low_candidate
                or "transit count" in low_candidate
            ):
                break
            window.append(candidate)
        for candidate in window:
            nums = numbers_from_line(candidate)
            if len(nums) < 2:
                continue
            low = candidate.lower()
            if "source ra offset" in low:
                out[f"{prefix}_ra_offset_arcsec"] = nums[0]
                out[f"{prefix}_ra_offset_err_arcsec"] = nums[1]
                if len(nums) >= 3:
                    out[f"{prefix}_ra_offset_sigma"] = nums[2]
            elif "source dec offset" in low:
                out[f"{prefix}_dec_offset_arcsec"] = nums[0]
                out[f"{prefix}_dec_offset_err_arcsec"] = nums[1]
                if len(nums) >= 3:
                    out[f"{prefix}_dec_offset_sigma"] = nums[2]
            elif "source offset distance" in low:
                out[f"{prefix}_offset_distance_arcsec"] = nums[0]
                out[f"{prefix}_offset_distance_err_arcsec"] = nums[1]
                if len(nums) >= 3:
                    out[f"{prefix}_offset_distance_sigma"] = nums[2]
        break
    return out


def parse_dvr_pdfs():
    dvr_files = sorted(DV_BASE.rglob("*dvr.pdf"))
    rows = []
    if extract_text is None:
        return rows, {"pdfminer_available": False, "n_dvr_files": len(dvr_files)}

    for path in dvr_files:
        start, stop, label, kind = sector_span(path)
        try:
            text = extract_text(str(path)) or ""
        except Exception as exc:
            rows.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "product_label": label,
                    "product_kind": kind,
                    "parse_error": str(exc),
                }
            )
            continue

        text = text.encode("ascii", "replace").decode("ascii")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidate_starts = [
            i
            for i, line in enumerate(lines)
            if re.match(r"Target\s+\d+\s*/\s*Planet Candidate\s+\d+", line)
        ]
        seen = set()
        for i in candidate_starts:
            match = re.search(r"Planet Candidate\s+(\d+)", lines[i])
            if not match:
                continue
            candidate_index = int(match.group(1))
            key = (str(path), candidate_index)
            block = lines[i : i + 140]
            if not any("Depth =" in line for line in block):
                continue
            if key in seen:
                continue
            seen.add(key)

            depth, depth_err = value_err_after(block, "Depth =")
            radius, radius_err = value_err_after(block, "Planet Radius")
            period, period_err = value_err_after(block, "Period =")
            stellar_radius, stellar_radius_err = value_err_after(block, "Stellar Radius")
            semi_major_axis, semi_major_axis_err = value_err_after(block, "Semi-major Axis")
            insolation, insolation_err = value_err_after(block, "Effective Stellar Flux")
            teq, teq_err = value_err_after(block, "Equilibrium Temperature")
            odd_even_value, odd_even_sig = statistic_after(block, "Odd-Even Depth")
            shorter_value, shorter_sig = statistic_after(block, "Shorter Period")
            longer_value, longer_sig = statistic_after(block, "Longer Period")
            core_statistic, core_significance = statistic_after(block, "Core Aperture Correlation Statistic")
            halo_statistic, halo_significance = statistic_after(block, "Halo Aperture Correlation Statistic")
            row = {
                "file": str(path.relative_to(ROOT)),
                "product_label": label,
                "product_kind": kind,
                "sector_start": start,
                "sector_stop": stop,
                "planet_candidate": candidate_index,
                "period_days_rounded": period,
                "period_days_rounded_err": period_err,
                "depth_ppm_rounded": depth,
                "depth_ppm_rounded_err": depth_err,
                "planet_radius_rearth_rounded": radius,
                "planet_radius_rearth_rounded_err": radius_err,
                "stellar_radius_rsun_rounded": stellar_radius,
                "stellar_radius_rsun_rounded_err": stellar_radius_err,
                "semi_major_axis_au_rounded": semi_major_axis,
                "semi_major_axis_au_rounded_err": semi_major_axis_err,
                "insolation_earth_rounded": insolation,
                "insolation_earth_rounded_err": insolation_err,
                "equilibrium_temperature_k_rounded": teq,
                "equilibrium_temperature_k_rounded_err": teq_err,
                "chi2_dof": value_after(block, "Chi-squared/DoF"),
                "snr": value_after(block, "SNR ="),
                "odd_even_statistic": odd_even_value,
                "odd_even_significance_percent": odd_even_sig,
                "core_aperture_correlation_statistic": core_statistic,
                "core_aperture_correlation_significance_percent": core_significance,
                "halo_aperture_correlation_statistic": halo_statistic,
                "halo_aperture_correlation_significance_percent": halo_significance,
                "core_halo_ratio": value_after(block, "Ratio ="),
                "shorter_period_statistic": shorter_value,
                "shorter_period_significance_percent": shorter_sig,
                "longer_period_statistic": longer_value,
                "longer_period_significance_percent": longer_sig,
                "false_alarm_probability": value_after(block, "False Alarm"),
                "transit_count": value_after(block, "Transit Count"),
                "max_mes_pdf": value_after(block, "Max Multiple Event Statistic"),
            }
            row.update(parse_offset_group(block, "Joint Offsets Relative to Tic Position", "joint"))
            row.update(parse_offset_group(block, "Multi-Sector Offsets Relative to TIC Position", "multi_sector"))
            rows.append(row)

    return rows, {"pdfminer_available": True, "n_dvr_files": len(dvr_files)}


def best_spoc_candidate(transit_rows):
    candidates = [
        r
        for r in transit_rows
        if r.get("tce_index") == 1 and r.get("product_kind") == "multi_sector" and r.get("relation_to_official") == "official_period"
    ]
    if not candidates:
        candidates = [r for r in transit_rows if r.get("relation_to_official") == "official_period"]
    if not candidates:
        return None
    return sorted(candidates, key=lambda r: (r.get("sector_stop") or -1, r.get("max_mes") or -1), reverse=True)[0]


def build_comparison(config, official, transit_rows, pdf_rows):
    local = config["transit"]
    official_params = official["official_planet_candidate_parameters"]
    best = best_spoc_candidate(transit_rows)
    comparison = {
        "local_corrected_120s": {
            "period_days": local["period"],
            "epoch_btjd": local["t0"],
            "depth_ppm": local["depth_ppm"],
            "rp_rs": local["rp_rs"],
            "rp_earth": local["rp_earth"],
            "duration_hours": local["duration_hrs"],
            "impact_parameter": local["impact_parameter"],
        },
        "official_toi": official_params,
        "spoc_dv_best_machine_readable": best,
        "interpretation": "SPOC DV products are independent pipeline products. They support the corrected deep-transit scale when their TCE period matches the official TOI ephemeris, but they do not constitute RV confirmation.",
    }
    if best:
        comparison["deltas_spoc_minus_local"] = {
            "period_days": best.get("period_days") - local["period"] if best.get("period_days") is not None else None,
            "epoch_days": best.get("epoch_btjd") - local["t0"] if best.get("epoch_btjd") is not None else None,
            "depth_ppm": best.get("depth_ppm") - local["depth_ppm"] if best.get("depth_ppm") is not None else None,
            "duration_hours": best.get("duration_hours") - local["duration_hrs"] if best.get("duration_hours") is not None else None,
            "rp_rs": best.get("rp_rs") - local["rp_rs"] if best.get("rp_rs") is not None else None,
            "rp_earth": best.get("rp_earth") - local["rp_earth"] if best.get("rp_earth") is not None else None,
        }
        comparison["relative_deltas_spoc_minus_local"] = {
            "depth_fraction": comparison["deltas_spoc_minus_local"]["depth_ppm"] / local["depth_ppm"] if comparison["deltas_spoc_minus_local"].get("depth_ppm") is not None else None,
            "rp_earth_fraction": comparison["deltas_spoc_minus_local"]["rp_earth"] / local["rp_earth"] if comparison["deltas_spoc_minus_local"].get("rp_earth") is not None else None,
        }

    pdf_best = None
    if best:
        matches = [
            r
            for r in pdf_rows
            if r.get("product_label") == best.get("product_label") and r.get("planet_candidate") == best.get("tce_index")
        ]
        if matches:
            pdf_best = matches[0]
    comparison["spoc_dv_best_pdf_dashboard"] = pdf_best
    return comparison


def write_markdown(summary, comparison, transit_rows, pdf_rows):
    lines = []
    lines.append("# SPOC DV Extraction Summary")
    lines.append("")
    lines.append(f"DVT FITS files: {summary['n_dvt_files']}")
    lines.append(f"DVR PDFs: {summary['n_dvr_files']}")
    lines.append(f"Machine-readable TCE rows: {summary['n_tce_rows']}")
    lines.append("")
    lines.append("## Key Result")
    lines.append("")
    best = comparison.get("spoc_dv_best_machine_readable")
    pdf_best = comparison.get("spoc_dv_best_pdf_dashboard")
    if best:
        lines.append(
            "The best multi-sector SPOC DV TCE matching the official TOI ephemeris is "
            f"{best['product_label']} TCE {best['tce_index']}: "
            f"P={best['period_days']:.8f} d, depth={best['depth_ppm']:.1f} ppm, "
            f"Rp={best['rp_earth']:.2f} Rearth, MES={best['max_mes']:.1f}."
        )
    if pdf_best:
        lines.append(
            "The corresponding DVR dashboard reports rounded values "
            f"depth={pdf_best.get('depth_ppm_rounded'):.0f}+/-{pdf_best.get('depth_ppm_rounded_err'):.0f} ppm, "
            f"Rp={pdf_best.get('planet_radius_rearth_rounded'):.1f}+/-{pdf_best.get('planet_radius_rearth_rounded_err'):.1f} Rearth, "
            f"SNR={pdf_best.get('snr'):.1f}."
        )
        if pdf_best.get("joint_offset_distance_arcsec") is not None:
            lines.append(
                "The DVR dashboard reports a joint centroid offset distance of "
                f"{pdf_best.get('joint_offset_distance_arcsec'):.2f}+/-{pdf_best.get('joint_offset_distance_err_arcsec'):.2f} arcsec "
                f"({pdf_best.get('joint_offset_distance_sigma'):.2f} sigma)."
            )
    lines.append("")
    lines.append("## TCE Inventory")
    lines.append("")
    lines.append("| Product | Kind | TCE | Relation | Period (d) | Depth (ppm) | Rp (Rearth) | MES |")
    lines.append("|---|---|---:|---|---:|---:|---:|---:|")
    for row in sorted(transit_rows, key=lambda r: (r.get("sector_start") or 9999, r.get("sector_stop") or 9999, r.get("tce_index") or 0)):
        lines.append(
            f"| {row.get('product_label')} | {row.get('product_kind')} | {row.get('tce_index')} | "
            f"{row.get('relation_to_official')} | {row.get('period_days'):.6f} | "
            f"{row.get('depth_ppm'):.1f} | {row.get('rp_earth'):.2f} | {row.get('max_mes'):.1f} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append("These SPOC DV products independently support the corrected several-thousand-ppm depth scale for the official-period TCEs. Single-sector DV products can prefer aliases or unrelated lower-SNR TCEs, so the multi-sector official-period products should be emphasized. This remains vetting evidence, not RV confirmation.")
    SUMMARY_MD.write_text("\n".join(lines) + "\n")


def main():
    OUT.mkdir(exist_ok=True)
    config = load_json(CONFIG_PATH)
    official = load_json(OFFICIAL_TOI_PATH)

    inventory, transit_rows = parse_dvt_files(config, official)
    pdf_rows, pdf_info = parse_dvr_pdfs()
    comparison = build_comparison(config, official, transit_rows, pdf_rows)

    relation_counts = pd.Series([r["relation_to_official"] for r in transit_rows]).value_counts().to_dict() if transit_rows else {}
    summary = {
        "source": "SPOC Data Validation products downloaded from MAST and parsed from local DVT FITS / DVR PDF files",
        "n_dvt_files": len(inventory),
        "n_dvr_files": pdf_info.get("n_dvr_files"),
        "n_tce_rows": len(transit_rows),
        "n_pdf_dashboard_rows": len(pdf_rows),
        "relation_counts": relation_counts,
        "best_product_label": comparison.get("spoc_dv_best_machine_readable", {}).get("product_label") if comparison.get("spoc_dv_best_machine_readable") else None,
        "key_interpretation": comparison["interpretation"],
        "outputs": {
            "inventory_json": INVENTORY_JSON.name,
            "transit_metrics_csv": TRANSIT_CSV.name,
            "pdf_metrics_csv": PDF_CSV.name,
            "comparison_json": COMPARISON_JSON.name,
            "summary_markdown": SUMMARY_MD.name,
        },
        "pdf_parser": pdf_info,
    }

    INVENTORY_JSON.write_text(json.dumps(inventory, indent=2, default=as_builtin))
    pd.DataFrame(transit_rows).to_csv(TRANSIT_CSV, index=False)
    pd.DataFrame(pdf_rows).to_csv(PDF_CSV, index=False)
    COMPARISON_JSON.write_text(json.dumps(comparison, indent=2, default=as_builtin))
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, default=as_builtin))
    write_markdown(summary, comparison, transit_rows, pdf_rows)

    print(f"Wrote {INVENTORY_JSON}")
    print(f"Wrote {TRANSIT_CSV}")
    print(f"Wrote {PDF_CSV}")
    print(f"Wrote {COMPARISON_JSON}")
    print(f"Wrote {SUMMARY_JSON}")
    print(f"Wrote {SUMMARY_MD}")
    best = comparison.get("spoc_dv_best_machine_readable")
    if best:
        print(
            "Best SPOC DV match: "
            f"{best['product_label']} TCE {best['tce_index']}, "
            f"P={best['period_days']:.8f} d, depth={best['depth_ppm']:.1f} ppm, "
            f"Rp={best['rp_earth']:.2f} Rearth, MES={best['max_mes']:.1f}"
        )


if __name__ == "__main__":
    main()
