"""A crown and a square seal on a cushion, on a low table before a folding screen (backlog #9).

Original procedural artwork, not modelled on any surviving regalia. Geometry is in regalia
units with the floor on y = 0 under ``translate(x, y)`` and ``scale(scale)``; the screen is
about 320 units wide and 300 tall.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import RegaliaLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4
THIN: Final = 0.9

SCREEN_PANELS: Final = 4
SCREEN_PANEL: Final = (78.0, 300.0)  # width, height
SCREEN_FOOT: Final = -6.0
SCREEN_FILL: Final = ("deep", "black")
SCREEN_INSET: Final = 8.0
MOTIF_COLOR: Final = "gold_dk"
MOTIF_SUN: Final = (0.0, -0.72, 0.16)  # centre x, y and radius, in panel widths/heights
MOTIF_CLOUD_Y: Final = -0.42

TABLE_TOP: Final = (-118.0, -78.0, 236.0, 14.0)  # x, y, w, h
TABLE_FILL: Final = "vermilion_dk"
TABLE_LEG_X: Final = (-104.0, 104.0)
TABLE_LEG_CURL: Final = 14.0

CUSHION: Final = (0.0, -92.0, 86.0, 18.0)  # centre x, y and radii
CUSHION_FILL: Final = ("vermilion", "vermilion_dk")
TASSEL_COLOR: Final = "gold_lt"

CROWN_X: Final = -36.0
CROWN_BASE: Final = (-108.0, 56.0, 18.0)  # top y, width, height
CROWN_FILL: Final = ("gold_lt", "gold_dk")
CROWN_POINTS: Final = 5
CROWN_POINT_HEIGHT: Final = 34.0
CROWN_JEWEL: Final = "vermilion"

SEAL_X: Final = 42.0
SEAL_BLOCK: Final = (-100.0, 36.0, 26.0)  # top y, width, height
SEAL_KNOB: Final = (13.0, 12.0)  # radii
SEAL_FILL: Final = ("gold", "gold_dk")
SEAL_FACE: Final = "vermilion"


def _grad(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _screen(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    w, h = SCREEN_PANEL
    left = -w * SCREEN_PANELS / 2
    for k in range(SCREEN_PANELS):
        x = left + k * w
        top = SCREEN_FOOT - h
        cv.rect(x, top, w, h)
        _grad(cv, ctx, SCREEN_FILL, top, SCREEN_FOOT)
        inset = SCREEN_INSET
        cv.color(pal[MOTIF_COLOR]).rect(x + inset, top + inset, w - 2 * inset, h - 2 * inset)
        cv.stroke(THIN)
        cx = x + w / 2 + MOTIF_SUN[0] * w
        sun_r = MOTIF_SUN[2] * w
        cv.color(pal[MOTIF_COLOR]).ellipse(cx, SCREEN_FOOT + MOTIF_SUN[1] * h, sun_r, sun_r)
        cv.stroke(THIN * 1.4)
        cy = SCREEN_FOOT + MOTIF_CLOUD_Y * h
        side = 1 if k % 2 else -1
        cv.M(cx - side * w * 0.3, cy).C(cx - side * w * 0.3, cy - 14, cx, cy - 14, cx, cy)
        cv.C(cx, cy + 10, cx + side * w * 0.2, cy + 10, cx + side * w * 0.2, cy)
        cv.color(pal[MOTIF_COLOR]).stroke(THIN * 1.4)


def _table(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    x, y, w, h = TABLE_TOP
    for lx in TABLE_LEG_X:
        out = TABLE_LEG_CURL if lx > 0 else -TABLE_LEG_CURL
        cv.M(lx, y + h).C(lx, y + h + 30, lx + out, -20, lx + out, 0)
        cv.color(pal[OUTLINE]).stroke(8.0)
        cv.M(lx, y + h).C(lx, y + h + 30, lx + out, -20, lx + out, 0)
        cv.color(pal[TABLE_FILL]).stroke(6.0)
    cv.rect(x, y, w, h).color(pal[TABLE_FILL]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _cushion(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, cy, rx, ry = CUSHION
    cv.ellipse(cx, cy, rx, ry)
    _grad(cv, ctx, CUSHION_FILL, cy - ry, cy + ry)
    for side in (-1, 1):
        tx = cx + side * rx
        cv.M(tx, cy).L(tx + side * 6, cy + 16).M(tx, cy).L(tx + side * 1, cy + 18)
        cv.color(pal[TASSEL_COLOR]).stroke(1.6)


def _crown(cv: Canvas, ctx: DrawContext) -> None:
    top, width, height = CROWN_BASE
    left = CROWN_X - width / 2
    step = width / (CROWN_POINTS - 1)
    cv.M(left, top)
    for k in range(CROWN_POINTS - 1):
        mid = left + step * (k + 0.5)
        peak = CROWN_POINT_HEIGHT * (1.0 if k in (1, 2) else 0.7)
        cv.C(mid - step * 0.4, top - peak * 0.3, mid - step * 0.1, top - peak, mid, top - peak)
        cv.C(
            mid + step * 0.1,
            top - peak,
            mid + step * 0.4,
            top - peak * 0.3,
            left + step * (k + 1),
            top,
        )
    cv.L(left + width, top + height).L(left, top + height).Z()
    _grad(cv, ctx, CROWN_FILL, top - CROWN_POINT_HEIGHT, top + height)
    pal = ctx.palette
    cv.color(pal[CROWN_JEWEL]).ellipse(CROWN_X, top + height / 2, 5, 5).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(THIN)
    cv.color(pal[OUTLINE]).M(left, top).L(left + width, top).stroke(THIN)


def _seal(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    top, width, height = SEAL_BLOCK
    left = SEAL_X - width / 2
    kx, ky = SEAL_KNOB
    cv.ellipse(SEAL_X, top - ky * 0.6, kx, ky)
    _grad(cv, ctx, SEAL_FILL, top - ky * 1.6, top)
    cv.rect(left, top, width, height)
    _grad(cv, ctx, SEAL_FILL, top, top + height)
    cv.color(pal[SEAL_FACE]).rect(left + 4, top + height - 6, width - 8, 4).fill()


def draw_regalia(img: FloatImage, layer: RegaliaLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Screen, table, cushion, then the crown and the seal resting on it."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    if layer.screen:
        _screen(cv, ctx)
    _table(cv, ctx)
    _cushion(cv, ctx)
    _crown(cv, ctx)
    _seal(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(RegaliaLayer, draw_regalia)])
