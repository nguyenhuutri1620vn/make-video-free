"""Contact sheet of every role x facing x prop and every scene layer type (FR-04).

The character block comes first: one lacquer-ground sheet with a cell per role x facing x
prop. Each figure uses its role preset's crest, so crest variants are not part of the sheet. A
cell whose prop the role's costume kit cannot draw stays empty; the columns keep their places.

Below it, one cell per scene layer type (``LAYER_SPECS``). Each layer is drawn at full canvas
scale with the reference template's parameters onto its own 1080x1920 lacquer ground, and a
fixed crop of that render (``crop``, a 3:4 box in canvas pixels) is scaled into the cell. The
``characters`` layer type is the character block above.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from history_shorts.artwork.load import library_for
from history_shorts.artwork.model import Artwork
from history_shorts.artwork.path import path_bounds
from history_shorts.canvas import Canvas
from history_shorts.characters import ROLES, resolve_style
from history_shorts.characters.figure import Placement, draw_figure
from history_shorts.characters.kits import kit_named
from history_shorts.compose import GROUND_LAYER as SCENE_GROUND_LAYER
from history_shorts.compose import DrawContext, over, rng_for
from history_shorts.config import (
    ArrowheadsLayer,
    ArtworkLayer,
    BambooVillageLayer,
    BannersLayer,
    CharacterSpec,
    CitadelLayer,
    CrossbowLayer,
    DigSiteLayer,
    DrumLayer,
    ElephantLayer,
    ExcavationLayer,
    FallenFlagsLayer,
    FurnaceLayer,
    GongLayer,
    HorseLayer,
    LanternItem,
    LanternsLayer,
    Layer,
    LonePathLayer,
    LotusLayer,
    MapLayer,
    MouldLayer,
    PlinthLayer,
    RegaliaLayer,
    SailBoatLayer,
    ScrollLayer,
    StiltHouseLayer,
    TabletLayer,
    TempleLayer,
    Theme,
    TurtleLayer,
)
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import Box, FloatImage
from history_shorts.scene import draw_layers
from history_shorts.scene import templates as tpl
from history_shorts.scene_config import Prop
from history_shorts.text import font
from history_shorts.textures import lacquer_ground

PROPS: Final[tuple[Prop, ...]] = ("flag", "spear", "oar", "none")  # ancient_female columns
PROP_LABELS: Final[Mapping[str, str]] = MappingProxyType({"sword_sheathed": "sword"})  # fit a cell
# Column order of each kit's props (at most four columns fit the sheet width).
KIT_PROPS: Final[Mapping[str, tuple[Prop, ...]]] = MappingProxyType(
    {
        "ancient_female": PROPS,
        "warrior_male": ("flag", "spear", "sword_sheathed", "shield"),
    }
)
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
COLUMNS: Final = SHEET_W // CELL_W
CHARACTER_ROWS: Final = len(ROLES) * len(FACINGS)

# A reference lotus (no template places one): the flower on its leaf at 3x, mid-canvas.
GALLERY_LOTUS: Final = LotusLayer(x=540, y=1000, scale=3.0)
# A reference drum face (backlog #1), centred like the lotus.
GALLERY_DRUM: Final = DrumLayer(x=540, y=880, r=280)
GALLERY_GONG: Final = GongLayer(x=540, y=880, r=130)
GALLERY_TEMPLE: Final = TempleLayer(x=540, y=1100, scale=1.3)
GALLERY_SCROLL: Final = ScrollLayer(x=540, y=900, scale=1.3)
GALLERY_ELEPHANT: Final = ElephantLayer(x=520, y=1150, scale=1.6)
GALLERY_STILT_HOUSE: Final = StiltHouseLayer(x=600, y=1150, scale=1.4)
GALLERY_BANNERS: Final = BannersLayer(y=1180, rows=3)
GALLERY_REGALIA: Final = RegaliaLayer(x=540, y=1160, scale=1.6)
GALLERY_FALLEN_FLAGS: Final = FallenFlagsLayer(x=540, y=1150, scale=1.3)
GALLERY_SAIL_BOAT: Final = SailBoatLayer(x=540, y=1120, scale=1.4)
GALLERY_LONE_PATH: Final = LonePathLayer(y=1300, depth=500)
GALLERY_LANTERNS: Final = LanternsLayer(
    items=(LanternItem(430, 960, 1.6), LanternItem(640, 1000, 2.0), LanternItem(520, 1080, 2.6))
)
GALLERY_TABLET: Final = TabletLayer(x=540, y=1180, scale=1.5)
GALLERY_HORSE: Final = HorseLayer(x=530, y=1160, scale=1.6)
GALLERY_CITADEL: Final = CitadelLayer(x=540, y=980, scale=0.85)
GALLERY_BAMBOO_VILLAGE: Final = BambooVillageLayer(x=540, y=1200, scale=1.05)
GALLERY_FURNACE: Final = FurnaceLayer(x=540, y=1200, scale=1.2)
GALLERY_PLINTH: Final = PlinthLayer(x=540, y=1200, scale=1.5)
GALLERY_ARROWHEADS: Final = ArrowheadsLayer(x=540, y=1150, scale=1.6, arrangement="pair")
GALLERY_MOULD: Final = MouldLayer(x=540, y=1200, scale=1.3)
GALLERY_DIG_SITE: Final = DigSiteLayer(x=540, y=800, scale=0.8, mode="hoard")
GALLERY_CROSSBOW: Final = CrossbowLayer(x=540, y=1200, scale=1.6, mode="claw")
GALLERY_TURTLE: Final = TurtleLayer(x=520, y=1150, scale=1.0)
GALLERY_EXCAVATION: Final = ExcavationLayer(x=540, y=1150, scale=0.75, mode="site")
GALLERY_MAP: Final = MapLayer(x=270, y=560, w=540, h=600, dots=((0.36, 0.38),), arrow=True)
# One entry per cell, in reading order: (label, layer type name, reference layer, crop).
# The crop is the 3:4 region of the full-canvas render that is scaled into the 270x360 cell. It
# is placed so the art sits in the upper three quarters and the label stays on bare ground.
# ``peaks`` appears twice, once per fill; ``characters`` is the character block above.
LAYER_SPECS: Final[tuple[tuple[str, str, Layer, Box], ...]] = (
    ("sun", "sun", tpl.GROUP_SUN, Box(165, 250, 915, 1250)),
    ("moon", "moon", tpl.LANDSCAPE_MOON, Box(590, 258, 950, 738)),
    ("clouds", "clouds", tpl.GROUP_CLOUDS, Box(135, 174, 405, 534)),
    ("mountains", "mountains", tpl.GROUP_MOUNTAINS, Box(315, 730, 765, 1330)),
    ("peaks gradient", "peaks", tpl.LANDSCAPE_BACK_PEAKS, Box(240, 390, 840, 1190)),
    ("peaks eggshell", "peaks", tpl.LANDSCAPE_MID_PEAKS, Box(0, 515, 600, 1315)),
    ("hills left", "hills", tpl.GROUP_HILL_LEFT, Box(0, 750, 450, 1350)),
    ("river", "river", tpl.LANDSCAPE_RIVER, Box(315, 845, 765, 1445)),
    ("ground", "ground", tpl.GROUP_GROUND, Box(390, 958, 690, 1358)),
    ("boat", "boat", tpl.LANDSCAPE_BOATS[0], Box(140, 780, 440, 1180)),
    ("birds", "birds", tpl.LANDSCAPE_BIRDS, Box(215, 297, 455, 617)),
    ("lotus", "lotus", GALLERY_LOTUS, Box(360, 758, 720, 1238)),
    ("drum", "drum", GALLERY_DRUM, Box(240, 580, 840, 1380)),
    ("gong", "gong", GALLERY_GONG, Box(240, 540, 840, 1340)),
    ("temple", "temple", GALLERY_TEMPLE, Box(240, 660, 840, 1460)),
    ("map", "map", GALLERY_MAP, Box(240, 530, 840, 1330)),
    ("scroll", "scroll", GALLERY_SCROLL, Box(240, 560, 840, 1360)),
    ("elephant", "elephant", GALLERY_ELEPHANT, Box(240, 600, 840, 1400)),
    ("stilt house", "stilt_house", GALLERY_STILT_HOUSE, Box(240, 560, 840, 1360)),
    ("banners", "banners", GALLERY_BANNERS, Box(240, 560, 840, 1360)),
    ("regalia", "regalia", GALLERY_REGALIA, Box(240, 600, 840, 1400)),
    ("fallen flags", "fallen_flags", GALLERY_FALLEN_FLAGS, Box(240, 620, 840, 1420)),
    ("sail boat", "sail_boat", GALLERY_SAIL_BOAT, Box(240, 560, 840, 1360)),
    ("lone path", "lone_path", GALLERY_LONE_PATH, Box(240, 560, 840, 1360)),
    ("lanterns", "lanterns", GALLERY_LANTERNS, Box(240, 600, 840, 1400)),
    ("tablet", "tablet", GALLERY_TABLET, Box(240, 580, 840, 1380)),
    ("horse", "horse", GALLERY_HORSE, Box(240, 600, 840, 1400)),
    ("citadel", "citadel", GALLERY_CITADEL, Box(240, 580, 840, 1380)),
    ("bamboo village", "bamboo_village", GALLERY_BAMBOO_VILLAGE, Box(240, 600, 840, 1400)),
    ("furnace", "furnace", GALLERY_FURNACE, Box(240, 620, 840, 1420)),
    ("plinth", "plinth", GALLERY_PLINTH, Box(240, 560, 840, 1360)),
    ("arrowheads", "arrowheads", GALLERY_ARROWHEADS, Box(240, 640, 840, 1440)),
    ("mould", "mould", GALLERY_MOULD, Box(240, 500, 840, 1300)),
    ("dig site", "dig_site", GALLERY_DIG_SITE, Box(150, 560, 930, 1600)),
    ("crossbow", "crossbow", GALLERY_CROSSBOW, Box(240, 600, 840, 1400)),
    ("turtle", "turtle", GALLERY_TURTLE, Box(240, 700, 840, 1500)),
    ("excavation", "excavation", GALLERY_EXCAVATION, Box(150, 720, 930, 1760)),
)
LAYER_ROWS: Final = -(-len(LAYER_SPECS) // COLUMNS)  # ceiling division

SHEET_H: Final = HEADER_H + (CHARACTER_ROWS + LAYER_ROWS) * CELL_H


@dataclass(frozen=True, slots=True)
class GalleryCell:
    """One cell: its box on the sheet and the figure standing in it."""

    role: str
    facing: int
    prop: Prop
    box: Box
    placement: Placement


@dataclass(frozen=True, slots=True)
class LayerCell:
    """One layer-type cell: its box on the sheet and what is drawn in it."""

    label: str
    type_name: str  # a key of ``LAYER_TYPES``
    layer: Layer
    crop: Box
    box: Box


def layer_cells() -> list[LayerCell]:
    """The layer-type cells below the character block, row by row, four to a row."""
    cells: list[LayerCell] = []
    for k, (label, type_name, layer, crop) in enumerate(LAYER_SPECS):
        row, column = divmod(k, COLUMNS)
        x0 = column * CELL_W
        y0 = HEADER_H + (CHARACTER_ROWS + row) * CELL_H
        cells.append(
            LayerCell(label, type_name, layer, crop, Box(x0, y0, x0 + CELL_W, y0 + CELL_H))
        )
    return cells


def grid_cells() -> list[GalleryCell]:
    """Every cell, row by row: roles in preset order, +1 then -1, props left to right.

    Props the role's kit cannot draw get no cell.
    """
    cells: list[GalleryCell] = []
    for role_index, role in enumerate(ROLES):
        drawable = kit_named(ROLES[role].kit).props
        columns = KIT_PROPS.get(ROLES[role].kit, PROPS)
        for facing_index, facing in enumerate(FACINGS):
            row = role_index * len(FACINGS) + facing_index
            y0 = HEADER_H + row * CELL_H
            for column, prop in enumerate(columns):
                if prop not in drawable:
                    continue
                x0 = column * CELL_W
                box = Box(x0, y0, x0 + CELL_W, y0 + CELL_H)
                placement = Placement(x0 + CELL_W / 2, box.y1 - FEET_MARGIN, FIGURE_H, facing)
                cells.append(GalleryCell(role, facing, prop, box, placement))
    return cells


def cell_label(cell: GalleryCell | LayerCell) -> str:
    if isinstance(cell, LayerCell):
        return cell.label
    return f"{cell.role} · {cell.facing:+d} · {PROP_LABELS.get(cell.prop, cell.prop)}"


def _draw_separators(cv: Canvas, theme: Theme) -> None:
    cv.color(theme.palette[SEPARATOR_COLOR], SEPARATOR_ALPHA)
    for column in range(1, len(PROPS)):
        cv.M(column * CELL_W, HEADER_H).L(column * CELL_W, SHEET_H)
        cv.stroke(SEPARATOR_WIDTH)
    for row in range(CHARACTER_ROWS + LAYER_ROWS + 1):
        y = HEADER_H + row * CELL_H
        cv.M(0, y).L(SHEET_W, y)
        cv.stroke(SEPARATOR_WIDTH)


def _draw_figures(cv: Canvas, theme: Theme, cells: list[GalleryCell]) -> None:
    for cell in cells:
        style = resolve_style(CharacterSpec(role=cell.role, prop=cell.prop), theme.palette)
        draw_figure(cv, style, cell.placement, theme.palette)


def label_font(theme: Theme) -> ImageFont.FreeTypeFont:
    return font(theme.fonts.tag, round(theme.type_scale.tag * LABEL_SCALE))


def label_anchor(cell: GalleryCell | LayerCell) -> tuple[float, float]:
    """Where the cell's label is centred (Pillow anchor ``mm``)."""
    return (cell.box.x0 + cell.box.x1) / 2, cell.box.y1 - LABEL_MARGIN


