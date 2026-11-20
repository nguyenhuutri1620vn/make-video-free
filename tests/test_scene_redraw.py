"""M10: scene layers redrawn at a loop phase (fire, smoke, cloth)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from helpers.phase import check_phase_drawer, draw_at, moved_box

from history_shorts.scene import PHASE_DRAWERS
from history_shorts.scene.furnace import draw_furnace_at
from history_shorts.scene_config import FurnaceLayer

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
