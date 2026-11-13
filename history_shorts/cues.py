"""Sound cues on the timeline: slide sound effects and music cuts (spec A.2.1, A.2.3).

A cue is placed relative to its slide's start, so its checks and its absolute time need the
final slide durations (voice-fitted or FR-83). Everything here is pure; probing the files
for an audio stream is the caller's job.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Final

from history_shorts.config import Script, Slide, Theme
from history_shorts.errors import Issue
from history_shorts.ffmpeg import VoiceInput
from history_shorts.script_config import LIVING_LEVEL, SCHEMA_LEVELS
from history_shorts.sfx import SynthJob
from history_shorts.video import overlaps

# Transitions that move the picture get an automatic whoosh (M9), panned with the motion.
WHOOSH_PAN: Final = {
    "slideleft": (1.0, -1.0),
    "wipeleft": (1.0, -1.0),
    "slideright": (-1.0, 1.0),
    "wiperight": (-1.0, 1.0),
    "slideup": (0.0, 0.0),
    "circleopen": (0.0, 0.0),
}
MOVING_TRANSITIONS: Final = tuple(WHOOSH_PAN)
AUTO_CUE_INDEX: Final = 99  # RNG key of a slide's automatic whoosh
WHOOSH_LEAD: Final = 0.2  # the whoosh starts this long before the transition, ends as long after


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
            if cue.duration is not None and cue.at + cue.duration > seconds:
                message = f"ends at {cue.at + cue.duration:g} s but the slide lasts {seconds:.3f} s"
                issues.append(Issue(name, f"{where}.duration", message, "error"))
            if cue.shake and not slide.living:
                message = 'has no effect without "living": true'
                issues.append(Issue(name, f"{where}.shake", message, "warning"))
            if cue.path is not None and has_audio is not None and not has_audio(cue.path):
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
    """Every file sound effect with its absolute start in milliseconds and its gain."""
    return tuple(
        VoiceInput(cue.path, round((start + cue.at) * 1000), cue.gain_db)
        for slide, start in zip(script.slides, _starts(durations), strict=True)
        for cue in slide.sfx
        if cue.path is not None
    )


def music_cuts(script: Script, durations: list[float]) -> tuple[tuple[float, float], ...]:
    """Absolute (start, end) seconds of every music cut."""
    return tuple(
        (start + slide.music_cut.at, start + slide.music_cut.at + slide.music_cut.duration)
        for slide, start in zip(script.slides, _starts(durations), strict=True)
        if slide.music_cut is not None
    )


def shake_times(slide: Slide) -> tuple[float, ...]:
    """Start times (s, from the slide start) of the cues that shake a living slide."""
    return tuple(sorted(cue.at for cue in slide.sfx if cue.shake))


def _auto_whoosh(
    index: int, slide: Slide, start: float, overlap: float, theme: Theme
) -> SynthJob | None:
    pan = WHOOSH_PAN.get(slide.transition)
    if index == 0 or pan is None or not slide.auto_sfx:
        return None
    at = max(start - WHOOSH_LEAD, 0.0)
    return SynthJob(
        name="whoosh",
        slide_index=index,
        cue_index=AUTO_CUE_INDEX,
        delay_ms=round(at * 1000),
        gain_db=theme.sfx.auto_whoosh_db,
        duration=overlap + 2 * WHOOSH_LEAD,
        pan=pan,
        auto=True,
    )


def synth_jobs(script: Script, durations: list[float], theme: Theme) -> tuple[SynthJob, ...]:
    """Every synthesized sound on the timeline: named cues, then (2.2) automatic whooshes."""
    starts = _starts(durations)
    jobs = [
        SynthJob(
            cue.sound,
            index,
            number,
            round((starts[index] + cue.at) * 1000),
            cue.gain_db,
            cue.duration,
            (0.0, 0.0),
            False,
        )
        for index, slide in enumerate(script.slides)
        for number, cue in enumerate(slide.sfx)
        if cue.sound is not None
    ]
    if SCHEMA_LEVELS.get(script.schema_version, 0) >= LIVING_LEVEL:
        transitions = [slide.transition for slide in script.slides]
        gaps = overlaps(durations, transitions, theme.transition.duration, theme.video.fps)
        for index, slide in enumerate(script.slides):
            overlap = gaps[index - 1] if index > 0 else 0.0
            job = _auto_whoosh(index, slide, starts[index], overlap, theme)
            if job is not None:
                jobs.append(job)
    return tuple(jobs)
