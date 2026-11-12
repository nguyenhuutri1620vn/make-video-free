"""A bronze-drum face: gold-leaf disc with a star, ring bands and flying birds (backlog #1).

Original procedural artwork in the spirit of Đông Sơn drum faces, not traced from any drum.
Geometry is in drum units: the face has radius 100 under ``translate(x, y)`` and
``scale(r / 100)``, so every band keeps its proportions at any size.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, fill_mask, over
from history_shorts.config import DrumLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.textures import gold_leaf

from .registry import WHITE, LayerDrawer, entry

UNITS: Final = 100.0  # face radius in drum units

LINE_COLOR: Final = "gold_dk"
LINE_WIDTH: Final = 0.9
RINGS: Final = (26.0, 32.0, 40.0, 64.0, 72.0, 86.0, 92.0, 100.0)

FIELD_RADIUS: Final = 26.0
FIELD_COLOR: Final = "deep"
STAR_COLOR: Final = "gold_lt"
STAR_RAYS: Final = 12
STAR_TIP: Final = 24.0
STAR_BASE: Final = 6.0
STAR_HALF_ANGLE: Final = 13.0  # degrees either side of a ray at its base

ZIGZAG_RADII: Final = (27.5, 30.5)
ZIGZAG_TEETH: Final = 40

BIRD_RADIUS: Final = 52.0
BIRD_FILL: Final = "vermilion_dk"
BIRD_SIZE: Final = 1.35  # bird units per drum unit

CIRCLE_RADIUS: Final = 68.0
CIRCLE_COUNT: Final = 28
CIRCLE_SIZE: Final = 2.6
CIRCLE_DOT: Final = 0.9

TICK_RADII: Final = (75.0, 83.0)
TICK_COUNT: Final = 90

DOT_RADIUS: Final = 89.0
DOT_COUNT: Final = 64
DOT_SIZE: Final = 1.1


def _polar(radius: float, degrees: float) -> tuple[float, float]:
    a = math.radians(degrees)
    return radius * math.cos(a), radius * math.sin(a)


def _star(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cv.color(pal[FIELD_COLOR]).ellipse(0, 0, FIELD_RADIUS, FIELD_RADIUS).fill()
    step = 360.0 / STAR_RAYS
    for k in range(STAR_RAYS):
        angle = k * step - 90
        cv.M(*_polar(STAR_BASE, angle - STAR_HALF_ANGLE)).L(*_polar(STAR_TIP, angle))
        cv.L(*_polar(STAR_BASE, angle + STAR_HALF_ANGLE)).Z()
    cv.color(pal[STAR_COLOR]).fill()
    cv.color(pal[STAR_COLOR]).ellipse(0, 0, STAR_BASE + 0.5, STAR_BASE + 0.5).fill()


def _rings(cv: Canvas, ctx: DrawContext) -> None:
    for radius in RINGS:
        cv.color(ctx.palette[LINE_COLOR]).ellipse(0, 0, radius, radius).stroke(LINE_WIDTH)


def _zigzag(cv: Canvas, ctx: DrawContext) -> None:
    inner, outer = ZIGZAG_RADII
    step = 360.0 / (ZIGZAG_TEETH * 2)
    cv.M(*_polar(inner, 0))
    for k in range(1, ZIGZAG_TEETH * 2 + 1):
        cv.L(*_polar(outer if k % 2 else inner, k * step))
    cv.color(ctx.palette[LINE_COLOR]).stroke(LINE_WIDTH)


def _bird_path(cv: Canvas) -> None:
    """A long-beaked bird flying towards +x: beak, crested head, swept wing, forked tail."""
    cv.M(13, 0).L(7, -1.2).C(6, -4, 4, -5.5, 3.5, -6).C(4, -4, 4.5, -2.6, 4, -2)
    cv.C(1, -2.4, -2, -7, -6, -8.5).C(-4, -5, -3, -3, -4, -2)
    cv.L(-12, -3.5).L(-9, 0).L(-12, 3).C(-6, 2.6, 2, 2.4, 7, 1.2).Z()


def _birds(cv: Canvas, ctx: DrawContext, count: int) -> None:
    pal = ctx.palette
    for k in range(count):
        angle = k * 360.0 / count
        cv.save()
        cv.translate(*_polar(BIRD_RADIUS, angle))
        cv.rotate(math.radians(angle - 90))  # fly anticlockwise, along the ring
        cv.scale(BIRD_SIZE, BIRD_SIZE)
        _bird_path(cv)
        cv.color(pal[BIRD_FILL]).fill(keep=True)
        cv.color(pal[LINE_COLOR]).stroke(LINE_WIDTH * 0.7)
        cv.restore()


def _circles_ticks_dots(cv: Canvas, ctx: DrawContext) -> None:
    line = ctx.palette[LINE_COLOR]
    for k in range(CIRCLE_COUNT):
        x, y = _polar(CIRCLE_RADIUS, k * 360.0 / CIRCLE_COUNT)
        cv.color(line).ellipse(x, y, CIRCLE_SIZE, CIRCLE_SIZE).stroke(LINE_WIDTH * 0.8)
        cv.color(line).ellipse(x, y, CIRCLE_DOT, CIRCLE_DOT).fill()
    inner, outer = TICK_RADII
    for k in range(TICK_COUNT):
        angle = k * 360.0 / TICK_COUNT
        cv.M(*_polar(inner, angle)).L(*_polar(outer, angle))
    cv.color(line).stroke(LINE_WIDTH * 0.6)
    for k in range(DOT_COUNT):
        x, y = _polar(DOT_RADIUS, k * 360.0 / DOT_COUNT)
        cv.color(line).ellipse(x, y, DOT_SIZE, DOT_SIZE).fill()


def draw_drum(img: FloatImage, layer: DrumLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Gold-leaf face masked to the circle, then the inlaid star, bands and birds."""
    gold = ctx.theme.textures.gold_leaf
    tile = gold.tile if layer.tile is None else layer.tile
    worn = gold.worn if layer.worn is None else layer.worn
    disc = Canvas(CANVAS_W, CANVAS_H)
    disc.color(WHITE).ellipse(layer.x, layer.y, layer.r, layer.r).fill()
    tex = gold_leaf(ctx.rng(index), ctx.palette, tile, worn, width=CANVAS_W, height=CANVAS_H)
    img = fill_mask(img, tex, disc.mask())
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.r / UNITS, layer.r / UNITS)
    _star(cv, ctx)
    _zigzag(cv, ctx)
    _birds(cv, ctx, layer.birds)
    _circles_ticks_dots(cv, ctx)
    _rings(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(DrumLayer, draw_drum)])
