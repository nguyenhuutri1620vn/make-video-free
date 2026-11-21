"""A three-piece stone mould for bronze arrowheads, with a top-view key (Cổ Loa video).

Original procedural artwork, a schematic rather than a copy of a museum piece. Front view:
three stone pieces (mang) stand side by side, slightly apart; the middle one shows the
arrowhead cavity, tip down, with the pouring funnel at the top. Above them a top-view key
shows the three pieces closing into one cylinder around the three-bladed cavity.

Geometry is in mould units with the floor on y = 0 under ``translate(x, y)`` and
``scale(scale)``: the pieces span 420 x 330 units, the key's centre is 450 units up.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import MouldLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .arrowheads import TIP_Y, outline_path
from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4
STONE_FILL: Final = ("egg_tone", "brown_lt")
SIDE_FILL: Final = ("brown_lt", "brown")
CAVITY_FILL: Final = ("egg_gap", "shadow")
CAVITY_RIM: Final = "gold_dk"

PIECE_W: Final = 124.0
PIECE_H: Final = 330.0
PIECE_GAP: Final = 24.0
PIECE_ROUND: Final = 16.0  # corner radius at the top
SHADOW: Final = (0.0, -4.0, 250.0, 16.0, 0.6)  # cx, cy, rx, ry, alpha
SHADOW_COLOR: Final = "shadow"

CAVITY_SCALE: Final = 0.86
CAVITY_TOP: Final = -300.0  # where the tang end of the cavity sits (tip points down)
FUNNEL: Final = (22.0, 6.0, -PIECE_H, -300.0)  # top half width, bottom half width, top y, low y
GROOVE_HALF: Final = 6.0  # the half-blade grooves on the side pieces
BAND_YS: Final = (-250.0, -90.0)  # cord bands across each piece
BAND_COLOR: Final = "gold_dk"
BAND_WIDTH: Final = 3.0

KEY: Final = (0.0, -455.0, 82.0)  # centre x, centre y, radius
KEY_SPREAD: Final = 10.0  # how far each sector is pushed out from the centre
KEY_SEAMS: Final = (-90.0, 30.0, 150.0)  # seam angles in degrees (blades lie along them)
KEY_BLADE: Final = 30.0  # length of each blade of the cavity
KEY_STEPS: Final = 24
KEY_RING_COLOR: Final = "gold_lt"
KEY_RING_ALPHA: Final = 0.35


def _piece_path(cv: Canvas, x0: float) -> None:
    r = PIECE_ROUND
    top = -PIECE_H
    cv.M(x0, 0.0).L(x0, top + r).C(x0, top, x0, top, x0 + r, top).L(x0 + PIECE_W - r, top)
    cv.C(x0 + PIECE_W, top, x0 + PIECE_W, top, x0 + PIECE_W, top + r).L(x0 + PIECE_W, 0.0).Z()


def _piece(cv: Canvas, ctx: DrawContext, x0: float, fill: tuple[str, str]) -> None:
    pal = ctx.palette
    _piece_path(cv, x0)
    cv.vgrad(-PIECE_H, 0.0, [(0, pal[fill[0]], 1), (1, pal[fill[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for y in BAND_YS:
        cv.M(x0, y).L(x0 + PIECE_W, y).color(pal[BAND_COLOR], 0.8).stroke(BAND_WIDTH)


def _cavity(cv: Canvas, ctx: DrawContext) -> None:
    """The arrowhead cavity, tip down, and the funnel it is poured through."""
    pal = ctx.palette
    top_half, low_half, fy0, fy1 = FUNNEL
    cv.M(-top_half, fy0).L(top_half, fy0).L(low_half, fy1).L(-low_half, fy1).Z()
    cv.vgrad(fy0, fy1, [(0, pal[CAVITY_FILL[1]], 1), (1, pal[CAVITY_FILL[0]], 1)]).fill()
    cv.save()
    cv.translate(0.0, CAVITY_TOP)
    cv.scale(CAVITY_SCALE, -CAVITY_SCALE)  # tip points down
    outline_path(cv)
    cv.vgrad(0.0, TIP_Y, [(0, pal[CAVITY_FILL[1]], 1), (1, pal[CAVITY_FILL[0]], 1)])
    cv.fill(keep=True).color(pal[CAVITY_RIM]).stroke(OUTLINE_WIDTH)
    cv.restore()


def _groove(cv: Canvas, ctx: DrawContext, cx: float) -> None:
    """A half-blade groove on a side piece: the edge of the cavity it shares."""
    pal = ctx.palette
    low = CAVITY_TOP - TIP_Y * CAVITY_SCALE
    cv.M(cx - GROOVE_HALF, CAVITY_TOP).L(cx + GROOVE_HALF, CAVITY_TOP).L(cx, low).Z()
    cv.color(pal[CAVITY_FILL[0]], 0.85).fill()


def _sector(cv: Canvas, a0: float, a1: float, r: float, push: float) -> None:
    mid = (a0 + a1) / 2
    ox, oy = push * math.cos(mid), push * math.sin(mid)
    cv.M(ox, oy)
    for k in range(KEY_STEPS + 1):
        a = a0 + (a1 - a0) * k / KEY_STEPS
        cv.L(ox + r * math.cos(a), oy + r * math.sin(a))
    cv.Z()


def _key(cv: Canvas, ctx: DrawContext) -> None:
    """Top view: three sectors pushed slightly apart around the three-bladed cavity."""
    pal = ctx.palette
    cx, cy, r = KEY
    cv.save()
    cv.translate(cx, cy)
    cv.ellipse(0.0, 0.0, r + KEY_SPREAD + 14.0, r + KEY_SPREAD + 14.0)
    cv.color(pal[KEY_RING_COLOR], KEY_RING_ALPHA).stroke(1.0)
    seams = [math.radians(a) for a in KEY_SEAMS]
    for k, a0 in enumerate(seams):
        a1 = seams[(k + 1) % len(seams)]
        if a1 <= a0:
            a1 += 2 * math.pi
        _sector(cv, a0, a1, r, KEY_SPREAD)
        cv.vgrad(-r, r, [(0, pal[STONE_FILL[0]], 1), (1, pal[STONE_FILL[1]], 1)])
        cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for a in seams:
        cv.M(0.0, 0.0).L(KEY_BLADE * math.cos(a), KEY_BLADE * math.sin(a))
    cv.color(pal[CAVITY_FILL[1]]).stroke(5.0)
    cv.restore()


def draw_mould(img: FloatImage, layer: MouldLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Shadow, the two side pieces with grooves, the middle piece with its cavity, the key."""
    del index  # no randomness: the mould is a fixed schematic
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    cx, cy, rx, ry, alpha = SHADOW
    shade = ctx.palette[SHADOW_COLOR]
    cv.save()
    cv.translate(cx, cy)
    cv.scale(1.0, ry / rx)
    cv.ellipse(0.0, 0.0, rx, rx).rgrad(0.0, 0.0, rx, [(0, shade, alpha), (1, shade, 0.0)]).fill()
    cv.restore()
    step = PIECE_W + PIECE_GAP
    for x0 in (-step - PIECE_W / 2, step - PIECE_W / 2):
        _piece(cv, ctx, x0, SIDE_FILL)
        _groove(cv, ctx, x0 + PIECE_W / 2)
    _piece(cv, ctx, -PIECE_W / 2, STONE_FILL)
    _cavity(cv, ctx)
    if layer.key:
        _key(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(MouldLayer, draw_mould)])
