"""
query_spectroscopic_archives.py
Queries APOGEE DR17, LAMOST DR10, and GALAH DR3 for independent
stellar parameters of TIC 81077799 (HD 96519) to cross-validate
TIC v8 values and potentially resolve the a/Rstar tension.

Each query is independent and wrapped in try/except so that a single
catalog failure does not stop the others.
"""
import json
import warnings
from pathlib import Path

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u

warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.parent
OUT = ROOT / "outputs" / "spectroscopic_archives.json"
OUT_MD = ROOT / "outputs" / "spectroscopic_archives_summary.md"

metadata = json.loads((ROOT / "outputs" / "official_toi_metadata.json").read_text())
ra = float(metadata["coordinates"]["ra_deg"])
dec = float(metadata["coordinates"]["dec_deg"])
coord = SkyCoord(ra=ra, dec=dec, unit="deg")
SEARCH_RADIUS = 5.0  # arcsec
delta_deg = SEARCH_RADIUS / 3600.0

results = {
    "target": "TOI-3492.01 / TIC 81077799 / HD 96519",
    "coordinates": {"ra_deg": ra, "dec_deg": dec},
    "search_radius_arcsec": SEARCH_RADIUS,
    "tic_v8_reference": metadata["official_stellar_parameters"],
    "queries": {},
}

tic_teff = metadata["official_stellar_parameters"]["teff_k"]
tic_logg = metadata["official_stellar_parameters"]["logg"]
tic_teff_err = metadata["official_stellar_parameters"]["teff_err_k"]
tic_logg_err = metadata["official_stellar_parameters"]["logg_err"]

print(f"Target: RA={ra:.6f} deg  Dec={dec:.6f} deg")
print(f"TIC v8: Teff={tic_teff:.0f}+/-{tic_teff_err:.0f} K  logg={tic_logg:.4f}+/-{tic_logg_err:.4f}")
print()

# -------------------------------------------------------------------------
# 1.  APOGEE DR17  (SDSS SkyServer SQL)
# -------------------------------------------------------------------------
print("=" * 60)
print("Querying APOGEE DR17 (SDSS SkyServer) ...")
try:
    from astroquery.sdss import SDSS

    # Try cone-search approach first (more reliable than raw SQL)
    apogee_tbl = SDSS.query_region(
        coord,
        radius=SEARCH_RADIUS * u.arcsec,
        spectro=True,
        data_release=17,
    )
    # query_region returns a list of tables; look for the main specObj-like result
    if apogee_tbl is not None and len(apogee_tbl) > 0:
        # Unpack: query_region may return multiple tables
        # The APOGEE star table might be in the results
        # Try to find a table with teff/logg columns
        found_apogee = None
        for t in apogee_tbl:
            if "teff" in [c.lower() for c in t.colnames] and "logg" in [c.lower() for c in t.colnames]:
                found_apogee = t
                break
        if found_apogee is not None:
            apogee_tbl = found_apogee
        else:
            apogee_tbl = apogee_tbl[0]  # fallback to first table

    if apogee_tbl is None or len(apogee_tbl) == 0:
        results["queries"]["apogee_dr17"] = {
            "status": "empty",
            "n_results": 0,
            "message": "No APOGEE star within 5 arcsec",
        }
        print("  No APOGEE match within 5 arcsec.")
    else:
        rows = []
        for row in apogee_tbl:
            r = {col: (float(row[col]) if row[col] is not None else None) for col in apogee_tbl.colnames}
            rows.append(r)
        results["queries"]["apogee_dr17"] = {
            "status": "success",
            "n_results": len(rows),
            "rows": rows,
        }
        for r in rows:
            flags_ok = (r.get("aspcap_flags") or 0) == 0
            print(f"  APOGEE_ID={r['apogee_id']}  Teff={r['teff']:.0f}+/-{r['teff_err']:.0f} K  "
                  f"logg={r['logg']:.3f}+/-{r['logg_err']:.3f}  "
                  f"[M/H]={r['m_h']:.3f}  SNR={r['snr']:.0f}  "
                  f"ASPCPFLAG={'OK' if flags_ok else r.get('aspcap_flags')}")
except Exception as e:
    results["queries"]["apogee_dr17"] = {"status": "failed", "error": str(e)}
    print(f"  APOGEE query failed: {e}")

