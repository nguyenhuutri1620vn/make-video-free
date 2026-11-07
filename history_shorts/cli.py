"""Command-line interface. The only module allowed to print.

Exit codes (spec §7): 0 success, 1 runtime or unexpected error, 2 usage error (argparse),
3 validation failure, 4 FFmpeg missing or too old, 5 FFmpeg failed, 130 interrupted.
Reports go to stdout, one ``ERROR``/``WARN`` line per issue.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
import time
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


def _load_and_check(args: argparse.Namespace) -> tuple[Script | None, Theme | None, list[Issue]]:
    """Load theme and script (each may fail on its own), then run the cross-file checks."""
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
    return script, theme, issues


def _cmd_validate(args: argparse.Namespace) -> int:
    return _print_report(_load_and_check(args)[2])


def _warn_ignored_flags(args: argparse.Namespace) -> None:
    given = [
        flag
        for flag, value in (
            ("--music", args.music),
            ("--music-volume", args.music_volume),
            ("--keep-temp", args.keep_temp),
            ("--jobs", args.jobs),
        )
        if value is not None and value is not False
    ]
    for flag in given:
        print(f"WARN {flag} is not implemented yet (milestone M5); ignored")


def _warn_stale_slides(directory: Path, slide_count: int) -> None:
    from history_shorts.output import stale_slides

    stale = stale_slides(directory, slide_count)
    if stale:
        names = ", ".join(p.name for p in stale)
        print(f"WARN stale slide PNGs left in place in {directory}: {names}")


def _print_sources(script: Script) -> None:
    if script.sources:
        print("Sources:")
        for number, source in enumerate(script.sources, start=1):
            print(f"[{number}] {source}")


def _cmd_render(args: argparse.Namespace) -> int:
    from history_shorts.output import default_out_path, slides_dir
    from history_shorts.render import render_slides

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR,
        format="%(levelname)s %(name)s: %(message)s",
    )
    script, theme, issues = _load_and_check(args)
    code = _print_report(issues)
    if code != EXIT_OK or script is None or theme is None:
        return code
    _warn_ignored_flags(args)
    out: Path = args.out if args.out is not None else default_out_path(script)
    started = time.perf_counter()
    directory = slides_dir(out)
    try:
        paths = render_slides(script, theme, out, debug_safe_zone=args.debug_safe_zone)
    except OSError as exc:
        print(f"ERROR cannot write slides to {directory}: {exc.strerror or exc}")
        return EXIT_ERROR
    elapsed = time.perf_counter() - started
    _warn_stale_slides(directory, len(paths))
    noun = "slide" if len(paths) == 1 else "slides"
    print(f"Rendered {len(paths)} {noun} to {directory} in {elapsed:.1f} s")
    _print_sources(script)
    if not args.preview:
        print("ERROR video assembly is not implemented yet (milestone M5)")
        return EXIT_ERROR
    return EXIT_OK


def _cmd_stub(args: argparse.Namespace) -> int:
    print(f"history-shorts {args.command}: not implemented yet")
    return EXIT_ERROR


def _add_theme_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--theme", type=Path, default=DEFAULT_THEME, help="path to theme.json (default: son_mai)"
    )


def _add_render_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    render = sub.add_parser("render", help="render slide PNGs (video assembly comes in M5)")
    render.add_argument("--script", type=Path, required=True, help="path to script.json")
    _add_theme_option(render)
    render.add_argument(
        "--out", type=Path, default=None, help="output video path (default: output/<slug>.mp4)"
    )
    render.add_argument("--music", type=Path, default=None, help="background music (not yet used)")
    render.add_argument(
        "--music-volume", type=float, default=None, help="music volume (not yet used)"
    )
    render.add_argument("--preview", action="store_true", help="write slide PNGs only, no video")
    render.add_argument("--keep-temp", action="store_true", help="keep temp files (not yet used)")
    render.add_argument("--jobs", type=int, default=None, help="parallel encodes (not yet used)")
    render.add_argument(
        "--debug-safe-zone", action="store_true", help="outline the safe zone and regions"
    )
    render.add_argument("--verbose", action="store_true", help="log per-slide timing")
    render.set_defaults(run=_cmd_render)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="history-shorts",
        description="Render Vietnamese-history lacquer-style vertical videos offline.",
    )
    parser.add_argument("--version", action="version", version=f"history-shorts {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="{render,validate,gallery}")
    _add_render_parser(sub)
    sub.add_parser("gallery", help="gallery (not implemented yet)").set_defaults(run=_cmd_stub)
    validate = sub.add_parser("validate", help="check a script and theme without rendering")
    validate.add_argument("--script", type=Path, required=True, help="path to script.json")
    _add_theme_option(validate)
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
