"""Texture tests: determinism, statistics, mask containment, source guards (FR-60..65, C-08)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.ndimage import binary_dilation, binary_opening, label

from history_shorts.config import SheenSpec
from history_shorts.textures import (
    EGG_MIN_SEED_SEPARATION,
    EGG_SHADE_RANGE,
    GOLD_GRAIN_AMOUNT,
    GOLD_GRAIN_SIGMA,
    GOLD_SEAM_DARKEN,
    GOLD_SEAM_WIDTH,
    GOLD_SHEEN_AMOUNT,
    GOLD_SHEEN_PERIOD,
    GOLD_TONE_RANGE,
    GOLD_WORN_DILATE,
    GOLD_WORN_KEEP,
    GOLD_WORN_SCALE,
    GOLD_WORN_SIGMA,
    GOLD_WORN_SPREAD,
    GROUND_BOTTOM_BLEND,
    GROUND_NOISE_AMOUNT,
    GROUND_NOISE_SCALE,
    GROUND_NOISE_SIGMA,
    GROUND_PROFILE_POWER,
    _cover,
    _separated,
    eggshell,
    finish,
    gold_leaf,
    lacquer_ground,
    noise,
)

H, W = 1920, 1080
REPO_ROOT = Path(__file__).resolve().parent.parent


def _make(fn: str, rng: np.random.Generator, palette: Any, mask: Any) -> Any:
    makers: dict[str, Callable[[], Any]] = {
        "ground": lambda: lacquer_ground(rng, palette),
        "gold": lambda: gold_leaf(rng, palette, tile=34, worn=0.05),
        "egg": lambda: eggshell(rng, mask, palette, cell=16, gap=1.0),
        "finish": lambda: finish(
            np.full((H, W, 3), 0.4, np.float32), rng, palette, SheenSpec(330, 760, 620, 0.1), 0.025
        ),
    }
    return makers[fn]()


@pytest.mark.parametrize("fn", ["ground", "gold", "egg", "finish"])
def test_deterministic(fn: str, palette: Any, cloud_mask: Any) -> None:
    a = _make(fn, np.random.default_rng([40, 0, 1]), palette, cloud_mask)
    b = _make(fn, np.random.default_rng([40, 0, 1]), palette, cloud_mask)
    assert a.dtype == np.float32 and a.shape == (H, W, 3)
    assert np.array_equal(a, b)


def test_noise_normalised() -> None:
    n = noise(100, 80, 4.0, np.random.default_rng(3))
    assert n.shape == (100, 80) and n.dtype == np.float32
    assert abs(float(n.mean())) < 1e-3
    assert float(np.abs(n).max()) == pytest.approx(1.0, abs=1e-4)


def test_lacquer_ground_profile(palette: Any) -> None:
    g = lacquer_ground(np.random.default_rng(1), palette)
    assert g.shape == (1920, 1080, 3) and g.dtype == np.float32 and not np.isnan(g).any()
    black, deep = np.array(palette.rgb01("black")), np.array(palette.rgb01("deep"))
    assert np.abs(g[0].mean(0) - black).max() < 0.03
    assert np.linalg.norm(g[960].mean(0) - deep) < np.linalg.norm(g[960].mean(0) - black)


def test_lacquer_ground_custom_size(palette: Any) -> None:
    g = lacquer_ground(np.random.default_rng(1), palette, width=200, height=300)
    assert g.shape == (300, 200, 3)


def test_gold_leaf_seams_and_tone(palette: Any) -> None:
    t = gold_leaf(np.random.default_rng(1), palette, tile=34, worn=0.05)
    gold = np.array(palette.rgb01("gold"))
    assert np.abs(t.mean((0, 1)) / gold - 1).max() < 0.12
    seam_rows = t[::34].mean()
    body = t[17::34].mean()
    assert 0.75 < seam_rows / body < 0.90
    assert t.min() >= 0 and t.max() <= 1


def _gold(worn: float, palette: Any, seed: int = 1) -> Any:
    return gold_leaf(np.random.default_rng(seed), palette, tile=34, worn=worn)


def test_gold_leaf_worn_spots_only_near_seams(palette: Any) -> None:  # FR-61
    base = _gold(0.0, palette)
    wornout = _gold(0.3, palette)
    under = np.array(palette.rgb01("vermilion_dk"), dtype=np.float32)
    changed = np.any(base != wornout, axis=-1)
    assert changed.sum() > 1000  # large `worn` really wears something
    yy, xx = np.mgrid[0:H, 0:W]
    seam = ((xx % 34) < GOLD_SEAM_WIDTH) | ((yy % 34) < GOLD_SEAM_WIDTH)
    assert not (changed & ~binary_dilation(seam, iterations=3)).any()
    expected = base[changed] * GOLD_WORN_KEEP + under * (1 - GOLD_WORN_KEEP)
    assert np.allclose(wornout[changed], np.clip(expected, 0, 1), atol=1e-6)
    # every worn pixel moved toward the under-layer colour
    before = np.linalg.norm(base[changed] - under, axis=-1)
    after = np.linalg.norm(wornout[changed] - under, axis=-1)
    assert np.all(after < before)


def test_gold_leaf_worn_zero_shows_no_underlayer(palette: Any) -> None:  # FR-61
    base = _gold(0.0, palette)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    # every un-worn pixel is the gold colour times one scalar (tone, sheen, grain, seam);
    # a pixel blended toward the under-layer would break that proportionality
    unclipped = base.max(axis=-1) < 0.999
    ratio = base[unclipped] / gold
    assert unclipped.mean() > 0.9
    assert np.abs(ratio.max(axis=-1) / ratio.min(axis=-1) - 1).max() < 1e-4


def test_gold_leaf_tile_tone_jitter_range(palette: Any) -> None:  # FR-61
    t = _gold(0.0, palette)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    ratios = []
    for ty in range(2, H // 34 - 1):
        for tx in range(1, W // 34 - 1):
            y0, x0 = ty * 34, tx * 34
            body = t[y0 + 3 : y0 + 33, x0 + 3 : x0 + 33].mean((0, 1)) / gold
            sheen = 1 + GOLD_SHEEN_AMOUNT * np.sin((x0 + y0 + 34) / GOLD_SHEEN_PERIOD)
            ratios.append(body.mean() / sheen - 1)
    r = np.array(ratios)
    assert r.min() > -0.09 - 0.02 and r.max() < 0.07 + 0.02
    assert r.min() < -0.07 and r.max() > 0.05  # the whole jitter range is used


def _reference_ground(rng: np.random.Generator, palette: Any, h: int, w: int) -> Any:
    """Local copy of the original floor-division ground (the code before the size fix)."""
    col = lambda key: np.array(palette.rgb01(key), dtype=np.float32)  # noqa: E731
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    k = np.clip(np.sin(y * np.pi), 0, 1) ** GROUND_PROFILE_POWER
    base = col("black") * (1 - k) + col("deep") * k
    base = base * (1 - y * GROUND_BOTTOM_BLEND) + col("black") * (y * GROUND_BOTTOM_BLEND)
    base = np.broadcast_to(base, (h, w, 3)).copy()
    scale = GROUND_NOISE_SCALE
    low = noise(h // scale, w // scale, GROUND_NOISE_SIGMA, rng)
    low = np.kron(low, np.ones((scale, scale), dtype=np.float32))[:h, :w]
    base *= (1 + GROUND_NOISE_AMOUNT * low)[..., None]
    return np.clip(base, 0, 1)


def _reference_gold(rng: np.random.Generator, palette: Any, tile: int, worn: float) -> Any:
    """Local copy of the original floor-division gold leaf (the code before the size fix)."""
    col = lambda key: np.array(palette.rgb01(key), dtype=np.float32)  # noqa: E731
    h, w = H, W
    tone = rng.uniform(*GOLD_TONE_RANGE, (h // tile + 2, w // tile + 2)).astype(np.float32)
    tone = np.kron(tone, np.ones((tile, tile), dtype=np.float32))[:h, :w]
    g = col("gold")[None, None, :] * (1 + tone[..., None])
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    g *= (1 + GOLD_SHEEN_AMOUNT * np.sin((xx + yy) / GOLD_SHEEN_PERIOD))[..., None]
    g *= (1 + GOLD_GRAIN_AMOUNT * noise(h, w, GOLD_GRAIN_SIGMA, rng))[..., None]
    seam = ((xx % tile) < GOLD_SEAM_WIDTH) | ((yy % tile) < GOLD_SEAM_WIDTH)
    g[seam] *= GOLD_SEAM_DARKEN
    scale = GOLD_WORN_SCALE
    wear = noise(h // scale, w // scale, GOLD_WORN_SIGMA, rng)
    wear = np.kron(wear, np.ones((scale, scale), dtype=np.float32))[:h, :w]
    near = binary_dilation(seam, iterations=GOLD_WORN_DILATE)
    mask = (wear > 1 - worn * GOLD_WORN_SPREAD) & near
    g[mask] = g[mask] * GOLD_WORN_KEEP + col("vermilion_dk") * (1 - GOLD_WORN_KEEP)
    return np.clip(g, 0, 1)


def test_cover_equals_floor_division_at_canvas_size() -> None:
    # same coarse-noise shapes as before the size fix, so the RNG draws are identical
    assert _cover(H, GROUND_NOISE_SCALE) == H // GROUND_NOISE_SCALE
    assert _cover(W, GROUND_NOISE_SCALE) == W // GROUND_NOISE_SCALE
    assert _cover(H, GOLD_WORN_SCALE) == H // GOLD_WORN_SCALE
    assert _cover(W, GOLD_WORN_SCALE) == W // GOLD_WORN_SCALE
    assert _cover(207, 4) == 52 and _cover(301, 2) == 151 and _cover(1, 4) == 1


def test_ground_and_gold_match_pre_fix_algorithm(palette: Any) -> None:
    ground = lacquer_ground(np.random.default_rng(1), palette)
    assert np.array_equal(ground, _reference_ground(np.random.default_rng(1), palette, H, W))
    gold = _gold(0.05, palette)
    assert np.array_equal(gold, _reference_gold(np.random.default_rng(1), palette, 34, 0.05))


@pytest.mark.parametrize("size", [(301, 207), (5, 3), (1, 1), (1080, 1921)])
def test_arbitrary_canvas_sizes(palette: Any, size: tuple[int, int]) -> None:
    w, h = size
    g = lacquer_ground(np.random.default_rng(1), palette, width=w, height=h)
    t = gold_leaf(np.random.default_rng(1), palette, tile=34, worn=0.05, width=w, height=h)
    assert g.shape == (h, w, 3) and t.shape == (h, w, 3)
    assert not np.isnan(g).any() and not np.isnan(t).any()


@pytest.mark.parametrize("fn", ["ground", "gold", "egg", "finish"])
def test_different_seeds_differ(fn: str, palette: Any, cloud_mask: Any) -> None:
    a = _make(fn, np.random.default_rng([40, 0, 1]), palette, cloud_mask)
    b = _make(fn, np.random.default_rng([40, 0, 2]), palette, cloud_mask)
    assert not np.array_equal(a, b)


def test_eggshell_contained_and_gap_ratio(palette: Any, cloud_mask: Any) -> None:  # FR-36
    e = eggshell(np.random.default_rng(1), cloud_mask, palette, cell=16, gap=1.0)
    ys, xs = np.nonzero(cloud_mask > 0.01)
    outside = np.ones(cloud_mask.shape, bool)
    outside[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1] = False
    assert e[outside].max() == 0
    gap = np.all(np.isclose(e, palette.rgb01("egg_gap"), atol=1e-6), axis=-1) & (cloud_mask > 0.99)
    assert 0.04 < gap.sum() / (cloud_mask > 0.99).sum() < 0.25


EGG_CELLS = (11, 12, 15, 16)  # the cell sizes the shipped templates use
BLOB_SEEDS = range(4)


def _slab() -> Any:
    from history_shorts.canvas import Canvas

    cv = Canvas(W, H)
    cv.color((255, 255, 255)).rect(100, 300, 300, 240).fill()
    return cv.mask()


def _largest_gap_blob(palette: Any, mask: Any, cell: int, seed: int) -> int:
    """Pixels in the biggest gap-coloured region that is thicker than a hairline.

    Gap pixels along every cell edge form one connected network, so a plain component count
    measures the whole network. A 5x5 opening removes the edge lines (about 1-3 px wide) and
    keeps only blobs: regions where a cell itself turned gap-coloured.
    """
    e = eggshell(np.random.default_rng([40, 0, seed]), mask, palette, cell=cell, gap=1.0)
    gap = np.all(np.isclose(e, palette.rgb01("egg_gap"), atol=1e-6), axis=-1) & (mask > 0.5)
    blobs, count = label(binary_opening(gap, np.ones((5, 5), bool)), structure=np.ones((3, 3)))
    return int(np.bincount(blobs.ravel())[1:].max()) if count else 0


@pytest.mark.parametrize("cell", EGG_CELLS)
def test_eggshell_has_no_dark_blobs(cell: int, palette: Any) -> None:  # C-08
    mask = _slab()
    worst = max(_largest_gap_blob(palette, mask, cell, seed) for seed in BLOB_SEEDS)
    assert worst < 0.5 * cell * cell


@pytest.mark.parametrize("cell", EGG_CELLS)
def test_blob_check_fails_without_seed_separation(
    cell: int, palette: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative control: with near-duplicate seeds kept (the old behaviour) the check trips."""
    monkeypatch.setattr(
        "history_shorts.textures._separated", lambda pts, r: np.ones(len(pts), bool)
    )
    mask = _slab()
    worst = max(_largest_gap_blob(palette, mask, cell, seed) for seed in BLOB_SEEDS)
    assert worst >= 0.5 * cell * cell


