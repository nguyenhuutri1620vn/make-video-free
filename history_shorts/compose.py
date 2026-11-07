"""Compositing core, deterministic RNG derivation, and FR-21 slide assembly."""

from __future__ import annotations

import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Final

import numpy as np
from numpy.random import Generator, default_rng
from PIL import Image, ImageDraw

from . import chrome
from .canvas import Canvas
from .config import Palette, Script, SheenSpec, Theme
from .layout import CANVAS_H, CANVAS_W, REGIONS, SAFE_ZONE
from .primitives import Box, FloatImage, FloatMask
from .text import TextPlan, draw_text, plan_text
from .textures import finish, lacquer_ground

GROUND_LAYER: Final = 0  # scene layer k uses k + 1
FINISH_LAYER: Final = 999

# The float buffer is converted to a PIL image lazily, at the first Pillow step ("seal").
# "ground" through "frame" work on the float32 buffer.
SLIDE_STEPS: Final = (
    "ground",
    "scene",
    "waves",
    "finish",
    "frame",
    "seal",
    "tag",
    "title",
    "subtitle",
    "progress_bar",
    "footer",
)

DEBUG_COLOR_KEY: Final = "pink"
DEBUG_LINE_WIDTH: Final = 2
MASK_THRESHOLD: Final = 0.5


# --------------------------------------------------------------------------------------
# Compositing
# --------------------------------------------------------------------------------------


def over(base: FloatImage, cv: Canvas) -> FloatImage:
    """Composite a Cairo canvas (premultiplied) over ``base``: ``rgb + base * (1 - a)``."""
    rgb, alpha = cv.to_premul()
    return np.asarray(rgb + base * (1 - alpha[..., None]), dtype=np.float32)


def fill_mask(base: FloatImage, tex: FloatImage, mask: FloatMask) -> FloatImage:
    """Blend ``tex`` into ``base`` where ``mask`` is set; untouched where it is zero."""
    m = mask[..., None]
    return np.asarray(tex * m + base * (1 - m), dtype=np.float32)


# --------------------------------------------------------------------------------------
# Deterministic RNG (FR-65)
# --------------------------------------------------------------------------------------


def rng_for(seed: int, slide_index: int, layer_index: int) -> Generator:
    """RNG for one texture layer of one slide; never touches global state."""
    return default_rng([seed, slide_index, layer_index])


def eggshell_rng(seed: int, layer_index: int, mask: FloatMask) -> Generator:
    """Eggshell RNG: independent of the slide index, so equal masks look equal on every slide."""
    crc = zlib.crc32(np.packbits(mask > MASK_THRESHOLD).tobytes())
    return default_rng([seed, layer_index, crc])


# --------------------------------------------------------------------------------------
# Contexts
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DrawContext:
    """What a scene drawing callback needs: theme, palette and RNG derivation."""

    theme: Theme
    palette: Palette
    seed: int
    slide_index: int

    def rng(self, layer_index: int) -> Generator:
        return rng_for(self.seed, self.slide_index, layer_index)

    def eggshell_rng(self, layer_index: int, mask: FloatMask) -> Generator:
        return eggshell_rng(self.seed, layer_index, mask)


@dataclass(frozen=True, slots=True)
class SceneStyle:
    """Per-scene look: ground colour keys (top, mid, bottom), sheen and RNG seed."""

    ground: tuple[str, str, str]
    sheen: SheenSpec
    seed: int


SceneDrawer = Callable[[FloatImage, DrawContext], FloatImage]


@dataclass(frozen=True, slots=True)
class SlideContext:
    script: Script
    theme: Theme
    slide_index: int
    style: SceneStyle
    draw_scene: SceneDrawer | None
    debug_safe_zone: bool


def default_style(theme: Theme) -> SceneStyle:
    return SceneStyle(("black", "deep", "black"), theme.textures.sheen, theme.seed)


class SlideState:
    """The slide under construction: a float32 buffer first, one PIL image from ``seal`` on.

    The buffer is converted to 8-bit exactly once, when the first Pillow step asks for
    ``image()``. After that the float buffer is gone and float steps would be a bug.
    """

    def __init__(self, buffer: FloatImage) -> None:
        self._buffer: FloatImage | None = buffer
        self._image: Image.Image | None = None
        self.text_plan: TextPlan | None = None

    def array(self) -> FloatImage:
        if self._buffer is None:
            raise RuntimeError("float step after PIL conversion: the buffer is already an image")
        return self._buffer

    def set_array(self, buffer: FloatImage) -> None:
        if self._image is not None:
            raise RuntimeError("float step after PIL conversion: the buffer is already an image")
        self._buffer = buffer

    def image(self) -> Image.Image:
        if self._image is None:
            if self._buffer is None:
                raise RuntimeError("slide state holds neither a buffer nor an image")
            self._image = Image.fromarray(
                (np.clip(self._buffer, 0, 1) * 255).astype(np.uint8), "RGB"
            )
            self._buffer = None
        return self._image


