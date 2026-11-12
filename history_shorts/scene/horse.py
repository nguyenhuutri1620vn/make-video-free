"""A bronze horse statue on a stone plinth, no rider (backlog #15).

Original procedural artwork. The horse is filled with the gold-leaf texture through a mask
(a cast-metal look), then outlined. Geometry is in statue units with the floor on y = 0 and
the head towards +x; it is placed with ``translate(x, y)`` and ``scale(facing * s, s)``.
The statue is about 240 units wide and 290 tall with its plinth.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, fill_mask, over
from history_shorts.config import HorseLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.textures import gold_leaf

from .registry import WHITE, LayerDrawer, entry

OUTLINE: Final = "gold_dk"
OUTLINE_WIDTH: Final = 1.6
PLINTH: Final = (-120.0, -52.0, 240.0, 52.0)  # x, y, w, h
PLINTH_CAP: Final = (-130.0, -62.0, 260.0, 12.0)
PLINTH_FILL: Final = ("egg_tone", "brown")
PLINTH_OUTLINE: Final = "gold"
STAND_Y: Final = -62.0  # hooves stand on the plinth cap
STATUE_TILE: Final = 14  # finer gold-leaf tiles than the sun: the statue is small

# legs: (top x, top y, hoof x), all ending on STAND_Y; far pair first
LEGS: Final = ((-58.0, -112.0, -62.0), (58.0, -112.0, 66.0), (-76.0, -116.0, -86.0),
               (42.0, -112.0, 40.0))  # fmt: skip
LEG_HALF: Final = 6.5
TAIL: Final = ((-92.0, -150.0), (-120.0, -120.0), (-104.0, -78.0))
TAIL_WIDTH: Final = 9.0
EYE: Final = (100.0, -222.0, 2.4)
MANE: Final = ((38.0, -168.0), (52.0, -196.0), (70.0, -224.0))
MANE_COLOR: Final = "gold_lt"


def _body(cv: Canvas) -> None:
    cv.M(-92, -138).C(-90, -170, -40, -176, 0, -170).C(26, -168, 40, -176, 46, -184)
    cv.C(56, -214, 74, -238, 88, -242).C(104, -246, 122, -222, 130, -206)
    cv.C(134, -198, 126, -192, 118, -196).C(108, -200, 96, -196, 88, -190)
    cv.C(80, -170, 80, -140, 70, -122).C(56, -104, 20, -102, -10, -104)
    cv.C(-50, -106, -88, -108, -92, -138).Z()
    cv.M(86, -238).L(90, -258).L(96, -240).Z()  # ear


def _legs(cv: Canvas) -> None:
    for top_x, top_y, hoof_x in LEGS:
        cv.M(top_x - LEG_HALF, top_y).L(top_x + LEG_HALF, top_y)
        cv.L(hoof_x + LEG_HALF, STAND_Y - 6).L(hoof_x + LEG_HALF + 2, STAND_Y)
        cv.L(hoof_x - LEG_HALF - 2, STAND_Y).L(hoof_x - LEG_HALF, STAND_Y - 6).Z()


def _tail(cv: Canvas) -> None:
    (ax, ay), (bx, by), (cx, cy) = TAIL
    cv.M(ax, ay).C(bx, by, bx, by + 10, cx, cy)


def _shape(cv: Canvas, fill: bool, colour: tuple[int, int, int]) -> None:
    """Draw the whole horse either filled (for the mask) or outlined."""
    for part in (_legs, _body):
        part(cv)
        if fill:
            cv.color(colour).fill()
        else:
            cv.color(colour).stroke(OUTLINE_WIDTH)
    _tail(cv)
    cv.color(colour).stroke(TAIL_WIDTH if fill else OUTLINE_WIDTH)


def _local(cv: Canvas, layer: HorseLayer) -> None:
    cv.translate(layer.x, layer.y)
    cv.scale(layer.facing * layer.scale, layer.scale)


def _plinth(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    for x, y, w, h in (PLINTH, PLINTH_CAP):
        cv.rect(x, y, w, h)
        cv.vgrad(y, y + h, [(0, pal[PLINTH_FILL[0]], 1), (1, pal[PLINTH_FILL[1]], 1)])
        cv.fill(keep=True).color(pal[PLINTH_OUTLINE]).stroke(1.2)


def draw_horse(img: FloatImage, layer: HorseLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Plinth, then the gold-leaf horse masked to its silhouette, then outlines and details."""
    pal = ctx.palette
    base = Canvas(CANVAS_W, CANVAS_H)
    base.save()
    _local(base, layer)
    _plinth(base, ctx)
    base.restore()
    img = over(img, base)
    mask = Canvas(CANVAS_W, CANVAS_H)
    mask.save()
    _local(mask, layer)
    _shape(mask, True, WHITE)
    mask.restore()
    worn = ctx.theme.textures.gold_leaf.worn
    tex = gold_leaf(ctx.rng(index), pal, STATUE_TILE, worn, width=CANVAS_W, height=CANVAS_H)
    img = fill_mask(img, tex, mask.mask())
    lines = Canvas(CANVAS_W, CANVAS_H)
    lines.save()
    _local(lines, layer)
    _shape(lines, False, pal[OUTLINE])
    x, y, r = EYE
    lines.color(pal[OUTLINE]).ellipse(x, y, r, r).fill()
    (ax, ay), (bx, by), (cx, cy) = MANE
    lines.M(ax, ay).C(bx - 8, by, bx, by - 6, cx, cy).color(pal[MANE_COLOR]).stroke(3.0)
    lines.restore()
    return over(img, lines)


DRAWERS: dict[type, LayerDrawer] = dict([entry(HorseLayer, draw_horse)])
