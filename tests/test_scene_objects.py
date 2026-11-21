"""Scene layers without people from the visual backlog (docs/visual_backlog.md, spec 6.3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.config import (
    ArrowheadsLayer,
    BambooVillageLayer,
    BannersLayer,
    CitadelLayer,
    CrossbowLayer,
    DigSiteLayer,
    DrumLayer,
    ElephantLayer,
    ExcavationLayer,
    FallenFlagsLayer,
    FurnaceLayer,
    GongLayer,
    HorseLayer,
    LanternItem,
    LanternsLayer,
    LonePathLayer,
    MapLayer,
    MouldLayer,
    PlinthLayer,
    RegaliaLayer,
    SailBoatLayer,
    ScrollLayer,
    StiltHouseLayer,
    TabletLayer,
    TempleLayer,
    TurtleLayer,
    load_script,
)
from history_shorts.errors import ValidationFailed
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.arrowheads import draw_arrowheads
from history_shorts.scene.bamboo_village import draw_bamboo_village
from history_shorts.scene.banners import draw_banners
from history_shorts.scene.citadel import draw_citadel
from history_shorts.scene.crossbow import draw_crossbow
from history_shorts.scene.delta_map import _in_sea, draw_map, scatter_points
from history_shorts.scene.dig_site import draw_dig_site
from history_shorts.scene.drum import draw_drum
from history_shorts.scene.elephant import draw_elephant
from history_shorts.scene.excavation import draw_excavation
from history_shorts.scene.fallen_flags import draw_fallen_flags
from history_shorts.scene.furnace import draw_furnace
from history_shorts.scene.gong import draw_gong
from history_shorts.scene.horse import draw_horse
from history_shorts.scene.lanterns import draw_lanterns
from history_shorts.scene.lone_path import draw_lone_path
from history_shorts.scene.mould import draw_mould
from history_shorts.scene.plinth import draw_plinth
from history_shorts.scene.regalia import draw_regalia
from history_shorts.scene.sail_boat import draw_sail_boat
from history_shorts.scene.scroll import draw_scroll
from history_shorts.scene.stilt_house import draw_stilt_house
from history_shorts.scene.tablet import draw_tablet
from history_shorts.scene.temple import draw_temple
from history_shorts.scene.turtle import draw_turtle

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


# --- bamboo village (backlog #18) ---------------------------------------------------------


def test_bamboo_village_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "bamboo_village", "x": 540, "y": 1095, "scale": 1.7}
    assert _layer(tmp_script, raw) == BambooVillageLayer(540, 1095, 1.7)
    assert LAYER_DRAWERS[BambooVillageLayer] is draw_bamboo_village


def test_bamboo_village_bounds_and_determinism(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    layer = BambooVillageLayer(540, 1100, 1.0)
    after = draw_bamboo_village(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    # hedge stalks up to 240 tall leaning 24, leaves fanning 30 more; banyan crown reaches -228
    assert ys.max() <= 1100 + 2 and ys.min() >= 1100 - 262
    assert xs.min() >= 540 - 330 and xs.max() <= 540 + 330
    assert np.array_equal(after, draw_bamboo_village(flat_base(), layer, ctx, 1))


# --- furnace and plinth (Trống đồng video) ------------------------------------------------


def test_furnace_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "furnace", "x": 540, "y": 1095, "scale": 1.4}
    assert _layer(tmp_script, raw) == FurnaceLayer(540, 1095, 1.4)
    assert LAYER_DRAWERS[FurnaceLayer] is draw_furnace


def test_furnace_bounds_and_determinism(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    layer = FurnaceLayer(540, 1100, 1.0)
    after = draw_furnace(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    # the halo (radius 300 about y -150) is the widest part; flames reach -400
    assert ys.min() >= 1100 - 452 and ys.max() <= 1100 + 152
    assert xs.min() >= 540 - 302 and xs.max() <= 540 + 302
    # the mouth glows: hotter (more red) than the kiln wall beside it
    assert after[1090, 540, 0] > after[1090, 540 + 110, 0]
    assert np.array_equal(after, draw_furnace(flat_base(), layer, ctx, 1))


def test_plinth_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "plinth", "x": 540, "y": 1095, "scale": 1.6}
    assert _layer(tmp_script, raw) == PlinthLayer(540, 1095, 1.6)
    assert LAYER_DRAWERS[PlinthLayer] is draw_plinth


def test_plinth_bounds_beam_fades_and_determinism(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    layer = PlinthLayer(540, 1100, 1.0)
    after = draw_plinth(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    assert ys.min() >= 1100 - 540 and ys.max() <= 1100 + 2
    assert xs.min() >= 540 - 152 and xs.max() <= 540 + 152
    # the beam fades out upwards: barely changed near its top, clearly lit near the plinth
    near_top = np.abs(after[1100 - 525, 540] - base[1100 - 525, 540]).max()
    near_cap = np.abs(after[1100 - 200, 540] - base[1100 - 200, 540]).max()
    assert near_top < 0.02 < near_cap
    assert np.array_equal(after, draw_plinth(flat_base(), layer, ctx, 1))


# --- arrowheads and mould (Cổ Loa video) --------------------------------------------------


def test_arrowheads_parse_with_default_arrangement(tmp_script: ScriptFactory) -> None:
    raw = {"type": "arrowheads", "x": 540, "y": 1080, "scale": 2.0}
    assert _layer(tmp_script, raw) == ArrowheadsLayer(540, 1080, 2.0, "single")
    raw["arrangement"] = "heap"
    assert _layer(tmp_script, raw) == ArrowheadsLayer(540, 1080, 2.0, "heap")
    assert LAYER_DRAWERS[ArrowheadsLayer] is draw_arrowheads


def test_arrowheads_reject_unknown_arrangement(tmp_script: ScriptFactory) -> None:
    raw = {"type": "arrowheads", "x": 540, "y": 1080, "scale": 2.0, "arrangement": "rain"}
    with pytest.raises(ValidationFailed):
        _layer(tmp_script, raw)


# (arrangement, half width, height above the floor, depth below it) at scale 1: the light
# pool (r 240 about -170) bounds `single`; tips reach 0.46 * 135 units round each heap item
ARROWHEAD_BOUNDS = [
    ("single", 242, 412, 72),
    ("pair", 132, 288, 2),
    ("quarter", 242, 260, 2),
    ("heap", 292, 235, 64),
]


@pytest.mark.parametrize(("arrangement", "half", "up", "down"), ARROWHEAD_BOUNDS)
def test_arrowheads_bounds_and_determinism(
    ctx: Any, flat_base: Base, arrangement: str, half: int, up: int, down: int
) -> None:
    base = flat_base()
    layer = ArrowheadsLayer(540, 1100, 1.0, arrangement)  # type: ignore[arg-type]
    after = draw_arrowheads(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    assert ys.size > 0
    assert ys.min() >= 1100 - up and ys.max() <= 1100 + down
    assert xs.min() >= 540 - half and xs.max() <= 540 + half
    assert np.array_equal(after, draw_arrowheads(flat_base(), layer, ctx, 1))


def test_polished_arrowhead_is_brighter_than_raw(ctx: Any, flat_base: Base) -> None:
    after = draw_arrowheads(flat_base(), ArrowheadsLayer(540, 1100, 1.0, "pair"), ctx, 1)
    # sample both blades just under their shoulders, left polished, right raw
    left = after[1100 - 14 - 140, 540 - 80 - 20].sum()
    right = after[1100 - 14 - 140, 540 + 80 - 20].sum()
    assert left > right


def test_mould_parses(tmp_script: ScriptFactory) -> None:
    raw = {"type": "mould", "x": 540, "y": 1095, "scale": 1.25}
    assert _layer(tmp_script, raw) == MouldLayer(540, 1095, 1.25)
    assert LAYER_DRAWERS[MouldLayer] is draw_mould


def test_mould_bounds_cavity_and_determinism(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    layer = MouldLayer(540, 1100, 1.0)
    after = draw_mould(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    # the key (radius 82 + spread 10 + ring 14) is the top; the shadow spans 250 each side
    assert ys.min() >= 1100 - 455 - 107 and ys.max() <= 1100 + 14
    assert xs.min() >= 540 - 252 and xs.max() <= 540 + 252
    # the cavity in the middle piece is darker than the stone beside it
    assert after[1100 - 250, 540].sum() < after[1100 - 250, 540 + 45].sum()
    assert np.array_equal(after, draw_mould(flat_base(), layer, ctx, 1))


def test_mould_without_key_draws_nothing_above_the_pieces(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_mould(base.copy(), MouldLayer(540, 1100, 1.0, key=False), ctx, 1)
    ys, _ = _changed(base, after)
    assert ys.min() >= 1100 - 332  # the pieces are 330 tall
    assert MouldLayer(540, 1100, 1.0).key is True


def test_plinth_without_hooves(ctx: Any, flat_base: Base, tmp_script: ScriptFactory) -> None:
    raw = {"type": "plinth", "x": 540, "y": 1095, "scale": 1.6, "hooves": False}
    assert _layer(tmp_script, raw) == PlinthLayer(540, 1095, 1.6, hooves=False)
    with_marks = draw_plinth(flat_base(), PlinthLayer(540, 1100, 1.0), ctx, 1)
    bare = draw_plinth(flat_base(), PlinthLayer(540, 1100, 1.0, hooves=False), ctx, 1)
    # a hoof mark sits at x -62, y -177 on the top face
    assert bare[1100 - 177, 540 - 62].sum() > with_marks[1100 - 177, 540 - 62].sum()


# --- dig site, crossbow, turtle, excavation (Cổ Loa video) --------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"type": "dig_site", "mode": "hoard"}, DigSiteLayer(540, 700, 1.0, "hoard")),
        ({"type": "dig_site"}, DigSiteLayer(540, 700, 1.0, "buried")),
        ({"type": "crossbow", "mode": "rack"}, CrossbowLayer(540, 700, 1.0, "rack")),
        ({"type": "crossbow"}, CrossbowLayer(540, 700, 1.0, "claw")),
        ({"type": "turtle", "facing": -1, "claw": False}, TurtleLayer(540, 700, 1.0, -1, False)),
        ({"type": "turtle"}, TurtleLayer(540, 700, 1.0, 1, True)),
        ({"type": "excavation", "mode": "trench"}, ExcavationLayer(540, 700, 1.0, "trench")),
        ({"type": "excavation"}, ExcavationLayer(540, 700, 1.0, "site")),
    ],
)
def test_co_loa_layers_parse(tmp_script: ScriptFactory, raw: dict[str, Any], expected: Any) -> None:
    assert _layer(tmp_script, {"x": 540, "y": 700, "scale": 1.0, **raw}) == expected
    assert type(expected) in LAYER_DRAWERS


@pytest.mark.parametrize("layer_type", ["dig_site", "crossbow", "excavation"])
def test_co_loa_layers_reject_unknown_mode(tmp_script: ScriptFactory, layer_type: str) -> None:
    with pytest.raises(ValidationFailed):
        _layer(tmp_script, {"type": layer_type, "x": 540, "y": 700, "scale": 1.0, "mode": "x"})


# (layer, up, down, left, right) at scale 1: the soil section is 860 x 460 under the surface
# line; pit tools reach 212 above it; a crossbow is 330 long, its volley reaches ~670.
COLOA_BOUNDS = [
    (DigSiteLayer(540, 700, 1.0, "buried"), 4, 461, 434, 434),
    (DigSiteLayer(540, 700, 1.0, "pit"), 214, 461, 434, 434),
    (DigSiteLayer(540, 700, 1.0, "hoard"), 214, 461, 434, 434),
    (DigSiteLayer(540, 700, 1.0, "covered"), 14, 461, 434, 434),
    (CrossbowLayer(540, 1100, 1.0, "claw"), 333, 2, 173, 173),
    (CrossbowLayer(540, 1100, 1.0, "volley"), 673, 11, 30, 516),
    (CrossbowLayer(540, 1100, 1.0, "rack"), 571, 2, 369, 369),
    (CrossbowLayer(540, 1100, 1.0, "missing"), 333, 2, 173, 173),
    (TurtleLayer(540, 1100, 1.0, 1, True), 372, 44, 263, 268),
    (TurtleLayer(540, 1100, 1.0, -1, False), 195, 44, 269, 262),
    (ExcavationLayer(540, 1100, 1.0, "site"), 273, 3, 483, 481),
    (ExcavationLayer(540, 700, 1.0, "trench"), 4, 461, 434, 434),
]
_DRAW = {
    DigSiteLayer: draw_dig_site,
    CrossbowLayer: draw_crossbow,
    TurtleLayer: draw_turtle,
    ExcavationLayer: draw_excavation,
}


@pytest.mark.parametrize(("layer", "up", "down", "left", "right"), COLOA_BOUNDS)
def test_co_loa_layers_bounds_and_determinism(
    ctx: Any, flat_base: Base, layer: Any, up: int, down: int, left: int, right: int
) -> None:
    draw = _DRAW[type(layer)]
    base = flat_base()
    after = draw(base.copy(), layer, ctx, 1)
    ys, xs = _changed(base, after)
    assert ys.size > 0
    assert ys.min() >= layer.y - up and ys.max() <= layer.y + down
    assert xs.min() >= layer.x - left and xs.max() <= layer.x + right
    assert np.array_equal(after, draw(flat_base(), layer, ctx, 1))


def test_dig_site_pit_is_dark_and_the_hoard_fills_it(ctx: Any, flat_base: Base) -> None:
    pit = draw_dig_site(flat_base(), DigSiteLayer(540, 700, 1.0, "pit"), ctx, 1)
    hoard = draw_dig_site(flat_base(), DigSiteLayer(540, 700, 1.0, "hoard"), ctx, 1)
    # pit spans x -40..140, depth 216; the soil at x -300 is untouched by it
    inside = (slice(700 + 60, 700 + 200), slice(540 - 30, 540 + 130))
    assert pit[inside].mean() < pit[700 + 30, 540 - 300].mean()
    assert hoard[inside].mean() > pit[inside].mean()


def test_crossbow_claw_glows_and_missing_leaves_an_empty_slot(ctx: Any, flat_base: Base) -> None:
    claw = draw_crossbow(flat_base(), CrossbowLayer(540, 1100, 1.0, "claw"), ctx, 1)
    gone = draw_crossbow(flat_base(), CrossbowLayer(540, 1100, 1.0, "missing"), ctx, 1)
    trigger = (1100 - 110 + 12, 540)  # inside the trigger, 12 units below its top
    assert claw[trigger].sum() > gone[trigger].sum()


def test_turtle_faces_its_head_and_claw_is_optional(ctx: Any, flat_base: Base) -> None:
    right = draw_turtle(flat_base(), TurtleLayer(540, 1100, 1.0, 1, True), ctx, 1)
    left = draw_turtle(flat_base(), TurtleLayer(540, 1100, 1.0, -1, True), ctx, 1)
    head = (1100 - 168, 540 + 232)
    mirrored = (1100 - 168, 540 - 232)
    assert right[head].sum() > right[mirrored].sum()
    assert left[mirrored].sum() > left[head].sum()


def test_excavation_trench_has_a_dark_ash_band(ctx: Any, flat_base: Base) -> None:
    after = draw_excavation(flat_base(), ExcavationLayer(540, 700, 1.0, "trench"), ctx, 1)
    ash = after[700 + 212 : 700 + 250, 540 + 350 : 540 + 420].mean()
    above = after[700 + 120 : 700 + 170, 540 + 350 : 540 + 420].mean()
    assert ash < above
