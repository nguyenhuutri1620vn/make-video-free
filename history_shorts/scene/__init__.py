"""Scene layers: a registry from layer class to drawer, and the layer loop."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from history_shorts.compose import GROUND_LAYER, DrawContext
from history_shorts.config import BoatLayer, CharactersLayer, Layer, LivingSpec
from history_shorts.primitives import FloatImage

from . import (
    artwork,
    bamboo_village,
    banners,
    boat,
    citadel,
    clouds,
    delta_map,
    drum,
    elephant,
    fallen_flags,
    furnace,
    gong,
    horse,
    lanterns,
    lone_path,
    lotus,
    people,
    plinth,
    regalia,
    sail_boat,
    scroll,
    sky,
    stilt_house,
    tablet,
    temple,
    terrain,
)
from .registry import LayerDrawer, PhaseDrawer, merge

__all__ = [
    "LAYER_DRAWERS",
    "PHASE_DRAWERS",
    "LayerDrawer",
    "PhaseDrawer",
    "draw_layers",
    "phase_loop_seconds",
    "redraws",
]

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
        lone_path.DRAWERS,
        lanterns.DRAWERS,
        tablet.DRAWERS,
        horse.DRAWERS,
        citadel.DRAWERS,
        bamboo_village.DRAWERS,
        furnace.DRAWERS,
        plinth.DRAWERS,
        artwork.DRAWERS,
    )
)


# Layers that move on 2.3 living slides by being redrawn at a loop phase (M10).
PHASE_DRAWERS: Mapping[type, PhaseDrawer] = MappingProxyType(
    merge(
        furnace.PHASE_DRAWERS,
        temple.PHASE_DRAWERS,
        banners.PHASE_DRAWERS,
        elephant.PHASE_DRAWERS,
        people.PHASE_DRAWERS,
        boat.PHASE_DRAWERS,
    )
)
# Layers whose loop is a character's idle breath rather than the ambient loop.
IDLE_LOOP_LAYERS: frozenset[type] = frozenset({CharactersLayer, BoatLayer})


def redraws(layer: Layer) -> bool:
    """Whether a 2.3 living slide redraws ``layer`` per frame (a crewless boat only bobs)."""
    if isinstance(layer, BoatLayer):
        return bool(layer.crew)
    return type(layer) in PHASE_DRAWERS


def phase_loop_seconds(layer: Layer, spec: LivingSpec) -> float:
    """Length of ``layer``'s redrawn loop."""
    return spec.idle_loop_seconds if type(layer) in IDLE_LOOP_LAYERS else spec.loop_seconds


def draw_layers(img: FloatImage, layers: Sequence[Layer], ctx: DrawContext) -> FloatImage:
    """Draw ``layers`` in order. The k-th layer gets index k + 1: index 0 is the ground."""
    for k, layer in enumerate(layers):
        drawer = LAYER_DRAWERS.get(type(layer))
        if drawer is None:
            raise TypeError(f"no drawer registered for layer type {type(layer).__name__}")
        img = drawer(img, layer, ctx, k + GROUND_LAYER + 1)
    return img
