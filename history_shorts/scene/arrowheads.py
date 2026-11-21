"""Three-bladed bronze arrowheads of the Cổ Loa type (Cổ Loa video).

Original procedural artwork, not traced from a photograph: a leaf-shaped head with backward
barbs, a raised middle blade facing the viewer, and a long tang. A *polished* arrowhead is
bright with a sheen line; a *raw* one is duller and keeps thin casting fins (via) along its
edges, as if just out of the mould.

Arrangements under ``translate(x, y)`` and ``scale(scale)``, floor on y = 0:

* ``single``: one large arrowhead, tilted, above its shadow in a pool of light (about
  480 x 480 units with its light pool);
* ``pair``: a polished arrowhead (left) and a raw one (right) standing upright (about
  300 x 290 units);
* ``quarter``: four upright arrowheads, the first polished and three raw (about
  440 x 260 units);
* ``heap``: a mound of small arrowheads, about one in four polished (about 460 x 200 units).

One arrowhead is 270 units long in its own frame: tip at y = -270, tang end at y = 0.
"""

from __future__ import annotations

import math
from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import ArrowheadsLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

# --- one arrowhead, in its own frame ----------------------------------------------------------
TIP_Y: Final = -270.0
SHOULDER: Final = (40.0, -150.0)  # half width, y of the widest point
BARB: Final = (36.0, -92.0)  # half width, y of the barb tips
NOTCH: Final = (9.0, -112.0)  # where the barb meets the tang
TANG_TOP: Final = 8.0  # tang half width at the notch
TANG_END: Final = (4.0, 0.0)  # tang half width at its end, y
RIDGE_HALF: Final = 7.0  # half width of the middle blade facing the viewer
RIDGE_FOOT: Final = -104.0

OUTLINE: Final = "black"
OUTLINE_WIDTH: Final = 1.4
POLISHED_FILL: Final = ("gold_lt", "gold", "gold_dk")
RAW_FILL: Final = ("gold", "gold_dk", "brown")
RIDGE_COLOR: Final = "gold_lt"
RIDGE_ALPHA: Final = (0.85, 0.45)  # polished, raw
SHEEN_COLOR: Final = "sheen"
SHEEN_ALPHA: Final = 0.7
SHEEN_WIDTH: Final = 2.2
PATINA_COLOR: Final = "jade"
PATINA_ALPHA: Final = 0.35
PATINA_SPOTS: Final = (
    (-14.0, -150.0, 7.0, 10.0),
    (12.0, -196.0, 5.0, 8.0),
    (-3.0, -58.0, 3.0, 9.0),
)

FIN_COLOR: Final = "gold_dk"
FIN_ALPHA: Final = 0.9
FIN_TEETH: Final = 9  # jagged teeth per blade edge
FIN_DEPTH: Final = (2.5, 7.0)  # how far a fin sticks out
TANG_FINS: Final = 4

# --- arrangements ------------------------------------------------------------------------------
GROUND_COLOR: Final = "shadow"
POOL_COLOR: Final = "gold_lt"

SINGLE_TILT: Final = math.radians(38.0)  # tip to the upper right
SINGLE_AT: Final = (0.0, -170.0)  # where the middle of the arrowhead sits
SINGLE_POOL: Final = (0.0, -170.0, 240.0, 0.32)  # cx, cy, r, alpha
SINGLE_SHADOW: Final = (0.0, -12.0, 170.0, 22.0, 0.6)  # cx, cy, rx, ry, alpha

PAIR_X: Final = 80.0  # each arrowhead stands this far from the centre
PAIR_LIFT: Final = -14.0  # tang end height above the floor
QUARTER_X: Final = (-195.0, -65.0, 65.0, 195.0)  # first polished, the other three raw
QUARTER_SCALE: Final = 0.9
PAIR_SHADOW: Final = (0.0, -6.0, 50.0, 7.0, 0.55)

HEAP_COUNT: Final = 90
HEAP_SIZE: Final = (230.0, 170.0)  # half width, height of the mound
HEAP_SCALE: Final = (0.34, 0.46)
HEAP_POLISHED: Final = 0.25  # share of polished arrowheads
HEAP_SHADOW: Final = (0.0, -8.0, 260.0, 30.0, 0.7)
HEAP_SOIL: Final = ("deep_warm", "egg_gap")  # mound top, mound foot


