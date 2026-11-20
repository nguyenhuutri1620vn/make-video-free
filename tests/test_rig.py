"""M10: jointed drawing of the ancient_female kit from a Pose."""

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
from history_shorts.characters.kits.ancient_female import HAND_CENTER, shaft_segment
from history_shorts.characters.pose import REST, Pose
from history_shorts.characters.rig import Affine, about, rotate, translate
from history_shorts.config import CharacterSpec

SCALE = 8  # px per local unit
W, H = 80 * SCALE, 160 * SCALE  # canvas around the figure: x -40..40, y -150..10
ROLE_MATRIX = [
    (role, facing, prop, crest)
    for role in ("leader", "general", "boat_crew")
    for facing in (-1, 1)
    for prop in ("flag", "spear", "oar", "none")
    for crest in (True, False)
]
SAMPLE_POSES = [
    Pose(torso_lean=8.0),
    Pose(head_tilt=10.0, head_drop=3.0),
    Pose(far_shoulder=120.0, far_elbow=30.0),
    Pose(near_shoulder=40.0, near_elbow=60.0),
    Pose(breath=0.01, torso_lean=-5.0, far_shoulder=60.0),
]


def _style(palette: Any, prop: str = "spear", pose: Pose | None = REST, **kw: Any) -> Any:
    spec = CharacterSpec(role=kw.pop("role", "general"), prop=prop, **kw)  # type: ignore[arg-type]
    return dataclasses.replace(resolve_style(spec, palette), pose=pose)


def _render(style: Any, palette: Any, facing: int = 1, names: Any = None) -> Any:
    cv = Canvas(W, H)
    draw_figure(cv, style, Placement(40 * SCALE, 150 * SCALE, 100 * SCALE, facing), palette, names)
    rgb, alpha = cv.to_premul()
    return np.concatenate([rgb, alpha[..., None]], axis=-1)


def _px(point: tuple[float, float]) -> tuple[int, int]:
    return round((point[1] + 150) * SCALE), round((point[0] + 40) * SCALE)


def test_affine_composition() -> None:
    m = translate(5, 0) @ rotate(90)
    x, y = m.apply((1.0, 0.0))
    assert (x, y) == pytest.approx((5.0, 1.0))
    pivot = about((2.0, 3.0), rotate(37))
    assert pivot.apply((2.0, 3.0)) == pytest.approx((2.0, 3.0))
    assert (Affine() @ m).apply((3.0, 4.0)) == pytest.approx(m.apply((3.0, 4.0)))


@pytest.mark.parametrize(("role", "facing", "prop", "crest"), ROLE_MATRIX)
def test_rest_pose_close_to_still(
    role: str, facing: int, prop: str, crest: bool, palette: Any
) -> None:
    still = _render(_style(palette, prop, None, role=role, crest=crest), palette, facing)
    rest = _render(_style(palette, prop, REST, role=role, crest=crest), palette, facing)
    diff = np.abs(still - rest)
    assert diff.mean() < 1 / 255
    assert diff.max() < 0.25


@pytest.mark.parametrize("pose", SAMPLE_POSES)
@pytest.mark.parametrize("prop", ["spear", "flag", "oar"])
def test_hand_on_shaft_in_every_pose(pose: Pose, prop: str, palette: Any) -> None:  # AC-33
    style = _style(palette, prop, pose)
    joints = kit_for(style).rig.joints(style, pose)  # type: ignore[union-attr]
    hand = joints["hand"].apply(HAND_CENTER)
    segment = shaft_segment(prop)
    assert segment is not None
    (x0, y0), (x1, y1) = (joints["prop"].apply(p) for p in segment)
    dist = abs((y1 - y0) * hand[0] - (x1 - x0) * hand[1] + x1 * y0 - y1 * x0)
    assert dist / math.hypot(x1 - x0, y1 - y0) <= 0.5
    alpha = _render(style, palette, names=("hand",))[..., 3]
    ys, xs = np.nonzero(alpha > 0.5)
    centre = (
        (xs.min() + xs.max() + 1) / 2 / SCALE - 40,
        (ys.min() + ys.max() + 1) / 2 / SCALE - 150,
    )
    assert math.dist(centre, hand) <= 0.5


@pytest.mark.parametrize("shoulder", [-60.0, 0.0, 45.0, 160.0])
def test_spear_stays_vertical(shoulder: float, palette: Any) -> None:
    style = _style(palette, "spear", Pose(near_shoulder=shoulder, torso_lean=6.0))
    m = kit_for(style).rig.joints(style, style.pose)["prop"]  # type: ignore[union-attr]
    angle = math.degrees(math.atan2(m.yx, m.xx))
    assert abs(angle) <= 10


