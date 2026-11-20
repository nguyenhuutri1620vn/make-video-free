"""M10: timed character actions and carriers on schema 2.3 living slides."""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.compose import SlideContext
from history_shorts.config import load_script
from history_shorts.living.depth import scene_layers
from history_shorts.living.planes import build_stack
from history_shorts.living.types import SpritePlane
from history_shorts.render import scene_expander

ScriptFactory = Callable[..., Path]
CLIP = 2.0


@pytest.fixture
def fast(theme: Any) -> Any:
    living = dataclasses.replace(theme.living, loop_seconds=0.5, idle_loop_seconds=1.0)
    video = dataclasses.replace(theme.video, fps=12)
    return dataclasses.replace(theme, living=living, video=video)


def _stack(tmp_script: ScriptFactory, theme: Any, slide: dict[str, Any]) -> tuple[Any, Any]:
    path = tmp_script(slides=[slide], extra={"schema_version": "2.3"})
    script = load_script(path)[0]
    style, draw = scene_expander(script.slides[0], theme)
    ctx = SlideContext(script, theme, 0, style, draw, False, None)
    layers, depths = scene_layers(script.slides[0], theme)
    return build_stack(ctx, layers, depths, redraw=True, clip_seconds=CLIP), layers


def _sprite(stack: Any, k: int) -> SpritePlane:
    (sprite,) = [p for p in stack.scene if isinstance(p, SpritePlane) and p.layer_indices == (k,)]
    return sprite


def _top_row(frame: Any) -> int:
    return int(np.nonzero(frame[..., 3].max(axis=1) > 0.5)[0].min())


LEADER = {"role": "boat_crew", "id": "a", "x": 540, "baseline": 1100, "height": 380}


def test_action_sprite_spans_the_clip(tmp_script: ScriptFactory, fast: Any) -> None:
    slide = {
        "title": "A",
        "duration": 2,
        "living": True,
        "scene": {"layers": [{"type": "characters", "items": [LEADER]}]},
        "actions": [{"who": "a", "do": "rally", "at": 0.2}],
    }
    stack, _ = _stack(tmp_script, fast, slide)
    sprite = _sprite(stack, 0)
    assert sprite.frames == math.ceil(CLIP * fast.video.fps)
    before = sprite.frame(0.1 / CLIP)
    peak = sprite.frame((0.2 + 0.8) / CLIP)
    assert _top_row(peak) < _top_row(before) - 20  # the raised arm is well above the head


def test_idle_only_layer_loops(tmp_script: ScriptFactory, fast: Any) -> None:
    slide = {
        "title": "A",
        "living": True,
        "scene": {"layers": [{"type": "characters", "items": [LEADER]}]},
    }
    stack, _ = _stack(tmp_script, fast, slide)
    sprite = _sprite(stack, 0)
    assert sprite.frames == round(fast.living.idle_loop_seconds * fast.video.fps)
    assert np.abs(sprite.frame(1.0) - sprite.frame(0.0)).max() < 0.02


def _lowest_row(frame: Any, col: int) -> int:
    return int(np.nonzero(frame[:, col, 3] > 0.5)[0].max())


def test_carried_character_moves_with_boat(tmp_script: ScriptFactory, fast: Any) -> None:
    rider = {"role": "boat_crew", "id": "r", "x": 540, "baseline": 1040, "height": 200, "on": 0}
    slide = {
        "title": "A",
        "living": True,
        "scene": {
            "layers": [
                {"type": "boat", "x": 540, "y": 1060, "scale": 1.5},
                {"type": "characters", "items": [rider]},
            ]
        },
        "actions": [{"who": "r", "do": "bow", "at": 0.1}],
    }
    stack, _ = _stack(tmp_script, fast, slide)
    boat, rider_sprite = _sprite(stack, 0), _sprite(stack, 1)
    # the same instant in both sprites: the boat loops every loop_seconds, the rider spans CLIP
    t0, t1 = 0.0, fast.living.loop_seconds / 4
    shifts = []
    for sprite, period in ((boat, fast.living.loop_seconds), (rider_sprite, CLIP)):
        x = 540 - sprite.origin[0]
        a = _lowest_row(sprite.frame(t0 / period), x) + sprite.origin[1]
        b = _lowest_row(sprite.frame(t1 / period), x) + sprite.origin[1]
        shifts.append(b - a)
    assert shifts[0] != 0  # the boat does move
    assert abs(shifts[0] - shifts[1]) <= 1


def test_on_must_name_a_boat(tmp_script: ScriptFactory, theme: Any) -> None:
    from history_shorts.checks import check_all

    rider = {"role": "boat_crew", "id": "r", "x": 540, "height": 200, "on": 0}
    slide = {
        "title": "A",
        "living": True,
        "scene": {
            "layers": [
                {"type": "mountains", "y": 700, "amp": 40},
                {"type": "characters", "items": [rider]},
            ]
        },
    }
    script = load_script(tmp_script(slides=[slide], extra={"schema_version": "2.3"}))[0]
    messages = [f"{i.path}: {i.message}" for i in check_all(script, theme)]
    assert any(".on" in m and "boat" in m for m in messages), messages
