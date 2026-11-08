"""Formations: where characters stand (FR-47). Positions only; nothing is drawn here.

``place`` returns the characters in draw order, back rows first, so the caller can draw
them as given. ``facing`` defaults outward: left of the centre looks left, the rest right.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from history_shorts.characters.figure import Placement
from history_shorts.config import CharacterSpec
from history_shorts.layout import CANVAS_W

CENTRE_X: Final = CANVAS_W / 2

# centre_pair: (x offset from the centre, baseline offset, height) per tier, front to back.
# The pair sits at CENTRE_X -/+ offset; a lone last character stands at CENTRE_X.
CENTRE_PAIR_TIERS: Final[tuple[tuple[float, float, float], ...]] = (
    (108, 6, 565),  # front: x 432 / 648
    (255, 0, 475),  # middle: x 285 / 795
    (390, -4, 420),  # outer: x 150 / 930
)
CENTRE_PAIR_MAX: Final = 2 * len(CENTRE_PAIR_TIERS)

LINE_X: Final = (150.0, 930.0)
LINE_HEIGHT: Final = 475.0
LINE_MAX: Final = 7

V_CENTRE_BASELINE: Final = 6.0
V_CENTRE_HEIGHT: Final = 565.0
V_STEP_DX: Final = 135.0
V_STEP_HEIGHT: Final = 0.88
V_STEP_BASELINE: Final = -4.0
V_MAX: Final = 7

FORMATION_NAMES: Final = ("centre_pair", "line", "v_shape")


@dataclass(frozen=True, slots=True)
class PlacedCharacter:
    """A character spec with its resolved canvas placement."""

    spec: CharacterSpec
    placement: Placement


@dataclass(frozen=True, slots=True)
class _Slot:
    x: float
    baseline: float
    height: float
    row: int  # larger = further back = drawn earlier


def _centre_pair_slots(count: int, baseline: float) -> list[_Slot]:
    slots: list[_Slot] = []
    for index in range(count):
        tier = index // 2
        dx, db, height = CENTRE_PAIR_TIERS[tier]
        alone = index == count - 1 and count % 2 == 1
        x = CENTRE_X if alone else CENTRE_X + (-dx if index % 2 == 0 else dx)
        slots.append(_Slot(x, baseline + db, height, row=tier))
    return slots


def _line_slots(count: int, baseline: float) -> list[_Slot]:
    left, right = LINE_X
    step = (right - left) / (count - 1) if count > 1 else 0.0
    first = left if count > 1 else CENTRE_X
    return [_Slot(first + k * step, baseline, LINE_HEIGHT, row=0) for k in range(count)]


def _v_shape_slots(count: int, baseline: float) -> list[_Slot]:
    """Index 0 is the centre; after it the characters alternate left, right, per step out."""
    slots = [_Slot(CENTRE_X, baseline + V_CENTRE_BASELINE, V_CENTRE_HEIGHT, row=0)]
    for index in range(1, count):
        step = (index + 1) // 2
        side = -1 if index % 2 == 1 else 1
        slots.append(
            _Slot(
                CENTRE_X + side * V_STEP_DX * step,
                baseline + V_CENTRE_BASELINE + V_STEP_BASELINE * step,
                V_CENTRE_HEIGHT * V_STEP_HEIGHT**step,
                row=step,
            )
        )
    return slots


# name -> (slot builder, maximum count)
_FORMATIONS: Final = {
    "centre_pair": (_centre_pair_slots, CENTRE_PAIR_MAX),
    "line": (_line_slots, LINE_MAX),
    "v_shape": (_v_shape_slots, V_MAX),
}


def count_error(formation: str, count: int) -> str | None:
    """The message for a wrong character count, or None when ``count`` fits."""
    limit = _FORMATIONS[formation][1]
    if 1 <= count <= limit:
        return None
    return f"formation {formation} supports 1–{limit} characters"


def _facing(spec: CharacterSpec, x: float) -> int:
    if spec.facing is not None:
        return spec.facing
    return -1 if x < CENTRE_X else 1


def _placed(spec: CharacterSpec, slot: _Slot) -> PlacedCharacter:
    x = slot.x if spec.x is None else spec.x
    baseline = slot.baseline if spec.baseline is None else spec.baseline
    height = slot.height if spec.height is None else spec.height
    return PlacedCharacter(spec, Placement(x, baseline, height, _facing(spec, x)))


def place(
    formation: str | None, specs: Sequence[CharacterSpec], baseline: float
) -> list[PlacedCharacter]:
    """Resolve each spec to a placement, returned in draw order (back rows first).

    With ``formation=None`` every spec needs its own ``x``; ``baseline`` and ``LINE_HEIGHT``
    fill what it omits. An explicit ``x``, ``baseline``, ``height`` or ``facing`` on a spec
    always beats the formation's slot. Raises ``ValueError`` for an unknown formation, a
    wrong count, or a missing ``x``.
    """
    if formation is None:
        slots = []
        for spec in specs:
            if spec.x is None:
                raise ValueError(f"character '{spec.role}' needs x without a formation")
            slots.append(_Slot(spec.x, baseline, LINE_HEIGHT, row=0))
    else:
        if formation not in _FORMATIONS:
            raise ValueError(f"unknown formation '{formation}'")
        problem = count_error(formation, len(specs))
        if problem is not None:
            raise ValueError(problem)
        slots = _FORMATIONS[formation][0](len(specs), baseline)
    order = sorted(range(len(specs)), key=lambda k: -slots[k].row)  # stable: input order in a row
    return [_placed(specs[k], slots[k]) for k in order]
