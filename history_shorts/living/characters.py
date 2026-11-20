"""Characters and boat crew on a 2.3 living slide (M10): one lazily drawn sprite per layer.

Each character follows its timeline (starting pose, timed actions, idle life). A layer
with any timed action spans the whole clip, one frame per video frame; otherwise it loops
one idle breath. Frames are drawn on demand inside a fixed box worked out from the posed
figures' geometry, so memory does not grow with the clip length. A boat bobs as in M9,
and characters standing ``on`` a boat get the same bob about the boat's own pivot, so their
feet stay on its deck.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from history_shorts.characters import resolve_style
from history_shorts.characters.figure import figure_boxes
from history_shorts.characters.formations import PlacedCharacter
from history_shorts.characters.idle import idle_params
from history_shorts.characters.pose import Pose
from history_shorts.characters.timeline import Timeline, timeline
from history_shorts.compose import GROUND_LAYER, DrawContext, SlideContext, rng_for
from history_shorts.config import BoatLayer, CharactersLayer, Layer, LivingSpec
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.living.animate import Motion, alpha_bbox, motion_margin, transform_frame
from history_shorts.living.types import FloatRGBA, SpritePlane
from history_shorts.primitives import Box, FloatImage
from history_shorts.scene.boat import crew_placements, draw_boat_posed
from history_shorts.scene.people import (
    CHAR_KEY,
    CHAR_STRIDE,
    draw_characters_posed,
    placed_characters,
)
from history_shorts.scene_config import Depth

BOX_SLACK = 6  # px around the posed geometry: strokes, anti-aliasing, the fist
ANIM_KEY = 500  # as living.planes: RNG key offset of a layer's ambient motion
CARRIERS: tuple[type, ...] = (BoatLayer,)  # layers a character may stand ``on``

Matte = Callable[[Callable[[FloatImage], FloatImage]], FloatRGBA]


def people_of(layer: Layer) -> list[PlacedCharacter]:
    """The layer's characters in draw order (crew order for a boat)."""
    if isinstance(layer, CharactersLayer):
        return placed_characters(layer)
    if isinstance(layer, BoatLayer):
        return crew_placements(layer)
    return []


@dataclass(frozen=True)
class Bob:
    """An M9 bob shared with a carrier: its motion and its pivot in canvas pixels."""

    motion: Motion
    pivot: tuple[float, float]


def _bob_sign(ctx: SlideContext, k: int) -> float:
    rng = rng_for(ctx.style.seed, ctx.slide_index, k + GROUND_LAYER + 1 + ANIM_KEY)
    return 1.0 if rng.random() < 0.5 else -1.0


def carrier_bob(ctx: SlideContext, k: int, still: FloatRGBA, spec: LivingSpec) -> Bob | None:
    """The bob of boat layer ``k`` as its M9 sprite applies it, pivot in canvas pixels."""
    box = alpha_bbox(still)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    margin = motion_margin(min(y1 - y0, 600), min(x1 - x0, 600), spec)
    pivot = (x0 + (x1 - x0) / 2, y1 - 1.0 + margin)
    return Bob(Motion("bob", (0.0, 0.0), 1, _bob_sign(ctx, k)), pivot)


