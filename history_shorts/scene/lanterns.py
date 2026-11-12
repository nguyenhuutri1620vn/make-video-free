"""Lotus lanterns floating on the water, each with a small flame and a reflection (backlog #13).

Original procedural artwork. Each lantern is drawn in lantern units under
``translate(x, y)`` and ``scale(s)``: ``y`` is the waterline, the lantern is about 44 units
wide and 50 tall with its flame.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import LanternItem, LanternsLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.0

REFLECTION_COLOR: Final = "gold_lt"
REFLECTION: Final = (6.0, 46.0, 0.35)  # half width, length, alpha
GLOW_COLOR: Final = "gold_lt"
GLOW: Final = (0.0, -30.0, 30.0, 0.35)  # centre x, y, radius, alpha

SAUCER: Final = (0.0, 0.0, 22.0, 5.0)  # centre and radii
SAUCER_FILL: Final = "gold_dk"
# (rotation in degrees, length, half width, fill); outer petals first
PETALS: Final = ((-55.0, 18.0, 7.0, "vermilion_dk"), (55.0, 18.0, 7.0, "vermilion_dk"),
                 (-25.0, 22.0, 8.0, "vermilion"), (25.0, 22.0, 8.0, "vermilion"),
                 (0.0, 24.0, 8.5, "vermilion"))  # fmt: skip
PETAL_BASE_Y: Final = -2.0
FLAME: Final = (0.0, -26.0, 4.5, 12.0)  # base x, base y, half width, height
FLAME_FILL: Final = "gold_lt"


def _reflection(cv: Canvas, ctx: DrawContext) -> None:
    half, length, alpha = REFLECTION
    colour = ctx.palette[REFLECTION_COLOR]
    cv.M(-half, 4).L(half, 4).L(half * 0.3, 4 + length).L(-half * 0.3, 4 + length).Z()
    cv.vgrad(4, 4 + length, [(0, colour, alpha), (1, colour, 0.0)]).fill()


def _glow(cv: Canvas, ctx: DrawContext) -> None:
    x, y, r, alpha = GLOW
    colour = ctx.palette[GLOW_COLOR]
    cv.ellipse(x, y, r, r).rgrad(x, y, r, [(0, colour, alpha), (1, colour, 0.0)]).fill()


def _body(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, cy, rx, ry = SAUCER
    cv.color(pal[SAUCER_FILL]).ellipse(cx, cy, rx, ry).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for rotation, length, half, fill in PETALS:
        cv.save()
        cv.translate(0, PETAL_BASE_Y)
        cv.rotate(math.radians(rotation))
        cv.M(0, 0).C(-half, -length * 0.4, -half * 0.6, -length * 0.85, 0, -length)
        cv.C(half * 0.6, -length * 0.85, half, -length * 0.4, 0, 0).Z()
        cv.color(pal[fill]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
        cv.restore()
    fx, fy, fw, fh = FLAME
    cv.M(fx, fy - fh).C(fx + fw, fy - fh * 0.4, fx + fw, fy, fx, fy)
    cv.C(fx - fw, fy, fx - fw, fy - fh * 0.4, fx, fy - fh).Z()
    cv.color(pal[FLAME_FILL]).fill()


def _lantern(cv: Canvas, ctx: DrawContext, item: LanternItem) -> None:
    cv.save()
    cv.translate(item.x, item.y)
    cv.scale(item.scale, item.scale)
    _reflection(cv, ctx)
    _glow(cv, ctx)
    _body(cv, ctx)
    cv.restore()


def draw_lanterns(
    img: FloatImage, layer: LanternsLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Lanterns in the order given; list far (small) ones first so near ones overlap them."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    for item in layer.items:
        _lantern(cv, ctx, item)
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(LanternsLayer, draw_lanterns)])
