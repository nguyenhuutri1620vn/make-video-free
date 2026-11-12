"""Scene layers: a registry from layer class to drawer, and the layer loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from history_shorts.compose import GROUND_LAYER, DrawContext
from history_shorts.config import Layer
from history_shorts.primitives import FloatImage

from . import (
    banners,
    boat,
    clouds,
    delta_map,
    drum,
    elephant,
    fallen_flags,
    gong,
    lotus,
    people,
    regalia,
    sail_boat,
    scroll,
    sky,
    stilt_house,
    temple,
    terrain,
)
from .registry import LayerDrawer, merge

__all__ = ["LAYER_DRAWERS", "LayerDrawer", "draw_layers"]

# Each layer module registers its own drawers; this read-only view is the single lookup table.
LAYER_DRAWERS: Mapping[type, LayerDrawer] = MappingProxyType(
    merge(
        sky.DRAWERS,
        clouds.DRAWERS,
        terrain.DRAWERS,
        boat.DRAWERS,
        lotus.DRAWERS,
        people.DRAWERS,
        drum.DRAWERS,
        gong.DRAWERS,
        temple.DRAWERS,
        delta_map.DRAWERS,
        scroll.DRAWERS,
        elephant.DRAWERS,
        stilt_house.DRAWERS,
        banners.DRAWERS,
        regalia.DRAWERS,
        fallen_flags.DRAWERS,
        sail_boat.DRAWERS,
    )
)


def draw_layers(img: FloatImage, layers: Sequence[Layer], ctx: DrawContext) -> FloatImage:
    """Draw ``layers`` in order. The k-th layer gets index k + 1: index 0 is the ground."""
    for k, layer in enumerate(layers):
        drawer = LAYER_DRAWERS.get(type(layer))
        if drawer is None:
            raise TypeError(f"no drawer registered for layer type {type(layer).__name__}")
        img = drawer(img, layer, ctx, k + GROUND_LAYER + 1)
    return img
