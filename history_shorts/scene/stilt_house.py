"""A stilt house (nhà sàn) with a saddle roof and a bamboo clump (backlog #7).

Original procedural artwork. The upturned saddle ridge echoes the houses shown on Đông Sơn
drums without copying any of them. Geometry is in house units with the ground on y = 0 under
``translate(x, y)`` and ``scale(scale)``; the house is about 300 units wide and 270 tall.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import StiltHouseLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 1.4
THIN: Final = 0.8

POSTS_X: Final = (-100.0, -50.0, 0.0, 50.0, 100.0)
POST_HALF_WIDTH: Final = 4.5
POST_FILL: Final = "brown"
FLOOR: Final = (-118.0, -80.0, 236.0, 9.0)  # x, y, w, h
FLOOR_FILL: Final = "brown_lt"

WALL: Final = (-100.0, -150.0, 200.0, 70.0)
WALL_FILL: Final = ("brown_lt", "brown")
PLANK_STEP: Final = 12.0
PLANK_COLOR: Final = "gold_dk"
DOOR: Final = (-16.0, -140.0, 32.0, 60.0)
DOOR_FILL: Final = "black"

LADDER: Final = ((-14.0, -80.0, -34.0, 0.0), (14.0, -80.0, -6.0, 0.0))  # two rails
LADDER_RUNGS: Final = 5
LADDER_COLOR: Final = "brown_lt"

ROOF_EAVE_Y: Final = -142.0
ROOF_EAVE_HALF: Final = 150.0
ROOF_TOP_Y: Final = -236.0
ROOF_TOP_HALF: Final = 92.0
ROOF_FILL: Final = ("gold", "gold_dk")
THATCH_COLOR: Final = "brown"
THATCH_ALPHA: Final = 0.45
THATCH_STEP: Final = 14.0
RIDGE_TIP: Final = (128.0, -270.0)  # upturned saddle-ridge tip (right; left is mirrored)
RIDGE_COLOR: Final = "brown"
RIDGE_WIDTH: Final = 5.0

BAMBOO_STALKS: Final = (  # base x, top x, top y
    (-190.0, -214.0, -330.0),
    (-176.0, -170.0, -360.0),
    (-162.0, -138.0, -320.0),
    (-150.0, -116.0, -270.0),
)
BAMBOO_WIDTH: Final = 6.0
BAMBOO_FILL: Final = "jade"
BAMBOO_NODE: Final = "gold_dk"
BAMBOO_NODE_STEP: Final = 38.0
LEAF_FILL: Final = ("jade", "leaf_dk")
LEAVES_PER_STALK: Final = 5


def _posts_floor(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x in POSTS_X:
        cv.rect(x - POST_HALF_WIDTH, FLOOR[1], POST_HALF_WIDTH * 2, -FLOOR[1])
        cv.color(pal[POST_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(THIN)
    cv.rect(*FLOOR).color(pal[FLOOR_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(THIN)


def _walls(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    x, y, w, h = WALL
    cv.rect(x, y, w, h).vgrad(y, y + h, [(0, pal[WALL_FILL[0]], 1), (1, pal[WALL_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    px = x + PLANK_STEP
    while px < x + w:
        cv.M(px, y).L(px, y + h)
        px += PLANK_STEP
    cv.color(pal[PLANK_COLOR]).stroke(THIN)
    cv.rect(*DOOR).color(pal[DOOR_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(THIN)


def _ladder(cv: Canvas, ctx: DrawContext) -> None:
    color = ctx.palette[LADDER_COLOR]
    (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = LADDER
    for k in range(1, LADDER_RUNGS + 1):
        t = k / (LADDER_RUNGS + 1)
        cv.M(ax0 + (ax1 - ax0) * t, ay0 + (ay1 - ay0) * t)
        cv.L(bx0 + (bx1 - bx0) * t, by0 + (by1 - by0) * t)
    cv.M(ax0, ay0).L(ax1, ay1).M(bx0, by0).L(bx1, by1)
    cv.color(color).stroke(3.0)


def _roof(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    eh, th = ROOF_EAVE_HALF, ROOF_TOP_HALF
    cv.M(-eh, ROOF_EAVE_Y).L(eh, ROOF_EAVE_Y).L(th, ROOF_TOP_Y).L(-th, ROOF_TOP_Y).Z()
    cv.vgrad(ROOF_TOP_Y, ROOF_EAVE_Y, [(0, pal[ROOF_FILL[0]], 1), (1, pal[ROOF_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    x = -eh + THATCH_STEP
    while x < eh:  # thatch strokes slant towards the ridge
        top = x * th / eh
        cv.M(x, ROOF_EAVE_Y - 2).L(top, ROOF_TOP_Y + 4)
        x += THATCH_STEP
    cv.color(pal[THATCH_COLOR], THATCH_ALPHA).stroke(THIN)
    for colour, width in ((RIDGE_COLOR, RIDGE_WIDTH), (OUTLINE, THIN)):
        _ridge(cv, th)
        cv.color(pal[colour]).stroke(width)


def _ridge(cv: Canvas, top_half: float) -> None:
    """The saddle ridge: along the roof top, its ends curling up and out."""
    tx, ty, y = RIDGE_TIP[0], RIDGE_TIP[1], ROOF_TOP_Y
    cv.M(-tx, ty).C(-tx + 8, y - 12, -top_half - 6, y, -top_half, y).L(top_half, y)
    cv.C(top_half + 6, y, tx - 8, y - 12, tx, ty)


def _leaf(cv: Canvas, x: float, y: float, dx: float, dy: float) -> None:
    """A narrow leaf from (x, y) pointing along (dx, dy)."""
    nx, ny = -dy * 0.22, dx * 0.22
    cv.M(x, y).C(x + dx * 0.4 + nx, y + dy * 0.4 + ny, x + dx * 0.8 + nx * 0.5,
                 y + dy * 0.8 + ny * 0.5, x + dx, y + dy)  # fmt: skip
    cv.C(x + dx * 0.8 - nx * 0.5, y + dy * 0.8 - ny * 0.5, x + dx * 0.4 - nx,
         y + dy * 0.4 - ny, x, y).Z()  # fmt: skip


def _bamboo(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for base, top_x, top_y in BAMBOO_STALKS:
        cv.M(base, 0).C(base, top_y * 0.5, top_x, top_y * 0.8, top_x, top_y)
        cv.color(pal[OUTLINE]).stroke(BAMBOO_WIDTH + 2)
        cv.M(base, 0).C(base, top_y * 0.5, top_x, top_y * 0.8, top_x, top_y)
        cv.color(pal[BAMBOO_FILL]).stroke(BAMBOO_WIDTH)
        y = -BAMBOO_NODE_STEP
        while y > top_y + 20:
            t = y / top_y
            x = base + (top_x - base) * t * t
            cv.M(x - 5, y).L(x + 5, y)
            y -= BAMBOO_NODE_STEP
        cv.color(pal[BAMBOO_NODE]).stroke(1.6)
        for k in range(LEAVES_PER_STALK):
            t = 0.55 + 0.45 * k / (LEAVES_PER_STALK - 1)
            x, y = base + (top_x - base) * t * t, top_y * t
            side = 1 if k % 2 else -1
            _leaf(cv, x, y, side * 34, 14 - k * 3)
            cv.vgrad(y - 10, y + 20, [(0, pal[LEAF_FILL[0]], 1), (1, pal[LEAF_FILL[1]], 1)])
            cv.fill(keep=True).color(pal[OUTLINE]).stroke(THIN * 0.8)


def draw_stilt_house(
    img: FloatImage, layer: StiltHouseLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """Bamboo behind, then stilts and floor, walls, ladder and the saddle roof."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    if layer.bamboo:
        _bamboo(cv, ctx)
    _posts_floor(cv, ctx)
    _walls(cv, ctx)
    _ladder(cv, ctx)
    _roof(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(StiltHouseLayer, draw_stilt_house)])
