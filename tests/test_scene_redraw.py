"""M10: scene layers redrawn at a loop phase (fire, smoke, cloth)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from helpers.phase import check_phase_drawer, draw_at, moved_box

from history_shorts.scene import PHASE_DRAWERS
from history_shorts.scene.furnace import draw_furnace_at
from history_shorts.scene.temple import draw_temple_at
from history_shorts.scene_config import BannersLayer, ElephantLayer, FurnaceLayer, TempleLayer

FURNACE = FurnaceLayer(540, 1300, 1.4)


def test_furnace_registered() -> None:
    assert PHASE_DRAWERS[FurnaceLayer] is draw_furnace_at


def test_furnace_phase_drawer(flat_base: Callable[[], Any], ctx: Any) -> None:
    check_phase_drawer(flat_base(), FURNACE, ctx)


def test_furnace_flames_move_kiln_still(flat_base: Callable[[], Any], ctx: Any) -> None:
    base = flat_base()
    box = moved_box(draw_at(base, FURNACE, ctx, 0.0), draw_at(base, FURNACE, ctx, 0.25))
    assert box is not None
    # the brick wall between the rim and the mouth is drawn the same at every phase
    rim_y = int(FURNACE.y + FURNACE.scale * -272) + 20
    mouth_y = int(FURNACE.y + FURNACE.scale * -150)
    kiln = draw_at(base, FURNACE, ctx, 0.0)[rim_y:mouth_y, 470:610]
    moved = draw_at(base, FURNACE, ctx, 0.4)[rim_y:mouth_y, 470:610]
    assert (abs(kiln - moved) <= 1 / 255).all()


TEMPLE = TempleLayer(540, 1200, 1.5, True)


def test_temple_registered() -> None:
    assert PHASE_DRAWERS[TempleLayer] is draw_temple_at


def test_temple_phase_drawer(flat_base: Callable[[], Any], ctx: Any) -> None:
    check_phase_drawer(flat_base(), TEMPLE, ctx)


def test_temple_only_smoke_moves(flat_base: Callable[[], Any], ctx: Any) -> None:
    base = flat_base()
    box = moved_box(draw_at(base, TEMPLE, ctx, 0.0), draw_at(base, TEMPLE, ctx, 0.3))
    assert box is not None
    burner_top = TEMPLE.y + TEMPLE.scale * -34
    assert box[3] <= burner_top + 3  # nothing below the incense sticks moves


def test_temple_without_incense_is_still(flat_base: Callable[[], Any], ctx: Any) -> None:
    bare = TempleLayer(540, 1200, 1.5, False)
    base = flat_base()
    assert moved_box(draw_at(base, bare, ctx, 0.0), draw_at(base, bare, ctx, 0.3)) is None


BANNERS = BannersLayer(1250, 3)
ELEPHANT = ElephantLayer(540, 1250, 1.6, 1, True)


@pytest.mark.parametrize("layer", [BANNERS, ELEPHANT])
def test_cloth_layers_phase_drawer(layer: Any, flat_base: Callable[[], Any], ctx: Any) -> None:
    check_phase_drawer(flat_base(), layer, ctx)
    base = flat_base()
    assert moved_box(draw_at(base, layer, ctx, 0.0), draw_at(base, layer, ctx, 0.3)) is not None


def test_elephant_body_still(flat_base: Callable[[], Any], ctx: Any) -> None:
    base = flat_base()
    box = moved_box(draw_at(base, ELEPHANT, ctx, 0.0), draw_at(base, ELEPHANT, ctx, 0.3))
    assert box is not None
    pole_bottom = ELEPHANT.y + ELEPHANT.scale * -160
    assert box[3] <= pole_bottom  # only the flag, high above the saddle, moves


def test_elephant_without_flag_is_still(flat_base: Callable[[], Any], ctx: Any) -> None:
    bare = ElephantLayer(540, 1250, 1.6, 1, False)
    base = flat_base()
    assert moved_box(draw_at(base, bare, ctx, 0.0), draw_at(base, bare, ctx, 0.3)) is None
