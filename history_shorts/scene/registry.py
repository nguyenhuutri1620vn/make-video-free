"""The layer drawer signature and the helper that adapts typed drawers to it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

from history_shorts.compose import DrawContext
from history_shorts.config import Layer
from history_shorts.primitives import FloatImage

# (image, layer, context, layer index) -> image. The index feeds the RNG derivation.
LayerDrawer = Callable[[FloatImage, Layer, DrawContext, int], FloatImage]

L = TypeVar("L")


def as_drawer(fn: Callable[[FloatImage, L, DrawContext, int], FloatImage]) -> LayerDrawer:
    """View a drawer typed for one layer class as a ``LayerDrawer``.

    Safe because ``draw_layers`` dispatches on the exact layer class before calling.
    """
    return cast(Callable[[FloatImage, Any, DrawContext, int], FloatImage], fn)
