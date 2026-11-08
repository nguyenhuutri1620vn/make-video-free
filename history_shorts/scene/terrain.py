"""Terrain layers: far mountains, karst peaks, hills, river and ground (FR-34 to FR-36)."""

from __future__ import annotations

from typing import Final, Literal

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, fill_mask, over
from history_shorts.config import (
    GroundLayer,
    HillsLayer,
    MountainsLayer,
    PeakItem,
    PeaksLayer,
    RiverLayer,
)
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.textures import eggshell

from .registry import WHITE, LayerDrawer, entry

# -- far mountains -----------------------------------------------------------------------
MOUNTAIN_GRADIENT_TOP: Final = -100.0  # gradient runs from y + top to y + bottom
MOUNTAIN_GRADIENT_BOTTOM: Final = 200.0
MOUNTAIN_FOOT: Final = 220.0  # the filled shape closes this far below y
MOUNTAIN_TOP_COLOR: Final = "vermilion_dk"
MOUNTAIN_BASE_COLOR: Final = "mountain_base"
RIDGE_COLOR: Final = "gold"
RIDGE_WIDTH: Final = 2.5

# -- peaks -------------------------------------------------------------------------------
PEAK_BASE_OVERLAP: Final = 2.0  # the base sits this far below y so neighbours leave no seam
PEAK_SHADE_STEP: Final = 0.06  # each later (nearer) peak is this much darker at its top
PEAK_TOP_COLOR: Final = "vermilion_dk"
PEAK_BASE_COLOR: Final = "peak_base"
PEAK_OUTLINE_COLOR: Final = "gold"
PEAK_GRADIENT_OUTLINE_WIDTH: Final = 1.8
PEAK_EGGSHELL_OUTLINE_WIDTH: Final = 2.5

# -- hills -------------------------------------------------------------------------------
HILL_OUTLINE_COLOR: Final = "gold"
HILL_OUTLINE_WIDTH: Final = 2.5

# -- river -------------------------------------------------------------------------------
RIVER_TOP_COLOR: Final = "river_top"
RIVER_DEEP_COLOR: Final = "black"
RIVER_MID_STOP: Final = 0.65
RIVER_MID_ALPHA: Final = 0.9
RIVER_BANK_COLOR: Final = "gold"
RIVER_BANK_WIDTH: Final = 2.0
WAVE_ROWS: Final = 6  # fixed: the river's height only stretches its gradient
WAVE_ROW_STEP: Final = 30.0  # row k (1-based) sits at y + 30 k
WAVE_COLORS: Final = ("gold", "gold_dk")  # alternate by row
WAVE_X_START: Final = -60.0
WAVE_ROW_OFFSET: Final = 45.0  # odd rows shift right by this much
WAVE_X_STEP: Final = 90.0
WAVE_X_END: Final = 1120.0
WAVE_CREST: Final = (15.0, -8.0, 35.0, -8.0, 50.0, 0.0)  # control points relative to the start
WAVE_WIDTH: Final = 1.6
WAVE_ALPHA: Final = 0.75

# -- ground ------------------------------------------------------------------------------
GROUND_TOP_COLOR: Final = "vermilion_dk"
GROUND_BOTTOM_COLOR: Final = "black"
GROUND_LINE_COLOR: Final = "gold"
GROUND_LINE_WIDTH: Final = 3.0
CURL_COLOR: Final = "gold_dk"
CURL_WIDTH: Final = 2.0
CURL_X_START: Final = -40.0
CURL_X_END: Final = 1120.0
CURL_X_STEP: Final = 120.0
CURL_START_DY: Final = 34.0
CURL_FIRST: Final = (10.0, 12.0, 46.0, 12.0, 56.0, 30.0)  # (dx, dy) control points from (x, y)
CURL_SECOND: Final = (60.0, 38.0, 48.0, 44.0, 42.0, 36.0)

Side = Literal["left", "right"]


# -- paths -------------------------------------------------------------------------------


