"""The characters layer: figures placed by a formation or by explicit items (FR-46, FR-47)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.characters import resolve_style
from history_shorts.characters.figure import draw_figure
from history_shorts.characters.formations import LINE_HEIGHT, PlacedCharacter, place
from history_shorts.characters.idle import idle_params, idle_pose
from history_shorts.characters.pose import Pose
from history_shorts.compose import DrawContext, over
from history_shorts.config import CharactersLayer, Palette
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, PhaseDrawer, entry, phase_entry

# Height of an explicitly placed item that gives none: the middle-row height. ``place``
# applies it, so drawing and the overlap checks agree.
DEFAULT_CHARACTER_HEIGHT: Final = LINE_HEIGHT
# RNG key of a character's motion: apart from every layer's drawing RNG (M10).
CHAR_KEY: Final = 700
CHAR_STRIDE: Final = 16  # characters per layer the keys leave room for


def placed_characters(layer: CharactersLayer) -> list[PlacedCharacter]:
    """The layer's characters with canvas placements, in draw order (back rows first).

    The single source of placement: drawing and the FR-48 checks both call this. Raises
    ``ValueError`` for a wrong formation count or an item without ``x`` and no formation.
    """
    return place(layer.formation, layer.items, layer.baseline)


def draw_figures(
    cv: Canvas,
    placed: list[PlacedCharacter],
    palette: Palette,
    poses: Sequence[Pose] | None = None,
) -> None:
    """Draw ``placed`` onto ``cv`` in the order given; with ``poses``, posed (M10)."""
    for k, item in enumerate(placed):
        style = resolve_style(item.spec, palette)
        if poses is not None:
            style = dataclasses.replace(style, pose=poses[k])
        draw_figure(cv, style, item.placement, palette)


def idle_poses(ctx: DrawContext, index: int, count: int, phase: float) -> list[Pose]:
    """Each of ``count`` characters of layer ``index`` at idle loop ``phase``."""
    spec = ctx.theme.living
    period = spec.idle_loop_seconds
    return [
        idle_pose(
            idle_params(ctx.rng(CHAR_KEY + index * CHAR_STRIDE + k)), phase * period, period, spec
        )  # fmt: skip
        for k in range(count)
    ]


def draw_characters(
    img: FloatImage, layer: CharactersLayer, ctx: DrawContext, index: int
) -> FloatImage:
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw_figures(cv, placed_characters(layer), ctx.palette)
    return over(img, cv)


def draw_characters_posed(
    img: FloatImage, layer: CharactersLayer, ctx: DrawContext, poses: Sequence[Pose]
) -> FloatImage:
    """The characters, each in its pose from ``poses`` (draw order)."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw_figures(cv, placed_characters(layer), ctx.palette, poses)
    return over(img, cv)


def draw_characters_at(
    img: FloatImage, layer: CharactersLayer, ctx: DrawContext, index: int, phase: float
) -> FloatImage:
    """The characters breathing and swaying at idle loop ``phase`` (M10)."""
    placed = placed_characters(layer)
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw_figures(cv, placed, ctx.palette, idle_poses(ctx, index, len(placed), phase))
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(CharactersLayer, draw_characters)])
PHASE_DRAWERS: dict[type, PhaseDrawer] = dict([phase_entry(CharactersLayer, draw_characters_at)])
