"""
archive_enrichment.py
Gathers and saves all publicly-available external data for TOI-3492.01 / HD 96519:
  1. Gaia DR3 RVS radial velocity + GSP-Phot stellar parameters
  2. HD catalog spectral type (F7IV/V)
  3. SPOC DV contamination ratio from the DVT/LC FITS files
  4. Exports a combined JSON for use in the paper
"""
import json
import numpy as np
from pathlib import Path
from astroquery.gaia import Gaia
from astropy.io import fits
import warnings
warnings.filterwarnings('ignore')

ROOT = Path(__file__).parent.parent
OUT = ROOT / 'outputs' / 'archive_enrichment.json'

# -------------------------------------------------------------------------
# 1.  Gaia DR3 full record
# -------------------------------------------------------------------------
print('Querying Gaia DR3...')
query = """
SELECT source_id, ra, dec, parallax, parallax_error,
       pmra, pmra_error, pmdec, pmdec_error,
       radial_velocity, radial_velocity_error, rv_nb_transits,
       teff_gspphot, teff_gspphot_lower, teff_gspphot_upper,
       logg_gspphot, logg_gspphot_lower, logg_gspphot_upper,
       mh_gspphot,   mh_gspphot_lower,   mh_gspphot_upper,
       azero_gspphot,
       non_single_star, ruwe, duplicated_source,
       phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag
FROM gaiadr3.gaia_source
WHERE source_id = 5347362071701193344
"""
job = Gaia.launch_job(query)
r = job.get_results()

gaia = {col: (float(r[col][0]) if r[col][0] is not None else None) for col in r.colnames}
# Override non-float fields
gaia['non_single_star'] = int(r['non_single_star'][0])
gaia['duplicated_source'] = bool(r['duplicated_source'][0])

print(f"  Gaia RVS: {gaia['radial_velocity']:.3f} +/- {gaia['radial_velocity_error']:.3f} km/s  (N={int(gaia['rv_nb_transits'])})")
print(f"  Gaia GSP-Phot: Teff={gaia['teff_gspphot']:.0f} K, logg={gaia['logg_gspphot']:.3f}, [M/H]={gaia['mh_gspphot']:.3f}")
print(f"  Distance (1/plx): {1000/gaia['parallax']:.1f} pc")
print(f"  RUWE={gaia['ruwe']:.3f}, non_single_star={gaia['non_single_star']}, dup={gaia['duplicated_source']}")

# -------------------------------------------------------------------------
# 2.  HD catalog info (from VizieR query already done; hard-code verified values)
# -------------------------------------------------------------------------
hd_catalog = {
    'hd_number': 'HD 96519',
    'spectral_type_hd': 'F7IV/V',
    'spectral_type_source': 'HD Catalog (Cannon & Pickering); confirmed by Gaia logg=3.85',
    'note': 'IV/V subgiant classification independently confirms evolved-star nature'
}
print(f"\n  HD catalog: {hd_catalog['hd_number']} ({hd_catalog['spectral_type_hd']})")

# -------------------------------------------------------------------------
# 3.  SPOC DV CROWDSAP / FLFRCSAP from LC FITS headers
# -------------------------------------------------------------------------
print('\nReading SPOC LC headers for contamination...')
lc_search = list((ROOT / 'data').rglob('toi3492_120s_reference.csv'))

# Actually get CROWDSAP from the SPOC FITS directly via lightkurve cache
import lightkurve as lk
sr = lk.search_lightcurve('TIC 81077799', author='SPOC', exptime=120)
crowdsap_vals = []
flfrcsap_vals = []
for i in range(len(sr)):
    try:
        lc = sr[i].download()
        cs = lc.meta.get('CROWDSAP', None)
        ff = lc.meta.get('FLFRCSAP', None)
        s  = lc.meta.get('SECTOR', i)
        if cs is not None:
            crowdsap_vals.append({'sector': int(s), 'CROWDSAP': float(cs), 'FLFRCSAP': float(ff) if ff else None})
            print(f'  Sector {s}: CROWDSAP={cs:.4f}, FLFRCSAP={ff:.4f}')
    except Exception as e:
        print(f'  Sector {i}: {e}')

contamination = {
    'crowdsap_per_sector': crowdsap_vals,
    'crowdsap_mean': float(np.mean([x['CROWDSAP'] for x in crowdsap_vals])) if crowdsap_vals else None,
    'crowdsap_note': 'CROWDSAP = fraction of flux from target; 1-CROWDSAP = contamination fraction',
    'exofop_contamination_ratio': 0.019471,
    'exofop_note': 'ExoFOP SPOC pipeline contamination ratio for the 2-min aperture'
}

# -------------------------------------------------------------------------
# 4.  Combine and save
# -------------------------------------------------------------------------
result = {
    'target': 'TOI-3492.01 / TIC 81077799 / HD 96519',
    'gaia_dr3': gaia,
    'hd_catalog': hd_catalog,
    'tess_spoc_contamination': contamination,
    'notes': [
        'Gaia RVS RV is a mean over 13 transits; single-epoch precision only, not a mass constraint.',
        'Gaia GSP-Phot Teff (6061 K) differs from TIC Stassun+2019 Teff (6332 K) by 271 K.',
        'Gaia logg=3.85 independently confirms subgiant nature despite TIC lumclass=DWARF.',
        'HD spectral type F7IV/V further supports evolved classification.',
        'No RAVE DR6 match within 5 arcsec.',
        'No GALAH DR3 match within 5 arcsec (GALAH coverage limited).',
    ]
}

OUT.write_text(json.dumps(result, indent=2))
print(f'\nSaved to {OUT}')
print('\n=== SUMMARY FOR PAPER ===')
print(f"HD 96519, F7IV/V, Gaia RV = {gaia['radial_velocity']:.2f}+/-{gaia['radial_velocity_error']:.2f} km/s")
print(f"Gaia GSP-Phot: Teff={gaia['teff_gspphot']:.0f} K, logg={gaia['logg_gspphot']:.2f}, [M/H]={gaia['mh_gspphot']:.3f}")
if crowdsap_vals:
    print(f"Mean CROWDSAP = {contamination['crowdsap_mean']:.4f} -> contamination = {1-contamination['crowdsap_mean']:.4f}")
