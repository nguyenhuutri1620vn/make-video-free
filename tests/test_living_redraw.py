"""M10: phase-redrawn scene layers on schema 2.3 living slides."""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, SlideContext, over
from history_shorts.config import load_script
from history_shorts.living import planes as planes_mod
from history_shorts.living.assets import render_living
from history_shorts.living.depth import scene_layers
from history_shorts.living.planes import build_stack, recompose
from history_shorts.living.types import SpritePlane, frame_name, frame_pattern
from history_shorts.primitives import FloatImage
from history_shorts.render import scene_expander
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene_config import MountainsLayer
from history_shorts.script_config import ANIMATED_SCHEMA_VERSION, SUPPORTED_SCHEMA_VERSIONS

REPO = Path(__file__).resolve().parents[1]


def _fake_at(img: FloatImage, layer: Any, ctx: DrawContext, index: int, phase: float) -> FloatImage:
    """The still mountains plus a small square that moves with the phase (still at p = 0)."""
    out = LAYER_DRAWERS[MountainsLayer](img, layer, ctx, index)
    cv = Canvas(1080, 1920)
    x = 400 + 40 * math.sin(2 * math.pi * phase)
    cv.rect(x, 600, 30, 30).color((200, 40, 40)).fill()
    return over(out, cv)


def _still_with_square(img: FloatImage, layer: Any, ctx: DrawContext, index: int) -> FloatImage:
    return _fake_at(img, layer, ctx, index, 0.0)


@pytest.fixture
def fake_redraw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(planes_mod, "PHASE_DRAWERS", {MountainsLayer: _fake_at})
    drawers = dict(planes_mod.LAYER_DRAWERS)
    drawers[MountainsLayer] = _still_with_square
    monkeypatch.setattr(planes_mod, "LAYER_DRAWERS", drawers)


@pytest.fixture
def fast(theme: Any) -> Any:
    """The default theme with the shortest allowed loop, so tests draw few phases."""
    return dataclasses.replace(theme, living=dataclasses.replace(theme.living, loop_seconds=0.5))


def _script() -> Any:
    script = load_script(REPO / "tests" / "data" / "living_script.json")[0]
    return script


def _stack(theme: Any, redraw: bool) -> Any:
    script = _script()
    slides = (dataclasses.replace(script.slides[0], sfx=()),)
    script = dataclasses.replace(script, slides=slides)
    style, draw = scene_expander(script.slides[0], theme)
    ctx = SlideContext(script, theme, 0, style, draw, False, None)
    layers, depths = scene_layers(script.slides[0], theme)
    return build_stack(ctx, layers, depths, redraw=redraw), layers


def test_schema_23_supported() -> None:
    assert ANIMATED_SCHEMA_VERSION == "2.3"
    assert SUPPORTED_SCHEMA_VERSIONS[-1] == "2.3"


def test_schema_23_script_loads(tmp_script: Any) -> None:
    mountains = {"type": "mountains", "y": 700, "amp": 40}
    slide = {"title": "A", "living": True, "scene": {"layers": [mountains]}}
    path = tmp_script(slides=[slide], extra={"schema_version": "2.3"})
    script, issues = load_script(path)
    assert script.schema_version == "2.3"
    assert not [i for i in issues if i.severity == "error"]


def test_redraw_layer_becomes_sprite_only_with_redraw(fast: Any, fake_redraw: None) -> None:
    still, layers = _stack(fast, redraw=False)
    moving, _ = _stack(fast, redraw=True)
    k = next(i for i, layer in enumerate(layers) if isinstance(layer, MountainsLayer))
    assert not any(isinstance(p, SpritePlane) and k in p.layer_indices for p in still.scene)
    sprites = [p for p in moving.scene if isinstance(p, SpritePlane) and p.layer_indices == (k,)]
    assert len(sprites) == 1
    sprite = sprites[0]
    assert not np.array_equal(sprite.frame(0.25), sprite.frame(0.0))
    assert np.array_equal(sprite.frame(1.0), sprite.frame(0.0))


def test_redraw_phase0_matches_still(fast: Any, fake_redraw: None) -> None:
    still, _ = _stack(fast, redraw=False)
    moving, _ = _stack(fast, redraw=True)
    diff = np.abs(recompose(moving) - recompose(still))
    assert diff.mean() < 0.5 / 255
    assert diff.max() <= 3 / 255


def test_frame_names_grow_past_999() -> None:
    assert frame_pattern(48) == "%03d.png" and frame_name(48, 7) == "007.png"
    assert frame_pattern(1000) == "%03d.png"
    assert frame_pattern(1001) == "%04d.png" and frame_name(1200, 7) == "0007.png"


def test_render_living_redraw_gate(tmp_path: Path, fast: Any, fake_redraw: None) -> None:
    script = _script()
    old = render_living(script, fast, [4.0, 3.0], tmp_path / "a")
    new_script = dataclasses.replace(script, schema_version="2.3")
    new = render_living(new_script, fast, [4.0, 3.0], tmp_path / "b")
    count = [sum(p.kind == "sprite" for p in c.planes) for c in (old[0], new[0]) if c]
    assert count[1] == count[0] + 1
