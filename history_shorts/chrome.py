"""Series chrome shared by every slide: frame, waves, seal, tag pill, progress bar, footer.

Frame and waves are Cairo shapes drawn on a ``Canvas`` (composited onto the float buffer by
``compose``); seal, tag, progress bar and footer are Pillow drawings on the final image.
Geometry is copied from the approved prototype (``lac.frame``, ``lac.tag_pill``,
``lac.seal``, ``elements.waves``); every colour comes from the theme palette.
"""

from __future__ import annotations

from typing import Final

from PIL import Image, ImageDraw

from history_shorts.canvas import Canvas
from history_shorts.config import Palette, Theme, WavesSpec
from history_shorts.layout import CANVAS_W
from history_shorts.primitives import Box
from history_shorts.text import font

# --- frame -----------------------------------------------------------------------------
FRAME_OUTER_INSET: Final = 40
FRAME_OUTER_WIDTH: Final = 5.0
FRAME_INNER_INSET: Final = 58
FRAME_INNER_WIDTH: Final = 1.5
SCROLL_OUTER: Final = ((0, 70), (0, 20, 20, 0, 70, 0))  # M(0,70) C(0,20 20,0 70,0)
SCROLL_OUTER_WIDTH: Final = 2.5
SCROLL_INNER: Final = ((18, 54), (18, 30, 30, 18, 54, 18))  # M(18,54) C(18,30 30,18 54,18)
SCROLL_INNER_WIDTH: Final = 1.5
SCROLL_DOT_CENTER: Final = (30, 30)
SCROLL_DOT_RADIUS: Final = 6

# --- waves -----------------------------------------------------------------------------
WAVE_ROW_SPACING: Final = 46
WAVE_STEP: Final = 104
WAVE_RADII: Final = (46, 32, 18)
WAVE_ALPHA_START: Final = 0.9
WAVE_ALPHA_DROP: Final = 0.15
WAVE_LINE_WIDTH: Final = 2.0
WAVE_CREST: Final = 1.1  # control-point height as a multiple of the radius
WAVE_COLOR_KEYS: Final = ("gold", "gold_dk")

# --- seal (metrics are proportional to the theme's seal size; 118 is the reference) -------
SEAL_REF_SIZE: Final = 118.0
SEAL_FONT_REF: Final = 36
SEAL_LINE_PITCH_REF: Final = 46
SEAL_TOP_REF: Final = 14
SEAL_INSET_REF: Final = 8
SEAL_RADIUS_REF: Final = 10
SEAL_INNER_RADIUS_REF: Final = 6
SEAL_BORDER_WIDTH: Final = 3
SEAL_INNER_WIDTH: Final = 1

# --- tag pill --------------------------------------------------------------------------
TAG_PAD_X: Final = 26  # per side
TAG_EXTRA_HEIGHT: Final = 26
TAG_RADIUS: Final = 30
TAG_BORDER_WIDTH: Final = 2
TAG_TEXT_DY: Final = 10
TAG_SEAL_GAP: Final = 12  # minimum clearance between seal and pill
TAG_RIGHT_MARGIN: Final = 58

# --- progress bar and footer (spec §8.2, amended) ---------------------------------------
PROGRESS_Y: Final = 1540
PROGRESS_HEIGHT: Final = 4
PROGRESS_X0: Final = 80
PROGRESS_X1: Final = 930
PROGRESS_TRACK_ALPHA: Final = 0.4
FOOTER_CENTER_X: Final = 540
FOOTER_TOP: Final = 1830


# --------------------------------------------------------------------------------------
# Frame and waves (Cairo)
# --------------------------------------------------------------------------------------


def draw_frame(cv: Canvas, palette: Palette) -> None:
    """Double gold frame with a cloud scroll in each inner corner."""
    gold, gold_dk = palette["gold"], palette["gold_dk"]
    outer, inner = FRAME_OUTER_INSET, FRAME_INNER_INSET
    cv.color(gold).rect(outer, outer, cv.w - 2 * outer, cv.h - 2 * outer).stroke(FRAME_OUTER_WIDTH)
    cv.color(gold_dk).rect(inner, inner, cv.w - 2 * inner, cv.h - 2 * inner).stroke(
        FRAME_INNER_WIDTH
    )
    corners = (
        (inner, inner, 1, 1),
        (cv.w - inner, inner, -1, 1),
        (inner, cv.h - inner, 1, -1),
        (cv.w - inner, cv.h - inner, -1, -1),
    )
    for x, y, flip_x, flip_y in corners:
        cv.save()
        cv.translate(x, y)
        cv.scale(flip_x, flip_y)
        _draw_scroll(cv, palette)
        cv.restore()


def _draw_scroll(cv: Canvas, palette: Palette) -> None:
    gold = palette["gold"]
    (mx, my), curve = SCROLL_OUTER
    cv.color(gold).M(mx, my).C(*curve).stroke(SCROLL_OUTER_WIDTH)
    (mx, my), curve = SCROLL_INNER
    cv.M(mx, my).C(*curve).stroke(SCROLL_INNER_WIDTH)
    dx, dy = SCROLL_DOT_CENTER
    cv.new_path().ellipse(dx, dy, SCROLL_DOT_RADIUS, SCROLL_DOT_RADIUS).fill()


