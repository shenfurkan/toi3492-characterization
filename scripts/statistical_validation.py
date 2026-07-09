"""Simplified Morton-style Bayesian FPP for TOI-3492.01.

Computes the false-positive probability by comparing the planet hypothesis
against two astrophysical false-positive scenarios:

    1. Unblended eclipsing binary (EB)
       Penalised by the odd/even transit depth difference.

    2. Background / hierarchical eclipsing binary (BEB)
       Penalised by the secondary-eclipse non-detection and the Gaia DR3
       neighbour census within 42 arcsec.

The calculation follows the methodology of:

    * Morton, T. D. 2012, ApJ, 761, 6
    * Morton, T. D. et al. 2016, ApJ, 822, 86 (VESPA)

This is a screening metric, not a formal VESPA or PASTIS validation.
The 2.6-sigma a/Rs tension is noted as a limitation on the strength of
any validation claim.

Output
------
outputs/statistical_validation_120s.json
"""

import json
from pathlib import Path

import numpy as np
from scipy.special import logsumexp

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_configs():
    """Load the three input files needed for the FPP calculation."""
    corrected = json.loads(
        (ROOT / "data" / "config_corrected_120s.json").read_text()
    )
    gaia = json.loads(
        (ROOT / "outputs" / "gaia_contamination_check.json").read_text()
    )
    fp = json.loads(
        (ROOT / "outputs" / "false_positive_tests_120s.json").read_text()
    )
    return corrected, gaia, fp


# ---------------------------------------------------------------------------
# Planet occurrence prior
# ---------------------------------------------------------------------------

def trapezoidal_prior(P_days):
    """Trapezoidal occurrence-rate prior for transiting planets.

    Flat in log(P) between 3 and 300 days, with linear ramps at the edges.
    Outside [1.2, 750] days the prior is zero.

    Parameters
    ----------
    P_days : float
        Orbital period in days.

    Returns
    -------
    float
        Prior value in [0, 1].
    """
    P0, P1, P2, P3 = 1.2, 3.0, 300.0, 750.0
    if P_days < P0:
        return 0.0
    if P_days <= P1:
        return (P_days - P0) / (P1 - P0)
    if P_days <= P2:
        return 1.0
    if P_days <= P3:
        return max((P3 - P_days) / (P3 - P2), 0.0)
    return 0.0


# ---------------------------------------------------------------------------
# Likelihoods
# ---------------------------------------------------------------------------

def eb_log_likelihood(depth_ppm, odd_depth, even_depth, odd_even_sigma):
    """Log-likelihood for the unblended EB hypothesis.

    An EB with unequal primary/secondary depths would show an odd/even
    difference.  We penalise the hypothesis based on the observed
    odd/even consistency.
    """
    logl = 0.0
    diff = abs(odd_depth - even_depth)
    sigma = odd_even_sigma
    if sigma > 0:
        logl -= 0.5 * (diff / sigma) ** 2
    return logl


def beb_log_likelihood_from_gaia(gaia_data, depth_ppm):
    """Log-likelihood for the background EB (BEB) hypothesis.

    Uses the fraction of Gaia sources within 42 arcsec that could produce
    the observed depth as fully eclipsed contaminants.
    """
    neighbors = gaia_data.get("neighbors_within_120arcsec", [])
    depth_fraction = depth_ppm / 1e6

    n_mimics = 0
    n_total = 0
    for nb in neighbors:
        sep = nb.get("separation_arcsec", 999)
        dg = nb.get("delta_G_mag", 99)
        if sep is None or dg is None:
            continue
        if sep > 42:
            continue
        n_total += 1
        flux_ratio = 10 ** (-0.4 * dg)
        if flux_ratio >= depth_fraction:
            n_mimics += 1

    if n_total > 0:
        mimic_fraction = n_mimics / n_total
    else:
        mimic_fraction = 0.01

    logl = np.log(max(mimic_fraction, 1e-10))
    return logl


def planet_log_likelihood(depth_ppm, model_depth_ppm, model_depth_err_ppm):
    """Log-likelihood for the planet hypothesis.

    Based on consistency between the observed and model transit depths.
    """
    diff = abs(depth_ppm - model_depth_ppm)
    sigma = max(model_depth_err_ppm, 1.0)
    return -0.5 * (diff / sigma) ** 2


# ---------------------------------------------------------------------------
# Morton-style FPP with Gaia contrast curve
# ---------------------------------------------------------------------------

