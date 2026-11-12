"""Scene layers without people from the visual backlog (docs/visual_backlog.md, spec 6.3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.config import (
    DrumLayer,
    ElephantLayer,
    GongLayer,
    MapLayer,
    ScrollLayer,
    StiltHouseLayer,
    TempleLayer,
    load_script,
)
from history_shorts.errors import ValidationFailed
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.delta_map import _in_sea, draw_map, scatter_points
from history_shorts.scene.drum import draw_drum
from history_shorts.scene.elephant import draw_elephant
from history_shorts.scene.gong import draw_gong
from history_shorts.scene.scroll import draw_scroll
from history_shorts.scene.stilt_house import draw_stilt_house
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


# --- map (backlog #4) ---------------------------------------------------------------------


def test_map_parses_dots_scatter_and_arrow(tmp_script: ScriptFactory) -> None:
    raw = {"type": "map", "x": 100, "y": 300, "w": 800, "h": 700}
    layer = _layer(tmp_script, {**raw, "dots": [[0.3, 0.4]], "scatter": 10, "arrow": True})
    assert layer == MapLayer(100, 300, 800, 700, ((0.3, 0.4),), 10, True)
    assert LAYER_DRAWERS[MapLayer] is draw_map


@pytest.mark.parametrize("dot", [[1.2, 0.5], [0.5], "x"])
def test_map_rejects_bad_dots(tmp_script: ScriptFactory, dot: Any) -> None:
    raw = {"type": "map", "x": 100, "y": 300, "w": 800, "h": 700, "dots": [dot]}
    with pytest.raises(ValidationFailed):
        _layer(tmp_script, raw)


def test_scatter_points_are_on_land_spaced_and_deterministic() -> None:
    a = scatter_points(np.random.default_rng(7), 65, ((0.34, 0.36),))
    assert a == scatter_points(np.random.default_rng(7), 65, ((0.34, 0.36),))
    assert len(a) >= 50
    assert not any(_in_sea(u, v) for u, v in a)
    assert all((u - 0.34) ** 2 + (v - 0.36) ** 2 >= 0.05**2 for u, v in a)


def test_map_stays_inside_its_box(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    layer = MapLayer(200, 400, 600, 500, ((0.5, 0.5),), 20, True)
    ys, xs = _changed(base, draw_map(base.copy(), layer, ctx, 1))
    assert xs.min() >= 200 - 2 and xs.max() <= 800 + 2
    assert ys.min() >= 400 - 2 and ys.max() <= 900 + 2


# --- scroll (backlog #5) ------------------------------------------------------------------


def test_scroll_parses(tmp_script: ScriptFactory) -> None:
    layer = _layer(tmp_script, {"type": "scroll", "x": 520, "y": 760, "scale": 2})
    assert layer == ScrollLayer(520, 760, 2)
    assert LAYER_DRAWERS[ScrollLayer] is draw_scroll


def test_scroll_bounds_and_determinism(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    layer = ScrollLayer(540, 800, 1.0)
    after = draw_scroll(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    # rod knobs at x -191, roll at x 184, brush handle to x 236 and y 172
    assert xs.min() >= 540 - 195 and xs.max() <= 540 + 240
    assert ys.min() >= 800 - 140 and ys.max() <= 800 + 176
    assert np.array_equal(after, draw_scroll(flat_base(), layer, ctx, 1))
    assert not np.array_equal(after, draw_scroll(flat_base(), layer, ctx, 2))  # ink marks vary


# --- elephant (backlog #6) ----------------------------------------------------------------


def test_elephant_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "elephant", "x": 520, "y": 1100, "scale": 2, "facing": -1, "flag": False}
    assert _layer(tmp_script, raw) == ElephantLayer(520, 1100, 2, -1, False)
    assert LAYER_DRAWERS[ElephantLayer] is draw_elephant


def test_elephant_stands_on_the_ground(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    ys, xs = _changed(base, draw_elephant(base.copy(), ElephantLayer(540, 1100, 1.0), ctx, 1))
    assert ys.max() <= 1100 + 2 and ys.min() >= 1100 - 310  # flag top at -304
    assert xs.min() >= 540 - 145 and xs.max() <= 540 + 160  # tail tuft, trunk tip


def test_elephant_mirrors_by_scale(ctx: Any, flat_base: Base) -> None:
    right = draw_elephant(flat_base(), ElephantLayer(540, 1100, 1.0, 1), ctx, 1)
    left = draw_elephant(flat_base(), ElephantLayer(540, 1100, 1.0, -1), ctx, 1)
    changed_r = np.any(right != flat_base(), axis=-1)
    changed_l = np.any(left != flat_base(), axis=-1)
    # mirrored about x = 540: column c on the right is column 1080 - c on the left (+-1 px)
    assert abs(int(changed_r.sum()) - int(changed_l.sum())) < changed_r.sum() * 0.02


# --- stilt house (backlog #7) -------------------------------------------------------------


def test_stilt_house_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "stilt_house", "x": 560, "y": 1095, "scale": 1.5, "bamboo": False}
    assert _layer(tmp_script, raw) == StiltHouseLayer(560, 1095, 1.5, False)
    assert LAYER_DRAWERS[StiltHouseLayer] is draw_stilt_house


def test_stilt_house_bounds_and_bamboo(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    house = draw_stilt_house(base.copy(), StiltHouseLayer(600, 1100, 1.0, False), ctx, 1)
    ys, xs = _changed(base, house)
    assert ys.max() <= 1100 + 2 and ys.min() >= 1100 - 275  # ridge tips at -270
    assert xs.min() >= 600 - 155 and xs.max() <= 600 + 155  # eaves at +-150
    with_bamboo = draw_stilt_house(base.copy(), StiltHouseLayer(600, 1100, 1.0), ctx, 1)
    ys, xs = _changed(base, with_bamboo)
    assert xs.min() < 600 - 200 and ys.min() >= 1100 - 380  # bamboo to the left, up to -360
