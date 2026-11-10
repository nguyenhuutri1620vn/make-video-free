"""Small shared types: colours, points, float images, and boxes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

RGB = tuple[int, int, int]
Point = tuple[float, float]
FloatImage = npt.NDArray[np.float32]
FloatMask = npt.NDArray[np.float32]


@dataclass(frozen=True, slots=True)
class Box:
    """Axis-aligned box in canvas pixels; x1 and y1 are exclusive edges."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def intersects(self, other: Box) -> bool:
        """True when the interiors overlap; touching edges do not count."""
        return (
            self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1
        )

    def inside(self, other: Box) -> bool:
        """True when this box lies fully within ``other`` (edges may touch)."""
        return (
            self.x0 >= other.x0
            and self.y0 >= other.y0
            and self.x1 <= other.x1
            and self.y1 <= other.y1
        )

    def union(self, other: Box) -> Box:
        return Box(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )
