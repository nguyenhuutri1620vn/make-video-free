"""M11: the shipped artwork library."""

from __future__ import annotations

from typing import Any

import numpy as np
from helpers.visual import region_delta_e

from history_shorts.artwork.load import library_for
from history_shorts.compose import DrawContext, EggshellCache
from history_shorts.gallery import canvas_ground
from history_shorts.layout import REGIONS
from history_shorts.scene import LAYER_DRAWERS, PHASE_DRAWERS
from history_shorts.scene_config import ArtworkLayer, TabletLayer

SHIPPED = ("tablet_altar", "torch")


def _ctx(theme: Any) -> DrawContext:
    return DrawContext(theme, theme.palette, theme.seed, 0, EggshellCache())


def _rgb8(img: Any) -> Any:
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def test_library_checks_clean(theme: Any) -> None:
    library = library_for(theme)
    assert set(SHIPPED) <= set(library.names())
    for name in library.names():
        library.get(name, theme.palette)  # raises on any problem


def test_tablet_altar_matches_python_tablet(theme: Any) -> None:  # AC-40
    ground = canvas_ground(theme)
    python = LAYER_DRAWERS[TabletLayer](ground.copy(), TabletLayer(540, 1150, 1.6), _ctx(theme), 3)
    art = LAYER_DRAWERS[ArtworkLayer](
        ground.copy(), ArtworkLayer("tablet_altar", 540, 1150, 1.6), _ctx(theme), 3
    )
    regions = {"visual": REGIONS["visual"]}
    assert region_delta_e(_rgb8(art), _rgb8(python), regions)["visual"] <= 3
    diff = np.abs(art - python).max(axis=2)
    assert np.percentile(diff, 99.5) < 0.1  # same shapes, not only the same mean


def test_torch_moves_above_the_pole(theme: Any) -> None:
    art = library_for(theme).get("torch", theme.palette)
    assert art.moves
    ground = canvas_ground(theme)
    layer = ArtworkLayer("torch", 540, 1300, 2.0)
    zero = PHASE_DRAWERS[ArtworkLayer](ground.copy(), layer, _ctx(theme), 3, 0.0)
    later = PHASE_DRAWERS[ArtworkLayer](ground.copy(), layer, _ctx(theme), 3, 0.3)
    moved = np.abs(later - zero).max(axis=2) > 1 / 255
    assert moved.any()
    assert not moved[1300 - 2 * 100 :].any()  # the lower pole never moves
