import json

import pytest

from exonym.isolation import check_repository, format_report
from exonym.workspace import create_candidate


def _write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_repo(tmp_path, with_candidate=True):
    if with_candidate:
        create_candidate(tmp_path, "candidate-alpha", toi="1234.01", tic="123456789")
        _write(
            tmp_path,
            "candidate/candidate-alpha/docs/note.md",
            "# alpha intake note\n",
        )
    return tmp_path


def test_clean_repository_passes(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "src/example.py", "def parse_sector(label):\n    return label\n")
    _write(repo, "README.md", "# Factory\nNeutral documentation.\n")

    report = check_repository(repo)
    assert report.ok, format_report(report)


def test_catalog_identifier_outside_candidate_fails(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "README.md", "Plan: study TOI-99999.01 next.\n")

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "target-id-in-neutral-zone" for v in report.violations)


def test_catalog_identifier_inside_candidate_passes(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "candidate/candidate-alpha/docs/note.md", "TOI-1234.01 target notes.\n")

    report = check_repository(repo)
    assert report.ok, format_report(report)


def test_registered_alias_leak_outside_candidate_fails(tmp_path):
    repo = _make_repo(tmp_path)
    create_candidate(tmp_path, "candidate-beta")
    metadata_path = tmp_path / "candidate" / "candidate-beta" / "candidate.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["identifiers"]["aliases"] = ["HD 99999"]
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _write(repo, "docs/note.md", "Reference: HD 99999 was checked.\n")

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "registered-alias-leak" for v in report.violations)


def test_hardcoded_sectors_in_shared_source_fail(tmp_path):
    repo = _make_repo(tmp_path)
    _write(
        repo,
        "src/analysis.py",
        "SECTORS = [37, 63, 64]\nPERIOD_DAYS = 9.2224171\n",
    )

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "hardcoded-target-literal" for v in report.violations)


def test_generic_source_passes(tmp_path):
    repo = _make_repo(tmp_path)
    _write(
        repo,
        "src/analysis.py",
        "def phase_hours(time, period_days, epoch_btjd):\n"
        "    return time % period_days\n"
        "def parse_sector(label):\n"
        "    import re\n"
        "    return re.search(r'Sector\\s+(\\d+)', str(label))\n",
    )

    report = check_repository(repo)
    assert report.ok, format_report(report)


def test_ephemeris_keyword_literal_fails_but_trivial_passes(tmp_path):
    repo = _make_repo(tmp_path)
    _write(
        repo,
        "src/analysis.py",
        "fit(period_days=9.2224171, epoch_btjd=2281.123)\n",
    )
    assert not check_repository(repo).ok

    _write(repo, "src/analysis.py", "fit(period_days=1.0, epoch_btjd=0.0)\n")
    assert check_repository(repo).ok


def test_research_payload_outside_candidate_fails(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "data/raw/lightcurve.fits", "binary")
    _write(repo, "results/outputs.csv", "a,b\n1,2\n")
    _write(repo, "docs/notes.ipynb", "{}")

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "research-payload-outside-candidate" for v in report.violations)


def test_research_payload_inside_candidate_passes(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "candidate/candidate-alpha/data/raw/lc.fits", "binary")
    _write(repo, "candidate/candidate-alpha/outputs/out.csv", "a,b\n")

    report = check_repository(repo)
    assert report.ok, format_report(report)


def test_top_level_archive_is_forbidden(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "archive/old-project/README.md", "frozen evidence\n")

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "top-level-archive-forbidden" for v in report.violations)


def test_top_level_data_is_forbidden(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "data/raw/lc.fits", "binary")

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "top-level-data-forbidden" for v in report.violations)


def test_exception_registry_suppresses_matching_violation(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "README.md", "Plan: study TOI-99999.01 next.\n")

    violations_before = check_repository(repo).violations
    assert violations_before

    target = violations_before[0]
    exception = {
        "path": target.path,
        "line": target.line,
        "rule": target.rule,
        "reason": "test fixture",
        "expires": "2099-01-01",
    }
    _write(
        repo,
        "policy/isolation-exceptions.json",
        json.dumps({"entries": [exception]}, indent=2),
    )

    assert check_repository(repo).ok


def test_symlink_or_reparse_point_rejected(tmp_path):
    repo = _make_repo(tmp_path)
    _write(repo, "src/target.txt", "neutral")
    link = repo / "src/link.txt"
    try:
        link.symlink_to(repo / "src" / "target.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    report = check_repository(repo)
    assert not report.ok
    assert any(v.rule == "symlink-or-reparse-point" for v in report.violations)


def test_self_check_of_actual_repository():
    import os

    root = os.environ.get("EXOPLANET_REPO_ROOT")
    if not root:
        pytest.skip("EXOPLANET_REPO_ROOT not set")
    report = check_repository(root)
    assert report.ok, format_report(report)
