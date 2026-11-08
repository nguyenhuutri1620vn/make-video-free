"""Title and subtitle: glyph coverage, pixel-width wrapping, auto-shrink, planning, drawing.

Text is drawn last with Pillow so no texture or finish effect touches it (FR-24). Wrapping
and shrinking follow FR-25; placement follows spec §8.2 and typography §8.4.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

from PIL import Image, ImageDraw, ImageFont

from history_shorts.config import Slide, Theme
from history_shorts.layout import (
    REGIONS,
    SUBTITLE_GAP,
    SUBTITLE_STEP_RATIO,
    TEXT_CENTER_X,
    TEXT_MAX_WIDTH,
    TITLE_STEP_RATIO,
    TITLE_TOP_ONE_LINE,
    TITLE_TOP_TWO_LINES,
)
from history_shorts.primitives import Box

FontKey = Literal["title", "subtitle"]

SHRINK_STEP: Final = 4
MAX_LINES: Final = 2
SHADOW_OFFSET: Final = 3
TITLE_COLOR_CYCLE: Final = ("egg", "gold_lt")
SHADOW_COLOR_KEY: Final = "shadow"
_NOTDEF: Final = "\U0010fffd"  # a private-use noncharacter: always renders as .notdef

_VIETNAMESE_BASES: Final = "aăâeêioôơuưy"
# combining marks in order: none, grave, acute, hook above, tilde, dot below
_TONE_MARKS: Final = ("", "̀", "́", "̉", "̃", "̣")


def _build_charset() -> str:
    chars: list[str] = []
    for upper in (False, True):
        for base in _VIETNAMESE_BASES:
            letter = base.upper() if upper else base
            for mark in _TONE_MARKS:
                chars.append(unicodedata.normalize("NFC", letter + mark))
        chars.append("Đ" if upper else "đ")
    return "".join(chars)


VIETNAMESE_CHARSET: Final = _build_charset()


@lru_cache(maxsize=64)
def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.BASIC)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    """The cached TrueType font at ``size`` px (shared with the chrome module)."""
    return _font(path, size)


def _glyph_signature(font: ImageFont.FreeTypeFont, ch: str) -> tuple[tuple[int, int], bytes]:
    mask = font.getmask(ch)
    return (mask.size, bytes(mask))


def missing_glyphs(font_path: Path, chars: str = VIETNAMESE_CHARSET) -> list[str]:
    """Characters whose rendering is identical to the font's ``.notdef`` glyph."""
    font = ImageFont.truetype(str(font_path), 64, layout_engine=ImageFont.Layout.BASIC)
    notdef = _glyph_signature(font, _NOTDEF)
    return [ch for ch in chars if not ch.isspace() and _glyph_signature(font, ch) == notdef]


def wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    """Greedy word wrap by measured pixel width; explicit ``\\n`` always breaks.

    A single word wider than ``max_width`` is kept whole on its own line (the caller decides
    whether that is an error).
    """
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if current and font.getlength(candidate) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


class TextFitError(ValueError):
    """The title or subtitle cannot fit even at the theme's minimum size."""

    def __init__(self, field: Literal["title", "subtitle"], suggestion: str) -> None:
        super().__init__(f"{field} does not fit: {suggestion}")
        self.field: Literal["title", "subtitle"] = field
        self.suggestion = suggestion


@dataclass(frozen=True, slots=True)
class TextLine:
    """One line to draw. ``x`` is the left edge and ``y`` the top as passed to Pillow."""

    text: str
    x: float
    y: int
    size: int
    color_key: str
    font_key: FontKey


@dataclass(frozen=True, slots=True)
class TextPlan:
    lines: tuple[TextLine, ...]
    shrunk: bool
    title_box: Box
    subtitle_box: Box | None


def _sizes(start: int, minimum: int) -> range:
    return range(start, minimum - 1, -SHRINK_STEP)


def _wrapped_ok(lines: list[str], font: ImageFont.FreeTypeFont) -> bool:
    return (
        0 < len(lines) <= MAX_LINES
        and max(font.getlength(line) for line in lines) <= TEXT_MAX_WIDTH
    )


def _suggestion(text: str, path: Path, minimum: int, field: str) -> str:
    """Approximate character budget at the minimum size, for the 'shorten' message."""
    font = _font(path, minimum)
    flat = " ".join(text.split())
    average = font.getlength(flat) / max(len(flat), 1)
    budget = max(int(MAX_LINES * TEXT_MAX_WIDTH / max(average, 1.0)), 1)
    return (
        f"shorten the {field} to about {budget} characters or fewer "
        f"(at most {MAX_LINES} lines of {TEXT_MAX_WIDTH}px, minimum size {minimum}px)"
    )