def test_separated_drops_the_later_of_each_close_pair() -> None:
    pts = np.array([[0, 0], [1, 1], [10, 10], [10.5, 10], [30, 30], [0, 1]], dtype=np.float32)
    keep = _separated(pts, 2.0)
    assert keep.tolist() == [True, False, True, False, True, False]
    assert _separated(pts[:0].reshape(0, 2), 2.0).tolist() == []


def test_eggshell_seeds_keep_cell_separation_and_rng_count(palette: Any) -> None:
    """Dropping seeds must not change how many random numbers are drawn (determinism)."""
    mask = _slab()
    cell = 16
    rng = np.random.default_rng([40, 0, 3])
    eggshell(rng, mask, palette, cell=cell, gap=1.0)
    ys, xs = np.nonzero(mask > 0.01)
    n = len(range(ys.min(), ys.max() + 1, cell)) * len(range(xs.min(), xs.max() + 1, cell))
    ref = np.random.default_rng([40, 0, 3])
    ref.uniform(0, cell, (n, 2))
    ref.uniform(*EGG_SHADE_RANGE, n)
    assert rng.bit_generator.state == ref.bit_generator.state
    assert 0 < EGG_MIN_SEED_SEPARATION < 1


def test_eggshell_empty_mask(palette: Any) -> None:
    e = eggshell(np.random.default_rng(1), np.zeros((H, W), np.float32), palette, cell=16, gap=1.0)
    assert e.shape == (H, W, 3) and e.max() == 0


