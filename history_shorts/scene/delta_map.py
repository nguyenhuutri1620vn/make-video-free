"""A lacquer map panel of a river delta with red place dots and an optional arrow (backlog #4).

The map is an original, stylised drawing (no real map is traced): a coastline, rivers that
fan into a delta, small mountain marks, red dots. Positions are in map units: (0, 0) is the
panel's top-left corner and (1, 1) its bottom-right, so a dot list does not depend on the
panel's size or position on the canvas.
"""

from __future__ import annotations

from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import MapLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

Point = tuple[float, float]

PANEL_FILL: Final = "deep_warm"
BORDER: Final = "gold"
BORDER_WIDTH: Final = 3.0
INNER_BORDER: Final = "gold_dk"
INNER_INSET: Final = 10.0
INNER_WIDTH: Final = 1.2

# coastline from the right edge down to the bottom edge; the sea lies below and right of it
COAST: Final[tuple[Point, ...]] = (
    (1.0, 0.30), (0.86, 0.38), (0.74, 0.47), (0.64, 0.58), (0.55, 0.70), (0.47, 0.84), (0.40, 1.0),
)  # fmt: skip
SEA_FILL: Final = "black"
COAST_COLOR: Final = "gold"
COAST_WIDTH: Final = 2.2
WAVE_COLOR: Final = "gold_dk"
WAVE_WIDTH: Final = 1.2
WAVES: Final[tuple[Point, ...]] = (
    (0.86, 0.55),
    (0.74, 0.70),
    (0.90, 0.78),
    (0.64, 0.88),
    (0.84, 0.93),
)
WAVE_SIZE: Final = 0.035

# rivers as cubic curves (start, control 1, control 2, end), widest first
RIVERS: Final[tuple[tuple[Point, Point, Point, Point], ...]] = (
    ((0.04, 0.12), (0.25, 0.25), (0.40, 0.42), (0.62, 0.60)),
    ((0.20, 0.02), (0.28, 0.20), (0.34, 0.32), (0.40, 0.40)),
    ((0.03, 0.42), (0.18, 0.44), (0.30, 0.42), (0.40, 0.40)),
    ((0.48, 0.50), (0.50, 0.62), (0.50, 0.72), (0.52, 0.76)),
    ((0.54, 0.54), (0.64, 0.50), (0.72, 0.48), (0.78, 0.44)),
)
RIVER_COLOR: Final = "gold"
RIVER_WIDTHS: Final = (3.2, 2.2, 2.2, 1.6, 1.6)

MOUNTAINS: Final[tuple[Point, ...]] = (
    (0.10, 0.25), (0.16, 0.20), (0.08, 0.60), (0.15, 0.66), (0.24, 0.72), (0.40, 0.10),
    (0.50, 0.06), (0.62, 0.14), (0.20, 0.86),
)  # fmt: skip
MOUNTAIN_SIZE: Final = 0.035
MOUNTAIN_FILL: Final = "vermilion_dk"
MOUNTAIN_LINE: Final = "gold_dk"

DOT_FILL: Final = "vermilion"
DOT_RING: Final = "gold_lt"
DOT_RADIUS: Final = 22.0  # px, listed dots
DOT_HALO: Final = 9.0  # px between a listed dot and its outer ring
SCATTER_RADIUS: Final = 6.0  # px, scattered dots
SCATTER_MARGIN: Final = 0.07
SCATTER_MIN_GAP: Final = 0.045  # map units between scattered dots
SCATTER_TRIES: Final = 4000
SCATTER_MOUNTAIN_GAP: Final = 0.05  # keep scattered dots off the mountain marks

ARROW: Final[tuple[Point, Point]] = ((0.62, -0.02), (0.44, 0.34))  # tail, tip
ARROW_WIDTH: Final = 0.045  # shaft half width, map units of the panel width
ARROW_HEAD: Final = (0.11, 0.08)  # head length, head half width
ARROW_FILL: Final = "vermilion"


def _in_sea(u: float, v: float) -> bool:
    """True below/right of the coastline (ray cast against the sea polygon)."""
    poly = (*COAST, (1.0, 1.0))
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1], strict=True):
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def scatter_points(rng: Generator, count: int, avoid: tuple[Point, ...] = ()) -> list[Point]:
    """Up to ``count`` well-spaced points on land, clear of the mountain marks and of the
    ``avoid`` points (listed dots); deterministic for a given generator."""
    points: list[Point] = []
    blocked = (*MOUNTAINS, *avoid)
    lo, hi = SCATTER_MARGIN, 1 - SCATTER_MARGIN
    for _ in range(SCATTER_TRIES):
        if len(points) >= count:
            break
        u, v = (float(c) for c in rng.uniform(lo, hi, size=2))
        if _in_sea(u, v) or any(
            (u - a) ** 2 + (v - b) ** 2 < SCATTER_MOUNTAIN_GAP**2 for a, b in blocked
        ):
            continue
        if all((u - a) ** 2 + (v - b) ** 2 >= SCATTER_MIN_GAP**2 for a, b in points):
            points.append((u, v))
    return points