def label_box(theme: Theme, cell: GalleryCell | LayerCell) -> Box:
    """Pixel box of the cell's label, as drawn (anchored at its middle)."""
    cx, cy = label_anchor(cell)
    x0, y0, x1, y1 = label_font(theme).getbbox(cell_label(cell), anchor="mm")
    return Box(cx + x0, cy + y0, cx + x1, cy + y1)


def _draw_labels(img: Image.Image, theme: Theme, cells: Sequence[GalleryCell | LayerCell]) -> None:
    draw = ImageDraw.Draw(img)
    colour = theme.palette[TEXT_COLOR]
    header_font = font(theme.fonts.title, theme.type_scale.tag)
    draw.text((SHEET_W / 2, HEADER_H / 2), theme.name, font=header_font, fill=colour, anchor="mm")
    text_font = label_font(theme)
    for cell in cells:
        draw.text(
            label_anchor(cell),
            cell_label(cell),
            font=text_font,
            fill=colour,
            anchor="mm",
        )


def canvas_ground(theme: Theme) -> FloatImage:
    """The plain 1080x1920 lacquer ground every layer cell is drawn on."""
    return lacquer_ground(
        rng_for(theme.seed, 0, GROUND_LAYER), theme.palette, width=CANVAS_W, height=CANVAS_H
    )


