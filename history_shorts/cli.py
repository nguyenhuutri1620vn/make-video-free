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
from history_shorts.video import (
    DEFAULT_MUSIC_VOLUME,
    MAX_MUSIC_VOLUME,
    RenderOptions,
    assemble,
    default_jobs,
)

COMMANDS = ("render", "validate", "gallery")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_INTERRUPTED = 130

# The theme shipped with the package, found from the package location, not the CWD.
DEFAULT_THEME = Path(__file__).resolve().parent.parent / "themes" / "son_mai" / "theme.json"

DEFAULT_GALLERY = Path("output") / "gallery.png"  # relative to the CWD

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
    """The video flags mean nothing to ``--preview``."""
    if args.preview:
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
            print(f"WARN {flag} has no effect with --preview")


def _warn_stale_slides(directory: Path, slide_count: int) -> None:
    from history_shorts.output import stale_slides

    stale = stale_slides(directory, slide_count)
    if stale:
        names = ", ".join(p.name for p in stale)
        print(f"WARN stale slide PNGs left in place in {directory}: {names}")


def _print_sources(script: Script) -> None:
    from history_shorts.report import sources_block

    block = sources_block(script)
    if block:
        print(block)


def _warn_unsupported_motion(script: Script) -> None:
    for index, slide in enumerate(script.slides):
        if slide.motion != "none":
            print(f"WARN slides[{index}].motion: {slide.motion} is not implemented yet; ignored")


def _render_pngs(
    args: argparse.Namespace, script: Script, theme: Theme, out: Path
) -> list[Path] | None:
    """Render the slide PNGs; ``None`` (after printing an ERROR) when they cannot be written."""
    from history_shorts.output import slides_dir
    from history_shorts.render import render_slides, scene_expander

    directory = slides_dir(out)
    try:
        paths = render_slides(
            script, theme, out, debug_safe_zone=args.debug_safe_zone, expand=scene_expander
        )
    except OSError as exc:
        print(f"ERROR cannot write slides to {directory}: {exc.strerror or exc}")
        return None
    _warn_stale_slides(directory, len(paths))
    return paths


def _print_summary(
    script: Script, out: Path, report: Path, total: float, elapsed: float, count: int
) -> None:
    print(f"Slides: {count}")
    print(f"Duration: {total:.1f} s")
    print(f"Video: {out}")
    print(f"Report: {report}")
    print(f"Elapsed: {elapsed:.1f} s")
    _print_sources(script)


def _encode_video(
    args: argparse.Namespace,
    script: Script,
    theme: Theme,
    issues: list[Issue],
    out: Path,
    began: float,
    validated: float,
) -> int:
    """Everything after validation for a full render; see the order in the module docs."""
    from history_shorts import ffmpeg as ff
    from history_shorts import report as rp
    from history_shorts.script_config import slide_duration

    music: Path | None = args.music
    if music is not None and not music.is_file():
        print(f"ERROR --music: {music} is not a file")
        return ValidationFailed.exit_code
    if out.is_dir():
        print(f"ERROR cannot write video to {out}: it is a directory")
        return EXIT_ERROR
    info = ff.find_ffmpeg()  # before any slide work, so a missing FFmpeg fails fast (AC-14)
    _warn_unsupported_motion(script)
    opts = RenderOptions(
        out=out,
        music=music,
        music_volume=DEFAULT_MUSIC_VOLUME if args.music_volume is None else args.music_volume,
        keep_temp=args.keep_temp,
        jobs=default_jobs() if args.jobs is None else args.jobs,
        verbose=args.verbose,
    )
    phase = time.perf_counter()
    paths = _render_pngs(args, script, theme, out)
    if paths is None:
        return EXIT_ERROR
    timings = {"validate": validated - began, "render_slides": time.perf_counter() - phase}
    durations = [slide_duration(s, theme.video.fps) for s in script.slides]
    try:
        assemble(info, paths, durations, theme, opts, timings)
    except OSError as exc:
        print(f"ERROR cannot write video to {out}: {exc.strerror or exc}")
        return EXIT_ERROR
    timings["total"] = time.perf_counter() - began
    warnings = [i for i in issues if i.severity == "warning"]
    data = rp.build_report(script, theme, opts, durations, paths, timings, warnings, info)
    try:
        report = rp.write_report(out, data)
    except OSError as exc:
        print(f"ERROR cannot write report to {rp.report_path(out)}: {exc.strerror or exc}")
        return EXIT_ERROR
    _print_summary(script, out, report, sum(durations), timings["total"], len(paths))
    return EXIT_OK