class _Frame:
    """Map units to canvas pixels for one panel."""

    def __init__(self, layer: MapLayer) -> None:
        self.x, self.y, self.w, self.h = layer.x, layer.y, layer.w, layer.h

    def __call__(self, p: Point) -> Point:
        return self.x + p[0] * self.w, self.y + p[1] * self.h


def _panel(cv: Canvas, ctx: DrawContext, f: _Frame) -> None:
    pal = ctx.palette
    cv.color(pal[PANEL_FILL]).rect(f.x, f.y, f.w, f.h).fill()
    cv.M(*f(COAST[0]))
    for p in COAST[1:]:
        cv.L(*f(p))
    cv.L(*f((1.0, 1.0))).Z().color(pal[SEA_FILL]).fill()
    cv.M(*f(COAST[0]))
    for p in COAST[1:]:
        cv.L(*f(p))
    cv.color(pal[COAST_COLOR]).stroke(COAST_WIDTH)
    for u, v in WAVES:
        size = WAVE_SIZE * f.w
        x, y = f((u, v))
        cv.M(x - size, y).C(x - size / 2, y - size / 2, x, y - size / 2, x, y)
        cv.C(x, y - size / 2, x + size / 2, y - size / 2, x + size, y)
        cv.color(pal[WAVE_COLOR]).stroke(WAVE_WIDTH)


def _land(cv: Canvas, ctx: DrawContext, f: _Frame) -> None:
    pal = ctx.palette
    for (a, b, c, d), width in zip(RIVERS, RIVER_WIDTHS, strict=True):
        cv.M(*f(a)).C(*f(b), *f(c), *f(d)).color(pal[RIVER_COLOR]).stroke(width)
    size = MOUNTAIN_SIZE * f.w
    for p in MOUNTAINS:
        x, y = f(p)
        cv.M(x - size, y + size * 0.6).L(x, y - size * 0.8).L(x + size, y + size * 0.6).Z()
        cv.color(pal[MOUNTAIN_FILL]).fill(keep=True).color(pal[MOUNTAIN_LINE]).stroke(1.2)


def _dot(cv: Canvas, ctx: DrawContext, x: float, y: float, r: float) -> None:
    cv.color(ctx.palette[DOT_FILL]).ellipse(x, y, r, r).fill(keep=True)
    cv.color(ctx.palette[DOT_RING]).stroke(max(r / 5, 1.2))


def _arrow(cv: Canvas, ctx: DrawContext, f: _Frame) -> None:
    (tx, ty), (hx, hy) = (f(p) for p in ARROW)
    dx, dy = hx - tx, hy - ty
    length = (dx * dx + dy * dy) ** 0.5
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    shaft, head_len, head_half = ARROW_WIDTH * f.w, ARROW_HEAD[0] * f.w, ARROW_HEAD[1] * f.w
    bx, by = hx - ux * head_len, hy - uy * head_len
    cv.M(tx + nx * shaft, ty + ny * shaft).L(bx + nx * shaft, by + ny * shaft)
    cv.L(bx + nx * head_half, by + ny * head_half).L(hx, hy)
    cv.L(bx - nx * head_half, by - ny * head_half).L(bx - nx * shaft, by - ny * shaft)
    cv.L(tx - nx * shaft, ty - ny * shaft).Z()
    cv.color(ctx.palette[ARROW_FILL]).fill(keep=True).color(ctx.palette[BORDER]).stroke(2.0)


def draw_map(img: FloatImage, layer: MapLayer, ctx: DrawContext, index: int) -> FloatImage:
    f = _Frame(layer)
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.rect(f.x, f.y, f.w, f.h).clip()
    _panel(cv, ctx, f)
    _land(cv, ctx, f)
    for x, y in (f(p) for p in scatter_points(ctx.rng(index), layer.scatter, layer.dots)):
        _dot(cv, ctx, x, y, SCATTER_RADIUS)
    for x, y in (f(p) for p in layer.dots):
        _dot(cv, ctx, x, y, DOT_RADIUS)
        halo = DOT_RADIUS + DOT_HALO
        cv.color(ctx.palette[DOT_RING]).ellipse(x, y, halo, halo).stroke(1.5)
    if layer.arrow:
        _arrow(cv, ctx, f)
    cv.restore()
    pal = ctx.palette
    cv.color(pal[BORDER]).rect(f.x, f.y, f.w, f.h).stroke(BORDER_WIDTH)
    inset = INNER_INSET
    cv.color(pal[INNER_BORDER]).rect(f.x + inset, f.y + inset, f.w - 2 * inset, f.h - 2 * inset)
    cv.stroke(INNER_WIDTH)
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(MapLayer, draw_map)])
