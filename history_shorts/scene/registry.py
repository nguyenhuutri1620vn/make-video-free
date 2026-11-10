"""The layer drawer signature and the helpers that build the registry table."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Final, TypeVar, cast

from history_shorts.compose import DrawContext
from history_shorts.config import Layer
from history_shorts.primitives import FloatImage

# (image, layer, context, layer index) -> image. The index feeds the RNG derivation.
LayerDrawer = Callable[[FloatImage, Layer, DrawContext, int], FloatImage]

L = TypeVar("L")

WHITE: Final = (255, 255, 255)  # mask colour: only the alpha channel of a mask canvas is used


def entry(
    layer_type: type[L], fn: Callable[[FloatImage, L, DrawContext, int], FloatImage]
) -> tuple[type, LayerDrawer]:
    """Pair a layer class with its drawer; mypy checks that the drawer takes that class.

    Safe to widen the drawer to ``LayerDrawer`` because ``draw_layers`` dispatches on the
    exact layer class before calling.
    """
    return layer_type, cast(Callable[[FloatImage, Any, DrawContext, int], FloatImage], fn)


def merge(*tables: Mapping[type, LayerDrawer]) -> dict[type, LayerDrawer]:
    """Combine drawer tables; two modules claiming one layer class is a bug."""
    merged: dict[type, LayerDrawer] = {}
    for table in tables:
        for layer_type, drawer in table.items():
            if layer_type in merged:
                raise ValueError(f"layer type {layer_type.__name__} has more than one drawer")
            merged[layer_type] = drawer
    return merged
