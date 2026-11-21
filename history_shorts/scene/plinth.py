"""An empty stone plinth under a shaft of light, dust motes drifting in the beam.

Original procedural artwork for "what is gone": the stepped plinth carries nothing but four
faint hoof marks on its top face. The light shaft fades to alpha 0 at its top, so it seems to
fall from the dark above. Geometry is in plinth units with the floor on y = 0 under
``translate(x, y)`` and ``scale(scale)``; the plinth is 300 units wide and 186 tall, the beam
starts 540 units above the floor.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import PlinthLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.3
STONE_FILL: Final = ("egg_tone", "brown")
TOP_FACE_FILL: Final = "egg_tone"

BASE: Final = (-150.0, -40.0, 300.0, 40.0)  # x, y, w, h
BODY: Final = (-110.0, -150.0, 220.0, 110.0)
CAP: Final = (-130.0, -170.0, 260.0, 20.0)
TOP_FACE: Final = (130.0, 110.0, -170.0, -184.0)  # front half width, back half width, y, back y
PANEL_INSET: Final = 14.0
PANEL_COLOR: Final = "gold_dk"
PANEL_WIDTH: Final = 0.9

HOOF_MARKS: Final = (-62.0, -38.0, 38.0, 62.0)
HOOF: Final = (-177.0, 7.0, 2.5)  # y, rx, ry
HOOF_COLOR: Final = "shadow"
HOOF_ALPHA: Final = 0.45

BEAM_TOP: Final = (-540.0, 40.0)  # y, half width
BEAM_BOTTOM: Final = (-176.0, 150.0)
BEAM_COLOR: Final = "gold_lt"
BEAM_ALPHA: Final = 0.26
POOL: Final = (0.0, -177.0, 150.0, 22.0)  # light pool on the top face: cx, cy, rx, ry
POOL_ALPHA: Final = 0.35

MOTES: Final = 26
MOTE_R: Final = (1.2, 2.6)
MOTE_COLOR: Final = "gold_lt"
MOTE_ALPHA: Final = (0.35, 0.8)


def _beam_path(cv: Canvas) -> None:
    (ty, th), (by, bh) = BEAM_TOP, BEAM_BOTTOM
    cv.M(-th, ty).L(th, ty).L(bh, by).L(-bh, by).Z()


def _beam(cv: Canvas, ctx: DrawContext, index: int) -> None:
    glow = ctx.palette[BEAM_COLOR]
    _beam_path(cv)
    cv.vgrad(BEAM_TOP[0], BEAM_BOTTOM[0], [(0, glow, 0.0), (1, glow, BEAM_ALPHA)]).fill()
    rng = ctx.rng(index)
    (ty, th), (by, bh) = BEAM_TOP, BEAM_BOTTOM
    for _ in range(MOTES):
        t = float(rng.uniform(0.15, 0.95))
        y = ty + (by - ty) * t
        half = th + (bh - th) * t
        x = float(rng.uniform(-half * 0.8, half * 0.8))
        r = float(rng.uniform(*MOTE_R))
        alpha = float(rng.uniform(*MOTE_ALPHA)) * t
        cv.ellipse(x, y, r, r).color(glow, alpha).fill()


def _block(cv: Canvas, ctx: DrawContext, box: tuple[float, float, float, float]) -> None:
    pal = ctx.palette
    x, y, w, h = box
    cv.rect(x, y, w, h)
    cv.vgrad(y, y + h, [(0, pal[STONE_FILL[0]], 1), (1, pal[STONE_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _stone(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    _block(cv, ctx, BASE)
    _block(cv, ctx, BODY)
    x, y, w, h = BODY
    inset = PANEL_INSET
    cv.rect(x + inset, y + inset, w - 2 * inset, h - 2 * inset)
    cv.color(pal[PANEL_COLOR]).stroke(PANEL_WIDTH)
    front, back, fy, by = TOP_FACE
    cv.M(-front, fy).L(-back, by).L(back, by).L(front, fy).Z()
    cv.color(pal[TOP_FACE_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    _block(cv, ctx, CAP)


def _top(cv: Canvas, ctx: DrawContext, hooves: bool) -> None:
    pal = ctx.palette
    cx, cy, rx, ry = POOL
    glow = pal[BEAM_COLOR]
    cv.ellipse(cx, cy, rx, ry).rgrad(cx, cy, rx, [(0, glow, POOL_ALPHA), (1, glow, 0.0)]).fill()
    if not hooves:
        return
    y, rx, ry = HOOF
    for x in HOOF_MARKS:
        cv.ellipse(x, y, rx, ry).color(pal[HOOF_COLOR], HOOF_ALPHA).fill()


def draw_plinth(img: FloatImage, layer: PlinthLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Light shaft and motes, the stepped plinth, then the light pool and hoof marks on top."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _beam(cv, ctx, index)
    _stone(cv, ctx)
    _top(cv, ctx, layer.hooves)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(PlinthLayer, draw_plinth)])
