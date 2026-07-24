import ast
import json
import math
import subprocess
import sys

import pytest


def load_json(root, relative_path):
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def test_s3_03_decision_passes_and_freezes_one_candidate(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    assert decision["status"] == "PASS"
    assert all(decision["gate"]["checks"].values())
    assert decision["scope"]["real_data_fit_executed"] is False
    assert decision["scope"]["real_data_fit_authorized"] is False
    assert decision["scope"]["phase_7_may_begin"] is False
    assert decision["candidate"]["role"] == "PRIMARY_CALIBRATION_CANDIDATE"
    assert decision["candidate"]["adopted_for_real_data"] is False
    assert decision["failed_reference"]["role"] == "FAILED_REFERENCE_ONLY"
    assert decision["failed_reference"]["not_adopted"] is True
    assert decision["branch_universe"]["model_count"] == 24


def test_s3_03_provenance_discloses_postmortem(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    assert decision["scope"]["protocol_not_blind_preregistration"] is True
    assert decision["scope"]["postmortem_informed_architecture"] is True
    cal = decision["s3_04_calibration"]
    assert cal["status"] == "MANDATORY_BEFORE_REAL_DATA"
    assert len(cal["must_calibrate"]) >= 14
    assert cal["failure_action"] == "STOP_NO_REAL_DATA_FIT"
    assert decision["stop_rules"]["no_real_data_before_s3_04_pass"] is True


def test_s3_03_justification_grounded_in_postmortem_findings(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    j = decision["justification"]
    assert "timescale" in j["primary_failure_addressed"].lower()
    assert "boundary" in j["primary_failure_addressed"].lower()
    assert "1.293606" in j["secondary_failure_addressed"] or "beta" in j["secondary_failure_addressed"].lower()
    assert "87" in j["why_not_ou"]
    assert "oscillator" in j["why_not_sho"].lower() or "q=" in j["why_not_sho"].lower()
    assert "sector" in j["timescale_pooling"].lower()
    assert "descriptive" in j["why_not_telemetry_regressors"].lower() or "s3-02" in j["why_not_telemetry_regressors"].lower()


def test_s3_03_24_branch_ids_match_phase5b_exactly(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    phase5b = load_json(root, "outputs/faz5b_remediation.json")
    frozen_ids = sorted(phase5b["handoff"]["model_ids"])
    raw_ids = decision["branch_universe"]["raw_valid"]["cell_ids"]
    ref_ids = decision["branch_universe"]["reference_included"]["cell_ids"]
    reconstructed = sorted(
        "raw_valid::" + cid for cid in raw_ids
    ) + sorted(
        "reference_included::" + cid for cid in ref_ids
    )
    assert reconstructed == frozen_ids
    assert len(raw_ids) == 11
    assert len(ref_ids) == 13
    assert "W26_P0" not in raw_ids
    assert "W26_P0" in ref_ids
    assert "W32_P2" not in raw_ids
    assert "W32_P2" in ref_ids


def test_s3_03_weights_match_phase5b(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    phase5b = load_json(root, "outputs/faz5b_remediation.json")
    weights = phase5b["handoff"]["joint_model_weights"]
    raw_sum = sum(weights[mid] for mid in weights if mid.startswith("raw_valid::"))
    ref_sum = sum(weights[mid] for mid in weights if mid.startswith("reference_included::"))
    assert math.isclose(raw_sum, 0.5, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(ref_sum, 0.5, rel_tol=0, abs_tol=1e-12)
    for mid, w in weights.items():
        if mid.startswith("raw_valid::"):
            assert math.isclose(w, 1.0 / 22, rel_tol=0, abs_tol=1e-12)
        else:
            assert math.isclose(w, 1.0 / 26, rel_tol=0, abs_tol=1e-12)

    branch = decision["branch_universe"]
    assert branch["likelihoods_multiplied"] is False
    assert branch["branch_selection_after_results"] is False


def test_s3_03_phase4_systematic_values_match_frozen(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    phase4 = load_json(root, "outputs/faz4_reduction_comparison.json")
    frozen = phase4["accepted_branch_geometry_comparison"]["between_reduction_systematic"]["values"]
    dval = decision["phase4_reduction_systematic"]["values"]
    for name in ("rp_rs", "a_rs", "impact_parameter", "t14_hours"):
        assert dval[name] == float(frozen[name]["adopted_systematic"])
    ps = decision["phase4_reduction_systematic"]
    assert ps["applied_after_mixture"] is True
    assert ps["applied_to_likelihood_or_beta"] is False
    assert ps["application_count"] == 1


def test_s3_03_timescale_bounds_are_support_derived(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    ts = decision["candidate"]["noise_hierarchy"]["gp_timescale"]
    assert ts["timescale_lower_minutes"] == 4.0
    assert ts["timescale_upper_minutes"] == 780.0
    assert "13 h" in ts["upper_bound_derivation"]
    assert math.isclose(ts["mu_tau_bounds"][0], math.log(4.0), rel_tol=0, abs_tol=1e-12)
    assert math.isclose(ts["mu_tau_bounds"][1], math.log(780.0), rel_tol=0, abs_tol=1e-12)


def test_s3_03_oot_boundary_matches_phase2_t14(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    phase2 = load_json(root, "outputs/faz2_transit_inventory.json")
    t14 = float(phase2["ephemeris_and_windows"]["t14_hours"])
    ingress = float(phase2["ephemeris_and_windows"]["ingress_hours"])
    sep = decision["candidate"]["transit_noise_separation"]
    assert math.isclose(sep["T14_hours"], t14, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(sep["oot_inner_hours"], 0.75 * t14, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(sep["ingress_hours"], ingress, rel_tol=0, abs_tol=1e-12)
    assert sep["oot_inner_definition"] == "0.75 * T14 from event midpoint"


def test_s3_03_noise_hierarchy_fully_specified(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    h = decision["candidate"]["noise_hierarchy"]
    for param_type in ("jitter", "gp_amplitude", "gp_timescale"):
        item = h[param_type]
        assert "transform" in item
        assert any("bounds" in key.lower() for key in item)
    ts = h["gp_timescale"]
    assert ts["timescale_upper_minutes"] >= 780.0
    integ = h["held_sector_integration"]
    assert integ["nodes_per_dimension"] == 5
    assert integ["total_evaluations_per_held_sector"] == 125
    assert len(integ["parameters_integrated"]) == 3
    assert integ["training_map_used_for"] == [
        "mu_j", "mu_A", "mu_tau",
        "delta_{j,train}", "delta_{A,train}", "delta_{tau,train}",
    ]
    jp = h["joint_fit_parameter_count"]
    assert jp["total"] == 24
    assert jp["geometry"] == 3
    lp = h["losofold_parameter_count"]
    assert lp["total_fitted"] == 18
    assert lp["total_integrated"] == 3


def test_s3_03_transit_baseline_and_branches_unchanged(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    prereg = load_json(root, "data/faz5_preregistered_grid.json")
    t = decision["candidate"]["transit_model"]
    assert t["period_days_fixed"] == prereg["transit_model"]["period_days_fixed"]
    assert t["t0_btjd_fixed"] == prereg["transit_model"]["t0_btjd_fixed"]
    assert t["limb_darkening_quadratic_fixed"] == prereg["transit_model"]["limb_darkening_quadratic_fixed"]
    assert t["geometry_uniform_bounds"] == prereg["transit_model"]["geometry_uniform_bounds"]
    b = decision["candidate"]["event_baseline"]
    assert b["coefficient_prior"]["sigma"] == 0.01
    assert b["coefficient_prior"]["distribution"] == "independent normal"


def test_s3_03_reference_k0_is_failed_not_adopted(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    ref = decision["failed_reference"]
    assert ref["id"] == "K0_WHITE_JITTER"
    assert ref["historical_status"] == "FAIL_RESIDUAL_CORRELATION"
    assert math.isclose(ref["historical_maximum_weighted_beta"], 1.2936064512125263, rel_tol=0, abs_tol=1e-12)


def test_s3_03_optimizer_and_computational_sections_populated(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    opt = decision["optimizer"]
    assert opt["reference_implementation"] == "scripts/run_faz6r.py"
    assert opt["analytic_gradient_not_available"] is True
    assert opt["s3_05_must_calibrate"] is True
    cf = decision["computational_feasibility"]
    assert cf["held_sector_quadrature"]["evaluations_per_fold_per_branch"] == 125
    assert cf["screening_workload"]["branches"] == 24
    assert cf["screening_workload"]["folds_per_branch"] == 6
    assert cf["joint_fit_workload"]["parameters"] == 24
    s5 = decision["s3_05_numerical_validation"]
    assert s5["status"] == "REQUIRED_BEFORE_REAL_DATA_AFTER_S3_04"
    assert len(s5["must_verify"]) >= 12
    assert any("quadrature" in item for item in s5["must_verify"])


def test_s3_03_beta_gate_marked_as_provisional(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    rd = decision["residual_diagnostics"]
    assert rd["beta_maximum_allowed"] == 1.2
    assert "s3-04 must calibrate" in rd["beta_gate_provisional"].lower()
    assert rd["thresholds_not_revised_from_observed_beta"] is True
    gates = decision["s3_04_calibration"]["gates_calibrated_not_assumed"]
    assert "residual-beta gate value" in gates


def test_s3_03_kernel_is_single_no_multi_component(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    k = decision["candidate"]["kernel"]
    assert k["family"] == "Matérn-3/2"
    assert k["celerite_term"] == "Matern32Term"
    assert k["eps_fixed"] == 0.01
    assert k["smoothness_fixed"] is True
    # No multi-component or term sum
    assert "sum" not in str(k).lower()
    assert "term_2" not in str(k).lower()


def test_s3_03_telemetry_regressors_are_empty(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    tel = decision["telemetry"]
    assert tel["regressors"] == []
    assert tel["causal_attribution_attempted"] is False


def test_s3_03_stop_rules_are_explicit_and_cascading(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    rules = decision["stop_rules"]
    assert rules["no_branch_sector_or_event_removal"] is True
    assert "versioned amendment" in rules["no_retroactive_s3_03_amendment"].lower()
    assert "candidate-assessment" in rules["on_s3_04_failure"].lower()
    assert "candidate characterization" in rules["on_real_data_failure"].lower()


def test_s3_03_runner_has_no_fit_or_import_of_optimizer(root):
    source = (root / "scripts/build_stage3_model_architecture_decision.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "scipy" not in imports
    assert "batman" not in imports
    assert "celerite" not in imports
    assert "run_faz6r" not in imports


def test_s3_03_runner_verifies_and_refuses_to_clobber(root):
    verify = subprocess.run(
        [sys.executable, "-B", "scripts/build_stage3_model_architecture_decision.py", "--verify-only"],
        cwd=root, check=False, capture_output=True, text=True, timeout=60,
    )
    assert verify.returncode == 0, verify.stderr
    assert "PASS (verified)" in verify.stdout
    no_clobber = subprocess.run(
        [sys.executable, "-B", "scripts/build_stage3_model_architecture_decision.py"],
        cwd=root, check=False, capture_output=True, text=True, timeout=60,
    )
    assert no_clobber.returncode != 0
    assert "no-clobber" in no_clobber.stderr


def test_s3_03_sources_are_referenceable(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    sources = decision["source_integrity"]["sources"]
    for path, item in sources.items():
        assert (root / item["relative_path"]).is_file()
        assert len(item["sha256"]) == 64
    assert "scripts/build_stage3_model_architecture_decision.py" in sources


def test_s3_03_all_transit_parameters_frozen_from_phase5_prereg(root):
    decision = load_json(root, "data/stage3_model_architecture_decision.json")
    prereg = load_json(root, "data/faz5_preregistered_grid.json")
    t = decision["candidate"]["transit_model"]
    g = prereg["transit_model"]
    assert t["shared_parameters"] == g["shared_geometry"]
    assert t["eccentricity_fixed"] == g["eccentricity_fixed"]
    assert t["exposure_seconds"] == g["exposure_seconds"]
    assert t["supersample_factor"] == g["supersample_factor"]
