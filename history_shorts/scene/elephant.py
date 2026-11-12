"""A war elephant in profile with a saddle cloth and a flag, no rider (backlog #6).

Original procedural artwork. Geometry is in elephant units with the feet on y = 0 and the
head towards +x; it is placed with ``translate(x, y)`` and ``scale(facing * s, s)``, so
mirroring is only ever done by the scale (as for characters).
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import ElephantLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.6
BODY_FILL: Final = ("brown_lt", "brown")  # top-to-bottom
BODY_TOP: Final = -170.0
FAR_LEG_FILL: Final = "hull_dk"
EAR_FILL: Final = ("brown", "deep_warm")
TUSK_FILL: Final = "egg"
NAIL_FILL: Final = "egg_tone"
EYE_COLOR: Final = "black"
EYE_WIDTH: Final = 1.6

# legs: (x left, width), far pair first; all run from LEG_TOP to the ground
FAR_LEGS: Final = ((-88.0, 30.0), (22.0, 30.0))
NEAR_LEGS: Final = ((-112.0, 34.0), (46.0, 34.0))
LEG_TOP: Final = -70.0
NAIL_RADIUS: Final = 4.0

CLOTH_FILL: Final = "vermilion"
CLOTH_TRIM: Final = "gold"
CLOTH_DOT: Final = "gold_lt"
CLOTH_DOTS: Final = ((-48.0, -118.0), (-18.0, -112.0), (12.0, -118.0))
FRINGE_COUNT: Final = 9

POLE: Final = ((-18.0, -160.0), (-18.0, -300.0))
POLE_COLOR: Final = "gold_dk"
POLE_WIDTH: Final = 3.0
FLAG_FILL: Final = "vermilion"
FLAG_EMBLEM: Final = (16.0, -276.0, 7.0)  # circle on the flag: x, y, r

TAIL: Final = ((-124.0, -112.0), (-140.0, -80.0), (-136.0, -50.0))
TAIL_WIDTH: Final = 2.5


def _body_path(cv: Canvas) -> None:
    cv.M(-122, -60).C(-140, -130, -80, -172, -10, -168)
    cv.C(45, -165, 82, -138, 86, -96).C(88, -70, 74, -58, 60, -56).L(-110, -56).Z()


def _head_path(cv: Canvas) -> None:
    cv.M(52, -128).C(62, -186, 128, -192, 134, -142).C(137, -118, 126, -104, 118, -98)
    cv.C(138, -70, 144, -40, 154, -16).C(158, -4, 148, 2, 142, -8)
    cv.C(134, -34, 116, -62, 96, -86).C(80, -84, 60, -96, 52, -128).Z()


def _ear_path(cv: Canvas) -> None:
    cv.M(58, -162).C(18, -168, 6, -112, 26, -86).C(42, -74, 66, -88, 72, -112)
    cv.C(74, -132, 70, -152, 58, -162).Z()


def _fill(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _legs(cv: Canvas, ctx: DrawContext, legs: tuple[tuple[float, float], ...], far: bool) -> None:
    pal = ctx.palette
    for x, w in legs:
        cv.M(x, LEG_TOP).L(x + w, LEG_TOP).L(x + w + 2, 0).L(x - 2, 0).Z()
        if far:
            cv.color(pal[FAR_LEG_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
        else:
            _fill(cv, ctx, BODY_FILL, LEG_TOP, 0)
        for k in range(3):
            nx = x + w * (k + 1) / 4
            cv.color(pal[NAIL_FILL]).ellipse(nx, -3, NAIL_RADIUS, NAIL_RADIUS * 0.7).fill()


def _cloth(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cv.M(-72, -158).C(-40, -168, 10, -168, 40, -150).L(36, -92)
    step = 108 / FRINGE_COUNT
    for k in range(FRINGE_COUNT):
        x = 36 - (k + 0.5) * step
        cv.L(x, -82).L(36 - (k + 1) * step, -92)
    cv.Z().color(pal[CLOTH_FILL]).fill(keep=True).color(pal[CLOTH_TRIM]).stroke(OUTLINE_WIDTH)
    for x, y in CLOTH_DOTS:
        cv.color(pal[CLOTH_DOT]).ellipse(x, y, 6, 6).fill(keep=True)
        cv.color(pal[CLOTH_TRIM]).stroke(1.0)


def _flag(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    (x0, y0), (x1, y1) = POLE
    cv.color(pal[POLE_COLOR]).M(x0, y0).L(x1, y1).stroke(POLE_WIDTH)
    cv.color(pal[OUTLINE]).ellipse(x1, y1 - 4, 4.5, 4.5).fill()
    cv.M(x1, y1 + 2).C(20, y1 - 6, 44, y1 + 10, 70, y1 + 4).L(56, y1 + 24).L(70, y1 + 44)
    cv.C(44, y1 + 48, 20, y1 + 36, x1, y1 + 46).Z()
    cv.color(pal[FLAG_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    fx, fy, fr = FLAG_EMBLEM
    cv.color(pal[OUTLINE]).ellipse(fx, fy, fr, fr).stroke(1.2)


def _face(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cv.M(112, -100).C(130, -96, 146, -100, 156, -118).C(150, -100, 134, -88, 110, -90).Z()
    cv.color(pal[TUSK_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(1.0)
    cv.M(102, -146).C(106, -142, 112, -142, 116, -146)  # closed, downcast eye
    cv.color(pal[EYE_COLOR]).stroke(EYE_WIDTH)
    (ax, ay), (bx, by), (cx, cy) = TAIL
    cv.color(pal[OUTLINE]).M(ax, ay).C(bx, by, bx, by, cx, cy).stroke(TAIL_WIDTH)
    for k in range(5):
        a = math.radians(70 + k * 10)
        cv.M(cx, cy).L(cx + 12 * math.cos(a), cy + 12 * math.sin(a))
    cv.color(pal[OUTLINE]).stroke(1.2)


def draw_elephant(
    img: FloatImage, layer: ElephantLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Far legs, tail, body, near legs, head and ear, saddle cloth, flag, tusk and eye."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.facing * layer.scale, layer.scale)
    _legs(cv, ctx, FAR_LEGS, far=True)
    _body_path(cv)
    _fill(cv, ctx, BODY_FILL, BODY_TOP, LEG_TOP)
    _legs(cv, ctx, NEAR_LEGS, far=False)
    _head_path(cv)
    _fill(cv, ctx, BODY_FILL, BODY_TOP, 0)
    _ear_path(cv)
    _fill(cv, ctx, EAR_FILL, -162, -80)
    if layer.flag:
        _flag(cv, ctx)
    _cloth(cv, ctx)
    _face(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(ElephantLayer, draw_elephant)])
