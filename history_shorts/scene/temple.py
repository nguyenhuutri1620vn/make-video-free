"""A temple gate (tam quan) with incense burners (backlog #3).

Original procedural artwork, not a drawing of any real temple. Geometry is in temple units
under ``translate(x, y)`` and ``scale(scale)``: ``y`` is the ground line, the gate is about
420 units wide and 250 units tall.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import TempleLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4
OUTLINE_THIN: Final = 0.9

# -- platform: (half width, top y) per tier, bottom tier first -------------------------------
STEPS: Final = ((215.0, -10.0), (195.0, -22.0))
STEP_FILL: Final = "egg_tone"
STEP_LINE: Final = "gold_dk"

PILLAR_FILL: Final = ("vermilion", "vermilion_dk")  # left-to-right gradient
PILLAR_HALF_WIDTH: Final = 7.0
OPENING_FILL: Final = "black"
PANEL_FILL: Final = "deep"
WINDOW_FILL: Final = "gold_dk"
WINDOW_RADIUS: Final = 14.0
ROOF_FILL: Final = ("vermilion", "vermilion_dk")  # top-to-bottom gradient
ROOF_CURL: Final = (18.0, 22.0)  # eave tip: out, up


@dataclass(frozen=True, slots=True)
class Bay:
    """One bay: centre x, pillar half spacing, top of the pillars, and its roof."""

    cx: float
    half: float
    top: float
    roof_half: float
    ridge: float


SIDE_BAYS: Final = (Bay(-130.0, 50.0, -120.0, 72.0, -150.0), Bay(130.0, 50.0, -120.0, 72.0, -150.0))
CENTRE_BAY: Final = Bay(0.0, 55.0, -170.0, 100.0, -205.0)
UPPER_ROOF: Final = Bay(0.0, 40.0, -210.0, 74.0, -245.0)  # second tier of the centre roof
ARCH_RISE: Final = 26.0
RIDGE_PEARL: Final = 9.0
RIDGE_CURL: Final = 12.0

BURNER_X: Final = (-150.0, 150.0)
BURNER_FILL: Final = "gold_dk"
SMOKE_COLOR: Final = "gold_lt"
SMOKE_ALPHA: Final = 0.45
SMOKE_WIDTH: Final = 1.5
SMOKE_HEIGHT: Final = 110.0


def _roof_path(cv: Canvas, cx: float, half: float, eave: float, ridge: float) -> None:
    out, up = ROOF_CURL
    top_half = half * 0.7
    cv.M(cx - half - out, eave - up)
    cv.C(cx - half - 5, eave + 2, cx - half, eave + 6, cx - half + 10, eave + 6)
    cv.L(cx + half - 10, eave + 6)
    cv.C(cx + half, eave + 6, cx + half + 5, eave + 2, cx + half + out, eave - up)
    cv.C(cx + half + 5, eave - 12, cx + top_half * 1.15, ridge + 6, cx + top_half, ridge)
    cv.L(cx - top_half, ridge)
    cv.C(cx - top_half * 1.15, ridge + 6, cx - half - 5, eave - 12, cx - half - out, eave - up)
    cv.Z()


def _paint(cv: Canvas, ctx: DrawContext, fill: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[fill[0]], 1), (1, pal[fill[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _roof(cv: Canvas, ctx: DrawContext, bay: Bay) -> None:
    _roof_path(cv, bay.cx, bay.roof_half, bay.top, bay.ridge)
    _paint(cv, ctx, ROOF_FILL, bay.ridge, bay.top + 6)


def _pillars(cv: Canvas, ctx: DrawContext, bay: Bay) -> None:
    base = STEPS[-1][1]
    for side in (-1, 1):
        x = bay.cx + side * bay.half
        cv.rect(x - PILLAR_HALF_WIDTH, bay.top, PILLAR_HALF_WIDTH * 2, base - bay.top)
        _paint(cv, ctx, PILLAR_FILL, bay.top, base)


def _side_bay(cv: Canvas, ctx: DrawContext, bay: Bay) -> None:
    pal = ctx.palette
    base = STEPS[-1][1]
    cv.color(pal[PANEL_FILL]).rect(bay.cx - bay.half, bay.top, bay.half * 2, base - bay.top)
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_THIN)
    window_y = (bay.top + base) / 2
    cv.color(pal[WINDOW_FILL]).ellipse(bay.cx, window_y, WINDOW_RADIUS, WINDOW_RADIUS)
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_THIN)
    _pillars(cv, ctx, bay)
    _roof(cv, ctx, bay)


def _centre_bay(cv: Canvas, ctx: DrawContext) -> None:
    pal, bay = ctx.palette, CENTRE_BAY
    base = STEPS[-1][1]
    left, right = bay.cx - bay.half, bay.cx + bay.half
    spring = bay.top + ARCH_RISE * 2
    cv.M(left, base).L(left, spring).C(left, bay.top + 4, right, bay.top + 4, right, spring)
    cv.L(right, base).Z()
    cv.color(pal[OPENING_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_THIN)
    _pillars(cv, ctx, bay)
    _roof(cv, ctx, bay)
    _roof(cv, ctx, UPPER_ROOF)
    ridge = UPPER_ROOF.ridge
    cv.color(pal[OUTLINE]).ellipse(0, ridge - RIDGE_PEARL, RIDGE_PEARL, RIDGE_PEARL).fill()
    for side in (-1, 1):
        x = side * UPPER_ROOF.roof_half * 0.7
        cv.M(x, ridge).C(x + side * RIDGE_CURL, ridge - RIDGE_CURL, x, ridge - RIDGE_CURL * 2,
                         x - side * 4, ridge - RIDGE_CURL * 1.2)  # fmt: skip
        cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH * 1.4)


def _steps(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    bottom = 0.0
    for half, top in STEPS:
        cv.color(pal[STEP_FILL]).rect(-half, top, half * 2, bottom - top).fill(keep=True)
        cv.color(pal[STEP_LINE]).stroke(OUTLINE_THIN)
        bottom = top


def _burners(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x in BURNER_X:
        cv.M(x - 16, -2).L(x - 20, -26).C(x - 20, -34, x + 20, -34, x + 20, -26).L(x + 16, -2)
        cv.Z().color(pal[BURNER_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_THIN)
        cv.M(x - 26, -30).L(x + 26, -30).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH * 1.6)
        for k, dx in enumerate((-6.0, 6.0)):
            sway = 10.0 if k else -10.0
            top = -34 - SMOKE_HEIGHT
            cv.M(x + dx, -34).C(x + dx + sway, -64, x + dx - sway, -94, x + dx + sway * 0.6, top)
            cv.color(pal[SMOKE_COLOR], SMOKE_ALPHA).stroke(SMOKE_WIDTH)


def draw_temple(img: FloatImage, layer: TempleLayer, ctx: DrawContext, index: int) -> FloatImage:
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _steps(cv, ctx)
    for bay in SIDE_BAYS:
        _side_bay(cv, ctx, bay)
    _centre_bay(cv, ctx)
    if layer.incense:
        _burners(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(TempleLayer, draw_temple)])