def _fit_title(text: str, theme: Theme) -> tuple[int, list[str]]:
    path, scale = theme.fonts.title, theme.type_scale
    for size in _sizes(scale.title, scale.title_min):
        lines = wrap(text, _font(path, size), TEXT_MAX_WIDTH)
        if _wrapped_ok(lines, _font(path, size)):
            return size, lines
    raise TextFitError("title", _suggestion(text, path, scale.title_min, "title"))


def _subtitle_bottom(lines: list[str], font: ImageFont.FreeTypeFont, size: int, top: int) -> float:
    step = round(size * SUBTITLE_STEP_RATIO)
    return top + step * (len(lines) - 1) + font.getbbox(lines[-1])[3]


def _fit_subtitle(text: str, theme: Theme, top: int) -> tuple[int, list[str]]:
    path, scale = theme.fonts.subtitle, theme.type_scale
    for size in _sizes(scale.subtitle, scale.subtitle_min):
        font = _font(path, size)
        lines = wrap(text, font, TEXT_MAX_WIDTH)
        if _wrapped_ok(lines, font) and _subtitle_bottom(lines, font, size, top) <= (
            REGIONS["subtitle"].y1
        ):
            return size, lines
    raise TextFitError("subtitle", _suggestion(text, path, scale.subtitle_min, "subtitle"))


def _place(
    lines: list[str],
    path: Path,
    size: int,
    top: int,
    step: int,
    colors: Sequence[str],
    key: FontKey,
) -> list[TextLine]:
    font = _font(path, size)
    return [
        TextLine(
            text=line,
            x=TEXT_CENTER_X - font.getlength(line) / 2,
            y=top + i * step,
            size=size,
            color_key=colors[i % len(colors)],
            font_key=key,
        )
        for i, line in enumerate(lines)
    ]


def _bounds(lines: list[TextLine], path: Path, shadow: int) -> Box:
    boxes: list[Box] = []
    for ln in lines:
        left, top, right, bottom = _font(path, ln.size).getbbox(ln.text)
        boxes.append(Box(ln.x + left, ln.y + top, ln.x + right + shadow, ln.y + bottom + shadow))
    box = boxes[0]
    for other in boxes[1:]:
        box = box.union(other)
    return box


def plan_text(slide: Slide, theme: Theme) -> TextPlan:
    """Fit and place the slide's title and subtitle. Raises ``TextFitError`` if they cannot fit.

    The title is fitted first, then the subtitle independently (FR-25). Title line tops follow
    §8.2; the subtitle starts ``SUBTITLE_GAP`` below the last title line.
    """
    scale = theme.type_scale
    title_size, title_lines = _fit_title(slide.title, theme)
    title_top = TITLE_TOP_ONE_LINE if len(title_lines) == 1 else TITLE_TOP_TWO_LINES
    title = _place(
        title_lines,
        theme.fonts.title,
        title_size,
        title_top,
        round(title_size * TITLE_STEP_RATIO),
        TITLE_COLOR_CYCLE,
        "title",
    )
    title_box = _bounds(title, theme.fonts.title, SHADOW_OFFSET)
    shrunk = title_size < scale.title
    subtitle: list[TextLine] = []
    subtitle_box: Box | None = None
    if slide.subtitle.strip():
        sub_top = title[-1].y + SUBTITLE_GAP
        sub_size, sub_lines = _fit_subtitle(slide.subtitle, theme, sub_top)
        subtitle = _place(
            sub_lines,
            theme.fonts.subtitle,
            sub_size,
            sub_top,
            round(sub_size * SUBTITLE_STEP_RATIO),
            (TITLE_COLOR_CYCLE[len(title_lines) % len(TITLE_COLOR_CYCLE)],),
            "subtitle",
        )
        subtitle_box = _bounds(subtitle, theme.fonts.subtitle, 0)
        shrunk = shrunk or sub_size < scale.subtitle
    return TextPlan(tuple(title + subtitle), shrunk, title_box, subtitle_box)


def draw_text(img: Image.Image, plan: TextPlan, theme: Theme) -> None:
    """Draw the planned lines onto ``img`` in place; the title gets a drop shadow."""
    draw = ImageDraw.Draw(img)
    for ln in plan.lines:
        path = theme.fonts.title if ln.font_key == "title" else theme.fonts.subtitle
        font = _font(path, ln.size)
        if ln.font_key == "title":
            draw.text(
                (ln.x + SHADOW_OFFSET, ln.y + SHADOW_OFFSET),
                ln.text,
                font=font,
                fill=theme.palette[SHADOW_COLOR_KEY],
            )
        draw.text((ln.x, ln.y), ln.text, font=font, fill=theme.palette[ln.color_key])
