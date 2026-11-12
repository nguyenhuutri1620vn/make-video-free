"""An earthen citadel of concentric ramparts seen from above-front (backlog #17).

Original procedural artwork (spec Appendix B, "thành quách"), not a plan of any real site.
Rings are painted outer to inner: each rampart is an ellipse filled with earth, then its inner
ditch; the next ring is painted on top. Geometry is in citadel units under
``translate(x, y)`` and ``scale(scale)``: (0, 0) is the centre, the moat is 340 units across
each way horizontally and squashed vertically by ``TILT``.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import CitadelLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

TILT: Final = 0.38  # vertical squash of the rings (view from above-front)
OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4

MOAT_RX: Final = 340.0
MOAT_FILL: Final = ("river_top", "black")
WAVE_COLOR: Final = "gold_dk"

RING_RX: Final = (300.0, 205.0, 115.0)  # outer, middle, inner rampart
RING_SHIFT: Final = (0.0, -14.0, 10.0)  # x offsets: the rings wind slightly like a spiral
RAMPART_BAND: Final = 30.0
WALL_HEIGHT: Final = 20.0  # visible front face of each rampart
WALL_FILL: Final = "mountain_base"
RAMPART_FILL: Final = ("brown_lt", "mountain_base")
RIDGE_COLOR: Final = "gold"
DITCH_FILL: Final = "deep"
FIELD_FILL: Final = ("deep_warm", "deep")

HALL: Final = (10.0, -6.0, 46.0, 22.0)  # centre x, base y, half width, wall height
HALL_ROOF: Final = ("vermilion", "vermilion_dk")
HALL_WALL: Final = "brown"
GATE_HALF: Final = 26.0
GATE_HEIGHT: Final = 34.0


def _grad(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _moat(cv: Canvas, ctx: DrawContext) -> None:
    ry = MOAT_RX * TILT
    cv.ellipse(0, 0, MOAT_RX, ry)
    _grad(cv, ctx, MOAT_FILL, -ry, ry)
    for x, y in ((-250.0, 70.0), (180.0, 96.0), (-80.0, 118.0), (290.0, 30.0)):
        cv.M(x - 18, y).C(x - 9, y - 8, x, y - 8, x, y).C(x, y - 8, x + 9, y - 8, x + 18, y)
    cv.color(ctx.palette[WAVE_COLOR]).stroke(1.2)


def _ring(cv: Canvas, ctx: DrawContext, rx: float, shift: float, last: bool) -> None:
    pal = ctx.palette
    ry = rx * TILT
    cv.ellipse(shift, WALL_HEIGHT, rx, ry)
    cv.color(pal[WALL_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    cv.ellipse(shift, 0, rx, ry)
    _grad(cv, ctx, RAMPART_FILL, -ry, ry)
    top = rx - RAMPART_BAND * 0.35
    cv.color(pal[RIDGE_COLOR]).ellipse(shift, -4, top, top * TILT).stroke(1.6)
    inner = rx - RAMPART_BAND
    cv.ellipse(shift, 6, inner, inner * TILT)
    if last:
        _grad(cv, ctx, FIELD_FILL, -inner * TILT, inner * TILT)
    else:
        cv.color(pal[DITCH_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH * 0.6)


def _hall(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, base, half, wall = HALL
    cv.color(pal[HALL_WALL]).rect(cx - half * 0.7, base - wall, half * 1.4, wall).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(1.0)
    top = base - wall
    cv.M(cx - half - 8, top - 4).C(cx - half, top + 2, cx + half, top + 2, cx + half + 8, top - 4)
    cv.L(cx + half * 0.6, top - 26).L(cx - half * 0.6, top - 26).Z()
    _grad(cv, ctx, HALL_ROOF, top - 26, top)


def _gate(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    y = RING_RX[0] * TILT  # front of the outer rampart
    cv.color(pal[DITCH_FILL]).rect(-GATE_HALF, y - GATE_HEIGHT, GATE_HALF * 2, GATE_HEIGHT)
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(1.0)
    top = y - GATE_HEIGHT
    cv.M(-GATE_HALF - 12, top).L(GATE_HALF + 12, top).L(GATE_HALF - 4, top - 18)
    cv.L(-GATE_HALF + 4, top - 18).Z()
    _grad(cv, ctx, HALL_ROOF, top - 18, top)


def draw_citadel(img: FloatImage, layer: CitadelLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Moat, then the ramparts outer to inner, the hall in the middle and the front gate."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _moat(cv, ctx)
    for k, (rx, shift) in enumerate(zip(RING_RX, RING_SHIFT, strict=True)):
        _ring(cv, ctx, rx, shift, last=k == len(RING_RX) - 1)
    _hall(cv, ctx)
    _gate(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(CitadelLayer, draw_citadel)])
