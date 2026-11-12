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
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .config import AudioSpec
from .errors import FfmpegFailed, FfmpegMissing, FfmpegTooOld
from .layout import CANVAS_H, CANVAS_W

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
class VoiceInput:
    """One narration clip placed on the timeline: its file, its start (ms) and its gain."""

    path: Path
    delay_ms: int
    gain_db: float


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


ZOOM_MAX = 1.06  # final zoom factor of ``zoom_in`` (FR-84)
PAN_ZOOM = 1.10  # constant zoom of the ``pan_*`` motions: the view travels the 10 % margin (A.2.1)
MOTIONS: tuple[str, ...] = (
    "none", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down",
)  # fmt: skip
# zoompan (x, y) per pan motion; ``P`` is the progress 0 -> 1 over the clip
_PAN_XY: dict[str, tuple[str, str]] = {
    "pan_left": ("(iw-iw/zoom)*(1-P)", "ih/2-(ih/zoom/2)"),
    "pan_right": ("(iw-iw/zoom)*P", "ih/2-(ih/zoom/2)"),
    "pan_up": ("iw/2-(iw/zoom/2)", "(ih-ih/zoom)*(1-P)"),
    "pan_down": ("iw/2-(iw/zoom/2)", "(ih-ih/zoom)*P"),
}
CUT_RAMP = 0.05  # seconds of fade at each edge of a ``music_cut`` (A.2.1)
ZOOM_PRESCALE = 4  # zoompan floors its crop origin to whole source pixels; 4x keeps the zoom smooth
VIDEO_SIZE = (CANVAS_W, CANVAS_H)


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
    return ",".join(parts)


def _zoom_filter(duration: float, fps: int) -> str:
    """Slow centred zoom from 100 % to ``ZOOM_MAX`` over ``duration`` (FR-84)."""
    frames = max(round(duration * fps), 1)
    width, height = VIDEO_SIZE
    step = f"{ZOOM_MAX - 1:.2f}"
    return (
        f"scale={width * ZOOM_PRESCALE}:{height * ZOOM_PRESCALE},"
        f"zoompan=z='min(1+{step}*on/{frames},{ZOOM_MAX})'"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps}"
    )


def _motion_filter(motion: str, duration: float, fps: int) -> str:
    """The zoompan chain for ``motion`` (A.2.1); ``zoom_in`` keeps the v2.0 string (FR-84)."""
    if motion == "zoom_in":
        return _zoom_filter(duration, fps)
    frames = max(round(duration * fps), 1)
    width, height = VIDEO_SIZE
    progress = f"on/{frames}"
    if motion == "zoom_out":
        z = f"max({ZOOM_MAX:.2f}-{ZOOM_MAX - 1:.2f}*{progress},1)"
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    else:
        z = f"{PAN_ZOOM:.2f}"
        x, y = (part.replace("P", progress) for part in _PAN_XY[motion])
    return (
        f"scale={width * ZOOM_PRESCALE}:{height * ZOOM_PRESCALE},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps}"
    )


@dataclass(frozen=True, slots=True)
class TextLayer:
    """A still RGBA text layer laid over the moving background, fading in (A.2.1)."""

    path: Path
    delay: float
    duration: float


