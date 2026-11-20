"""M10: characters and boat crew come alive on schema 2.3 living slides."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from helpers.phase import draw_at

from history_shorts.compose import SlideContext
from history_shorts.config import load_script
from history_shorts.layout import REGIONS
from history_shorts.living.depth import scene_layers
from history_shorts.living.planes import build_stack, recompose
from history_shorts.living.types import SpritePlane
from history_shorts.render import scene_expander
from history_shorts.scene import PHASE_DRAWERS, phase_loop_seconds, redraws
from history_shorts.scene_config import BoatLayer, CharactersLayer, CharacterSpec

REPO = Path(__file__).resolve().parents[1]
GROUP = CharactersLayer(
    None,
    1100,
    (
        CharacterSpec("leader", x=400, height=420),
        CharacterSpec("general", x=700, height=380, facing=-1),
    ),
)


@pytest.fixture
def fast(theme: Any) -> Any:
    living = dataclasses.replace(theme.living, loop_seconds=0.5, idle_loop_seconds=1.0)
    return dataclasses.replace(theme, living=living)


def test_character_layers_redraw() -> None:
    assert CharactersLayer in PHASE_DRAWERS and BoatLayer in PHASE_DRAWERS


def test_boat_without_crew_keeps_m9_bob() -> None:
    assert redraws(BoatLayer(500, 1000, 1.0, (CharacterSpec("boat_crew"),)))
    assert not redraws(BoatLayer(500, 1000, 1.0, ()))


def test_idle_loop_length(theme: Any) -> None:
    assert phase_loop_seconds(GROUP, theme.living) == theme.living.idle_loop_seconds


def test_characters_phase0_close_to_still(flat_base: Callable[[], Any], ctx: Any) -> None:
    from history_shorts.scene import LAYER_DRAWERS

    base = flat_base()
    still = LAYER_DRAWERS[CharactersLayer](base.copy(), GROUP, ctx, 3)
    zero = draw_at(base, GROUP, ctx, 0.0)
    diff = np.abs(still - zero)
    assert diff.mean() < 1 / 255 and diff.max() < 0.25


def test_characters_breathe_and_loop(flat_base: Callable[[], Any], ctx: Any) -> None:
    base = flat_base()
    zero, quarter = draw_at(base, GROUP, ctx, 0.0), draw_at(base, GROUP, ctx, 0.25)
    assert np.abs(quarter - zero).max() > 0.2
    assert np.abs(draw_at(base, GROUP, ctx, 1.0) - zero).max() < 0.02


def _template_stack(theme: Any, redraw: bool) -> Any:
    script = load_script(REPO / "tests" / "data" / "living_script.json")[0]
    slide = dataclasses.replace(script.slides[1], particles="none")
    script = dataclasses.replace(script, slides=(script.slides[0], slide))
    style, draw = scene_expander(slide, theme)
    ctx = SlideContext(script, theme, 1, style, draw, False, None)
    layers, depths = scene_layers(slide, theme)
    return build_stack(ctx, layers, depths, redraw=redraw), layers


def test_landscape_crew_animated_with_boat(fast: Any) -> None:
    stack, layers = _template_stack(fast, redraw=True)
    boats = [k for k, layer in enumerate(layers) if isinstance(layer, BoatLayer) and layer.crew]
    assert boats
    frames = round(fast.living.idle_loop_seconds * fast.video.fps)
    for k in boats:
        (sprite,) = [
            p for p in stack.scene if isinstance(p, SpritePlane) and p.layer_indices == (k,)
        ]
        assert sprite.frames == frames
        assert np.abs(sprite.frame(0.25) - sprite.frame(0.0)).max() > 0.2
        assert np.abs(sprite.frame(1.0) - sprite.frame(0.0)).max() < 0.02


def test_first_frame_close_to_preview(fast: Any) -> None:
    still = recompose(_template_stack(fast, redraw=False)[0])
    moving = recompose(_template_stack(fast, redraw=True)[0])
    for name, box in REGIONS.items():
        y0, y1 = int(box.y0), int(box.y1)
        mean = np.abs(moving[y0:y1].mean(axis=(0, 1)) - still[y0:y1].mean(axis=(0, 1)))
        assert mean.max() * 255 <= 2, name
