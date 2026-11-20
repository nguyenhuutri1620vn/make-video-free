"""A bronze-casting furnace with a glowing mouth and flames over its top (Trống đồng video).

Original procedural artwork: a squat clay-brick kiln, its arched mouth full of fire, a warm
halo around it and flame tongues rising from the open top. Geometry is in furnace units with
the floor on y = 0 under ``translate(x, y)`` and ``scale(scale)``; the kiln is 300 units wide
and the flames reach about 400 units above the floor.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import FurnaceLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .registry import LayerDrawer, PhaseDrawer, entry, phase_entry

OUTLINE: Final = "gold_dk"
OUTLINE_WIDTH: Final = 1.6
HOT_OUTLINE: Final = "gold"

HALO: Final = (0.0, -150.0, 300.0)  # centre x, centre y, radius
HALO_COLOR: Final = "vermilion"
HALO_ALPHA: Final = 0.45

BODY_HALF: Final = 150.0  # half width at the floor
SHOULDER: Final = (130.0, -180.0)  # half width, y where the walls start to curve in
TOP: Final = (40.0, -272.0)  # half width of the opening, y of the rim
BODY_FILL: Final = ("brown_lt", "brown")
COURSE_STEP: Final = 34.0  # brick course height
BRICK_W: Final = 52.0
COURSE_COLOR: Final = "gold_dk"
COURSE_ALPHA: Final = 0.45
COURSE_WIDTH: Final = 1.0

MOUTH_HALF: Final = 70.0
MOUTH_SPRING: Final = -90.0  # y where the arch starts
MOUTH_CROWN: Final = -150.0  # control height of the arch
MOUTH_FILL: Final = ("vermilion", "gold_lt")  # top, bottom: hottest at the floor
MOUTH_TONGUES: Final = ((-38.0, 30.0, 92.0, 8.0), (0.0, 36.0, 120.0, -6.0), (38.0, 28.0, 86.0, 6.0))

RIM: Final = (0.0, -272.0, 42.0, 10.0)  # centre x, y, rx, ry
RIM_FILL: Final = "vermilion_dk"
# flame tongues over the top: (x, half width, height, lean), back to front
TOP_TONGUES: Final = (
    (-22.0, 26.0, 96.0, -14.0, "vermilion"),
    (20.0, 24.0, 110.0, 12.0, "vermilion"),
    (0.0, 30.0, 128.0, -4.0, "gold"),
    (-6.0, 16.0, 80.0, 4.0, "gold_lt"),
)
MOUTH_TONGUE_COLORS: Final = ("gold", "gold_lt")

# Flicker (M10): each tongue's height and lean follow a smooth periodic wobble of three
# harmonics with random phases, zero at phase 0 so the first frame is the still drawing.
FLICKER_WEIGHTS: Final = (1.0, 0.5, 0.25)
LEAN_SHARE: Final = 0.6  # lean wobble relative to the height wobble
MOUTH_SHARE: Final = 0.5  # the fire inside the mouth moves less than the open flames


Wobble = Callable[[int, int], float]  # (tongue index, channel) -> offset in furnace units


def _still(_k: int, _channel: int) -> float:
    return 0.0


def _wobble(ctx: DrawContext, index: int, phase: float) -> Wobble:
    """Smooth periodic offsets per tongue; channel 0 is height, 1 is lean."""
    count = len(TOP_TONGUES) + len(MOUTH_TONGUES)
    phis = ctx.rng(index).uniform(0, 2 * math.pi, (count, 2, len(FLICKER_WEIGHTS)))
    amp = ctx.theme.living.flame_px
    total = sum(FLICKER_WEIGHTS)

    def offset(k: int, channel: int) -> float:
        wave = sum(
            w
            * (
                math.sin(2 * math.pi * (n + 1) * phase + phis[k, channel, n])
                - math.sin(phis[k, channel, n])
            )
            for n, w in enumerate(FLICKER_WEIGHTS)
        )
        return amp * (LEAN_SHARE if channel else 1.0) * wave / total

    return offset


def _tongue(cv: Canvas, x: float, base: float, half: float, height: float, lean: float) -> None:
    tip = (x + lean, base - height)
    cv.M(x - half, base).C(x - half, base - height * 0.5, tip[0] - half * 0.3, base - height * 0.7,
                           *tip)  # fmt: skip
    cv.C(tip[0] + half * 0.3, base - height * 0.7, x + half, base - height * 0.5, x + half, base)
    cv.Z()


def _body_path(cv: Canvas) -> None:
    sw, sy = SHOULDER
    tw, ty = TOP
    cv.M(-BODY_HALF, 0).L(-sw, sy).C(-sw + 10, sy - 60, -tw - 20, ty + 2, -tw, ty)
    cv.L(tw, ty).C(tw + 20, ty + 2, sw - 10, sy - 60, sw, sy).L(BODY_HALF, 0).Z()


def _mouth_path(cv: Canvas) -> None:
    h, s, c = MOUTH_HALF, MOUTH_SPRING, MOUTH_CROWN
    cv.M(-h, 0).L(-h, s).C(-h, c, h, c, h, s).L(h, 0).Z()


def _halo(cv: Canvas, ctx: DrawContext, phase: float) -> None:
    x, y, r = HALO
    glow = ctx.palette[HALO_COLOR]
    alpha = HALO_ALPHA * (1 + ctx.theme.living.flame_glow * math.sin(2 * math.pi * phase))
    cv.ellipse(x, y, r, r).rgrad(x, y, r, [(0, glow, alpha), (1, glow, 0.0)]).fill()


def _courses(cv: Canvas, ctx: DrawContext) -> None:
    """Brick courses and staggered joints, clipped to the kiln body."""
    cv.save()
    _body_path(cv)
    cv.clip()
    cv.color(ctx.palette[COURSE_COLOR], COURSE_ALPHA)
    row = 0
    y = -COURSE_STEP
    while y > TOP[1]:
        cv.M(-BODY_HALF, y).L(BODY_HALF, y)
        offset = BRICK_W / 2 if row % 2 else 0.0
        x = -BODY_HALF + offset
        while x < BODY_HALF:
            cv.M(x, y).L(x, y + COURSE_STEP)
            x += BRICK_W
        row += 1
        y -= COURSE_STEP
    cv.stroke(COURSE_WIDTH)
    cv.restore()


def _body(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    _body_path(cv)
    cv.vgrad(TOP[1], 0, [(0, pal[BODY_FILL[0]], 1), (1, pal[BODY_FILL[1]], 1)]).fill()
    _courses(cv, ctx)
    _body_path(cv)
    cv.color(pal[OUTLINE]).stroke(OUTLINE_WIDTH)


def _mouth(cv: Canvas, ctx: DrawContext, wobble: Wobble) -> None:
    pal = ctx.palette
    _mouth_path(cv)
    cv.vgrad(MOUTH_CROWN, 0, [(0, pal[MOUTH_FILL[0]], 1), (1, pal[MOUTH_FILL[1]], 1)]).fill()
    cv.save()
    _mouth_path(cv)
    cv.clip()
    for i, (x, half, height, lean) in enumerate(MOUTH_TONGUES):
        k = len(TOP_TONGUES) + i
        dh, dl = MOUTH_SHARE * wobble(k, 0), MOUTH_SHARE * wobble(k, 1)
        _tongue(cv, x, 0, half, height + dh, lean + dl)
        cv.color(pal[MOUTH_TONGUE_COLORS[i % 2]]).fill()
    cv.restore()
    _mouth_path(cv)
    cv.color(pal[HOT_OUTLINE]).stroke(OUTLINE_WIDTH)


def _top(cv: Canvas, ctx: DrawContext, wobble: Wobble) -> None:
    pal = ctx.palette
    cx, cy, _, _ = RIM
    for k, (x, half, height, lean, colour) in enumerate(TOP_TONGUES):
        _tongue(cv, cx + x, cy, half, height + wobble(k, 0), lean + wobble(k, 1))
        cv.color(pal[colour]).fill()


def draw_furnace(img: FloatImage, layer: FurnaceLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Halo, kiln body with brick courses, fire in the mouth, then the flames over the top."""
    return _draw(img, layer, ctx, 0.0, _still)


def draw_furnace_at(
    img: FloatImage, layer: FurnaceLayer, ctx: DrawContext, index: int, phase: float
) -> FloatImage:
    """The furnace at loop ``phase``: flames flicker and the halo glows (M10)."""
    return _draw(img, layer, ctx, phase, _wobble(ctx, index, phase))


def _draw(
    img: FloatImage, layer: FurnaceLayer, ctx: DrawContext, phase: float, wobble: Wobble
) -> FloatImage:
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _halo(cv, ctx, phase)
    _top(cv, ctx, wobble)
    _body(cv, ctx)
    _mouth(cv, ctx, wobble)
    cv.ellipse(*RIM).color(ctx.palette[RIM_FILL]).fill(keep=True)
    cv.color(ctx.palette[HOT_OUTLINE]).stroke(OUTLINE_WIDTH)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(FurnaceLayer, draw_furnace)])
PHASE_DRAWERS: dict[type, PhaseDrawer] = dict([phase_entry(FurnaceLayer, draw_furnace_at)])
