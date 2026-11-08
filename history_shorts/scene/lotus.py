"""A lacquered lotus flower on its leaf (FR-46)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import LotusLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

# -- leaf (lotus units, drawn under translate(x, y) and scale(s, s)) ------------------------
LEAF_CENTRE: Final = (0.0, 6.0)
LEAF_RADII: Final = (46.0, 11.0)
LEAF_GRADIENT: Final = (-6.0, 16.0)
LEAF_TOP_COLOR: Final = "jade"
LEAF_BOTTOM_COLOR: Final = "leaf_dk"
LEAF_OUTLINE_COLOR: Final = "gold"
LEAF_OUTLINE_WIDTH: Final = 1.2
VEIN_COLOR: Final = "gold_dk"
VEIN_WIDTH: Final = 0.8
VEIN_ANGLES: Final = (-30, -15, 0, 15, 30)
VEIN_REACH: Final = 1.4  # each vein runs from the leaf centre to x = angle * reach

# -- petals --------------------------------------------------------------------------------
PETAL_TIP_COLOR: Final = "petal_tip"
PETAL_BASE_COLOR: Final = "vermilion_dk"
PETAL_MID_STOP: Final = 0.45
PETAL_OUTLINE_COLOR: Final = "gold"
PETAL_OUTLINE_WIDTH: Final = 1.0
PETAL_VEIN_COLOR: Final = "gold_dk"
PETAL_VEIN_ALPHA: Final = 0.6
PETAL_VEIN_WIDTH: Final = 0.5
PETAL_VEIN_START: Final = -2.0
PETAL_VEIN_REACH: Final = 0.8  # of the petal length
BELLY: Final = 0.35  # control-point heights, as a fraction of the petal length
SHOULDER: Final = 0.85
SHOULDER_WIDTH: Final = 0.7  # of the petal width


@dataclass(frozen=True, slots=True)
class Petal:
    rotation: float  # degrees from upright
    length: float
    width: float
    fill: str  # palette key of the petal's middle colour


# Drawing order: the outer pair first, the centre petal last (in front).
PETALS: Final = (
    Petal(-62, 34, 13, "vermilion_dk"),
    Petal(62, 34, 13, "vermilion_dk"),
    Petal(-32, 42, 15, "vermilion"),
    Petal(32, 42, 15, "vermilion"),
    Petal(0, 48, 16, "vermilion"),
)


def _petal_path(cv: Canvas, length: float, width: float) -> None:
    sw = width * SHOULDER_WIDTH
    cv.M(0, 0).C(-width, -length * BELLY, -sw, -length * SHOULDER, 0, -length)
    cv.C(sw, -length * SHOULDER, width, -length * BELLY, 0, 0).Z()


def _draw_leaf(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cx, cy = LEAF_CENTRE
    rx, ry = LEAF_RADII
    top, bottom = LEAF_GRADIENT
    cv.vgrad(top, bottom, [(0, pal[LEAF_TOP_COLOR], 1), (1, pal[LEAF_BOTTOM_COLOR], 1)])
    cv.ellipse(cx, cy, rx, ry).fill()
    cv.color(pal[LEAF_OUTLINE_COLOR]).ellipse(cx, cy, rx, ry).stroke(LEAF_OUTLINE_WIDTH)
    for angle in VEIN_ANGLES:
        # flat: the end point keeps the centre's y, so the vein is a horizontal dash
        cv.color(pal[VEIN_COLOR]).M(cx, cy).L(angle * VEIN_REACH, cy).stroke(VEIN_WIDTH)


def _draw_petal(cv: Canvas, ctx: DrawContext, petal: Petal) -> None:
    pal = ctx.palette
    length, width = petal.length, petal.width
    cv.save()
    cv.rotate(math.radians(petal.rotation))
    _petal_path(cv, length, width)
    cv.vgrad(
        -length,
        0,
        [
            (0, pal[PETAL_TIP_COLOR], 1),
            (PETAL_MID_STOP, pal[petal.fill], 1),
            (1, pal[PETAL_BASE_COLOR], 1),
        ],
    ).fill()
    _petal_path(cv, length, width)
    cv.color(pal[PETAL_OUTLINE_COLOR]).stroke(PETAL_OUTLINE_WIDTH)
    cv.color(pal[PETAL_VEIN_COLOR], PETAL_VEIN_ALPHA).M(0, PETAL_VEIN_START)
    cv.L(0, -length * PETAL_VEIN_REACH).stroke(PETAL_VEIN_WIDTH)
    cv.restore()


def draw_lotus(img: FloatImage, layer: LotusLayer, ctx: DrawContext, index: int) -> FloatImage:
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _draw_leaf(cv, ctx)
    for petal in PETALS:
        _draw_petal(cv, ctx, petal)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(LotusLayer, draw_lotus)])
