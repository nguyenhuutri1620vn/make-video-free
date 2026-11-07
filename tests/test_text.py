"""Tests for history_shorts.text: charset, glyph check, wrap, fit, plan, draw (FR-24, FR-25)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageFont

from history_shorts.config import Theme
from history_shorts.layout import REGIONS, TEXT_CENTER_X
from history_shorts.text import (
    VIETNAMESE_CHARSET,
    TextFitError,
    draw_text,
    missing_glyphs,
    plan_text,
    wrap,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BOLD = REPO_ROOT / "themes" / "son_mai" / "fonts" / "LiberationSerif-Bold.ttf"
ITALIC = BOLD.with_name("LiberationSerif-Italic.ttf")

MakeSlide = Callable[..., Any]


def test_charset_contents() -> None:
    assert len(VIETNAMESE_CHARSET) == 146
    assert len(set(VIETNAMESE_CHARSET)) == 146
    for ch in "ĂÂĐÊÔƠƯăâđêôơưộẶỹỴ":
        assert ch in VIETNAMESE_CHARSET


def test_charset_is_nfc_single_codepoints() -> None:
    import unicodedata

    assert unicodedata.normalize("NFC", VIETNAMESE_CHARSET) == VIETNAMESE_CHARSET
    assert all(len(ch) == 1 for ch in VIETNAMESE_CHARSET)


def test_liberation_has_every_vietnamese_glyph() -> None:  # AC-08
    assert missing_glyphs(BOLD) == []
    assert missing_glyphs(ITALIC) == []


def test_missing_glyph_detected_against_notdef() -> None:
    assert missing_glyphs(BOLD, chars="a\U0010fffd") == ["\U0010fffd"]


def test_missing_glyphs_skips_whitespace() -> None:
    assert missing_glyphs(BOLD, chars="a b\n") == []


def test_explicit_newline_respected_and_width_wrap() -> None:
    font = ImageFont.truetype(str(BOLD), 92)
    assert wrap("Những nữ tướng\nbên Hai Bà Trưng", font, 850) == [
        "Những nữ tướng",
        "bên Hai Bà Trưng",
    ]
    assert all(font.getlength(line) <= 850 for line in wrap("Hai Bà Trưng " * 4, font, 850))


def test_wrap_keeps_unbreakable_word_whole() -> None:
    font = ImageFont.truetype(str(BOLD), 92)
    assert wrap("g" * 40, font, 850) == ["g" * 40]


def test_reference_layout_two_line_title(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(
        make_slide("Những nữ tướng\nbên Hai Bà Trưng", "Khi phụ nữ cầm quân giữ nước"), theme
    )
    t = [ln for ln in plan.lines if ln.font_key == "title"]
    s = [ln for ln in plan.lines if ln.font_key == "subtitle"]
    assert [ln.y for ln in t] == [1190, 1292] and [ln.color_key for ln in t] == ["egg", "gold_lt"]
    assert s[0].y == 1420 and s[0].color_key == "egg" and not plan.shrunk
    assert [ln.size for ln in t] == [92, 92] and s[0].size == 46


def test_reference_layout_one_line_title(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(make_slide("Mê Linh, năm 40", "Nơi cuộc khởi nghĩa bắt đầu"), theme)
    assert [ln.y for ln in plan.lines] == [1215, 1343]
    assert plan.lines[1].color_key == "gold_lt"


def test_lines_are_centred_on_text_center(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(make_slide("Mê Linh, năm 40", "Nơi cuộc khởi nghĩa bắt đầu"), theme)
    for ln in plan.lines:
        font = ImageFont.truetype(
            str(theme.fonts.title if ln.font_key == "title" else theme.fonts.subtitle), ln.size
        )
        assert ln.x + font.getlength(ln.text) / 2 == pytest.approx(TEXT_CENTER_X)


def test_empty_subtitle_has_no_subtitle_lines(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(make_slide("Mê Linh", ""), theme)
    assert all(ln.font_key == "title" for ln in plan.lines)
    assert plan.subtitle_box is None


def test_boxes_lie_inside_regions(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(
        make_slide("Những nữ tướng\nbên Hai Bà Trưng", "Khi phụ nữ cầm quân giữ nước"), theme
    )
    assert plan.subtitle_box is not None
    assert plan.title_box.inside(REGIONS["title"])
    assert plan.subtitle_box.inside(REGIONS["subtitle"])
    assert plan.title_box.x0 >= 80 and plan.title_box.x1 <= 1080 - 150


def test_long_title_shrinks_in_4px_steps(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(make_slide("Khởi nghĩa Hai Bà Trưng\nđánh đuổi quân Đông Hán", ""), theme)
    sizes = {ln.size for ln in plan.lines}
    assert plan.shrunk and len(sizes) == 1
    size = sizes.pop()
    assert (92 - size) % 4 == 0 and size < 92
    assert len(plan.lines) == 2
    assert plan.lines[1].y - plan.lines[0].y == round(size * 102 / 92)


def test_two_line_subtitle_shrinks_to_fit_region(theme: Theme, make_slide: MakeSlide) -> None:
    sub = "Cuộc khởi nghĩa của hai chị em đã làm rung chuyển cả vùng đất Giao Chỉ"
    plan = plan_text(make_slide("Mê Linh\nnăm 40", sub), theme)
    s = [ln for ln in plan.lines if ln.font_key == "subtitle"]
    assert plan.shrunk and len(s) <= 2
    assert plan.subtitle_box is not None and plan.subtitle_box.y1 <= REGIONS["subtitle"].y1
    assert all(ln.size < 46 and (46 - ln.size) % 4 == 0 for ln in s)
    if len(s) == 2:
        assert s[1].y - s[0].y == round(s[0].size * 56 / 46)


def test_title_shrink_does_not_shrink_subtitle(theme: Theme, make_slide: MakeSlide) -> None:
    plan = plan_text(make_slide("Khởi nghĩa Hai Bà Trưng\nđánh đuổi quân Đông Hán", "Ngắn"), theme)
    assert plan.shrunk
    assert [ln.size for ln in plan.lines if ln.font_key == "subtitle"] == [46]


def test_unbreakable_word_is_fit_error(theme: Theme, make_slide: MakeSlide) -> None:
    with pytest.raises(TextFitError) as exc:
        plan_text(make_slide("Trưnggggggggggggggggggggggggggg", ""), theme)
    assert exc.value.field == "title" and "shorten" in exc.value.suggestion
    assert isinstance(exc.value, ValueError)


def test_too_many_lines_is_fit_error(theme: Theme, make_slide: MakeSlide) -> None:
    with pytest.raises(TextFitError) as exc:
        plan_text(make_slide("a\nb\nc", ""), theme)
    assert exc.value.field == "title"


def test_subtitle_overflow_is_fit_error(theme: Theme, make_slide: MakeSlide) -> None:
    with pytest.raises(TextFitError) as exc:
        plan_text(make_slide("Mê Linh", "từ " * 80), theme)
    assert exc.value.field == "subtitle" and "shorten" in exc.value.suggestion
    assert any(ch.isdigit() for ch in exc.value.suggestion)


def test_draw_text_only_touches_text_regions(theme: Theme, make_slide: MakeSlide) -> None:
    img = Image.new("RGB", (1080, 1920))
    draw_text(img, plan_text(make_slide("Mê Linh", "x"), theme), theme)
    a = np.asarray(img)
    assert a[:1150].max() == 0 and a[1600:].max() == 0
    assert a[1170:1500].max() > 0


def test_draw_text_title_has_shadow_subtitle_does_not(theme: Theme, make_slide: MakeSlide) -> None:
    img = Image.new("RGB", (1080, 1920))
    draw_text(img, plan_text(make_slide("Mê Linh", "Khi phụ nữ cầm quân"), theme), theme)
    is_shadow = (np.asarray(img) == np.array(theme.palette["shadow"], dtype=np.uint8)).all(axis=2)
    assert is_shadow[1170:1330].any()  # title rows
    assert not is_shadow[1330:].any()  # subtitle rows: no shadow
