"""Render report JSON and the sources block (FR-91, FR-92)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from collections.abc import Mapping, Sequence
from pathlib import Path

from history_shorts.config import Script, Theme
from history_shorts.errors import Issue
from history_shorts.ffmpeg import FfmpegInfo
from history_shorts.video import RenderOptions

REPORT_SUFFIX = ".report.json"
DEV_VERSION = "dev"


def sources_block(script: Script) -> str:
    """``Sources:`` then ``[n] text`` lines, ready to paste into a caption; ``""`` if none."""
    if not script.sources:
        return ""
    lines = ["Sources:", *(f"[{n}] {text}" for n, text in enumerate(script.sources, start=1))]
    return "\n".join(lines)


def report_path(out: Path) -> Path:
    """``<out stem>.report.json`` next to the video."""
    return out.with_name(out.stem + REPORT_SUFFIX)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(path: Path, base: Path) -> str:
    try:
        return Path(os.path.relpath(path, base)).as_posix()
    except ValueError:  # different drive on Windows
        return path.as_posix()


def _versions(info: FfmpegInfo) -> dict[str, str]:
    import cairo
    import numpy
    import PIL
    import scipy

    ffmpeg_version = ".".join(map(str, info.version)) if info.version else DEV_VERSION
    return {
        "python": platform.python_version(),
        "pycairo": str(cairo.version),
        "cairo": str(cairo.cairo_version_string()),
        "numpy": str(numpy.__version__),
        "scipy": str(scipy.__version__),
        "Pillow": str(PIL.__version__),
        "ffmpeg": ffmpeg_version,
    }


def _slide_rows(slides: Sequence[Path], durations: Sequence[float], base: Path) -> list[object]:
    return [
        {"index": number, "duration": round(seconds, 3), "png": _relative(png, base)}
        for number, (png, seconds) in enumerate(zip(slides, durations, strict=True), start=1)
    ]


def build_report(
    script: Script,
    theme: Theme,
    opts: RenderOptions,
    durations: Sequence[float],
    slides: Sequence[Path],
    timings: Mapping[str, float],
    warnings: Sequence[Issue | str],
    info: FfmpegInfo,
) -> dict[str, object]:
    """Everything needed to reproduce and audit a render. PNG paths are relative to the
    report's directory; ``timings`` are seconds per phase."""
    base = opts.out.parent
    return {
        "script_sha256": _sha256(script.path),
        "theme_sha256": _sha256(theme.path),
        "music_sha256": _sha256(opts.music) if opts.music is not None else None,
        "slides": _slide_rows(slides, durations, base),
        "total_duration": round(sum(durations), 3),
        "warnings": [w.format() if isinstance(w, Issue) else w for w in warnings],
        "versions": _versions(info),
        "timings": {name: round(seconds, 3) for name, seconds in timings.items()},
        "sources": list(script.sources),
    }


def write_report(out: Path, data: Mapping[str, object]) -> Path:
    """Write ``<out stem>.report.json`` atomically (UTF-8, sorted keys) and return its path."""
    target = report_path(out)
    tmp = target.with_name(target.name + ".tmp")
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return target
