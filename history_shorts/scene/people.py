"""The characters layer: figures placed by a formation or by explicit items (FR-46, FR-47)."""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.characters import resolve_style
from history_shorts.characters.figure import draw_figure
from history_shorts.characters.formations import LINE_HEIGHT, PlacedCharacter, place
from history_shorts.compose import DrawContext, over
from history_shorts.config import CharactersLayer, Palette
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

# Height of an explicitly placed item that gives none: the middle-row height. ``place``
# applies it, so drawing and the overlap checks agree.
DEFAULT_CHARACTER_HEIGHT: Final = LINE_HEIGHT


def placed_characters(layer: CharactersLayer) -> list[PlacedCharacter]:
    """The layer's characters with canvas placements, in draw order (back rows first).

    The single source of placement: drawing and the FR-48 checks both call this. Raises
    ``ValueError`` for a wrong formation count or an item without ``x`` and no formation.
    """
    return place(layer.formation, layer.items, layer.baseline)


def draw_figures(cv: Canvas, placed: list[PlacedCharacter], palette: Palette) -> None:
    """Draw ``placed`` onto ``cv`` in the order given."""
    for item in placed:
        draw_figure(cv, resolve_style(item.spec, palette), item.placement, palette)


def draw_characters(
    img: FloatImage, layer: CharactersLayer, ctx: DrawContext, index: int
) -> FloatImage:
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw_figures(cv, placed_characters(layer), ctx.palette)
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(CharactersLayer, draw_characters)])
