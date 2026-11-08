"""FFmpeg discovery, exact command builders and a safe runner (FR-80..86, NFR-04, NFR-09).

Every command is a ``list[str]`` run without a shell. Paths appear in argv as ``str(path)``
unchanged: no quoting is needed because no shell ever parses them.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import FfmpegFailed, FfmpegMissing, FfmpegTooOld

logger = logging.getLogger(__name__)

MIN_VERSION: tuple[int, int] = (4, 4)
STDERR_TAIL_LINES = 20
AUDIO_RATE = 48000
AUDIO_BITRATE = "192k"
MUSIC_FADE_IN = 0.5
MUSIC_FADE_OUT = 1.5
X264_PRESET = "medium"

_VERSION_RE = re.compile(r"ffmpeg version n?(\d+)\.(\d+)")
_INSTALL_HINTS: dict[str, str] = {
    "darwin": "brew install ffmpeg",
    "linux": "sudo apt install ffmpeg",
    "win32": "winget install Gyan.FFmpeg",
}
_DEFAULT_HINT = "install FFmpeg from https://ffmpeg.org/download.html"

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


@dataclass(frozen=True, slots=True)
class FfmpegInfo:
    """Located binaries and the parsed version (``None`` for a dev build)."""

    ffmpeg: Path
    ffprobe: Path
    version: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """The facts about a video file that tests and the report need."""

    width: int
    height: int
    codec: str
    pix_fmt: str
    fps: str
    duration: float
    audio_codec: str | None
    audio_duration: float | None


def parse_version(banner: str) -> tuple[int, int] | None:
    """``(major, minor)`` from an ``ffmpeg -version`` banner; ``None`` for dev builds."""
    match = _VERSION_RE.search(banner)
    return (int(match.group(1)), int(match.group(2))) if match else None


def install_hint(platform: str) -> str:
    key = "linux" if platform.startswith("linux") else platform
    return _INSTALL_HINTS.get(key, _DEFAULT_HINT)


def _run_text(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )


def find_ffmpeg(
    *,
    which: Callable[[str], str | None] | None = None,
    platform: str | None = None,
    runner: Runner | None = None,
) -> FfmpegInfo:
    """Locate ffmpeg and ffprobe and check the version (>= 4.4); raise with an install hint."""
    locate = which or shutil.which
    hint = install_hint(platform or sys.platform)
    paths: dict[str, str] = {}
    for name in ("ffmpeg", "ffprobe"):
        found = locate(name)
        if found is None:
            raise FfmpegMissing(f"{name} was not found on PATH. Install it: {hint}")
        paths[name] = found
    try:
        result = (runner or _run_text)([paths["ffmpeg"], "-version"])
    except OSError as exc:  # exists on PATH but cannot be executed
        raise FfmpegMissing(
            f"cannot run {paths['ffmpeg']}: {exc}. Reinstall FFmpeg: {hint}"
        ) from exc
    if result.returncode != 0:
        raise FfmpegMissing(f"`{paths['ffmpeg']} -version` failed. Reinstall FFmpeg: {hint}")
    version = parse_version(result.stdout)
    if version is None:
        logger.warning("could not determine the FFmpeg version (dev build?); continuing")
    elif version < MIN_VERSION:
        need = ".".join(map(str, MIN_VERSION))
        have = ".".join(map(str, version))
        raise FfmpegTooOld(
            f"FFmpeg {have} is too old; {need} or newer is required. Upgrade: {hint}"
        )
    return FfmpegInfo(Path(paths["ffmpeg"]), Path(paths["ffprobe"]), version)


def _secs(value: float) -> str:
    return f"{value:.3f}"


def _music_fades(total: float) -> tuple[float, float]:
    """Music fade-in and fade-out lengths, scaled down together when ``total`` < their sum."""
    span = MUSIC_FADE_IN + MUSIC_FADE_OUT
    scale = min(max(total, 0.0) / span, 1.0)
    return MUSIC_FADE_IN * scale, MUSIC_FADE_OUT * scale


def _fade_filter(duration: float, fade_in: float, fade_out: float) -> str:
    fade_in, fade_out = max(fade_in, 0.0), max(fade_out, 0.0)
    total = fade_in + fade_out
    if total > duration > 0:
        scale = duration / total
        fade_in, fade_out = fade_in * scale, fade_out * scale
    parts: list[str] = []
    if fade_in > 0:
        parts.append(f"fade=t=in:st=0:d={_secs(fade_in)}")
    if fade_out > 0:
        start = max(duration - fade_out, 0.0)
        parts.append(f"fade=t=out:st={_secs(start)}:d={_secs(fade_out)}")
    parts.append("format=yuv420p")
    return ",".join(parts)


def clip_cmd(
    info: FfmpegInfo,
    png: Path,
    out: Path,
    duration: float,
    fps: int,
    crf: int,
    fade_in: float,
    fade_out: float,
    motion: str = "none",
    threads: int | None = None,
) -> list[str]:
    """One slide PNG to a silent H.264 clip with fades (FR-80).

    ``threads`` caps libx264's threads (``-threads N``) when clips encode in parallel.
    """
    if motion != "none":
        raise NotImplementedError(f"motion {motion!r} is not supported by clip_cmd yet")
    cap = [] if threads is None else ["-threads", str(threads)]
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", str(fps), "-t", _secs(duration),
        "-i", str(png),
        "-vf", _fade_filter(duration, fade_in, fade_out),
        "-c:v", "libx264", *cap, "-preset", X264_PRESET, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", str(fps), "-an", str(out),
    ]  # fmt: skip


def concat_list_text(clips: list[Path]) -> str:
    """Concat-demuxer list file text: POSIX paths, single quotes escaped (FR-81)."""
    lines = []
    for clip in clips:
        escaped = clip.as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'\n")
    return "".join(lines)


def concat_cmd(info: FfmpegInfo, list_file: Path, out: Path) -> list[str]:
    """Join clips without re-encoding."""
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out),
    ]  # fmt: skip


def mux_cmd(
    info: FfmpegInfo,
    video: Path,
    out: Path,
    total: float,
    music: Path | None,
    volume: float,
) -> list[str]:
    """Add an audio track: looped/trimmed music (FR-85) or silence (FR-86)."""
    head = [str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    tail = [
        "-c:v", "copy", "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        "-t", _secs(total), "-movflags", "+faststart", str(out),
    ]  # fmt: skip
    if music is None:
        return [
            *head, "-f", "lavfi", "-i", f"anullsrc=r={AUDIO_RATE}:cl=stereo",
            "-map", "0:v", "-map", "1:a", *tail,
        ]  # fmt: skip
    fade_in, fade_out = _music_fades(total)
    graph = (
        f"[1:a]atrim=0:{_secs(total)},asetpts=N/SR/TB,volume={volume:.2f},"
        f"afade=t=in:st=0:d={fade_in:g},"
        f"afade=t=out:st={_secs(max(total - fade_out, 0.0))}:d={fade_out:g},"
        f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo[a]"
    )
    return [
        *head, "-stream_loop", "-1", "-i", str(music), "-filter_complex", graph,
        "-map", "0:v", "-map", "[a]", *tail,
    ]  # fmt: skip


def run(cmd: list[str], *, verbose: bool) -> None:
    """Run a command without a shell; raise ``FfmpegFailed`` with the last stderr lines."""
    if verbose:
        logger.debug("running: %s", shlex.join(cmd))
    try:
        result = _run_text(cmd)
    except OSError as exc:
        raise FfmpegFailed(cmd, f"cannot run {cmd[0]}: {exc}") from exc
    if result.returncode != 0:
        tail = "\n".join(result.stderr.splitlines()[-STDERR_TAIL_LINES:])
        raise FfmpegFailed(cmd, tail)


def _opt_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def probe(info: FfmpegInfo, path: Path) -> ProbeResult:
    """Inspect a media file with ffprobe (JSON output)."""
    cmd = [
        str(info.ffprobe), "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,duration:format=duration",
        "-of", "json", str(path),
    ]  # fmt: skip
    try:
        result = _run_text(cmd)
    except OSError as exc:
        raise FfmpegFailed(cmd, f"cannot run {cmd[0]}: {exc}") from exc
    if result.returncode != 0:
        raise FfmpegFailed(cmd, "\n".join(result.stderr.splitlines()[-STDERR_TAIL_LINES:]))
    try:
        data = json.loads(result.stdout)
        streams: list[dict[str, Any]] = data.get("streams", [])
        video = next(s for s in streams if s.get("codec_type") == "video")
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        duration = _opt_float(data.get("format", {}).get("duration"))
        if duration is None:
            duration = _opt_float(video.get("duration")) or 0.0
        return ProbeResult(
            width=int(video["width"]),
            height=int(video["height"]),
            codec=str(video["codec_name"]),
            pix_fmt=str(video["pix_fmt"]),
            fps=str(video["r_frame_rate"]),
            duration=duration,
            audio_codec=str(audio["codec_name"]) if audio else None,
            audio_duration=_opt_float(audio.get("duration")) if audio else None,
        )
    except (ValueError, KeyError, StopIteration, AttributeError, TypeError) as exc:
        raise FfmpegFailed(cmd, f"unexpected ffprobe output: {exc}") from exc
