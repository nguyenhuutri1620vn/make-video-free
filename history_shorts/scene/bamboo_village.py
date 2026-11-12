"""A village behind its bamboo hedge, with thatched roofs, a banyan and a gate (backlog #18).

Original procedural artwork (spec Appendix B, "làng tre"). Geometry is in village units with
the ground on y = 0 under ``translate(x, y)`` and ``scale(scale)``; the village is about 540
units wide and 260 tall. Bamboo stalk positions jitter with the layer's RNG.
"""

from __future__ import annotations

from typing import Final

from numpy.random import Generator

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import BambooVillageLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.3

HEDGE_SPAN: Final = (-270.0, 270.0)
HEDGE_STALKS: Final = 34
HEDGE_HEIGHT: Final = (170.0, 240.0)
STALK_COLOR: Final = "jade"
STALK_WIDTH: Final = 4.0
LEAF_FILL: Final = ("jade", "leaf_dk")
LEAF_CLUSTERS: Final = 4  # leaf tufts per stalk, near its top
LEAF_FAN: Final = ((-30.0, 6.0), (-6.0, 14.0), (26.0, 8.0))  # leaf tip offsets per tuft

HOUSES: Final = ((-130.0, 1.0), (10.0, 1.15), (150.0, 0.95))  # centre x, size
HOUSE_WALL: Final = (46.0, 34.0)  # half width, height at size 1
HOUSE_ROOF: Final = (70.0, 52.0)  # eave half width, roof height
WALL_FILL: Final = ("brown_lt", "brown")
ROOF_FILL: Final = ("gold", "gold_dk")
DOOR_FILL: Final = "black"

BANYAN_X: Final = -205.0
TRUNK: Final = (18.0, 120.0)  # half width at the base, height
TRUNK_FILL: Final = ("brown", "hull_dk")
CANOPY: Final = ((-205.0, -150.0, 70.0), (-250.0, -120.0, 50.0), (-160.0, -125.0, 55.0),
                 (-215.0, -190.0, 48.0))  # fmt: skip
CANOPY_FILL: Final = ("jade", "leaf_dk")
ROOTS: Final = 5

GATE_X: Final = 60.0
GATE: Final = (36.0, 62.0)  # half width, height of the gate wall
GATE_FILL: Final = ("egg_tone", "brown_lt")
GATE_ROOF_FILL: Final = ("vermilion", "vermilion_dk")


def _grad(cv: Canvas, ctx: DrawContext, keys: tuple[str, str], y0: float, y1: float) -> None:
    pal = ctx.palette
    cv.vgrad(y0, y1, [(0, pal[keys[0]], 1), (1, pal[keys[1]], 1)]).fill(keep=True)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _hedge(cv: Canvas, ctx: DrawContext, rng: Generator) -> None:
    pal = ctx.palette
    left, right = HEDGE_SPAN
    step = (right - left) / (HEDGE_STALKS - 1)
    tops: list[tuple[float, float]] = []
    for k in range(HEDGE_STALKS):
        x = left + k * step + float(rng.uniform(-0.3, 0.3)) * step
        height = float(rng.uniform(*HEDGE_HEIGHT))
        lean = float(rng.uniform(-24, 24))
        cv.M(x, 0).C(x, -height * 0.5, x + lean * 0.5, -height * 0.8, x + lean, -height)
        tops.append((x + lean, -height))
    cv.color(pal[STALK_COLOR]).stroke(STALK_WIDTH)
    for tx, ty in tops:
        for c in range(LEAF_CLUSTERS):
            cx = tx + float(rng.uniform(-14, 14))
            cy = ty + c * 26 + float(rng.uniform(-6, 6))
            for dx, dy in LEAF_FAN:
                _leaf(cv, cx, cy, dx, dy)
                _grad(cv, ctx, LEAF_FILL, cy - 6, cy + dy + 6)