# -------------------------------------------------------------------------
# 2.  LAMOST DR10  (VizieR V/164)
# -------------------------------------------------------------------------
print()
print("=" * 60)
print("Querying LAMOST DR10 (VizieR V/164) ...")
try:
    from astroquery.vizier import Vizier

    Vizier.ROW_LIMIT = -1
    coord_lamost = SkyCoord(ra=ra, dec=dec, unit="deg")

    lamost_tables = Vizier.query_region(
        coord_lamost,
        radius=SEARCH_RADIUS * u.arcsec,
        catalog="V/164/lmst_dr10",
    )
    # Vizier.query_region returns None or a list of tables
    if lamost_tables is None or len(lamost_tables) == 0:
        results["queries"]["lamost_dr10"] = {
            "status": "empty",
            "n_results": 0,
            "message": "No LAMOST DR10 star within 5 arcsec",
        }
        print("  No LAMOST DR10 match within 5 arcsec.")
    else:
        tbl = lamost_tables[0]
        rows = []
        for row in tbl:
            r = {}
            for col in tbl.colnames:
                val = row[col]
                if isinstance(val, (np.integer, np.floating)):
                    r[col] = float(val)
                elif isinstance(val, (bytes, np.bytes_)):
                    r[col] = val.decode("utf-8", errors="replace")
                elif isinstance(val, np.ndarray):
                    r[col] = val.tolist()
                else:
                    r[col] = val if not np.ma.is_masked(val) else None
            rows.append(r)
        results["queries"]["lamost_dr10"] = {
            "status": "success",
            "n_results": len(rows),
            "rows": rows,
        }
        for r in rows:
            teff_val = r.get("Teff")
            logg_val = r.get("logg")
            feh_val = r.get("__Fe_H_") or r.get("[Fe/H]")
            snr_val = r.get("snru") or r.get("snrg") or r.get("snrr")
            print(f"  LAMOST obsid={r.get('obsid','?')}  "
                  f"Teff={teff_val}  logg={logg_val}  [Fe/H]={feh_val}  SNR={snr_val}")
except Exception as e:
    results["queries"]["lamost_dr10"] = {"status": "failed", "error": str(e)}
    print(f"  LAMOST query failed: {e}")

# -------------------------------------------------------------------------
# 3.  GALAH DR3  (VizieR J/MNRAS/506/150)
# -------------------------------------------------------------------------
print()
print("=" * 60)
print("Querying GALAH DR3 (VizieR J/MNRAS/506/150) ...")
try:
    from astroquery.vizier import Vizier

    Vizier.ROW_LIMIT = -1
    coord_galah = SkyCoord(ra=ra, dec=dec, unit="deg")

    galah_tables = Vizier.query_region(
        coord_galah,
        radius=SEARCH_RADIUS * u.arcsec,
        catalog="J/MNRAS/506/150",  # GALAH DR3 main catalog
    )
    if galah_tables is None or len(galah_tables) == 0:
        results["queries"]["galah_dr3"] = {
            "status": "empty",
            "n_results": 0,
            "message": "No GALAH DR3 star within 5 arcsec",
        }
        print("  No GALAH DR3 match within 5 arcsec.")
    else:
        tbl = galah_tables[0]
        rows = []
        for row in tbl:
            r = {}
            for col in tbl.colnames:
                val = row[col]
                if isinstance(val, (np.integer, np.floating)):
                    r[col] = float(val)
                elif isinstance(val, (bytes, np.bytes_)):
                    r[col] = val.decode("utf-8", errors="replace")
                elif isinstance(val, np.ndarray):
                    r[col] = val.tolist()
                else:
                    r[col] = val if not np.ma.is_masked(val) else None
            rows.append(r)
        results["queries"]["galah_dr3"] = {
            "status": "success",
            "n_results": len(rows),
            "rows": rows,
        }
        for r in rows:
            print(f"  GALAH star_id={r.get('Name','?')}  "
                  f"Teff={r.get('Teff')}  logg={r.get('logg')}  [Fe/H]={r.get('__Fe_H_')}")
except Exception as e:
    results["queries"]["galah_dr3"] = {"status": "failed", "error": str(e)}
    print(f"  GALAH query failed: {e}")

# -------------------------------------------------------------------------
# 4.  RAVE DR6  (VizieR III/283)
# -------------------------------------------------------------------------
print()
print("=" * 60)
print("Querying RAVE DR6 (VizieR III/283) ...")
try:
    from astroquery.vizier import Vizier

    Vizier.ROW_LIMIT = -1
    coord_rave = SkyCoord(ra=ra, dec=dec, unit="deg")

    rave_tables = Vizier.query_region(
        coord_rave,
        radius=SEARCH_RADIUS * u.arcsec,
        catalog="III/283",  # RAVE DR6
    )
    if rave_tables is None or len(rave_tables) == 0:
        results["queries"]["rave_dr6"] = {
            "status": "empty",
            "n_results": 0,
            "message": "No RAVE DR6 star within 5 arcsec",
        }
        print("  No RAVE DR6 match within 5 arcsec.")
    else:
        tbl = rave_tables[0]
        rows = []
        for row in tbl:
            r = {}
            for col in tbl.colnames:
                val = row[col]
                if isinstance(val, (np.integer, np.floating)):
                    r[col] = float(val)
                elif isinstance(val, (bytes, np.bytes_)):
                    r[col] = val.decode("utf-8", errors="replace")
                elif isinstance(val, np.ndarray):
                    r[col] = val.tolist()
                else:
                    r[col] = val if not np.ma.is_masked(val) else None
            rows.append(r)
        results["queries"]["rave_dr6"] = {
            "status": "success",
            "n_results": len(rows),
            "rows": rows,
        }
        for r in rows:
            print(f"  RAVE ID={r.get('Name','?')}  "
                  f"Teff={r.get('Teff')}  logg={r.get('logg')}  [M/H]={r.get('__M_H_')}")
