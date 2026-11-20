"""A character's pose over a slide (M10): starting pose, timed actions, idle life.

``timeline`` returns a function of slide seconds. Before an action the character holds its
base pose; during it, the action's pose; after a ``hold`` action (kneel, sit) the new base
is its last pose, after ``stand_up`` it is standing again. Idle breathing and sway are added
on top throughout, so the character never freezes between actions.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from history_shorts.characters.actions import ACTIONS, POSES, action_pose, for_prop
from history_shorts.characters.idle import IdleParams, idle_pose
from history_shorts.characters.pose import REST, Pose, add
from history_shorts.config import LivingSpec
from history_shorts.script_config import SlideAction

Timeline = Callable[[float], Pose]


def action_seconds(action: SlideAction) -> float:
    return action.duration if action.duration is not None else ACTIONS[action.do].duration


def timeline(
    start: str,
    prop: str,
    actions: Sequence[SlideAction],
    idle: IdleParams | None,
    spec: LivingSpec,
) -> Timeline:
    """Pose at ``t`` slide seconds for a character starting in pose ``start``."""
    steps = sorted(actions, key=lambda a: a.at)
    period = spec.idle_loop_seconds

    def at(t: float) -> Pose:
        base = POSES[start]
        pose = base
        for step in steps:
            action = for_prop(ACTIONS[step.do], prop)
            seconds = action_seconds(step)
            if t < step.at:
                break
            if t <= step.at + seconds:
                pose = action_pose(action, (t - step.at) / seconds, base)
                break
            if action.hold:
                base = action_pose(action, 1.0, base)
            elif action.to_rest:
                base = REST
            pose = base
        else:
            pose = base
        return pose if idle is None else add(pose, idle_pose(idle, t % period, period, spec))

    return at
