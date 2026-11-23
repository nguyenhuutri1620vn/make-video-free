"""M12: jointed drawing of the warrior_male kit from a Pose."""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.characters import resolve_style
from history_shorts.characters.figure import Placement, draw_figure
from history_shorts.characters.kits import kit_for
from history_shorts.characters.pose import REST, Pose
from history_shorts.config import CharacterSpec

SCALE = 8
W, H = 80 * SCALE, 170 * SCALE
WARRIORS = ("viet_general", "viet_soldier", "northern_general", "northern_soldier")
PROPS = ("flag", "spear", "sword_sheathed", "shield", "none")
SAMPLE_POSES = [
    Pose(torso_lean=8.0),
    Pose(head_tilt=10.0, head_drop=3.0),
    Pose(far_shoulder=120.0, far_elbow=30.0),
    Pose(near_shoulder=40.0, near_elbow=60.0),
    Pose(breath=0.01, torso_lean=-5.0, far_shoulder=60.0),
]


def _style(palette: Any, role: str, prop: str, pose: Pose | None = REST) -> Any:
    spec = CharacterSpec(role=role, prop=prop)  # type: ignore[arg-type]
    return dataclasses.replace(resolve_style(spec, palette), pose=pose)


def _render(style: Any, palette: Any, facing: int = 1, names: Any = None) -> Any:
    cv = Canvas(W, H)
    draw_figure(cv, style, Placement(40 * SCALE, 160 * SCALE, 100 * SCALE, facing), palette, names)
    rgb, alpha = cv.to_premul()
    return np.concatenate([rgb, alpha[..., None]], axis=-1)


def _px(point: tuple[float, float]) -> tuple[int, int]:
    return round((point[1] + 160) * SCALE), round((point[0] + 40) * SCALE)


def test_kit_has_a_rig() -> None:
    style = resolve_style(CharacterSpec(role="viet_soldier"), _palette())
    assert kit_for(style).rig is not None


def _palette() -> Any:
    from pathlib import Path

    from history_shorts.config import load_theme

    root = Path(__file__).resolve().parents[1]
    return load_theme(root / "themes" / "son_mai" / "theme.json")[0].palette


@pytest.mark.parametrize("role", WARRIORS)
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("prop", PROPS)
def test_rest_pose_close_to_still(role: str, facing: int, prop: str, palette: Any) -> None:
    still = _render(_style(palette, role, prop, None), palette, facing)
    rest = _render(_style(palette, role, prop, REST), palette, facing)
    diff = np.abs(still - rest)
    assert diff.mean() < 1 / 255
    assert diff.max() < 0.25


@pytest.mark.parametrize("pose", SAMPLE_POSES)
@pytest.mark.parametrize("prop", ["flag", "spear"])
def test_hand_on_shaft(pose: Pose, prop: str, palette: Any) -> None:  # AC-47
    style = _style(palette, "viet_soldier", prop, pose)
    kit = kit_for(style)
    joints = kit.rig.joints(style, pose)  # type: ignore[union-attr]
    hand = joints["hand"].apply(kit.hand_center)
    segment = kit.shaft_segment(prop)
    assert segment is not None
    (x0, y0), (x1, y1) = (joints["prop"].apply(p) for p in segment)
    dist = abs((y1 - y0) * hand[0] - (x1 - x0) * hand[1] + x1 * y0 - y1 * x0)
    assert dist / math.hypot(x1 - x0, y1 - y0) <= 0.5


@pytest.mark.parametrize("pose", SAMPLE_POSES)
def test_no_crack_at_elbows(pose: Pose, palette: Any) -> None:  # AC-48 / AC-34
    from history_shorts.characters.kits.warrior_male_rig import ELBOWS

    style = _style(palette, "viet_soldier", "none", pose)
    joints = kit_for(style).rig.joints(style, pose)  # type: ignore[union-attr]
    alpha = _render(style, palette, names=("far_sleeve", "near_sleeve"))[..., 3]
    for side, elbow in ELBOWS.items():
        cx, cy = joints[f"{side}_arm"].apply(elbow)
        for dx, dy in [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)]:
            assert alpha[_px((cx + dx, cy + dy))] > 0.95, (side, dx, dy)


@pytest.mark.parametrize("pose", [Pose(crouch=1.0), Pose(torso_lean=12.0)])
def test_waist_closed(pose: Pose, palette: Any) -> None:
    from history_shorts.characters.kits.warrior_male_rig import CROUCH_DROP

    style = _style(palette, "northern_soldier", "none", pose)
    alpha = _render(style, palette, names=("body", "belt"))[..., 3]
    waist = -52 + CROUCH_DROP * pose.crouch
    for x in (-8.0, 0.0, 8.0):
        for dy in (-1.0, 0.0, 1.0):
            assert alpha[_px((x, waist + dy))] > 0.95