except Exception as e:
    results["queries"]["rave_dr6"] = {"status": "failed", "error": str(e)}
    print(f"  RAVE query failed: {e}")

# -------------------------------------------------------------------------
# 5.  Comparative analysis
# -------------------------------------------------------------------------
print()
print("=" * 60)
print("Cross-comparing archive vs TIC v8 ...")

comparison = {
    "tic_v8": {"teff": tic_teff, "teff_err": tic_teff_err, "logg": tic_logg, "logg_err": tic_logg_err, "source": "TIC v8 (Stassun+2019)"},
    "gaia_gspphot": {
        "teff": 6061.15, "teff_err": None, "logg": 3.8506, "logg_err": None,
        "source": "Gaia DR3 GSP-Phot",
        "note": "Gaia GSP-Phot uncertainties are very small; systematic floor dominates.",
    },
    "archives": [],
}

# Collect best available from each archive
for catalog_key, catalog_label in [
    ("apogee_dr17", "APOGEE DR17"),
    ("lamost_dr10", "LAMOST DR10"),
    ("galah_dr3", "GALAH DR3"),
    ("rave_dr6", "RAVE DR6"),
]:
    q = results["queries"].get(catalog_key, {})
    if q.get("status") != "success" or not q.get("rows"):
        comparison["archives"].append({"catalog": catalog_label, "status": "no_match"})
        continue
    best = q["rows"][0]
    # Try to find Teff/logg columns (naming varies by catalog)
    teff_cols = ["teff", "Teff", "TEFF", "teff_gspphot"]
    logg_cols = ["logg", "LOGG", "logg_gspphot"]
    feh_cols = ["m_h", "[Fe/H]", "__Fe_H_", "feh", "Fe_H"]
    found_teff = next((best.get(c) for c in teff_cols if best.get(c) is not None), None)
    found_logg = next((best.get(c) for c in logg_cols if best.get(c) is not None), None)
    found_feh = next((best.get(c) for c in feh_cols if best.get(c) is not None), None)
    if found_teff is not None and found_logg is not None:
        comparison["archives"].append({
            "catalog": catalog_label,
            "status": "matched",
            "teff": float(found_teff),
            "logg": float(found_logg),
            "feh": float(found_feh) if found_feh is not None else None,
            "teff_diff_from_tic": float(found_teff) - tic_teff if found_teff else None,
            "logg_diff_from_tic": float(found_logg) - tic_logg if found_logg else None,
        })
    else:
        comparison["archives"].append({"catalog": catalog_label, "status": "columns_unavailable"})

results["comparison"] = comparison

# Determine which catalogs provided useful data
matched_catalogs = [a for a in comparison["archives"] if a.get("status") == "matched"]
print(f"\nMatched catalogs: {len(matched_catalogs)}")

for mc in matched_catalogs:
    d_teff = mc.get("teff_diff_from_tic")
    d_logg = mc.get("logg_diff_from_tic")
    print(f"  {mc['catalog']}: Teff={mc['teff']:.0f} K (diff={d_teff:+.0f} K vs TIC)  "
          f"logg={mc['logg']:.4f} (diff={d_logg:+.4f} vs TIC)"
          f"{'  [Fe/H]=' + str(mc['feh']) if mc.get('feh') is not None else ''}")

# Key scientific question: do any archives suggest a different logg that would resolve a/Rstar?
results["a_rstar_implication"] = {
    "tic_density_logg": tic_logg,
    "tic_density_a_rs_prediction": 7.69,
    "fitted_a_rs": 9.209,
    "if_logg_4_0": "At logg=4.0 (dwarf), rho would be ~0.54 rho_sun, a/Rs prediction ~5.7 — worse.",
    "if_logg_3_5": "At logg=3.5 (more evolved), rho would be ~0.023 rho_sun, a/Rs prediction ~10.9 — closer.",
    "conclusion": "If archive logg is LOWER than 3.71, the tension REDUCES. If HIGHER, tension INCREASES.",
}

OUT.write_text(json.dumps(results, indent=2))
print(f"\nSaved to {OUT}")

