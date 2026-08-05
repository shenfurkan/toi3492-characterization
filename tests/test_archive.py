import json
import shutil
from unittest.mock import MagicMock, patch

import pytest

from exonym.__main__ import main
from exonym.archive import ArchivalVettingService, run_archival_vetting
from exonym.workspace import load_candidate


def _setup_repo(tmp_path):
    for name in (
        "docs/01_intake_manifest.md",
        "docs/02_feasibility_report.md",
        "docs/03_spoc_dv_vetting.md",
        "docs/04_tfop_sg_followup.md",
    ):
        path = tmp_path / "templates" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("- [ ] [MANDATORY] task\n", encoding="utf-8")
    (tmp_path / "templates/decisions/review_gate.md").parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "templates/decisions/review_gate.md").write_text(
        "- [ ] [MANDATORY] task\n", encoding="utf-8"
    )
    (tmp_path / "templates/protocols").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates/tracking").mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas").mkdir(parents=True, exist_ok=True)
    for name in ("candidate.schema.json", "provenance.schema.json", "claim.schema.json"):
        shutil.copy2("schemas/{0}".format(name), tmp_path / "schemas" / name)
    (tmp_path / "requirements-lock.txt").write_text(
        "numpy==1.26.4\nscipy==1.13.1\n", encoding="utf-8"
    )
    return tmp_path


def test_query_gaia_astrometry_mock():
    service = ArchivalVettingService()
    mock_gaia_data = {
        "data": [
            ["1234567890", 10.0, 20.0, 12.5, 1.85, 0.0],
            ["1234567891", 10.001, 20.001, 15.2, 1.10, 4.5],
        ]
    }
    with patch.object(service, "_http_get_json", return_value=mock_gaia_data):
        res = service.query_gaia_astrometry(10.0, 20.0, radius_arcsec=10.0)
        assert res["ruwe"] == 1.85
        assert res["suspected_binary"] is True
        assert res["nearby_sources_count"] == 2
        assert len(res["sources"]) == 2


def test_query_gaia_falls_back_to_tap_when_astroquery_fails():
    service = ArchivalVettingService()
    esa_rows = {"data": [["111", 10.0, 20.0, 12.5, 1.05, 0.5]]}
    with patch(
        "astroquery.gaia.Gaia.cone_search_async", side_effect=RuntimeError("archive down")
    ), patch.object(service, "_http_get_json", return_value=esa_rows):
        res = service.query_gaia_astrometry(10.0, 20.0, radius_arcsec=10.0)
    assert res["backend"] == "esa-tap"
    assert res["validated"] is True
    assert res["nearby_sources_count"] == 1
    assert res["ruwe"] == 1.05


def test_query_gaia_validation_rejects_incomplete_backend():
    service = ArchivalVettingService()
    stale = {"data": [["111", 10.0, 20.0, 15.0, 1.1, 25.0]]}
    complete = {
        "data": [
            ["222", 10.0, 20.0, 12.5, 1.02, 0.1],
            ["333", 10.001, 20.001, 14.0, 1.3, 8.0],
        ]
    }
    responses = iter([stale, complete])
    with patch(
        "astroquery.gaia.Gaia.cone_search_async", side_effect=RuntimeError("archive down")
    ), patch.object(service, "_gaia_sources_vizier", return_value=[]), patch.object(
        service, "_http_get_json", side_effect=lambda url: next(responses)
    ):
        res = service.query_gaia_astrometry(10.0, 20.0, radius_arcsec=30.0)
    assert res["backend"] == "gaia-mirror"
    assert res["validated"] is True
    assert res["nearby_sources_count"] == 2
    assert res["ruwe"] == 1.02


def test_query_gaia_flags_unvalidated_when_no_backend_sees_target():
    service = ArchivalVettingService()
    stale = {"data": [["111", 10.0, 20.0, 15.0, 1.1, 25.0]]}
    with patch(
        "astroquery.gaia.Gaia.cone_search_async", side_effect=RuntimeError("archive down")
    ), patch.object(service, "_gaia_sources_vizier", return_value=[]), patch.object(
        service, "_http_get_json", return_value=stale
    ):
        res = service.query_gaia_astrometry(10.0, 20.0, radius_arcsec=30.0)
    assert res["validated"] is False
    assert res["backend"] == "esa-tap"
    assert res["nearby_sources_count"] == 1


