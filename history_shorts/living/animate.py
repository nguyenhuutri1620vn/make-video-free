"""Ambient motion of one scene layer, applied to its rendered RGBA (no drawer changes).

Every motion is periodic in the loop phase ``p`` (0…1), so the last frame of a loop runs
into the first without a seam, and is the identity at ``p = 0``, so a living slide's first
frame equals its still preview. Pixels are premultiplied, which keeps resampled edges clean.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from scipy.ndimage import affine_transform, map_coordinates

from history_shorts.config import LivingSpec
from history_shorts.living.types import FloatRGBA

RIPPLE_WAVELENGTH: Final = 24.0  # px between ripple crests
CROP_SLACK: Final = 4  # px of margin beyond the motion amplitude
ALPHA_FLOOR: Final = 1 / 255
KINDS: Final = ("bob", "sway", "ripple", "pulse", "float")


@dataclass(frozen=True, slots=True)
class Motion:
    """One layer's ambient motion.

    ``anchor`` is the pivot (x, y) in crop pixels; ``freq`` the whole number of cycles per
    loop; ``sign`` flips the direction (items drift out of step); ``flicker`` weighs three
    harmonics of a lantern's glow."""

    kind: str
    anchor: tuple[float, float]
    freq: int = 1
    sign: float = 1.0
    flicker: tuple[float, float, float] = (0.0, 0.0, 0.0)


def _wave(p: float, motion: Motion) -> float:
    return motion.sign * math.sin(2 * math.pi * motion.freq * p)


def _affine(crop: FloatRGBA, degrees: float, dy: float, anchor: tuple[float, float]) -> FloatRGBA:
    """Rotate about ``anchor`` and move down by ``dy`` (bilinear, transparent outside)."""
    theta = math.radians(degrees)
    c, s = math.cos(theta), math.sin(theta)
    matrix = np.array([[c, s], [-s, c]])  # output (row, col) -> input (row, col)
    pivot = np.array([anchor[1], anchor[0]])
    offset = pivot - matrix @ (pivot + np.array([dy, 0.0]))
    out = np.empty_like(crop)
    for ch in range(crop.shape[2]):
        out[..., ch] = affine_transform(crop[..., ch], matrix, offset, order=1, mode="constant")
    return out


def _ripple(crop: FloatRGBA, p: float, spec: LivingSpec, motion: Motion) -> FloatRGBA:
    """Horizontal shimmer travelling down the water; zero displacement at ``p = 0``."""
    h, w = crop.shape[:2]
    rows = np.arange(h, dtype=np.float64)[:, None]
    phase = 2 * math.pi * rows / RIPPLE_WAVELENGTH
    loop = 2 * math.pi * motion.freq * p
    dx = spec.ripple_px * motion.sign * (np.sin(phase - loop) - np.sin(phase))
    cols = np.arange(w, dtype=np.float64)[None, :] - dx
    coords = np.stack([np.broadcast_to(rows, (h, w)), cols])
    out = np.empty_like(crop)
    for ch in range(crop.shape[2]):
        out[..., ch] = map_coordinates(crop[..., ch], coords, order=1, mode="nearest")
    return out


def _brightness(crop: FloatRGBA, factor: float) -> FloatRGBA:
    out = crop.copy()
    out[..., :3] = crop[..., :3] * factor  # grain may lift premultiplied RGB a hair above alpha
    return out


def _flicker(p: float, motion: Motion, spec: LivingSpec) -> float:
    harmonics = sum(w * math.sin(2 * math.pi * (n + 1) * p) for n, w in enumerate(motion.flicker))
    return 1 + spec.flicker * harmonics / max(sum(abs(w) for w in motion.flicker), 1e-9)


def transform_frame(crop: FloatRGBA, p: float, motion: Motion, spec: LivingSpec) -> FloatRGBA:
    """``crop`` at loop phase ``p``."""
    wave = _wave(p, motion)
    if motion.kind == "bob":
        return _affine(crop, spec.roll_deg * wave, spec.bob_px * wave, motion.anchor)
    if motion.kind == "sway":
        return _affine(crop, spec.sway_deg * wave, 0.0, motion.anchor)
    if motion.kind == "ripple":
        return _ripple(crop, p, spec, motion)
    if motion.kind == "pulse":
        return _brightness(crop, 1 + spec.glow_pulse * wave)
    if motion.kind == "float":
        moved = _affine(crop, spec.roll_deg * wave, spec.bob_px * wave, motion.anchor)
        return _brightness(moved, _flicker(p, motion, spec))
    raise ValueError(f"unknown motion {motion.kind!r}; allowed: {', '.join(KINDS)}")


def motion_margin(h: int, w: int, spec: LivingSpec) -> int:
    """Crop margin that holds the largest bob plus the largest rotation of an h x w box."""
    turn = math.sin(math.radians(max(spec.roll_deg, spec.sway_deg))) * math.hypot(h, w)
    return math.ceil(spec.bob_px + spec.ripple_px * 2 + turn + CROP_SLACK)


def alpha_bbox(full: FloatRGBA) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) of the visible pixels, x1/y1 exclusive; None when empty."""
    ys, xs = np.nonzero(full[..., 3] > ALPHA_FLOOR)
    if not len(ys):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def animate_crop(full: FloatRGBA, margin: int) -> tuple[FloatRGBA, tuple[int, int]]:
    """The visible part of a full-canvas layer plus ``margin`` px all round (zeros outside the
    canvas), and its top-left origin (x, y) in canvas pixels (may be negative)."""
    box = alpha_bbox(full)
    if box is None:
        return np.zeros((1, 1, 4), dtype=np.float32), (0, 0)
    x0, y0, x1, y1 = box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin
    h, w = full.shape[:2]
    pad = ((max(-y0, 0), max(y1 - h, 0)), (max(-x0, 0), max(x1 - w, 0)), (0, 0))
    padded = np.pad(full, pad)
    sy, sx = y0 + pad[0][0], x0 + pad[1][0]
    return np.ascontiguousarray(padded[sy : sy + (y1 - y0), sx : sx + (x1 - x0)]), (x0, y0)
