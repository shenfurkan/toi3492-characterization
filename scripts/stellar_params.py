import numpy as np
import warnings
from astroquery.mast import Catalogs
import ldtk
from utils import load_config, save_config

warnings.filterwarnings("ignore")

print("=" * 60)
print("Phase 1: Stellar Characterization")
print("=" * 60)

CONFIG = load_config()
tic_id = CONFIG["target"]["tic_id"]

print(f"\nQuerying TIC v8 for TIC {tic_id}...")
try:
    tic_data = Catalogs.query_criteria(catalog="Tic", ID=tic_id)
    if len(tic_data) == 0:
        raise ValueError("No TIC entry found")
    star = tic_data[0]
    print(f"  TIC entry found: ID={star['ID']}")
except Exception as e:
    print(f"  TIC query failed: {e}")
    raise RuntimeError(
        "TIC query failed; refusing to overwrite the target configuration "
        "with unrelated fallback values."
    ) from e

def _safe_float(star, col, err_col=None):
    if star is None:
        return None
    try:
        val = star[col]
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        return float(val)
    except (KeyError, ValueError, TypeError):
        return None

if star is not None:
    teff = _safe_float(star, "Teff")
    teff_err = _safe_float(star, "e_Teff")
    logg = _safe_float(star, "logg")
    logg_err = _safe_float(star, "e_logg")
    feh = _safe_float(star, "MH")
    feh_err = _safe_float(star, "e_MH")
    r_star = _safe_float(star, "rad")
    r_star_err = _safe_float(star, "e_rad")
    m_star = _safe_float(star, "mass")
    m_star_err = _safe_float(star, "e_mass")
    tmag = _safe_float(star, "Tmag")
else:
    raise RuntimeError("No TIC target record is available")

missing = []
for name, val in [("Teff", teff), ("logg", logg), ("[Fe/H]", feh),
                   ("Rstar", r_star), ("Mstar", m_star), ("Tmag", tmag)]:
    if val is None:
        missing.append(name)

if missing:
    raise RuntimeError(f"Required TIC fields are missing: {missing}")

teff_e = teff_err if teff_err is not None else 100.0
logg_e = logg_err if logg_err is not None else 0.10
feh_e = feh_err if feh_err is not None else 0.15
r_star_e = r_star_err if r_star_err is not None else 0.05
m_star_e = m_star_err if m_star_err is not None else 0.05

print(f"\nStellar Parameters:")
print(f"  Teff  = {teff:.0f} +/- {teff_e:.0f} K")
print(f"  log g = {logg:.2f} +/- {logg_e:.2f} dex")
print(f"  [Fe/H] = {feh:.2f} +/- {feh_e:.2f} dex")
print(f"  R*    = {r_star:.3f} +/- {r_star_e:.3f} Rsun")
print(f"  M*    = {m_star:.3f} +/- {m_star_e:.3f} Msun")
print(f"  Tmag  = {tmag:.1f}")

Msun_kg = 1.98847e30
Rsun_m = 6.957e8
rho_star_cgs = (m_star * Msun_kg) / ((4.0 / 3.0) * np.pi * (r_star * Rsun_m) ** 3)
rho_star_sun = rho_star_cgs / (Msun_kg / ((4.0 / 3.0) * np.pi * Rsun_m ** 3))
rho_err = rho_star_sun * np.sqrt((m_star_e / m_star) ** 2 + (3 * r_star_e / r_star) ** 2)

print(f"\n  Stellar density: {rho_star_sun:.3f} +/- {rho_err:.3f} rho_sun")
print(f"                    = {rho_star_cgs/1000:.2f} +/- {rho_err*rho_star_cgs/1000/rho_star_sun:.2f} g/cm^3")

print("\nComputing limb darkening coefficients via ExoMol LDTk...")
print("  (First run downloads ~23MB of stellar model grids; subsequent runs use cache.)")

try:
    creator = ldtk.LDPSetCreator(
        teff=(teff, teff_e),
        logg=(logg, logg_e),
        z=(feh, feh_e),
        filters=[ldtk.tess],
        verbose=False,
    )
    profiles = creator.create_profiles(nsamples=200)
    profiles.fit_limb()
    coeffs, coeffs_err = profiles.coeffs_qd()
    u1 = float(coeffs[0, 0])
    u2 = float(coeffs[0, 1])
    u1_err = float(coeffs_err[0, 0])
    u2_err = float(coeffs_err[0, 1])
    ldc_source = "ExoMol LDTk (Claret 2016/2017 PHOENIX models, TESS bandpass)"
    print(f"  u1 = {u1:.6f} +/- {u1_err:.6f}")
    print(f"  u2 = {u2:.6f} +/- {u2_err:.6f}")
except Exception as e:
    raise RuntimeError(
        "LDTk failed; refusing to substitute approximate limb-darkening "
        "coefficients."
    ) from e

CONFIG["stellar"].update({
    "teff": teff, "teff_err": teff_e,
    "logg": logg, "logg_err": logg_e,
    "feh": feh, "feh_err": feh_e,
    "r_star": r_star, "r_star_err": r_star_e,
    "m_star": m_star, "m_star_err": m_star_e,
    "rho_star": rho_star_sun, "rho_star_err": rho_err,
    "tmag": tmag,
})

CONFIG["limb_darkening"].update({
    "u1": u1, "u1_err": u1_err,
    "u2": u2, "u2_err": u2_err,
    "source": ldc_source,
})

CONFIG["pipeline_status"]["stellar_params"] = True
save_config(CONFIG)

G_msun = 2942.2062
P_guess = 9.22
a_rs_predicted = (G_msun * m_star * P_guess**2 / (4 * np.pi**2)) ** (1.0 / 3.0) / r_star
a_rs_unc = a_rs_predicted * np.sqrt(
    (m_star_e / (3 * m_star)) ** 2 + (r_star_e / r_star) ** 2
)
print(f"\nPredicted a/Rs from Kepler III (P=9.22d): {a_rs_predicted:.2f} +/- {a_rs_unc:.2f}")
print("  -> Catalog comparison only; the adopted circular transit fit uses no stellar-density prior.")
print("\nPhase 1 complete.\n")
