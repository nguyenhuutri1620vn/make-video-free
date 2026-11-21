"""The golden turtle of the legend rising from the water, a glowing claw above it (Cổ Loa video).

Original procedural artwork, stylised like the other lacquer motifs: a domed gold shell with
scute lines, head raised on a long neck, front flippers on the water, ripple rings around it
and the claw it gives the king floating in a halo over its head.

Geometry is in turtle units under ``translate(x, y)``, ``scale(facing * scale, scale)``, with
the water line on y = 0; the head faces +x. The shell is 300 units long, the ripples reach
260 units from the centre and the claw halo is centred 300 units above the water.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import TurtleLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "black"
OUTLINE_WIDTH: Final = 1.6
SHELL: Final = (-10.0, -40.0, 150.0, 78.0)  # cx, cy, rx, ry (upper half above the water)
SHELL_FILL: Final = ("gold_lt", "gold", "gold_dk")
SCUTE_COLOR: Final = "gold_dk"
SCUTE_WIDTH: Final = 1.6
# scute ridge lines in shell units: across the dome and the central row of plates
SCUTE_ROWS: Final = (-0.45, 0.0, 0.45)
RIM_COLOR: Final = "vermilion_dk"

SKIN_FILL: Final = ("gold", "gold_dk")
NECK: Final = ((120.0, -40.0), (175.0, -60.0), (195.0, -140.0), (215.0, -160.0))
NECK_HALF: Final = 20.0
HEAD: Final = (232.0, -168.0, 34.0, 24.0)  # cx, cy, rx, ry
EYE: Final = (244.0, -176.0, 3.5)
FLIPPERS: Final = ((90.0, -4.0, 70.0, 16.0), (-120.0, -2.0, 52.0, 13.0))  # x, y, length, width

WATER_COLOR: Final = "gold_lt"
RIPPLES: Final = ((150.0, 22.0, 0.55), (205.0, 32.0, 0.35), (260.0, 42.0, 0.2))  # rx, ry, alpha
WATER_SHADE: Final = ("river_top", 0.7)

CLAW: Final = (20.0, -300.0, 70.0)  # cx, cy, halo radius
CLAW_FILL: Final = ("gold_lt", "gold")
HALO_COLOR: Final = "gold_lt"
HALO_ALPHA: Final = 0.5


def _water(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    color, alpha = WATER_SHADE
    rx, ry, _ = RIPPLES[-1]
    cv.ellipse(0.0, 0.0, rx, ry).color(pal[color], alpha).fill()
    for rx, ry, a in RIPPLES:
        cv.ellipse(0.0, 0.0, rx, ry).color(pal[WATER_COLOR], a).stroke(1.5)


def _flippers(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x, y, length, width in FLIPPERS:
        cv.M(x, y - width).C(x + length * 0.6, y - width, x + length, y, x + length, y + 4.0)
        cv.C(x + length * 0.5, y + width, x, y + width, x, y - width).Z()
        cv.color(pal[SKIN_FILL[1]]).fill(keep=True).color(pal[OUTLINE]).stroke(1.0)


def _neck_and_head(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = NECK
    h = NECK_HALF
    cv.M(x0, y0 - h).C(x1, y1 - h, x2 - h, y2, x3 - h * 0.4, y3 - h * 0.6)
    cv.L(x3 + h * 0.4, y3 + h * 0.6).C(x2 + h, y2 + h, x1, y1 + h, x0, y0 + h).Z()
    cv.vgrad(y3, y0, [(0, pal[SKIN_FILL[0]], 1), (1, pal[SKIN_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    cx, cy, rx, ry = HEAD
    cv.ellipse(cx, cy, rx, ry).color(pal[SKIN_FILL[0]]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    ex, ey, er = EYE
    cv.ellipse(ex, ey, er, er).color(pal["black"]).fill()


def _shell(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, cy, rx, ry = SHELL
    cv.save()
    cv.rect(cx - rx - 2, cy - ry - 2, 2 * rx + 4, ry + 42.0).clip()  # dome above the water
    cv.ellipse(cx, cy, rx, ry)
    stops = [(0, pal[SHELL_FILL[0]], 1), (0.55, pal[SHELL_FILL[1]], 1), (1, pal[SHELL_FILL[2]], 1)]
    cv.vgrad(cy - ry, cy + 40.0, stops).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for t in SCUTE_ROWS:  # meridians across the dome
        x = cx + t * rx
        cv.M(x, cy - ry * (1 - t * t) ** 0.5).C(x * 1.05, cy - 10.0, x * 1.1, cy + 20.0, x, cy + 40)
    cv.ellipse(cx, cy + 6.0, rx * 0.72, ry * 0.62)
    cv.color(pal[SCUTE_COLOR]).stroke(SCUTE_WIDTH)
    cv.restore()
    cv.M(cx - rx + 6.0, 0.0).L(cx + rx - 6.0, 0.0).color(pal[RIM_COLOR]).stroke(4.0)


def _claw(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, cy, r = CLAW
    glow = pal[HALO_COLOR]
    cv.ellipse(cx, cy, r, r).rgrad(cx, cy, r, [(0, glow, HALO_ALPHA), (1, glow, 0.0)]).fill()
    cv.M(cx - 12.0, cy - 26.0).C(cx - 14.0, cy, cx - 4.0, cy + 22.0, cx + 22.0, cy + 30.0)
    cv.C(cx + 8.0, cy + 12.0, cx + 10.0, cy - 8.0, cx + 12.0, cy - 26.0).Z()
    cv.vgrad(cy - 26.0, cy + 30.0, [(0, pal[CLAW_FILL[0]], 1), (1, pal[CLAW_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(1.2)


def draw_turtle(img: FloatImage, layer: TurtleLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Water and ripples, flippers, neck and head, the shell dome, then the claw."""
    del index  # no randomness
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.facing * layer.scale, layer.scale)
    _water(cv, ctx)
    _flippers(cv, ctx)
    _neck_and_head(cv, ctx)
    _shell(cv, ctx)
    if layer.claw:
        _claw(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(TurtleLayer, draw_turtle)])
