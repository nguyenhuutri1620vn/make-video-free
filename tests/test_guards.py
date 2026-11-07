"""AST guard tests: no network, no shell=True, only cli.py prints (C-02, NFR-09)."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

from history_shorts.errors import (
    FfmpegFailed,
    FfmpegMissing,
    FfmpegTooOld,
    HistoryShortsError,
    Issue,
    Issues,
    ValidationFailed,
)
from history_shorts.primitives import Box

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "history_shorts"
FORBIDDEN = {"requests", "httpx", "urllib.request", "http.client", "socket"}


def _sources() -> Iterator[tuple[Path, ast.AST]]:
    files = sorted(PACKAGE_DIR.rglob("*.py"))
    assert files, "no package sources found"
    for path in files:
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_forbidden(name: str) -> bool:
    return any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN)


def test_no_network_imports() -> None:
    offenders: list[str] = []
    for path, tree in _sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [module] + [f"{module}.{alias.name}" for alias in node.names]
            else:
                continue
            offenders += [f"{path.name}: {n}" for n in names if _is_forbidden(n)]
    assert not offenders, offenders


def test_no_shell_true() -> None:
    offenders: list[str] = []
    for path, tree in _sources():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (
                    kw.arg == "shell"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, offenders


def test_only_cli_prints() -> None:
    offenders: list[str] = []
    for path, tree in _sources():
        if path.name == "cli.py":
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, offenders


def test_box_intersects_and_inside() -> None:
    a, b = Box(0, 0, 10, 10), Box(9, 9, 20, 20)
    assert a.intersects(b) and not a.inside(b) and Box(1, 1, 2, 2).inside(a)
    assert not Box(0, 0, 10, 10).intersects(Box(10, 0, 20, 10))  # touching edges do not intersect


def test_box_geometry() -> None:
    a, b = Box(0, 0, 10, 20), Box(5, -5, 30, 8)
    assert a.width == 10 and a.height == 20
    assert a.union(b) == Box(0, -5, 30, 20)


def test_issue_format_and_collection() -> None:
    issue = Issue("script.json", "slides[2].x", "must be 0-1080", "error")
    assert issue.format() == "script.json › slides[2].x: must be 0-1080"
    issues = Issues()
    issues.warning("script.json", "sources", "missing")
    issues.raise_if_errors()  # warnings alone do not raise
    issues.error("script.json", "a", "bad")
    issues.error("theme.json", "b", "worse")
    assert len(issues.errors) == 2 and len(issues.warnings) == 1
    with pytest.raises(ValidationFailed) as exc:
        issues.raise_if_errors()
    assert exc.value.exit_code == 3
    assert exc.value.issues is issues


def test_exception_exit_codes() -> None:
    assert HistoryShortsError("x").exit_code == 1
    assert FfmpegMissing("x").exit_code == 4
    assert FfmpegTooOld("x").exit_code == 4
    failed = FfmpegFailed(["ffmpeg", "-i"], "tail")
    assert failed.exit_code == 5
    assert failed.command == ["ffmpeg", "-i"] and failed.stderr_tail == "tail"
