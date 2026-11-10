"""Eggshell-inlay clouds with a gold outline (FR-34, FR-36)."""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.compose import DrawContext, over
from history_shorts.config import CloudItem, CloudsLayer
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage

from .inlay import inlay_fill
from .registry import LayerDrawer, entry

OUTLINE_WIDTH: Final = 2.2  # divided by the item scale
CURL_WIDTH: Final = 1.6


def cloud_path(cv: Canvas, item: CloudItem) -> None:
    """Trace one cloud outline in canvas space; the caller fills or strokes it."""
    cv.save()
    cv.translate(item.x, item.y)
    cv.scale(item.scale * item.flip, item.scale)
    cv.M(-62, 0).C(-74, -18, -56, -36, -38, -27).C(-36, -48, -6, -54, 4, -35)
    cv.C(14, -52, 46, -48, 47, -27).C(64, -35, 80, -16, 66, 0).C(30, 6, -26, 6, -62, 0).Z()
    cv.restore()


def cloud_lines(cv: Canvas, item: CloudItem, color: tuple[int, int, int]) -> None:
    """Outline plus three inner curls for one cloud."""
    s = item.scale
    cv.save()
    cv.translate(item.x, item.y)
    cv.scale(s * item.flip, s)
    cv.color(color).M(-62, 0).C(-74, -18, -56, -36, -38, -27).C(-36, -48, -6, -54, 4, -35)
    cv.C(14, -52, 46, -48, 47, -27).C(64, -35, 80, -16, 66, 0).C(30, 6, -26, 6, -62, 0).Z()
    cv.stroke(OUTLINE_WIDTH / s)
    cv.color(color).M(-38, -27).C(-30, -22, -30, -12, -40, -10).stroke(CURL_WIDTH / s)
    cv.M(4, -35).C(10, -28, 8, -18, -2, -17).stroke(CURL_WIDTH / s)
    cv.M(47, -27).C(52, -20, 50, -12, 42, -11).stroke(CURL_WIDTH / s)
    cv.restore()


def draw_clouds(img: FloatImage, layer: CloudsLayer, ctx: DrawContext, index: int) -> FloatImage:
    """All clouds share one mask and one eggshell texture, then get their outlines."""

    def paint(cv: Canvas) -> None:
        for item in layer.items:
            cloud_path(cv, item)
            cv.fill()

    img = inlay_fill(img, ctx, index, paint, layer.cell, layer.gap)
    lines = Canvas(CANVAS_W, CANVAS_H)
    color = ctx.palette[layer.outline]
    for item in layer.items:
        cloud_lines(lines, item, color)
    return over(img, lines)


DRAWERS: dict[type, LayerDrawer] = dict([entry(CloudsLayer, draw_clouds)])
