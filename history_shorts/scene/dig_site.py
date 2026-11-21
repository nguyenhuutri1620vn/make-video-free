"""A cut-away of the ground at a find spot (Cổ Loa video).

Original procedural artwork: a block of earth seen in section, wavy soil strata under a thin
topsoil line, and above the surface what the narration names. Modes:

* ``buried``: one arrowhead deep in the soil, a faint shaft of light reaching down to it;
* ``pit``: a road embankment being built, a hoe stuck in the ground and a basket of earth,
  beside a square pit about as wide as it is deep, with width and depth marks;
* ``hoard``: the same pit packed with arrowheads, the hoe at its rim;
* ``covered``: the pit full of arrowheads and filled over with darker earth, a low mound.

Geometry is in site units under ``translate(x, y)`` and ``scale(scale)``, with the ground
surface on y = 0: the section is 860 units wide and 460 deep; tools rise about 200 above.
The pit is 180 units wide and 216 deep (about 1 m by 1.2 m).
"""

from __future__ import annotations

import math
from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import DigSiteLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .arrowheads import TIP_Y, draw_one
from .registry import LayerDrawer, entry

HALF_W: Final = 430.0
DEPTH: Final = 460.0
OUTLINE: Final = "gold_dk"
OUTLINE_WIDTH: Final = 1.4
# (top y, colour) of each stratum, top to bottom; boundaries wave by STRATA_WAVE
STRATA: Final = ((0.0, "brown_lt"), (70.0, "brown"), (190.0, "deep_warm"), (320.0, "mountain_base"))
STRATA_WAVE: Final = 9.0
STRATA_LINE: Final = "gold_dk"
STRATA_LINE_ALPHA: Final = 0.55
PEBBLES: Final = 46
PEBBLE_R: Final = (2.0, 5.5)
PEBBLE_COLOR: Final = "egg_gap"
TOPSOIL: Final = ("jade", 6.0)  # colour, thickness of the grass line

SHAFT: Final = (60.0, 150.0, 0.30)  # half width at the surface, at the bottom, alpha
SHAFT_COLOR: Final = "gold_lt"
BURIED_AT: Final = (40.0, 290.0, math.radians(-58.0), 1.25)  # x, y, angle, scale

PIT: Final = (-40.0, 180.0, 216.0)  # left x, width, depth
PIT_FILL: Final = ("shadow", "egg_gap")
MARK_COLOR: Final = "gold_lt"
MARK_WIDTH: Final = 2.0
MARK_GAP: Final = 22.0  # how far the dimension marks sit from the pit
MARK_TICK: Final = 9.0

ROAD: Final = (-430.0, -120.0, 46.0, 30.0)  # left x, right x, height, slope run
ROAD_FILL: Final = ("egg_tone", "brown_lt")
HOE: Final = (175.0, -8.0, math.radians(28.0))  # blade point x, y, lean of the handle
HOE_HANDLE: Final = (190.0, 7.0)  # length, width
HOE_BLADE: Final = (44.0, 30.0)  # length, width
HOE_WOOD: Final = "brown_lt"
HOE_IRON: Final = "gold_dk"
BASKET: Final = (300.0, 0.0, 58.0, 44.0)  # centre x, floor y, half width, height
BASKET_FILL: Final = ("gold_dk", "brown")
BASKET_WEAVE: Final = "gold"

HOARD_COUNT: Final = 70
HOARD_SCALE: Final = (0.26, 0.34)
HOARD_POLISHED: Final = 0.25
FILL_EARTH: Final = "egg_gap"
MOUND: Final = 16.0


def _wave(x: float, k: int) -> float:
    return STRATA_WAVE * math.sin(x / 70.0 + k * 1.7) + 0.5 * STRATA_WAVE * math.sin(x / 23.0 + k)