def _cmd_render(args: argparse.Namespace) -> int:
    from history_shorts.output import default_out_path, slides_dir

    began = time.perf_counter()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO if args.keep_temp else logging.ERROR,
        format="%(levelname)s %(name)s: %(message)s",
    )
    script, theme, issues = _load_and_check(args)
    validated = time.perf_counter()
    code = _print_report(issues)
    if code != EXIT_OK or script is None or theme is None:
        return code
    _warn_ignored_flags(args)
    out: Path = args.out if args.out is not None else default_out_path(script)
    if not args.preview:
        return _encode_video(args, script, theme, issues, out, began, validated)
    paths = _render_pngs(args, script, theme, out)
    if paths is None:
        return EXIT_ERROR
    noun = "slide" if len(paths) == 1 else "slides"
    elapsed = time.perf_counter() - validated
    print(f"Rendered {len(paths)} {noun} to {slides_dir(out)} in {elapsed:.1f} s")
    _print_sources(script)
    return EXIT_OK


def _cmd_gallery(args: argparse.Namespace) -> int:
    from history_shorts.gallery import render_gallery
    from history_shorts.render import write_png

    try:
        theme, warnings = load_theme(args.theme)
    except ValidationFailed as exc:
        return _print_report(exc.issues.items)
    for issue in warnings:
        print(f"WARN {issue.format()}")
    out: Path = args.out
    started = time.perf_counter()
    image = render_gallery(theme)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        write_png(image, out)
    except OSError as exc:
        print(f"ERROR cannot write gallery to {out}: {exc.strerror or exc}")
        return EXIT_ERROR
    print(f"Wrote gallery to {out} in {time.perf_counter() - started:.1f} s")
    return EXIT_OK


def _add_theme_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--theme", type=Path, default=DEFAULT_THEME, help="path to theme.json (default: son_mai)"
    )


def _music_volume(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid number: {text!r}") from None
    if not 0.0 <= value <= MAX_MUSIC_VOLUME:  # also rejects nan
        raise argparse.ArgumentTypeError(f"{text} is outside 0 to {MAX_MUSIC_VOLUME:g}")
    return value


def _jobs(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"{text} is not at least 1")
    return value


def _add_render_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    render = sub.add_parser("render", help="render the slides and assemble the MP4 video")
    render.add_argument("--script", type=Path, required=True, help="path to script.json")
    _add_theme_option(render)
    render.add_argument(
        "--out", type=Path, default=None, help="output video path (default: output/<slug>.mp4)"
    )
    render.add_argument(
        "--music", type=Path, default=None, help="background music file (looped or trimmed)"
    )
    render.add_argument(
        "--music-volume",
        type=_music_volume,
        default=None,
        help="music volume, 0 to 2 (default: 0.6)",
    )
    render.add_argument("--preview", action="store_true", help="write slide PNGs only, no video")
    render.add_argument(
        "--keep-temp", action="store_true", help="keep the temp directory with the clips"
    )
    render.add_argument(
        "--jobs",
        type=_jobs,
        default=None,
        help="parallel clip encodes, at least 1 (default: CPU count - 1)",
    )
    render.add_argument(
        "--debug-safe-zone", action="store_true", help="outline the safe zone and regions"
    )
    render.add_argument(
        "--verbose", action="store_true", help="log per-slide timing and every FFmpeg command"
    )
    render.set_defaults(run=_cmd_render)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="history-shorts",
        description="Render Vietnamese-history lacquer-style vertical videos offline.",
    )
    parser.add_argument("--version", action="version", version=f"history-shorts {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="{render,validate,gallery}")
    _add_render_parser(sub)
    gallery = sub.add_parser("gallery", help="contact sheet of every role, facing and prop")
    _add_theme_option(gallery)
    gallery.add_argument(
        "--out", type=Path, default=DEFAULT_GALLERY, help="output PNG (default: output/gallery.png)"
    )
    gallery.set_defaults(run=_cmd_gallery)
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
