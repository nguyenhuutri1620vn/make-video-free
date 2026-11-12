"""A large sailing boat with ribbed sails on the water, no crew (backlog #11).

Original procedural artwork. Geometry is in boat units with the waterline on y = 0 and the
bow towards +x; it is placed with ``translate(x, y)`` and ``scale(facing * s, s)``, so
mirroring is only ever done by the scale. The boat is about 330 units long and 360 tall.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import SailBoatLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

Point = tuple[float, float]

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.5
THIN: Final = 0.9

HULL_FILL: Final = ("brown", "hull_dk")
HULL_DECK_Y: Final = -34.0
PLANKS: Final = (-20.0, -9.0)  # plank line heights
PLANK_COLOR: Final = "gold_dk"
EYE: Final = (128.0, -32.0, 6.0)  # bow eye: x, y, r
EYE_FILL: Final = ("egg", "black")

MAST_COLOR: Final = "brown_lt"
MAST_WIDTH: Final = 5.0
MASTS: Final = ((20.0, -330.0), (-104.0, -215.0))  # x, top y; both stand on the deck

# sails as quads: top-back, top-front, bottom-front, bottom-back
SAILS: Final[tuple[tuple[Point, Point, Point, Point], ...]] = (
    ((-14.0, -300.0), (118.0, -322.0), (130.0, -56.0), (-6.0, -48.0)),
    ((-150.0, -196.0), (-62.0, -208.0), (-56.0, -52.0), (-142.0, -48.0)),
)
SAIL_FILL: Final = ("vermilion", "vermilion_dk")
BATTEN_COLOR: Final = "gold"
BATTEN_STEP: Final = 36.0
BATTEN_SAG: Final = 6.0

PENNANT: Final = 28.0
PENNANT_FILL: Final = "gold_lt"

WAVE_COLOR: Final = "gold"
WAVES: Final[tuple[Point, ...]] = ((-180.0, 10.0), (-110.0, 18.0), (60.0, 16.0), (150.0, 8.0))
WAVE_SIZE: Final = 26.0


def _grad(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _hull_path(cv: Canvas) -> None:
    cv.M(-168, -62).C(-150, -40, -120, HULL_DECK_Y, -90, HULL_DECK_Y).L(110, HULL_DECK_Y)
    cv.C(140, HULL_DECK_Y, 160, -50, 176, -70).C(170, -30, 140, 8, 100, 10)
    cv.L(-110, 10).C(-150, 8, -166, -20, -168, -62).Z()


def _hull(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    _hull_path(cv)
    _grad(cv, ctx, HULL_FILL, -70, 10)
    for y in PLANKS:
        cv.M(-140, y).C(-60, y + 4, 60, y + 4, 140, y - 6)
    cv.color(pal[PLANK_COLOR]).stroke(THIN)
    x, y, r = EYE
    cv.ellipse(x, y, r * 1.4, r)
    _grad(cv, ctx, EYE_FILL, y - r, y + r)


def _lerp(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _sail(cv: Canvas, ctx: DrawContext, quad: tuple[Point, Point, Point, Point]) -> None:
    tb, tf, bf, bb = quad
    cv.M(*tb).L(*tf).C(tf[0] + 16, (tf[1] + bf[1]) / 2, bf[0] + 10, bf[1] - 40, *bf)
    cv.L(*bb).Z()
    _grad(cv, ctx, SAIL_FILL, tf[1], bb[1])
    height = bb[1] - tb[1]
    count = int(height // BATTEN_STEP)
    for k in range(1, count + 1):
        t = k / (count + 1)
        (x0, y0), (x1, y1) = _lerp(tb, bb, t), _lerp(tf, bf, t)
        cv.M(x0, y0).C(x0 + (x1 - x0) / 3, y0 + BATTEN_SAG, x0 + 2 * (x1 - x0) / 3,
                       y1 + BATTEN_SAG, x1, y1)  # fmt: skip
    cv.color(ctx.palette[BATTEN_COLOR]).stroke(THIN * 1.3)


def _rig(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x, top in MASTS:
        cv.color(pal[OUTLINE]).M(x, HULL_DECK_Y).L(x, top).stroke(MAST_WIDTH + 2)
        cv.color(pal[MAST_COLOR]).M(x, HULL_DECK_Y).L(x, top).stroke(MAST_WIDTH)
    for quad in SAILS:
        _sail(cv, ctx, quad)
    x, top = MASTS[0]
    cv.M(x, top).L(x - PENNANT, top + PENNANT * 0.25).L(x, top + PENNANT * 0.5).Z()
    cv.color(pal[PENNANT_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(THIN)


def _waves(cv: Canvas, ctx: DrawContext) -> None:
    s = WAVE_SIZE
    for x, y in WAVES:
        cv.M(x - s, y).C(x - s / 2, y - s / 2, x, y - s / 2, x, y)
        cv.C(x, y - s / 2, x + s / 2, y - s / 2, x + s, y)
    cv.color(ctx.palette[WAVE_COLOR]).stroke(1.4)


def draw_sail_boat(
    img: FloatImage, layer: SailBoatLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Masts and ribbed sails, then the hull in front, then wave strokes at the waterline."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.facing * layer.scale, layer.scale)
    _rig(cv, ctx)
    _hull(cv, ctx)
    _waves(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(SailBoatLayer, draw_sail_boat)])
