"""M10: idle breathing and sway of a character on a living slide."""

from __future__ import annotations

import numpy as np
import pytest

from history_shorts.characters.idle import idle_params, idle_pose
from history_shorts.characters.pose import REST
from history_shorts.config import LivingSpec

SPEC = LivingSpec()
PERIOD = SPEC.idle_loop_seconds


def _params(seed: int) -> object:
    return idle_params(np.random.default_rng(seed))


def test_idle_starts_at_rest_except_flag() -> None:
    pose = idle_pose(_params(1), 0.0, PERIOD, SPEC)
    assert pose == REST


def test_idle_periodic() -> None:
    p = _params(2)
    a, b = idle_pose(p, 0.3, PERIOD, SPEC), idle_pose(p, 0.3 + PERIOD, PERIOD, SPEC)
    for name in ("breath", "torso_lean", "head_tilt", "far_shoulder", "near_shoulder"):
        assert getattr(b, name) == pytest.approx(getattr(a, name), abs=1e-9)
    d = (b.flag_wave - a.flag_wave) % 1.0
    assert min(d, 1.0 - d) == pytest.approx(0.0, abs=1e-9)


def test_idle_bounded() -> None:
    p = _params(3)
    for k in range(200):
        pose = idle_pose(p, k * PERIOD / 200, PERIOD, SPEC)
        assert abs(pose.torso_lean) <= SPEC.idle_sway_deg + 1e-9
        assert abs(pose.head_tilt) <= SPEC.idle_head_deg + 1e-9
        assert abs(pose.breath) <= SPEC.breath_scale + 1e-12
        assert 0.0 <= pose.flag_wave < 1.0


def test_idle_out_of_step() -> None:
    t = PERIOD / 4
    assert idle_pose(_params(4), t, PERIOD, SPEC).torso_lean != pytest.approx(
        idle_pose(_params(5), t, PERIOD, SPEC).torso_lean, abs=1e-3
    )


def test_idle_smooth() -> None:
    p, dt = _params(6), 1 / 24
    lean = [idle_pose(p, k * dt, PERIOD, SPEC).torso_lean for k in range(200)]
    assert np.abs(np.diff(lean)).max() <= 0.1


def test_idle_moves() -> None:
    p = _params(7)
    pose = idle_pose(p, PERIOD / 4, PERIOD, SPEC)
    assert pose.breath > 0.5 * SPEC.breath_scale
    assert pose.flag_wave > 0
