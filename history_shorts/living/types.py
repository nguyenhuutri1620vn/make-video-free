"""Array and plane types shared by the living-slide modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from history_shorts.scene_config import Depth

FloatRGBA = NDArray[np.float32]  # (h, w, 4): premultiplied RGB, then alpha


@dataclass(frozen=True)
class ScenePlane:
    """Consecutive still scene layers of one depth; the first plane (ground) is opaque."""

    depth: Depth
    rgba: FloatRGBA
    layer_indices: tuple[int, ...]
    opaque: bool = False


@dataclass(frozen=True)
class DriftPlane:
    """A full-canvas layer that slides steadily (clouds, birds): ``velocity`` in px/s."""

    depth: Depth
    rgba: FloatRGBA
    velocity: tuple[float, float]
    layer_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class SpritePlane:
    """A looping animated crop at ``origin`` (x, y, canvas px); ``frames`` per loop.

    ``render(p)`` draws the crop at loop phase ``p`` in 0…1 (``render(1) == render(0)``)."""

    depth: Depth
    origin: tuple[int, int]
    size: tuple[int, int]  # (h, w) of every frame
    frames: int
    render: Callable[[float], FloatRGBA]
    layer_indices: tuple[int, ...] = ()

    def frame(self, p: float) -> FloatRGBA:
        return self.render(p)


AnyPlane = ScenePlane | DriftPlane | SpritePlane
