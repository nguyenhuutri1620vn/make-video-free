"""A lacquered boat hull with its crew standing in it (FR-46)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.characters.figure import Placement
from history_shorts.characters.formations import PlacedCharacter
from history_shorts.compose import DrawContext, over
from history_shorts.config import BoatLayer, CharacterSpec
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .people import draw_figures
from .registry import LayerDrawer, entry


@dataclass(frozen=True, slots=True)
class CrewSlot:
    """Where a crew member stands, in boat units: offset from the boat origin and height."""

    dx: float
    dy: float
    height: float


BOAT_CREW_SLOTS: Final = (CrewSlot(6.7, -5.3, 100.0), CrewSlot(-26.7, -4.0, 80.0))
MAX_CREW: Final = len(BOAT_CREW_SLOTS)
DEFAULT_CREW_FACING: Final = 1
CREW_COUNT_ERROR: Final = f"boat supports at most {MAX_CREW} crew"

# -- hull (boat units, drawn under translate(x, y) and scale(s, s)) ------------------------
HULL_TOP_COLOR: Final = "brown_lt"
HULL_BOTTOM_COLOR: Final = "hull_dk"
HULL_GRADIENT: Final = (-14.0, 16.0)  # y of the gradient's start and end
HULL_OUTLINE_COLOR: Final = "gold"
HULL_OUTLINE_WIDTH: Final = 1.4
HULL_START: Final = (-70.0, -10.0)
HULL_TOP_CURVE: Final = (-40.0, 8.0, 40.0, 8.0, 74.0, -14.0)  # the deck line, bow to stern
HULL_KEEL_CURVE: Final = (60.0, 6.0, 30.0, 16.0, 0.0, 16.0)
HULL_BACK_CURVE: Final = (-30.0, 16.0, -58.0, 8.0, -70.0, -10.0)
TRIM_COLOR: Final = "gold"
TRIM_WIDTH: Final = 0.8
TRIM_START: Final = (-62.0, -4.0)
TRIM_CURVE: Final = (-30.0, 7.0, 30.0, 7.0, 66.0, -8.0)
STUD_COLOR: Final = "gold_lt"
STUD_CENTRE: Final = (62.0, -6.0)
STUD_RADIUS: Final = 2.4


def crew_placements(layer: BoatLayer) -> list[PlacedCharacter]:
    """Crew placements in canvas pixels, in draw order (the order given).

    An explicit ``x``, ``baseline`` or ``height`` on a crew spec wins; otherwise the
    member stands in its slot, scaled with the boat. Facing defaults to +1. This is the
    single source of crew placement: drawing and the FR-48 checks both call it. Raises
    ``ValueError`` for more crew than slots.
    """
    if len(layer.crew) > MAX_CREW:
        raise ValueError(CREW_COUNT_ERROR)
    slots = zip(layer.crew, BOAT_CREW_SLOTS, strict=False)  # fewer crew than slots is fine
    return [_place_member(layer, spec, slot) for spec, slot in slots]


def _place_member(layer: BoatLayer, spec: CharacterSpec, slot: CrewSlot) -> PlacedCharacter:
    s = layer.scale
    x = layer.x + slot.dx * s if spec.x is None else spec.x
    baseline = layer.y + slot.dy * s if spec.baseline is None else spec.baseline
    height = slot.height * s if spec.height is None else spec.height
    facing = DEFAULT_CREW_FACING if spec.facing is None else spec.facing
    return PlacedCharacter(spec, Placement(x, baseline, height, facing))


def _hull_path(cv: Canvas) -> None:
    cv.M(*HULL_START).C(*HULL_TOP_CURVE).C(*HULL_KEEL_CURVE).C(*HULL_BACK_CURVE).Z()


def _draw_hull(cv: Canvas, ctx: DrawContext) -> None:
    pal = ctx.palette
    top, bottom = HULL_GRADIENT
    _hull_path(cv)
    cv.vgrad(top, bottom, [(0, pal[HULL_TOP_COLOR], 1), (1, pal[HULL_BOTTOM_COLOR], 1)]).fill()
    _hull_path(cv)
    cv.color(pal[HULL_OUTLINE_COLOR]).stroke(HULL_OUTLINE_WIDTH)
    cv.color(pal[TRIM_COLOR]).M(*TRIM_START).C(*TRIM_CURVE).stroke(TRIM_WIDTH)
    cx, cy = STUD_CENTRE
    cv.color(pal[STUD_COLOR]).ellipse(cx, cy, STUD_RADIUS, STUD_RADIUS).fill()


def draw_boat(img: FloatImage, layer: BoatLayer, ctx: DrawContext, index: int) -> FloatImage:
    """Crew first, then the hull on top of their feet, all on one canvas."""
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw_figures(cv, crew_placements(layer), ctx.palette)
    cv.save()
    cv.translate(layer.x, layer.y)
    cv.scale(layer.scale, layer.scale)
    _draw_hull(cv, ctx)
    cv.restore()
    return over(img, cv)


DRAWERS: dict[type, LayerDrawer] = dict([entry(BoatLayer, draw_boat)])
