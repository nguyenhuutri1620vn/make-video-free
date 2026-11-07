"""Thin typed wrapper over pycairo: transparent ARGB32 surface with a small path API."""

from __future__ import annotations

import math
from collections.abc import Sequence

import cairo
import numpy as np

from .primitives import RGB, FloatImage, FloatMask

DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920

ColorStop = tuple[float, RGB, float]


def _add_stops(pattern: cairo.Gradient, stops: Sequence[ColorStop]) -> None:
    for offset, (r, g, b), alpha in stops:
        pattern.add_color_stop_rgba(offset, r / 255, g / 255, b / 255, alpha)


class Canvas:
    """Transparent premultiplied ARGB32 canvas; path methods are chainable."""

    def __init__(self, w: int = DEFAULT_WIDTH, h: int = DEFAULT_HEIGHT) -> None:
        self.w = w
        self.h = h
        self._surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        self._cr = cairo.Context(self._surface)
        self._cr.set_line_cap(cairo.LINE_CAP_ROUND)
        self._cr.set_line_join(cairo.LINE_JOIN_ROUND)

    @property
    def surface(self) -> cairo.ImageSurface:
        """The backing surface (for tests and debugging only)."""
        return self._surface

    # state
    def save(self) -> None:
        self._cr.save()

    def restore(self) -> None:
        self._cr.restore()

    def translate(self, x: float, y: float) -> None:
        self._cr.translate(x, y)

    def scale(self, sx: float, sy: float) -> None:
        self._cr.scale(sx, sy)

    def rotate(self, angle: float) -> None:
        self._cr.rotate(angle)

    # paths
    def M(self, x: float, y: float) -> Canvas:
        self._cr.move_to(x, y)
        return self

    def L(self, x: float, y: float) -> Canvas:
        self._cr.line_to(x, y)
        return self

    def C(self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float) -> Canvas:
        self._cr.curve_to(x1, y1, x2, y2, x3, y3)
        return self

    def Z(self) -> Canvas:
        self._cr.close_path()
        return self

    def new_path(self) -> Canvas:
        self._cr.new_path()
        return self

    def ellipse(self, cx: float, cy: float, rx: float, ry: float) -> Canvas:
        self._cr.new_sub_path()
        self._cr.save()
        self._cr.translate(cx, cy)
        self._cr.scale(rx, ry)
        self._cr.arc(0, 0, 1, 0, 2 * math.pi)
        self._cr.restore()
        return self

    def rect(self, x: float, y: float, w: float, h: float) -> Canvas:
        return self.M(x, y).L(x + w, y).L(x + w, y + h).L(x, y + h).Z()

    # sources
    def color(self, rgb: RGB, alpha: float = 1.0) -> Canvas:
        r, g, b = rgb
        self._cr.set_source_rgba(r / 255, g / 255, b / 255, alpha)
        return self

    def vgrad(self, y0: float, y1: float, stops: Sequence[ColorStop]) -> Canvas:
        pattern = cairo.LinearGradient(0, y0, 0, y1)
        _add_stops(pattern, stops)
        self._cr.set_source(pattern)
        return self

    def rgrad(self, cx: float, cy: float, r: float, stops: Sequence[ColorStop]) -> Canvas:
        pattern = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
        _add_stops(pattern, stops)
        self._cr.set_source(pattern)
        return self

    # painting
    def fill(self, keep: bool = False) -> Canvas:
        if keep:
            self._cr.fill_preserve()
        else:
            self._cr.fill()
        return self

    def stroke(self, width: float, keep: bool = False) -> Canvas:
        self._cr.set_line_width(width)
        if keep:
            self._cr.stroke_preserve()
        else:
            self._cr.stroke()
        return self

    def clip(self) -> Canvas:
        self._cr.clip()
        return self

    # output
    def to_premul(self) -> tuple[FloatImage, FloatMask]:
        """Return (premultiplied RGB, alpha) as fresh float32 arrays in 0..1."""
        self._surface.flush()
        stride = self._surface.get_stride()
        raw = np.frombuffer(self._surface.get_data(), dtype=np.uint8).copy()
        bgra = raw.reshape(self.h, stride // 4, 4)[:, : self.w]
        arr = bgra.astype(np.float32) / 255
        rgb: FloatImage = np.ascontiguousarray(arr[..., [2, 1, 0]])
        alpha: FloatMask = np.ascontiguousarray(arr[..., 3])
        return rgb, alpha

    def mask(self) -> FloatMask:
        return self.to_premul()[1]