def ridge_path(cv: Canvas, y: float, amp: float) -> None:
    """The far-mountain skyline as an open path from x = 0 to x = 1080."""
    cv.M(0, y + 80 * amp).C(80, y - 20 * amp, 140, y - 90 * amp, 210, y - 40 * amp)
    cv.C(270, y + 5 * amp, 320, y - 60 * amp, 410, y - 20 * amp)
    cv.C(480, y + 15 * amp, 560, y - 100 * amp, 650, y - 50 * amp)
    cv.C(730, y - 5 * amp, 790, y - 80 * amp, 880, y - 40 * amp)
    cv.C(960, y - 5 * amp, 1020, y - 70 * amp, 1080, y - 30 * amp)


def peak_path(cv: Canvas, item: PeakItem, y: float) -> None:
    """One closed karst peak: a single path, never merged with its neighbours (FR-35)."""
    px, ph, pw = item.x, item.height, item.width
    base = y + PEAK_BASE_OVERLAP
    cv.M(px - pw, base).C(px - pw * 0.6, y - ph * 0.5, px - pw * 0.55, y - ph, px, y - ph)
    cv.C(px + pw * 0.55, y - ph, px + pw * 0.6, y - ph * 0.5, px + pw, base).Z()


def hill_path(cv: Canvas, side: Side, base: float, top: float) -> None:
    """A closed hill hugging the left or right canvas edge."""
    if side == "left":
        cv.M(0, base).L(0, top + 40).C(60, top - 10, 150, top - 20, 220, top + 60)
        cv.C(260, top + 110, 300, base - 40, 340, base).Z()
    else:
        cv.M(1080, base).L(1080, top + 20).C(1010, top - 30, 930, top - 10, 860, top + 70)
        cv.C(820, top + 120, 780, base - 40, 740, base).Z()


# -- drawers -----------------------------------------------------------------------------