def _layered_clip_cmd(
    info: FfmpegInfo,
    png: Path,
    out: Path,
    duration: float,
    fps: int,
    crf: int,
    fades: str,
    motion: str,
    text: TextLayer,
    cap: list[str],
) -> list[str]:
    """Background (with motion) plus a fading text layer, as one H.264 clip."""
    still = ["-loop", "1", "-framerate", str(fps), "-t", _secs(duration)]
    moving = _motion_filter(motion, duration, fps) + "," if motion != "none" else ""
    graph = (
        f"[0:v]{moving}format=rgba[bg];"
        f"[1:v]format=rgba,fade=t=in:st={_secs(text.delay)}:d={_secs(text.duration)}:alpha=1[tx];"
        f"[bg][tx]overlay=0:0:format=auto,{fades + ',' if fades else ''}format=yuv420p[v]"
    )
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        *still, "-i", str(png), *still, "-i", str(text.path),
        "-filter_complex", graph, "-map", "[v]",
        "-c:v", "libx264", *cap, "-preset", X264_PRESET, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", str(fps), "-an", str(out),
    ]  # fmt: skip


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
    text: TextLayer | None = None,
) -> list[str]:
    """One slide PNG to a silent H.264 clip with fades (FR-80).

    ``threads`` caps libx264's threads (``-threads N``) when clips encode in parallel. With
    ``text``, ``png`` is the background and the text layer fades in over it (A.2.1).
    """
    if motion not in MOTIONS:
        raise ValueError(f"unknown motion {motion!r}")
    fades = _fade_filter(duration, fade_in, fade_out)
    cap = [] if threads is None else ["-threads", str(threads)]
    if text is not None:
        return _layered_clip_cmd(info, png, out, duration, fps, crf, fades, motion, text, cap)
    chain = [_motion_filter(motion, duration, fps)] if motion != "none" else []
    vf = ",".join([*chain, *([fades] if fades else []), "format=yuv420p"])
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-framerate", str(fps), "-t", _secs(duration),
        "-i", str(png),
        "-vf", vf,
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


def xfade_cmd(
    info: FfmpegInfo,
    clips: list[Path],
    starts: list[float],
    transitions: list[str],
    overlaps: list[float],
    out: Path,
    fps: int,
    crf: int,
) -> list[str]:
    """Join clips with ``xfade`` where a slide has a transition, ``concat`` where it cuts
    (A.2.3). ``starts[k]`` is when slide k begins; ``overlaps[k - 1]`` is how far clip k - 1
    runs past that start, so the xfade offset is ``starts[k]`` and the total is unchanged."""
    inputs: list[str] = []
    parts: list[str] = []
    for index, clip in enumerate(clips):
        inputs += ["-i", str(clip)]
        parts.append(f"[{index}:v]fps={fps},settb=1/{fps},format=yuv420p[s{index}]")
    last = "s0"
    for k in range(1, len(clips)):
        label = f"j{k}"
        if transitions[k] == "cut":
            parts.append(f"[{last}][s{k}]concat=n=2:v=1:a=0,settb=1/{fps}[{label}]")
        else:
            parts.append(
                f"[{last}][s{k}]xfade=transition={transitions[k]}"
                f":duration={_secs(overlaps[k - 1])}:offset={_secs(starts[k])}[{label}]"
            )
        last = label
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *inputs,
        "-filter_complex", ";".join(parts), "-map", f"[{last}]",
        "-c:v", "libx264", "-preset", X264_PRESET, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-r", str(fps), "-an", str(out),
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


def _voice_graph(
    voices: list[VoiceInput], total: float, volume: float, audio: AudioSpec, music: bool
) -> str:
    """Filter graph for voices (A.1.7): each clip to 48 kHz stereo at its gain and delay,
    summed with ``amix``; music (if any) ducked by the voice; then one ``loudnorm`` pass."""
    parts: list[str] = []
    labels: list[str] = []
    for number, voice in enumerate(voices, start=1):
        label = f"v{number}"
        labels.append(f"[{label}]")
        parts.append(
            f"[{number}:a]aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
            f"volume={voice.gain_db:g}dB,adelay={voice.delay_ms}|{voice.delay_ms}[{label}]"
        )
    if len(voices) == 1:
        parts.append("[v1]anull[voice]")
    else:
        parts.append(
            "".join(labels) + f"amix=inputs={len(voices)}:normalize=0:duration=longest[voice]"
        )
    # Pad the voice track to the full length: the sidechain and loudnorm stop at the shortest
    # input, so without this the music and the audio stream would end with the last voice.
    parts.append(f"[voice]apad=whole_dur={_secs(total)}[padded]")
    source = "padded"
    if music:
        fade_in, fade_out = _music_fades(total)
        duck = audio.duck
        parts.append(
            f"[{len(voices) + 1}:a]atrim=0:{_secs(total)},asetpts=N/SR/TB,volume={volume:.2f},"
            f"afade=t=in:st=0:d={fade_in:g},"
            f"afade=t=out:st={_secs(max(total - fade_out, 0.0))}:d={fade_out:g},"
            f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo[mus]"
        )
        parts.append("[padded]asplit=2[vk][vm]")
        parts.append(
            f"[mus][vk]sidechaincompress=threshold={duck.threshold:g}:ratio={duck.ratio:g}"
            f":attack={duck.attack_ms:g}:release={duck.release_ms:g}[ducked]"
        )
        parts.append("[ducked][vm]amix=inputs=2:normalize=0:duration=longest[mix]")
        source = "mix"
    parts.append(
        f"[{source}]loudnorm=I={audio.loudness_lufs:g}:TP={audio.true_peak_db:g}:LRA=11,"
        f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo[a]"
    )
    return ";".join(parts)


