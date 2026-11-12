"""A gong hanging in a carved wooden frame, with its mallet (backlog #2).

Original procedural artwork. Geometry is in gong units: the gong face has radius 100 under
``translate(x, y)`` and ``scale(r / 100)``; the frame and mallet are placed around it.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, fill_mask, over
from history_shorts.config import GongLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.textures import gold_leaf

from .registry import WHITE, LayerDrawer, entry

UNITS: Final = 100.0  # gong face radius in gong units

# -- frame ---------------------------------------------------------------------------------
POST_X: Final = 150.0
POST_HALF_WIDTH: Final = 9.0
BEAM_Y: Final = -225.0
BEAM_HALF_HEIGHT: Final = 9.0
BEAM_HALF_LENGTH: Final = 185.0
CURL: Final = 26.0  # how far the beam ends curl up
FOOT_Y: Final = 210.0
FOOT_HALF_WIDTH: Final = 26.0
FOOT_HEIGHT: Final = 14.0
WOOD_LIGHT: Final = "brown_lt"
WOOD_DARK: Final = "brown"
WOOD_OUTLINE: Final = "gold"
WOOD_OUTLINE_WIDTH: Final = 1.6

# -- cords ---------------------------------------------------------------------------------
CORD_COLOR: Final = "vermilion"
CORD_WIDTH: Final = 2.4
CORD_TOP_X: Final = 55.0
CORD_BOTTOM: Final = ((-38.0, -92.0), (38.0, -92.0))

# -- face ----------------------------------------------------------------------------------
RIM_COLOR: Final = "gold_dk"
RIM_WIDTH: Final = 3.0
RINGS: Final = (34.0, 62.0, 90.0)
RING_COLOR: Final = "gold_dk"
RING_WIDTH: Final = 1.2
BOSS_RADIUS: Final = 24.0
BOSS_STOPS: Final = (("gold_lt", 0.0), ("gold", 0.55), ("gold_dk", 1.0))
BOSS_HIGHLIGHT: Final = (-7.0, -8.0)  # radial gradient centre, offset from the boss centre
DOT_RADIUS: Final = 76.0
DOT_COUNT: Final = 24
DOT_SIZE: Final = 1.8

# -- mallet (leaning against the right post) -----------------------------------------------
MALLET_HANDLE: Final = ((112.0, 205.0), (178.0, 40.0))
MALLET_HANDLE_WIDTH: Final = 5.0
MALLET_HEAD: Final = (182.0, 28.0, 16.0, 12.0)  # centre x, y and radii
MALLET_HEAD_COLOR: Final = "vermilion_dk"


def _beam_path(cv: Canvas) -> None:
    top, bottom = BEAM_Y - BEAM_HALF_HEIGHT, BEAM_Y + BEAM_HALF_HEIGHT
    half = BEAM_HALF_LENGTH
    cv.M(-half + 20, bottom).C(-half, bottom, -half - 8, top - CURL * 0.4, -half - 2, top - CURL)
    cv.C(-half + 6, top - CURL * 0.5, -half + 10, top, -half + 30, top)
    cv.L(half - 30, top).C(half - 10, top, half - 6, top - CURL * 0.5, half + 2, top - CURL)
    cv.C(half + 8, top - CURL * 0.4, half, bottom, half - 20, bottom).Z()


def _wood(cv: Canvas, ctx: DrawContext, y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[WOOD_LIGHT], 1), (1, pal[WOOD_DARK], 1)]).fill(keep=True)
    cv.color(pal[WOOD_OUTLINE]).stroke(WOOD_OUTLINE_WIDTH)


def _frame(cv: Canvas, ctx: DrawContext) -> None:
    for side in (-1, 1):
        x = side * POST_X
        cv.rect(x - POST_HALF_WIDTH, BEAM_Y, POST_HALF_WIDTH * 2, FOOT_Y - BEAM_Y)
        _wood(cv, ctx, BEAM_Y, FOOT_Y)
        cv.M(x - FOOT_HALF_WIDTH, FOOT_Y + FOOT_HEIGHT).L(x - POST_HALF_WIDTH - 4, FOOT_Y)
        cv.L(x + POST_HALF_WIDTH + 4, FOOT_Y).L(x + FOOT_HALF_WIDTH, FOOT_Y + FOOT_HEIGHT).Z()
        _wood(cv, ctx, FOOT_Y, FOOT_Y + FOOT_HEIGHT)
    _beam_path(cv)
    _wood(cv, ctx, BEAM_Y - BEAM_HALF_HEIGHT - CURL, BEAM_Y + BEAM_HALF_HEIGHT)
    for (bx, by), top_x in zip(CORD_BOTTOM, (-CORD_TOP_X, CORD_TOP_X), strict=True):
        cv.color(ctx.palette[CORD_COLOR]).M(top_x, BEAM_Y + BEAM_HALF_HEIGHT).L(bx, by)
        cv.stroke(CORD_WIDTH)


def _face(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for radius in RINGS:
        cv.color(pal[RING_COLOR]).ellipse(0, 0, radius, radius).stroke(RING_WIDTH)
    for k in range(DOT_COUNT):
        a = 2 * math.pi * k / DOT_COUNT
        cv.color(pal[RING_COLOR])
        cv.ellipse(DOT_RADIUS * math.cos(a), DOT_RADIUS * math.sin(a), DOT_SIZE, DOT_SIZE).fill()
    hx, hy = BOSS_HIGHLIGHT
    stops = [(offset, pal[key], 1.0) for key, offset in BOSS_STOPS]
    cv.ellipse(0, 0, BOSS_RADIUS, BOSS_RADIUS)
    cv.rgrad(hx, hy, BOSS_RADIUS * 1.3, stops).fill(keep=True)
    cv.color(pal[RIM_COLOR]).stroke(RING_WIDTH)
    cv.color(pal[RIM_COLOR]).ellipse(0, 0, UNITS, UNITS).stroke(RIM_WIDTH)


def _mallet(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    (x0, y0), (x1, y1) = MALLET_HANDLE
    cv.color(pal[WOOD_OUTLINE]).M(x0, y0).L(x1, y1).stroke(MALLET_HANDLE_WIDTH + 2)
    cv.color(pal[WOOD_LIGHT]).M(x0, y0).L(x1, y1).stroke(MALLET_HANDLE_WIDTH)
    cx, cy, rx, ry = MALLET_HEAD
    cv.color(pal[MALLET_HEAD_COLOR]).ellipse(cx, cy, rx, ry).fill(keep=True)
    cv.color(pal[WOOD_OUTLINE]).stroke(WOOD_OUTLINE_WIDTH)


def _local(cv: Canvas, layer: GongLayer) -> None:
    cv.translate(layer.x, layer.y)
    cv.scale(layer.r / UNITS, layer.r / UNITS)


def draw_gong(img: FloatImage, layer: GongLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Frame and cords, then the gold-leaf face masked to its circle, its rings and boss, and
    the mallet in front."""
    back = Canvas(CANVAS_W, CANVAS_H)
    back.save()
    _local(back, layer)
    _frame(back, ctx)
    back.restore()
    img = over(img, back)
    gold = ctx.theme.textures.gold_leaf
    tile = gold.tile if layer.tile is None else layer.tile
    disc = Canvas(CANVAS_W, CANVAS_H)
    disc.color(WHITE).ellipse(layer.x, layer.y, layer.r, layer.r).fill()
    tex = gold_leaf(ctx.rng(index), ctx.palette, tile, gold.worn, width=CANVAS_W, height=CANVAS_H)
    img = fill_mask(img, tex, disc.mask())
    front = Canvas(CANVAS_W, CANVAS_H)
    front.save()
    _local(front, layer)
    _face(front, ctx)
    _mallet(front, ctx)
    front.restore()
    return over(img, front)


DRAWERS: dict[type, LayerDrawer] = dict([entry(GongLayer, draw_gong)])
