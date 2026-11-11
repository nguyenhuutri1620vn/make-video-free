"""Narration exchange with the owner's sound project and voice timing (v2.1, spec A.1).

history-shorts writes the narration text (``export_narration``) and reads the audio manifest the
sound project writes (``load_manifest``). The two sides share files only: no TTS runs here (C-01)
and nothing starts or calls the sound project (C-02). ``plan_audio`` checks the voices against
the script and turns them into slide durations (A.1.6) and voice placements for the mix (A.1.7).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from history_shorts import narration
from history_shorts.config import AudioSpec, Script, Slide, Theme
from history_shorts.errors import Issue, Issues
from history_shorts.ffmpeg import VoiceInput
from history_shorts.script_config import MAX_SLIDE_SECONDS, slide_duration
from history_shorts.validation import Ctx, read_json_object

NARRATION_KIND: Final = "history-shorts.narration"
AUDIO_KIND: Final = "history-shorts.audio"
MANIFEST_SCHEMA: Final = "1.0"  # both manifests; a different major version is rejected
NARRATION_MANIFEST: Final = "manifest.json"
MIN_VOICE_SECONDS: Final = 0.3
MAX_VOICE_SECONDS: Final = 14.0
MAX_GAIN_DB: Final = 12.0

Measure = Callable[[Path], float]


@dataclass(frozen=True, slots=True)
class Segment:
    """One line of the audio manifest: which file holds the voice for which slide."""

    id: str
    file: str
    text_sha256: str
    gain_db: float


@dataclass(frozen=True, slots=True)
class AudioManifest:
    path: Path
    sha256: str
    segments: Mapping[str, Segment] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Voice:
    """A checked voice clip for one narrated slide; ``seconds`` is its measured length."""

    slide_index: int  # 0-based position in ``script.slides``
    slide_id: str
    path: Path
    seconds: float
    gain_db: float


@dataclass(frozen=True, slots=True)
class AudioPlan:
    """Voices and slide durations for one render, with the manifest they came from."""

    manifest: AudioManifest
    voices: tuple[Voice, ...]
    durations: tuple[float, ...]


# --------------------------------------------------------------------------------------
# Timing (A.1.6)
# --------------------------------------------------------------------------------------


def ceil_to_frame(seconds: float, fps: int) -> float:
    """``seconds`` rounded up to a whole frame; the epsilon keeps 2.0000000001 s at 2 s."""
    return math.ceil(round(seconds * fps, 6)) / fps


def voiced_slide_seconds(slide: Slide, voice_seconds: float, fps: int, audio: AudioSpec) -> float:
    """Length of a slide that has a voice: ``required = ceil_to_frame(lead_in + v + tail)``.

    An absent ``duration`` takes ``required``; a ``duration`` of at least ``required`` wins.
    A shorter explicit ``duration`` is an error and is raised by ``plan_audio``.
    """
    required = ceil_to_frame(audio.lead_in + voice_seconds + audio.tail, fps)
    if slide.duration is None:
        return required
    return round(slide.duration * fps) / fps


# --------------------------------------------------------------------------------------
# Export (A.1.3)
# --------------------------------------------------------------------------------------


def export_narration(script: Script, out_dir: Path) -> Path:
    """Write ``<id>.txt`` for every narrated slide and ``manifest.json`` into ``out_dir``.

    Byte-identical on a second run for an unchanged script. Returns the manifest path.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    segments: list[dict[str, object]] = []
    for slide in script.slides:
        if slide.narration is None:
            continue
        name = f"{slide.id}.txt"
        data = narration.file_bytes(slide.narration)
        (out_dir / name).write_bytes(data)
        segments.append(
            {
                "id": slide.id,
                "file": name,
                "text_sha256": hashlib.sha256(data).hexdigest(),
                "chars": len(narration.normalise(slide.narration)),
            }
        )
    manifest = {
        "kind": NARRATION_KIND,
        "schema_version": MANIFEST_SCHEMA,
        "script_title": script.title,
        "segments": segments,
    }
    path = out_dir / NARRATION_MANIFEST
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------
# Audio manifest (A.1.4)
# --------------------------------------------------------------------------------------


