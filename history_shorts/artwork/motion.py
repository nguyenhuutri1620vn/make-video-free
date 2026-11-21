"""Motion declared in artwork files (M11), applied to a part's points per loop phase.

Every offset is measured from phase 0, so phase 0 is the still drawing, and is periodic in
the phase. Random phases come from the layer RNG, so two copies of one file move out of
step. ``scale`` is the theme's ``living.artwork_motion`` knob.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from typing import Final

import numpy as np

from history_shorts.artwork.model import Part
from history_shorts.artwork.path import Op, path_bounds
from history_shorts.cloth import wave_point
from history_shorts.compose import DrawContext

ARTWORK_MOTION_KEY: Final = 900  # RNG key offset of an artwork layer's motion phases
WEIGHTS: Final = (1.0, 0.5, 0.25)  # harmonics of the smooth periodic wobble
RISE_WAVES: Final = 1.0  # wave crests along a rising part's height


def motion_phases(ctx: DrawContext, index: int, count: int) -> np.ndarray:
    """(count, 2, 3) random phases in radians: per part, two channels, three harmonics."""
    return ctx.rng(index + ARTWORK_MOTION_KEY).uniform(0, 2 * math.pi, (count, 2, len(WEIGHTS)))


def _wobble(phase: float, phis: np.ndarray) -> float:
    """Smooth periodic value in about -1..1, exactly 0 at phase 0."""
    total = sum(
        w * (math.sin(2 * math.pi * (n + 1) * phase + phis[n]) - math.sin(phis[n]))
        for n, w in enumerate(WEIGHTS)
    )
    return float(total / sum(WEIGHTS))


def _map_points(
    ops: tuple[Op, ...], move: Callable[[float, float], tuple[float, float]]
) -> tuple[Op, ...]:
    out: list[Op] = []
    for kind, values in ops:
        pts: list[float] = []
        for k in range(0, len(values), 2):
            x, y = move(values[k], values[k + 1])
            pts += [x, y]
        out.append((kind, tuple(pts)))
    return tuple(out)


def move_part(part: Part, phase: float, phis: np.ndarray, scale: float) -> Part:
    """``part`` at loop ``phase``; ``phis`` its (2, 3) random phases."""
    motion = part.motion
    if motion is None or scale == 0:
        return part
    amp, kind = motion.amp * scale, motion.kind
    if kind == "pulse":
        factor = 1 + amp * math.sin(2 * math.pi * phase)
        return dataclasses.replace(
            part, alpha=max(part.alpha * factor, 0.0)
        )  # clamped when painted
    x0, y0, x1, y1 = path_bounds(part.ops)
    height = max(y1 - y0, 1e-9)
    if kind == "flicker":
        dx, dy = amp * _wobble(phase, phis[0]), amp * _wobble(phase, phis[1])

        def move(x: float, y: float) -> tuple[float, float]:
            w = (y1 - y) / height  # 0 at the bottom of the part, 1 at its top
            return x + w * dx, y + w * dy
    elif kind == "wave":
        width = max(abs(x0 - motion.pole), abs(x1 - motion.pole), 1e-9)

        def move(x: float, y: float) -> tuple[float, float]:
            return wave_point(x, y, motion.pole, width, phase, amp, float(phis[0][0]))
    elif kind == "sway":
        angle = math.radians(motion.deg * scale) * _wobble(phase, phis[0])
        c, s = math.cos(angle), math.sin(angle)
        px, py = motion.pivot

        def move(x: float, y: float) -> tuple[float, float]:
            dx_, dy_ = x - px, y - py
            return px + c * dx_ - s * dy_, py + s * dx_ + c * dy_
    else:  # rise: a sideways wave travelling up the part

        def move(x: float, y: float) -> tuple[float, float]:
            u = (y1 - y) / height
            lag = 2 * math.pi * RISE_WAVES * u
            turn = 2 * math.pi * phase
            return x + amp * u * (math.sin(turn - lag) - math.sin(-lag)), y

    return dataclasses.replace(part, ops=_map_points(part.ops, move))
