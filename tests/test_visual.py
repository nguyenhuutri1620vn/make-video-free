"""Rendered first slides against the owner-approved references (AC-03, AC-04, AC-06)."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from helpers.visual import region_delta_e, srgb_to_lab
from PIL import Image

from history_shorts.checks import check_all
from history_shorts.config import load_script
from history_shorts.layout import REGIONS

DELTA_E_MAX = 8.0  # AC-03, AC-04: per region, mean colour, ΔE76
EXAMPLES = [("nu_tuong", "scene_group.png"), ("me_linh", "scene_landscape.png")]


def _rgb(path: Path) -> Any:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


# -- the helper itself ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rgb", "lab"),
    [
        ((255, 255, 255), (100.0, 0.0, 0.0)),
        ((0, 0, 0), (0.0, 0.0, 0.0)),
        ((255, 0, 0), (53.24, 80.09, 67.20)),
        ((0, 255, 0), (87.73, -86.18, 83.18)),
        ((0, 0, 255), (32.30, 79.19, -107.86)),
        ((128, 128, 128), (53.59, 0.0, 0.0)),
    ],
)
def test_srgb_to_lab_matches_the_standard_values(
    rgb: tuple[int, int, int], lab: tuple[float, float, float]
) -> None:
    got = srgb_to_lab(np.array(rgb, dtype=np.uint8))
    assert got.tolist() == pytest.approx(list(lab), abs=0.1)


def test_srgb_to_lab_keeps_the_leading_shape() -> None:
    assert srgb_to_lab(np.zeros((4, 5, 3), dtype=np.uint8)).shape == (4, 5, 3)


def test_region_delta_e_is_zero_for_equal_images_and_euclidean_otherwise() -> None:
    from history_shorts.primitives import Box

    a = np.zeros((20, 20, 3), dtype=np.uint8)
    b = a.copy()
    b[:, 10:] = 255  # right half white: the left box is unchanged
    boxes = {"left": Box(0, 0, 10, 20), "all": Box(0, 0, 20, 20)}
    deltas = region_delta_e(a, b, boxes)
    assert deltas["left"] == 0.0
    mean_lab = srgb_to_lab(np.array([127.5] * 3))  # mean colour first, then Lab
    assert deltas["all"] == pytest.approx(math.hypot(*mean_lab), abs=1e-6)
    assert region_delta_e(a, a, boxes) == {"left": 0.0, "all": 0.0}


def test_region_delta_e_rejects_different_shapes() -> None:
    from history_shorts.primitives import Box

    with pytest.raises(ValueError, match="shapes differ"):
        region_delta_e(
            np.zeros((4, 4, 3), np.uint8), np.zeros((5, 4, 3), np.uint8), {"r": Box(0, 0, 2, 2)}
        )


# -- AC-03 / AC-04 (automated part) -------------------------------------------------------------


@pytest.mark.parametrize(("example", "reference"), EXAMPLES)
def test_first_slide_matches_reference_regions(
    example: str, reference: str, repo_root: Path, first_slide_png: Callable[[str], Path]
) -> None:
    ref = _rgb(repo_root / "docs" / "reference" / "approved" / reference)
    deltas = region_delta_e(_rgb(first_slide_png(example)), ref, REGIONS)
    assert set(deltas) == set(REGIONS)
    assert max(deltas.values()) <= DELTA_E_MAX, deltas


# -- AC-06 on templates ---------------------------------------------------------------------


@pytest.mark.parametrize("example", ["nu_tuong", "me_linh"])
def test_examples_have_no_overlap_or_other_errors(
    example: str, repo_root: Path, theme: Any
) -> None:
    script, _warnings = load_script(repo_root / "examples" / example / "script.json")
    errors = [i for i in check_all(script, theme) if i.severity == "error"]
    assert errors == []
