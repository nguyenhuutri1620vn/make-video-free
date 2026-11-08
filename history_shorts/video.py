"""Assemble slide PNGs into the final MP4 (FR-80..82, 85, 86, 90, NFR-05).

Clips, the concat list and the silent video live in a temp directory. The audio mux writes
``<out>.partial.mp4`` next to the output, and only a finished file is renamed onto ``out``,
so a failed or interrupted run never leaves a partial file at the output path.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from history_shorts import ffmpeg
from history_shorts.config import Theme
from history_shorts.ffmpeg import FfmpegInfo

logger = logging.getLogger(__name__)

TEMP_PREFIX: Final = "history-shorts-"
PARTIAL_SUFFIX: Final = ".partial.mp4"
DEFAULT_MUSIC_VOLUME: Final = 0.6
MAX_MUSIC_VOLUME: Final = 2.0
TOTAL_DECIMALS: Final = 3


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """What the command line asks of the video step."""

    out: Path
    music: Path | None
    music_volume: float = DEFAULT_MUSIC_VOLUME
    keep_temp: bool = False
    jobs: int = 1
    verbose: bool = False


def partial_path(out: Path) -> Path:
    """The scratch file the mux writes before it is renamed onto ``out``."""
    return out.with_name(out.name + PARTIAL_SUFFIX)


def _encode_clips(
    info: FfmpegInfo,
    slides: list[Path],
    durations: list[float],
    theme: Theme,
    opts: RenderOptions,
    work: Path,
) -> list[Path]:
    clips: list[Path] = []
    fade = theme.transition
    for number, (png, seconds) in enumerate(zip(slides, durations, strict=True), start=1):
        clip = work / f"clip_{number:02d}.mp4"
        cmd = ffmpeg.clip_cmd(
            info, png, clip, seconds, theme.video.fps, theme.video.crf, fade.fade_in, fade.fade_out
        )
        ffmpeg.run(cmd, verbose=opts.verbose)
        clips.append(clip)
    return clips


def _run_steps(
    info: FfmpegInfo,
    slides: list[Path],
    durations: list[float],
    theme: Theme,
    opts: RenderOptions,
    work: Path,
    timings: dict[str, float],
) -> None:
    started = time.perf_counter()
    clips = _encode_clips(info, slides, durations, theme, opts, work)
    timings["encode"] = time.perf_counter() - started

    started = time.perf_counter()
    list_file, joined = work / "list.txt", work / "video.mp4"
    list_file.write_text(ffmpeg.concat_list_text(clips), encoding="utf-8")
    ffmpeg.run(ffmpeg.concat_cmd(info, list_file, joined), verbose=opts.verbose)
    timings["concat"] = time.perf_counter() - started

    started = time.perf_counter()
    total = round(sum(durations), TOTAL_DECIMALS)
    mux = ffmpeg.mux_cmd(info, joined, partial_path(opts.out), total, opts.music, opts.music_volume)
    ffmpeg.run(mux, verbose=opts.verbose)
    timings["mux"] = time.perf_counter() - started


def assemble(
    info: FfmpegInfo,
    slides: list[Path],
    durations: list[float],
    theme: Theme,
    opts: RenderOptions,
    timings: dict[str, float] | None = None,
) -> Path:
    """Encode every slide, join the clips, add the audio and write ``opts.out`` atomically.

    ``durations`` are seconds per slide (whole frames). ``timings``, when given, receives the
    seconds spent in ``encode``, ``concat`` and ``mux``. On any exception, ``KeyboardInterrupt``
    included, the partial file is removed, the temp directory too unless ``opts.keep_temp``,
    and the exception propagates. An existing ``opts.out`` is replaced only on success.
    """
    if len(slides) != len(durations):
        raise ValueError(f"{len(slides)} slides but {len(durations)} durations")
    out = opts.out
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX))
    partial = partial_path(out)
    try:
        _run_steps(
            info, slides, durations, theme, opts, work, timings if timings is not None else {}
        )
        os.replace(partial, out)
    except BaseException:
        partial.unlink(missing_ok=True)
        _drop_temp(work, opts.keep_temp)
        raise
    _drop_temp(work, opts.keep_temp)
    return out


def _drop_temp(work: Path, keep: bool) -> None:
    if keep:
        logger.info("kept temporary files in %s", work)
    else:
        shutil.rmtree(work, ignore_errors=True)
