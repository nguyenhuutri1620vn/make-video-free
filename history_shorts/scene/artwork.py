"""The ``artwork`` layer (M11): a library file drawn part by part in the lacquer style.

Parts draw in file order, fill then outline, under ``translate(x, y)`` and
``scale(flip * scale, scale)`` (mirroring only through the scale). Flat colours and
gradients go on one Cairo canvas; a gold-leaf or eggshell part first flushes that canvas
onto the image, then fills its own mask with the texture (FR-36), and drawing goes on on a
fresh canvas, so later parts still cover it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial

import numpy as np

from history_shorts.artwork.load import library_for
from history_shorts.artwork.model import Artwork, Gradient, Part, Solid, Stroke, Texture
from history_shorts.artwork.motion import motion_phases, move_part
from history_shorts.artwork.path import path_bounds, trace
from history_shorts.canvas import Canvas, ColorStop
from history_shorts.compose import DrawContext, fill_mask, over
from history_shorts.config import ArtworkLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.textures import gold_leaf

from .inlay import cell_and_gap, inlay_fill
from .registry import WHITE, LayerDrawer, PhaseDrawer, entry, phase_entry

MIN_TEXTURE_PX = 2  # smallest gold-leaf tile / eggshell cell after scaling


def _place(cv: Canvas, layer: ArtworkLayer) -> None:
    cv.translate(layer.x, layer.y)
    cv.scale(layer.flip * layer.scale, layer.scale)


def _clip(cv: Canvas, shapes: Mapping[str, Part], part: Part) -> None:
    if part.clip is not None:
        trace(cv, shapes[part.clip].ops)
        cv.clip()


def _alpha(*factors: float) -> float:
    """A paint alpha: the product of ``factors``, kept within 0..1 (a pulse may exceed 1)."""
    return min(max(float(np.prod(factors)), 0.0), 1.0)


def _stops(ctx: DrawContext, fill: Gradient, alpha: float) -> list[ColorStop]:
    return [(offset, ctx.palette[key], _alpha(a, alpha)) for key, a, offset in fill.stops]


def _paint_fill(cv: Canvas, ctx: DrawContext, part: Part) -> None:
    fill = part.fill
    if isinstance(fill, Solid):
        cv.color(ctx.palette[fill.color], _alpha(fill.alpha, part.alpha))
    elif isinstance(fill, Gradient):
        if fill.radial is not None:
            cx, cy, r = fill.radial
            cv.rgrad(cx, cy, r, _stops(ctx, fill, part.alpha))
        else:
            x0, y0, x1, y1 = path_bounds(part.ops)
            stops = _stops(ctx, fill, part.alpha)
            if fill.direction == "h":
                cv.hgrad(x0, x1, stops)
            else:
                cv.vgrad(y0, y1, stops)
    trace(cv, part.ops)
    cv.fill()


def _paint_stroke(cv: Canvas, ctx: DrawContext, part: Part, stroke: Stroke) -> None:
    trace(cv, part.ops)
    cv.color(ctx.palette[stroke.color], _alpha(stroke.alpha, part.alpha)).stroke(stroke.width)


def _shape_mask(layer: ArtworkLayer, shapes: Mapping[str, Part], part: Part) -> Canvas:
    shape = Canvas(CANVAS_W, CANVAS_H)
    shape.save()
    _place(shape, layer)
    _clip(shape, shapes, part)
    trace(shape, part.ops)
    shape.color(WHITE).fill()
    shape.restore()
    return shape


def _texture(
    img: FloatImage,
    ctx: DrawContext,
    index: int,
    layer: ArtworkLayer,
    shapes: Mapping[str, Part],
    part: Part,
) -> FloatImage:
    """A gold-leaf or eggshell part: texture inside its mask only; sizes in artwork units."""
    fill = part.fill
    assert isinstance(fill, Texture)
    if fill.kind == "gold_leaf":
        spec = ctx.theme.textures.gold_leaf
        tile = max(MIN_TEXTURE_PX, round((fill.tile or spec.tile) * layer.scale))
        worn = spec.worn if fill.worn is None else fill.worn
        mask = _shape_mask(layer, shapes, part).mask() * _alpha(part.alpha)
        tex = gold_leaf(ctx.rng(index), ctx.palette, tile, worn, width=CANVAS_W, height=CANVAS_H)
        return fill_mask(img, tex, mask)
    cell, gap = cell_and_gap(ctx, None, fill.gap)
    cell = max(MIN_TEXTURE_PX, round((fill.cell or cell) * layer.scale))

    def paint(cv: Canvas) -> None:
        cv.save()
        _place(cv, layer)
        _clip(cv, shapes, part)
        trace(cv, part.ops)
        cv.fill()
        cv.restore()

    return inlay_fill(img, ctx, index, paint, cell, gap)


def draw_parts(
    img: FloatImage,
    art: Artwork,
    layer: ArtworkLayer,
    ctx: DrawContext,
    index: int,
    parts: Sequence[Part],
) -> FloatImage:
    """Draw ``parts`` (the file's parts, possibly moved) of ``art`` at ``layer``; a part is
    clipped to the given version of its clip part."""
    shapes = {part.id: part for part in parts}
    cv = Canvas(CANVAS_W, CANVAS_H)
    used = False

    def on_canvas(draw: Callable[[Canvas], None], part: Part) -> None:
        nonlocal used
        cv.save()
        _place(cv, layer)
        _clip(cv, shapes, part)
        draw(cv)
        cv.restore()
        used = True

    for part in parts:
        if isinstance(part.fill, Texture):
            if used:
                img, cv, used = over(img, cv), Canvas(CANVAS_W, CANVAS_H), False
            img = _texture(img, ctx, index, layer, shapes, part)
        elif part.fill is not None:
            on_canvas(partial(_paint_fill, ctx=ctx, part=part), part)
        if part.stroke is not None:
            on_canvas(partial(_paint_stroke, ctx=ctx, part=part, stroke=part.stroke), part)
    return over(img, cv) if used else np.asarray(img, dtype=np.float32)


def draw_artwork(img: FloatImage, layer: ArtworkLayer, ctx: DrawContext, index: int) -> FloatImage:
    art = library_for(ctx.theme).get(layer.name, ctx.palette)
    return draw_parts(img, art, layer, ctx, index, art.parts)


def draw_artwork_at(
    img: FloatImage, layer: ArtworkLayer, ctx: DrawContext, index: int, phase: float
) -> FloatImage:
    """The artwork at loop ``phase``: parts with ``motion`` moved, the rest as drawn still."""
    art = library_for(ctx.theme).get(layer.name, ctx.palette)
    phis = motion_phases(ctx, index, len(art.parts))
    knob = ctx.theme.living.artwork_motion
    moved = [move_part(part, phase, phis[k], knob) for k, part in enumerate(art.parts)]
    return draw_parts(img, art, layer, ctx, index, moved)


DRAWERS: dict[type, LayerDrawer] = dict([entry(ArtworkLayer, draw_artwork)])
PHASE_DRAWERS: dict[type, PhaseDrawer] = dict([phase_entry(ArtworkLayer, draw_artwork_at)])
