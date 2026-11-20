"""2-D affine transforms for jointed figures (M10), in Cairo's convention.

``Affine(xx, yx, xy, yy, x0, y0)`` maps ``(x, y)`` to ``(xx*x + xy*y + x0, yx*x + yy*y + y0)``,
like ``cairo.Matrix``. ``a @ b`` applies ``b`` first, then ``a`` — the order in which Cairo
applies ``translate``/``rotate`` calls made one after another.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.primitives import Point


@dataclass(frozen=True, slots=True)
class Affine:
    xx: float = 1.0
    yx: float = 0.0
    xy: float = 0.0
    yy: float = 1.0
    x0: float = 0.0
    y0: float = 0.0

    def apply(self, point: Point) -> Point:
        x, y = point
        return (self.xx * x + self.xy * y + self.x0, self.yx * x + self.yy * y + self.y0)

    def __matmul__(self, inner: Affine) -> Affine:
        return Affine(
            self.xx * inner.xx + self.xy * inner.yx,
            self.yx * inner.xx + self.yy * inner.yx,
            self.xx * inner.xy + self.xy * inner.yy,
            self.yx * inner.xy + self.yy * inner.yy,
            self.xx * inner.x0 + self.xy * inner.y0 + self.x0,
            self.yx * inner.x0 + self.yy * inner.y0 + self.y0,
        )


IDENTITY: Final = Affine()


def translate(dx: float, dy: float) -> Affine:
    return Affine(x0=dx, y0=dy)


def rotate(degrees: float) -> Affine:
    """Cairo ``rotate``: positive turns +x toward +y (clockwise on screen)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return Affine(c, s, -s, c)


def scale(sx: float, sy: float) -> Affine:
    return Affine(sx, 0.0, 0.0, sy)


def about(pivot: Point, m: Affine) -> Affine:
    """``m`` applied around ``pivot`` instead of the origin."""
    px, py = pivot
    return translate(px, py) @ m @ translate(-px, -py)


def apply_to(cv: Canvas, m: Affine) -> None:
    """Multiply the canvas's current transform by ``m``."""
    if m != IDENTITY:
        cv.transform(m.xx, m.yx, m.xy, m.yy, m.x0, m.y0)
