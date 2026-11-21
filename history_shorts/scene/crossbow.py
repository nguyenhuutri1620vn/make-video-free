"""A crossbow seen from above, its trigger the golden claw of the legend (Cổ Loa video).

Original procedural artwork, stylised. One crossbow points up in its own frame: the stock runs
from the butt at y = 0 to the nose at y = -300, the bow arcs across at y = -255 (340 units
tip to tip), the drawn string meets the nut at y = -130, an arrow lies along the stock and the
trigger sits at y = -110. Modes under ``translate(x, y)`` and ``scale(scale)``:

* ``claw``: one crossbow, the trigger a glowing golden claw;
* ``volley``: the crossbow tilted, a fan of arrows streaking out of it (no target is shown);
* ``rack``: three rows of plain crossbows on wooden racks, front row largest;
* ``missing``: one crossbow, the trigger slot empty, only a faint outline of the claw.
"""

from __future__ import annotations

import math
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import CrossbowLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, entry

OUTLINE: Final = "black"
OUTLINE_WIDTH: Final = 1.5
STOCK: Final = (0.0, -300.0, 16.0, 11.0)  # butt y, nose y, half width at butt, at nose
STOCK_FILL: Final = ("brown_lt", "brown")
BOW: Final = (-255.0, 170.0, 34.0, 9.0)  # y at the middle, half span, sweep back, thickness
BOW_FILL: Final = "vermilion_dk"
BOW_BAND: Final = "gold"
STRING: Final = (-130.0, "egg", 1.6)  # nut y, colour, width
ARROW: Final = (-130.0, -330.0, 3.0)  # nock y, tip y, shaft half width
ARROW_FILL: Final = "egg_tone"
ARROW_TIP: Final = "gold"
TRIGGER: Final = (-110.0, 9.0, 34.0)  # y, half width, length down the stock
CLAW_FILL: Final = ("gold_lt", "gold")
CLAW_GLOW: Final = (60.0, 0.55)  # radius, alpha
GLOW_COLOR: Final = "gold_lt"
SLOT_FILL: Final = "shadow"
GHOST_ALPHA: Final = 0.45  # outline of the claw that is no longer there

VOLLEY_TILT: Final = math.radians(32.0)
VOLLEY_ARROWS: Final = 13
VOLLEY_SPREAD: Final = math.radians(46.0)
VOLLEY_REACH: Final = (230.0, 420.0)  # nearest, farthest arrow distance from the nose
VOLLEY_TRAIL: Final = 120.0
TRAIL_COLOR: Final = "gold_lt"

RACK_ROWS: Final = ((-430.0, 0.42, 5), (-215.0, 0.55, 4), (0.0, 0.7, 3))  # floor y, scale, count
RACK_SPACING: Final = 330.0  # between crossbows, in crossbow units
RACK_BEAM: Final = ("brown", 14.0)


