"""Living slides (M9): depth table and the exact plane decomposition of a slide."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.compose import SlideContext, over, render_slide
from history_shorts.config import LAYER_TYPES, CloudItem, CloudsLayer, Script, load_script
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.living.depth import DEFAULT_DEPTH, effective_depths, scene_layers
from history_shorts.living.planes import build_stack, matte, recompose
from history_shorts.render import scene_expander
from history_shorts.scene_config import BoatLayer, MountainsLayer
from history_shorts.textures import finish, grain_field, sheen_field

REPO = Path(__file__).resolve().parents[1]


def _ctx(script: Script, theme: Any, index: int) -> SlideContext:
    style, draw = scene_expander(script.slides[index], theme)
    return SlideContext(script, theme, index, style, draw, False, None)


def _check(script: Script, theme: Any, index: int) -> None:
    ctx = _ctx(script, theme, index)
    layers, depths = scene_layers(script.slides[index], theme)
    stack = build_stack(ctx, layers, depths)
    flat = np.asarray(render_slide(ctx), dtype=np.float32)
    diff = np.abs(recompose(stack) * 255 - flat)
    # the still path floors to 8 bits before Pillow (a ~0.5 bias); clipping in ``finish``
    # moves a handful of very bright pixels a little more
    assert diff.mean() <= 1.0
    assert np.percentile(diff, 99.99) <= 3
    assert diff.max() <= 8


def test_default_depth_covers_all_layer_types() -> None:
    assert set(LAYER_TYPES.values()) <= set(DEFAULT_DEPTH)


def test_effective_depths_monotone() -> None:  # RF-3
    clouds = CloudsLayer((CloudItem(300, 400, 1.0, 1),), "gold", None, None)
    boat = BoatLayer(500, 1000, 1.0, ())
    layers = [clouds, boat, MountainsLayer(700, 40)]
    depths, raised = effective_depths(layers, [None, None, "far"])
    assert depths == ("far", "mid", "mid")
    assert raised == (2,)


def test_matte_recovers_alpha() -> None:
    def draw(base: Any) -> Any:
        cv = Canvas(CANVAS_W, CANVAS_H)
        cv.rect(100, 100, 200, 200).color((200, 40, 40), alpha=0.5).fill()
        return over(base, cv)

    rgba = matte(draw, CANVAS_H, CANVAS_W)
    assert rgba.shape == (CANVAS_H, CANVAS_W, 4)
    assert rgba[150, 150, 3] == pytest.approx(0.5, abs=1 / 255)
    assert rgba[50, 50, 3] == 0.0


def test_finish_equals_sheen_plus_grain(theme: Any) -> None:
    rng_a, rng_b = np.random.default_rng(5), np.random.default_rng(5)
    img = np.random.default_rng(1).random((64, 48, 3)).astype(np.float32)
    sheen = dataclasses.replace(theme.textures.sheen, x=20, y=30, r=40)
    expected = finish(img, rng_a, theme.palette, sheen, theme.textures.grain)
    glow = sheen_field(64, 48, theme.palette, sheen)
    grain = grain_field(64, 48, rng_b, theme.textures.grain)
    got = np.clip((img + glow) * grain[..., None], 0, 1)
    assert np.array_equal(expected, got)


@pytest.mark.parametrize("example", ["hai_ba_trung", "nu_tuong"])
def test_recompose_matches_flat(example: str, theme: Any) -> None:
    script = load_script(REPO / "examples" / example / "script.json")[0]
    for index in range(len(script.slides)):
        _check(script, theme, index)


def test_recompose_matches_flat_with_tone_and_text_in(theme: Any) -> None:
    script = load_script(REPO / "examples" / "hai_ba_trung" / "script.json")[0]
    slides = list(script.slides)
    slides[0] = dataclasses.replace(slides[0], tone="warm", text_in="fade")
    _check(dataclasses.replace(script, slides=tuple(slides)), theme, 0)


def test_no_scene_living_slide(theme: Any) -> None:  # RF-2
    script = load_script(REPO / "examples" / "hai_ba_trung" / "script.json")[0]
    slides = (dataclasses.replace(script.slides[0], scene=None),)
    bare = dataclasses.replace(script, slides=slides)
    ctx = _ctx(bare, theme, 0)
    stack = build_stack(ctx, (), ())
    assert len(stack.scene) == 1 and stack.scene[0].opaque
    _check(bare, theme, 0)


def test_depth_raise_warns(tmp_script: Any) -> None:  # RF-3
    from history_shorts.cli import main

    lotus = {"type": "lotus", "x": 540, "y": 1100, "scale": 1.0}
    mountains = {"type": "mountains", "y": 700, "amp": 40}
    slide = {"title": "A", "living": True, "scene": {"layers": [lotus, mountains]}}
    path = tmp_script(slides=[slide], extra={"schema_version": "2.2"})
    from history_shorts.living.depth import depth_warnings

    script = load_script(path)[0]
    (issue,) = depth_warnings(script)
    assert issue.path == "slides[0].scene.layers[1].plane"
    assert "raised from far to near" in issue.message
    assert main(["validate", "--script", str(path)]) == 0
