"""Scene layers without people from the visual backlog (docs/visual_backlog.md, spec 6.3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.config import DrumLayer, GongLayer, TempleLayer, load_script
from history_shorts.errors import ValidationFailed
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.drum import draw_drum
from history_shorts.scene.gong import draw_gong
from history_shorts.scene.temple import draw_temple

Base = Callable[[], FloatImage]
ScriptFactory = Callable[..., Path]


def _layer(tmp_script: ScriptFactory, layer: dict[str, Any]) -> Any:
    path = tmp_script(slides=[{"title": "A", "scene": {"layers": [layer]}}])
    return load_script(path)[0].slides[0].scene.layers[0]


def _changed(before: FloatImage, after: FloatImage) -> tuple[Any, Any]:
    return np.nonzero(np.any(after != before, axis=-1))


# --- drum (backlog #1) --------------------------------------------------------------------


def test_drum_parses_with_defaults(tmp_script: ScriptFactory) -> None:
    layer = _layer(tmp_script, {"type": "drum", "x": 540, "y": 700, "r": 300})
    assert layer == DrumLayer(540, 700, 300)
    assert LAYER_DRAWERS[DrumLayer] is draw_drum


def test_drum_bird_count_is_limited(tmp_script: ScriptFactory) -> None:
    with pytest.raises(ValidationFailed):
        _layer(tmp_script, {"type": "drum", "x": 540, "y": 700, "r": 300, "birds": 40})


def test_drum_stays_inside_its_face(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_drum(base.copy(), DrumLayer(540, 800, 200), ctx, 1)
    ys, xs = _changed(base, after)
    assert xs.size > 100_000
    radius = np.hypot(xs - 540, ys - 800)
    assert radius.max() <= 200 + 3  # rim ring: half its stroke plus antialiasing


def test_drum_is_deterministic_and_counts_birds(ctx: Any, flat_base: Base) -> None:
    layer = DrumLayer(540, 800, 200)
    a = draw_drum(flat_base(), layer, ctx, 1)
    assert np.array_equal(a, draw_drum(flat_base(), layer, ctx, 1))
    assert not np.array_equal(a, draw_drum(flat_base(), DrumLayer(540, 800, 200, 4), ctx, 1))


# --- gong (backlog #2) --------------------------------------------------------------------


def test_gong_parses(tmp_script: ScriptFactory) -> None:
    layer = _layer(tmp_script, {"type": "gong", "x": 540, "y": 730, "r": 160})
    assert layer == GongLayer(540, 730, 160)
    assert LAYER_DRAWERS[GongLayer] is draw_gong


def test_gong_frame_bounds(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_gong(base.copy(), GongLayer(540, 800, 100), ctx, 1)
    ys, xs = _changed(base, after)
    # beam curls reach x = +-187 and y = -260; feet reach y = +224 (gong units = px here)
    assert xs.min() >= 540 - 195 and xs.max() <= 540 + 200
    assert ys.min() >= 800 - 265 and ys.max() <= 800 + 228
    assert np.array_equal(after, draw_gong(flat_base(), GongLayer(540, 800, 100), ctx, 1))


# --- temple (backlog #3) ------------------------------------------------------------------


def test_temple_parses(tmp_script: ScriptFactory) -> None:
    layer = _layer(tmp_script, {"type": "temple", "x": 540, "y": 1100, "scale": 1.5})
    assert layer == TempleLayer(540, 1100, 1.5)
    assert LAYER_DRAWERS[TempleLayer] is draw_temple


def test_temple_stands_on_its_ground_line(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_temple(base.copy(), TempleLayer(540, 1100, 1.0), ctx, 1)
    ys, xs = _changed(base, after)
    assert ys.max() <= 1100 + 1  # nothing below the ground line
    # widest part is the bottom step (half width 215) plus its outline
    assert ys.min() >= 1100 - 280 and xs.min() >= 540 - 225 and xs.max() <= 540 + 225


def test_temple_incense_is_optional(ctx: Any, flat_base: Base) -> None:
    with_smoke = draw_temple(flat_base(), TempleLayer(540, 1100, 1.0), ctx, 1)
    without = draw_temple(flat_base(), TempleLayer(540, 1100, 1.0, incense=False), ctx, 1)
    assert not np.array_equal(with_smoke, without)
