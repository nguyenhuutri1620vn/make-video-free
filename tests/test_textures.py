"""Texture tests: determinism, statistics, mask containment, source guards (FR-60..65, C-08)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.ndimage import binary_dilation

from history_shorts.config import SheenSpec
from history_shorts.textures import eggshell, finish, gold_leaf, lacquer_ground, noise

H, W = 1920, 1080
REPO_ROOT = Path(__file__).resolve().parent.parent

# SHA-256 of the 1080x1920 outputs for default_rng(1); guards against output drift.
GROUND_SHA = "2e657d1920514d629f4b01b23d0966fec4ee210b405bce0d2cbf09989c314666"
GOLD_SHA = "884ca80cd2d8f49cac22644d35fad7828e44a8561ec8f555c39eaee3314204b7"


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
    seam = ((xx % 34) < 1.2) | ((yy % 34) < 1.2)
    assert not (changed & ~binary_dilation(seam, iterations=3)).any()
    expected = base[changed] * 0.35 + under * 0.65
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
            sheen = 1 + 0.10 * np.sin((x0 + y0 + 34) / 260.0)
            ratios.append(body.mean() / sheen - 1)
    r = np.array(ratios)
    assert r.min() > -0.09 - 0.02 and r.max() < 0.07 + 0.02
    assert r.min() < -0.07 and r.max() > 0.05  # the whole jitter range is used


def test_ground_and_gold_exact_output_unchanged(palette: Any) -> None:
    import hashlib

    g = lacquer_ground(np.random.default_rng(1), palette)
    assert hashlib.sha256(g.tobytes()).hexdigest() == GROUND_SHA
    assert hashlib.sha256(_gold(0.05, palette).tobytes()).hexdigest() == GOLD_SHA


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
