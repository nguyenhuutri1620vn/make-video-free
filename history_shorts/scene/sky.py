"""Gold-leaf sun and moon, and birds (FR-23)."""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, fill_mask, over
from history_shorts.config import BirdsLayer, SunLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.textures import gold_leaf

from .registry import WHITE, LayerDrawer, entry

RING_INNER_COLOR: Final = "gold_lt"
RING_OUTER_COLOR: Final = "gold_dk"
SUN_RING_WIDTH: Final = 3.0
MOON_RING_WIDTH: Final = 2.5
OUTER_RING_OFFSET: Final = 18.0
OUTER_RING_WIDTH: Final = 1.5
BIRD_COLOR: Final = "gold"
BIRD_STROKE: Final = 1.6  # divided by the bird scale so the line stays the same width


def draw_sun(img: FloatImage, layer: SunLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Gold-leaf disc masked to the circle, then one or two thin rings."""
    gold = ctx.theme.textures.gold_leaf
    tile = gold.tile if layer.tile is None else layer.tile
    worn = gold.worn if layer.worn is None else layer.worn
    disc = Canvas(CANVAS_W, CANVAS_H)
    disc.color(WHITE).ellipse(layer.x, layer.y, layer.r, layer.r).fill()
    mask = disc.mask()
    tex = gold_leaf(ctx.rng(index), ctx.palette, tile, worn, width=CANVAS_W, height=CANVAS_H)
    img = fill_mask(img, tex, mask)
    if layer.rings < 1:
        return img
    cv = Canvas(CANVAS_W, CANVAS_H)
    ring_width = SUN_RING_WIDTH if layer.kind == "sun" else MOON_RING_WIDTH
    cv.color(ctx.palette[RING_INNER_COLOR]).ellipse(layer.x, layer.y, layer.r, layer.r)
    cv.stroke(ring_width)
    if layer.rings >= 2:
        outer = layer.r + OUTER_RING_OFFSET
        cv.color(ctx.palette[RING_OUTER_COLOR]).ellipse(layer.x, layer.y, outer, outer)
        cv.stroke(OUTER_RING_WIDTH)
    return over(img, cv)


def draw_birds(img: FloatImage, layer: BirdsLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Each bird is a single two-arc gold stroke."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    for item in layer.items:
        s = item.scale
        cv.save()
        cv.translate(item.x, item.y)
        cv.scale(s, s)
        cv.color(ctx.palette[BIRD_COLOR]).M(-12, 0).C(-8, -6, -3, -6, 0, 0)
        cv.C(3, -6, 8, -6, 12, 0).stroke(BIRD_STROKE / s)
        cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(SunLayer, draw_sun), entry(BirdsLayer, draw_birds)])
