import argparse
import lightkurve as lk
import matplotlib.pyplot as plt
import numpy as np
import warnings
from utils import load_config

warnings.filterwarnings("ignore")

parser = argparse.ArgumentParser()
parser.add_argument(
    "--allow-nonadopted-screening",
    action="store_true",
    help="Run an exploratory periodogram that cannot support a rotation claim",
)
args = parser.parse_args()
if not args.allow_nonadopted_screening:
    parser.error(
        "This script is quarantined. Pass --allow-nonadopted-screening only "
        "for method development; no rotation result may be adopted."
    )

print("=" * 60)
print("Phase 4: Stellar Rotation Analysis (Multi-Sector)")
print("=" * 60)

CONFIG = load_config()
target = "TIC 81077799"

print(f"\nQuerying TESS SPOC data for {target}...")
search_result = lk.search_lightcurve(target, author="SPOC")
n_sectors = len(search_result)
print(f"Found {n_sectors} sectors: {list(search_result.mission)}")

if n_sectors == 0:
    print("No data found. Aborting.")
    exit(1)

detected_periods = []
detected_powers = []

for i in range(min(n_sectors, 5)):
    print(f"\n  Sector {i+1}/{min(n_sectors,5)}...")
    try:
        lc = search_result[i].download()
    except Exception as e:
        print(f"    Download failed: {e}")
        continue

    lc_clean = lc.remove_nans().normalize().remove_outliers(
        sigma_upper=3, sigma_lower=10
    )

    pg = lc_clean.to_periodogram(method="lombscargle",
                                  minimum_period=1, maximum_period=20)
    best_p = pg.period_at_max_power.value
    best_power = pg.max_power.value
    detected_periods.append(best_p)
    detected_powers.append(best_power)
    print(f"    Best period: {best_p:.2f} d (power={best_power:.2f})")

detected_periods = np.array(detected_periods)
detected_powers = np.array(detected_powers)

if len(detected_periods) > 0:
    mean_period = np.average(detected_periods, weights=detected_powers)
    std_period = np.sqrt(np.average((detected_periods - mean_period)**2,
                                     weights=detected_powers))
    print(f"\nWeighted peak summary: {mean_period:.2f} +/- {std_period:.2f} days")
else:
    raise RuntimeError("No finite exploratory periodogram peaks were produced")

ref_sector_label = str(search_result[0].mission[0]) if len(search_result) > 0 else "index 0"
print(f"\nWindow function analysis ({ref_sector_label})...")
try:
    lc_ref = search_result[0].download()
    lc_ref = lc_ref.remove_nans().normalize()
    t_span = lc_ref.time.value[-1] - lc_ref.time.value[0]
    print(f"  Time span: {t_span:.1f} days")
    pg_win = lc_ref.to_periodogram(method="lombscargle",
                                    minimum_period=0.5, maximum_period=30)
except Exception as e:
    print(f"  Window function failed: {e}")
    pg_win = None

fig, axes = plt.subplots(2, 1, figsize=(10, 8))

ax1 = axes[0]
lc_ref = search_result[0].download()
lc_clean = lc_ref.remove_nans().normalize().remove_outliers(sigma_upper=3, sigma_lower=10)
ax1.scatter(lc_clean.time.value, lc_clean.flux.value, s=1, alpha=0.5, color="black")
ax1.set_ylabel("Normalized Flux")
ax1.set_title(f"TIC 81077799 — Unflattened Light Curve ({ref_sector_label})")

ax2 = axes[1]
p_fine = np.linspace(1, 20, 5000)
pg_full = lc_clean.to_periodogram(method="lombscargle",
                                    minimum_period=1, maximum_period=20)
ax2.plot(pg_full.period.value, pg_full.power.value, "k-", linewidth=1, alpha=0.5)
ax2.axvline(mean_period, color="red", linestyle="--",
            label=f"Weighted peak = {mean_period:.2f} +/- {std_period:.2f} d")
ax2.set_xlabel("Period (days)")
ax2.set_ylabel("Lomb-Scargle Power")
ax2.set_title("Exploratory Periodogram - No Rotation Detection Claimed")
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("figures/toi3492_stellar_rotation.png", dpi=150)
plt.close(fig)
print("Saved: figures/toi3492_stellar_rotation.png")

print("\nExploratory non-adopted screening complete.\n")
