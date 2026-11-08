"""Contact sheet of every role x facing x prop on lacquer ground (FR-04).

Layer-type rows are added with the scene layers (Task 20). Each figure uses its role
preset's crest, so crest variants are not part of the sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, get_args

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from history_shorts.canvas import Canvas
from history_shorts.characters import ROLES, resolve_style
from history_shorts.characters.figure import Placement, draw_figure
from history_shorts.compose import over, rng_for
from history_shorts.config import CharacterSpec, Theme
from history_shorts.layout import CANVAS_W
from history_shorts.primitives import Box
from history_shorts.scene_config import Prop
from history_shorts.text import font
from history_shorts.textures import lacquer_ground

PROPS: Final[tuple[Prop, ...]] = get_args(Prop)  # flag, spear, oar, none: the columns
FACINGS: Final[tuple[int, ...]] = (1, -1)  # per role, in this order: the rows

CELL_W: Final = 270
CELL_H: Final = 360
HEADER_H: Final = 120
# The tallest prop (spear) reaches 1.44 figure heights above the feet and the oar blade
# 0.16 below them, so the figure is sized to keep the spear tip inside the cell while
# FEET_MARGIN leaves room under the oar blade for the label.
FIGURE_H: Final = 195
FEET_MARGIN: Final = 64  # feet sit this far above the cell bottom
LABEL_MARGIN: Final = 14  # label centre sits this far above the cell bottom
LABEL_SCALE: Final = 0.6  # label size = type_scale.tag * LABEL_SCALE

SEPARATOR_COLOR: Final = "gold_dk"
SEPARATOR_ALPHA: Final = 0.5
SEPARATOR_WIDTH: Final = 1
TEXT_COLOR: Final = "gold_lt"
GROUND_LAYER: Final = 0  # rng_for(theme.seed, 0, 0)

SHEET_W: Final = CANVAS_W
SHEET_H: Final = HEADER_H + len(ROLES) * len(FACINGS) * CELL_H
assert SHEET_W == len(PROPS) * CELL_W


@dataclass(frozen=True, slots=True)
class GalleryCell:
    """One cell: its box on the sheet and the figure standing in it."""

    role: str
    facing: int
    prop: Prop
    box: Box
    placement: Placement


def grid_cells() -> list[GalleryCell]:
    """Every cell, row by row: roles in preset order, +1 then -1, props left to right."""
    cells: list[GalleryCell] = []
    for role_index, role in enumerate(ROLES):
        for facing_index, facing in enumerate(FACINGS):
            row = role_index * len(FACINGS) + facing_index
            y0 = HEADER_H + row * CELL_H
            for column, prop in enumerate(PROPS):
                x0 = column * CELL_W
                box = Box(x0, y0, x0 + CELL_W, y0 + CELL_H)
                placement = Placement(x0 + CELL_W / 2, box.y1 - FEET_MARGIN, FIGURE_H, facing)
                cells.append(GalleryCell(role, facing, prop, box, placement))
    return cells


def cell_label(cell: GalleryCell) -> str:
    return f"{cell.role} · {cell.facing:+d} · {cell.prop}"


def _draw_separators(cv: Canvas, theme: Theme) -> None:
    cv.color(theme.palette[SEPARATOR_COLOR], SEPARATOR_ALPHA)
    for column in range(1, len(PROPS)):
        cv.M(column * CELL_W, HEADER_H).L(column * CELL_W, SHEET_H)
        cv.stroke(SEPARATOR_WIDTH)
    rows = len(ROLES) * len(FACINGS)
    for row in range(rows + 1):
        y = HEADER_H + row * CELL_H
        cv.M(0, y).L(SHEET_W, y)
        cv.stroke(SEPARATOR_WIDTH)


def _draw_figures(cv: Canvas, theme: Theme, cells: list[GalleryCell]) -> None:
    for cell in cells:
        style = resolve_style(CharacterSpec(role=cell.role, prop=cell.prop), theme.palette)
        draw_figure(cv, style, cell.placement, theme.palette)


def label_font(theme: Theme) -> ImageFont.FreeTypeFont:
    return font(theme.fonts.tag, round(theme.type_scale.tag * LABEL_SCALE))


def label_box(theme: Theme, cell: GalleryCell) -> Box:
    """Pixel box of the cell's label, as drawn (anchored at its middle)."""
    cx, cy = (cell.box.x0 + cell.box.x1) / 2, cell.box.y1 - LABEL_MARGIN
    x0, y0, x1, y1 = label_font(theme).getbbox(cell_label(cell), anchor="mm")
    return Box(cx + x0, cy + y0, cx + x1, cy + y1)


def _draw_labels(img: Image.Image, theme: Theme, cells: list[GalleryCell]) -> None:
    draw = ImageDraw.Draw(img)
    colour = theme.palette[TEXT_COLOR]
    header_font = font(theme.fonts.title, theme.type_scale.tag)
    draw.text((SHEET_W / 2, HEADER_H / 2), theme.name, font=header_font, fill=colour, anchor="mm")
    text_font = label_font(theme)
    for cell in cells:
        draw.text(
            ((cell.box.x0 + cell.box.x1) / 2, cell.box.y1 - LABEL_MARGIN),
            cell_label(cell),
            font=text_font,
            fill=colour,
            anchor="mm",
        )


def render_gallery(theme: Theme) -> Image.Image:
    """The 1080x3000 contact sheet: separators and figures on one canvas, then the text."""
    cells = grid_cells()
    ground = lacquer_ground(
        rng_for(theme.seed, 0, GROUND_LAYER), theme.palette, width=SHEET_W, height=SHEET_H
    )
    cv = Canvas(SHEET_W, SHEET_H)
    _draw_separators(cv, theme)
    _draw_figures(cv, theme, cells)
    buffer = over(ground, cv)
    img = Image.fromarray((np.clip(buffer, 0, 1) * 255).astype(np.uint8), "RGB")
    _draw_labels(img, theme, cells)
    return img