@dataclass
class CharacterSprite:
    """Draws one character layer at any frame; see the module docstring."""

    ctx: SlideContext
    dctx: DrawContext
    k: int
    layer: Layer
    finish: Callable[[FloatRGBA], FloatRGBA]
    matte: Matte
    clip_seconds: float | None
    bob: Bob | None

    def __post_init__(self) -> None:
        slide = self.ctx.script.slides[self.ctx.slide_index]
        spec = self.ctx.theme.living
        fps = self.ctx.theme.video.fps
        self.people = people_of(self.layer)
        palette = self.ctx.theme.palette
        self.styles = [resolve_style(p.spec, palette) for p in self.people]
        index = self.k + GROUND_LAYER + 1
        mine = {p.spec.id for p in self.people if p.spec.id}
        timed = any(a.who in mine for a in slide.actions) and self.clip_seconds is not None
        self.timelines: list[Timeline] = []
        for n, (person, style) in enumerate(zip(self.people, self.styles, strict=True)):
            acts = [a for a in slide.actions if a.who and a.who == person.spec.id]
            rng = self.dctx.rng(CHAR_KEY + index * CHAR_STRIDE + n)
            idle = idle_params(rng) if person.spec.idle else None
            self.timelines.append(timeline(person.spec.pose, style.prop, acts, idle, spec))
        seconds = self.clip_seconds if timed and self.clip_seconds else spec.idle_loop_seconds
        self.frames = (math.ceil if timed else round)(seconds * fps)
        self.frames = max(self.frames, 2)
        self.loop = not timed
        self.fps = fps
        self.box = self._box()

    def time(self, p: float) -> float:
        """Slide seconds of frame ``p`` (0..1 over the sprite's frames)."""
        i = round(p * self.frames)
        i = i % self.frames if self.loop else min(i, self.frames - 1)
        return i / self.fps

    def poses(self, t: float) -> list[Pose]:
        return [at(t) for at in self.timelines]

    def _draw(self, poses: Sequence[Pose] | None) -> FloatRGBA:
        layer, dctx = self.layer, self.dctx

        def draw(base: FloatImage) -> FloatImage:
            if isinstance(layer, BoatLayer):
                return draw_boat_posed(base, layer, dctx, poses)
            assert isinstance(layer, CharactersLayer)
            still = [Pose() for _ in self.people] if poses is None else poses
            return draw_characters_posed(base, layer, dctx, still)

        return self.finish(self.matte(draw))

    def _box(self) -> Box:
        """Canvas box holding every frame: the layer at rest plus every posed figure."""
        rest = alpha_bbox(self._draw(None))
        box = Box(*rest) if rest is not None else None
        for i in range(self.frames):
            for person, style, pose in zip(
                self.people, self.styles, self.poses(i / self.fps), strict=True
            ):
                boxes = figure_boxes(dataclasses.replace(style, pose=pose), person.placement)
                for part in (boxes.head, boxes.body, boxes.prop):
                    if part is not None:
                        box = part if box is None else box.union(part)
        assert box is not None
        slack = BOX_SLACK
        if self.bob is not None:
            spec = self.ctx.theme.living
            slack += motion_margin(min(int(box.height), 600), min(int(box.width), 600), spec)
        x0 = max(math.floor(box.x0) - slack, -slack)
        y0 = max(math.floor(box.y0) - slack, -slack)
        x1 = min(math.ceil(box.x1) + slack, CANVAS_W + slack)
        y1 = min(math.ceil(box.y1) + slack, CANVAS_H + slack)
        return Box(x0, y0, x1, y1)

    def render(self, p: float) -> FloatRGBA:
        t = self.time(p)
        full = self._draw(self.poses(t))
        x0, y0, x1, y1 = (int(v) for v in (self.box.x0, self.box.y0, self.box.x1, self.box.y1))
        pad = ((max(-y0, 0), max(y1 - CANVAS_H, 0)), (max(-x0, 0), max(x1 - CANVAS_W, 0)), (0, 0))
        padded = np.pad(full, pad)
        sy, sx = y0 + pad[0][0], x0 + pad[1][0]
        crop = np.ascontiguousarray(padded[sy : sy + (y1 - y0), sx : sx + (x1 - x0)])
        if self.bob is None:
            return crop
        spec = self.ctx.theme.living
        pivot = (self.bob.pivot[0] - x0, self.bob.pivot[1] - y0)
        motion = dataclasses.replace(self.bob.motion, anchor=pivot)
        return transform_frame(crop, (t / spec.loop_seconds) % 1.0, motion, spec)

    def plane(self, depth: Depth) -> SpritePlane:
        size = (int(self.box.height), int(self.box.width))
        origin = (int(self.box.x0), int(self.box.y0))
        return SpritePlane(depth, origin, size, self.frames, self.render, (self.k,))