def voice_mux_cmd(
    info: FfmpegInfo,
    video: Path,
    out: Path,
    total: float,
    voices: list[VoiceInput],
    music: Path | None,
    volume: float,
    audio: AudioSpec,
) -> list[str]:
    """Add narration (and optional ducked music) to the video (A.1.7).

    Used only when at least one voice is given; without voices ``mux_cmd`` runs unchanged.
    """
    if not voices:
        raise ValueError("voice_mux_cmd needs at least one voice")
    inputs: list[str] = ["-i", str(video)]
    for voice in voices:
        inputs += ["-i", str(voice.path)]
    if music is not None:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
    graph = _voice_graph(voices, total, volume, audio, music is not None)
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        *inputs, "-filter_complex", graph,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        "-t", _secs(total), "-movflags", "+faststart", str(out),
    ]  # fmt: skip


def _cut_gain(start: float, end: float) -> str:
    """A ``volume`` filter that is 0 inside [start, end] and ramps back over ``CUT_RAMP``."""
    centre, half = (start + end) / 2, (end - start) / 2
    return f"volume='min(1,max(0,abs(t-{centre:.3f})-{half:.3f})/{CUT_RAMP:g})':eval=frame"


def _music_chain(index: int, total: float, volume: float, cuts: list[tuple[float, float]]) -> str:
    fade_in, fade_out = _music_fades(total)
    gates = "".join(f"{_cut_gain(start, end)}," for start, end in cuts)
    return (
        f"[{index}:a]atrim=0:{_secs(total)},asetpts=N/SR/TB,volume={volume:.2f},"
        f"afade=t=in:st=0:d={fade_in:g},"
        f"afade=t=out:st={_secs(max(total - fade_out, 0.0))}:d={fade_out:g},{gates}"
        f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo[mus]"
    )


def _delayed(index: int, clip: VoiceInput, label: str) -> str:
    return (
        f"[{index}:a]aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
        f"volume={clip.gain_db:g}dB,adelay={clip.delay_ms}|{clip.delay_ms}[{label}]"
    )


def _bus(labels: list[str], name: str, total: float) -> str:
    """Sum ``labels`` and pad the result to the full length, as ``[name]``."""
    if len(labels) == 1:
        joined = f"{labels[0]}anull[{name}_raw]"
    else:
        joined = (
            "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest[{name}_raw]"
        )
    return f"{joined};[{name}_raw]apad=whole_dur={_secs(total)}[{name}]"


@dataclass(frozen=True, slots=True)
class MixPlan:
    """Everything the A.2 mix needs besides the video: voices, effects, music and its cuts."""

    voices: tuple[VoiceInput, ...] = ()
    sfx: tuple[VoiceInput, ...] = ()
    cuts: tuple[tuple[float, float], ...] = ()


