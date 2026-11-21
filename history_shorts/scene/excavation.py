"""An archaeological excavation (Cổ Loa video: Đền Thượng 2004–2007).

Original procedural artwork. Modes under ``translate(x, y)`` and ``scale(scale)``:

* ``site``: a grid of square trenches laid out with pegs and string on the ground, seen in
  perspective, some squares dug out, small spoil heaps; front edge on y = 0, 900 units wide,
  back edge 260 units up. Pair it with a ``temple`` layer behind.
* ``trench``: a section through the find layers: soil strata (as in ``dig_site``), a black ash
  and charcoal band, the clay base of a casting furnace cut in half and stone mould pieces
  lying in the ash; ground surface on y = 0, 860 x 460 units.
"""

from __future__ import annotations

from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import ExcavationLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .dig_site import HALF_W, soil_section
from .registry import LayerDrawer, entry

OUTLINE: Final = "gold_dk"
OUTLINE_WIDTH: Final = 1.4

# --- site ----------------------------------------------------------------------------------------
FRONT_HALF: Final = 450.0
BACK: Final = (-260.0, 260.0)  # back edge y, half width
GRID: Final = (4, 3)  # columns, rows
GROUND_FILL: Final = ("brown", "brown_lt")
DUG: Final = ((1, 1), (2, 1), (1, 2), (2, 2), (3, 0))  # (column, row) squares dug out
DUG_FILL: Final = ("egg_gap", "deep_warm")
STRING_COLOR: Final = "egg"
STRING_ALPHA: Final = 0.8
PEG: Final = ("gold_dk", 16.0, 3.0)  # colour, height at the front, width
HEAPS: Final = ((-420.0, -40.0, 60.0, 22.0), (400.0, -150.0, 46.0, 18.0))  # x, y, rx, ry

# --- trench --------------------------------------------------------------------------------------
ASH: Final = (205.0, 255.0)  # top, bottom of the ash band
ASH_FILL: Final = "egg_gap"
CHARCOAL: Final = ("shadow", 60, (2.0, 5.0))  # colour, count, radius range
FURNACE_BASE: Final = (-200.0, 205.0, 120.0, 95.0)  # cx, rim y, half width, depth
FURNACE_FILL: Final = ("vermilion_dk", "brown_lt")
FURNACE_WALL: Final = 18.0
SLAG: Final = "gold_dk"
# mould pieces in the ash: x, y, width, height, tilt (radians)
MOULDS: Final = (
    (40.0, 222.0, 58.0, 30.0, 0.15),
    (130.0, 236.0, 50.0, 26.0, -0.2),
    (230.0, 220.0, 62.0, 30.0, 0.05),
    (320.0, 240.0, 46.0, 24.0, 0.3),
)
MOULD_FILL: Final = ("egg_tone", "brown_lt")
GROOVE: Final = "egg_gap"


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _grid_point(col: float, row: float) -> tuple[float, float]:
    cols, rows = GRID
    v = row / rows  # 0 at the front edge, 1 at the back
    back_y, back_half = BACK
    y = _lerp(0.0, back_y, v)
    half = _lerp(FRONT_HALF, back_half, v)
    return _lerp(-half, half, col / cols), y


def _quad(cv: Canvas, col: int, row: int, inset: float = 0.0) -> None:
    a = _grid_point(col + inset, row + inset)
    b = _grid_point(col + 1 - inset, row + inset)
    c = _grid_point(col + 1 - inset, row + 1 - inset)
    d = _grid_point(col + inset, row + 1 - inset)
    cv.M(*a).L(*b).L(*c).L(*d).Z()


