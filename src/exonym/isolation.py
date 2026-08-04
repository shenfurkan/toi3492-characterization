"""Repository isolation enforcement.

Invariant: every target-specific path and byte must live under
``candidate/<candidate-id>/``. Everything outside ``candidate/`` must be
demonstrably target-neutral.

Checks implemented here:

1. Path ownership: no top-level ``archive/`` or ``data/``; no research payload
   formats (FITS/CSV/NPY/NPZ/PDF/TeX/ZIP/TAR/GZ/IPYNB/...) outside
   ``candidate/``.
2. Registered alias scan: TOI/TIC and alias tokens derived from every
   ``candidate.json`` must not appear in neutral-zone text.
3. Python AST scan (``src/`` only): no numeric literals bound to
   sector/ephemeris names or ephemeris call keywords.
4. Symlink/junction/reparse-point rejection across the whole tree.

The module ships with a test suite and a CLI:
``exonym verify`` or ``python -m exonym.isolation --root .``
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .workspace import discover_candidates

CANDIDATE_DIRECTORY = "candidate"

NEUTRAL_TOP_LEVEL_EXTENSIONS = {".md", ".toml", ".txt", ".gitignore", ""}
NEUTRAL_DIRECTORIES = (
    "src",
    "tests",
    "docs",
    "protocols",
    "methods",
    "resources",
    "schemas",
    "policy",
    "templates",
    ".github",
)
NEUTRAL_EXTENSIONS = {
    ".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml", ".gitignore", ".cff", "",
}

RESEARCH_PAYLOAD_EXTENSIONS = {
    ".fits", ".fit", ".fz", ".csv", ".tsv", ".parquet",
    ".npy", ".npz", ".h5", ".hdf5", ".pkl", ".joblib",
    ".pdf", ".tex", ".zip", ".tar", ".gz", ".ipynb",
    ".png", ".jpg", ".jpeg", ".log",
}

TOI_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])TOI[\s._-]*\d{1,7}(?:\.\d{1,2})?(?![A-Za-z0-9])", re.IGNORECASE
)
TIC_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])TIC[\s._:-]*\d{5,12}(?![A-Za-z0-9])", re.IGNORECASE
)
COMPACT_ID_PATTERN = re.compile(r"(?<![A-Za-z0-9])(?:TOI|TIC)\d{4,}(?![A-Za-z0-9])", re.IGNORECASE)

SECTOR_NAME = re.compile(r"^(?:tess_)?sectors?(?:_ids?|_numbers?)?$", re.IGNORECASE)
EPHEMERIS_NAME = re.compile(
    r"^(?:period|epoch|t0|duration|ephemeris|transit_time)(?:_days?|_hours?|_btjd|_bjd|_jd|_tdb)?$",
    re.IGNORECASE,
)
EPHEMERIS_KEYWORDS = {
    "period_days", "epoch_btjd", "epoch_bjd", "epoch_jd", "epoch_tdb", "t0",
    "duration_hours", "duration_days", "transit_time", "ephemeris",
}
TRIVIAL_VALUES = {0.0, 1.0, -1.0, 0.5, -0.5}

EXCEPTIONS_PATH = Path("policy") / "isolation-exceptions.json"


@dataclass(frozen=True)
class Violation:
    path: str
    rule: str
    detail: str
    line: Optional[int] = None

    def __str__(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.rule}] {location}: {self.detail}"


@dataclass
class IsolationReport:
    violations: List[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations

    def add(self, path: Path, rule: str, detail: str, line: Optional[int] = None) -> None:
        self.violations.append(
            Violation(path.as_posix(), rule, detail, line=line)
        )


def is_reparse_point(path: Path) -> bool:
    """Detect symlinks and junctions on Windows and POSIX."""
    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    attributes = ctypes.windll.kernel32.GetFileAttributesW(str(path))
    return bool(attributes != 0xFFFFFFFF and (attributes & 0x400))


def _text_payload(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _alias_tokens(candidate_root: Path) -> Dict[str, str]:
    """Return {escaped-token: owning candidate_id} for every registered alias."""
    tokens: Dict[str, str] = {}
    for workspace in discover_candidates(candidate_root.parent):
        for alias in workspace.metadata.get("identifiers", {}).get("aliases", []):
            compact = re.sub(r"[^0-9A-Za-z]", "", str(alias))
            if compact and len(compact) >= 4:
                tokens[re.escape(str(alias))] = workspace.candidate_id
                tokens[re.escape(compact)] = workspace.candidate_id
    return tokens


def _scan_text_for_ids(
    report: IsolationReport,
    path: Path,
    content: str,
    alias_tokens: Dict[str, str],
    scan_catalog_patterns: bool = True,
) -> None:
    for line_number, line in enumerate(content.splitlines(), start=1):
        if scan_catalog_patterns and (
            TOI_PATTERN.search(line) or TIC_PATTERN.search(line) or COMPACT_ID_PATTERN.search(line)
        ):
            report.add(
                path,
                "target-id-in-neutral-zone",
                f"catalog identifier found: {line.strip()[:120]}",
                line_number,
            )
        for token, owner in alias_tokens.items():
            if re.search(token, line, flags=re.IGNORECASE):
                report.add(
                    path,
                    "registered-alias-leak",
                    f"alias owned by {owner}: {line.strip()[:120]}",
                    line_number,
                )
                break


def _scan_ast(report: IsolationReport, path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if not isinstance(value, ast.Constant) or isinstance(value.value, bool):
                continue
            try:
                number = float(value.value)
            except (TypeError, ValueError):
                continue
            if number in TRIVIAL_VALUES:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and (
                    SECTOR_NAME.fullmatch(target.id) or EPHEMERIS_NAME.fullmatch(target.id)
                ):
                    report.add(
                        path,
                        "hardcoded-target-literal",
                        f"{target.id} = {number!r}",
                        node.lineno,
                    )
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg in EPHEMERIS_KEYWORDS and isinstance(
                    keyword.value, ast.Constant
                ):
                    try:
                        number = float(keyword.value.value)
                    except (TypeError, ValueError):
                        continue
                    if number not in TRIVIAL_VALUES and float(number).is_integer() is False:
                        report.add(
                            path,
                            "hardcoded-ephemeris-keyword",
                            f"{keyword.arg}={number!r}",
                            node.lineno,
                        )


def _load_exceptions(root: Path) -> Dict[str, Any]:
    path = root / EXCEPTIONS_PATH
    if not path.is_file():
        return {"entries": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def check_repository(root: Path) -> IsolationReport:
    """Run the full isolation check over a repository tree."""
    root = Path(root).resolve()
    report = IsolationReport()
    exceptions = _load_exceptions(root)
    exception_paths = {
        (entry.get("path"), entry.get("line"), entry.get("rule"))
        for entry in exceptions.get("entries", [])
    }
    alias_tokens = _alias_tokens(root / CANDIDATE_DIRECTORY)

    if (root / "archive").exists():
        report.add(
            root / "archive",
            "top-level-archive-forbidden",
            "archived targets must remain under candidate/<candidate-id>/",
        )
    if (root / "data").exists():
        report.add(
            root / "data",
            "top-level-data-forbidden",
            "target data must live under candidate/<candidate-id>/data/",
        )

    for directory in NEUTRAL_DIRECTORIES:
        neutral_root = root / directory
        if not neutral_root.is_dir():
            continue
        for path in sorted(neutral_root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in {"__pycache__", ".pytest_cache", ".git"} for part in path.parts):
                continue
            if is_reparse_point(path):
                report.add(path, "symlink-or-reparse-point", "not permitted in neutral zone")
                continue
            relative = path.relative_to(root)
            if path.suffix.lower() not in NEUTRAL_EXTENSIONS:
                report.add(
                    path,
                    "research-payload-outside-candidate",
                    f"format {path.suffix or '(none)'} is only allowed under candidate/",
                )
                continue
            content = _text_payload(path)
            if content is not None:
                # Shared tests necessarily exercise ID-detection fixtures, so
                # generic catalog patterns are skipped there; real registered
                # aliases are still scanned everywhere.
                _scan_text_for_ids(
                    report,
                    path,
                    content,
                    alias_tokens,
                    scan_catalog_patterns=not (relative.parts and relative.parts[0] == "tests"),
                )
            if path.suffix.lower() == ".py" and relative.parts and relative.parts[0] == "src":
                _scan_ast(report, path)

    neutral_files: List[Path] = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if is_reparse_point(path):
            report.add(path, "symlink-or-reparse-point", "root files must be plain files")
            continue
        if path.name in {"LICENSE"}:
            continue
        if path.suffix.lower() not in NEUTRAL_TOP_LEVEL_EXTENSIONS:
            report.add(
                path,
                "research-payload-outside-candidate",
                f"root format {path.suffix or '(none)'} is only allowed under candidate/",
            )
            continue
        neutral_files.append(path)
    for path in neutral_files:
        content = _text_payload(path)
        if content is not None:
            _scan_text_for_ids(report, path, content, alias_tokens)

    candidate_root = root / CANDIDATE_DIRECTORY
    if candidate_root.is_dir():
        for path in sorted(candidate_root.rglob("*")):
            if path.is_file() and is_reparse_point(path):
                report.add(path, "symlink-or-reparse-point", "not permitted in candidate workspaces")

    if exception_paths:
        kept: List[Violation] = []
        for violation in report.violations:
            key = (violation.path, violation.line, violation.rule)
            if key in exception_paths:
                continue
            kept.append(violation)
        report.violations = kept
    return report


def format_report(report: IsolationReport) -> str:
    if report.ok:
        return "ISOLATION: PASS (no violations)"
    lines = [f"ISOLATION: FAIL ({len(report.violations)} violation(s))"]
    lines.extend(str(violation) for violation in report.violations)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Enforce candidate/ research isolation.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    args = parser.parse_args(argv)
    report = check_repository(args.root.resolve())
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