def test_query_exofop_metadata_mock():
    service = ArchivalVettingService()
    mock_exofop_data = {
        "coordinates": {"ra": 150.0, "dec": 30.0},
        "imaging": [
            {"type": "AO", "instrument": "NIRC2"},
            {"type": "Speckle", "instrument": "NESSI"},
        ],
        "spectroscopy": [
            {"type": "Recon", "instrument": "TRES"},
        ],
    }
    with patch.object(service, "_http_get_json", return_value=mock_exofop_data):
        res = service.query_exofop_metadata("123456789")
        assert res["has_imaging"] is True
        assert res["imaging_records_count"] == 2
        assert res["has_spectroscopy"] is True
        assert res["spectroscopy_records_count"] == 1
        assert "AO" in res["imaging_types"]


def test_synthesize_archival_report(tmp_path):
    repo = _setup_repo(tmp_path)
    root = ["--root", str(repo)]
    assert main(root + ["init", "test-candidate", "--toi", "123.01", "--tic", "987654321"]) == 0

    workspace = load_candidate(repo, "test-candidate")
    service = ArchivalVettingService()

    mock_gaia = {
        "target_ra_deg": 10.0,
        "target_dec_deg": 20.0,
        "search_radius_arcsec": 10.0,
        "ruwe": 1.62,
        "suspected_binary": True,
        "nearby_sources_count": 3,
        "sources": [{"source_id": "1", "separation_arcsec": 0.0, "ruwe": 1.62}],
    }
    mock_exofop = {
        "tic_id": "987654321",
        "has_imaging": True,
        "has_spectroscopy": False,
        "imaging_records_count": 1,
        "spectroscopy_records_count": 0,
        "imaging_types": ["AO"],
        "spectroscopy_types": [],
    }

    with patch.object(service, "query_gaia_astrometry", return_value=mock_gaia), patch.object(
        service, "query_exofop_metadata", return_value=mock_exofop
    ):
        report = service.synthesize_archival_report(workspace, radius_arcsec=10.0)

        assessment = report["scientific_assessment"]
        assert assessment["1_is_hidden_binary"]["answer"] is True
        assert assessment["2_has_nearby_contaminants"]["answer"] is True
        assert assessment["3_has_ground_based_followup"]["answer"] is True
        assert report["tic_id"] == "987654321"


def test_cli_archive_command(tmp_path, capsys):
    repo = _setup_repo(tmp_path)
    root = ["--root", str(repo)]
    assert main(root + ["init", "archive-candidate", "--toi", "456.01", "--tic", "11223344"]) == 0

    candidate = load_candidate(repo, "archive-candidate")

    mock_gaia = {
        "target_ra_deg": 0.0,
        "target_dec_deg": 0.0,
        "search_radius_arcsec": 10.0,
        "ruwe": 1.0,
        "suspected_binary": False,
        "nearby_sources_count": 1,
        "sources": [],
    }
    mock_exofop = {
        "tic_id": "11223344",
        "has_imaging": False,
        "has_spectroscopy": False,
        "imaging_records_count": 0,
        "spectroscopy_records_count": 0,
        "imaging_types": [],
        "spectroscopy_types": [],
    }

    with patch(
        "exonym.archive.ArchivalVettingService.query_gaia_astrometry", return_value=mock_gaia
    ), patch(
        "exonym.archive.ArchivalVettingService.query_exofop_metadata", return_value=mock_exofop
    ):
        output_file = run_archival_vetting(candidate, radius_arcsec=10.0)
        assert output_file.exists()

        output_data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "scientific_assessment" in output_data
        assert output_data["candidate_id"] == "archive-candidate"

        assert main(root + ["archive", "archive-candidate", "--radius-arcsec", "15.0"]) == 0
        captured = capsys.readouterr().out
        assert "archival_vetting_report.json" in captured
