"""M10: FR-48 boxes of a posed figure and over a figure's motion."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from history_shorts.characters import resolve_style
from history_shorts.characters.figure import Placement, figure_boxes, pose_union_boxes
from history_shorts.characters.pose import REST, Pose
from history_shorts.config import CharacterSpec

PLACE = Placement(540, 1100, 400, 1)


def _style(palette: Any, prop: str, pose: Pose | None) -> Any:
    spec = CharacterSpec(role="leader", prop=prop)  # type: ignore[arg-type]
    return dataclasses.replace(resolve_style(spec, palette), pose=pose)


@pytest.mark.parametrize("prop", ["flag", "spear", "none"])
def test_rest_boxes_equal_still_boxes(prop: str, palette: Any) -> None:
    still = figure_boxes(_style(palette, prop, None), PLACE)
    rest = figure_boxes(_style(palette, prop, REST), PLACE)
    for a, b in ((still.head, rest.head), (still.body, rest.body)):
        assert (a.x0, a.y0, a.x1, a.y1) == pytest.approx((b.x0, b.y0, b.x1, b.y1), abs=0.5)
    if still.prop is not None:
        assert rest.prop is not None
        assert rest.prop.y0 == pytest.approx(still.prop.y0, abs=0.5)


def test_raised_arm_grows_body_box(palette: Any) -> None:
    still = figure_boxes(_style(palette, "flag", None), PLACE)
    raised = figure_boxes(_style(palette, "flag", Pose(far_shoulder=160, far_elbow=20)), PLACE)
    assert raised.body.y0 < still.head.y0  # the fist is above the head


def test_raised_flag_moves_prop_box(palette: Any) -> None:
    still = figure_boxes(_style(palette, "flag", None), PLACE)
    raised = figure_boxes(_style(palette, "flag", Pose(near_shoulder=35)), PLACE)
    assert raised.prop is not None and still.prop is not None
    assert raised.prop.y0 < still.prop.y0


def test_kneel_lowers_head_box(palette: Any) -> None:
    still = figure_boxes(_style(palette, "none", None), PLACE)
    kneel = figure_boxes(_style(palette, "none", Pose(crouch=1.0)), PLACE)
    assert kneel.head.y0 > still.head.y0 + 0.2 * PLACE.height * 0.9


def test_union_contains_every_sample(palette: Any) -> None:
    poses = [REST, Pose(far_shoulder=160), Pose(crouch=1.0), Pose(near_shoulder=35)]
    union = pose_union_boxes(_style(palette, "flag", REST), PLACE, poses)
    for pose in poses:
        one = figure_boxes(_style(palette, "flag", pose), PLACE)
        for big, small in ((union.head, one.head), (union.body, one.body)):
            assert big.x0 <= small.x0 and big.y0 <= small.y0
            assert big.x1 >= small.x1 and big.y1 >= small.y1
