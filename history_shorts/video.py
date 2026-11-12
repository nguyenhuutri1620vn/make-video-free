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
from history_shorts.config import AudioSpec, Theme
from history_shorts.ffmpeg import FfmpegInfo
from history_shorts.output import layer_paths

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
    motions: tuple[str, ...] = ()  # per slide; missing entries mean "none" (FR-84)
    voices: tuple[ffmpeg.VoiceInput, ...] = ()  # narration clips (v2.1); none means no voice
    audio: AudioSpec = AudioSpec()  # voice mix and loudness settings, used with ``voices``
    transitions: tuple[str, ...] = ()  # per slide, how it enters; missing means "cut" (A.2)
    text_layers: tuple[ffmpeg.TextLayer | None, ...] = ()  # per slide ``text_in`` layer (A.2)
    sfx: tuple[ffmpeg.VoiceInput, ...] = ()  # sound effects on the timeline (A.2)
    cuts: tuple[tuple[float, float], ...] = ()  # music silent between these times (A.2)


def default_jobs() -> int:
    """Parallel clip encodes when ``--jobs`` is not given: one fewer than the CPU count (FR-87)."""
    return max(1, (os.cpu_count() or 2) - 1)


def _per_slide(values: tuple[str, ...], count: int, default: str) -> list[str]:
    return [values[i] if i < len(values) else default for i in range(count)]


def overlaps(
    durations: list[float], transitions: list[str], length: float, fps: int
) -> list[float]:
    """Seconds clip k runs past the start of slide k + 1 (A.2.3): 0 before a cut, else the
    theme length clamped to half of the shorter neighbour, in whole frames (at least one)."""
    result: list[float] = []
    for k in range(len(durations) - 1):
        if transitions[k + 1] == "cut":
            result.append(0.0)
            continue
        seconds = min(length, durations[k] / 2, durations[k + 1] / 2)
        result.append(max(round(seconds * fps), 1) / fps)
    return result


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
    clips = [work / f"clip_{number:02d}.mp4" for number in range(1, len(slides) + 1)]
    cmds = _clip_cmds(info, slides, durations, theme, opts, clips)
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


def _clip_cmds(
    info: FfmpegInfo,
    slides: list[Path],
    durations: list[float],
    theme: Theme,
    opts: RenderOptions,
    clips: list[Path],
) -> list[list[str]]:
    """One clip command per slide. A clip before a transition runs on by the overlap, and
    theme fades are dropped on both sides of a transition (A.2.3)."""
    fade, count = theme.transition, len(slides)
    transitions = _per_slide(opts.transitions, count, "cut")
    extra = [*overlaps(durations, transitions, fade.duration, theme.video.fps), 0.0]
    motions = _per_slide(opts.motions, count, "none")
    threads = max(1, (os.cpu_count() or 2) // opts.jobs) if opts.jobs > 1 else None
    cmds: list[list[str]] = []
    for k in range(count):
        enters = k > 0 and transitions[k] != "cut"
        leaves = k + 1 < count and transitions[k + 1] != "cut"
        text = opts.text_layers[k] if k < len(opts.text_layers) else None
        cmds.append(
            ffmpeg.clip_cmd(
                info,
                layer_paths(slides[k])[0] if text is not None else slides[k],
                clips[k],
                durations[k] + extra[k],
                theme.video.fps,
                theme.video.crf,
                0.0 if enters else fade.fade_in,
                0.0 if leaves else fade.fade_out,
                motion=motions[k],
                threads=threads,
                text=text,
            )
        )
    return cmds


def _join(
    info: FfmpegInfo,
    clips: list[Path],
    durations: list[float],
    theme: Theme,
    opts: RenderOptions,
    work: Path,
) -> Path:
    """Concat the clips by stream copy, or with ``xfade`` when any slide has a transition."""
    joined = work / "video.mp4"
    transitions = _per_slide(opts.transitions, len(clips), "cut")
    if all(name == "cut" for name in transitions[1:]):
        list_file = work / "list.txt"
        list_file.write_text(ffmpeg.concat_list_text(clips), encoding="utf-8")
        ffmpeg.run(ffmpeg.concat_cmd(info, list_file, joined), verbose=opts.verbose)
        return joined
    fps = theme.video.fps
    starts = [sum(durations[:k]) for k in range(len(durations))]
    gaps = overlaps(durations, transitions, theme.transition.duration, fps)
    cmd = ffmpeg.xfade_cmd(info, clips, starts, transitions, gaps, joined, fps, theme.video.crf)
    ffmpeg.run(cmd, verbose=opts.verbose)
    return joined


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
    joined = _join(info, clips, durations, theme, opts, work)
    timings["concat"] = time.perf_counter() - started

    started = time.perf_counter()
    total = round(sum(durations), TOTAL_DECIMALS)
    plan = ffmpeg.MixPlan(opts.voices, opts.sfx, opts.cuts)
    mux = ffmpeg.mix_cmd(
        info, joined, partial_path(opts.out), total, plan, opts.music, opts.music_volume, opts.audio
    )
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