def _site(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    cols, rows = GRID
    back_y, back_half = BACK
    cv.M(-FRONT_HALF - 30, 0.0).L(FRONT_HALF + 30, 0.0).L(back_half + 30, back_y).L(
        -back_half - 30, back_y
    )
    cv.Z().vgrad(back_y, 0.0, [(0, pal[GROUND_FILL[0]], 1), (1, pal[GROUND_FILL[1]], 1)]).fill()
    for col, row in DUG:
        _quad(cv, col, row, 0.08)
        cv.vgrad(_grid_point(0, row + 1)[1], _grid_point(0, row)[1],
                 [(0, pal[DUG_FILL[0]], 1), (1, pal[DUG_FILL[1]], 1)])  # fmt: skip
        cv.fill(keep=True).color(pal[OUTLINE]).stroke(1.0)
    for col in range(cols + 1):
        cv.M(*_grid_point(col, 0)).L(*_grid_point(col, rows))
    for row in range(rows + 1):
        cv.M(*_grid_point(0, row)).L(*_grid_point(cols, row))
    cv.color(pal[STRING_COLOR], STRING_ALPHA).stroke(1.2)
    color, height, width = PEG
    for row in range(rows + 1):
        size = _lerp(1.0, 0.6, row / rows)
        for col in range(cols + 1):
            x, y = _grid_point(col, row)
            cv.M(x, y).L(x, y - height * size).color(pal[color]).stroke(width * size)
    for x, y, rx, ry in HEAPS:
        cv.M(x - rx, y).C(x - rx * 0.4, y - ry * 2, x + rx * 0.4, y - ry * 2, x + rx, y).Z()
        cv.color(pal[GROUND_FILL[1]]).fill(keep=True).color(pal[OUTLINE]).stroke(1.0)


def _ash(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    pal = ctx.palette
    top, bottom = ASH
    cv.rect(-HALF_W, top, 2 * HALF_W, bottom - top).color(pal[ASH_FILL]).fill()
    color, count, (r0, r1) = CHARCOAL
    for _ in range(count):
        x = float(rng.uniform(-HALF_W + 8.0, HALF_W - 8.0))
        y = float(rng.uniform(top + 4.0, bottom - 4.0))
        r = float(rng.uniform(r0, r1))
        cv.ellipse(x, y, r * 1.6, r).color(pal[color], 0.85).fill()


def _furnace_base(cv: Canvas, ctx: DrawContext) -> None:
    """A clay bowl cut in half: thick fired wall, slag-filled hollow."""
    pal = ctx.palette
    cx, rim, half, depth = FURNACE_BASE
    cv.M(cx - half, rim).C(
        cx - half, rim + depth * 1.3, cx + half, rim + depth * 1.3, cx + half, rim
    )
    cv.Z().vgrad(rim, rim + depth, [(0, pal[FURNACE_FILL[0]], 1), (1, pal[FURNACE_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    inner = half - FURNACE_WALL
    d = depth - FURNACE_WALL
    cv.M(cx - inner, rim).C(cx - inner, rim + d * 1.3, cx + inner, rim + d * 1.3, cx + inner, rim)
    cv.Z().color(pal[ASH_FILL]).fill()
    cv.ellipse(cx, rim + d * 0.7, inner * 0.6, d * 0.22).color(pal[SLAG], 0.7).fill()


def _moulds(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x, y, w, h, tilt in MOULDS:
        cv.save()
        cv.translate(x, y)
        cv.rotate(tilt)
        cv.rect(-w / 2, -h / 2, w, h)
        cv.vgrad(-h / 2, h / 2, [(0, pal[MOULD_FILL[0]], 1), (1, pal[MOULD_FILL[1]], 1)])
        cv.fill(keep=True).color(pal[OUTLINE]).stroke(1.0)
        cv.M(-w * 0.35, 0.0).L(w * 0.3, -h * 0.12).L(w * 0.3, h * 0.12).Z()
        cv.color(pal[GROOVE]).fill()
        cv.restore()


def draw_excavation(
    img: FloatImage, layer: ExcavationLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """The trench grid, or the find-layer section with ash, furnace base and moulds."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    rng = ctx.rng(index)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    if layer.mode == "site":
        _site(cv, ctx)
    else:
        soil_section(cv, ctx, rng)
        _ash(cv, ctx, rng)
        _furnace_base(cv, ctx)
        _moulds(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(ExcavationLayer, draw_excavation)])
