"""Command-line interface. The only module allowed to print.

Exit codes (spec §7): 0 success, 1 runtime or unexpected error, 2 usage error (argparse),
3 validation failure, 4 FFmpeg missing or too old, 5 FFmpeg failed, 130 interrupted.
Reports go to stdout, one ``ERROR``/``WARN`` line per issue.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import ModuleType

from history_shorts import __version__
from history_shorts.config import Script, Theme, load_script, load_theme
from history_shorts.errors import HistoryShortsError, Issue, Issues, ValidationFailed

COMMANDS = ("render", "validate", "gallery")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130

# The theme shipped with the package, found from the package location, not the CWD.
DEFAULT_THEME = Path(__file__).resolve().parent.parent / "themes" / "son_mai" / "theme.json"

# Import name -> (what to install, install hint per platform; None means "same on all").
_PIP_HINT = 'pip install -e ".[dev]"'
_CAIRO_HINTS: dict[str, str] = {
    "darwin": "brew install cairo pkg-config && pip install pycairo",
    "linux": "sudo apt install libcairo2-dev && pip install pycairo",
    "win32": "pip install pycairo",
}
RUNTIME_MODULES: tuple[tuple[str, str], ...] = (
    ("cairo", "pycairo"),
    ("numpy", "numpy"),
    ("scipy", "scipy"),
    ("PIL", "Pillow"),
)


def _import_module(name: str) -> ModuleType:
    """Indirection over ``importlib.import_module`` so tests can simulate a missing module."""
    return importlib.import_module(name)


def _install_hint(module: str) -> str:
    if module != "cairo":
        return _PIP_HINT
    hint = _CAIRO_HINTS.get(sys.platform)
    if hint is not None:
        return hint
    return "; ".join(f"{os_name}: {text}" for os_name, text in _CAIRO_HINTS.items())


def _require_runtime() -> bool:
    """True when every runtime library imports; otherwise print an install hint, return False."""
    for module, package in RUNTIME_MODULES:
        try:
            _import_module(module)
        except ImportError:
            hint = _install_hint(module)
            print(f"ERROR cannot import {module} ({package}). Install it with: {hint}")
            return False
    return True


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------


def _print_report(issues: list[Issue]) -> int:
    """Print errors, then warnings, then the summary; return the exit code."""
    collected = Issues(list(issues))
    for issue in collected.errors:
        print(f"ERROR {issue.format()}")
    for issue in collected.warnings:
        print(f"WARN {issue.format()}")
    print(f"{len(collected.errors)} errors, {len(collected.warnings)} warnings")
    return ValidationFailed.exit_code if collected.errors else EXIT_OK


# --------------------------------------------------------------------------------------
# Sub-commands
# --------------------------------------------------------------------------------------


def _cmd_validate(args: argparse.Namespace) -> int:
    from history_shorts import checks  # imports Pillow: only after the runtime check passed

    issues: list[Issue] = []
    theme: Theme | None = None
    script: Script | None = None
    try:
        theme, warnings = load_theme(args.theme)
        issues.extend(warnings)
    except ValidationFailed as exc:
        issues.extend(exc.issues.items)
    try:
        script, warnings = load_script(args.script)
        issues.extend(warnings)
    except ValidationFailed as exc:
        issues.extend(exc.issues.items)
    if theme is not None and script is not None:
        issues.extend(checks.check_all(script, theme))
    return _print_report(issues)


def _cmd_stub(args: argparse.Namespace) -> int:
    print(f"history-shorts {args.command}: not implemented yet")
    return EXIT_ERROR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="history-shorts",
        description="Render Vietnamese-history lacquer-style vertical videos offline.",
    )
    parser.add_argument("--version", action="version", version=f"history-shorts {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="{render,validate,gallery}")
    for name in ("render", "gallery"):
        sub.add_parser(name, help=f"{name} (not implemented yet)").set_defaults(run=_cmd_stub)
    validate = sub.add_parser("validate", help="check a script and theme without rendering")
    validate.add_argument("--script", type=Path, required=True, help="path to script.json")
    validate.add_argument(
        "--theme", type=Path, default=DEFAULT_THEME, help="path to theme.json (default: son_mai)"
    )
    validate.set_defaults(run=_cmd_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not _require_runtime():
            return EXIT_ERROR
        return int(args.run(args))
    except HistoryShortsError as exc:
        print(f"ERROR {exc}")
        return exc.exit_code
    except KeyboardInterrupt:
        print("interrupted")
        return EXIT_INTERRUPTED
    except Exception as exc:  # noqa: BLE001 - last-resort handler: report, never a traceback
        print(f"ERROR internal: {type(exc).__name__}: {exc}")
        return EXIT_ERROR
