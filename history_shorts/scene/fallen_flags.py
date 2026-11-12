"""An abandoned camp: an empty tent, spears on the ground, a torn flag, a cold fire (backlog #10).

Original procedural artwork. Nothing here shows people or violence: weapons lie at rest and
the fire is out. Geometry is in camp units with the ground on y = 0 under ``translate(x, y)``
and ``scale(scale)``; the camp is about 420 units wide and 190 tall.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import FallenFlagsLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4
THIN: Final = 0.9

TENT: Final = (130.0, 190.0, 70.0)  # centre x, half width at the ground, height
TENT_FILL: Final = ("vermilion", "vermilion_dk")
TENT_FLAP: Final = "black"
TENT_POLE: Final = "gold_dk"

# (x0, y0, x1, y1): shaft from butt to blade base; the blade continues past (x1, y1)
SPEARS: Final = (
    (-205.0, -4.0, -10.0, -14.0),
    (-180.0, -14.0, 20.0, -2.0),
    (-120.0, -2.0, 70.0, -30.0),
)
SHAFT_COLOR: Final = "brown_lt"
SHAFT_WIDTH: Final = 3.2
BLADE_LENGTH: Final = 22.0
BLADE_HALF: Final = 5.0
BLADE_FILL: Final = "gold_lt"

FLAG_POLE: Final = ((-150.0, 0.0), (-62.0, -150.0))  # foot, top: leaning pole
POLE_COLOR: Final = "gold_dk"
POLE_WIDTH: Final = 3.5
FLAG_FILL: Final = "vermilion_dk"
FLAG_DROP: Final = 70.0  # how far the limp flag hangs below the pole top
FLAG_TEETH: Final = 5  # ragged lower edge

FIRE: Final = (40.0, -6.0)  # centre of the ring of stones
STONES: Final = 7
STONE_RING: Final = (30.0, 9.0)  # radii of the ring
STONE_SIZE: Final = (7.0, 5.0)
STONE_FILL: Final = ("egg_tone", "brown")
LOG_COLOR: Final = "hull_dk"
LOG_WIDTH: Final = 6.0
SMOKE_COLOR: Final = "egg_tone"
SMOKE_ALPHA: Final = 0.3


def _grad(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _tent(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, half, height = TENT
    cv.M(cx - half * 0.55, 0).L(cx, -height).L(cx + half * 0.55, 0).Z()
    _grad(cv, ctx, TENT_FILL, -height, 0)
    cv.M(cx, -height * 0.75).C(cx - 10, -height * 0.4, cx - 18, -10, cx - 22, 0).L(cx + 6, 0).Z()
    cv.color(pal[TENT_FLAP]).fill()
    cv.M(cx - 12, -height - 14).L(cx + 6, -height + 6).M(cx + 12, -height - 14)
    cv.L(cx - 6, -height + 6).color(pal[TENT_POLE]).stroke(2.5)


def _spears(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x0, y0, x1, y1 in SPEARS:
        cv.color(pal[SHAFT_COLOR]).M(x0, y0).L(x1, y1).stroke(SHAFT_WIDTH)
        dx, dy = x1 - x0, y1 - y0
        length = (dx * dx + dy * dy) ** 0.5
        ux, uy, nx, ny = dx / length, dy / length, -dy / length, dx / length
        tx, ty = x1 + ux * BLADE_LENGTH, y1 + uy * BLADE_LENGTH
        mx, my = x1 + ux * BLADE_LENGTH * 0.4, y1 + uy * BLADE_LENGTH * 0.4
        cv.M(x1, y1).L(mx + nx * BLADE_HALF, my + ny * BLADE_HALF).L(tx, ty)
        cv.L(mx - nx * BLADE_HALF, my - ny * BLADE_HALF).Z()
        cv.color(pal[BLADE_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(THIN)


def _flag(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    (fx, fy), (tx, ty) = FLAG_POLE
    cv.color(pal[POLE_COLOR]).M(fx, fy).L(tx, ty).stroke(POLE_WIDTH)
    width = 64.0
    cv.M(tx, ty).C(tx + width * 0.5, ty + 6, tx + width * 0.8, ty + 14, tx + width, ty + 24)
    bottom = ty + FLAG_DROP
    step = width / FLAG_TEETH
    for k in range(FLAG_TEETH, 0, -1):  # ragged edge from right to left
        x = tx + k * step
        cv.L(x - step * 0.3, bottom - (12 if k % 2 else 0) + k * 3)
        cv.L(x - step, bottom - 4 + k * 2)
    cv.L(tx + 2, ty + 20).Z()
    cv.color(pal[FLAG_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(THIN)


def _fire(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, cy = FIRE
    cv.color(pal[LOG_COLOR]).M(cx - 22, cy + 2).L(cx + 20, cy - 8).stroke(LOG_WIDTH)
    cv.color(pal[LOG_COLOR]).M(cx - 18, cy - 8).L(cx + 22, cy + 2).stroke(LOG_WIDTH)
    rx, ry = STONE_RING
    sx, sy = STONE_SIZE
    for k in range(STONES):
        a = math.pi * (0.05 + 0.9 * k / (STONES - 1))  # front half of the ring only
        x, y = cx + rx * math.cos(a), cy + ry * math.sin(a)
        cv.ellipse(x, y, sx, sy)
        _grad(cv, ctx, STONE_FILL, y - sy, y + sy)
    cv.M(cx, cy - 12).C(cx - 14, cy - 40, cx + 16, cy - 60, cx + 2, cy - 92)
    cv.color(pal[SMOKE_COLOR], SMOKE_ALPHA).stroke(2.0)


def draw_fallen_flags(
    img: FloatImage, layer: FallenFlagsLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Tent at the back, then the leaning flag, the cold fire and the spears in front."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _tent(cv, ctx)
    _flag(cv, ctx)
    _fire(cv, ctx)
    _spears(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(FallenFlagsLayer, draw_fallen_flags)])
