import numpy as np
from pathlib import Path

from utils import load_config

ROOT = Path(__file__).parent.parent
c = load_config(ROOT / "data" / "config_corrected_120s.json")
s = c["stellar"]
t = c["transit"]
l = c["limb_darkening"]

print("=" * 55)
print("FINAL VERIFICATION - TOI-3492.01")
print("=" * 55)

print(f"Star:  Teff={s['teff']:.0f} K  log g={s['logg']:.2f}")
print(f"       R={s['r_star']:.3f} Rsun  M={s['m_star']:.3f} Msun")
print(f"       rho={s['rho_star']:.3f} rho_sun (TIC v8)")
print(f"       LDC: u1={l['u1']:.4f}, u2={l['u2']:.4f}")

print(f"\nPlanet:")
print(f"       status = {t.get('status', 'current candidate characterization')}")
print(f"       P = {t['period']:.6f} d")
print(f"       Rp/Rs = {t['rp_rs']:.5f} +/- {t['rp_rs_err']:.5f}")
print(f"       a/Rs  = {t['a_rs']:.2f} +/- {t['a_rs_err']:.2f}")
print(f"       inc   = {t['inc']:.2f} +/- {t['inc_err']:.2f} deg")
print(f"       ecc   = 0.0 (adopted circular photometric solution)")
print(f"       Depth = {t['depth_ppm']:.0f} ppm")
print(f"       Rp    = {t['rp_earth']:.1f} Rearth = {t['rp_earth']/11.21:.2f} Rjup")
print(f"       T14   = {t['duration_hrs']:.2f} hours")

rp = t["rp_rs"]
ar = t["a_rs"]
inc_val = t["inc"]
b = t.get("impact_parameter", ar * np.cos(np.radians(inc_val)))
print(f"\nImpact parameter: b = {b:.3f}")
print(f"Transit condition: b < 1 + Rp/Rs = {1+rp:.3f}  ->  {'PASS' if b < 1+rp else 'FAIL'}")

G_msun = 2942.2062
M = s["m_star"]
R = s["r_star"]
P = t["period"]
ar_pred = (G_msun * M * P**2 / (4 * np.pi**2))**(1/3) / R
delta = abs(ar - ar_pred)
print(f"\nKepler consistency check:")
print(f"  a/Rs (Kepler III) = {ar_pred:.2f}")
print(f"  a/Rs (fitted)     = {ar:.2f}")
print(f"  Delta             = {delta:.2f} ({'CONSISTENT' if delta < 1.5 else 'TENSION'})")

print(f"\nCandidate size: {t['rp_earth']:.1f} Rearth = giant-planet-size regime")
print(f"(Neptune ~4 Re, Saturn ~9 Re, Jupiter ~11 Re)")

print("\nValidation status: unvalidated and not RV-confirmed; no calibrated population FPP is reported")
print("Corrected basic vetting: odd/even and phase-0.5 secondary checks show no obvious EB signature")
print("Gaia/source localization: qualitative geometry only; calibrated PRF and high-resolution imaging missing")
print("TTV analysis: corrected 120s timing is SNR-limited; no TTV detection claimed")

print(f"\n{'-'*55}")
print(f"Pipeline status: {c['pipeline_status']}")
