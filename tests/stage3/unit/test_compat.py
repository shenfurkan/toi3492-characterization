"""Tests for the single repository-bound legacy import bridge (compat.py).

The pytest process itself already has ``scripts/`` on ``sys.path``
(``tests/conftest.py`` and ``pyproject.toml``), so the clean-subprocess test
is the only proof that the bridge works from a pristine environment.
"""

import os
import subprocess
import sys

import pytest

from toi3492.stage3 import compat


def test_ensure_legacy_imports_is_idempotent(root, monkeypatch):
    fake_path = []
    monkeypatch.setattr(compat, "SCRIPTS", root / "scripts")
    monkeypatch.setattr(sys, "path", fake_path)
    assert compat.ensure_legacy_imports() == root / "scripts"
    assert compat.ensure_legacy_imports() == root / "scripts"
    assert fake_path.count(str(root / "scripts")) == 1
    assert fake_path[0] == str(root / "scripts")


def test_ensure_legacy_imports_fails_loudly_when_scripts_is_missing(tmp_path, monkeypatch):
    missing = tmp_path / "scripts"
    monkeypatch.setattr(compat, "SCRIPTS", missing)
    with pytest.raises(RuntimeError, match="repository layout is broken"):
        compat.ensure_legacy_imports()


def test_legacy_bridge_imports_resolve_scripts_in_a_clean_subprocess(root):
    code = "\n".join([
        "import sys",
        "from toi3492.stage3 import compat",
        "import toi3492.stage3.inputs",
        "import toi3492.stage3.simulation",
        "import toi3492.stage3.screening",
        "import toi3492.stage3.recovery",
        "import run_faz5_window_grid",
        "assert str(compat.SCRIPTS) in sys.path",
        "assert run_faz5_window_grid.__file__.startswith(str(compat.SCRIPTS))",
        "print('BRIDGE_OK')",
    ])
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "BRIDGE_OK" in result.stdout