# --------------------------------------------------------------------------------------
# Steps (FR-21)
# --------------------------------------------------------------------------------------

StepFunction = Callable[[SlideContext, SlideState], None]


def _step_ground(ctx: SlideContext, state: SlideState) -> None:
    top, mid, bottom = ctx.style.ground
    rng = rng_for(ctx.style.seed, ctx.slide_index, GROUND_LAYER)
    state.set_array(
        lacquer_ground(rng, ctx.theme.palette, top, mid, bottom, width=CANVAS_W, height=CANVAS_H)
    )


def _step_scene(ctx: SlideContext, state: SlideState) -> None:
    if ctx.draw_scene is None:
        return
    draw_ctx = DrawContext(ctx.theme, ctx.theme.palette, ctx.style.seed, ctx.slide_index)
    result = ctx.draw_scene(state.array(), draw_ctx)
    expected = (CANVAS_H, CANVAS_W, 3)
    if result.dtype != np.float32:
        raise TypeError(f"scene callback must return float32, got {result.dtype}")
    if result.shape != expected:
        raise ValueError(f"scene callback must return shape {expected}, got {result.shape}")
    state.set_array(result)


def _step_finish(ctx: SlideContext, state: SlideState) -> None:
    rng = rng_for(ctx.style.seed, ctx.slide_index, FINISH_LAYER)
    state.set_array(
        finish(state.array(), rng, ctx.theme.palette, ctx.style.sheen, ctx.theme.textures.grain)
    )


def _text_plan(ctx: SlideContext, state: SlideState) -> TextPlan:
    if state.text_plan is None:
        state.text_plan = plan_text(ctx.script.slides[ctx.slide_index], ctx.theme)
    return state.text_plan


def _draw_lines(ctx: SlideContext, state: SlideState, font_key: str) -> None:
    plan = _text_plan(ctx, state)
    lines = tuple(ln for ln in plan.lines if ln.font_key == font_key)
    draw_text(state.image(), replace(plan, lines=lines), ctx.theme)


def _step_title(ctx: SlideContext, state: SlideState) -> None:
    _draw_lines(ctx, state, "title")


def _step_subtitle(ctx: SlideContext, state: SlideState) -> None:
    _draw_lines(ctx, state, "subtitle")


def _overlay(state: SlideState, draw: Callable[[Canvas], None]) -> None:
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw(cv)
    state.set_array(over(state.array(), cv))


def _step_waves(ctx: SlideContext, state: SlideState) -> None:
    _overlay(state, lambda cv: chrome.draw_waves(cv, ctx.theme.palette, ctx.theme.chrome.waves))


def _step_frame(ctx: SlideContext, state: SlideState) -> None:
    if ctx.theme.chrome.frame:
        _overlay(state, lambda cv: chrome.draw_frame(cv, ctx.theme.palette))


def _step_seal(ctx: SlideContext, state: SlideState) -> None:
    chrome.draw_seal(state.image(), ctx.theme)


def _step_tag(ctx: SlideContext, state: SlideState) -> None:
    chrome.draw_tag(state.image(), ctx.script.slides[ctx.slide_index].tag, ctx.theme)


def _step_progress_bar(ctx: SlideContext, state: SlideState) -> None:
    if ctx.theme.chrome.progress_bar:
        chrome.draw_progress_bar(state.image(), ctx.theme, ctx.slide_index, len(ctx.script.slides))


def _step_footer(ctx: SlideContext, state: SlideState) -> None:
    if ctx.theme.chrome.footer.enabled:
        chrome.draw_footer(state.image(), ctx.theme)


STEP_FUNCTIONS: Mapping[str, StepFunction] = {
    "ground": _step_ground,
    "scene": _step_scene,
    "waves": _step_waves,
    "finish": _step_finish,
    "frame": _step_frame,
    "seal": _step_seal,
    "tag": _step_tag,
    "title": _step_title,
    "subtitle": _step_subtitle,
    "progress_bar": _step_progress_bar,
    "footer": _step_footer,
}


def _outline(draw: ImageDraw.ImageDraw, box: Box, color: tuple[int, int, int]) -> None:
    draw.rectangle((box.x0, box.y0, box.x1 - 1, box.y1 - 1), outline=color, width=DEBUG_LINE_WIDTH)


def _draw_debug_safe_zone(ctx: SlideContext, state: SlideState) -> None:
    draw = ImageDraw.Draw(state.image())
    color = ctx.theme.palette[DEBUG_COLOR_KEY]
    _outline(draw, SAFE_ZONE, color)
    for box in REGIONS.values():
        _outline(draw, box, color)


def render_slide(ctx: SlideContext) -> Image.Image:
    """Compose one slide in FR-21 order and return it as a 1080x1920 RGB image."""
    state = SlideState(np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.float32))
    for name in SLIDE_STEPS:
        STEP_FUNCTIONS[name](ctx, state)
    if ctx.debug_safe_zone:
        _draw_debug_safe_zone(ctx, state)
    return state.image()
