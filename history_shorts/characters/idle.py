"""Idle life of a character on a living slide (M10): breathing, a small sway, a waving flag.

Every motion repeats exactly every ``period`` seconds (a whole number of cycles), so an
idle character loops without a seam, and is measured from ``t = 0``, so the first frame is
the rest pose. Phases come from the character's own RNG, so neighbours move out of step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from numpy.random import Generator

from history_shorts.characters.pose import Pose
from history_shorts.config import LivingSpec

SWAY_WEIGHTS: Final = (0.7, 0.3)  # first and second harmonic of the slow sway
ARM_SHARE: Final = 1.0  # free arms sway as much as the torso, out of step with it


@dataclass(frozen=True, slots=True)
class IdleParams:
    """Random phases (radians) of one character's sway channels."""

    torso: tuple[float, float]
    head: tuple[float, float]
    near: tuple[float, float]
    far: tuple[float, float]
    flag: float  # loop fraction


def idle_params(rng: Generator) -> IdleParams:
    def pair() -> tuple[float, float]:
        a, b = rng.uniform(0, 2 * math.pi, 2)
        return float(a), float(b)

    return IdleParams(pair(), pair(), pair(), pair(), float(rng.uniform(0, 1)))


def _sway(phases: tuple[float, float], turn: float) -> float:
    """Smooth periodic value in -1..1, zero at ``turn = 0``."""
    total = 0.0
    for n, (w, phi) in enumerate(zip(SWAY_WEIGHTS, phases, strict=True)):
        total += w * (math.sin((n + 1) * turn + phi) - math.sin(phi))
    return 0.5 * total / sum(SWAY_WEIGHTS)


def idle_pose(params: IdleParams, t: float, period: float, spec: LivingSpec) -> Pose:
    """The idle pose at ``t`` seconds into a loop of ``period`` seconds."""
    turn = 2 * math.pi * t / period
    cycles = max(1, round(spec.flag_wave_hz * period))
    flag = (cycles * t / period) % 1.0
    return Pose(
        breath=spec.breath_scale * math.sin(turn),
        torso_lean=spec.idle_sway_deg * _sway(params.torso, turn),
        head_tilt=spec.idle_head_deg * _sway(params.head, turn),
        near_shoulder=ARM_SHARE * spec.idle_sway_deg * _sway(params.near, turn),
        far_shoulder=ARM_SHARE * spec.idle_sway_deg * _sway(params.far, turn),
        flag_wave=flag,
    )