def scale_crop(full: FloatImage, crop: Box) -> FloatImage:
    """``crop`` of a full-canvas buffer scaled to one cell (Lanczos, deterministic)."""
    image = Image.fromarray((np.clip(full, 0, 1) * 255).astype(np.uint8), "RGB")
    box = (crop.x0, crop.y0, crop.x1, crop.y1)
    small = image.resize((CELL_W, CELL_H), Image.Resampling.LANCZOS, box=box)
    return np.asarray(np.asarray(small, dtype=np.float32) / 255, dtype=np.float32)


def layer_art(theme: Theme, ground: FloatImage, cell: LayerCell) -> FloatImage:
    """The cell's pixels: the layer drawn at canvas scale on ``ground``, cropped and scaled."""
    ctx = DrawContext(theme, theme.palette, theme.seed, SCENE_GROUND_LAYER)
    return scale_crop(draw_layers(ground.copy(), [cell.layer], ctx), cell.crop)


def _paste_layer_cells(buffer: FloatImage, theme: Theme) -> None:
    ground = canvas_ground(theme)
    for cell in layer_cells():
        y0, x0 = int(cell.box.y0), int(cell.box.x0)
        buffer[y0 : y0 + CELL_H, x0 : x0 + CELL_W] = layer_art(theme, ground, cell)


def render_gallery(theme: Theme) -> Image.Image:
    """The 1080x6600 contact sheet: layer cells, separators and figures, then the text."""
    cells = grid_cells()
    ground = lacquer_ground(
        rng_for(theme.seed, 0, GROUND_LAYER), theme.palette, width=SHEET_W, height=SHEET_H
    )
    _paste_layer_cells(ground, theme)
    cv = Canvas(SHEET_W, SHEET_H)
    _draw_separators(cv, theme)
    _draw_figures(cv, theme, cells)
    buffer = over(ground, cv)
    img = Image.fromarray((np.clip(buffer, 0, 1) * 255).astype(np.uint8), "RGB")
    _draw_labels(img, theme, [*cells, *layer_cells()])
    return img


# --------------------------------------------------------------------------------------
# Artwork files (M11): previews and the library sheet
# --------------------------------------------------------------------------------------

PREVIEW_CELL_W: Final = 540  # one preview cell: half the canvas width
PREVIEW_CELL_H: Final = 960
PREVIEW_FILL: Final = 0.8  # the object takes this share of the cell
PREVIEW_GROUND_Y: Final = 1500  # where the object stands on the full canvas before cropping
SHEET_COLUMNS: Final = 2


def _artwork_crop(art: Artwork, scale: float) -> Box:
    """The canvas box (cell aspect) around ``art`` drawn at ``scale`` at the preview spot."""
    bounds = [path_bounds(part.ops) for part in art.parts if part.ops]
    x0 = min(b[0] for b in bounds) * scale + CANVAS_W / 2
    x1 = max(b[2] for b in bounds) * scale + CANVAS_W / 2
    y0 = min(b[1] for b in bounds) * scale + PREVIEW_GROUND_Y
    y1 = max(b[3] for b in bounds) * scale + PREVIEW_GROUND_Y
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half_w, half_h = PREVIEW_CELL_W / 2, PREVIEW_CELL_H / 2
    return Box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def _artwork_scale(art: Artwork) -> float:
    bounds = [path_bounds(part.ops) for part in art.parts if part.ops]
    w = max(b[2] for b in bounds) - min(b[0] for b in bounds)
    h = max(b[3] for b in bounds) - min(b[1] for b in bounds)
    return min(
        PREVIEW_FILL * PREVIEW_CELL_W / max(w, 1e-6), PREVIEW_FILL * PREVIEW_CELL_H / max(h, 1e-6)
    )


