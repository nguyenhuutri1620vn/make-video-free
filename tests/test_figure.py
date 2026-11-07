"""Figure parts and drawing order (FR-40 to FR-46, AC-07)."""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.characters import resolve_style
from history_shorts.characters.figure import DRAW_ORDER, Placement, draw_figure
from history_shorts.characters.parts import (
    HAND_CENTER,
    HEAD_CENTER_Y,
    HEM_HALF_WIDTH,
    OAR_SHAFT,
    PROP_X,
    SHOULDER_Y,
    WAIST_Y,
    shaft_segment,
)
from history_shorts.config import CharacterSpec


def test_draw_order_is_fr41() -> None:
    assert DRAW_ORDER == (
        "hair_back",
        "prop_back",
        "robe",
        "belt",
        "sleeves",
        "prop_front",
        "hand",
        "neck",
        "face",
        "features",
        "hair_front",
        "bun",
        "headwrap",
        "crest",
    )


def test_proportion_constants_match_prototype() -> None:
    assert (HEAD_CENTER_Y, SHOULDER_Y, WAIST_Y, HEM_HALF_WIDTH, PROP_X) == (-88.5, -79, -55, 25, 17)
    assert HAND_CENTER == (17.3, -60.5)


def test_shaft_segments() -> None:
    assert shaft_segment("flag") == ((17, -136), (17, 1))
    assert shaft_segment("spear") == ((17, -134), (17, 1))
    assert shaft_segment("oar") == OAR_SHAFT
    assert shaft_segment("none") is None


@pytest.mark.parametrize("prop", ["spear", "flag", "oar"])
def test_hand_centre_on_shaft(prop: str) -> None:  # AC-07
    segment = shaft_segment(prop)
    assert segment is not None
    (x0, y0), (x1, y1) = segment
    hx, hy = HAND_CENTER
    dist = abs((y1 - y0) * hx - (x1 - x0) * hy + x1 * y0 - y1 * x0) / math.hypot(x1 - x0, y1 - y0)
    assert dist <= 0.5


@pytest.mark.parametrize("role", ["leader", "general", "general_alt", "boat_crew"])
@pytest.mark.parametrize("facing", [-1, 1])
@pytest.mark.parametrize("prop", ["flag", "spear", "oar", "none"])
@pytest.mark.parametrize("crest", [True, False])
def test_every_combination_renders(
    role: str, facing: int, prop: str, crest: bool, palette: Any
) -> None:  # AC-07
    cv = Canvas(500, 760)
    style = resolve_style(CharacterSpec(role=role, prop=prop, crest=crest), palette)  # type: ignore[arg-type]
    draw_figure(cv, style, Placement(250, 650, 400, facing), palette)
    a = cv.mask()
    assert a.sum() > 1000
    assert a[:, :5].max() == 0 and a[:, -5:].max() == 0


def test_mirroring_is_exact(palette: Any) -> None:
    style = resolve_style(CharacterSpec(role="leader"), palette)
    left, right = Canvas(1080, 1200), Canvas(1080, 1200)
    draw_figure(left, style, Placement(540, 1150, 565, -1), palette)
    draw_figure(right, style, Placement(540, 1150, 565, 1), palette)
    # Cairo's anti-aliasing is not bit-symmetric under a mirror: allow edge-coverage noise
    # (at most 10 % on a handful of edge pixels) but require identical geometry.
    diff = np.abs(left.mask() - right.mask()[:, ::-1])
    assert diff.max() <= 0.1
    assert (diff > 1 / 255).sum() < 0.02 * (left.mask() > 0).sum()


def test_draw_figure_restores_canvas_state(palette: Any) -> None:
    style = resolve_style(CharacterSpec(role="general"), palette)
    cv = Canvas(300, 300)
    draw_figure(cv, style, Placement(150, 250, 200, 1), palette)
    cv.color((255, 255, 255)).rect(0, 0, 10, 10).fill()
    assert cv.mask()[5, 5] == 1.0  # identity transform again


@pytest.mark.parametrize(("facing", "height"), [(0, 100.0), (2, 100.0), (1, 0.0), (1, -5.0)])
def test_placement_validates(facing: int, height: float) -> None:
    with pytest.raises(ValueError):
        Placement(0, 0, height, facing)


def test_placement_is_frozen() -> None:
    placement = Placement(1, 2, 3, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        placement.x = 5  # type: ignore[misc]


def test_oar_passes_through_hand(palette: Any) -> None:
    """The oar shaft is drawn both behind and in front of the arm (FR-44)."""
    style = resolve_style(CharacterSpec(role="boat_crew"), palette)
    cv = Canvas(500, 760)
    draw_figure(cv, style, Placement(250, 650, 400, 1), palette)
    rgb, a = cv.to_premul()
    # hand centre in pixels: x = 250 + 17.3*4, y = 650 - 60.5*4
    px, py = int(250 + HAND_CENTER[0] * 4), int(650 + HAND_CENTER[1] * 4)
    assert a[py, px] == 1.0


def test_no_pure_black_in_figure(palette: Any) -> None:
    style = resolve_style(CharacterSpec(role="leader"), palette)
    cv = Canvas(500, 760)
    draw_figure(cv, style, Placement(250, 650, 400, 1), palette)
    rgb, a = cv.to_premul()
    solid = a > 0.99
    assert not np.any(solid & (rgb.sum(axis=-1) == 0))
