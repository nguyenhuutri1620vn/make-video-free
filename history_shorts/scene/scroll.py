"""A half-unrolled paper scroll with columns of ink marks and a brush (backlog #5).

Original procedural artwork. The ink marks are abstract dashes in vertical columns, never
readable characters. Geometry is in scroll units under ``translate(x, y)`` and
``scale(scale)``: the sheet is centred on (0, 0), about 370 units wide and 250 tall.
"""

from __future__ import annotations

from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import ScrollLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold_dk"
OUTLINE_WIDTH: Final = 1.2

SHEET: Final = (-176.0, -110.0, 326.0, 220.0)  # x, y, w, h
SHEET_FILL: Final = ("egg", "egg_tone")  # top-to-bottom
SHEET_BORDER_INSET: Final = 8.0

ROD_X: Final = -182.0
ROD_HALF_WIDTH: Final = 6.0
ROD_REACH: Final = 128.0  # rod half length
ROD_FILL: Final = "brown"
KNOB: Final = (9.0, 6.0)  # radii
KNOB_FILL: Final = "gold"

ROLL: Final = (150.0, -116.0, 34.0, 232.0)  # rolled-up part: x, y, w, h
ROLL_FILL: Final = "egg_tone"
ROLL_SHADE: Final = "egg_gap"
ROLL_SHADE_ALPHA: Final = 0.25
ROLL_CAP_RY: Final = 6.0
ROLL_SPIRALS: Final = (0.75, 0.5, 0.25)  # spiral arcs, fraction of the cap radius

INK: Final = "brown"
INK_ALPHA: Final = 0.85
INK_WIDTH: Final = 4.0
COLUMNS_X: Final = (-128.0, 126.0)  # first and last column x (the seal sits left of them)
COLUMN_STEP: Final = 22.0
COLUMN_TOP: Final = -88.0
COLUMN_BOTTOM: Final = 88.0
MARK_LENGTH: Final = (5.0, 13.0)
MARK_GAP: Final = (4.0, 9.0)
EMPTY_COLUMN_ODDS: Final = 0.15  # chance a column ends early, like the end of a paragraph

SEAL: Final = (-160.0, 62.0, 20.0)  # x, y, size
SEAL_FILL: Final = "vermilion"

BRUSH: Final = ((40.0, 168.0), (232.0, 118.0))  # tip, end of the handle
BRUSH_WIDTH: Final = 7.0
BRUSH_FILL: Final = "brown_lt"
BRUSH_TIP_LENGTH: Final = 0.18  # of the brush length
BRUSH_TIP_FILL: Final = "black"
BRUSH_BAND_FILL: Final = "gold"


def _sheet(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    x, y, w, h = SHEET
    cv.rect(x, y, w, h).vgrad(y, y + h, [(0, pal[SHEET_FILL[0]], 1), (1, pal[SHEET_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    inset = SHEET_BORDER_INSET
    cv.color(pal[OUTLINE]).rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset)
    cv.stroke(OUTLINE_WIDTH * 0.6)


def _ink(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    color = ctx.palette[INK]
    first, last = COLUMNS_X
    x = last
    while x >= first:  # columns run right to left
        y = COLUMN_TOP
        stop = COLUMN_BOTTOM
        if rng.random() < EMPTY_COLUMN_ODDS:
            stop = COLUMN_TOP + (COLUMN_BOTTOM - COLUMN_TOP) * float(rng.uniform(0.3, 0.7))
        while y < stop:
            length = float(rng.uniform(*MARK_LENGTH))
            cv.M(x, y).L(x, min(y + length, stop))
            y += length + float(rng.uniform(*MARK_GAP))
        x -= COLUMN_STEP
    cv.color(color, INK_ALPHA).stroke(INK_WIDTH)


def _rod_and_roll(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cv.rect(ROD_X - ROD_HALF_WIDTH, -ROD_REACH, ROD_HALF_WIDTH * 2, ROD_REACH * 2)
    cv.color(pal[ROD_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    rx, ry = KNOB
    for y in (-ROD_REACH, ROD_REACH):
        cv.color(pal[KNOB_FILL]).ellipse(ROD_X, y, rx, ry).fill(keep=True)
        cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    x, y, w, h = ROLL
    cv.color(pal[ROLL_FILL]).rect(x, y, w, h).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    cv.color(pal[ROLL_SHADE], ROLL_SHADE_ALPHA).rect(x + w * 0.6, y, w * 0.4, h).fill()
    cx, half = x + w / 2, w / 2
    for cap_y in (y, y + h):
        cv.color(pal[ROLL_FILL]).ellipse(cx, cap_y, half, ROLL_CAP_RY).fill(keep=True)
        cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for k in ROLL_SPIRALS:
        cv.color(pal[OUTLINE]).ellipse(cx, y, half * k, ROLL_CAP_RY * k).stroke(OUTLINE_WIDTH * 0.6)


def _seal_and_brush(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    sx, sy, size = SEAL
    cv.color(pal[SEAL_FILL]).rect(sx, sy, size, size).fill()
    (tx, ty), (ex, ey) = BRUSH
    jx, jy = tx + (ex - tx) * BRUSH_TIP_LENGTH, ty + (ey - ty) * BRUSH_TIP_LENGTH
    cv.color(pal[OUTLINE]).M(jx, jy).L(ex, ey).stroke(BRUSH_WIDTH + 2)
    cv.color(pal[BRUSH_FILL]).M(jx, jy).L(ex, ey).stroke(BRUSH_WIDTH)
    dx, dy = jx - tx, jy - ty
    nx, ny = -dy, dx
    scale = BRUSH_WIDTH * 0.75 / (nx * nx + ny * ny) ** 0.5
    cv.M(jx + nx * scale, jy + ny * scale).C(jx, jy, tx + dx * 0.3, ty + dy * 0.3, tx, ty)
    cv.C(tx + dx * 0.3, ty + dy * 0.3, jx, jy, jx - nx * scale, jy - ny * scale).Z()
    cv.color(pal[BRUSH_TIP_FILL]).fill()
    cv.color(pal[BRUSH_BAND_FILL]).M(jx, jy).L(jx + dx * 0.25, jy + dy * 0.25).stroke(
        BRUSH_WIDTH + 1
    )


def draw_scroll(img: FloatImage, layer: ScrollLayer, ctx: DrawContext, index: int) -> FloatImage:
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _sheet(cv, ctx)
    _ink(cv, ctx, ctx.rng(index))
    _rod_and_roll(cv, ctx)
    _seal_and_brush(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(ScrollLayer, draw_scroll)])
