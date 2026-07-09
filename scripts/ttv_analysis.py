import numpy as np
import matplotlib.pyplot as plt
import batman
from pathlib import Path
from scipy.optimize import minimize
from utils import load_config
import pandas as pd
import json

print("=" * 60)
print("Phase 3: Transit Timing Analysis on Corrected 120s Light Curve (SNR-limited)")
print("=" * 60)

CONFIG = load_config(path=Path(__file__).parent.parent / "data" / "config_corrected_120s.json")
df = pd.read_csv(Path(__file__).parent.parent / "data" / "toi3492_120s_reference.csv")
df = df.dropna(subset=["time", "flux"])
t_all = df["time"].to_numpy(float)
f_all = df["flux"].to_numpy(float)
f_err_all = np.full_like(f_all, 0.002)  # approx uniform err; TTV only needs rough timing

period = CONFIG["transit"]["period"]
t0_ref = CONFIG["transit"]["t0"]
rp_rs = CONFIG["transit"]["rp_rs"]
a_rs = CONFIG["transit"]["a_rs"]
inc = CONFIG["transit"]["inc"]
u1 = CONFIG["limb_darkening"]["u1"]
u2 = CONFIG["limb_darkening"]["u2"]

depth_ppm = rp_rs ** 2 * 1e6
print(f"Period: {period:.6f} d, T0: {t0_ref:.6f} BJD")
print(f"Transit depth: {depth_ppm:.0f} ppm, a/Rs={a_rs:.2f}, inc={inc:.2f}")

print(f"\nWARNING: Individual-transit timing is SNR-limited in the 120s light curve.")
print(f"Use the 5-year phase-folded fit (Phase 2) for robust parameters.")
print(f"Proceeding with timing fits for completeness, but results are noise-dominated.")

def get_model(t_points, t0_local):
    params = batman.TransitParams()
    params.t0 = t0_local
    params.per = period
    params.rp = rp_rs
    params.a = a_rs
    params.inc = inc
    params.ecc = 0.0
    params.w = 90.0
    params.u = [u1, u2]
    params.limb_dark = "quadratic"
    m = batman.TransitModel(params, t_points)
    return m.light_curve(params)

N_min = int(np.floor((t_all.min() - t0_ref) / period))
N_max = int(np.ceil((t_all.max() - t0_ref) / period))

epochs = []
t_obs = []
t_calc = []
t_err = []

for N in range(N_min, N_max + 1):
    t_expected = t0_ref + N * period
    mask = (t_all > t_expected - 0.35) & (t_all < t_expected + 0.35)
    t_window = t_all[mask]
    f_window = f_all[mask]
    f_err_window = f_err_all[mask]
    if len(t_window) < 30:
        continue

    def objective(t0_guess):
        model = get_model(t_window, t0_guess[0])
        return np.sum(((f_window - model) / f_err_window) ** 2)

    try:
        res = minimize(objective, [t_expected], method="Nelder-Mead",
                       options={"maxiter": 2000})
    except Exception:
        continue

    t0_fit = res.x[0]
    eps = 1e-5 * period
    obj_c = objective([t0_fit])
    obj_p = objective([t0_fit + eps])
    obj_m = objective([t0_fit - eps])
    d2 = (obj_p - 2 * obj_c + obj_m) / (eps ** 2)
    sigma_t0 = np.sqrt(2.0 / d2) if d2 > 0 else 0.01
    sigma_t0 = np.clip(sigma_t0, 0.002, 0.03)

    epochs.append(N)
    t_calc.append(t_expected)
    t_obs.append(t0_fit)
    t_err.append(sigma_t0)

epochs = np.array(epochs)
t_calc = np.array(t_calc)
t_obs = np.array(t_obs)
t_err = np.array(t_err)

oc_minutes = (t_obs - t_calc) * 24 * 60
oc_err_minutes = t_err * 24 * 60
rms_oc = np.sqrt(np.mean(oc_minutes ** 2))
mean_unc = np.mean(oc_err_minutes)

print(f"\nDetected {len(epochs)} transits (of {N_max-N_min+1} expected)")
print(f"O-C RMS: {rms_oc:.0f} min (mean unc: {mean_unc:.1f} min)")
print(f"-> Per-sector timing is noise-dominated; no reliable TTVs.")

fig, ax = plt.subplots(figsize=(10, 5))
ax.errorbar(epochs, oc_minutes, yerr=oc_err_minutes, fmt="o",
            color="gray", markeredgecolor="black", capsize=3, alpha=0.6)
ax.axhline(0, color="red", linestyle="--")
ax.set_xlabel("Transit Epoch N")
ax.set_ylabel("O-C (minutes)")
ax.set_title(f"TOI-3492.01 TTV check on corrected 120s light curve ({depth_ppm:.0f} ppm)\n"
             f"N={len(epochs)} transits, RMS={rms_oc:.0f} min - no reliable TTV detection claimed")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("figures/toi3492_ttv_plot.png", dpi=150)
plt.close(fig)

result = {
    "source": "Corrected 120s SPOC reference light curve; individual timing is SNR-limited",
    "period_days": float(period),
    "t0_btjd": float(t0_ref),
    "depth_ppm": float(depth_ppm),
    "n_transits_fit": int(len(epochs)),
    "oc_rms_minutes": float(rms_oc),
    "mean_uncertainty_minutes": float(mean_unc),
    "claim": "No reliable TTV detection claimed",
}
out_path = Path(__file__).parent.parent / "outputs" / "ttv_analysis_120s.json"
out_path.write_text(json.dumps(result, indent=2))
print("\nPhase 3 complete.\n")
