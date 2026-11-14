"""Light particles over a living slide: falling lotus petals, drifting dust, rising embers.

Each particle moves on a smooth path that is periodic over the loop (``PARTICLE_LOOPS`` times
the ambient loop), so the sequence repeats without a seam. Particles stay inside the visual
region and fade out near its edges.
"""

from __future__ import annotations

import math
from functools import partial
from typing import Final

import numpy as np

from history_shorts.canvas import Canvas
from history_shorts.config import LivingSpec, Palette
from history_shorts.living.types import FloatRGBA, SpritePlane
from history_shorts.primitives import Box

PARTICLE_LOOPS: Final = 4  # a particle loop lasts this many ambient loops
EDGE_FADE: Final = 40.0  # px over which particles fade out at the region edges
SWAY_PX: Final = (12.0, 28.0)  # sideways sway range
DUST_WANDER: Final = (18.0, 30.0)  # vertical, horizontal wander of dust motes
# per kind: (rx, ry) size in px, alpha, vertical travel per loop (+1 down, -1 up, 0 wander)
SHAPES: Final = {
    "petals": ((6.0, 3.2), 0.85, 1),
    "dust": ((1.6, 1.6), 0.45, 0),
    "embers": ((2.2, 2.2), 0.8, -1),
}


def _edge(value: float, size: float) -> float:
    return max(0.0, min(1.0, value / EDGE_FADE, (size - value) / EDGE_FADE))


def _draw(
    params: np.ndarray, kind: str, color: tuple[int, int, int], h: int, w: int, p: float
) -> FloatRGBA:
    (rx, ry), alpha, travel = SHAPES[kind]
    cv = Canvas(w, h)
    for x0, y0, sway, freq, phase, wander in params:
        angle = 2 * math.pi * (freq * p + phase)
        x = x0 + sway * math.sin(angle)
        if travel:
            y = (y0 + travel * h * p) % h
        else:
            y = y0 + wander * math.sin(2 * math.pi * (p + phase))
        a = alpha * _edge(x, w) * _edge(y, h)
        if kind == "embers":
            a *= 0.6 + 0.4 * math.sin(2 * math.pi * (2 * p + phase)) ** 2
        if a <= 0:
            continue
        cv.save()
        cv.translate(x, y)
        cv.rotate(0.6 * math.sin(angle) if kind == "petals" else 0.0)
        cv.ellipse(0, 0, rx, ry).color(color, alpha=a).fill()
        cv.restore()
    rgb, mask = cv.to_premul()
    return np.concatenate([rgb, mask[..., None]], axis=-1).astype(np.float32)


def particle_sprite(
    kind: str,
    spec: LivingSpec,
    palette: Palette,
    rng: np.random.Generator,
    frames: int,
    region: Box,
) -> SpritePlane:
    """A sprite of ``spec.particle_count`` particles of ``kind`` filling ``region``;
    ``frames`` is the ambient loop length, the particle loop is ``PARTICLE_LOOPS`` times it."""
    if kind not in SHAPES:
        raise ValueError(f"unknown particles {kind!r}; allowed: {', '.join(SHAPES)}")
    h, w = int(region.y1 - region.y0), int(region.x1 - region.x0)
    n = spec.particle_count
    params = np.stack(
        [
            rng.uniform(EDGE_FADE, w - EDGE_FADE, n),
            rng.uniform(0, h, n),
            rng.uniform(*SWAY_PX, n),
            rng.integers(1, 4, n).astype(np.float64),
            rng.uniform(0, 1, n),
            rng.uniform(*DUST_WANDER, n),
        ],
        axis=1,
    )
    color = palette[spec.particle_colors[kind]]
    render = partial(_draw, params, kind, color, h, w)
    return SpritePlane(
        "near", (int(region.x0), int(region.y0)), (h, w), frames * PARTICLE_LOOPS, render
    )
