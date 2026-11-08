"""Eggshell inlay shared by clouds, peaks and hills: white mask, texture, optional outline."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, EggshellCache, EggshellCrop, fill_mask, over
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import RGB, FloatImage, FloatMask
from history_shorts.textures import eggshell_crop

from .registry import WHITE

# Draws and fills one or more shapes on a canvas whose source colour is already white.
Paint = Callable[[Canvas], None]
# Traces one closed path without filling or stroking it.
Trace = Callable[[Canvas], None]


def cell_and_gap(ctx: DrawContext, cell: int | None, gap: float | None) -> tuple[int, float]:
    """A layer's own eggshell cell/gap, or the theme's where the layer leaves them unset."""
    spec = ctx.theme.textures.eggshell
    return (spec.cell if cell is None else cell, spec.gap if gap is None else gap)


def eggshell_texture(
    ctx: DrawContext, index: int, mask: FloatMask, cell: int, gap: float
) -> EggshellCrop:
    """The eggshell crop (bbox texture, (y0, x0)) for ``mask``; cached when the context has one."""

    def compute() -> EggshellCrop:
        return eggshell_crop(ctx.eggshell_rng(index, mask), mask, ctx.palette, cell, gap)

    if ctx.cache is None:
        return compute()
    key = EggshellCache.key(mask, cell, gap, ctx.seed, index)
    return ctx.cache.get_or_compute(key, compute)


def inlay_fill(
    img: FloatImage,
    ctx: DrawContext,
    index: int,
    paint: Paint,
    cell: int | None,
    gap: float | None,
) -> FloatImage:
    """Eggshell texture inside the shapes ``paint`` fills; nothing outside them (FR-36)."""
    shape = Canvas(CANVAS_W, CANVAS_H)
    shape.color(WHITE)
    paint(shape)
    mask = shape.mask()
    the_cell, the_gap = cell_and_gap(ctx, cell, gap)
    tex, (y0, x0) = eggshell_texture(ctx, index, mask, the_cell, the_gap)
    h, w = tex.shape[:2]
    out = img.copy()
    if h and w:
        window = (slice(y0, y0 + h), slice(x0, x0 + w))
        out[window] = fill_mask(img[window], tex, mask[window])
        outside = mask.copy()
        outside[window] = 0
    else:
        outside = mask
    if outside.any():  # faint mask pixels (alpha <= 0.01) beyond the bbox still dim the base
        keep = 1 - outside[..., None]
        out = np.asarray(out * keep, dtype=np.float32)
    return out


def inlay_outlined(
    img: FloatImage,
    ctx: DrawContext,
    index: int,
    trace: Trace,
    cell: int | None,
    gap: float | None,
    outline: RGB,
    width: float,
) -> FloatImage:
    """One closed shape: eggshell inside, then a ``width`` px outline in ``outline``."""

    def paint(cv: Canvas) -> None:
        trace(cv)
        cv.fill()

    img = inlay_fill(img, ctx, index, paint, cell, gap)
    line = Canvas(CANVAS_W, CANVAS_H)
    trace(line)
    line.color(outline).stroke(width)
    return over(img, line)