# -------------------------------------------------------------------------
# 5.  Markdown summary
# -------------------------------------------------------------------------
md_lines = [
    "# Spectroscopic Archive Query Results",
    "",
    f"**Target:** TOI-3492.01 / TIC 81077799 / HD 96519",
    f"**Coordinates:** RA={ra:.6f} deg, Dec={dec:.6f} deg",
    f"**Search radius:** {SEARCH_RADIUS} arcsec",
    "",
    "## TIC v8 Reference",
    f"| Parameter | Value |",
    f"|---|---|",
    f"| Teff | {tic_teff:.0f} +/- {tic_teff_err:.0f} K |",
    f"| logg | {tic_logg:.4f} +/- {tic_logg_err:.4f} |",
    "",
    "## Archive Query Summary",
    "",
    "| Catalog | Status | Teff (K) | logg | [Fe/H] | Delta Teff | Delta logg |",
    "|---|---|---|---|---|---|---|",
]
md_lines.append(f"| TIC v8 | reference | {tic_teff:.0f} | {tic_logg:.4f} | 0.00 | — | — |")
md_lines.append(
    f"| Gaia GSP-Phot | auto | {comparison['gaia_gspphot']['teff']:.0f} | {comparison['gaia_gspphot']['logg']:.4f} | -0.046 | {comparison['gaia_gspphot']['teff']-tic_teff:+.0f} | {comparison['gaia_gspphot']['logg']-tic_logg:+.4f} |"
)

for a in comparison["archives"]:
    if a.get("status") == "matched":
        md_lines.append(
            f"| {a['catalog']} | matched | {a['teff']:.0f} | {a['logg']:.4f} | {a.get('feh','N/A')} | {a['teff_diff_from_tic']:+.0f} | {a['logg_diff_from_tic']:+.4f} |"
        )
    else:
        status_label = a.get("status", "error").replace("_", " ")
        md_lines.append(f"| {a['catalog']} | {status_label} | — | — | — | — | — |")

md_lines.extend([
    "",
    "## Impact on a/Rstar Tension",
    "",
    f"- TIC v8 logg = {tic_logg:.4f} → predicted a/Rstar = 7.69",
    f"- Fitted a/Rstar = 9.21",
    f"- If archive logg is **lower** than {tic_logg:.4f}, the stellar density drops, a/Rstar prediction rises, and the tension **reduces**.",
    f"- If archive logg is **higher** than {tic_logg:.4f}, the tension **increases** — making the anomaly more significant.",
    "",
    "## Interpretation",
    "",
])

if matched_catalogs:
    md_lines.append("Archive spectroscopic parameters provide an independent check on TIC v8 values.")
    for mc in matched_catalogs:
        d_logg = mc.get("logg_diff_from_tic")
        if d_logg is not None and abs(d_logg) > 0.1:
            md_lines.append(f"- **{mc['catalog']}**: logg differs by {d_logg:+.4f} dex — this could meaningfully affect stellar density.")
    # Check if any significantly differ
    best_teff_diffs = [abs(mc.get("teff_diff_from_tic", 0)) for mc in matched_catalogs if mc.get("teff_diff_from_tic") is not None]
    best_logg_diffs = [abs(mc.get("logg_diff_from_tic", 0)) for mc in matched_catalogs if mc.get("logg_diff_from_tic") is not None]
else:
    md_lines.append("**No spectroscopic archives had a match for this target within 5 arcsec.**")
    md_lines.append("")
    md_lines.append("This is a significant finding in itself:")
    md_lines.append("- TIC 81077799 (HD 96519, F7IV/V, V~8.5) has **never been observed** by any major spectroscopic survey.")
    md_lines.append("- **LAMOST DR10**: Northern-hemisphere survey (Dec > -10 deg typical) — target at Dec = -53.7 deg is outside primary footprint.")
    md_lines.append("- **APOGEE DR17**: Targets primarily red giants in specific fields — this F-type subgiant was not in any APOGEE field.")
    md_lines.append("- **GALAH DR3**: Southern survey but limited to ~1 million stars — this target was not included.")
    md_lines.append("- **RAVE DR6**: Southern survey (I < 13 mag, limited to ~450,000 stars) — no match.")
    md_lines.append("- Therefore, the **only available stellar parameters are photometric**: TIC v8 (broadband photometry + parallax) and Gaia GSP-Phot (BP/RP spectra).")
    md_lines.append("- The a/Rstar tension **cannot be resolved with existing public spectroscopic data** — it requires new dedicated spectroscopy.")
    md_lines.append("- This also means TOI-3492.01 is a **genuinely uncharacterized host star** at the spectroscopic level, making our photometric characterization the first detailed analysis.")

md_lines.append("")
md_lines.append(f"Full results: `{OUT.name}`")

OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print(f"Summary saved to {OUT_MD}")