def _leaf(cv: Canvas, x: float, y: float, dx: float, dy: float) -> None:
    """A narrow bamboo leaf from (x, y) to (x + dx, y + dy)."""
    nx, ny = -dy * 0.18, dx * 0.18
    cv.M(x, y).C(x + dx * 0.4 + nx, y + dy * 0.4 + ny, x + dx * 0.8 + nx * 0.4,
                 y + dy * 0.8 + ny * 0.4, x + dx, y + dy)  # fmt: skip
    cv.C(x + dx * 0.8 - nx * 0.4, y + dy * 0.8 - ny * 0.4, x + dx * 0.4 - nx,
         y + dy * 0.4 - ny, x, y).Z()  # fmt: skip


def _house(cv: Canvas, ctx: DrawContext, cx: float, size: float) -> None:
    pal = ctx.palette
    hw, wh = HOUSE_WALL[0] * size, HOUSE_WALL[1] * size
    rw, rh = HOUSE_ROOF[0] * size, HOUSE_ROOF[1] * size
    cv.rect(cx - hw, -wh, hw * 2, wh)
    _grad(cv, ctx, WALL_FILL, -wh, 0)
    cv.color(pal[DOOR_FILL]).rect(cx - hw * 0.25, -wh * 0.8, hw * 0.5, wh * 0.8).fill()
    eave = -wh + 6 * size
    cv.M(cx - rw, eave).L(cx + rw, eave).L(cx + rw * 0.35, eave - rh).L(cx - rw * 0.35, eave - rh)
    cv.Z()
    _grad(cv, ctx, ROOF_FILL, eave - rh, eave)


def _banyan(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    half, height = TRUNK
    x = BANYAN_X
    cv.M(x - half * 1.6, 0).C(
        x - half, -height * 0.3, x - half * 0.6, -height * 0.7, x - 8, -height
    )
    cv.L(x + 8, -height).C(
        x + half * 0.6, -height * 0.7, x + half, -height * 0.3, x + half * 1.6, 0
    )
    cv.Z()
    _grad(cv, ctx, TRUNK_FILL, -height, 0)
    for k in range(ROOTS):
        rx = x - 40 + k * 20
        cv.M(rx, -height * 0.9).C(rx - 4, -height * 0.5, rx + 4, -height * 0.3, rx, 0)
    cv.color(pal[TRUNK_FILL[0]]).stroke(1.6)
    for cx, cy, r in CANOPY:
        cv.ellipse(cx, cy, r, r * 0.8)
        _grad(cv, ctx, CANOPY_FILL, cy - r, cy + r)


def _gate(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    half, height = GATE
    x = GATE_X
    cv.M(x - half, 0).L(x - half, -height).L(x + half, -height).L(x + half, 0)
    cv.L(x + half * 0.55, 0).L(x + half * 0.55, -height * 0.55)
    cv.C(
        x + half * 0.55,
        -height * 0.85,
        x - half * 0.55,
        -height * 0.85,
        x - half * 0.55,
        -height * 0.55,
    )
    cv.L(x - half * 0.55, 0).Z()
    _grad(cv, ctx, GATE_FILL, -height, 0)
    top = -height
    cv.M(x - half - 16, top - 2).C(x - half, top + 4, x + half, top + 4, x + half + 16, top - 2)
    cv.L(x + half * 0.6, top - 22).L(x - half * 0.6, top - 22).Z()
    _grad(cv, ctx, GATE_ROOF_FILL, top - 22, top)
    cv.color(pal[OUTLINE]).M(x - half * 0.6, top - 22).L(x + half * 0.6, top - 22).stroke(2.0)


def draw_bamboo_village(
    img: FloatImage, layer: BambooVillageLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Hedge at the back, the houses, the banyan, then the gate in front."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _hedge(cv, ctx, ctx.rng(index))
    for cx, size in HOUSES:
        _house(cv, ctx, cx, size)
    _banyan(cv, ctx)
    _gate(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(BambooVillageLayer, draw_bamboo_village)])
