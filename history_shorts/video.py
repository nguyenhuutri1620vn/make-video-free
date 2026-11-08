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
from concurrent.futures import FIRST_EXCEPTION, Future, ThreadPoolExecutor, wait
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


def default_jobs() -> int:
    """Parallel clip encodes when ``--jobs`` is not given: one fewer than the CPU count (FR-87)."""
    return max(1, (os.cpu_count() or 2) - 1)


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
    """Encode one clip per slide and return the clips in slide order.

    ``opts.jobs == 1`` encodes in the calling thread. Otherwise a thread pool runs one
    FFmpeg process per clip. On the first failure (or Ctrl-C) pending clips are cancelled and
    the clips already running are waited for, so no FFmpeg writes into a temp directory that
    is being deleted. Child FFmpeg processes are not killed: each finishes its single clip,
    which takes a few seconds. The first failure in slide order is raised.
    """
    fade = theme.transition
    jobs = list(zip(slides, durations, strict=True))
    clips = [work / f"clip_{number:02d}.mp4" for number in range(1, len(jobs) + 1)]
    threads = max(1, (os.cpu_count() or 2) // opts.jobs) if opts.jobs > 1 else None
    cmds = [
        ffmpeg.clip_cmd(
            info,
            png,
            clip,
            seconds,
            theme.video.fps,
            theme.video.crf,
            fade.fade_in,
            fade.fade_out,
            threads=threads,
        )
        for (png, seconds), clip in zip(jobs, clips, strict=True)
    ]
    if opts.jobs <= 1:
        for cmd in cmds:
            ffmpeg.run(cmd, verbose=opts.verbose)
        return clips
    futures: list[Future[None]] = []
    with ThreadPoolExecutor(max_workers=opts.jobs) as pool:
        try:
            futures = [pool.submit(ffmpeg.run, cmd, verbose=opts.verbose) for cmd in cmds]
            wait(futures, return_when=FIRST_EXCEPTION)
        finally:  # also on KeyboardInterrupt, even during submission
            pool.shutdown(wait=True, cancel_futures=True)
    _raise_first_failure(futures)
    return clips


def _raise_first_failure(futures: list[Future[None]]) -> None:
    for future in futures:
        if not future.cancelled() and (error := future.exception()) is not None:
            raise error


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
