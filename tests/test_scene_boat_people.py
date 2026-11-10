"""Boat with crew, lotus and the characters layer (FR-46, FR-48, spec 6.3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.characters import resolve_style
from history_shorts.characters.figure import draw_figure
from history_shorts.characters.formations import place
from history_shorts.checks import check_all
from history_shorts.compose import over
from history_shorts.config import (
    BoatLayer,
    CharactersLayer,
    CharacterSpec,
    LotusLayer,
    load_script,
)
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.boat import BOAT_CREW_SLOTS, crew_placements, draw_boat
from history_shorts.scene.lotus import draw_lotus
from history_shorts.scene.people import (
    DEFAULT_CHARACTER_HEIGHT,
    draw_characters,
    placed_characters,
)

Base = Callable[[], FloatImage]
ScriptFactory = Callable[..., Path]
BOAT = BoatLayer(290, 1056, 1.5, (CharacterSpec("leader"), CharacterSpec("boat_crew")))


def _summary(layer: BoatLayer) -> list[tuple[float, float, float, int]]:
    return [
        (p.placement.x, p.placement.baseline, p.placement.height, p.placement.facing)
        for p in crew_placements(layer)
    ]


# --------------------------------------------------------------------------------------
# Boat crew placement
# --------------------------------------------------------------------------------------


def test_crew_default_slots() -> None:
    (x0, b0, h0, f0), (x1, b1, h1, f1) = _summary(BOAT)
    assert (x0, b0, h0) == pytest.approx((300.05, 1048.05, 150))
    assert (x1, b1, h1) == pytest.approx((249.95, 1050.0, 120))
    assert (f0, f1) == (1, 1)  # facing defaults to +1
    assert len(BOAT_CREW_SLOTS) == 2


def test_explicit_crew_values_beat_slots() -> None:
    crew = (
        CharacterSpec("leader", x=300, baseline=1048, height=150, facing=1),
        CharacterSpec("boat_crew", x=250, baseline=1050, height=120, facing=-1),
    )
    layer = BoatLayer(290, 1056, 1.5, crew)
    assert _summary(layer) == [(300, 1048, 150, 1), (250, 1050, 120, -1)]
    mixed = BoatLayer(290, 1056, 1.5, (CharacterSpec("leader", height=90),))
    x, b, h, f = _summary(mixed)[0]
    assert (x, b, h, f) == pytest.approx((300.05, 1048.05, 90, 1))


def test_crew_keeps_spec_order_and_specs() -> None:
    placed = crew_placements(BOAT)
    assert [p.spec for p in placed] == list(BOAT.crew)


def test_too_many_crew_raises() -> None:
    layer = BoatLayer(290, 1056, 1.0, (CharacterSpec("leader"),) * 3)
    with pytest.raises(ValueError, match="boat supports at most 2 crew"):
        crew_placements(layer)


# --------------------------------------------------------------------------------------
# Boat drawing
# --------------------------------------------------------------------------------------


def test_hull_drawn_over_crew_feet(ctx: Any, palette: Any, flat_base: Base) -> None:
    # Feet stand 8 px inside the hull (hull top edge is ~4.5 px below the boat origin at
    # the centre), so the hull must cover the lower robe.
    crew = (CharacterSpec("general", x=290, baseline=1064, height=150, facing=1, prop="none"),)
    with_crew = draw_boat(flat_base(), BoatLayer(290, 1056, 1.5, crew), ctx, 1)
    hull_only = draw_boat(flat_base(), BoatLayer(290, 1056, 1.5, ()), ctx, 1)
    figure = Canvas(1080, 1920)
    placed = crew_placements(BoatLayer(290, 1056, 1.5, crew))[0]
    draw_figure(figure, resolve_style(placed.spec, palette), placed.placement, palette)
    alpha = figure.mask()
    foot_y, foot_x = 1062, 290  # inside the hull and on the robe's lower edge
    assert alpha[foot_y, foot_x] > 0.9  # the figure alone paints this pixel
    assert np.allclose(with_crew[foot_y, foot_x], hull_only[foot_y, foot_x])
    assert not np.allclose(hull_only[foot_y, foot_x], flat_base()[foot_y, foot_x])
    # higher up, above the hull, the crew shows
    torso_y = 1064 - 70
    assert not np.allclose(with_crew[torso_y, foot_x], hull_only[torso_y, foot_x])


def test_boat_without_crew_draws_hull_with_theme_colours(
    ctx: Any, palette: Any, flat_base: Base
) -> None:
    base = flat_base()
    after = draw_boat(base.copy(), BoatLayer(500, 1000, 1.0, ()), ctx, 1)
    changed = np.any(after != base, axis=-1)
    ys, xs = np.nonzero(changed)
    # hull spans x -70..74, y -14..16 around the origin, plus stroke slack
    assert xs.min() >= 500 - 70 - 3 and xs.max() <= 500 + 74 + 3
    assert ys.min() >= 1000 - 14 - 3 and ys.max() <= 1000 + 16 + 3
    gold_lt = np.array(palette["gold_lt"], dtype=np.float32) / 255
    assert np.allclose(after[1000 - 6, 500 + 62], gold_lt, atol=0.1)  # the gold_lt dot


def test_boat_is_deterministic(ctx: Any, flat_base: Base) -> None:
    a = draw_boat(flat_base(), BOAT, ctx, 1)
    b = draw_boat(flat_base(), BOAT, ctx, 1)
    assert np.array_equal(a, b)


# --------------------------------------------------------------------------------------
# Lotus
# --------------------------------------------------------------------------------------


def test_lotus_renders_within_bbox(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_lotus(base.copy(), LotusLayer(540, 1000, 2.0), ctx, 1)
    changed = np.any(after != base, axis=-1)
    ys, xs = np.nonzero(changed)
    assert xs.size > 2000
    # leaf is 46 wide, petals reach 48 up; the 62 degree petals stay inside the leaf width
    assert xs.min() >= 540 - 2 * 50 and xs.max() <= 540 + 2 * 50
    assert ys.min() >= 1000 - 2 * 52 and ys.max() <= 1000 + 2 * 19


def test_lotus_is_deterministic_and_scales(ctx: Any, flat_base: Base) -> None:
    layer = LotusLayer(540, 1000, 2.0)
    a = draw_lotus(flat_base(), layer, ctx, 1)
    assert np.array_equal(a, draw_lotus(flat_base(), layer, ctx, 1))
    small = draw_lotus(flat_base(), LotusLayer(540, 1000, 1.0), ctx, 1)
    assert not np.array_equal(a, small)


# --------------------------------------------------------------------------------------
# Characters layer
# --------------------------------------------------------------------------------------

REF_ROLES = ("leader", "leader", "general_alt", "general_alt", "general", "general")


def test_characters_layer_uses_formation() -> None:
    items = tuple(CharacterSpec(r) for r in REF_ROLES)
    layer = CharactersLayer("centre_pair", 1100, items)
    assert placed_characters(layer) == place("centre_pair", items, 1100)


def test_explicit_items_default_height_baseline_and_facing() -> None:
    items = (
        CharacterSpec("general", x=200),
        CharacterSpec("general", x=800, baseline=900, height=300),
        CharacterSpec("general", x=300, facing=1),
    )
    placed = placed_characters(CharactersLayer(None, 1050, items))
    got = [
        (p.placement.x, p.placement.baseline, p.placement.height, p.placement.facing)
        for p in placed
    ]
    assert DEFAULT_CHARACTER_HEIGHT == 475
    assert got == [(200, 1050, 475, -1), (800, 900, 300, 1), (300, 1050, 475, 1)]


def test_explicit_items_without_x_raise() -> None:
    with pytest.raises(ValueError, match="needs x"):
        placed_characters(CharactersLayer(None, 1100, (CharacterSpec("general"),)))


def test_draw_characters_matches_manual_draw_order(ctx: Any, palette: Any, flat_base: Base) -> None:
    items = tuple(CharacterSpec(r) for r in REF_ROLES)
    layer = CharactersLayer("centre_pair", 1100, items)
    cv = Canvas(1080, 1920)
    for p in place("centre_pair", items, 1100):
        draw_figure(cv, resolve_style(p.spec, palette), p.placement, palette)
    expected = over(flat_base(), cv)
    assert np.array_equal(draw_characters(flat_base(), layer, ctx, 1), expected)


def test_draw_characters_places_pixels_inside_the_figure(ctx: Any, flat_base: Base) -> None:
    layer = CharactersLayer(None, 1100, (CharacterSpec("general", x=540, prop="none"),))
    base = flat_base()
    after = draw_characters(base.copy(), layer, ctx, 1)
    ys, xs = np.nonzero(np.any(after != base, axis=-1))
    assert ys.max() <= 1100 + 4  # feet at the baseline
    assert 1100 - 1.1 * 475 <= ys.min() < 1100 - 0.95 * 475  # head near the default height
    assert abs(float(xs.mean()) - 540) < 60


# --------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("layer_type", [BoatLayer, LotusLayer, CharactersLayer])
def test_drawers_registered(layer_type: type) -> None:
    assert layer_type in LAYER_DRAWERS


# --------------------------------------------------------------------------------------
# Checks use the same placement (FR-48)
# --------------------------------------------------------------------------------------


def _load(tmp_script: ScriptFactory, layers: list[dict[str, Any]]) -> Any:
    slide = {"title": "Hai Bà Trưng", "scene": {"layers": layers}}
    return load_script(tmp_script(slides=[slide]))[0]


def test_boat_crew_flag_on_seal_reported(tmp_script: ScriptFactory, theme: Any) -> None:
    crew = [{"role": "leader", "x": 100, "baseline": 1000, "height": 565, "facing": 1}]
    script = _load(
        tmp_script,
        [{"type": "ground", "y": 1100}, {"type": "boat", "x": 100, "y": 1000, "crew": crew}],
    )
    issues = check_all(script, theme)
    hits = [i for i in issues if "overlaps seal" in i.message]
    assert [i.path for i in hits] == ["slides[0].scene.layers[1].crew[0]"]
    assert hits[0].severity == "error"


def test_boat_too_many_crew_reported(tmp_script: ScriptFactory, theme: Any) -> None:
    crew = [{"role": "boat_crew"}] * 3
    script = _load(tmp_script, [{"type": "boat", "x": 540, "y": 1100, "crew": crew}])
    issues = check_all(script, theme)
    assert [(i.path, i.message) for i in issues] == [
        ("slides[0].scene.layers[0].crew", "boat supports at most 2 crew")
    ]


def test_default_slot_crew_gets_overlap_check(tmp_script: ScriptFactory, theme: Any) -> None:
    # the slot position (not an explicit one) is what the check must use
    crew = [{"role": "leader", "height": 565}]
    script = _load(tmp_script, [{"type": "boat", "x": 60, "y": 1000, "crew": crew}])
    issues = check_all(script, theme)
    assert any(
        i.path == "slides[0].scene.layers[0].crew[0]" and "outside the frame" in i.message
        for i in issues
    )


def test_reference_boats_pass_checks(tmp_script: ScriptFactory, theme: Any) -> None:
    boat1 = {
        "type": "boat",
        "x": 290,
        "y": 1056,
        "scale": 1.5,
        "crew": [
            {"role": "leader", "x": 300, "baseline": 1048, "height": 150, "facing": 1},
            {"role": "boat_crew", "x": 250, "baseline": 1050, "height": 120, "facing": -1},
        ],
    }
    boat2 = {
        "type": "boat",
        "x": 780,
        "y": 1104,
        "scale": 1.25,
        "crew": [
            {"role": "general", "x": 760, "baseline": 1098, "height": 125, "facing": 1},
            {"role": "boat_crew", "x": 815, "baseline": 1100, "height": 110, "facing": 1},
        ],
    }
    assert check_all(_load(tmp_script, [boat1, boat2]), theme) == []