def _mix_graph(plan: MixPlan, total: float, music: bool, volume: float, audio: AudioSpec) -> str:
    """Voices (ducking the music), music with its cuts, and sound effects mixed after the
    ducking; then one ``loudnorm`` pass (A.2.3). Input 0 is the video."""
    parts: list[str] = []
    buses: list[str] = []
    voices = [f"[v{n}]" for n in range(1, len(plan.voices) + 1)]
    parts += [_delayed(n, voice, f"v{n}") for n, voice in enumerate(plan.voices, start=1)]
    if voices:
        parts.append(_bus(voices, "speech", total))
    music_index = len(plan.voices) + 1
    if music:
        parts.append(_music_chain(music_index, total, volume, list(plan.cuts)))
    if voices and music:
        duck = audio.duck
        parts.append("[speech]asplit=2[vk][vm]")
        parts.append(
            f"[mus][vk]sidechaincompress=threshold={duck.threshold:g}:ratio={duck.ratio:g}"
            f":attack={duck.attack_ms:g}:release={duck.release_ms:g}[ducked]"
        )
        buses += ["[ducked]", "[vm]"]
    elif voices:
        buses.append("[speech]")
    elif music:
        buses.append("[mus]")
    first_fx = music_index + (1 if music else 0)
    fx = [f"[f{n}]" for n in range(1, len(plan.sfx) + 1)]
    parts += [_delayed(first_fx + n - 1, cue, f"f{n}") for n, cue in enumerate(plan.sfx, start=1)]
    if fx:
        parts.append(_bus(fx, "fx", total))
        buses.append("[fx]")
    parts.append(
        "".join(buses) + f"amix=inputs={len(buses)}:normalize=0:duration=longest[mix]"
        if len(buses) > 1
        else f"{buses[0]}anull[mix]"
    )
    parts.append(
        f"[mix]loudnorm=I={audio.loudness_lufs:g}:TP={audio.true_peak_db:g}:LRA=11,"
        f"aresample={AUDIO_RATE},aformat=channel_layouts=stereo[a]"
    )
    return ";".join(parts)


def mix_cmd(
    info: FfmpegInfo,
    video: Path,
    out: Path,
    total: float,
    plan: MixPlan,
    music: Path | None,
    volume: float,
    audio: AudioSpec,
) -> list[str]:
    """The audio mux for a render. Without effects or cuts it is exactly ``voice_mux_cmd`` or
    ``mux_cmd`` (A.1, FR-85/86); otherwise one graph mixes everything (A.2.3)."""
    cuts = plan.cuts if music is not None else ()
    if not plan.sfx and not cuts:
        if plan.voices:
            return voice_mux_cmd(info, video, out, total, list(plan.voices), music, volume, audio)
        return mux_cmd(info, video, out, total, music, volume)
    inputs: list[str] = ["-i", str(video)]
    for voice in plan.voices:
        inputs += ["-i", str(voice.path)]
    if music is not None:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
    for cue in plan.sfx:
        inputs += ["-i", str(cue.path)]
    graph = _mix_graph(replace(plan, cuts=cuts), total, music is not None, volume, audio)
    return [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        *inputs, "-filter_complex", graph,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ar", str(AUDIO_RATE), "-ac", "2",
        "-t", _secs(total), "-movflags", "+faststart", str(out),
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


def audio_duration(info: FfmpegInfo, path: Path) -> float:
    """Length in seconds of an audio file, from ffprobe's container duration (A.1.5)."""
    cmd = [
        str(info.ffprobe), "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
    ]  # fmt: skip
    try:
        result = _run_text(cmd)
    except OSError as exc:
        raise FfmpegFailed(cmd, f"cannot run {cmd[0]}: {exc}") from exc
    if result.returncode != 0:
        raise FfmpegFailed(cmd, "\n".join(result.stderr.splitlines()[-STDERR_TAIL_LINES:]))
    seconds = _opt_float(result.stdout.strip())
    if seconds is None:
        raise FfmpegFailed(cmd, f"no duration in ffprobe output: {result.stdout.strip()!r}")
    return seconds


def has_audio(info: FfmpegInfo, path: Path, runner: Runner | None = None) -> bool:
    """True when ffprobe finds at least one audio stream in ``path``; False on any failure."""
    cmd = [
        str(info.ffprobe), "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path),
    ]  # fmt: skip
    try:
        result = (runner or _run_text)(cmd)
    except OSError:
        return False
    return result.returncode == 0 and "audio" in result.stdout