def artwork_cell(theme: Theme, name: str, phase: float) -> FloatImage:
    """One preview cell: ``name`` at loop ``phase`` on the lacquer ground."""
    from history_shorts.compose import EggshellCache
    from history_shorts.scene.artwork import draw_artwork_at

    art = library_for(theme).get(name, theme.palette)
    scale = _artwork_scale(art)
    layer = ArtworkLayer(name, CANVAS_W / 2, PREVIEW_GROUND_Y, scale, 1)
    ctx = DrawContext(theme, theme.palette, theme.seed, 0, EggshellCache())
    full = draw_artwork_at(canvas_ground(theme), layer, ctx, 1, phase)
    box = _artwork_crop(art, scale)
    image = Image.fromarray((np.clip(full, 0, 1) * 255).astype(np.uint8), "RGB")
    cell = image.crop((round(box.x0), round(box.y0), round(box.x1), round(box.y1)))
    return np.asarray(np.asarray(cell, dtype=np.float32) / 255, dtype=np.float32)


def artwork_preview(theme: Theme, name: str, phases: int = 4) -> Image.Image:
    """``phases`` cells side by side: the object at phase 0, 1/n, 2/n, ..."""
    cells = [artwork_cell(theme, name, k / phases) for k in range(phases)]
    strip = np.concatenate(cells, axis=1)
    return Image.fromarray((np.clip(strip, 0, 1) * 255).astype(np.uint8), "RGB")


def artwork_sheet(theme: Theme) -> Image.Image | None:
    """Every library item at phase 0, two to a row, titled; None for an empty library."""
    library = library_for(theme)
    names = library.names()
    if not names:
        return None
    rows = -(-len(names) // SHEET_COLUMNS)
    sheet = Image.new("RGB", (SHEET_COLUMNS * PREVIEW_CELL_W, rows * PREVIEW_CELL_H))
    font = label_font(theme)
    draw = ImageDraw.Draw(sheet)
    for k, name in enumerate(names):
        row, column = divmod(k, SHEET_COLUMNS)
        cell = artwork_cell(theme, name, 0.0)
        tile = Image.fromarray((np.clip(cell, 0, 1) * 255).astype(np.uint8), "RGB")
        x, y = column * PREVIEW_CELL_W, row * PREVIEW_CELL_H
        sheet.paste(tile, (x, y))
        title = library.get(name, theme.palette).title
        draw.text((x + 16, y + 16), f"{name} · {title}", font=font, fill=theme.palette["gold_lt"])
    return sheet
