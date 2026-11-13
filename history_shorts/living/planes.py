"""Split a slide into premultiplied planes whose t = 0 composite equals the still slide.

The still slide is ``Pillow(T(frame + (1 - a_f) * (G * (waves + (1 - a_w) * scene) + G * sheen)))``
with grain ``G`` (a per-pixel factor) and tone ``T`` (linear in RGB). Both distribute over
premultiplied compositing, so each scene plane gets ``T(G * rgb)``, the waves plane likewise,
the sheen becomes a fixed additive plane ``T(G * sheen)``, and the frame plus the Pillow
chrome (seal, tag, progress bar, footer, and the text unless it fades in) form one top plane.
Planes made of Cairo drawings are recovered by drawing on black and on white (``matte``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from functools import partial
from typing import Final

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from history_shorts import chrome
from history_shorts.canvas import Canvas
from history_shorts.compose import (
    FINISH_LAYER,
    GROUND_LAYER,
    DrawContext,
    SlideContext,
    rng_for,
)
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage, FloatMask
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene_config import Depth, Layer
from history_shorts.text import draw_text, plan_text
from history_shorts.textures import grain_field, lacquer_ground, sheen_field, tone_grade

FloatRGBA = NDArray[np.float32]  # (h, w, 4): premultiplied RGB, then alpha
TEXT_FONTS: Final = ("title", "subtitle")


@dataclass(frozen=True)
class ScenePlane:
    """Consecutive scene layers of one depth; the first plane (ground) is opaque."""

    depth: Depth
    rgba: FloatRGBA
    layer_indices: tuple[int, ...]
    opaque: bool = False


@dataclass(frozen=True)
class TopPlanes:
    """The fixed planes over the moving scene: waves, additive sheen, chrome, fading text."""

    waves: FloatRGBA
    sheen: FloatImage
    chrome: FloatRGBA
    text: FloatRGBA | None


@dataclass(frozen=True)
class LivingStack:
    scene: tuple[ScenePlane, ...]
    top: TopPlanes


def _rgba(rgb: FloatImage, alpha: FloatMask) -> FloatRGBA:
    return np.concatenate([rgb, alpha[..., None]], axis=-1).astype(np.float32)


def matte(draw: Callable[[FloatImage], FloatImage], h: int, w: int) -> FloatRGBA:
    """Premultiplied RGBA of whatever ``draw`` composites over its base (linear drawers only)."""
    black = draw(np.zeros((h, w, 3), dtype=np.float32))
    white = draw(np.ones((h, w, 3), dtype=np.float32))
    alpha = np.clip(1 - (white - black).mean(axis=-1), 0, 1)
    return _rgba(black, alpha.astype(np.float32))


def _pillow_matte(base: FloatRGBA, draw: Callable[[Image.Image], None]) -> FloatRGBA:
    """Pillow steps drawn over the RGBA plane ``base``, recovered on black and on white."""
    rgb, alpha = base[..., :3], base[..., 3:]
    images = []
    for under in (0.0, 1.0):
        flat = np.clip(rgb + under * (1 - alpha), 0, 1)
        image = Image.fromarray((flat * 255).astype(np.uint8), "RGB")
        draw(image)
        images.append(np.asarray(np.asarray(image, dtype=np.float32) / 255, dtype=np.float32))
    black, white = images
    out_alpha = np.clip(1 - (white - black).mean(axis=-1), 0, 1)
    return _rgba(black, out_alpha.astype(np.float32))


def _draw_ctx(ctx: SlideContext) -> DrawContext:
    return DrawContext(ctx.theme, ctx.theme.palette, ctx.style.seed, ctx.slide_index, ctx.cache)


def draw_indexed(
    img: FloatImage, pairs: Sequence[tuple[int, Layer]], dctx: DrawContext
) -> FloatImage:
    """Draw scene layers keeping their index in the full list (it keys their RNG)."""
    for k, layer in pairs:
        img = LAYER_DRAWERS[type(layer)](img, layer, dctx, k + GROUND_LAYER + 1)
    return img


class _Finish:
    """Grain and tone of a slide, applied to premultiplied planes."""

    def __init__(self, ctx: SlideContext) -> None:
        rng = rng_for(ctx.style.seed, ctx.slide_index, FINISH_LAYER)
        self.grain = grain_field(CANVAS_H, CANVAS_W, rng, ctx.theme.textures.grain)[..., None]
        name = ctx.script.slides[ctx.slide_index].tone
        self.tone = ctx.theme.tones[name] if name != "none" else None

    def toned(self, rgb: FloatImage) -> FloatImage:
        return rgb if self.tone is None else tone_grade(rgb, self.tone)

    def plane(self, rgba: FloatRGBA) -> FloatRGBA:
        rgb = self.toned(np.asarray(rgba[..., :3] * self.grain, dtype=np.float32))
        return _rgba(rgb, rgba[..., 3])


def _groups(depths: Sequence[Depth]) -> list[tuple[Depth, list[int]]]:
    groups: list[tuple[Depth, list[int]]] = []
    for k, depth in enumerate(depths):
        if groups and groups[-1][0] == depth:
            groups[-1][1].append(k)
        else:
            groups.append((depth, [k]))
    return groups


def _scene_planes(
    ctx: SlideContext, layers: Sequence[Layer], depths: Sequence[Depth], fin: _Finish
) -> list[ScenePlane]:
    dctx = _draw_ctx(ctx)
    groups = _groups(depths)
    top, mid, bottom = ctx.style.ground
    rng = rng_for(ctx.style.seed, ctx.slide_index, GROUND_LAYER)
    ground = lacquer_ground(
        rng, ctx.theme.palette, top, mid, bottom, width=CANVAS_W, height=CANVAS_H
    )
    first: list[int] = groups.pop(0)[1] if groups and groups[0][0] == "far" else []
    back = draw_indexed(ground, [(k, layers[k]) for k in first], dctx)
    alpha = np.ones((CANVAS_H, CANVAS_W), dtype=np.float32)
    planes = [ScenePlane("far", fin.plane(_rgba(back, alpha)), tuple(first), opaque=True)]
    for depth, indices in groups:
        pairs = [(k, layers[k]) for k in indices]
        rgba = matte(partial(draw_indexed, pairs=pairs, dctx=dctx), CANVAS_H, CANVAS_W)
        planes.append(ScenePlane(depth, fin.plane(rgba), tuple(indices)))
    return planes


def _canvas_rgba(draw: Callable[[Canvas], None]) -> FloatRGBA:
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw(cv)
    rgb, alpha = cv.to_premul()
    return _rgba(rgb, alpha)


def _chrome_plane(ctx: SlideContext, fin: _Finish, text_in: bool) -> FloatRGBA:
    theme, slide = ctx.theme, ctx.script.slides[ctx.slide_index]
    frame = _canvas_rgba(lambda cv: chrome.draw_frame(cv, theme.palette))
    if not theme.chrome.frame:
        frame = np.zeros_like(frame)
    frame = _rgba(fin.toned(frame[..., :3]), frame[..., 3])
    plan = plan_text(slide, theme)

    def pillow(image: Image.Image) -> None:
        chrome.draw_seal(image, theme)
        chrome.draw_tag(image, slide.tag, theme)
        if not text_in:
            for font in TEXT_FONTS:
                lines = tuple(ln for ln in plan.lines if ln.font_key == font)
                draw_text(image, replace(plan, lines=lines), theme)
        if theme.chrome.progress_bar:
            chrome.draw_progress_bar(image, theme, ctx.slide_index, len(ctx.script.slides))
        if theme.chrome.footer.enabled:
            chrome.draw_footer(image, theme)

    return _pillow_matte(frame, pillow)


def _top_planes(ctx: SlideContext, fin: _Finish) -> TopPlanes:
    theme, slide = ctx.theme, ctx.script.slides[ctx.slide_index]
    waves = fin.plane(
        _canvas_rgba(lambda cv: chrome.draw_waves(cv, theme.palette, theme.chrome.waves))
    )
    glow = sheen_field(CANVAS_H, CANVAS_W, theme.palette, ctx.style.sheen)
    sheen = fin.toned(np.asarray(glow * fin.grain, dtype=np.float32))
    text_in = slide.text_in != "none"
    text = None
    if text_in:
        empty = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.float32)
        plan = plan_text(slide, theme)
        text = _pillow_matte(empty, lambda image: draw_text(image, plan, theme))
    return TopPlanes(waves, sheen, _chrome_plane(ctx, fin, text_in), text)


def build_stack(ctx: SlideContext, layers: Sequence[Layer], depths: Sequence[Depth]) -> LivingStack:
    """The planes of slide ``ctx.slide_index``; ``depths`` from ``effective_depths``."""
    fin = _Finish(ctx)
    return LivingStack(tuple(_scene_planes(ctx, layers, depths, fin)), _top_planes(ctx, fin))


def over_rgba(base: FloatImage, plane: FloatRGBA) -> FloatImage:
    return np.asarray(plane[..., :3] + base * (1 - plane[..., 3:]), dtype=np.float32)


def recompose(stack: LivingStack) -> FloatImage:
    """The t = 0 composite of ``stack`` (equals the still slide up to 8-bit rounding)."""
    img = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.float32)
    for plane in stack.scene:
        img = over_rgba(img, plane.rgba)
    img = over_rgba(img, stack.top.waves)
    img = np.clip(img + stack.top.sheen, 0, 1)
    img = over_rgba(img, stack.top.chrome)
    if stack.top.text is not None:
        img = over_rgba(img, stack.top.text)
    return np.asarray(np.clip(img, 0, 1), dtype=np.float32)
