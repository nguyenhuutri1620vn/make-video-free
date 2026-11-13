"""Cue planning for synthesized sounds and the automatic transition whoosh (M9)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from history_shorts import cues
from history_shorts.config import Theme, load_script

ScriptFactory = Callable[..., Path]


def _load(tmp_script: ScriptFactory, version: str, *slides: dict[str, Any]) -> Any:
    path = tmp_script(slides=list(slides), extra={"schema_version": version})
    return load_script(path)[0]


def _three(**second: Any) -> list[dict[str, Any]]:
    return [
        {"title": "A", "duration": 3},
        {"title": "B", "duration": 3, **second},
        {"title": "C", "duration": 3},
    ]


def test_auto_whoosh_on_moving_transition(tmp_script: ScriptFactory, theme: Theme) -> None:
    script = _load(tmp_script, "2.2", *_three(transition="slideleft"))
    jobs = cues.synth_jobs(script, [3.0, 3.0, 3.0], theme)
    assert len(jobs) == 1
    job = jobs[0]
    assert (job.name, job.slide_index, job.cue_index, job.auto) == ("whoosh", 1, 99, True)
    assert job.delay_ms == 2800
    assert job.pan == (1.0, -1.0)
    assert job.gain_db == -14.0
    assert job.duration == 0.5 + 0.4


def test_auto_whoosh_pan_follows_direction(tmp_script: ScriptFactory, theme: Theme) -> None:
    for name, pan in (("wiperight", (-1.0, 1.0)), ("circleopen", (0.0, 0.0))):
        script = _load(tmp_script, "2.2", *_three(transition=name))
        assert cues.synth_jobs(script, [3.0, 3.0, 3.0], theme)[0].pan == pan


def test_no_auto_whoosh_for_fade_opt_out_or_v21(tmp_script: ScriptFactory, theme: Theme) -> None:
    fade = _load(tmp_script, "2.2", *_three(transition="fade"))
    off = _load(tmp_script, "2.2", *_three(transition="slideleft", auto_sfx=False))
    v21 = _load(tmp_script, "2.1", *_three(transition="slideleft"))
    for script in (fade, off, v21):
        assert cues.synth_jobs(script, [3.0, 3.0, 3.0], theme) == ()


def test_named_cue_job(tmp_script: ScriptFactory, theme: Theme) -> None:
    slides = _three()
    slides[2]["sfx"] = [{"sound": "bell", "at": 1.0, "gain_db": -3}]
    script = _load(tmp_script, "2.2", *slides)
    (job,) = cues.synth_jobs(script, [3.0, 3.0, 3.0], theme)
    assert (job.name, job.slide_index, job.cue_index, job.delay_ms) == ("bell", 2, 0, 7000)
    assert (job.gain_db, job.duration, job.pan, job.auto) == (-3.0, None, (0.0, 0.0), False)


def test_file_and_sound_cues_split(tmp_script: ScriptFactory, theme: Theme) -> None:
    sfx = [{"file": "a.wav", "at": 0.5}, {"sound": "drum", "at": 1.0}]
    path = tmp_script(slides=[{"title": "A", "sfx": sfx}], extra={"schema_version": "2.2"})
    (path.parent / "a.wav").write_bytes(b"RIFF")
    script = load_script(path)[0]
    assert [i.delay_ms for i in cues.sfx_inputs(script, [3.0])] == [500]
    assert [j.name for j in cues.synth_jobs(script, [3.0], theme)] == ["drum"]


def test_shake_times(tmp_script: ScriptFactory) -> None:
    sfx = [
        {"sound": "gong", "at": 2.0, "shake": True},
        {"sound": "drum", "at": 0.5, "shake": True},
        {"sound": "bell", "at": 1.0},
    ]
    script = _load(tmp_script, "2.2", {"title": "A", "duration": 3, "living": True, "sfx": sfx})
    assert cues.shake_times(script.slides[0]) == (0.5, 2.0)


def test_shake_without_living_warns(tmp_script: ScriptFactory) -> None:  # RF-5
    sfx = [{"sound": "gong", "at": 0.5, "shake": True}]
    script = _load(tmp_script, "2.2", {"title": "A", "duration": 3, "sfx": sfx})
    issues = cues.cue_problems(script, [3.0])
    assert [(i.path, i.severity) for i in issues] == [("slides[0].sfx[0].shake", "warning")]