def _safe_relative(file: str) -> bool:
    """A manifest path must be relative, with no ``..`` parts (A.1.4)."""
    path = Path(file)
    return bool(file) and not path.is_absolute() and ".." not in path.parts


def _read_segment(ctx: Ctx, raw: object, seen: set[str]) -> Segment | None:
    if not isinstance(raw, dict):
        ctx.error("must be an object")
        return None
    obj = ctx.mapping(raw, ("id", "file", "text_sha256", "gain_db"))
    errors = len(ctx.issues.errors)
    sid = ctx.str_(obj, "id")
    file = ctx.str_(obj, "file")
    digest = ctx.str_(obj, "text_sha256")
    gain = ctx.num(obj, "gain_db", default=0.0, lo=-MAX_GAIN_DB, hi=MAX_GAIN_DB)
    if file and not _safe_relative(file):
        ctx.at("file").error("must be a relative path inside the manifest folder")
    if sid in seen:
        ctx.at("id").error(f'duplicate segment id "{sid}"')
    seen.add(sid)
    if len(ctx.issues.errors) > errors:
        return None
    return Segment(id=sid, file=file, text_sha256=digest, gain_db=gain)


def load_manifest(path: Path, issues: Issues) -> AudioManifest | None:
    """Read and check an audio manifest; record issues and return None when it is unusable."""
    data = read_json_object(path, issues)
    if data is None:
        return None
    ctx = Ctx(path.name, issues)
    kind = ctx.str_(data, "kind")
    if kind and kind != AUDIO_KIND:
        ctx.at("kind").error(f'must be "{AUDIO_KIND}"')
    version = ctx.str_(data, "schema_version")
    if version and version.split(".")[0] != MANIFEST_SCHEMA.split(".")[0]:
        ctx.at("schema_version").error(f'unsupported schema_version "{version}"')
    seen: set[str] = set()
    segments: dict[str, Segment] = {}
    if "segments" not in data:
        ctx.at("segments").missing()
    for child, raw in ctx.at("segments").items(data.get("segments", [])):
        segment = _read_segment(child, raw, seen)
        if segment is not None:
            segments[segment.id] = segment
    if issues.errors:
        return None
    return AudioManifest(path=path.resolve(), sha256=_file_sha256(path), segments=segments)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------
# Matching voices to the script (A.1.5) and timing
# --------------------------------------------------------------------------------------


def _voice_path(manifest: AudioManifest, segment: Segment) -> Path:
    """The segment's file, resolved against the manifest folder; must stay inside it."""
    base = manifest.path.parent.resolve()
    resolved = (base / segment.file).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"{segment.file} is outside {base}")
    return resolved


def plan_audio(
    script: Script,
    theme: Theme,
    manifest: AudioManifest,
    measure: Measure,
    issues: Issues,
) -> AudioPlan | None:
    """Check the manifest against the script, measure each voice and time the slides.

    Every problem is recorded in ``issues`` (A.1.5); the plan is returned only when there are
    no errors. ``measure`` returns a file's length in seconds (ffprobe in the CLI).
    """
    fps, audio = theme.video.fps, theme.audio
    name = manifest.path.name
    narrated = [(i, s) for i, s in enumerate(script.slides) if s.narration is not None]
    stale = [s.id for _, s in narrated if _is_stale(manifest, s)]
    if stale:
        issues.error(
            name, "segments", "narration changed since recording; re-record: " + ", ".join(stale)
        )
    narrated_ids = {slide.id for _, slide in narrated}
    for known in manifest.segments.values():
        if known.id not in narrated_ids:
            issues.warning(name, f"segments.{known.id}", "no narrated slide has this id (ignored)")
    voices: list[Voice] = []
    for index, slide in narrated:
        segment = manifest.segments.get(slide.id)
        if segment is None:
            issues.error(name, f"segments.{slide.id}", f"no audio segment for slide {slide.id}")
            continue
        voice = _measure_voice(issues, name, manifest, segment, index, slide, measure)
        if voice is not None:
            voices.append(voice)
    if issues.errors:
        return None
    durations = _slide_durations(script, fps, audio, voices, issues)
    if issues.errors:
        return None
    return AudioPlan(manifest=manifest, voices=tuple(voices), durations=tuple(durations))