@pytest.mark.parametrize("pose", SAMPLE_POSES)
def test_no_crack_at_elbow(pose: Pose, palette: Any) -> None:  # AC-34
    style = _style(palette, "none", pose)
    joints = kit_for(style).rig.joints(style, pose)  # type: ignore[union-attr]
    alpha = _render(style, palette, names=("sleeves",))[..., 3]
    from history_shorts.characters.kits.ancient_female_rig import ELBOWS

    for side, elbow in ELBOWS.items():
        cx, cy = joints[f"{side}_arm"].apply(elbow)
        for dx, dy in [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2), (1.4, 1.4), (-1.4, -1.4)]:
            assert alpha[_px((cx + dx, cy + dy))] > 0.95, (side, dx, dy)


def test_shaft_never_sinks_below_feet(palette: Any) -> None:
    style = _style(palette, "spear", Pose(torso_lean=20.0))
    m = kit_for(style).rig.joints(style, style.pose)  # type: ignore[union-attr]
    assert m["hand"].apply(HAND_CENTER)[1] > HAND_CENTER[1]  # the hand went down
    assert m["prop"].y0 == 0.0  # the shaft did not


def test_elbow_folds_toward_head(palette: Any) -> None:
    style = _style(palette, "none", Pose(far_shoulder=120.0, far_elbow=40.0))
    m = kit_for(style).rig.joints(style, style.pose)  # type: ignore[union-attr]
    straight = kit_for(style).rig.joints(style, Pose(far_shoulder=120.0))  # type: ignore[union-attr]
    cuff = (-16.0, -44.0)
    assert abs(m["far_fore"].apply(cuff)[0]) < abs(straight["far_fore"].apply(cuff)[0])


def test_torso_lean_moves_head_not_feet(palette: Any) -> None:
    rest = _render(_style(palette, "none"), palette)[..., 3]
    lean = _render(_style(palette, "none", Pose(torso_lean=10.0)), palette)[..., 3]
    feet = slice(*_px((0, -10))[:1] + _px((0, 0))[:1])
    assert np.abs(rest[feet] - lean[feet]).max() < 0.05
    head = slice(*_px((0, -100))[:1] + _px((0, -85))[:1])
    assert np.abs(rest[head] - lean[head]).max() > 0.5


def test_draw_figure_restores_state_with_pose(palette: Any) -> None:
    cv = Canvas(200, 300)
    draw_figure(cv, _style(palette, "flag", SAMPLE_POSES[2]), Placement(100, 250, 200, 1), palette)
    assert cv._cr.get_matrix() == Canvas(200, 300)._cr.get_matrix()  # noqa: SLF001


@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("prop", ["spear", "none"])
def test_free_arm_raise(facing: int, prop: str, palette: Any) -> None:
    from history_shorts.characters.kits.ancient_female_rig import free_arm

    side = free_arm(_style(palette, prop))
    assert side == ("far" if prop != "none" else "near")
    pose = Pose(**{f"{side}_shoulder": 160.0, f"{side}_elbow": 20.0})
    style = _style(palette, prop, pose)
    alpha = _render(style, palette, facing, names=("sleeves",))[..., 3]
    top_row = int(np.nonzero(alpha.max(axis=1) > 0.5)[0].min())
    assert top_row / SCALE - 150 < -102.3  # above the bun
    if prop != "none":
        joints = kit_for(style).rig.joints(style, pose)  # type: ignore[union-attr]
        assert joints["hand"].apply(HAND_CENTER) == pytest.approx(HAND_CENTER)


def _fist_pixel(style: Any, palette: Any) -> Any:
    from history_shorts.characters.kits.ancient_female_rig import FIST_AT

    side = "far"
    m = kit_for(style).rig.joints(style, style.pose)  # type: ignore[union-attr]
    return _render(style, palette, names=("sleeves",))[_px(m[f"{side}_fore"].apply(FIST_AT[side]))]


def test_raised_arm_shows_fist(palette: Any) -> None:
    egg = np.array(palette["egg"]) / 255
    raised = _fist_pixel(_style(palette, "spear", Pose(far_shoulder=120.0)), palette)
    assert raised[3] > 0.99 and np.abs(raised[:3] - egg).max() < 0.03
    low = _fist_pixel(_style(palette, "spear", Pose(far_shoulder=20.0)), palette)
    assert low[3] < 0.01
