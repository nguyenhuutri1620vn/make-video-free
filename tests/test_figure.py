"""Figure parts and drawing order (FR-40 to FR-46, AC-07)."""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pytest

from history_shorts.canvas import Canvas
from history_shorts.characters import figure, parts, resolve_style
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


def _line_distance(point: tuple[float, float], segment: tuple[Any, Any]) -> float:
    (x0, y0), (x1, y1) = segment
    px, py = point
    return abs((y1 - y0) * px - (x1 - x0) * py + x1 * y0 - y1 * x0) / math.hypot(x1 - x0, y1 - y0)


def _render_part(
    part: Any, palette: Any, prop: str, *, scale: int = 10, role: str = "general"
) -> tuple[Any, Any]:
    """Draw one part at ``scale`` px per unit; returns (alpha, scale)."""
    style = resolve_style(CharacterSpec(role=role, prop=prop), palette)  # type: ignore[arg-type]
    cv = Canvas(60 * scale, 160 * scale)
    cv.translate(20 * scale, 150 * scale)
    cv.scale(scale, scale)
    part(cv, style, palette)
    return cv.mask(), scale


def _to_local(px: float, py: float, scale: int) -> tuple[float, float]:
    return px / scale - 20, py / scale - 150


def _covered(alpha: Any, scale: int, x: float, y: float) -> bool:
    return bool(alpha[round((y + 150) * scale), round((x + 20) * scale)] > 0.3)


@pytest.mark.parametrize("prop", ["spear", "flag", "oar"])
def test_hand_centre_on_shaft(prop: str, palette: Any) -> None:  # AC-07
    alpha, scale = _render_part(parts.hand, palette, prop)
    ys, xs = np.nonzero(alpha > 0.5)
    box_centre = _to_local((xs.min() + xs.max() + 1) / 2, (ys.min() + ys.max() + 1) / 2, scale)
    assert math.hypot(box_centre[0] - HAND_CENTER[0], box_centre[1] - HAND_CENTER[1]) <= 0.5
    segment = shaft_segment(prop)
    assert segment is not None
    assert _line_distance(HAND_CENTER, segment) <= 0.5


def test_hand_draws_nothing_without_prop(palette: Any) -> None:
    alpha, _ = _render_part(parts.hand, palette, "none")
    assert alpha.max() == 0


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


def test_mirroring_matches_within_antialiasing(palette: Any) -> None:
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


def test_oar_grip_segment_drawn_in_front(palette: Any) -> None:
    """prop_front alone covers the oar line across the hand (y -66..-55), nothing off it."""
    alpha, scale = _render_part(parts.prop_front, palette, "oar", scale=20)
    (x0, y0), (x1, y1) = OAR_SHAFT
    for y in (-65.5, -63.0, -60.5, -58.0, -55.5):
        x = x0 + (y - y0) / (y1 - y0) * (x1 - x0)
        assert _covered(alpha, scale, x, y), y
        assert not _covered(alpha, scale, x + 3, y)
        assert not _covered(alpha, scale, x - 3, y)
    assert not _covered(alpha, scale, x0 + (-70 - y0) / (y1 - y0) * (x1 - x0), -70)  # above grip
    assert not _covered(alpha, scale, x0 + (-50 - y0) / (y1 - y0) * (x1 - x0), -50)  # below grip


def test_oar_adds_shaft_below_hem(palette: Any) -> None:
    def render(prop: str) -> Any:
        style = resolve_style(CharacterSpec(role="boat_crew", prop=prop), palette)  # type: ignore[arg-type]
        cv = Canvas(60 * 10, 170 * 10)
        draw_figure(cv, style, Placement(20 * 10, 150 * 10, 1000, 1), palette)
        return cv.mask()

    with_oar, without = render("oar"), render("none")
    (x0, y0), (x1, y1) = OAR_SHAFT
    for y in (1.0, 3.0, 5.0):  # below the hem line (y > 0)
        x = x0 + (y - y0) / (y1 - y0) * (x1 - x0)
        py, px = round((150 + y) * 10), round((20 + x) * 10)
        assert with_oar[py, px] > 0.3
        assert without[py, px] == 0


def test_parts_called_in_draw_order(palette: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def recorder(name: str) -> Any:
        return lambda cv, style, pal: calls.append(name)

    monkeypatch.setattr(figure, "_PARTS", {name: recorder(name) for name in DRAW_ORDER})
    style = resolve_style(CharacterSpec(role="leader"), palette)
    draw_figure(Canvas(50, 50), style, Placement(25, 40, 30, 1), palette)
    assert calls == list(DRAW_ORDER)


@pytest.mark.parametrize("role", ["leader", "general", "general_alt", "boat_crew"])
def test_no_pure_black_in_figure(role: str, palette: Any) -> None:
    style = resolve_style(CharacterSpec(role=role), palette)
    cv = Canvas(500, 760)
    draw_figure(cv, style, Placement(250, 650, 400, 1), palette)
    rgb, a = cv.to_premul()
    solid = a > 0.99
    assert not np.any(solid & (rgb.sum(axis=-1) == 0))
