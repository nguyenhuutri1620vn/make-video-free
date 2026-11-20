"""M10: a character's pose over a slide."""

from __future__ import annotations

import numpy as np
import pytest

from history_shorts.characters.actions import POSES
from history_shorts.characters.idle import idle_params
from history_shorts.characters.pose import REST
from history_shorts.characters.timeline import timeline
from history_shorts.config import LivingSpec
from history_shorts.script_config import SlideAction

SPEC = LivingSpec()


def test_rest_before_and_after_rally() -> None:
    at = timeline("standing", "spear", [SlideAction("a", "rally", 1.0)], None, SPEC)
    assert at(0.5) == REST
    assert at(1.8).far_shoulder > 90  # mid-rally, the free arm is up
    assert at(3.0) == REST


def test_kneel_holds_through_transition_overlap() -> None:  # Review Focus 2
    at = timeline("standing", "none", [SlideAction("a", "kneel", 3.8)], None, SPEC)
    assert at(5.0).crouch == 1.0
    assert at(5.0 + 0.6).crouch == 1.0  # still kneeling while the next slide fades in


def test_kneel_then_stand_up() -> None:
    steps = [SlideAction("a", "kneel", 0.5), SlideAction("a", "stand_up", 2.5)]
    at = timeline("standing", "none", steps, None, SPEC)
    assert at(2.0).crouch == 1.0
    assert at(3.0).crouch == pytest.approx(0.5, abs=0.2)
    assert at(4.0) == REST


def test_seated_start() -> None:
    at = timeline("seated", "none", [], None, SPEC)
    assert at(2.0) == POSES["seated"]


def test_idle_on_top() -> None:
    idle = idle_params(np.random.default_rng(3))
    at = timeline("standing", "none", [], idle, SPEC)
    assert at(0.0) == REST
    assert at(1.0).breath != 0.0


def test_custom_duration() -> None:
    at = timeline("standing", "none", [SlideAction("a", "bow", 1.0, 3.0)], None, SPEC)
    assert at(2.5).torso_lean > 20  # the longer bow is still at its deepest