def outline_path(cv: Canvas) -> None:
    sw, sy = SHOULDER
    bw, by = BARB
    nw, ny = NOTCH
    tw, ty = TANG_END
    cv.M(0.0, TIP_Y)
    cv.C(sw * 0.45, TIP_Y + 40.0, sw, sy - 40.0, sw, sy)
    cv.L(bw, by).L(nw, ny).L(TANG_TOP, ny).L(tw, ty).L(-tw, ty).L(-TANG_TOP, ny).L(-nw, ny)
    cv.L(-bw, by).L(-sw, sy)
    cv.C(-sw, sy - 40.0, -sw * 0.45, TIP_Y + 40.0, 0.0, TIP_Y).Z()


def _ridge_path(cv: Canvas) -> None:
    cv.M(0.0, TIP_Y + 6.0).L(RIDGE_HALF, SHOULDER[1]).L(RIDGE_HALF * 0.6, RIDGE_FOOT)
    cv.L(-RIDGE_HALF * 0.6, RIDGE_FOOT).L(-RIDGE_HALF, SHOULDER[1]).Z()


def _edge_points(side: float) -> list[tuple[float, float]]:
    """Points along one blade edge, tip to barb, for the casting fins."""
    sw, sy = SHOULDER
    bw, by = BARB
    pts: list[tuple[float, float]] = []
    for k in range(FIN_TEETH):
        t = (k + 0.5) / FIN_TEETH
        if t < 0.75:  # the curved edge from the tip to the shoulder
            u = t / 0.75
            x = sw * math.sin(u * math.pi / 2) ** 0.8
            y = TIP_Y + (sy - TIP_Y) * u
        else:  # the straight edge down to the barb
            u = (t - 0.75) / 0.25
            x = sw + (bw - sw) * u
            y = sy + (by - sy) * u
        pts.append((side * x, y))
    return pts


