import json

import pytest

from exonym.vetting.centroid import centroid_gate, centroid_offset_z
from exonym.vetting.oddeven import odd_even_gate, odd_even_z
from exonym.vetting.tricera_parse import fpp_gate, load_fpp_report


def test_centroid_offset_z_uses_cos_dec():
    z = centroid_offset_z(ra_offset_arcsec=0.0, dec_offset_arcsec=3.0, dec_deg=0.0, sigma_arcsec=1.0)
    assert z == pytest.approx(3.0)
    z_on_target = centroid_offset_z(0.5, 0.5, 0.0, 1.0)
    assert z_on_target < 3.0


def test_centroid_gate_threshold():
    passed, z = centroid_gate(0.1, 0.1, 0.0, 1.0)
    assert passed and z < 3.0
    failed, z = centroid_gate(3.0, 0.0, 0.0, 1.0)
    assert not failed and z >= 3.0


def test_centroid_requires_positive_sigma():
    with pytest.raises(ValueError):
        centroid_offset_z(0.0, 0.0, 0.0, 0.0)


def test_odd_even_z():
    z = odd_even_z(100.0, 10.0, 90.0, 10.0)
    assert z == pytest.approx(0.7071, abs=1e-3)
    assert odd_even_gate(100.0, 10.0, 90.0, 10.0)[0] is True
    assert odd_even_gate(100.0, 5.0, 70.0, 5.0)[0] is False


def test_fpp_gate_dict_and_value():
    report = {"fpp": 0.005, "nfpp": 0.0}
    passed, fpp = fpp_gate(report)
    assert passed and fpp == pytest.approx(0.005)
    assert fpp_gate(0.02)[0] is False


def test_fpp_report_probes_common_keys(tmp_path):
    path = tmp_path / "triceratops.json"
    path.write_text(json.dumps({"FPP_specific": 0.008}), encoding="utf-8")
    report = load_fpp_report(path)
    assert fpp_gate(report)[0] is True


def test_fpp_missing_value_raises(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"note": "no fpp"}), encoding="utf-8")
    with pytest.raises(ValueError, match="no FPP"):
        fpp_gate(load_fpp_report(path))
