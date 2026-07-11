from astropy.io import fits
from pathlib import Path
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')

dv_base = Path('data/spoc_dv/mastDownload/TESS')
dvt_files = sorted(dv_base.rglob('*dvt.fits'))
print(f'Found {len(dvt_files)} DVT files\n')

all_sector_data = {}

for dvt_path in dvt_files:
    fname = dvt_path.name
    # Extract sector number from filename
    parts = fname.split('-')
    sector_part = [p for p in parts if p.startswith('s0')]
    sector = sector_part[0] if sector_part else 'unknown'

    with fits.open(dvt_path) as hdul:
        # Print ALL primary header keywords
        hdr = hdul[0].header
        hdr_dict = dict(hdr)
        
        print(f'=== {fname} | {sector} ===')
        # Key vetting keywords
        key_groups = {
            'Centroid': ['CENT', 'DROW', 'DCOL', 'OFFSET'],
            'Transit': ['PERIOD', 'EPOCH', 'TDUR', 'DEPTH', 'RPLANET'],
            'Stats': ['MES', 'SES', 'CHASES', 'ROBSTAT', 'BOOTFAP'],
            'Star': ['CROWDSAP', 'FLFRCSAP', 'TMAG', 'TESSMAG'],
            'Ghost': ['GHOST', 'SIGPINK'],
        }
        
        for group, keywords in key_groups.items():
            found = {k: v for k, v in hdr_dict.items() 
                    if any(kw in k.upper() for kw in keywords)}
            if found:
                print(f'  [{group}]')
                for k, v in found.items():
                    print(f'    {k}: {v}')
        
        # Also check each extension header
        for i, ext in enumerate(hdul):
            ehdr = ext.header
            cent_kws = {k: v for k, v in dict(ehdr).items() 
                       if any(x in k.upper() for x in ['CENT', 'OFFSET', 'DROW', 'DCOL'])}
            if cent_kws:
                print(f'  [Ext {i} {ext.name} centroid keywords]')
                for k, v in cent_kws.items():
                    print(f'    {k}: {v}')
        print()

print('\nDone.')
