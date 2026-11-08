"""The costume-kit type: one era's figure as data plus part functions (FR-45).

A kit is everything ``figure.py`` needs to draw, box and mask a character without knowing
what the character looks like: its part functions in drawing order, which parts form the
head, the props it can hold, and the local-frame extents used for bounding boxes (FR-48).
All geometry is in the shared local frame: feet at (0, 0), 100 units tall, y up negative.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import numpy as np

from history_shorts.canvas import Canvas
from history_shorts.config import Palette
from history_shorts.primitives import Point

if TYPE_CHECKING:
    from history_shorts.characters.roles import CharacterStyle

VARIATION_STREAM: Final = 49  # second RNG word, so a character seed never collides with others
VARIATION_RANGE: Final = 0.1  # factors are uniform in 1 +- 10 % (FR-49)


@dataclass(frozen=True, slots=True)
class Variation:
    """Per-character scale factors (FR-49); 1.0 everywhere is the reference look.

    A kit may honour any of them: ``bun`` scales the bun, ``sash`` the sash ribbons'
    length, ``dot_spacing`` the gap between hem dots.
    """

    bun: float
    sash: float
    dot_spacing: float


def variation_for(seed: int | None) -> Variation:
    """The identity for no seed; otherwise bun, sash and dot spacing drawn in that order."""
    if seed is None:
        return Variation(1.0, 1.0, 1.0)
    rng = np.random.default_rng([seed, VARIATION_STREAM])
    lo, hi = 1 - VARIATION_RANGE, 1 + VARIATION_RANGE
    return Variation(
        float(rng.uniform(lo, hi)), float(rng.uniform(lo, hi)), float(rng.uniform(lo, hi))
    )


PartFn = Callable[[Canvas, "CharacterStyle", Palette], None]
ShaftFn = Callable[[str], tuple[Point, Point] | None]
LocalBox = tuple[float, float, float, float]  # (x0, y0, x1, y1) in local units


@dataclass(frozen=True, slots=True)
class KitExtents:
    """Extreme points of a kit's regions in the local frame, for bounding boxes.

    The head runs from ``head_top`` (``crest_top`` when the style has a crest) down to
    ``chin_y``; ``head_mask`` also cuts the head pixels at ``chin_y``. ``props`` maps each
    prop with a visible object to its box, flag or spear tip included; props without an
    entry (e.g. ``none``) have no prop box.
    """

    head_half_width: float
    head_top: float
    crest_top: float
    chin_y: float
    body: LocalBox
    props: Mapping[str, LocalBox]

    def head_box(self, crest: bool) -> LocalBox:
        top = self.crest_top if crest else self.head_top
        return (-self.head_half_width, top, self.head_half_width, self.chin_y)


@dataclass(frozen=True, slots=True)
class Kit:
    """A pluggable part set. ``figure.py`` resolves everything through one of these."""

    name: str
    draw_order: tuple[str, ...]
    parts: Mapping[str, PartFn]
    head_parts: frozenset[str]
    props: frozenset[str]
    hand_center: Point
    shaft_segment: ShaftFn
    extents: KitExtents

    def __post_init__(self) -> None:
        for name in self.draw_order:
            if name not in self.parts:
                raise ValueError(f"kit '{self.name}': no part '{name}' for its draw order")
        for name in sorted(self.head_parts):
            if name not in self.draw_order:
                raise ValueError(f"kit '{self.name}': head part '{name}' is not in the draw order")
        for prop in sorted(self.extents.props):
            if prop not in self.props:
                raise ValueError(f"kit '{self.name}': extent for prop '{prop}' not in props")

    @property
    def head_order(self) -> tuple[str, ...]:
        """The head parts in drawing order."""
        return tuple(name for name in self.draw_order if name in self.head_parts)