def test_crouch_drops_head_keeps_feet(palette: Any) -> None:
    from history_shorts.characters.kits.warrior_male_rig import CROUCH_DROP

    def rows(pose: Pose) -> tuple[float, float]:
        alpha = _render(_style(palette, "viet_soldier", "none", pose), palette)[..., 3]
        r = np.nonzero(alpha.max(axis=1) > 0.5)[0]
        return r.min() / SCALE - 160, (r.max() + 1) / SCALE - 160

    stand, kneel = rows(REST), rows(Pose(crouch=1.0))
    assert kneel[0] - stand[0] == pytest.approx(CROUCH_DROP, abs=0.6)
    assert kneel[1] == pytest.approx(stand[1], abs=0.25)


def test_shield_follows_the_far_forearm(palette: Any) -> None:
    rest = _render(_style(palette, "northern_soldier", "shield"), palette, names=("shield",))
    raised = _render(
        _style(palette, "northern_soldier", "shield", Pose(far_shoulder=60.0)),
        palette,
        names=("shield",),
    )
    assert not np.array_equal(rest[..., 3], raised[..., 3])
    style = _style(palette, "northern_soldier", "shield", Pose(far_shoulder=60.0))
    joints = kit_for(style).rig.joints(style, style.pose)  # type: ignore[union-attr]
    cx, cy = joints["far_fore"].apply((-20.0, -50.0))
    assert raised[_px((cx, cy))][3] > 0.95


@pytest.mark.parametrize("lean", [8.0, -8.0])
def test_cape_closed_at_the_waist(lean: float, palette: Any) -> None:
    style = _style(palette, "viet_general", "flag", Pose(torso_lean=lean))
    alpha = _render(style, palette, names=("cape",))[..., 3]
    side = -1.0 if lean > 0 else 1.0  # the side whose upper cape lifts off the cut
    for x in (15.0, 17.0, 19.0):
        for y in (-53.5, -53.0, -52.5):
            assert alpha[_px((side * x, y))] > 0.95, (x, y)


ACTION_NAMES = ("rally", "bow", "kneel", "sit", "raise_flag", "look")


@pytest.mark.parametrize("role", WARRIORS)
@pytest.mark.parametrize("name", ACTION_NAMES)
def test_actions_run_on_every_role(role: str, name: str, palette: Any) -> None:  # AC-48
    from history_shorts.characters.actions import ACTIONS, action_pose, for_prop

    prop = "flag" if name == "raise_flag" else resolve_style(CharacterSpec(role=role), palette).prop
    action = for_prop(ACTIONS[name], prop)
    for k in range(11):
        pose = action_pose(action, k / 10, REST)
        alpha = _render(_style(palette, role, prop, pose), palette)[..., 3]
        assert alpha.sum() > 1000


def test_mirrored_shield_bearer_rally(palette: Any) -> None:  # Review Focus 4
    from history_shorts.characters.actions import ACTIONS, action_pose, for_prop

    pose = action_pose(for_prop(ACTIONS["rally"], "shield"), 0.5, REST)
    assert pose.near_shoulder > 90 and pose.far_shoulder == 0
    style = _style(palette, "northern_soldier", "shield", pose)
    shield = _render(style, palette, -1, names=("shield",))[..., 3]
    ys, xs = np.nonzero(shield > 0.5)
    assert xs.mean() / SCALE - 40 > 0  # mirrored: the far (shield) arm is on the right
    sleeves = _render(style, palette, -1, names=("near_sleeve",))[..., 3]
    top = np.nonzero(sleeves.max(axis=1) > 0.5)[0].min() / SCALE - 160
    assert top < -95  # the near arm is up


def test_warrior_flag_waves(palette: Any) -> None:  # final review 1
    rest = _render(_style(palette, "viet_general", "flag", REST), palette, names=("prop_back",))
    wave = _render(
        _style(palette, "viet_general", "flag", Pose(flag_wave=0.25)), palette, names=("prop_back",)
    )
    loop = _render(
        _style(palette, "viet_general", "flag", Pose(flag_wave=1.0)), palette, names=("prop_back",)
    )
    diff = np.abs(rest - wave).max(axis=2)
    ys, xs = np.nonzero(diff > 0.1)
    assert len(ys) > 0
    assert xs.min() / SCALE - 40 > 19.5  # the pole never moves
    assert np.abs(loop - rest).max() < 0.02