def draw_waves(cv: Canvas, palette: Palette, spec: WavesSpec) -> None:
    """Rows of nested wave arcs (sóng nước); odd rows are shifted half a step."""
    for row in range(spec.rows):
        y = spec.y + row * WAVE_ROW_SPACING
        offset = 0.0 if row % 2 == 0 else WAVE_STEP / 2
        rgb = palette[WAVE_COLOR_KEYS[row % 2]]
        x = -WAVE_STEP + offset
        while x < cv.w + WAVE_STEP:
            for k, r in enumerate(WAVE_RADII):
                alpha = WAVE_ALPHA_START - k * WAVE_ALPHA_DROP
                crest = y - r * WAVE_CREST
                cv.color(rgb, alpha).M(x - r, y).C(x - r, crest, x + r, crest, x + r, y)
                cv.stroke(WAVE_LINE_WIDTH)
            x += WAVE_STEP


# --------------------------------------------------------------------------------------
# Seal and tag (Pillow)
# --------------------------------------------------------------------------------------


def seal_box(theme: Theme) -> Box:
    seal = theme.chrome.seal
    return Box(seal.x, seal.y, seal.x + seal.size, seal.y + seal.size)


def draw_seal(img: Image.Image, theme: Theme) -> None:
    """Vermilion seal with a gold border, an inner ivory line and the theme's seal lines."""
    spec, palette = theme.chrome.seal, theme.palette
    unit = spec.size / SEAL_REF_SIZE
    x, y, size = spec.x, spec.y, spec.size
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (x, y, x + size, y + size),
        radius=SEAL_RADIUS_REF * unit,
        fill=palette["vermilion"],
        outline=palette["gold"],
        width=SEAL_BORDER_WIDTH,
    )
    inset = SEAL_INSET_REF * unit
    draw.rounded_rectangle(
        (x + inset, y + inset, x + size - inset, y + size - inset),
        radius=SEAL_INNER_RADIUS_REF * unit,
        outline=palette["egg"],
        width=SEAL_INNER_WIDTH,
    )
    face = font(theme.fonts.title, round(SEAL_FONT_REF * unit))
    for i, line in enumerate(spec.lines):
        w = draw.textlength(line, font=face)
        top = y + (SEAL_TOP_REF + i * SEAL_LINE_PITCH_REF) * unit
        draw.text((x + (size - w) / 2, top), line, font=face, fill=palette["egg"])


def tag_box(text: str, theme: Theme) -> Box | None:
    """The pill's box (centred on ``tag.cx``), or ``None`` for an empty tag."""
    if not text.strip():
        return None
    size = theme.type_scale.tag
    width = font(theme.fonts.tag, size).getlength(text) + 2 * TAG_PAD_X
    spec = theme.chrome.tag
    return Box(spec.cx - width / 2, spec.y, spec.cx + width / 2, spec.y + size + TAG_EXTRA_HEIGHT)


def draw_tag(img: Image.Image, text: str, theme: Theme) -> None:
    box = tag_box(text, theme)
    if box is None:
        return
    palette = theme.palette
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (box.x0, box.y0, box.x1, box.y1),
        radius=TAG_RADIUS,
        fill=palette["vermilion"],
        outline=palette["gold"],
        width=TAG_BORDER_WIDTH,
    )
    face = font(theme.fonts.tag, theme.type_scale.tag)
    draw.text((box.x0 + TAG_PAD_X, box.y0 + TAG_TEXT_DY), text, font=face, fill=palette["gold_lt"])


def tag_too_wide(box: Box, theme: Theme) -> bool:
    """True when the pill would touch the seal or run past the right margin."""
    return box.x0 < seal_box(theme).x1 + TAG_SEAL_GAP or box.x1 > CANVAS_W - TAG_RIGHT_MARGIN


# --------------------------------------------------------------------------------------
# Progress bar and footer (Pillow, off by default)
# --------------------------------------------------------------------------------------


def draw_progress_bar(img: Image.Image, theme: Theme, index: int, count: int) -> None:
    """Thin track with a gold fill showing ``(index + 1) / count`` of the video."""
    palette = theme.palette
    y1 = PROGRESS_Y + PROGRESS_HEIGHT
    track = Image.new("RGB", (PROGRESS_X1 - PROGRESS_X0, PROGRESS_HEIGHT), palette["gold_dk"])
    mask = Image.new("L", track.size, round(255 * PROGRESS_TRACK_ALPHA))
    img.paste(track, (PROGRESS_X0, PROGRESS_Y), mask)
    fill_x1 = PROGRESS_X0 + round((PROGRESS_X1 - PROGRESS_X0) * (index + 1) / count)
    ImageDraw.Draw(img).rectangle(
        (PROGRESS_X0, PROGRESS_Y, fill_x1 - 1, y1 - 1), fill=palette["gold"]
    )


def draw_footer(img: Image.Image, theme: Theme) -> None:
    text = theme.chrome.footer.text
    if not text.strip():
        return
    face = font(theme.fonts.tag, theme.type_scale.tag)
    draw = ImageDraw.Draw(img)
    width = draw.textlength(text, font=face)
    draw.text(
        (FOOTER_CENTER_X - width / 2, FOOTER_TOP), text, font=face, fill=theme.palette["gold_dk"]
    )
