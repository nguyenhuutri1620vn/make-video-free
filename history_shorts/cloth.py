"""A travelling wave for flag cloth (M10), shared by banners, the elephant and characters.

The cloth hangs from a pole at ``pole_x``; a point ``u = |x - pole_x| / width`` of the way
out moves vertically by a sine travelling away from the pole whose amplitude grows with
``u``, so the cloth stays fixed at the pole. Every offset is measured from phase 0, which is
therefore the still drawing, and the motion is periodic in the phase.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def wave_point(
    x: float, y: float, pole_x: float, width: float, phase: float, amp: float, shift: float
) -> tuple[float, float]:
    """``(x, y)`` displaced by the wave at loop ``phase``; ``amp`` is a fraction of ``width``.

    ``shift`` (radians) offsets the wave so neighbouring flags do not move in step."""
    u = abs(x - pole_x) / width
    turn = 2 * math.pi * (phase - u) + shift
    rest = -2 * math.pi * u + shift
    return x, y + amp * width * u * (math.sin(turn) - math.sin(rest))


@dataclass(frozen=True, slots=True)
class ClothWave:
    """``wave_point`` with its pole, width, phase, amplitude and shift bound."""

    pole_x: float
    width: float
    phase: float
    amp: float
    shift: float

    def pt(self, x: float, y: float) -> tuple[float, float]:
        return wave_point(x, y, self.pole_x, self.width, self.phase, self.amp, self.shift)
