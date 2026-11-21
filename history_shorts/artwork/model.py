"""Parsed artwork files (M11): frozen records the drawer and motion code read."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from history_shorts.artwork.path import Op
from history_shorts.scene_config import Depth

MotionKind = Literal["flicker", "wave", "sway", "rise", "pulse"]
TextureKind = Literal["gold_leaf", "eggshell"]


@dataclass(frozen=True, slots=True)
class Solid:
    color: str
    alpha: float = 1.0


@dataclass(frozen=True, slots=True)
class Gradient:
    """Stops (palette key, alpha, offset); linear along ``direction`` over the part's bounds,
    or radial around ``radial`` (cx, cy, r) in artwork units."""

    stops: tuple[tuple[str, float, float], ...]
    direction: Literal["v", "h"] | None = "v"
    radial: tuple[float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class Texture:
    """Gold leaf or eggshell inside the part; sizes in artwork units (None: theme value)."""

    kind: TextureKind
    tile: float | None = None
    worn: float | None = None
    cell: float | None = None
    gap: float | None = None


Fill = Solid | Gradient | Texture


@dataclass(frozen=True, slots=True)
class Stroke:
    color: str
    width: float
    alpha: float = 1.0


@dataclass(frozen=True, slots=True)
class Motion:
    kind: MotionKind
    amp: float = 0.0
    deg: float = 0.0
    pole: float = 0.0
    pivot: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True, slots=True)
class Part:
    id: str
    ops: tuple[Op, ...]
    fill: Fill | None = None
    stroke: Stroke | None = None
    alpha: float = 1.0
    clip: str | None = None
    motion: Motion | None = None


@dataclass(frozen=True, slots=True)
class Artwork:
    name: str
    title: str
    plane: Depth
    parts: tuple[Part, ...]

    @property
    def moves(self) -> bool:
        return any(part.motion is not None for part in self.parts)

    def part(self, part_id: str) -> Part:
        return next(p for p in self.parts if p.id == part_id)
