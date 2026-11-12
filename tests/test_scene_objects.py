"""Scene layers without people from the visual backlog (docs/visual_backlog.md, spec 6.3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.config import DrumLayer, load_script
from history_shorts.errors import ValidationFailed
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.drum import draw_drum

Base = Callable[[], FloatImage]
ScriptFactory = Callable[..., Path]


def _layer(tmp_script: ScriptFactory, layer: dict[str, Any]) -> Any:
    path = tmp_script(slides=[{"title": "A", "scene": {"layers": [layer]}}])
    return load_script(path)[0].slides[0].scene.layers[0]


def _changed(before: FloatImage, after: FloatImage) -> tuple[Any, Any]:
    return np.nonzero(np.any(after != before, axis=-1))


# --- drum (backlog #1) --------------------------------------------------------------------


def test_drum_parses_with_defaults(tmp_script: ScriptFactory) -> None:
    layer = _layer(tmp_script, {"type": "drum", "x": 540, "y": 700, "r": 300})
    assert layer == DrumLayer(540, 700, 300)
    assert LAYER_DRAWERS[DrumLayer] is draw_drum


def test_drum_bird_count_is_limited(tmp_script: ScriptFactory) -> None:
    with pytest.raises(ValidationFailed):
        _layer(tmp_script, {"type": "drum", "x": 540, "y": 700, "r": 300, "birds": 40})


def test_drum_stays_inside_its_face(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    after = draw_drum(base.copy(), DrumLayer(540, 800, 200), ctx, 1)
    ys, xs = _changed(base, after)
    assert xs.size > 100_000
    radius = np.hypot(xs - 540, ys - 800)
    assert radius.max() <= 200 + 3  # rim ring: half its stroke plus antialiasing


def test_drum_is_deterministic_and_counts_birds(ctx: Any, flat_base: Base) -> None:
    layer = DrumLayer(540, 800, 200)
    a = draw_drum(flat_base(), layer, ctx, 1)
    assert np.array_equal(a, draw_drum(flat_base(), layer, ctx, 1))
    assert not np.array_equal(a, draw_drum(flat_base(), DrumLayer(540, 800, 200, 4), ctx, 1))
