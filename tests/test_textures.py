"""Texture tests: determinism, statistics, mask containment, source guards (FR-60..65, C-08)."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.config import SheenSpec
from history_shorts.textures import eggshell, finish, gold_leaf, lacquer_ground, noise

H, W = 1920, 1080


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
    src = Path("history_shorts/textures.py").read_text(encoding="utf-8")
    assert not re.search(r"crackle|scratch|crack", src, re.I)
    assert not re.search(r"np\.random\.(?!Generator\b|default_rng\b)", src)
    assert "import random" not in src
