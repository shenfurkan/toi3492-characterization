"""Export preregistered 120-s PDCSAP observing blocks for pySYD."""

from pathlib import Path

import numpy as np

from asteroseismic_search import BLOCKS, ROOT, collect


OUT_DIR = ROOT / "data" / "asteroseismology" / "pysyd"
RESULT_DIR = ROOT / "outputs" / "pysyd"
INFO_DIR = OUT_DIR / "info"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    INFO_DIR.mkdir(parents=True, exist_ok=True)
    # pySYD caches generated spectra beside the light curves. Remove them when
    # regenerating inputs so a changed flux-unit convention cannot go stale.
    for cached_spectrum in OUT_DIR.glob("*_PS.txt"):
        cached_spectrum.unlink()
    per_sector = collect("PDCSAP_FLUX", 120)
    for block, sectors in BLOCKS.items():
        time = np.concatenate([per_sector[sector][0] for sector in sectors])
        flux = np.concatenate([per_sector[sector][1] for sector in sectors])
        name = block.replace("+", "p")
        path = OUT_DIR / f"{name}_LC.txt"
        # pySYD 6.10.5 multiplies input flux by 1e6 during PSD normalization,
        # despite its input documentation labeling the light-curve unit ppm.
        np.savetxt(path, np.column_stack((time, flux / 1e6)), fmt="%.10f %.12f")
        print(f"Wrote {path} ({len(time)} points)")


if __name__ == "__main__":
    main()
