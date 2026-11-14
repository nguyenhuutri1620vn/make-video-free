"""Array and plane types shared by the living-slide modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from history_shorts.scene_config import Depth
from history_shorts.textures import ToneMatrix

FloatRGBA = NDArray[np.float32]  # (h, w, 4): premultiplied RGB, then alpha
SHEEN_PNG_GAIN = 4  # sheen is ≤ 0.10, so it is stored ×4 for 8-bit precision; FFmpeg divides


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


@dataclass(frozen=True, slots=True)
class PlaneFile:
    """One scene plane on disk. ``path`` is a PNG, or a frame of a sprite whose frames are
    ``path.parent/%03d.png``. ``pad`` (px, py) is the edge padding of the plane's depth;
    ``size`` (h, w) the image size; ``origin`` the sprite's top-left in padded pixels."""

    kind: Literal["static", "drift", "sprite"]
    depth: Depth
    path: Path
    frames: int
    origin: tuple[int, int]
    velocity: tuple[float, float]
    pad: tuple[int, int]
    size: tuple[int, int]


@dataclass(frozen=True, slots=True)
class LivingClip:
    planes: tuple[PlaneFile, ...]
    waves: Path
    sheen: Path
    chrome: Path
    text: Path | None
    shakes: tuple[float, ...]
    frame: Path | None = None  # the gold frame, overlaid before the tone
    tone: ToneMatrix | None = None  # applied once to the composite, as on the still
