"""M10: character actions and named poses are data."""

from __future__ import annotations

import dataclasses

import pytest

from history_shorts.characters.actions import (
    ACTIONS,
    POSES,
    Action,
    action_pose,
    ease,
    for_prop,
)
from history_shorts.characters.pose import REST, Pose

NAMES = ("rally", "bow", "kneel", "sit", "stand_up", "raise_flag", "look")
FIELDS = [f.name for f in dataclasses.fields(Pose)]


def test_action_names() -> None:
    assert set(NAMES) <= set(ACTIONS)
    assert set(POSES) >= {"standing", "kneeling", "seated"}
    assert POSES["standing"] == REST and POSES["kneeling"].crouch == 1.0


def test_ease() -> None:
    assert ease(0.0) == 0.0 and ease(1.0) == 1.0 and ease(0.5) == pytest.approx(0.5)
    xs = [ease(k / 50) for k in range(51)]
    assert all(b >= a for a, b in zip(xs, xs[1:], strict=False))


@pytest.mark.parametrize("name", ["rally", "bow", "raise_flag", "look"])
def test_returning_actions_start_and_end_at_base(name: str) -> None:
    action = ACTIONS[name]
    base = Pose(torso_lean=1.0)
    assert action_pose(action, 0.0, base) == base
    assert action_pose(action, 1.0, base) == pytest.approx(base)  # type: ignore[comparison-overlap]


def test_hold_ends_at_last_key() -> None:
    assert action_pose(ACTIONS["kneel"], 1.0, REST).crouch == 1.0
    assert ACTIONS["kneel"].hold and ACTIONS["sit"].hold
    assert not ACTIONS["rally"].hold


def test_stand_up_returns_to_standing() -> None:
    kneeling = POSES["seated"]
    assert ACTIONS["stand_up"].needs_crouch
    assert action_pose(ACTIONS["stand_up"], 0.0, kneeling) == kneeling
    end = action_pose(ACTIONS["stand_up"], 1.0, kneeling)
    assert end.crouch == pytest.approx(0.0) and end.lean_back == pytest.approx(0.0)


@pytest.mark.parametrize("name", NAMES)
def test_no_overshoot(name: str) -> None:
    action = ACTIONS[name]
    base = POSES["kneeling"] if action.needs_crouch else REST
    keys = [getattr(base, f) for f in FIELDS]
    for pose in (action_pose(action, k / 100, base) for k in range(101)):
        for f, b in zip(FIELDS, keys, strict=True):
            lo = min([b] + [b + getattr(p, f) for _, p in action.keys] + [0.0])
            hi = max([b] + [b + getattr(p, f) for _, p in action.keys] + [0.0])
            assert lo - 1e-9 <= getattr(pose, f) <= hi + 1e-9, (name, f)


def test_rally_uses_free_arm_for_spear() -> None:
    rally = for_prop(ACTIONS["rally"], "spear")
    peak = action_pose(rally, 0.5, REST)
    assert peak.far_shoulder > 90 and peak.near_shoulder == 0


def test_rally_uses_near_arm_without_prop() -> None:
    peak = action_pose(for_prop(ACTIONS["rally"], "none"), 0.5, REST)
    assert peak.near_shoulder > 90 and peak.far_shoulder == 0


def test_rally_with_flag_raises_the_flag() -> None:
    assert for_prop(ACTIONS["rally"], "flag") == for_prop(ACTIONS["raise_flag"], "flag")


def test_actions_are_data() -> None:
    wave = Action(keys=((0.0, REST), (0.5, Pose(far_shoulder=40)), (1.0, REST)), duration=1.0)
    assert action_pose(wave, 0.5, REST).far_shoulder == pytest.approx(40, abs=4)


@pytest.mark.parametrize(
    ("prop", "arm"),
    [("sword_sheathed", "near"), ("shield", "near"), ("spear", "far"), ("flag", "near")],
)
def test_rally_arm_by_prop(prop: str, arm: str) -> None:  # M12
    peak = action_pose(for_prop(ACTIONS["rally"], prop), 0.5, REST)
    raised = peak.near_shoulder if arm == "near" else peak.far_shoulder
    assert raised > 30  # (flag raises the flag arm, which is the near one)
