import shutil

import pytest

from exonym.__main__ import main


def _repo(tmp_path):
    for name in (
        "docs/01_intake_manifest.md",
        "docs/02_feasibility_report.md",
        "docs/03_spoc_dv_vetting.md",
        "docs/04_tfop_sg_followup.md",
    ):
        path = tmp_path / "templates" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("- [ ] [MANDATORY] task\n", encoding="utf-8")
    (tmp_path / "templates/decisions/review_gate.md").parent.mkdir(parents=True, exist_ok=True)
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


def test_cli_full_lifecycle(tmp_path, capsys):
    repo = _repo(tmp_path)
    root = ["--root", str(repo)]

    assert main(root + ["init", "candidate-alpha", "--toi", "1234.01", "--tic", "123456789"]) == 0
    assert main(root + ["list"]) == 0
    assert main(root + ["list", "--mission", "tess"]) == 0
    assert main(root + ["status", "candidate-alpha"]) == 0
    assert main(root + ["track", "candidate-alpha"]) == 0

    with pytest.raises(SystemExit) as exc_info:
        main(root + ["advance", "candidate-alpha"])
    assert exc_info.value.code == 2

    assert main(root + ["tag", "candidate-alpha", "sg1-cleared"]) == 0
    assert main(root + ["freeze", "candidate-alpha", "--version", "v1.0.0"]) == 0
    assert main(root + ["verify"]) == 0

    output = capsys.readouterr().out
    assert "ISOLATION: PASS" in output


def test_cli_init_sets_mission_and_tags(tmp_path, capsys):
    repo = _repo(tmp_path)
    root = ["--root", str(repo)]
    main(
        root
        + ["init", "candidate-beta", "--toi", "1234.01", "--tic", "123456789",
           "--mission", "tess", "--tag", "priority-1"]
    )
    output = capsys.readouterr().out
    assert '"mission": "tess"' in output
    assert '"priority-1"' in output


def test_cli_list_filters_by_phase(tmp_path, capsys):
    repo = _repo(tmp_path)
    root = ["--root", str(repo)]
    main(root + ["init", "candidate-alpha", "--toi", "1234.01", "--tic", "123456789"])
    main(root + ["init", "candidate-beta"])
    main(root + ["list", "--phase", "intake"])
    output = capsys.readouterr().out
    assert "candidate-alpha" in output
    assert "candidate-beta" in output

    main(root + ["list", "--phase", "analysis"])
    output = capsys.readouterr().out
    assert "candidate-alpha" not in output


def test_cli_ingest_requires_tic(tmp_path):
    repo = _repo(tmp_path)
    root = ["--root", str(repo)]
    main(root + ["init", "candidate-alpha"])
    with pytest.raises(SystemExit) as exc_info:
        main(root + ["ingest", "candidate-alpha", "--sectors", "37"])
    assert exc_info.value.code == 2


def test_cli_vet_command(tmp_path, capsys):
    repo = _repo(tmp_path)
    root = ["--root", str(repo)]
    main(root + ["init", "candidate-alpha", "--toi", "1234.01", "--tic", "123456789"])
    assert main(root + ["vet", "candidate-alpha", "--n-draws", "100"]) == 0
    output = capsys.readouterr().out
    assert "triceratops_report.json" in output