def draw_mountains(
    img: FloatImage, layer: MountainsLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Vermilion silhouette fading to the mountain base colour, with a gold ridge line."""
    y, pal = layer.y, ctx.palette
    cv = Canvas(CANVAS_W, CANVAS_H)
    ridge_path(cv, y, layer.amp)
    cv.L(CANVAS_W, y + MOUNTAIN_FOOT).L(0, y + MOUNTAIN_FOOT).Z()
    top, bottom = y + MOUNTAIN_GRADIENT_TOP, y + MOUNTAIN_GRADIENT_BOTTOM
    cv.vgrad(top, bottom, [(0, pal[MOUNTAIN_TOP_COLOR], 1), (1, pal[MOUNTAIN_BASE_COLOR], 1)])
    cv.fill()
    ridge_path(cv, y, layer.amp)
    cv.color(pal[RIDGE_COLOR]).stroke(RIDGE_WIDTH)
    return over(img, cv)


def _gradient_peaks(img: FloatImage, layer: PeaksLayer, ctx: DrawContext) -> FloatImage:
    pal = ctx.palette
    cv = Canvas(CANVAS_W, CANVAS_H)
    for i, item in enumerate(layer.items):
        shade = 1.0 - i * PEAK_SHADE_STEP
        top = tuple(int(v * shade) for v in pal[PEAK_TOP_COLOR])
        peak_path(cv, item, layer.y)
        cv.vgrad(
            layer.y - item.height,
            layer.y,
            [(0, (top[0], top[1], top[2]), 1), (1, pal[PEAK_BASE_COLOR], 1)],
        ).fill()
        peak_path(cv, item, layer.y)  # outline now, so the next peak's fill can hide its overlap
        cv.color(pal[PEAK_OUTLINE_COLOR]).stroke(PEAK_GRADIENT_OUTLINE_WIDTH)
    return over(img, cv)


def _eggshell_peaks(img: FloatImage, layer: PeaksLayer, ctx: DrawContext, index: int) -> FloatImage:
    spec = ctx.theme.textures.eggshell
    cell = spec.cell if layer.cell is None else layer.cell
    gap = spec.gap if layer.gap is None else layer.gap
    for item in layer.items:
        shape = Canvas(CANVAS_W, CANVAS_H)
        shape.color(WHITE)
        peak_path(shape, item, layer.y)
        shape.fill()
        mask = shape.mask()
        tex = eggshell(ctx.eggshell_rng(index, mask), mask, ctx.palette, cell, gap)
        img = fill_mask(img, tex, mask)
        line = Canvas(CANVAS_W, CANVAS_H)
        peak_path(line, item, layer.y)
        line.color(ctx.palette[PEAK_OUTLINE_COLOR]).stroke(PEAK_EGGSHELL_OUTLINE_WIDTH)
        img = over(img, line)
    return img


def draw_peaks(img: FloatImage, layer: PeaksLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Peaks back to front in list order: each is filled and outlined before the next (FR-35)."""
    if layer.fill == "eggshell":
        return _eggshell_peaks(img, layer, ctx, index)
    return _gradient_peaks(img, layer, ctx)


def draw_hills(img: FloatImage, layer: HillsLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Eggshell-inlaid hill at one canvas edge with a gold outline."""
    spec = ctx.theme.textures.eggshell
    cell = spec.cell if layer.cell is None else layer.cell
    gap = spec.gap if layer.gap is None else layer.gap
    shape = Canvas(CANVAS_W, CANVAS_H)
    shape.color(WHITE)
    hill_path(shape, layer.side, layer.base, layer.top)
    shape.fill()
    mask = shape.mask()
    tex = eggshell(ctx.eggshell_rng(index, mask), mask, ctx.palette, cell, gap)
    img = fill_mask(img, tex, mask)
    line = Canvas(CANVAS_W, CANVAS_H)
    hill_path(line, layer.side, layer.base, layer.top)
    line.color(ctx.palette[HILL_OUTLINE_COLOR]).stroke(HILL_OUTLINE_WIDTH)
    return over(img, line)


def _wave(cv: Canvas, x: float, y: float) -> None:
    x1, y1, x2, y2, x3, y3 = WAVE_CREST
    cv.M(x, y).C(x + x1, y + y1, x + x2, y + y2, x + x3, y + y3)


def draw_river(img: FloatImage, layer: RiverLayer, ctx: DrawContext, index: int) -> FloatImage:
    """A band that darkens downwards and fades to nothing, with gold wave strokes."""
    y, pal = layer.y, ctx.palette
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.vgrad(
        y,
        y + layer.height,
        [
            (0, pal[RIVER_TOP_COLOR], 1),
            (RIVER_MID_STOP, pal[RIVER_DEEP_COLOR], RIVER_MID_ALPHA),
            (1, pal[RIVER_DEEP_COLOR], 0),
        ],
    )
    cv.rect(0, y, CANVAS_W, layer.height).fill()
    cv.color(pal[RIVER_BANK_COLOR]).M(0, y).L(CANVAS_W, y).stroke(RIVER_BANK_WIDTH)
    for row in range(WAVE_ROWS):
        row_y = y + WAVE_ROW_STEP * (row + 1)
        colour = pal[WAVE_COLORS[row % len(WAVE_COLORS)]]
        x = WAVE_X_START + (row % 2) * WAVE_ROW_OFFSET
        while x < WAVE_X_END:
            _wave(cv.color(colour, WAVE_ALPHA), x, row_y)
            cv.stroke(WAVE_WIDTH)
            x += WAVE_X_STEP
    return over(img, cv)


def _curl(cv: Canvas, x: float, y: float) -> None:
    a = CURL_FIRST
    b = CURL_SECOND
    cv.M(x, y + CURL_START_DY).C(x + a[0], y + a[1], x + a[2], y + a[3], x + a[4], y + a[5])
    cv.C(x + b[0], y + b[1], x + b[2], y + b[3], x + b[4], y + b[5])


def draw_ground(img: FloatImage, layer: GroundLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Dark vermilion earth band with a gold edge and a row of gold_dk curls."""
    y, pal = layer.y, ctx.palette
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.vgrad(
        y,
        y + layer.height,
        [(0, pal[GROUND_TOP_COLOR], 1), (1, pal[GROUND_BOTTOM_COLOR], 1)],
    )
    cv.rect(0, y, CANVAS_W, layer.height).fill()
    cv.color(pal[GROUND_LINE_COLOR]).M(0, y).L(CANVAS_W, y).stroke(GROUND_LINE_WIDTH)
    x = CURL_X_START
    while x < CURL_X_END:
        _curl(cv.color(pal[CURL_COLOR]), x, y)
        cv.stroke(CURL_WIDTH)
        x += CURL_X_STEP
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict(
    [
        entry(MountainsLayer, draw_mountains),
        entry(PeaksLayer, draw_peaks),
        entry(HillsLayer, draw_hills),
        entry(RiverLayer, draw_river),
        entry(GroundLayer, draw_ground),
    ]
)
