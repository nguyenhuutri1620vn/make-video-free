"""Draw one character: placement transform plus the FR-41 part order."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.characters import parts
from history_shorts.characters.roles import CharacterStyle
from history_shorts.config import Palette

LOCAL_HEIGHT: Final = 100.0

PartFunction = Callable[[Canvas, CharacterStyle, Palette], None]

DRAW_ORDER: Final[tuple[str, ...]] = (
    "hair_back",
    "prop_back",
    "robe",
    "belt",
    "sleeves",
    "prop_front",
    "hand",
    "neck",
    "face",
    "features",
    "hair_front",
    "bun",
    "headwrap",
    "crest",
)

_PARTS: Final[dict[str, PartFunction]] = {name: getattr(parts, name) for name in DRAW_ORDER}


@dataclass(frozen=True, slots=True)
class Placement:
    """Where a figure stands: feet at (x, baseline); facing +1 = prop on the right."""

    x: float
    baseline: float
    height: float
    facing: int

    def __post_init__(self) -> None:
        if self.facing not in (-1, 1):
            raise ValueError(f"facing must be -1 or 1, got {self.facing}")
        if self.height <= 0:
            raise ValueError(f"height must be positive, got {self.height}")


def draw_figure(cv: Canvas, style: CharacterStyle, placement: Placement, palette: Palette) -> None:
    """Draw all parts in FR-41 order; mirroring is only ``scale(-1, 1)``."""
    unit = placement.height / LOCAL_HEIGHT
    cv.save()
    cv.translate(placement.x, placement.baseline)
    cv.scale(placement.facing * unit, unit)
    for name in DRAW_ORDER:
        _PARTS[name](cv, style, palette)
    cv.restore()
