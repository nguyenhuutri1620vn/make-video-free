"""Layout constants: canvas, safe zone, regions and text anchors (spec §8.2, §8.4)."""

from __future__ import annotations

from history_shorts.layout import (
    CANVAS_H,
    CANVAS_W,
    REGIONS,
    SAFE_ZONE,
    SUBTITLE_GAP,
    SUBTITLE_STEP_RATIO,
    TEXT_CENTER_X,
    TEXT_MAX_WIDTH,
    TITLE_STEP_RATIO,
    TITLE_TOP_ONE_LINE,
    TITLE_TOP_TWO_LINES,
)
from history_shorts.primitives import Box


def test_canvas_size() -> None:
    assert CANVAS_W == 1080
    assert CANVAS_H == 1920


def test_safe_zone() -> None:
    assert SAFE_ZONE == Box(80, 160, 930, 1500)


def test_text_geometry() -> None:
    assert TEXT_CENTER_X == 505
    assert TEXT_MAX_WIDTH == 850


def test_regions_exact_boxes() -> None:
    assert set(REGIONS) == {"header", "visual", "title", "subtitle", "chrome"}
    assert REGIONS["header"] == Box(0, 160, 1080, 290)
    assert REGIONS["visual"] == Box(0, 290, 1080, 1150)
    assert REGIONS["title"] == Box(0, 1170, 1080, 1400)
    assert REGIONS["subtitle"] == Box(0, 1400, 1080, 1500)
    assert REGIONS["chrome"] == Box(0, 1540, 1080, 1920)


def test_title_and_subtitle_regions_abut() -> None:
    assert REGIONS["title"].y1 == REGIONS["subtitle"].y0


def test_text_anchors() -> None:
    assert TITLE_TOP_ONE_LINE == 1215
    assert TITLE_TOP_TWO_LINES == 1190
    assert TITLE_STEP_RATIO == 102 / 92
    assert SUBTITLE_GAP == 128
    assert SUBTITLE_STEP_RATIO == 56 / 46
