"""Tests for history_shorts.chrome: frame, waves, seal, tag pill, progress bar, footer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from history_shorts.canvas import Canvas
from history_shorts.chrome import (
    draw_footer,
    draw_frame,
    draw_progress_bar,
    draw_seal,
    draw_tag,
    draw_waves,
    seal_box,
    tag_box,
)
from history_shorts.compose import SlideContext, default_style, over, render_slide
from history_shorts.config import FooterSpec, Script, Theme, WavesSpec, load_theme
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import Box

TAG = "NĂM 40 SAU CÔNG NGUYÊN"
FRAME_X = 40  # the outer gold line is centred on x = 40 (5 px wide, so x 38..41 are solid)


def render_array(theme: Theme, script: Script, *, seed_shift: int = 0, index: int = 0) -> Any:
    style = default_style(theme)
    style = replace(style, seed=style.seed + seed_shift)
    ctx = SlideContext(script, theme, index, style, None, False)
    return np.asarray(render_slide(ctx)).astype(int)


def gold_like(arr: Any) -> Any:
    """Pixels that are clearly gold: bright red and green channels, red well above blue."""
    return (arr[..., 0] > 110) & (arr[..., 1] > 70) & (arr[..., 0] > arr[..., 2] + 40)


def with_chrome(theme: Theme, **changes: Any) -> Theme:
    return replace(theme, chrome=replace(theme.chrome, **changes))


def blank(color: tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    return Image.new("RGB", (CANVAS_W, CANVAS_H), color)


def tagged(make_slide: Callable[..., Any], script: Script, tag: str) -> Script:
    return replace(script, slides=(make_slide("Hai Bà Trưng", tag=tag),))


# --------------------------------------------------------------------------------------
# Frame
# --------------------------------------------------------------------------------------


def test_frame_lines(theme: Theme, script_one_slide: Script) -> None:
    arr = render_array(theme, script_one_slide)
    gold = np.array(theme.palette["gold"])
    assert np.abs(arr[960, FRAME_X] - gold).max() < 30
    gold_dk = np.array(theme.palette["gold_dk"])
    assert np.abs(arr[960, 58] - gold_dk).max() < 60  # 1.5 px line, antialiased


def test_frame_can_be_disabled(theme: Theme, script_one_slide: Script) -> None:
    arr = render_array(with_chrome(theme, frame=False), script_one_slide)
    gold = np.array(theme.palette["gold"])
    assert np.abs(arr[960, FRAME_X] - gold).max() > 100


def test_frame_corner_scrolls_are_mirrored(palette: Any) -> None:
    cv = Canvas()
    draw_frame(cv, palette)
    alpha = cv.mask()
    # the corner dot (r 6 at (30, 30) in each local frame) lands at all four corners
    for x, y in [(58 + 30, 58 + 30), (1080 - 88, 58 + 30), (58 + 30, 1920 - 88), (992, 1832)]:
        assert alpha[y, x] > 0.99
    # symmetric up to Cairo's antialiasing rounding
    assert np.abs(alpha - alpha[:, ::-1]).max() < 0.1
    assert np.abs(alpha - alpha[::-1, :]).max() < 0.1


def test_frame_drawn_after_finish(theme: Theme, script_one_slide: Script) -> None:
    a = render_array(theme, script_one_slide, seed_shift=0)
    b = render_array(theme, script_one_slide, seed_shift=1)  # different ground and grain
    assert (a[300:900, 200:800] != b[300:900, 200:800]).any()  # the seeds do matter
    for x in range(38, 42):  # the solid core of the outer gold line
        assert np.array_equal(a[300:1500, x], b[300:1500, x])


def test_palette_gold_drives_all_gold(
    theme: Theme, script_one_slide: Script, tmp_theme: Callable[..., Path]
) -> None:  # AC-09
    green, _ = load_theme(tmp_theme(palette={"gold": [20, 200, 40]}))
    a = render_array(theme, script_one_slide)[960, FRAME_X]
    b = render_array(green, script_one_slide)[960, FRAME_X]
    assert not np.array_equal(a, b)
    assert b[1] > b[0]


# --------------------------------------------------------------------------------------
# Waves
# --------------------------------------------------------------------------------------


def test_waves_only_in_chrome_band(theme: Theme, script_one_slide: Script) -> None:
    arr = render_array(theme, script_one_slide)
    band = slice(70, 1010)  # inside the frame, away from corner scrolls
    assert gold_like(arr[1550:1741, band]).any()
    assert not gold_like(arr[1450:1550, band]).any()


def test_waves_use_alternating_palette_rows(palette: Any) -> None:
    cv = Canvas()
    draw_waves(cv, palette, WavesSpec(1600, 4))
    rgb, alpha = cv.to_premul()
    assert alpha[1450:1550].max() == 0  # nothing above the first row's crest
    # row 0 crest region is gold, row 1 gold_dk (un-premultiplied colour at strongest alpha)
    for y_row, key in ((1600, "gold"), (1646, "gold_dk")):
        rows = slice(y_row - 40, y_row + 3)
        weights = alpha[rows]
        colour = rgb[rows][weights > 0.5].mean(axis=0) / weights[weights > 0.5].mean()
        assert np.abs(colour * 255 - np.array(palette[key])).max() < 25


def test_waves_row_count_follows_spec(palette: Any) -> None:
    low = Canvas()
    draw_waves(low, palette, WavesSpec(1600, 1))
    high = Canvas()
    draw_waves(high, palette, WavesSpec(1600, 4))
    assert low.mask()[1640:].max() == 0
    assert high.mask()[1640:].max() > 0.5


# --------------------------------------------------------------------------------------
# Seal
# --------------------------------------------------------------------------------------


def test_seal_box(theme: Theme) -> None:
    assert seal_box(theme) == Box(92, 160, 210, 278)


def test_seal_box_follows_spec(theme: Theme) -> None:
    seal = replace(theme.chrome.seal, x=50.0, y=100.0, size=60.0)
    assert seal_box(with_chrome(theme, seal=seal)) == Box(50, 100, 110, 160)


def test_seal_colours(theme: Theme) -> None:
    img = blank()
    draw_seal(img, theme)
    px = np.asarray(img)
    p = theme.palette
    assert tuple(px[200, 93]) == p["gold"]  # 3 px border at x 92..94
    assert tuple(px[200, 97]) == p["vermilion"]  # fill between border and inner line
    assert tuple(px[200, 100]) == p["egg"]  # inner 1 px line at inset 8
    assert tuple(px[150, 150]) == (0, 0, 0)  # nothing drawn outside the seal
    inside = px[170:270, 100:200].reshape(-1, 3)
    assert (inside == np.array(p["egg"])).all(axis=1).sum() > 200  # SỬ / VIỆT glyphs in egg


def test_seal_scales_with_size(theme: Theme) -> None:
    small = replace(theme.chrome.seal, size=59.0)
    img = blank()
    draw_seal(img, with_chrome(theme, seal=small))
    px = np.asarray(img)
    assert tuple(px[160 + 30, 92 + 1]) == theme.palette["gold"]
    assert (px[160 + 59 + 4 :, 92 : 92 + 70] == 0).all()  # nothing below the smaller seal
    assert (px[:, 92 + 59 + 4 : 300] == 0).all()


# --------------------------------------------------------------------------------------
# Tag pill
# --------------------------------------------------------------------------------------


def test_tag_box_reference_geometry(theme: Theme) -> None:
    box = tag_box(TAG, theme)
    assert box is not None
    assert box.y0 == 180 and box.height == 60
    assert (box.x0 + box.x1) / 2 == pytest.approx(590)


def test_tag_box_width_is_text_plus_52(theme: Theme) -> None:
    from history_shorts.text import font

    text_w = font(theme.fonts.tag, theme.type_scale.tag).getlength(TAG)
    box = tag_box(TAG, theme)
    assert box is not None and box.width == pytest.approx(text_w + 52)


def test_empty_tag_has_no_box_and_draws_nothing(theme: Theme) -> None:
    assert tag_box("", theme) is None
    img = blank()
    draw_tag(img, "", theme)
    assert not np.asarray(img).any()


def test_tag_pill_colours(theme: Theme) -> None:
    img = blank()
    draw_tag(img, TAG, theme)
    px = np.asarray(img)
    box = tag_box(TAG, theme)
    assert box is not None
    mid = int((box.y0 + box.y1) / 2)
    assert tuple(px[mid, int(box.x0) + 10]) == theme.palette["vermilion"]
    edge = {tuple(px[mid, x]) for x in range(int(box.x0) - 1, int(box.x0) + 3)}
    assert theme.palette["gold"] in edge
    text = px[int(box.y0) : int(box.y1), int(box.x0) : int(box.x1)].reshape(-1, 3)
    assert (text == np.array(theme.palette["gold_lt"])).all(axis=1).sum() > 100


def test_tag_in_rendered_slide(
    theme: Theme, script_one_slide: Script, make_slide: Callable[..., Any]
) -> None:
    script = tagged(make_slide, script_one_slide, TAG)
    arr = render_array(theme, script)
    box = tag_box(TAG, theme)
    assert box is not None
    assert (
        arr[200, int(box.x0) + 10] == np.array(theme.palette["vermilion"])
    ).all()  # drawn after finish
    plain = render_array(theme, script_one_slide)
    assert not (plain[200, int(box.x0) + 10] == np.array(theme.palette["vermilion"])).all()


# --------------------------------------------------------------------------------------
# Progress bar and footer
# --------------------------------------------------------------------------------------


def test_progress_bar_geometry_and_colours(theme: Theme) -> None:
    img = blank()
    draw_progress_bar(img, theme, 0, 2)
    px = np.asarray(img)
    gold = theme.palette["gold"]
    assert tuple(px[1541, 100]) == gold  # filled part
    assert tuple(px[1541, 504]) == gold  # fill reaches 80 + 850 / 2 = 505
    track = px[1541, 800]
    expected = np.array(theme.palette["gold_dk"]) * 0.4
    assert np.abs(track - expected).max() <= 1  # track: gold_dk at alpha 0.4
    assert not px[1539].any() and not px[1544].any()  # 4 px tall: rows 1540..1543
    assert not px[1541, :79].any() and not px[1541, 931:].any()


def test_progress_bar_last_slide_is_full(theme: Theme) -> None:
    img = blank()
    draw_progress_bar(img, theme, 2, 3)
    px = np.asarray(img)
    assert tuple(px[1541, 929]) == theme.palette["gold"]
    assert tuple(px[1541, 80]) == theme.palette["gold"]


def test_progress_bar_off_by_default_on_when_enabled(
    theme: Theme, script_one_slide: Script
) -> None:
    off = render_array(theme, script_one_slide)
    on = render_array(with_chrome(theme, progress_bar=True), script_one_slide)
    assert not np.array_equal(off[1540:1544], on[1540:1544])
    assert tuple(on[1541, 100]) == theme.palette["gold"]  # one slide: bar is full
    assert np.array_equal(off[:1540], on[:1540]) and np.array_equal(off[1544:], on[1544:])


def test_footer_off_by_default_and_on_when_enabled(theme: Theme, script_one_slide: Script) -> None:
    off = render_array(theme, script_one_slide)
    enabled = FooterSpec(enabled=True, text="Sử Việt")
    on = render_array(with_chrome(theme, footer=enabled), script_one_slide)
    assert np.array_equal(off[:1830], on[:1830])
    assert not np.array_equal(off[1830:1890], on[1830:1890])
    dk = np.array(theme.palette["gold_dk"])
    assert (on[1830:1890] == dk).all(axis=-1).sum() > 100


def test_footer_is_centred(theme: Theme) -> None:
    img = blank()
    draw_footer(img, with_chrome(theme, footer=FooterSpec(True, "Sử Việt")))
    cols = np.nonzero(np.asarray(img).any(axis=(0, 2)))[0]
    assert abs((cols.min() + cols.max()) / 2 - 540) < 4


def test_footer_empty_text_draws_nothing(theme: Theme) -> None:
    img = blank()
    draw_footer(img, with_chrome(theme, footer=FooterSpec(True, "")))
    assert not np.asarray(img).any()


# --------------------------------------------------------------------------------------
# Wiring
# --------------------------------------------------------------------------------------


def test_over_of_frame_canvas_leaves_interior_untouched(palette: Any) -> None:
    base = np.full((CANVAS_H, CANVAS_W, 3), 0.25, np.float32)
    cv = Canvas()
    draw_frame(cv, palette)
    out = over(base, cv)
    assert np.array_equal(out[900:1000, 300:700], base[900:1000, 300:700])
