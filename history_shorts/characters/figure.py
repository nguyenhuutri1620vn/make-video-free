"""Draw, box and mask one character through its costume kit (FR-41, FR-45, FR-48).

This module knows the placement transform and nothing about how a character looks: part
names, drawing order, head parts and local extents all come from ``kits.kit_for(style)``.
A new era adds a kit module and role data; this file does not change.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

import numpy as np

from history_shorts.canvas import Canvas
from history_shorts.characters.kits import KITS, LocalBox, kit_for
from history_shorts.characters.roles import DEFAULT_KIT, CharacterStyle
from history_shorts.config import Palette
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import Box, FloatMask

LOCAL_HEIGHT: Final = 100.0  # the shared local frame: feet at (0, 0), 100 units tall

# Compatibility alias: the default kit's FR-41 order. Drawing uses the style's own kit.
DRAW_ORDER: Final[tuple[str, ...]] = KITS[DEFAULT_KIT].draw_order
MASK_MARGIN: Final = 4  # px around a box so anti-aliased edges and strokes are inside


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a figure stands: feet at (x, baseline); facing +1 = prop on the right."""

    x: float
    baseline: float
    height: float
    facing: int

    def __post_init__(self) -> None:
        if self.facing not in (-1, 1):
            raise ValueError(f"facing must be -1 or 1, got {self.facing}")
        if self.height <= 0:
            raise ValueError(f"height must be positive, got {self.height}")


@dataclass(frozen=True, slots=True)
class FigureBoxes:
    """Canvas-pixel boxes of one placed figure; ``prop`` is None without a prop."""

    head: Box
    body: Box
    prop: Box | None


def _transform_box(local: LocalBox, placement: Placement) -> Box:
    """Map a local-frame box through the placement; mirroring flips the x order."""
    unit = placement.height / LOCAL_HEIGHT
    lx0, ly0, lx1, ly1 = local
    xs = sorted(placement.x + placement.facing * unit * lx for lx in (lx0, lx1))
    ys = sorted(placement.baseline + unit * ly for ly in (ly0, ly1))
    return Box(xs[0], ys[0], xs[1], ys[1])


def figure_boxes(style: CharacterStyle, placement: Placement) -> FigureBoxes:
    """Head, body and prop boxes from the kit's extents; nothing is rendered."""
    extents = kit_for(style).extents
    head = _transform_box(extents.head_box(style.crest), placement)
    body = _transform_box(extents.body, placement)
    extent = extents.props.get(style.prop)
    prop = None if extent is None else _transform_box(extent, placement)
    return FigureBoxes(head, body, prop)


def draw_figure(
    cv: Canvas,
    style: CharacterStyle,
    placement: Placement,
    palette: Palette,
    names: Iterable[str] | None = None,
) -> None:
    """Draw ``names`` (default: the kit's whole draw order); mirroring is only ``scale(-1, 1)``.

    ``names`` must be in the kit's draw order; ``KeyError`` for a name the kit lacks.
    """
    kit = kit_for(style)
    unit = placement.height / LOCAL_HEIGHT
    cv.save()
    cv.translate(placement.x, placement.baseline)
    cv.scale(placement.facing * unit, unit)
    for name in kit.draw_order if names is None else names:
        kit.parts[name](cv, style, palette)
    cv.restore()


def _render_mask(
    style: CharacterStyle,
    placement: Placement,
    palette: Palette,
    names: tuple[str, ...] | None,
    area: Box,
) -> tuple[FloatMask, Box]:
    """Alpha of ``names`` on a canvas cropped to ``area`` (+ margin, clamped to the frame).

    The returned box is in canvas coordinates: ``mask[j, i]`` is canvas pixel
    ``(box.x0 + i, box.y0 + j)``.
    """
    x0 = max(0, math.floor(area.x0) - MASK_MARGIN)
    y0 = max(0, math.floor(area.y0) - MASK_MARGIN)
    x1 = min(CANVAS_W, math.ceil(area.x1) + MASK_MARGIN)
    y1 = min(CANVAS_H, math.ceil(area.y1) + MASK_MARGIN)
    if x1 <= x0 or y1 <= y0:
        return np.zeros((0, 0), dtype=np.float32), Box(x0, y0, x0, y0)
    cv = Canvas(x1 - x0, y1 - y0)
    cv.save()
    cv.translate(-x0, -y0)
    draw_figure(cv, style, placement, palette, names)
    cv.restore()
    return cv.mask(), Box(x0, y0, x1, y1)


def figure_mask(
    style: CharacterStyle, placement: Placement, palette: Palette
) -> tuple[FloatMask, Box]:
    """Alpha of the whole figure and the canvas box the array covers."""
    boxes = figure_boxes(style, placement)
    area = boxes.head.union(boxes.body)
    if boxes.prop is not None:
        area = area.union(boxes.prop)
    return _render_mask(style, placement, palette, None, area)


def head_mask(
    style: CharacterStyle, placement: Placement, palette: Palette
) -> tuple[FloatMask, Box]:
    """Alpha of the visible head: the kit's head parts, from the top down to its chin line.

    The hair behind the robe hangs below the chin but is hidden by the robe, so the mask
    stops at the chin; covering it would hide nothing.
    """
    kit = kit_for(style)
    head = figure_boxes(style, placement).head  # bottom edge = the kit's chin_y, placed
    mask, box = _render_mask(style, placement, palette, kit.head_order, head)
    chin = math.ceil(head.y1) - int(box.y0)
    mask[max(chin, 0) :, :] = 0
    return mask, box
