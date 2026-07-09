import numpy as np
import corner
from pathlib import Path
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
samples = np.load(ROOT / "data" / "toi3492_chains_120s_corrected.npy")

fig = plt.figure(figsize=(10, 10))
fig = corner.corner(
    samples,
    fig=fig,
    labels=["Rp/Rs", "a/Rs", "b", "baseline"],
    show_titles=True,
    quantiles=[0.16, 0.5, 0.84],
    title_fmt=".5f",
    title_kwargs={"fontsize": 10},
    label_kwargs={"labelpad": 20, "fontsize": 11},
    max_n_ticks=3,
)

fig.subplots_adjust(top=0.95, bottom=0.1, left=0.1, right=0.95, hspace=0.1, wspace=0.1)

fig.savefig(
    ROOT / "figures" / "toi3492_corner_120s_corrected.png", dpi=160
)
plt.close(fig)
print("Re-plotted corner plot with larger figure size and smaller font.")