def _band(cv: Canvas, top: float, bottom: float, k: int) -> None:
    xs = [-HALF_W + i * 20.0 for i in range(int(2 * HALF_W / 20.0) + 1)]
    cv.M(-HALF_W, top + (_wave(-HALF_W, k) if k else 0.0))
    for x in xs:
        cv.L(x, top + (_wave(x, k) if k else 0.0))
    for x in reversed(xs):
        cv.L(x, bottom + (_wave(x, k + 1) if bottom < DEPTH else 0.0))
    cv.Z()


def soil_section(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    pal = ctx.palette
    for k, (top, color) in enumerate(STRATA):
        bottom = STRATA[k + 1][0] if k + 1 < len(STRATA) else DEPTH
        _band(cv, top, bottom, k)
        cv.color(pal[color]).fill()
        if k:
            xs = [-HALF_W + i * 20.0 for i in range(int(2 * HALF_W / 20.0) + 1)]
            cv.M(-HALF_W, top + _wave(-HALF_W, k))
            for x in xs:
                cv.L(x, top + _wave(x, k))
            cv.color(pal[STRATA_LINE], STRATA_LINE_ALPHA).stroke(1.0)
    for _ in range(PEBBLES):
        x = float(rng.uniform(-HALF_W + 10.0, HALF_W - 10.0))
        y = float(rng.uniform(40.0, DEPTH - 10.0))
        r = float(rng.uniform(*PEBBLE_R))
        cv.ellipse(x, y, r * 1.4, r).color(pal[PEBBLE_COLOR], 0.8).fill()
    color, width = TOPSOIL
    cv.M(-HALF_W, 0.0).L(HALF_W, 0.0).color(pal[color]).stroke(width)
    cv.rect(-HALF_W, 0.0, 2 * HALF_W, DEPTH).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _buried(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    top, bottom, alpha = SHAFT
    x, y, angle, scale = BURIED_AT
    glow = ctx.palette[SHAFT_COLOR]
    cv.M(x - top, 0.0).L(x + top, 0.0).L(x + bottom, y + 60.0).L(x - bottom, y + 60.0).Z()
    cv.vgrad(0.0, y + 60.0, [(0, glow, alpha), (0.8, glow, alpha * 0.6), (1, glow, 0.0)]).fill()
    cv.ellipse(x, y, 120.0, 120.0).rgrad(x, y, 120.0, [(0, glow, 0.35), (1, glow, 0.0)]).fill()
    _arrow_at(cv, ctx, rng, x, y, angle, scale, polished=False)


def _arrow_at(
    cv: Canvas,
    ctx: DrawContext,
    rng: Generator,
    x: float,
    y: float,
    angle: float,
    scale: float,
    *,
    polished: bool,
) -> None:
    cv.save()
    cv.translate(x, y)
    cv.rotate(angle)
    cv.scale(scale, scale)
    cv.translate(0.0, -TIP_Y / 2)  # about the middle of the arrowhead
    draw_one(cv, ctx, rng, polished=polished)
    cv.restore()


def _pit(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    left, width, depth = PIT
    cv.rect(left, 0.0, width, depth)
    cv.vgrad(0.0, depth, [(0, pal[PIT_FILL[0]], 1), (1, pal[PIT_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _marks(cv: Canvas, ctx: DrawContext) -> None:
    """Width mark over the pit and depth mark beside it, with end ticks."""
    left, width, depth = PIT
    y = -MARK_GAP
    x = left - MARK_GAP
    t = MARK_TICK
    cv.M(left, y).L(left + width, y).M(left, y - t).L(left, y + t)
    cv.M(left + width, y - t).L(left + width, y + t)
    cv.M(x, 0.0).L(x, depth).M(x - t, 0.0).L(x + t, 0.0).M(x - t, depth).L(x + t, depth)
    cv.color(ctx.palette[MARK_COLOR]).stroke(MARK_WIDTH)


def _road(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    left, right, height, run = ROAD
    cv.M(left, 0.0).L(left, -height).L(right - run, -height).L(right, 0.0).Z()
    cv.vgrad(-height, 0.0, [(0, pal[ROAD_FILL[0]], 1), (1, pal[ROAD_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for k in range(1, 6):
        x = left + (right - run - left) * k / 6
        cv.M(x, -height + 8.0).L(x + 14.0, -height + 8.0)
    cv.color(pal[OUTLINE], 0.6).stroke(1.0)


def _hoe(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    px, py, lean = HOE
    length, width = HOE_HANDLE
    blade_len, blade_w = HOE_BLADE
    cv.save()
    cv.translate(px, py)
    cv.rotate(lean)
    cv.rect(-width / 2, -length - blade_len + 6.0, width, length)
    cv.color(pal[HOE_WOOD]).fill(keep=True).color(pal[OUTLINE]).stroke(1.0)
    cv.M(-blade_w / 2, -blade_len).L(blade_w / 2, -blade_len).L(blade_w * 0.3, 8.0)
    cv.L(-blade_w * 0.3, 8.0).Z()
    cv.color(pal[HOE_IRON]).fill(keep=True).color(pal["black"]).stroke(1.0)
    cv.restore()


def _basket(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, floor, half, height = BASKET
    cv.M(cx - half, floor - height).L(cx + half, floor - height).L(cx + half * 0.75, floor)
    cv.L(cx - half * 0.75, floor).Z()
    cv.vgrad(floor - height, floor, [(0, pal[BASKET_FILL[0]], 1), (1, pal[BASKET_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for k in range(1, 4):
        y = floor - height * k / 4
        cv.M(cx - half * (0.75 + 0.25 * k / 4), y).L(cx + half * (0.75 + 0.25 * k / 4), y)
    cv.color(pal[BASKET_WEAVE], 0.7).stroke(1.0)
    cv.ellipse(cx, floor - height, half * 0.9, 14.0).color(pal[ROAD_FILL[1]]).fill()


def _hoard(cv: Canvas, ctx: DrawContext, rng: Generator, fill_to: float) -> None:
    """Arrowheads packed in the pit from ``fill_to`` down, clipped to the pit."""
    left, width, depth = PIT
    cv.save()
    cv.rect(left, 0.0, width, depth).clip()
    items = []
    for _ in range(HOARD_COUNT):
        x = float(rng.uniform(left + 10.0, left + width - 10.0))
        y = float(rng.uniform(fill_to, depth))
        items.append(
            (y, x, float(rng.uniform(-math.pi, math.pi)), float(rng.uniform(*HOARD_SCALE)))
        )
    for y, x, angle, scale in sorted(items):
        polished = bool(rng.uniform() < HOARD_POLISHED)
        _arrow_at(cv, ctx, rng, x, y, angle, scale, polished=polished)
    cv.restore()


def _cover(cv: Canvas, ctx: DrawContext) -> None:
    left, width, _ = PIT
    fill_depth = 70.0
    pal = ctx.palette
    cv.rect(left, 0.0, width, fill_depth).color(pal[FILL_EARTH]).fill()
    cv.M(left - 20.0, 0.0).C(left + width * 0.3, -MOUND, left + width * 0.7, -MOUND,
                             left + width + 20.0, 0.0).Z()  # fmt: skip
    cv.color(pal[FILL_EARTH]).fill()


def draw_dig_site(img: FloatImage, layer: DigSiteLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Soil section, then the mode's pit, finds and tools."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    rng = ctx.rng(index)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    soil_section(cv, ctx, rng)
    if layer.mode == "buried":
        _buried(cv, ctx, rng)
    else:
        _pit(cv, ctx)
        if layer.mode == "pit":
            _marks(cv, ctx)
            _road(cv, ctx)
            _basket(cv, ctx)
        elif layer.mode == "hoard":
            _hoard(cv, ctx, rng, 20.0)
            _marks(cv, ctx)
        else:
            _hoard(cv, ctx, rng, 80.0)
            _cover(cv, ctx)
        if layer.mode != "covered":
            _hoe(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(DigSiteLayer, draw_dig_site)])
