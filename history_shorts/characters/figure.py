"""Draw, box and mask one character through its costume kit (FR-41, FR-45, FR-48).

This module knows the placement transform and nothing about how a character looks: part
names, drawing order, head parts and local extents all come from ``kits.kit_for(style)``.
A new era adds a kit module and role data; this file does not change. A style with a
``pose`` is drawn through the kit's rig, part by part under its joint transform (M10).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

import numpy as np

from history_shorts.canvas import Canvas
from history_shorts.characters.kits import KITS, LocalBox, kit_for
from history_shorts.characters.kits.base import Kit, KitRig, PartFn
from history_shorts.characters.pose import Pose
from history_shorts.characters.rig import Affine, apply_to
from history_shorts.characters.roles import DEFAULT_KIT, CharacterStyle
from history_shorts.config import Palette
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import Box, FloatMask

LOCAL_HEIGHT: Final = 100.0  # the shared local frame: feet at (0, 0), 100 units tall

# Compatibility alias: the default kit's FR-41 order. Drawing uses the style's own kit.
DRAW_ORDER: Final[tuple[str, ...]] = KITS[DEFAULT_KIT].draw_order
ROOT: Final = "root"  # rig segment of parts drawn in the plain local frame
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


def _posed_box(local: LocalBox, m: Affine, placement: Placement) -> Box:
    """``local`` moved by joint ``m``, then mapped through the placement."""
    lx0, ly0, lx1, ly1 = local
    corners = [m.apply((x, y)) for x in (lx0, lx1) for y in (ly0, ly1)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return _transform_box((min(xs), min(ys), max(xs), max(ys)), placement)


def _union(boxes: Iterable[Box]) -> Box:
    items = list(boxes)
    out = items[0]
    for box in items[1:]:
        out = out.union(box)
    return out


def _posed_boxes(style: CharacterStyle, placement: Placement, kit: Kit) -> FigureBoxes:
    assert style.pose is not None and kit.rig is not None
    m = kit.rig.joints(style, style.pose)
    head = _posed_box(kit.extents.head_box(style.crest), m["head"], placement)
    body = _union(_posed_box(b, m[j], placement) for j, b in kit.rig.body_boxes.items())
    extent = kit.extents.props.get(style.prop)
    prop = None if extent is None else _posed_box(extent, m["prop"], placement)
    return FigureBoxes(head, body, prop)


def pose_union_boxes(
    style: CharacterStyle, placement: Placement, poses: Iterable[Pose]
) -> FigureBoxes:
    """Boxes that hold the figure in every one of ``poses`` (FR-48 over a motion)."""
    each = [figure_boxes(dataclasses.replace(style, pose=pose), placement) for pose in poses]
    props = [b.prop for b in each if b.prop is not None]
    return FigureBoxes(
        _union(b.head for b in each),
        _union(b.body for b in each),
        _union(props) if props else None,
    )


def figure_boxes(style: CharacterStyle, placement: Placement) -> FigureBoxes:
    """Head, body and prop boxes from the kit's extents; nothing is rendered. A posed style
    gets the boxes of its pose (M10)."""
    kit = kit_for(style)
    if style.pose is not None and kit.rig is not None:
        return _posed_boxes(style, placement, kit)
    extents = kit.extents
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
    order = kit.draw_order if names is None else names
    if style.pose is None or kit.rig is None:
        for name in order:
            kit.parts[name](cv, style, palette)
    else:
        _draw_posed(cv, kit.rig, kit.parts, style, palette, order)
    cv.restore()


def _draw_posed(
    cv: Canvas,
    rig: KitRig,
    parts: Mapping[str, PartFn],
    style: CharacterStyle,
    palette: Palette,
    order: Iterable[str],
) -> None:
    """Each part under its segment's joint transform (M10); split parts place themselves."""
    assert style.pose is not None
    joints = rig.joints(style, style.pose)
    for name in order:
        segment = rig.segments[name]
        cv.save()
        if segment != ROOT:
            apply_to(cv, joints[segment])
        rig.parts.get(name, parts[name])(cv, style, palette)
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