def _stock(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    butt, nose, wb, wn = STOCK
    cv.M(-wb, butt).L(wb, butt).L(wn, nose).L(-wn, nose).Z()
    cv.vgrad(nose, butt, [(0, pal[STOCK_FILL[0]], 1), (1, pal[STOCK_FILL[1]], 1)])
    cv.fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _bow(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    y, span, sweep, thick = BOW
    cv.M(-span, y + sweep).C(-span * 0.5, y - 6.0, span * 0.5, y - 6.0, span, y + sweep)
    cv.L(span, y + sweep - thick).C(span * 0.5, y - 6.0 - thick, -span * 0.5, y - 6.0 - thick,
                                    -span, y + sweep - thick).Z()  # fmt: skip
    cv.color(pal[BOW_FILL]).fill(keep=True).color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)
    for x in (-span * 0.55, span * 0.55):
        cv.M(x, y - 10.0).L(x, y + 8.0)
    cv.color(pal[BOW_BAND]).stroke(4.0)
    nut, color, width = STRING
    cv.M(-span, y + sweep - thick / 2).L(0.0, nut).L(span, y + sweep - thick / 2)
    cv.color(pal[color], 0.9).stroke(width)


def _arrow(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    nock, tip, half = ARROW
    cv.rect(-half, tip + 22.0, 2 * half, nock - tip - 22.0).color(pal[ARROW_FILL]).fill()
    cv.M(0.0, tip).L(8.0, tip + 26.0).L(-8.0, tip + 26.0).Z()
    cv.color(pal[ARROW_TIP]).fill(keep=True).color(pal[OUTLINE]).stroke(1.0)


def _claw_path(cv: Canvas, y: float, half: float, length: float) -> None:
    """A curved claw: wide at the root, hooked at the tip."""
    cv.M(-half, y).C(-half, y + length * 0.6, -half * 0.2, y + length, half * 1.4, y + length)
    cv.C(half * 0.4, y + length * 0.7, half, y + length * 0.3, half, y).Z()


def _trigger(cv: Canvas, ctx: DrawContext, mode: str) -> None:
    pal = ctx.palette
    y, half, length = TRIGGER
    if mode == "missing":
        cv.rect(-half, y, 2 * half, length).color(pal[SLOT_FILL]).fill()
        _claw_path(cv, y, half, length)
        cv.color(pal[GLOW_COLOR], GHOST_ALPHA).stroke(1.2)
        return
    if mode in ("claw", "volley"):
        r, alpha = CLAW_GLOW
        glow = pal[GLOW_COLOR]
        cv.ellipse(0.0, y + length / 2, r, r)
        cv.rgrad(0.0, y + length / 2, r, [(0, glow, alpha), (1, glow, 0.0)]).fill()
        _claw_path(cv, y, half, length)
        cv.vgrad(y, y + length, [(0, pal[CLAW_FILL[0]], 1), (1, pal[CLAW_FILL[1]], 1)])
        cv.fill(keep=True).color(pal[OUTLINE]).stroke(1.0)
    else:
        cv.rect(-half * 0.6, y, half * 1.2, length * 0.8).color(pal["gold_dk"]).fill()


def draw_one_crossbow(cv: Canvas, ctx: DrawContext, mode: str, *, loaded: bool = True) -> None:
    """One crossbow in its own frame (butt at the origin, pointing up)."""
    _stock(cv, ctx)
    _bow(cv, ctx)
    if loaded:
        _arrow(cv, ctx)
    _trigger(cv, ctx, mode)


def _volley(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    nose = STOCK[1]
    for k in range(VOLLEY_ARROWS):
        t = k / (VOLLEY_ARROWS - 1)
        angle = -VOLLEY_SPREAD / 2 + VOLLEY_SPREAD * t
        reach = VOLLEY_REACH[0] + (VOLLEY_REACH[1] - VOLLEY_REACH[0]) * ((k * 7) % 5) / 4
        dx, dy = math.sin(angle), -math.cos(angle)
        tx, ty = dx * reach, nose + dy * reach
        sx, sy = tx - dx * VOLLEY_TRAIL, ty - dy * VOLLEY_TRAIL
        trail = pal[TRAIL_COLOR]
        cv.M(sx, sy).L(tx, ty)
        cv.vgrad(sy, ty, [(0, trail, 0.0), (1, trail, 0.85)]).stroke(3.0)
        cv.save()
        cv.translate(tx, ty)
        cv.rotate(angle)
        cv.M(0.0, -14.0).L(6.0, 6.0).L(-6.0, 6.0).Z().color(pal[ARROW_TIP]).fill()
        cv.restore()
    draw_one_crossbow(cv, ctx, "volley", loaded=False)


def _rack(cv: Canvas, ctx: DrawContext) -> None:
    color, width = RACK_BEAM
    for floor, scale, count in RACK_ROWS:
        span = RACK_SPACING * scale * (count - 1)
        cv.M(-span / 2 - 60.0, floor - 40.0 * scale).L(span / 2 + 60.0, floor - 40.0 * scale)
        cv.color(ctx.palette[color]).stroke(width * scale)
        for k in range(count):
            cv.save()
            cv.translate(-span / 2 + k * RACK_SPACING * scale, floor)
            cv.scale(scale, scale)
            draw_one_crossbow(cv, ctx, "plain")
            cv.restore()


def draw_crossbow(
    img: FloatImage, layer: CrossbowLayer, ctx: DrawContext, index: int
) -> FloatImage:
    """The crossbow(s) for the mode."""
    del index  # no randomness
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    if layer.mode == "volley":
        cv.rotate(VOLLEY_TILT)
        _volley(cv, ctx)
    elif layer.mode == "rack":
        _rack(cv, ctx)
    else:
        draw_one_crossbow(cv, ctx, layer.mode)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(CrossbowLayer, draw_crossbow)])
