"""M10: the Pose type of a character's joints."""

from __future__ import annotations

import dataclasses

import pytest

from history_shorts.characters.pose import REST, Pose, add, blend
from history_shorts.characters.roles import CharacterStyle

A = Pose(head_tilt=4.0, near_shoulder=30.0, crouch=0.2, flag_wave=0.1)
B = Pose(head_tilt=-2.0, near_shoulder=90.0, crouch=1.0, torso_lean=10.0)


def test_rest_is_all_zero() -> None:
    assert all(getattr(REST, f.name) == 0.0 for f in dataclasses.fields(Pose))


def test_blend_ends() -> None:
    assert blend(A, B, 0.0) == A
    assert blend(A, B, 1.0) == B


def test_blend_middle() -> None:
    mid = blend(A, B, 0.5)
    assert mid.near_shoulder == pytest.approx(60.0)
    assert mid.crouch == pytest.approx(0.6)


def test_add_rest_is_identity() -> None:
    assert add(REST, A) == A
    assert add(A, REST) == A


def test_add_clips_crouch() -> None:
    assert add(B, Pose(crouch=0.5)).crouch == 1.0
    assert add(REST, Pose(crouch=-0.5)).crouch == 0.0


def test_style_pose_defaults_to_none() -> None:
    fields = {f.name: f for f in dataclasses.fields(CharacterStyle)}
    assert fields["pose"].default is None
