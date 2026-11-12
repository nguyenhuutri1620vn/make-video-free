"""Rows of hills planted with war flags and spears at rest, no people (backlog #8).

Original procedural artwork. Rows run back to front: the back row is smallest and highest,
each row nearer is larger, lower and has fewer, wider-spaced poles. Pole positions jitter
slightly with the layer's RNG, so the rows never look like a ruled grid.
"""

from __future__ import annotations

from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import BannersLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

ROW_STEP: Final = 70.0  # px between row baselines
BACK_SCALE: Final = 0.5
SCALE_STEP: Final = 0.17
BACK_COUNT: Final = 13
COUNT_STEP: Final = 2
MARGIN: Final = 60.0
JITTER: Final = 0.25  # of the pole spacing

HILL_FILL: Final = ("mountain_base", "deep")
HILL_RIDGE: Final = "gold_dk"
HILL_RISE: Final = 34.0
HILL_DEPTH: Final = 90.0

POLE_HEIGHT: Final = 160.0  # at scale 1
POLE_COLOR: Final = "gold_dk"
POLE_WIDTH: Final = 3.0
SPEAR_EVERY: Final = 3  # every third pole carries a spear blade instead of a flag
BLADE: Final = (7.0, 26.0)  # half width, length
BLADE_FILL: Final = "gold_lt"
FLAG_FILLS: Final = ("vermilion", "vermilion_dk")
FLAG_SIZE: Final = (84.0, 52.0)  # length, height
FLAG_OUTLINE: Final = "gold"
FLAG_EMBLEM: Final = 8.0


def _hill(cv: Canvas, ctx: DrawContext, base: float) -> None:
    pal = ctx.palette
    w = float(CANVAS_W)
    cv.M(0, base + 12).C(w * 0.25, base - HILL_RISE, w * 0.75, base - HILL_RISE, w, base + 12)
    cv.L(w, base + HILL_DEPTH).L(0, base + HILL_DEPTH).Z()
    cv.vgrad(
        base - HILL_RISE, base + HILL_DEPTH, [(0, pal[HILL_FILL[0]], 1), (1, pal[HILL_FILL[1]], 1)]
    )
    cv.fill()
    cv.M(0, base + 12).C(w * 0.25, base - HILL_RISE, w * 0.75, base - HILL_RISE, w, base + 12)
    cv.color(pal[HILL_RIDGE]).stroke(1.5)


def _ridge_y(base: float, x: float) -> float:
    """Height of the hill's ridge curve at ``x`` (the cubic's y for t = x / width)."""
    t = x / CANVAS_W
    p0, p1 = base + 12, base - HILL_RISE
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p1 + t**3 * p0


def _pole(cv: Canvas, ctx: DrawContext, x: float, foot: float, s: float, kind: int) -> None:
    pal = ctx.palette
    top = foot - POLE_HEIGHT * s
    cv.color(pal[POLE_COLOR]).M(x, foot).L(x, top).stroke(POLE_WIDTH * max(s, 0.5))
    if kind % SPEAR_EVERY == SPEAR_EVERY - 1:
        hw, length = BLADE[0] * s, BLADE[1] * s
        cv.M(x, top - length).C(x + hw, top - length * 0.5, x + hw, top, x, top)
        cv.C(x - hw, top, x - hw, top - length * 0.5, x, top - length).Z()
        cv.color(pal[BLADE_FILL]).fill(keep=True).color(pal[FLAG_OUTLINE]).stroke(0.8)
        return
    length, height = FLAG_SIZE[0] * s, FLAG_SIZE[1] * s
    cv.M(x, top).C(x + length * 0.35, top - height * 0.15, x + length * 0.7, top + height * 0.2,
                   x + length, top + height * 0.1)  # fmt: skip
    cv.L(x + length * 0.8, top + height * 0.55).L(x + length, top + height)
    cv.C(
        x + length * 0.6, top + height * 1.1, x + length * 0.3, top + height * 0.8, x, top + height
    )
    cv.Z().color(pal[FLAG_FILLS[kind % 2]]).fill(keep=True)
    cv.color(pal[FLAG_OUTLINE]).stroke(1.0)
    cv.color(pal[FLAG_OUTLINE]).ellipse(x + length * 0.4, top + height * 0.45, FLAG_EMBLEM * s,
                                        FLAG_EMBLEM * s).stroke(0.8)  # fmt: skip


def _row(cv: Canvas, ctx: DrawContext, rng: Generator, base: float, k: int, count: int) -> None:
    s = BACK_SCALE + SCALE_STEP * k
    step = (CANVAS_W - 2 * MARGIN) / max(count - 1, 1)
    for n in range(count):
        x = MARGIN + n * step + float(rng.uniform(-JITTER, JITTER)) * step
        _pole(cv, ctx, x, _ridge_y(base, x) + 6, s, n + k)
    _hill(cv, ctx, base)


def draw_banners(img: FloatImage, layer: BannersLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Back row first; each row's poles stand in its hill, which covers their feet."""
    rng = ctx.rng(index)
    cv = Canvas(CANVAS_W, CANVAS_H)
    for k in range(layer.rows):
        base = layer.y - (layer.rows - 1 - k) * ROW_STEP
        _row(cv, ctx, rng, base, k, max(BACK_COUNT - COUNT_STEP * k, 3))
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(BannersLayer, draw_banners)])
