"""M12: the warrior_male kit (still drawing) and its four roles."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.characters import ROLES, resolve_style
from history_shorts.characters.figure import Placement, draw_figure
from history_shorts.characters.kits import kit_named
from history_shorts.checks import kit_problem
from history_shorts.config import CharacterSpec, load_script
from history_shorts.errors import ValidationFailed

WARRIORS = ("viet_general", "viet_soldier", "northern_general", "northern_soldier")
SCALE = 8


def _style(palette: Any, role: str, **kw: Any) -> Any:
    return resolve_style(CharacterSpec(role=role, **kw), palette)  # type: ignore[arg-type]


def _render(style: Any, palette: Any, facing: int = 1, names: Any = None) -> Any:
    cv = Canvas(80 * SCALE, 170 * SCALE)
    draw_figure(cv, style, Placement(40 * SCALE, 160 * SCALE, 100 * SCALE, facing), palette, names)
    return cv.mask()


def test_roles_use_the_kit() -> None:
    kit = kit_named("warrior_male")
    for role in WARRIORS:
        assert ROLES[role].kit == "warrior_male"
        assert ROLES[role].prop in kit.props


@pytest.mark.parametrize("role", WARRIORS)
@pytest.mark.parametrize("facing", [1, -1])
@pytest.mark.parametrize("prop", ["flag", "spear", "sword_sheathed", "shield", "none"])
def test_every_role_facing_prop_draws(role: str, facing: int, prop: str, palette: Any) -> None:
    alpha = _render(_style(palette, role, prop=prop), palette, facing)
    assert alpha.sum() > 1000


def test_kit_props_are_checked() -> None:  # Review Focus 2
    assert kit_problem(CharacterSpec(role="leader", prop="shield")) is not None
    assert kit_problem(CharacterSpec(role="general", prop="sword_sheathed")) is not None
    assert kit_problem(CharacterSpec(role="viet_soldier", prop="oar")) is not None
    assert kit_problem(CharacterSpec(role="viet_soldier", prop="shield")) is None


@pytest.mark.parametrize("prop", ["flag", "spear"])
def test_hand_on_shaft(prop: str, palette: Any) -> None:  # AC-07
    kit = kit_named("warrior_male")
    segment = kit.shaft_segment(prop)
    assert segment is not None
    (x0, _), (x1, _) = segment
    assert abs(x0 - kit.hand_center[0]) <= 0.5 and abs(x1 - kit.hand_center[0]) <= 0.5
    alpha = _render(_style(palette, "viet_soldier", prop=prop), palette, names=("hand",))
    ys, xs = np.nonzero(alpha > 0.5)
    centre = (
        (xs.min() + xs.max() + 1) / 2 / SCALE - 40,
        (ys.min() + ys.max() + 1) / 2 / SCALE - 160,
    )
    assert math.dist(centre, kit.hand_center) <= 0.5


def test_sword_hangs_at_the_near_hip(palette: Any) -> None:
    alpha = _render(_style(palette, "northern_general"), palette, names=("sword",))
    ys, xs = np.nonzero(alpha > 0.5)
    assert xs.min() / SCALE - 40 > 0  # on the near (prop) side
    assert ys.min() / SCALE - 160 > -60  # from the belt down


def test_shield_on_the_far_forearm(palette: Any) -> None:
    alpha = _render(_style(palette, "northern_soldier", prop="shield"), palette, names=("shield",))
    ys, xs = np.nonzero(alpha > 0.5)
    centre = (
        (xs.min() + xs.max() + 1) / 2 / SCALE - 40,
        (ys.min() + ys.max() + 1) / 2 / SCALE - 160,
    )
    assert math.dist(centre, (-20.0, -50.0)) <= 0.5


def test_faces_identical_across_roles(palette: Any) -> None:  # AC-49
    masks = [_render(_style(palette, r), palette, names=("face", "features")) for r in WARRIORS]
    for mask in masks[1:]:
        assert np.array_equal(mask, masks[0])


def test_male_face_differs_from_female(palette: Any) -> None:
    male = _render(_style(palette, "viet_soldier"), palette, names=("face", "features"))
    female = _render(_style(palette, "general"), palette, names=("face", "features"))
    assert not np.array_equal(male, female)


def test_helmet_override(palette: Any) -> None:
    default = _render(_style(palette, "northern_soldier"), palette, names=("headwear",))
    cap = _render(_style(palette, "northern_soldier", helmet="cap"), palette, names=("headwear",))
    assert cap.sum() < default.sum() * 0.6


def test_warrior_roles_need_24(tmp_script: Callable[..., Path]) -> None:  # Review Focus 1
    item = {"role": "viet_general", "x": 540}
    slide = {"title": "A", "scene": {"layers": [{"type": "characters", "items": [item]}]}}
    with pytest.raises(ValidationFailed) as exc:
        load_script(tmp_script(slides=[slide], extra={"schema_version": "2.3"}))
    assert any(
        i.path.endswith("items[0].role") and 'requires schema_version "2.4"' in i.message
        for i in exc.value.issues.items
    )