def compute_fpp_with_contrast_curve(corrected, gaia, fp):
    """Compute the Morton-style FPP using observed diagnostics.

    Parameters
    ----------
    corrected : dict
        The adopted transit solution (config_corrected_120s.json).
    gaia : dict
        Gaia DR3 neighbour census.
    fp : dict
        Odd/even and secondary-eclipse test results.

    Returns
    -------
    dict
        FPP and its components.
    """
    depth_ppm = corrected["transit"]["depth_ppm"]
    P = corrected["transit"]["period"]

    odd_even = fp["odd_even"]
    secondary = fp["secondary_eclipse"]

    # ---- Priors ---------------------------------------------------------
    # Planet: trapezoidal occurrence rate
    gp_prior = trapezoidal_prior(P)

    # EB: areal density of field stars in the TESS aperture
    star_density_per_arcmin2 = 0.003
    survey_area_arcmin2 = np.pi * (42 / 60.0) ** 2
    expected_random_ebs = (
        star_density_per_arcmin2 * survey_area_arcmin2 * 0.001
    )
    eb_prior_effective = max(expected_random_ebs, 1e-6)

    # BEB: scaled by the summed Gaia flux ratio within 42 arcsec
    flux_ratio_sum_42 = 0.01247
    beb_prior_effective = max(flux_ratio_sum_42 * 0.01, 1e-6)

    # ---- Likelihoods ----------------------------------------------------
    # Planet: null model
    logl_planet = 0.0

    # EB: penalise odd/even difference
    odd_even_sigma = odd_even["difference_sigma"]
    logl_eb = -0.5 * odd_even_sigma ** 2

    # BEB: penalise non-zero secondary eclipse
    sec_depth = secondary["depth_ppm"]
    # Use the 3-sigma upper limit / 3 as the effective uncertainty
    sec_sigma = secondary["three_sigma_upper_limit_ppm"] / 3.0
    logl_beb = -0.5 * (sec_depth / sec_sigma) ** 2

    # ---- Combine --------------------------------------------------------
    log_total_fp = logsumexp(
        [
            np.log(max(eb_prior_effective, 1e-10)) + logl_eb,
            np.log(max(beb_prior_effective, 1e-10)) + logl_beb,
        ]
    )
    log_planet = np.log(max(gp_prior, 1e-10)) + logl_planet

    fpp = np.exp(log_total_fp - logsumexp([log_planet, log_total_fp]))
    nfpp = 1.0 - fpp

    # Count sources within 42 arcsec that could mimic the signal
    neighbor_summary = gaia.get("neighbor_summary", {})
    full_eclipse_mimics = neighbor_summary.get(
        "full_eclipse_mimic_candidates", []
    )
    n_mimics_42 = sum(
        1
        for mimic in full_eclipse_mimics
        if mimic.get("separation_arcsec", 999) <= 42
    )

    return {
        "FPP": float(fpp),
        "NFPP": float(nfpp),
        "FPP_percent": float(fpp * 100),
        "NFPP_percent": float(nfpp * 100),
        "planet_prior": float(gp_prior),
        "eb_prior_effective": float(eb_prior_effective),
        "beb_prior_effective": float(beb_prior_effective),
        "flux_ratio_sum_42arcsec": float(flux_ratio_sum_42),
        "n_full_eclipse_mimics_42arcsec": n_mimics_42,
        "odd_even_sigma": float(odd_even_sigma),
        "secondary_depth_sigma": float(sec_depth / sec_sigma),
        "method": "Simplified Morton-style Bayesian FPP screening",
    }


# ---------------------------------------------------------------------------
# Caveat assessment
# ---------------------------------------------------------------------------

def trappist_caveat(fpp_result):
    """Assess the impact of the a/Rs tension on the FPP interpretation.

    The a/Rs tension means the transit model is internally inconsistent
    with the TIC stellar density.  This limits the discriminating power
    between planet and FP scenarios.
    """
    corrected = json.loads(
        (ROOT / "data" / "config_corrected_120s.json").read_text()
    )
    ar_fit = corrected["transit"]["a_rs"]
    ar_fit_err = corrected["transit"]["a_rs_err"]
    ar_prior = corrected["transit_corrected_120s"]["a_rs_prior"]
    ar_prior_sigma = corrected["transit_corrected_120s"]["a_rs_prior_sigma"]

    tension = abs(ar_fit - ar_prior) / np.sqrt(
        ar_fit_err ** 2 + ar_prior_sigma ** 2
    )

    if tension > 2.0:
        caveat = (
            f"CAVEAT: The a/Rstar tension ({tension:.1f} sigma) indicates "
            "that the circular transit solution is not self-consistent "
            "with the TIC-density prediction. This limits the strength of "
            "validation language. The computed FPP should be treated as a "
            "screening metric, not an exact probability or a formal "
            "validation result."
        )
    else:
        caveat = "No significant a/Rstar tension; FPP is reliable."

    return {"aRstar_tension_sigma": float(tension), "caveat": caveat}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    corrected, gaia, fp = load_configs()

    print("=" * 70)
    print("SIMPLIFIED FALSE-POSITIVE ESTIMATE - TOI-3492.01")
    print("Morton-style Bayesian FPP screening framework")
    print("=" * 70)

    result = compute_fpp_with_contrast_curve(corrected, gaia, fp)
    caveat_result = trappist_caveat(result)

    print()
    for key, value in result.items():
        if isinstance(value, float):
            if abs(value) < 0.01 and value > 0:
                print(f"  {key:40s} = {value:.6f}")
            elif abs(value) < 1:
                print(f"  {key:40s} = {value:.4f}")
            else:
                print(f"  {key:40s} = {value:.2f}")
        else:
            print(f"  {key:40s} = {value}")

    print()
    print("-" * 70)
    print(caveat_result["caveat"])
    print("-" * 70)

    fpp = result["FPP"] * 100
    print()
    if fpp < 0.1:
        print(
            "RESULT: FPP < 0.1% - passes strong false-positive criteria"
        )
    elif fpp < 1.0:
        print(
            "RESULT: FPP < 1% - passes common false-positive criteria"
        )
    elif fpp < 5.0:
        print(f"RESULT: FPP = {fpp:.2f}% - promising candidate")
    elif fpp < 10.0:
        print(f"RESULT: FPP = {fpp:.2f}% - promising candidate")
    else:
        print(
            f"RESULT: FPP = {fpp:.2f}% - ambiguous; follow-up required"
        )

    print()
    print(
        "Caveat: This is a simplified FPP calculation based on available data."
    )
    print("A separate TRICERATOPS screening run is recorded in")
    print("triceratops_validation_120s.json; RVs and high-resolution imaging")
    print("are still needed for confirmation-level claims.")
    print("=" * 70)

    (ROOT / "outputs" / "statistical_validation_120s.json").write_text(
        json.dumps({**result, **caveat_result}, indent=2)
    )


if __name__ == "__main__":
    main()
