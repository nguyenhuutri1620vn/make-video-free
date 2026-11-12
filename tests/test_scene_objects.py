"""Scene layers without people from the visual backlog (docs/visual_backlog.md, spec 6.3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.config import (
    BannersLayer,
    CitadelLayer,
    DrumLayer,
    ElephantLayer,
    FallenFlagsLayer,
    GongLayer,
    HorseLayer,
    LanternItem,
    LanternsLayer,
    LonePathLayer,
    MapLayer,
    RegaliaLayer,
    SailBoatLayer,
    ScrollLayer,
    StiltHouseLayer,
    TabletLayer,
    TempleLayer,
    load_script,
)
from history_shorts.errors import ValidationFailed
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.banners import draw_banners
from history_shorts.scene.citadel import draw_citadel
from history_shorts.scene.delta_map import _in_sea, draw_map, scatter_points
from history_shorts.scene.drum import draw_drum
from history_shorts.scene.elephant import draw_elephant
from history_shorts.scene.fallen_flags import draw_fallen_flags
from history_shorts.scene.gong import draw_gong
from history_shorts.scene.horse import draw_horse
from history_shorts.scene.lanterns import draw_lanterns
from history_shorts.scene.lone_path import draw_lone_path
from history_shorts.scene.regalia import draw_regalia
from history_shorts.scene.sail_boat import draw_sail_boat
from history_shorts.scene.scroll import draw_scroll
from history_shorts.scene.stilt_house import draw_stilt_house
from history_shorts.scene.tablet import draw_tablet
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


# --- banners (backlog #8) -----------------------------------------------------------------


def test_banners_parse(tmp_script: ScriptFactory) -> None:
    assert _layer(tmp_script, {"type": "banners", "y": 1080}) == BannersLayer(1080)
    assert LAYER_DRAWERS[BannersLayer] is draw_banners
    with pytest.raises(ValidationFailed):
        _layer(tmp_script, {"type": "banners", "y": 1080, "rows": 9})


def test_banners_rows_stack_upwards(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    one = draw_banners(base.copy(), BannersLayer(1080, 1), ctx, 1)
    four = draw_banners(base.copy(), BannersLayer(1080, 4), ctx, 1)
    top_one, top_four = _changed(base, one)[0].min(), _changed(base, four)[0].min()
    assert top_four < top_one  # back rows sit higher
    assert _changed(base, four)[0].max() <= 1080 + 90 + 1  # hill depth below the baseline
    assert np.array_equal(four, draw_banners(flat_base(), BannersLayer(1080, 4), ctx, 1))


# --- regalia (backlog #9) -----------------------------------------------------------------


def test_regalia_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "regalia", "x": 540, "y": 1095, "scale": 2, "screen": False}
    assert _layer(tmp_script, raw) == RegaliaLayer(540, 1095, 2, False)
    assert LAYER_DRAWERS[RegaliaLayer] is draw_regalia


def test_regalia_screen_is_optional_and_bounded(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    full = draw_regalia(base.copy(), RegaliaLayer(540, 1100, 1.0), ctx, 1)
    bare = draw_regalia(base.copy(), RegaliaLayer(540, 1100, 1.0, False), ctx, 1)
    ys, xs = _changed(base, full)
    # table legs are 8-unit strokes whose ends sit on the floor; screen top at -306
    assert ys.max() <= 1100 + 4 and ys.min() >= 1100 - 308
    assert xs.min() >= 540 - 160 and xs.max() <= 540 + 160  # 4 panels of 78
    assert _changed(base, bare)[0].min() > 1100 - 160  # without the screen only the table set


# --- fallen flags (backlog #10) -----------------------------------------------------------


def test_fallen_flags_parse(tmp_script: ScriptFactory) -> None:
    raw = {"type": "fallen_flags", "x": 560, "y": 1095, "scale": 2}
    assert _layer(tmp_script, raw) == FallenFlagsLayer(560, 1095, 2)
    assert LAYER_DRAWERS[FallenFlagsLayer] is draw_fallen_flags


def test_fallen_flags_lie_low(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_fallen_flags(base.copy(), FallenFlagsLayer(540, 1100, 1.0), ctx, 1)
    ys, xs = _changed(base, after)
    # tent poles reach -84 and its right foot +234; the leaning flag pole -150; spears from -205
    assert ys.max() <= 1100 + 16 and ys.min() >= 1100 - 160
    assert xs.min() >= 540 - 210 and xs.max() <= 540 + 240
    assert np.array_equal(
        after, draw_fallen_flags(flat_base(), FallenFlagsLayer(540, 1100, 1.0), ctx, 1)
    )


# --- sail boat (backlog #11) --------------------------------------------------------------


def test_sail_boat_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "sail_boat", "x": 540, "y": 1060, "scale": 1.5, "facing": -1}
    assert _layer(tmp_script, raw) == SailBoatLayer(540, 1060, 1.5, -1)
    assert LAYER_DRAWERS[SailBoatLayer] is draw_sail_boat


def test_sail_boat_bounds_and_mirror(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    right = draw_sail_boat(base.copy(), SailBoatLayer(540, 1100, 1.0), ctx, 1)
    ys, xs = _changed(base, right)
    # mast top at -330, waves reach +18; bow tip at +176 and stern waves at -206
    assert ys.min() >= 1100 - 335 and ys.max() <= 1100 + 22
    assert xs.min() >= 540 - 210 and xs.max() <= 540 + 182
    left = draw_sail_boat(base.copy(), SailBoatLayer(540, 1100, 1.0, -1), ctx, 1)
    lxs = _changed(base, left)[1]
    assert lxs.max() <= 540 + 210 and lxs.min() >= 540 - 182  # mirrored about x = 540


# --- lone path (backlog #12) --------------------------------------------------------------


def test_lone_path_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "lone_path", "y": 1145, "depth": 340, "mist": False}
    assert _layer(tmp_script, raw) == LonePathLayer(1145, 340, False)
    assert LAYER_DRAWERS[LonePathLayer] is draw_lone_path


def test_lone_path_narrows_into_the_distance(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_lone_path(base.copy(), LonePathLayer(1140, 340, False), ctx, 1)
    changed = np.any(after != base, axis=-1)
    near = np.count_nonzero(changed[1130])
    far = np.count_nonzero(changed[1140 - 300])
    assert near > 250 and far < near / 3
    assert np.nonzero(changed)[0].max() <= 1140 + 2
    misty = draw_lone_path(base.copy(), LonePathLayer(1140, 340), ctx, 1)
    assert not np.array_equal(after, misty)


# --- lanterns (backlog #13) ---------------------------------------------------------------


def test_lanterns_parse(tmp_script: ScriptFactory) -> None:
    raw = {"type": "lanterns", "items": [{"x": 300, "y": 1000, "scale": 1.5}]}
    assert _layer(tmp_script, raw) == LanternsLayer((LanternItem(300, 1000, 1.5),))
    assert LAYER_DRAWERS[LanternsLayer] is draw_lanterns


def test_lanterns_float_and_reflect(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_lanterns(base.copy(), LanternsLayer((LanternItem(540, 1000, 1.0),)), ctx, 1)
    ys, xs = _changed(base, after)
    # glow reaches 60 above the waterline, the reflection 50 below it
    assert ys.min() >= 1000 - 62 and ys.max() <= 1000 + 52
    assert xs.min() >= 540 - 32 and xs.max() <= 540 + 32
    assert ys.max() > 1000 + 20  # the reflection is there


# --- tablet (backlog #14) -----------------------------------------------------------------


def test_tablet_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "tablet", "x": 540, "y": 1095, "scale": 1.75}
    assert _layer(tmp_script, raw) == TabletLayer(540, 1095, 1.75)
    assert LAYER_DRAWERS[TabletLayer] is draw_tablet


def test_tablet_stands_on_the_floor(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_tablet(base.copy(), TabletLayer(540, 1100, 1.0), ctx, 1)
    ys, xs = _changed(base, after)
    # crown at -348, smoke curls to about -286; altar top is 280 wide
    assert ys.max() <= 1100 + 2 and ys.min() >= 1100 - 352
    assert xs.min() >= 540 - 142 and xs.max() <= 540 + 142
    assert np.array_equal(after, draw_tablet(flat_base(), TabletLayer(540, 1100, 1.0), ctx, 1))


# --- horse (backlog #15) ------------------------------------------------------------------


def test_horse_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "horse", "x": 690, "y": 1095, "scale": 1.75, "facing": -1}
    assert _layer(tmp_script, raw) == HorseLayer(690, 1095, 1.75, -1)
    assert LAYER_DRAWERS[HorseLayer] is draw_horse


def test_horse_stands_on_its_plinth(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_horse(base.copy(), HorseLayer(540, 1100, 1.0), ctx, 1)
    ys, xs = _changed(base, after)
    # ear tip at -258, plinth cap 260 wide; the muzzle reaches +134
    assert ys.max() <= 1100 + 2 and ys.min() >= 1100 - 262
    assert xs.min() >= 540 - 132 and xs.max() <= 540 + 138
    mirrored = draw_horse(base.copy(), HorseLayer(540, 1100, 1.0, -1), ctx, 1)
    assert _changed(base, mirrored)[1].min() < xs.min()  # the muzzle now passes the left edge


# --- citadel (backlog #17) ----------------------------------------------------------------


def test_citadel_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "citadel", "x": 540, "y": 860, "scale": 1.3}
    assert _layer(tmp_script, raw) == CitadelLayer(540, 860, 1.3)
    assert LAYER_DRAWERS[CitadelLayer] is draw_citadel


def test_citadel_fits_its_moat(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_citadel(base.copy(), CitadelLayer(540, 900, 1.0), ctx, 1)
    ys, xs = _changed(base, after)
    # moat 340 x 129; the outer wall face hangs 20 below its 114 ring, so 134 below the centre
    assert xs.min() >= 540 - 342 and xs.max() <= 540 + 342
    assert ys.min() >= 900 - 131 and ys.max() <= 900 + 136
    assert np.array_equal(after, draw_citadel(flat_base(), CitadelLayer(540, 900, 1.0), ctx, 1))