def _fins(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    """Thin jagged casting fins along both blade edges and the tang."""
    color = ctx.palette[FIN_COLOR]
    for side in (-1.0, 1.0):
        for x, y in _edge_points(side):
            depth = float(rng.uniform(*FIN_DEPTH))
            half = float(rng.uniform(4.0, 8.0))
            cv.M(x, y - half).L(x + side * depth, y + float(rng.uniform(-2.0, 2.0)))
            cv.L(x, y + half).Z()
        for k in range(TANG_FINS):
            y = NOTCH[1] + (TANG_END[1] - NOTCH[1]) * (k + 0.5) / TANG_FINS
            x = side * (TANG_TOP + (TANG_END[0] - TANG_TOP) * (k + 0.5) / TANG_FINS)
            depth = float(rng.uniform(1.5, 4.0))
            cv.M(x, y - 5.0).L(x + side * depth, y).L(x, y + 5.0).Z()
    cv.color(color, FIN_ALPHA).fill()


def draw_one(cv: Canvas, ctx: DrawContext, rng: Generator, *, polished: bool) -> None:
    """One arrowhead in its own frame (tip up at y = -270, tang end at y = 0)."""
    pal = ctx.palette
    if not polished:
        _fins(cv, ctx, rng)
    top, mid, low = POLISHED_FILL if polished else RAW_FILL
    outline_path(cv)
    cv.vgrad(TIP_Y, 0.0, [(0, pal[top], 1), (0.5, pal[mid], 1), (1, pal[low], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    _ridge_path(cv)
    cv.color(pal[RIDGE_COLOR], RIDGE_ALPHA[0] if polished else RIDGE_ALPHA[1]).fill()
    cv.M(0.0, TIP_Y + 4.0).L(0.0, RIDGE_FOOT).color(pal[OUTLINE], 0.6).stroke(0.8)
    if polished:
        sw, sy = SHOULDER
        cv.M(-4.0, TIP_Y + 16.0).C(-sw * 0.4, TIP_Y + 60.0, -sw * 0.8, sy - 30.0, -sw * 0.8, sy)
        cv.color(pal[SHEEN_COLOR], SHEEN_ALPHA).stroke(SHEEN_WIDTH)
    else:
        for cx, cy, rx, ry in PATINA_SPOTS:
            cv.ellipse(cx, cy, rx, ry).color(pal[PATINA_COLOR], PATINA_ALPHA).fill()


def _shadow(cv: Canvas, ctx: DrawContext, spec: tuple[float, float, float, float, float]) -> None:
    cx, cy, rx, ry, alpha = spec
    shade = ctx.palette[GROUND_COLOR]
    cv.save()
    cv.translate(cx, cy)
    cv.scale(1.0, ry / rx)
    cv.ellipse(0.0, 0.0, rx, rx).rgrad(0.0, 0.0, rx, [(0, shade, alpha), (1, shade, 0.0)]).fill()
    cv.restore()


def _single(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    cx, cy, r, alpha = SINGLE_POOL
    glow = ctx.palette[POOL_COLOR]
    cv.ellipse(cx, cy, r, r).rgrad(cx, cy, r, [(0, glow, alpha), (1, glow, 0.0)]).fill()
    _shadow(cv, ctx, SINGLE_SHADOW)
    cv.save()
    cv.translate(*SINGLE_AT)
    cv.rotate(SINGLE_TILT)
    cv.translate(0.0, -TIP_Y / 2)  # rotate about the middle of the arrowhead
    draw_one(cv, ctx, rng, polished=False)
    cv.restore()


def _pair(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    for side, polished in ((-1.0, True), (1.0, False)):
        cx, cy, rx, ry, alpha = PAIR_SHADOW
        _shadow(cv, ctx, (cx + side * PAIR_X, cy, rx, ry, alpha))
        cv.save()
        cv.translate(side * PAIR_X, PAIR_LIFT)
        draw_one(cv, ctx, rng, polished=polished)
        cv.restore()


def _quarter(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    cx, cy, rx, ry, alpha = PAIR_SHADOW
    for k, x in enumerate(QUARTER_X):
        _shadow(cv, ctx, (x, cy, rx * QUARTER_SCALE, ry, alpha))
        cv.save()
        cv.translate(x, PAIR_LIFT)
        cv.scale(QUARTER_SCALE, QUARTER_SCALE)
        draw_one(cv, ctx, rng, polished=k == 0)
        cv.restore()


def _heap_items(rng: Generator) -> list[tuple[float, float, float, float, bool]]:
    """(x, y, angle, scale, polished) inside a half-ellipse mound, back (top) to front."""
    half, height = HEAP_SIZE
    items: list[tuple[float, float, float, float, bool]] = []
    while len(items) < HEAP_COUNT:
        x = float(rng.uniform(-half, half))
        top = height * math.sqrt(max(0.0, 1.0 - (x / half) ** 2))
        y = -float(rng.uniform(0.0, top))
        angle = float(rng.uniform(-math.pi, math.pi))
        scale = float(rng.uniform(*HEAP_SCALE))
        items.append((x, y, angle, scale, bool(rng.uniform() < HEAP_POLISHED)))
    return sorted(items, key=lambda item: item[1])


def _heap(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    pal = ctx.palette
    _shadow(cv, ctx, HEAP_SHADOW)
    half, height = HEAP_SIZE
    cv.M(-half - 20.0, 0.0).C(-half * 0.7, -height * 0.9, half * 0.7, -height * 0.9, half + 20.0, 0)
    cv.Z().vgrad(-height * 0.7, 0.0, [(0, pal[HEAP_SOIL[0]], 1), (1, pal[HEAP_SOIL[1]], 1)]).fill()
    for x, y, angle, scale, polished in _heap_items(rng):
        cv.save()
        cv.translate(x, y)
        cv.rotate(angle)
        cv.scale(scale, scale)
        cv.translate(0.0, -TIP_Y / 2)  # rotate about the middle of the arrowhead
        draw_one(cv, ctx, rng, polished=polished)
        cv.restore()


def draw_arrowheads(
    img: FloatImage, layer: ArrowheadsLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Arrowheads in the chosen arrangement, shadows and light pool first."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    rng = ctx.rng(index)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    if layer.arrangement == "pair":
        _pair(cv, ctx, rng)
    elif layer.arrangement == "quarter":
        _quarter(cv, ctx, rng)
    elif layer.arrangement == "heap":
        _heap(cv, ctx, rng)
    else:
        _single(cv, ctx, rng)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(ArrowheadsLayer, draw_arrowheads)])
