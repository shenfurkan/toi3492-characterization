import ast
import json
import math
import subprocess
import sys

import pytest


def load_json(root, relative_path):
    return json.loads((root / relative_path).read_text(encoding="utf-8"))


def test_s3_04a_protocol_passes_without_seeing_data(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    assert protocol["status"] == "PASS"
    assert all(protocol["gate"]["checks"].values())
    assert protocol["scope"]["synthetic_results_observed"] is False
    assert protocol["scope"]["real_data_fit_executed"] is False
    assert protocol["scope"]["phase_7_may_begin"] is False


def test_s3_04a_all_12_classes_defined(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    classes = protocol["simulation_classes"]
    assert len(classes) == 12
    names = [item["name"] for item in classes]
    assert names[0] == "C01_white_jitter_transit"
    assert names[1] == "C02_m1_160_transit"
    assert "C06_ou_160_misspec" in names
    assert "C07_sho_160_misspec" in names
    assert "C11_no_transit_null" in names
    assert "C12_near_boundary_tau4" in names


def test_s3_04a_total_requested_positive(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    total = protocol["requested_total"]
    assert total > 0
    assert total == sum(item["requested_count"] for item in protocol["simulation_classes"])
    assert total >= 180


def test_s3_04a_every_class_has_geometry_and_metrics(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    for item in protocol["simulation_classes"]:
        assert "noise_family" in item
        assert "noise_parameters" in item
        assert "inject_transit" in item or "inject_transit" in str(item)
        eval_items = item["evaluation"]["measured_quantities"]
        assert "rp_rs_bias" in eval_items
        assert "rp_rs_coverage_68" in eval_items
        assert "transit_depth_attenuation_fraction" in eval_items
        assert "k0_selected" in eval_items
        assert "m1_selected" in eval_items


def test_s3_04a_deterministic_seed_scheme(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    seeds = protocol["deterministic_seeds"]
    assert seeds["base_seed"] == 349204
    assert "independent of worker count" in seeds["scheme"]


def test_s3_04a_geometry_injection_broad_not_centered_on_target(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    c01 = protocol["simulation_classes"][0]
    geom = c01["geometry_injection"]
    assert geom["target_values_not_used"] is True
    assert geom["rp_rs"]["bounds"] == [0.03, 0.09]
    assert geom["a_rs"]["bounds"] == [5.0, 16.0]
    assert "0.055" in str(geom["target_values_listed_for_audit_only"])


def test_s3_04a_threshold_derivation_frozen_before_results(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    tdr = protocol["threshold_derivation_rules"]
    assert "bias_tolerance" in tdr
    assert "2 * standard_deviation" in tdr["bias_tolerance"]
    assert "coverage_acceptance" in tdr
    assert "0.50" in tdr["coverage_acceptance"]
    assert "0.85" in tdr["coverage_acceptance"]


def test_s3_04a_calibration_failure_rules_explicit(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    failure = protocol["calibration_failure"]
    assert len(failure["conditions"]) >= 6
    assert "do not run s3-07" in failure["action"].lower()
    assert "partial_completion" in failure


def test_s3_04a_provisional_gates_listed_as_uncalibrated(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    gates = protocol["provisional_gate_thresholds"]
    assert gates["predictive"]["delta_elpd"]["calibrated_from_synthetic"] is True
    assert gates["transit"]["rp_rs"]["derived_from_synthetic"] is True
    assert gates["model_selection"]["false_m1_rate_on_white_max"] == 0.10
    assert gates["model_selection"]["true_m1_rate_on_m1_minimum"] == 0.70


def test_s3_04a_runner_no_fit_imports(root):
    source = (root / "scripts/build_stage3_synthetic_calibration_protocol.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert "scipy" not in imports
    assert "celerite" not in imports
    assert "batman" not in imports


def test_s3_04a_runner_verifies_and_refuses_clobber(root):
    verify = subprocess.run(
        [sys.executable, "-B", "scripts/build_stage3_synthetic_calibration_protocol.py", "--verify-only"],
        cwd=root, check=False, capture_output=True, text=True, timeout=60,
    )
    assert verify.returncode == 0, verify.stderr
    no_clobber = subprocess.run(
        [sys.executable, "-B", "scripts/build_stage3_synthetic_calibration_protocol.py"],
        cwd=root, check=False, capture_output=True, text=True, timeout=60,
    )
    assert no_clobber.returncode != 0


def test_s3_04a_sources_referenceable(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    for path, item in protocol["source_integrity"]["sources"].items():
        assert (root / item["relative_path"]).is_file()
        assert len(item["sha256"]) == 64


def test_s3_04a_data_reuse_declares_timestamps_not_flux(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    dr = protocol["data_reuse"]
    assert "real flux values are not used" in dr["cadence_timestamps"].lower()


def test_s3_04a_single_latent_per_both_masks(root):
    protocol = load_json(root, "data/stage3_synthetic_calibration_protocol.json")
    pipeline = protocol["generative_pipeline"]
    assert "one latent realization" in pipeline["step_5_flux"].lower()
    assert "both masks" in pipeline["step_5_flux"].lower()
