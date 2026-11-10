"""AST guard tests: no network, no shell=True, only cli.py prints (C-02, NFR-09)."""

from __future__ import annotations

import ast
from collections.abc import Callable
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
CLI_PATH = PACKAGE_DIR / "cli.py"
FORBIDDEN = {"requests", "httpx", "urllib.request", "http.client", "socket"}
# "urllib" itself is flagged too: any bare import or "from urllib import ..." is rejected.
FORBIDDEN_ROOTS = FORBIDDEN | {"urllib"}
DYNAMIC_IMPORTERS = {"__import__", "importlib.import_module", "import_module"}
SHELL_CALLS = {"os.system", "os.popen"}


def _is_forbidden(name: str) -> bool:
    return any(name == bad or name.startswith(bad + ".") for bad in FORBIDDEN_ROOTS)


def _dotted(node: ast.expr) -> str:
    """Dotted name of a Name/Attribute chain, or "" for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else ""
    return ""


def find_network_imports(source: str, filename: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [module] + [f"{module}.{alias.name}" for alias in node.names]
        elif isinstance(node, ast.Call) and _dotted(node.func) in DYNAMIC_IMPORTERS:
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names = [first.value]
        violations += [f"{filename}:{node.lineno}: {n}" for n in names if _is_forbidden(n)]
    return violations


def find_shell_usage(source: str, filename: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            violations += [
                f"{filename}:{node.lineno}: from os import {a.name}"
                for a in node.names
                if f"os.{a.name}" in SHELL_CALLS
            ]
        if not isinstance(node, ast.Call):
            continue
        if _dotted(node.func) in SHELL_CALLS:
            violations.append(f"{filename}:{node.lineno}: {_dotted(node.func)}")
        for kw in node.keywords:
            is_false = isinstance(kw.value, ast.Constant) and kw.value.value is False
            hides_shell = (
                kw.arg is None
                and isinstance(kw.value, ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "shell" for k in kw.value.keys)
            )
            if (kw.arg == "shell" and not is_false) or hides_shell:
                violations.append(f"{filename}:{node.lineno}: shell keyword")
    return violations


def find_prints(source: str, filename: str) -> list[str]:
    """Flag print() calls everywhere except in exactly history_shorts/cli.py."""
    if Path(filename) == CLI_PATH:
        return []
    return [
        f"{filename}:{node.lineno}: print"
        for node in ast.walk(ast.parse(source, filename=filename))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]


def _scan(check: Callable[[str, str], list[str]]) -> list[str]:
    files = sorted(PACKAGE_DIR.rglob("*.py"))
    assert files, "no package sources found"
    return [v for f in files for v in check(f.read_text(encoding="utf-8"), str(f))]


def test_no_network_imports() -> None:
    assert not _scan(find_network_imports)


def test_no_shell_true() -> None:
    assert not _scan(find_shell_usage)


def test_only_cli_prints() -> None:
    assert not _scan(find_prints)


NETWORK_BAD = [
    "from urllib import request",
    "from urllib import parse",
    "import urllib",
    "import socket as s",
    "import urllib.request as r",
    "from http import client",
    "import http.client",
    "from socket import socket",
    "import requests",
    '__import__("socket")',
    'importlib.import_module("socket")',
]
SHELL_BAD = [
    "subprocess.run(x, shell=True)",
    "subprocess.run(x, shell=flag)",
    "subprocess.run(x, shell=1)",
    'subprocess.run(x, shell="yes")',
    'subprocess.run(x, **{"shell": True})',
    'os.system("ls")',
    'os.popen("ls")',
    "from os import system",
]
CLEAN = """
import subprocess
import importlib
from http import HTTPStatus

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, shell=False, check=True)
    importlib.import_module("json")
    __import__("json")
"""


@pytest.mark.parametrize("snippet", NETWORK_BAD)
def test_network_guard_flags_violation(snippet: str) -> None:
    assert find_network_imports(snippet, "bad.py")


@pytest.mark.parametrize("snippet", SHELL_BAD)
def test_shell_guard_flags_violation(snippet: str) -> None:
    assert find_shell_usage(snippet, "bad.py")


def test_print_guard_flags_non_cli_file() -> None:
    assert find_prints('print("x")', str(PACKAGE_DIR / "other.py"))
    # Only the top-level cli.py is exempt, not any cli.py at depth.
    assert find_prints('print("x")', str(PACKAGE_DIR / "sub" / "cli.py"))
    assert not find_prints('print("x")', str(CLI_PATH))


def test_guards_accept_clean_snippet() -> None:
    assert not find_network_imports(CLEAN, "ok.py")
    assert not find_shell_usage(CLEAN, "ok.py")
    assert not find_prints(CLEAN, "ok.py")


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
