"""M11: motion declared in artwork files, redrawn per loop phase on 2.3 living slides."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.compose import DrawContext, EggshellCache, SlideContext
from history_shorts.config import load_script, load_theme
from history_shorts.living.depth import scene_layers
from history_shorts.living.planes import build_stack
from history_shorts.living.types import SpritePlane
from history_shorts.render import scene_expander
from history_shorts.scene import LAYER_DRAWERS, PHASE_DRAWERS, redraws
from history_shorts.scene_config import ArtworkLayer

ScriptFactory = Callable[..., Path]
BASE = {"id": "base", "rect": [-40, -20, 80, 20], "fill": {"color": "brown"}}
FILES: dict[str, list[dict[str, Any]]] = {
    "still": [BASE],
    "flicker": [BASE, {"id": "f", "d": "M -20 -20 C -20 -60 20 -60 20 -20 Z",
                       "fill": {"color": "vermilion"}, "motion": {"kind": "flicker", "amp": 8}}],
    "wave": [BASE, {"id": "w", "rect": [0, -120, 60, 30], "fill": {"color": "vermilion"},
                    "motion": {"kind": "wave", "amp": 0.2, "pole": 0}}],
    "sway": [BASE, {"id": "s", "rect": [-5, -120, 10, 100], "fill": {"color": "gold"},
                    "motion": {"kind": "sway", "deg": 8, "pivot": [0, -20]}}],
    "rise": [BASE, {"id": "r", "d": "M 0 -20 C 10 -50 -10 -80 0 -110",
                    "stroke": {"color": "egg", "width": 2}, "motion": {"kind": "rise", "amp": 8}}],
    "pulse": [BASE, {"id": "p", "ellipse": [0, -60, 30, 30],
                     "fill": {"color": "gold_lt", "alpha": 0.5},
                     "motion": {"kind": "pulse", "amp": 0.4}}],
}  # fmt: skip
MOVERS = ("flicker", "wave", "sway", "rise", "pulse")


@pytest.fixture
def art_theme(tmp_theme: Callable[..., Path]) -> Any:
    path = tmp_theme()
    folder = path.parent / "artwork"
    folder.mkdir(exist_ok=True)
    for name, parts in FILES.items():
        data = {"artwork": "1", "parts": parts}
        (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    return load_theme(path)[0]


def _ctx(theme: Any) -> DrawContext:
    return DrawContext(theme, theme.palette, theme.seed, 0, EggshellCache())


def _at(theme: Any, name: str, phase: float, flip: int = 1) -> Any:
    base = np.zeros((1920, 1080, 3), dtype=np.float32)
    layer = ArtworkLayer(name, 540, 1000, 2.0, flip)
    return PHASE_DRAWERS[ArtworkLayer](base, layer, _ctx(theme), 3, phase)


def _still(theme: Any, name: str) -> Any:
    base = np.zeros((1920, 1080, 3), dtype=np.float32)
    return LAYER_DRAWERS[ArtworkLayer](base, ArtworkLayer(name, 540, 1000, 2.0, 1), _ctx(theme), 3)


@pytest.mark.parametrize("name", MOVERS)
def test_phase0_is_still_and_loop_closes(name: str, art_theme: Any) -> None:  # AC-42
    zero = _at(art_theme, name, 0.0)
    assert np.array_equal(zero, _still(art_theme, name))
    assert np.abs(_at(art_theme, name, 1.0) - zero).max() <= 1 / 255
    moved = np.abs(_at(art_theme, name, 0.25) - zero).max(axis=2) > 1 / 255
    assert moved.any()
    assert not moved[972:1000].any()  # the still base (y -14..0 units) never changes


def _part(name: str, phase: float, palette: Any, tmp_path: Path) -> Any:
    from history_shorts.artwork.load import load_artwork
    from history_shorts.artwork.motion import move_part

    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"artwork": "1", "parts": FILES[name]}), encoding="utf-8")
    part = load_artwork(path, palette)[0].parts[1]
    phis = np.random.default_rng(1).uniform(0, 6.28, (2, 3))
    return part, move_part(part, phase, phis, 1.0)


def test_flicker_keeps_the_bottom(palette: Any, tmp_path: Path) -> None:
    before, after = _part("flicker", 0.3, palette, tmp_path)
    for (_, a), (_, b) in zip(before.ops, after.ops, strict=True):
        for k in range(0, len(a), 2):
            if a[k + 1] == -20:  # on the flame's base line
                assert (b[k], b[k + 1]) == (a[k], a[k + 1])
    assert after.ops != before.ops


def test_sway_keeps_pivot(palette: Any, tmp_path: Path) -> None:
    from history_shorts.artwork.model import Part

    before, after = _part("sway", 0.25, palette, tmp_path)
    probe = Part("probe", (("M", (0.0, -20.0)), ("L", (0.0, -120.0))), motion=before.motion)
    from history_shorts.artwork.motion import move_part

    moved = move_part(probe, 0.25, np.random.default_rng(1).uniform(0, 6.28, (2, 3)), 1.0)
    assert moved.ops[0][1] == pytest.approx((0.0, -20.0))
    assert moved.ops[1][1] != pytest.approx((0.0, -120.0))


def test_pulse_changes_alpha_only(art_theme: Any) -> None:
    zero, quarter = _at(art_theme, "pulse", 0.0), _at(art_theme, "pulse", 0.25)
    ys, xs = np.nonzero(np.abs(quarter - zero).max(axis=2) > 1 / 255)
    assert ((xs - 540) ** 2 + (ys - 880) ** 2 <= 62**2).all()
    assert quarter[880, 540].sum() > zero[880, 540].sum()


@pytest.mark.parametrize("name", MOVERS)
def test_zero_motion_knob_freezes(name: str, art_theme: Any) -> None:
    calm = dataclasses.replace(
        art_theme, living=dataclasses.replace(art_theme.living, artwork_motion=0.0)
    )
    assert np.array_equal(_at(calm, name, 0.3), _at(calm, name, 0.0))


@pytest.mark.parametrize("name", MOVERS)
def test_flip_mirrors_motion(name: str, art_theme: Any) -> None:  # Review Focus 3
    right = _at(art_theme, name, 0.3, 1)
    left = _at(art_theme, name, 0.3, -1)
    assert np.abs(left[:, 1:] - right[:, ::-1][:, :-1]).mean() < 0.003


def test_redraws_only_moving_artwork(art_theme: Any) -> None:
    assert redraws(ArtworkLayer("flicker", 1, 1), art_theme)
    assert not redraws(ArtworkLayer("still", 1, 1), art_theme)
    assert not redraws(ArtworkLayer("missing", 1, 1), art_theme)


def _stack(tmp_script: ScriptFactory, theme: Any, name: str, version: str) -> Any:
    layer = {"type": "artwork", "name": name, "x": 540, "y": 1000}
    slide = {"title": "A", "living": True, "scene": {"layers": [layer]}}
    script = load_script(tmp_script(slides=[slide], extra={"schema_version": version}))[0]
    style, draw = scene_expander(script.slides[0], theme)
    ctx = SlideContext(script, theme, 0, style, draw, False, None)
    layers, depths = scene_layers(script.slides[0], theme)
    return build_stack(ctx, layers, depths, redraw=version == "2.3")


def test_living_slide_gets_a_sprite(tmp_script: ScriptFactory, art_theme: Any) -> None:
    fast = dataclasses.replace(
        art_theme, living=dataclasses.replace(art_theme.living, loop_seconds=0.5)
    )
    moving = _stack(tmp_script, fast, "flicker", "2.3")
    still = _stack(tmp_script, fast, "still", "2.3")
    assert any(isinstance(p, SpritePlane) and p.layer_indices == (0,) for p in moving.scene)
    assert not any(isinstance(p, SpritePlane) for p in still.scene)
