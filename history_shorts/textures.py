"""Lacquer materials: ground, gold leaf, eggshell inlay, and the sheen + grain finish.

Pure numpy/scipy functions. All randomness comes from the ``rng`` argument, drawn in a
fixed order, so the same generator state always gives the same pixels. Colours come from
the theme palette (C-07). The only surface finish is a warm sheen and fine grain (C-08).
"""

from __future__ import annotations

import math

import numpy as np
from numpy.random import Generator
from scipy.ndimage import binary_dilation, gaussian_filter
from scipy.spatial import cKDTree

from .config import Palette, SheenSpec
from .layout import CANVAS_H, CANVAS_W
from .primitives import FloatImage, FloatMask

GROUND_NOISE_SCALE = 4  # low-frequency depth noise is made at 1/4 resolution
GROUND_NOISE_SIGMA = 18.0
GROUND_NOISE_AMOUNT = 0.10
GROUND_BOTTOM_BLEND = 0.30
GROUND_PROFILE_POWER = 1.5

GOLD_TONE_RANGE = (-0.09, 0.07)
GOLD_SHEEN_AMOUNT = 0.10
GOLD_SHEEN_PERIOD = 260.0
GOLD_GRAIN_AMOUNT = 0.04
GOLD_GRAIN_SIGMA = 0.8
GOLD_SEAM_WIDTH = 1.2
GOLD_SEAM_DARKEN = 0.82
GOLD_WORN_SCALE = 2  # worn-spot noise is made at 1/2 resolution
GOLD_WORN_SIGMA = 6.0
GOLD_WORN_SPREAD = 2.2
GOLD_WORN_DILATE = 3
GOLD_WORN_KEEP = 0.35

EGG_SHADE_RANGE = (-0.16, 0.02)

FINISH_GRAIN_SIGMA = 0.7


def noise(h: int, w: int, sigma: float, rng: Generator) -> FloatMask:
    """Smoothed standard-normal noise, zero mean, scaled so that max |v| is 1."""
    n = gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), sigma)
    n -= n.mean()
    return np.asarray(n / (np.abs(n).max() + 1e-6), dtype=np.float32)


def _upsample(small: FloatMask, factor: int, h: int, w: int) -> FloatMask:
    """Nearest-neighbour upsample by an integer factor, cropped to (h, w)."""
    big = np.kron(small, np.ones((factor, factor), dtype=np.float32))
    return np.asarray(big[:h, :w], dtype=np.float32)


def _colour(palette: Palette, key: str) -> FloatImage:
    return np.array(palette.rgb01(key), dtype=np.float32)


def lacquer_ground(
    rng: Generator,
    palette: Palette,
    top: str = "black",
    mid: str = "deep",
    bottom: str = "black",
    *,
    width: int = CANVAS_W,
    height: int = CANVAS_H,
) -> FloatImage:
    """Black-to-deep-to-black vertical ground with low-frequency depth variation."""
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None, None]
    k = np.clip(np.sin(y * math.pi), 0, 1) ** GROUND_PROFILE_POWER
    base = _colour(palette, top) * (1 - k) + _colour(palette, mid) * k
    base = base * (1 - y * GROUND_BOTTOM_BLEND) + _colour(palette, bottom) * (
        y * GROUND_BOTTOM_BLEND
    )
    base = np.broadcast_to(base, (height, width, 3)).copy()
    low = noise(height // GROUND_NOISE_SCALE, width // GROUND_NOISE_SCALE, GROUND_NOISE_SIGMA, rng)
    low = _upsample(low, GROUND_NOISE_SCALE, height, width)
    base *= (1 + GROUND_NOISE_AMOUNT * low)[..., None]
    return np.asarray(np.clip(base, 0, 1), dtype=np.float32)


def gold_leaf(
    rng: Generator,
    palette: Palette,
    tile: int,
    worn: float,
    under: str = "vermilion_dk",
    *,
    width: int = CANVAS_W,
    height: int = CANVAS_H,
) -> FloatImage:
    """Gold-leaf squares with tone jitter, seams, and worn spots showing the under-layer."""
    tiles_h, tiles_w = height // tile + 2, width // tile + 2
    tone = rng.uniform(*GOLD_TONE_RANGE, (tiles_h, tiles_w)).astype(np.float32)
    tone = np.kron(tone, np.ones((tile, tile), dtype=np.float32))[:height, :width]
    g = _colour(palette, "gold")[None, None, :] * (1 + tone[..., None])
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    g *= (1 + GOLD_SHEEN_AMOUNT * np.sin((xx + yy) / GOLD_SHEEN_PERIOD))[..., None]
    g *= (1 + GOLD_GRAIN_AMOUNT * noise(height, width, GOLD_GRAIN_SIGMA, rng))[..., None]
    seam = ((xx % tile) < GOLD_SEAM_WIDTH) | ((yy % tile) < GOLD_SEAM_WIDTH)
    g[seam] *= GOLD_SEAM_DARKEN
    wear = noise(height // GOLD_WORN_SCALE, width // GOLD_WORN_SCALE, GOLD_WORN_SIGMA, rng)
    wear = _upsample(wear, GOLD_WORN_SCALE, height, width)
    near_seam = binary_dilation(seam, iterations=GOLD_WORN_DILATE)
    worn_mask = (wear > 1 - worn * GOLD_WORN_SPREAD) & near_seam
    g[worn_mask] = g[worn_mask] * GOLD_WORN_KEEP + _colour(palette, under) * (1 - GOLD_WORN_KEEP)
    return np.asarray(np.clip(g, 0, 1), dtype=np.float32)


def eggshell(
    rng: Generator, mask: FloatMask, palette: Palette, cell: int, gap: float
) -> FloatImage:
    """Voronoi eggshell mosaic (can vo trung), computed only inside the mask's bounding box."""
    h, w = mask.shape
    out = np.zeros((h, w, 3), dtype=np.float32)
    ys, xs = np.nonzero(mask > 0.01)
    if len(ys) == 0:
        return out
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    gy, gx = np.mgrid[y0:y1:cell, x0:x1:cell]
    pts = np.stack([gy.ravel(), gx.ravel()], 1).astype(np.float32)
    pts += rng.uniform(0, cell, pts.shape)
    tree = cKDTree(pts)
    py, px = np.mgrid[y0:y1, x0:x1]
    query = np.stack([py.ravel(), px.ravel()], 1)
    dist, idx = tree.query(query, k=2)
    edge = (dist[:, 1] - dist[:, 0]) < gap
    shade = rng.uniform(*EGG_SHADE_RANGE, len(pts)).astype(np.float32)
    region = _colour(palette, "egg_tone")[None, :] * (1 + shade[idx[:, 0]])[:, None]
    region[edge] = _colour(palette, "egg_gap")
    out[y0:y1, x0:x1] = region.reshape(y1 - y0, x1 - x0, 3)
    return out


def finish(
    img: FloatImage, rng: Generator, palette: Palette, sheen: SheenSpec, grain: float
) -> FloatImage:
    """Warm radial sheen (added) and very fine grain (multiplied); nothing else."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((xx - sheen.x) ** 2 + (yy - sheen.y) ** 2) / sheen.r
    glow = (np.clip(1 - d, 0, 1) ** 2 * sheen.strength)[..., None] * _colour(palette, "sheen")
    out = img + glow
    out *= (1 + grain * noise(h, w, FINISH_GRAIN_SIGMA, rng))[..., None]
    return np.asarray(np.clip(out, 0, 1), dtype=np.float32)
