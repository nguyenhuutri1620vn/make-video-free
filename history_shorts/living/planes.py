"""Split a slide into premultiplied planes whose t = 0 composite equals the still slide.

The still slide is ``Pillow(T(frame + (1 - a_f) * C))`` with the finished scene
``C = clip(G * (waves + (1 - a_w) * scene) + G * sheen)``, grain ``G`` (a per-pixel
factor) and tone ``T`` (a 3x3 matrix, then a clip). Grain distributes over premultiplied
compositing, so each scene plane gets ``G * rgb``, the waves plane likewise, and the sheen
becomes a fixed additive plane ``G * sheen``. The tone is not applied per plane: a plane's
toned colour can pass 1 and be clipped where a plane above still lets it show through, so
``T`` is applied once to the composite after the frame, as on the still. The Pillow chrome
(seal, tag, progress bar, footer, and the text unless it fades in) forms one plane above.
Planes made of Cairo drawings are recovered by drawing on black and on white (``matte``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from types import MappingProxyType
from typing import Final

import numpy as np
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
from history_shorts.config import LivingSpec, ToneSpec
from history_shorts.layout import CANVAS_H, CANVAS_W, REGIONS
from history_shorts.living.animate import Motion, animate_crop, motion_margin, transform_frame
from history_shorts.living.particles import particle_sprite
from history_shorts.living.types import AnyPlane, DriftPlane, FloatRGBA, ScenePlane, SpritePlane
from history_shorts.primitives import FloatImage, FloatMask
from history_shorts.scene import LAYER_DRAWERS, PHASE_DRAWERS, phase_loop_seconds, redraws
from history_shorts.scene_config import (
    BirdsLayer,
    BoatLayer,
    CloudsLayer,
    Depth,
    LanternsLayer,
    Layer,
    LotusLayer,
    RiverLayer,
    SailBoatLayer,
    SunLayer,
)
from history_shorts.text import draw_text, plan_text
from history_shorts.textures import grain_field, lacquer_ground, sheen_field, tone_grade

TEXT_FONTS: Final = ("title", "subtitle")
EDGE_SLACK: Final = 2  # px beyond travel + shake that an edge sprite is extended
DRIFT_KINDS: Final[Mapping[type, str]] = MappingProxyType(
    {CloudsLayer: "cloud", BirdsLayer: "bird"}
)
SPRITE_KINDS: Final[Mapping[type, str]] = MappingProxyType(
    {
        BoatLayer: "bob",
        SailBoatLayer: "bob",
        RiverLayer: "ripple",
        LotusLayer: "sway",
        SunLayer: "pulse",
        LanternsLayer: "float",
    }
)
ANIMATED: Final = frozenset({*DRIFT_KINDS, *SPRITE_KINDS})


@dataclass(frozen=True)
class TopPlanes:
    """The fixed planes over the moving scene: waves, additive sheen, frame, then the tone
    (``None`` for none), then chrome and fading text."""

    waves: FloatRGBA
    sheen: FloatImage
    frame: FloatRGBA
    tone: ToneSpec | None
    chrome: FloatRGBA
    text: FloatRGBA | None


@dataclass(frozen=True)
class LivingStack:
    scene: tuple[AnyPlane, ...]
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
    """Grain of a slide, applied to premultiplied planes; its tone, applied to the composite."""

    def __init__(self, ctx: SlideContext) -> None:
        rng = rng_for(ctx.style.seed, ctx.slide_index, FINISH_LAYER)
        self.grain = grain_field(CANVAS_H, CANVAS_W, rng, ctx.theme.textures.grain)[..., None]
        name = ctx.script.slides[ctx.slide_index].tone
        self.tone = ctx.theme.tones[name] if name != "none" else None

    def plane(self, rgba: FloatRGBA) -> FloatRGBA:
        return _rgba(np.asarray(rgba[..., :3] * self.grain, dtype=np.float32), rgba[..., 3])


def _is_moving(layer: Layer, animated: bool, redraw: bool) -> bool:
    return animated and (type(layer) in ANIMATED or (redraw and redraws(layer)))


def _groups(
    layers: Sequence[Layer], depths: Sequence[Depth], animated: bool, redraw: bool = False
) -> list[tuple[Depth, list[int], bool]]:
    """Runs of still layers of one depth; an animated layer is a run of its own."""
    groups: list[tuple[Depth, list[int], bool]] = []
    for k, depth in enumerate(depths):
        moving = _is_moving(layers[k], animated, redraw)
        if groups and groups[-1][0] == depth and not moving and not groups[-1][2]:
            groups[-1][1].append(k)
        else:
            groups.append((depth, [k], moving))
    return groups


class _Animator:
    """Turns one animated layer into drift or sprite planes."""

    def __init__(self, ctx: SlideContext, fin: _Finish, redraw: bool = False) -> None:
        self.ctx, self.fin, self.dctx, self.redraw = ctx, fin, _draw_ctx(ctx), redraw
        self.spec = ctx.theme.living
        self.frames = max(round(self.spec.loop_seconds * ctx.theme.video.fps), 2)

    def _render(self, k: int, layer: Layer) -> FloatRGBA:
        draw = partial(draw_indexed, pairs=[(k, layer)], dctx=self.dctx)
        return self.fin.plane(matte(draw, CANVAS_H, CANVAS_W))

    def _sprite(self, k: int, depth: Depth, rgba: FloatRGBA, motion: Motion) -> SpritePlane:
        box_h, box_w = rgba.shape[:2]
        margin = motion_margin(min(box_h, 600), min(box_w, 600), self.spec)
        reach = math.ceil(self.spec.travel_px[depth] + self.spec.shake_px + EDGE_SLACK)
        edge = (reach, math.ceil(reach * CANVAS_H / CANVAS_W))
        crop, origin = animate_crop(rgba, margin, edge)
        h, w = crop.shape[:2]
        anchored = Motion(motion.kind, (w / 2, h - 1.0), motion.freq, motion.sign, motion.flicker)
        render = partial(_frame_at, crop, anchored, self.spec)
        return SpritePlane(depth, origin, (h, w), self.frames, render, (k,))

    def _redrawn(self, k: int, layer: Layer, depth: Depth, sign: float) -> SpritePlane:
        """Every loop phase drawn by the layer's phase drawer, cropped to their union box.

        A layer that also has an M9 ambient motion (a boat's bob) gets it on top, at as many
        whole cycles as fit its loop, so the crew moves with the hull."""
        drawer = PHASE_DRAWERS[type(layer)]
        reach = math.ceil(self.spec.travel_px[depth] + self.spec.shake_px + EDGE_SLACK)
        edge = (reach, math.ceil(reach * CANVAS_H / CANVAS_W))
        index = k + GROUND_LAYER + 1
        seconds = phase_loop_seconds(layer, self.spec)
        count = max(round(seconds * self.ctx.theme.video.fps), 2)
        crops: list[tuple[FloatRGBA, tuple[int, int]]] = []
        for i in range(count):
            phase = i / count

            def draw(base: FloatImage, phase: float = phase) -> FloatImage:
                return drawer(base, layer, self.dctx, index, phase)

            crops.append(animate_crop(self.fin.plane(matte(draw, CANVAS_H, CANVAS_W)), 0, edge))
        frames, origin = union_frames(crops)
        kind = SPRITE_KINDS.get(type(layer))
        if kind is not None:
            frames, origin = self._with_motion(frames, origin, kind, seconds, sign)
        h, w = frames[0].shape[:2]
        render = partial(_loop_frame, tuple(frames))
        return SpritePlane(depth, origin, (h, w), count, render, (k,))

    def _with_motion(
        self,
        frames: list[FloatRGBA],
        origin: tuple[int, int],
        kind: str,
        seconds: float,
        sign: float,
    ) -> tuple[list[FloatRGBA], tuple[int, int]]:
        h, w = frames[0].shape[:2]
        margin = motion_margin(min(h, 600), min(w, 600), self.spec)
        pad = ((margin, margin), (margin, margin), (0, 0))
        cycles = max(1, round(seconds / self.spec.loop_seconds))
        motion = Motion(kind, (w / 2 + margin, h - 1.0 + margin), cycles, sign)
        moved = [
            transform_frame(np.pad(f, pad), i / len(frames), motion, self.spec)
            for i, f in enumerate(frames)
        ]
        return moved, (origin[0] - margin, origin[1] - margin)

    def planes(self, k: int, layer: Layer, depth: Depth) -> list[AnyPlane]:
        rng = rng_for(self.ctx.style.seed, self.ctx.slide_index, k + GROUND_LAYER + 1 + ANIM_KEY)
        sign = 1.0 if rng.random() < 0.5 else -1.0
        if self.redraw and redraws(layer):
            return [self._redrawn(k, layer, depth, sign)]
        drift = DRIFT_KINDS.get(type(layer))
        if drift is not None:
            speed = self.spec.cloud_drift_px_s if drift == "cloud" else self.spec.bird_drift_px_s
            return [DriftPlane(depth, self._render(k, layer), (sign * speed, 0.0), (k,))]
        kind = SPRITE_KINDS[type(layer)]
        if isinstance(layer, LanternsLayer):
            out: list[AnyPlane] = []
            for item in layer.items:
                flicker = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
                motion = Motion(kind, (0.0, 0.0), int(rng.integers(1, 3)), sign, flicker)
                single = replace(layer, items=(item,))
                out.append(self._sprite(k, depth, self._render(k, single), motion))
                sign = -sign
            return out
        return [self._sprite(k, depth, self._render(k, layer), Motion(kind, (0.0, 0.0), 1, sign))]


def union_frames(
    crops: Sequence[tuple[FloatRGBA, tuple[int, int]]],
) -> tuple[list[FloatRGBA], tuple[int, int]]:
    """Paste crops with their own (x, y) origins into frames of their common box."""
    x0 = min(o[0] for _, o in crops)
    y0 = min(o[1] for _, o in crops)
    x1 = max(o[0] + c.shape[1] for c, o in crops)
    y1 = max(o[1] + c.shape[0] for c, o in crops)
    frames: list[FloatRGBA] = []
    for crop, (x, y) in crops:
        frame = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.float32)
        frame[y - y0 : y - y0 + crop.shape[0], x - x0 : x - x0 + crop.shape[1]] = crop
        frames.append(frame)
    return frames, (x0, y0)


def _loop_frame(frames: tuple[FloatRGBA, ...], p: float) -> FloatRGBA:
    return frames[round(p * len(frames)) % len(frames)]


ANIM_KEY: Final = 500  # RNG key offset for a layer's motion, apart from its drawing RNG


def _frame_at(crop: FloatRGBA, motion: Motion, spec: LivingSpec, p: float) -> FloatRGBA:
    return transform_frame(crop, p, motion, spec)


def _scene_planes(
    ctx: SlideContext,
    layers: Sequence[Layer],
    depths: Sequence[Depth],
    fin: _Finish,
    animated: bool,
    redraw: bool = False,
) -> list[AnyPlane]:
    dctx = _draw_ctx(ctx)
    groups = _groups(layers, depths, animated, redraw)
    top, mid, bottom = ctx.style.ground
    rng = rng_for(ctx.style.seed, ctx.slide_index, GROUND_LAYER)
    ground = lacquer_ground(
        rng, ctx.theme.palette, top, mid, bottom, width=CANVAS_W, height=CANVAS_H
    )
    still_far = groups and groups[0][0] == "far" and not groups[0][2]
    first: list[int] = groups.pop(0)[1] if still_far else []
    back = draw_indexed(ground, [(k, layers[k]) for k in first], dctx)
    alpha = np.ones((CANVAS_H, CANVAS_W), dtype=np.float32)
    planes: list[AnyPlane] = [
        ScenePlane("far", fin.plane(_rgba(back, alpha)), tuple(first), opaque=True)
    ]
    animator = _Animator(ctx, fin, redraw)
    for depth, indices, moving in groups:
        if moving:
            planes += animator.planes(indices[0], layers[indices[0]], depth)
            continue
        pairs = [(k, layers[k]) for k in indices]
        rgba = matte(partial(draw_indexed, pairs=pairs, dctx=dctx), CANVAS_H, CANVAS_W)
        planes.append(ScenePlane(depth, fin.plane(rgba), tuple(indices)))
    slide = ctx.script.slides[ctx.slide_index]
    if animated and slide.particles != "none":
        rng = rng_for(ctx.style.seed, ctx.slide_index, PARTICLE_KEY)
        spec, palette = ctx.theme.living, ctx.theme.palette
        planes.append(
            particle_sprite(slide.particles, spec, palette, rng, animator.frames, REGIONS["visual"])
        )
    return planes


PARTICLE_KEY: Final = 998  # RNG key of a slide's particles


def _canvas_rgba(draw: Callable[[Canvas], None]) -> FloatRGBA:
    cv = Canvas(CANVAS_W, CANVAS_H)
    draw(cv)
    rgb, alpha = cv.to_premul()
    return _rgba(rgb, alpha)


def _frame_plane(ctx: SlideContext) -> FloatRGBA:
    frame = _canvas_rgba(lambda cv: chrome.draw_frame(cv, ctx.theme.palette))
    return frame if ctx.theme.chrome.frame else np.zeros_like(frame)


def _chrome_plane(ctx: SlideContext, text_in: bool) -> FloatRGBA:
    theme, slide = ctx.theme, ctx.script.slides[ctx.slide_index]
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

    return _pillow_matte(np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.float32), pillow)


def _top_planes(ctx: SlideContext, fin: _Finish) -> TopPlanes:
    theme, slide = ctx.theme, ctx.script.slides[ctx.slide_index]
    waves = fin.plane(
        _canvas_rgba(lambda cv: chrome.draw_waves(cv, theme.palette, theme.chrome.waves))
    )
    glow = sheen_field(CANVAS_H, CANVAS_W, theme.palette, ctx.style.sheen)
    sheen = np.asarray(glow * fin.grain, dtype=np.float32)
    text_in = slide.text_in != "none"
    text = None
    if text_in:
        empty = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.float32)
        plan = plan_text(slide, theme)
        text = _pillow_matte(empty, lambda image: draw_text(image, plan, theme))
    chrome_plane = _chrome_plane(ctx, text_in)
    return TopPlanes(waves, sheen, _frame_plane(ctx), fin.tone, chrome_plane, text)


def build_stack(
    ctx: SlideContext,
    layers: Sequence[Layer],
    depths: Sequence[Depth],
    *,
    animated: bool = True,
    redraw: bool = False,
) -> LivingStack:
    """The planes of slide ``ctx.slide_index``; ``depths`` from ``effective_depths``.
    With ``animated``, moving layers become drift or sprite planes and particles are added;
    with ``redraw`` (schema 2.3), layers with a phase drawer are redrawn per loop frame."""
    fin = _Finish(ctx)
    scene = _scene_planes(ctx, layers, depths, fin, animated, redraw)
    return LivingStack(tuple(scene), _top_planes(ctx, fin))


def paste(img: FloatImage, sprite: FloatRGBA, origin: tuple[int, int]) -> FloatImage:
    """Composite ``sprite`` over ``img`` with its top-left corner at ``origin`` (clipped)."""
    x0, y0 = origin
    h, w = sprite.shape[:2]
    ys, xs = (
        slice(max(y0, 0), min(y0 + h, img.shape[0])),
        slice(max(x0, 0), min(x0 + w, img.shape[1])),
    )
    if ys.start >= ys.stop or xs.start >= xs.stop:
        return img
    part = sprite[ys.start - y0 : ys.stop - y0, xs.start - x0 : xs.stop - x0]
    out = img.copy()
    out[ys, xs] = over_rgba(img[ys, xs], part)
    return out


def over_rgba(base: FloatImage, plane: FloatRGBA) -> FloatImage:
    return np.asarray(plane[..., :3] + base * (1 - plane[..., 3:]), dtype=np.float32)


def recompose(stack: LivingStack) -> FloatImage:
    """The t = 0 composite of ``stack`` (equals the still slide up to 8-bit rounding)."""
    img = np.zeros((CANVAS_H, CANVAS_W, 3), dtype=np.float32)
    for plane in stack.scene:
        if isinstance(plane, SpritePlane):
            img = paste(img, plane.frame(0.0), plane.origin)
        else:
            img = over_rgba(img, plane.rgba)
    img = over_rgba(img, stack.top.waves)
    img = np.clip(img + stack.top.sheen, 0, 1)
    img = over_rgba(img, stack.top.frame)
    if stack.top.tone is not None:
        img = tone_grade(img, stack.top.tone)
    img = over_rgba(img, stack.top.chrome)
    if stack.top.text is not None:
        img = over_rgba(img, stack.top.text)
    return np.asarray(np.clip(img, 0, 1), dtype=np.float32)
