"""Sound cues on the timeline: slide sound effects and music cuts (spec A.2.1, A.2.3).

A cue is placed relative to its slide's start, so its checks and its absolute time need the
final slide durations (voice-fitted or FR-83). Everything here is pure; probing the files
for an audio stream is the caller's job.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from history_shorts.config import Script
from history_shorts.errors import Issue
from history_shorts.ffmpeg import VoiceInput


def _starts(durations: list[float]) -> list[float]:
    return [sum(durations[:k]) for k in range(len(durations))]


def cue_problems(
    script: Script, durations: list[float], has_audio: Callable[[Path], bool] | None = None
) -> list[Issue]:
    """Errors for cues that start after their slide ends or that have no audio stream."""
    name = script.path.name
    issues: list[Issue] = []
    for index, (slide, seconds) in enumerate(zip(script.slides, durations, strict=True)):
        for number, cue in enumerate(slide.sfx):
            where = f"slides[{index}].sfx[{number}]"
            if cue.at >= seconds:
                message = f"starts at {cue.at:g} s but the slide lasts {seconds:.3f} s"
                issues.append(Issue(name, f"{where}.at", message, "error"))
            if has_audio is not None and not has_audio(cue.path):
                message = f"no audio stream in {cue.path}"
                issues.append(Issue(name, f"{where}.file", message, "error"))
        cut = slide.music_cut
        if cut is not None and cut.at + cut.duration > seconds:
            message = f"ends at {cut.at + cut.duration:g} s but the slide lasts {seconds:.3f} s"
            issues.append(Issue(name, f"slides[{index}].music_cut", message, "error"))
    return issues


def music_cut_without_music(script: Script) -> Issue | None:
    """The warning for a ``music_cut`` rendered without ``--music`` (A.2.1)."""
    if any(slide.music_cut is not None for slide in script.slides):
        return Issue(
            script.path.name, "slides", "music_cut has no effect without --music", "warning"
        )
    return None


def sfx_inputs(script: Script, durations: list[float]) -> tuple[VoiceInput, ...]:
    """Every sound effect with its absolute start in milliseconds and its gain."""
    return tuple(
        VoiceInput(cue.path, round((start + cue.at) * 1000), cue.gain_db)
        for slide, start in zip(script.slides, _starts(durations), strict=True)
        for cue in slide.sfx
    )


def music_cuts(script: Script, durations: list[float]) -> tuple[tuple[float, float], ...]:
    """Absolute (start, end) seconds of every music cut."""
    return tuple(
        (start + slide.music_cut.at, start + slide.music_cut.at + slide.music_cut.duration)
        for slide, start in zip(script.slides, _starts(durations), strict=True)
        if slide.music_cut is not None
    )
