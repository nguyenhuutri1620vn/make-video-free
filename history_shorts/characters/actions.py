"""Character actions and named poses as data (M10).

An action is a few keyframes of pose *changes* added to the character's current pose (its
base), eased in and out between keys; the head and arms follow the body a moment later.
``hold`` actions (kneel, sit) leave the character in their last pose; ``to_rest`` actions
(stand up) return the whole base to standing. Keys raise the gesturing arm in the ``near``
fields; ``for_prop`` moves them to the far arm when the near hand holds a prop. Adding an
action is a new entry here; no drawing code changes.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from history_shorts.characters.pose import REST, Pose, add, blend

# Props gripped in the near hand: a gesture then uses the far arm (M12: a sheathed sword
# or a shield on the far forearm leaves the near hand free).
NEAR_HAND_PROPS: Final = frozenset({"flag", "spear", "oar"})
FOLLOW_LAG: Final = 0.08  # seconds the head and arms trail the body
LAGGED: Final = frozenset(
    {"head_tilt", "head_drop", "near_shoulder", "near_elbow", "far_shoulder", "far_elbow"}
)
_NAMES: Final = tuple(f.name for f in dataclasses.fields(Pose))


@dataclass(frozen=True, slots=True)
class Action:
    keys: tuple[tuple[float, Pose], ...]  # (fraction 0..1, pose change); first 0, last 1
    duration: float  # default seconds
    hold: bool = False  # keep the last pose afterwards
    needs_crouch: bool = False  # only from a kneeling or seated pose
    to_rest: bool = False  # ease the whole base pose back to standing
    gesture: bool = False  # keys use the near arm for the free arm (see ``for_prop``)
    with_flag: str | None = None  # the action to use instead when holding a flag


def ease(x: float) -> float:
    """Cosine ease in and out on 0..1."""
    return (1 - math.cos(math.pi * min(max(x, 0.0), 1.0))) / 2


def _arm_swap(pose: Pose) -> Pose:
    return dataclasses.replace(
        pose,
        near_shoulder=pose.far_shoulder,
        near_elbow=pose.far_elbow,
        far_shoulder=pose.near_shoulder,
        far_elbow=pose.near_elbow,
    )


def for_prop(action: Action, prop: str) -> Action:
    """``action`` as performed by a character holding ``prop``."""
    if prop == "flag" and action.with_flag is not None:
        return for_prop(ACTIONS[action.with_flag], prop)
    if action.gesture and prop in NEAR_HAND_PROPS:
        keys = tuple((t, _arm_swap(p)) for t, p in action.keys)
        return dataclasses.replace(action, keys=keys, gesture=False)
    return dataclasses.replace(action, gesture=False)


def _at(keys: tuple[tuple[float, Pose], ...], u: float) -> Pose:
    for (t0, p0), (t1, p1) in zip(keys, keys[1:], strict=False):
        if u <= t1:
            return blend(p0, p1, ease((u - t0) / (t1 - t0)) if t1 > t0 else 1.0)
    return keys[-1][1]


def action_pose(action: Action, u: float, base: Pose) -> Pose:
    """The pose ``u`` (0..1) of the way through ``action`` started from ``base``."""
    u = min(max(u, 0.0), 1.0)
    lag = min(FOLLOW_LAG / action.duration, 0.5)
    late = min(max((u - lag) / (1 - lag), 0.0), 1.0)
    if action.to_rest:
        body, trail = blend(base, REST, ease(u)), blend(base, REST, ease(late))
    else:
        body, trail = add(base, _at(action.keys, u)), add(base, _at(action.keys, late))
    return Pose(*(getattr(trail if n in LAGGED else body, n) for n in _NAMES))


def _wave(peak: Pose, rise: float, fall: float) -> tuple[tuple[float, Pose], ...]:
    """Rest, up to ``peak`` by ``rise``, held until ``fall``, back to rest."""
    return ((0.0, REST), (rise, peak), (fall, peak), (1.0, REST))


RALLY_PEAK: Final = Pose(near_shoulder=120.0, near_elbow=20.0, head_tilt=8.0, torso_lean=4.0)
BOW_PEAK: Final = Pose(torso_lean=25.0, head_drop=3.0, head_tilt=-10.0)
FLAG_PEAK: Final = Pose(near_shoulder=35.0, head_tilt=4.0)
LOOK_PEAK: Final = Pose(head_tilt=6.0)
SEATED_LEAN: Final = 6.0  # deg the upper body leans back when seated

POSES: Final[Mapping[str, Pose]] = MappingProxyType(
    {
        "standing": REST,
        "kneeling": Pose(crouch=1.0),
        "seated": Pose(crouch=1.0, lean_back=SEATED_LEAN),
    }
)

ACTIONS: Final[Mapping[str, Action]] = MappingProxyType(
    {
        "rally": Action(_wave(RALLY_PEAK, 0.35, 0.7), 1.6, gesture=True, with_flag="raise_flag"),
        "bow": Action(_wave(BOW_PEAK, 0.4, 0.6), 1.4),
        "kneel": Action(((0.0, REST), (1.0, POSES["kneeling"])), 1.2, hold=True),
        "sit": Action(((0.0, REST), (1.0, POSES["seated"])), 1.2, hold=True),
        "stand_up": Action(((0.0, REST), (1.0, REST)), 1.2, needs_crouch=True, to_rest=True),
        "raise_flag": Action(_wave(FLAG_PEAK, 0.3, 0.7), 1.6),
        "look": Action(((0.0, REST), (0.5, LOOK_PEAK), (1.0, REST)), 1.0),
    }
)