def _is_stale(manifest: AudioManifest, slide: Slide) -> bool:
    segment = manifest.segments.get(slide.id)
    return segment is None or segment.text_sha256 != narration.text_sha256(slide.narration or "")


def _measure_voice(
    issues: Issues,
    name: str,
    manifest: AudioManifest,
    segment: Segment,
    index: int,
    slide: Slide,
    measure: Measure,
) -> Voice | None:
    where = f"segments.{slide.id}"
    if segment.text_sha256 != narration.text_sha256(slide.narration or ""):
        return None  # reported once for all stale slides in ``plan_audio``
    try:
        path = _voice_path(manifest, segment)
    except ValueError as exc:
        issues.error(name, where, str(exc))
        return None
    if not path.is_file():
        issues.error(name, where, f"audio file not found: {path}")
        return None
    try:
        seconds = measure(path)
    except Exception as exc:  # noqa: BLE001 - any ffprobe failure is a bad audio file here
        issues.error(name, where, f"cannot read audio file {path}: {exc}")
        return None
    if not MIN_VOICE_SECONDS <= seconds <= MAX_VOICE_SECONDS:
        issues.error(
            name,
            where,
            f"audio length {seconds:.2f} s is outside "
            f"{MIN_VOICE_SECONDS:g}–{MAX_VOICE_SECONDS:g} s: {path}",
        )
        return None
    return Voice(index, slide.id, path, seconds, segment.gain_db)


def _slide_durations(
    script: Script, fps: int, audio: AudioSpec, voices: list[Voice], issues: Issues
) -> list[float]:
    by_index = {voice.slide_index: voice for voice in voices}
    durations: list[float] = []
    for index, slide in enumerate(script.slides):
        voice = by_index.get(index)
        if voice is None:
            durations.append(slide_duration(slide, fps))
            continue
        seconds = voiced_slide_seconds(slide, voice.seconds, fps, audio)
        required = ceil_to_frame(audio.lead_in + voice.seconds + audio.tail, fps)
        if required > MAX_SLIDE_SECONDS:
            issues.error(
                script.path.name,
                f"slides[{index}]",
                f"voice is {voice.seconds:.2f} s, so the slide needs {required:.2f} s; "
                f"the limit is {MAX_SLIDE_SECONDS:g} s",
            )
        elif slide.duration is not None and seconds < required:
            issues.error(
                script.path.name,
                f"slides[{index}].duration",
                f"{slide.duration:g} s is shorter than the voice needs ({required:.2f} s)",
            )
        durations.append(seconds)
    return durations


def voice_offsets(
    durations: list[float], voices: tuple[Voice, ...], audio: AudioSpec
) -> list[tuple[Voice, float]]:
    """Each voice with its start time on the timeline: slide start + ``lead_in`` (A.1.6)."""
    starts = [0.0]
    for seconds in durations:
        starts.append(starts[-1] + seconds)
    return [(voice, starts[voice.slide_index] + audio.lead_in) for voice in voices]


def narration_without_audio(script: Script, path_name: str) -> Issue | None:
    """The warning for a narrated script rendered without ``--audio`` (A.1.5)."""
    if any(slide.narration is not None for slide in script.slides):
        return Issue(
            path_name,
            "slides",
            "narration present but no --audio: slides use auto timing and no voice",
            "warning",
        )
    return None


def voice_inputs(
    plan: AudioPlan, durations: list[float], audio: AudioSpec
) -> tuple[VoiceInput, ...]:
    """The voices for the mix: start in milliseconds and gain, theme trim included (A.1.7)."""
    return tuple(
        VoiceInput(
            path=voice.path,
            delay_ms=round(start * 1000),
            gain_db=voice.gain_db + audio.voice_gain_db,
        )
        for voice, start in voice_offsets(durations, plan.voices, audio)
    )
