"""A narrow path winding into misty mountains, no figures (backlog #12).

Original procedural artwork. The path is sampled along a centre curve from the near end
(``y``, wide) to the far end (``y - depth``, a thread), so it narrows with distance. Mist
bands are translucent ivory ellipses laid over the far end.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import LonePathLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

SAMPLES: Final = 48
CENTRE_X: Final = CANVAS_W / 2
SWAY: Final = 120.0  # px of side-to-side winding at the near end
SWAY_TURNS: Final = 2.4  # radians of winding over the whole path
NEAR_HALF_WIDTH: Final = 150.0
FAR_HALF_WIDTH: Final = 3.0
PATH_FILL: Final = ("brown", "brown_lt")  # far (top) to near (bottom)
EDGE_COLOR: Final = "gold_dk"
EDGE_WIDTH: Final = 1.4

TUFTS: Final = 9  # grass tufts along each edge
TUFT_COLOR: Final = "gold_dk"
TUFT_SIZE: Final = 14.0  # at the near end; tufts shrink with distance

MIST_COLOR: Final = "egg_tone"
MIST_BANDS: Final = ((0.7, 0.22), (0.86, 0.28), (1.0, 0.32))  # depth fraction, centre alpha
MIST_RADII: Final = (560.0, 46.0)


def _point(layer: LonePathLayer, t: float) -> tuple[float, float, float]:
    """Centre x, y and half width at ``t`` (0 near, 1 far)."""
    x = CENTRE_X + SWAY * math.sin(SWAY_TURNS * t) * (1 - 0.6 * t)
    y = layer.y - layer.depth * (1 - (1 - t) ** 2)
    half = FAR_HALF_WIDTH + (NEAR_HALF_WIDTH - FAR_HALF_WIDTH) * (1 - t) ** 1.5
    return x, y, half


def _path(cv: Canvas, layer: LonePathLayer) -> None:
    samples = [_point(layer, k / SAMPLES) for k in range(SAMPLES + 1)]
    x, y, half = samples[0]
    cv.M(x - half, y)
    for x, y, half in samples[1:]:
        cv.L(x - half, y)
    for x, y, half in reversed(samples):
        cv.L(x + half, y)
    cv.Z()


def _tufts(cv: Canvas, ctx: DrawContext, layer: LonePathLayer) -> None:
    for k in range(TUFTS):
        t = 0.08 + 0.8 * k / TUFTS
        x, y, half = _point(layer, t)
        size = TUFT_SIZE * (1 - t) + 2
        for side in (-1, 1):
            bx = x + side * (half + 4)
            for lean in (-0.5, 0.0, 0.5):
                cv.M(bx, y).L(bx + lean * size + side * size * 0.3, y - size)
    cv.color(ctx.palette[TUFT_COLOR]).stroke(1.2)


def _mist(cv: Canvas, ctx: DrawContext, layer: LonePathLayer) -> None:
    """Soft bands: a radial gradient fading to clear, squashed into a wide ellipse."""
    rx, ry = MIST_RADII
    colour = ctx.palette[MIST_COLOR]
    for fraction, alpha in MIST_BANDS:
        cv.save()
        cv.translate(CENTRE_X, layer.y - layer.depth * fraction)
        cv.scale(1.0, ry / rx)
        cv.ellipse(0, 0, rx, rx).rgrad(0, 0, rx, [(0, colour, alpha), (1, colour, 0.0)]).fill()
        cv.restore()


def draw_lone_path(
    img: FloatImage, layer: LonePathLayer, ctx: DrawContext, index: int
) -> FloatImage:
    pal = ctx.palette
    cv = Canvas(CANVAS_W, CANVAS_H)
    top = layer.y - layer.depth
    _path(cv, layer)
    cv.vgrad(top, layer.y, [(0, pal[PATH_FILL[0]], 1), (1, pal[PATH_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[EDGE_COLOR]).stroke(EDGE_WIDTH)
    _tufts(cv, ctx, layer)
    if layer.mist:
        _mist(cv, ctx, layer)
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(LonePathLayer, draw_lone_path)])