def _patch(img: Any, cx: int, cy: int, half: int = 10) -> Any:
    return img[cy - half : cy + half + 1, cx - half : cx + half + 1].mean((0, 1))


def test_finish_sheen_shape_and_grain(palette: Any) -> None:  # FR-62, C-08
    base = np.full((H, W, 3), 0.5, np.float32)
    strength, r = 0.10, 400
    out = finish(
        base, np.random.default_rng(1), palette, SheenSpec(540, 960, r, strength), grain=0.025
    )
    glow = strength * np.array(palette.rgb01("sheen"))
    far = _patch(out, 40, 40)  # d > r: no sheen
    centre = _patch(out, 540, 960) - far
    half_way = _patch(out, 540 + r // 2, 960) - far
    # centre: (1 - d/r)^2 over a 21 px patch averages just under 1
    assert np.allclose(centre, glow, atol=0.008)
    assert np.all(centre > 0.05)  # a no-op finish would give ~0
    # d = r/2 gives (1 - 1/2)^2 = 0.25 of the centre increment
    assert np.allclose(half_way, 0.25 * glow, atol=0.006)
    assert np.all(half_way > 0.015)
    # outside the sheen radius: grain only, spread ~2.5 % and never more
    region = out[1500:1920, 700:1080] / 0.5 - 1
    assert 0.003 < region.std()
    assert np.abs(region).max() <= 0.025 + 1e-5
    assert np.abs(region).max() > 0.012  # grain reaches a good part of its amplitude


def test_finish_bounds(palette: Any) -> None:
    base = np.full((1920, 1080, 3), 0.5, np.float32)
    out = finish(
        base, np.random.default_rng(1), palette, SheenSpec(330, 760, 620, 0.10), grain=0.025
    )
    far = out[1900, 1070] / 0.5
    assert np.all((far > 0.97) & (far < 1.03)) and out.max() <= 0.5 * 1.03 + 0.10 + 1e-6


def test_finish_does_not_mutate_input(palette: Any) -> None:
    base = np.full((100, 80, 3), 0.5, np.float32)
    finish(base, np.random.default_rng(1), palette, SheenSpec(10, 10, 50, 0.1), grain=0.025)
    assert np.all(base == 0.5)


def test_textures_module_has_no_crackle_or_global_rng() -> None:  # C-08, FR-65 guard
    src = (REPO_ROOT / "history_shorts" / "textures.py").read_text(encoding="utf-8")
    assert not re.search(r"crackle|scratch|crack", src, re.I)
    assert not re.search(r"(np|numpy)\.random\.(?!Generator\b|default_rng\b)", src)
    assert not re.search(r"from numpy import[^\n]*\brandom\b", src)
    assert not re.search(r"from numpy\.random import (?!Generator\b|default_rng\b)", src)
    assert not re.search(r"^\s*(import|from)\s+random\b", src, re.M)
    assert not re.search(r"^\s*import\s+[^\n]*\brandom\b", src, re.M)
    assert not re.search(r"^\s*(import|from)\s+time\b", src, re.M)
    assert not re.search(r"\btime\.\w+\(", src)
