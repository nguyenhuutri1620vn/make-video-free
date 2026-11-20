"""Shared checks for phase drawers (M10): phase 0 is the still drawing, the loop is closed."""

from __future__ import annotations

from typing import Any

import numpy as np

from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS, PHASE_DRAWERS

INDEX = 3  # any layer index; it keys the layer's RNG


def draw_at(base: FloatImage, layer: Any, ctx: Any, phase: float) -> FloatImage:
    return PHASE_DRAWERS[type(layer)](base.copy(), layer, ctx, INDEX, phase)


def check_phase_drawer(base: FloatImage, layer: Any, ctx: Any) -> None:
    """Phase 0 equals the still drawer exactly; phase 1 equals phase 0 (seamless loop)."""
    still = LAYER_DRAWERS[type(layer)](base.copy(), layer, ctx, INDEX)
    zero = draw_at(base, layer, ctx, 0.0)
    assert np.array_equal(zero, still)
    assert np.abs(draw_at(base, layer, ctx, 1.0) - zero).max() <= 1 / 255


def moved_box(a: FloatImage, b: FloatImage) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) of the pixels that differ by more than 1/255; None when none do."""
    ys, xs = np.nonzero(np.abs(a - b).max(axis=2) > 1 / 255)
    if not len(ys):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
