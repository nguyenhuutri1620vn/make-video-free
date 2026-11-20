"""A character's joint angles (M10): rest is all zero; kits draw jointed parts from it.

Angles are degrees in the character's local frame before mirroring (facing +1). A style
whose ``pose`` is ``None`` is drawn with the kit's original still paths; any ``Pose``,
``REST`` included, is drawn with the jointed parts.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Pose:
    head_tilt: float = 0.0  # deg, + = chin up
    head_drop: float = 0.0  # units the head moves forward and down when bowing
    torso_lean: float = 0.0  # deg about the waist, + = forward (toward facing)
    breath: float = 0.0  # -1..1, scales the chest a little
    near_shoulder: float = 0.0  # deg, + = arm swings forward and up
    near_elbow: float = 0.0  # deg, + = forearm bends up
    far_shoulder: float = 0.0
    far_elbow: float = 0.0
    crouch: float = 0.0  # 0 standing .. 1 kneeling
    lean_back: float = 0.0  # deg, seated only
    flag_wave: float = 0.0  # loop phase of a held flag's cloth


REST: Final = Pose()
_NAMES: Final = tuple(f.name for f in dataclasses.fields(Pose))


def blend(a: Pose, b: Pose, w: float) -> Pose:
    """Per-joint linear mix: ``a`` at 0, ``b`` at 1."""
    return Pose(*(getattr(a, n) + (getattr(b, n) - getattr(a, n)) * w for n in _NAMES))


def add(a: Pose, b: Pose) -> Pose:
    """Per-joint sum; ``crouch`` stays within 0..1."""
    total = Pose(*(getattr(a, n) + getattr(b, n) for n in _NAMES))
    return dataclasses.replace(total, crouch=min(max(total.crouch, 0.0), 1.0))
