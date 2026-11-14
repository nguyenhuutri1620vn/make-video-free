"""Script contract 2.2 (M9): living slides, particles, synthesized sound cues, layer depth."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts import cues
from history_shorts.config import LayerScene, load_script
from history_shorts.errors import ValidationFailed
from history_shorts.script_config import SfxCue

ScriptFactory = Callable[..., Path]

CLOUDS = {"type": "clouds", "items": [{"x": 300, "y": 400, "scale": 1.0, "flip": 1}]}


def _script(tmp_script: ScriptFactory, version: str, *slides: dict[str, Any]) -> Path:
    return tmp_script(slides=list(slides), extra={"schema_version": version})


def _errors(path: Path) -> list[str]:
    with pytest.raises(ValidationFailed) as exc:
        load_script(path)
    return [f"{i.path}: {i.message}" for i in exc.value.issues.errors]


def test_v22_accepts_living_fields(tmp_script: ScriptFactory) -> None:
    path = _script(
        tmp_script,
        "2.2",
        {"title": "A", "living": True, "particles": "petals", "auto_sfx": False},
    )
    slide = load_script(path)[0].slides[0]
    assert slide.living is True
    assert slide.particles == "petals"
    assert slide.auto_sfx is False


def test_v21_rejects_living_fields(tmp_script: ScriptFactory) -> None:
    path = _script(
        tmp_script,
        "2.1",
        {"title": "A", "living": True, "particles": "petals", "auto_sfx": False},
    )
    errors = _errors(path)
    assert len(errors) == 3
    assert all('requires schema_version "2.2"' in e for e in errors)


def test_v21_script_defaults_unchanged(tmp_script: ScriptFactory) -> None:
    slide = load_script(_script(tmp_script, "2.1", {"title": "A"}))[0].slides[0]
    assert (slide.living, slide.particles, slide.auto_sfx) == (False, "none", True)


def test_sound_cue_parsed(tmp_script: ScriptFactory) -> None:
    cue = {"sound": "gong", "at": 0.4, "gain_db": -6, "shake": True}
    path = _script(tmp_script, "2.2", {"title": "A", "sfx": [cue]})
    got = load_script(path)[0].slides[0].sfx[0]
    assert got == SfxCue(path=None, at=0.4, gain_db=-6.0, sound="gong", duration=None, shake=True)


@pytest.mark.parametrize("cue", [{"at": 0.1}, {"sound": "gong", "file": "a.wav"}])
def test_cue_needs_exactly_one_source(tmp_script: ScriptFactory, cue: dict[str, Any]) -> None:
    path = _script(tmp_script, "2.2", {"title": "A", "sfx": [cue]})
    (path.parent / "a.wav").write_bytes(b"RIFF")
    assert any("give either 'file' or 'sound'" in e for e in _errors(path))


def test_unknown_sound_lists_allowed(tmp_script: ScriptFactory) -> None:
    path = _script(tmp_script, "2.2", {"title": "A", "sfx": [{"sound": "trumpet"}]})
    assert any("gong, drum, bell, whoosh, wind, water" in e for e in _errors(path))


@pytest.mark.parametrize(
    ("cue", "message"),
    [
        ({"sound": "wind"}, "duration"),
        ({"sound": "gong", "duration": 2.0}, "duration"),
        ({"sound": "wind", "duration": 20.0}, "duration"),
        ({"sound": "bell", "shake": True}, "shake"),
    ],
)
def test_sound_cue_rules(tmp_script: ScriptFactory, cue: dict[str, Any], message: str) -> None:
    path = _script(tmp_script, "2.2", {"title": "A", "duration": 14, "sfx": [cue]})
    assert any(message in e for e in _errors(path))


def test_bed_cue_with_duration_ok(tmp_script: ScriptFactory) -> None:
    cue = {"sound": "water", "at": 0.0, "duration": 3.0, "gain_db": -18}
    path = _script(tmp_script, "2.2", {"title": "A", "sfx": [cue]})
    assert load_script(path)[0].slides[0].sfx[0].duration == 3.0


def test_sound_cue_requires_v22(tmp_script: ScriptFactory) -> None:
    path = _script(tmp_script, "2.1", {"title": "A", "sfx": [{"sound": "gong"}]})
    assert any('requires schema_version "2.2"' in e for e in _errors(path))


def test_layer_depth_override(tmp_script: ScriptFactory) -> None:
    layers = [{**CLOUDS, "plane": "near"}, CLOUDS]
    path = _script(tmp_script, "2.2", {"title": "A", "scene": {"layers": layers}})
    scene = load_script(path)[0].slides[0].scene
    assert isinstance(scene, LayerScene)
    assert scene.depths == ("near", None)


def test_layer_depth_requires_v22(tmp_script: ScriptFactory) -> None:
    layers = [{**CLOUDS, "plane": "near"}]
    path = _script(tmp_script, "2.1", {"title": "A", "scene": {"layers": layers}})
    assert any('requires schema_version "2.2"' in e for e in _errors(path))


def test_layer_depth_unknown(tmp_script: ScriptFactory) -> None:
    layers = [{**CLOUDS, "plane": "deep"}]
    path = _script(tmp_script, "2.2", {"title": "A", "scene": {"layers": layers}})
    assert any("far, mid, near" in e for e in _errors(path))


def test_bed_past_slide_end_is_error(tmp_script: ScriptFactory) -> None:  # RF-5
    cue = {"sound": "wind", "at": 2.0, "duration": 2.0}
    path = _script(tmp_script, "2.2", {"title": "A", "duration": 3, "sfx": [cue]})
    script = load_script(path)[0]
    issues = cues.cue_problems(script, [3.0])
    assert [i.path for i in issues if i.severity == "error"] == ["slides[0].sfx[0].duration"]
    assert cues.sfx_inputs(script, [3.0]) == ()


def test_whoosh_accepts_duration(tmp_script: ScriptFactory) -> None:  # review: docs allow it
    cue = {"sound": "whoosh", "at": 0.5, "duration": 1.0}
    path = _script(tmp_script, "2.2", {"title": "A", "duration": 3, "sfx": [cue]})
    assert load_script(path)[0].slides[0].sfx[0].duration == 1.0
