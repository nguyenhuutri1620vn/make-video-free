"""A blank memorial tablet on an altar, with an incense bowl and two candles (backlog #14).

Original procedural artwork. The tablet's plaque is left blank on purpose: no text is ever
drawn in a scene. Geometry is in altar units with the floor on y = 0 under
``translate(x, y)`` and ``scale(scale)``; the altar is about 280 units wide and the tablet
reaches about 340 units above the floor.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import TabletLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4
THIN: Final = 0.9

ALTAR_TOP: Final = (-140.0, -130.0, 280.0, 16.0)  # x, y, w, h
ALTAR_BODY: Final = (-122.0, -114.0, 244.0, 114.0)
ALTAR_FILL: Final = ("vermilion", "vermilion_dk")
ALTAR_PANEL: Final = "gold_dk"
ALTAR_PANEL_INSET: Final = 14.0

TABLET_BASE: Final = (-52.0, -160.0, 104.0, 30.0)  # pedestal x, y, w, h
TABLET_BODY: Final = (-36.0, -320.0, 72.0, 160.0)
TABLET_CROWN: Final = 22.0  # height of the cloud-shaped crown above the body
TABLET_FILL: Final = ("vermilion", "vermilion_dk")
PLAQUE: Final = (-22.0, -300.0, 44.0, 124.0)
PLAQUE_FILL: Final = ("gold_lt", "gold_dk")

BOWL: Final = (0.0, -146.0, 30.0, 16.0)  # centre x, rim y, radius x, depth
BOWL_FILL: Final = ("gold", "gold_dk")
STICKS: Final = (-10.0, 0.0, 10.0)
STICK_HEIGHT: Final = 70.0
STICK_COLOR: Final = "vermilion_dk"
EMBER: Final = "gold_lt"
SMOKE_COLOR: Final = "egg_tone"
SMOKE_ALPHA: Final = 0.35

CANDLES: Final = (-100.0, 100.0)
CANDLE: Final = (9.0, 46.0)  # half width, height
CANDLE_FILL: Final = ("vermilion", "vermilion_dk")
FLAME_FILL: Final = "gold_lt"
GLOW_ALPHA: Final = 0.3


def _grad(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _altar(cv: Canvas, ctx: DrawContext) -> None:
    x, y, w, h = ALTAR_BODY
    cv.rect(x, y, w, h)
    _grad(cv, ctx, ALTAR_FILL, y, 0)
    inset = ALTAR_PANEL_INSET
    cv.color(ctx.palette[ALTAR_PANEL]).rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset)
    cv.stroke(THIN)
    tx, ty, tw, th = ALTAR_TOP
    cv.rect(tx, ty, tw, th)
    _grad(cv, ctx, ALTAR_FILL, ty, ty + th)


def _tablet(cv: Canvas, ctx: DrawContext) -> None:
    x, y, w, h = TABLET_BASE
    cv.rect(x, y, w, h)
    _grad(cv, ctx, TABLET_FILL, y, y + h)
    bx, by, bw, bh = TABLET_BODY
    crown = by - TABLET_CROWN
    cv.M(bx, by + bh).L(bx, by).C(bx, crown, bx + bw * 0.3, crown - 6, bx + bw / 2, crown)
    cv.C(bx + bw * 0.7, crown - 6, bx + bw, crown, bx + bw, by).L(bx + bw, by + bh).Z()
    _grad(cv, ctx, TABLET_FILL, crown, by + bh)
    px, py, pw, ph = PLAQUE
    cv.rect(px, py, pw, ph)
    _grad(cv, ctx, PLAQUE_FILL, py, py + ph)


def _incense(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, rim, rx, depth = BOWL
    for dx in STICKS:
        cv.color(pal[STICK_COLOR]).M(cx + dx, rim).L(cx + dx * 1.4, rim - STICK_HEIGHT).stroke(2.0)
        top = (cx + dx * 1.4, rim - STICK_HEIGHT)
        cv.color(pal[EMBER]).ellipse(*top, 2.2, 2.2).fill()
        cv.M(*top).C(top[0] - 8, top[1] - 24, top[0] + 10, top[1] - 44, top[0] + 2, top[1] - 70)
        cv.color(pal[SMOKE_COLOR], SMOKE_ALPHA).stroke(1.4)
    cv.M(cx - rx, rim).C(cx - rx, rim + depth * 1.3, cx + rx, rim + depth * 1.3, cx + rx, rim).Z()
    _grad(cv, ctx, BOWL_FILL, rim, rim + depth)
    cv.color(pal[OUTLINE]).ellipse(cx, rim, rx, 4).stroke(THIN)


def _candles(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    half, height = CANDLE
    base = ALTAR_TOP[1]
    for x in CANDLES:
        cv.rect(x - half, base - height, half * 2, height)
        _grad(cv, ctx, CANDLE_FILL, base - height, base)
        fy = base - height - 4
        glow = pal[FLAME_FILL]
        cv.ellipse(x, fy - 8, 26, 26).rgrad(x, fy - 8, 26, [(0, glow, GLOW_ALPHA), (1, glow, 0.0)])
        cv.fill()
        cv.M(x, fy - 18).C(x + 6, fy - 8, x + 5, fy, x, fy).C(x - 5, fy, x - 6, fy - 8, x, fy - 18)
        cv.Z().color(pal[FLAME_FILL]).fill()


def draw_tablet(img: FloatImage, layer: TabletLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Altar, tablet on its pedestal, candles, then the incense bowl in front."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _altar(cv, ctx)
    _tablet(cv, ctx)
    _candles(cv, ctx)
    _incense(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(TabletLayer, draw_tablet)])
