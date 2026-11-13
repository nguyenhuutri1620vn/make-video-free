"""Which plane (far, mid, near) each scene layer of a living slide belongs to."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

from history_shorts.config import Script, Slide, Theme
from history_shorts.errors import Issue
from history_shorts.scene.templates import expand
from history_shorts.scene_config import (
    PLANE_KEY,
    BambooVillageLayer,
    BannersLayer,
    BirdsLayer,
    BoatLayer,
    CharactersLayer,
    CitadelLayer,
    CloudsLayer,
    Depth,
    DrumLayer,
    ElephantLayer,
    FallenFlagsLayer,
    GongLayer,
    GroundLayer,
    HillsLayer,
    HorseLayer,
    LanternsLayer,
    Layer,
    LayerScene,
    LonePathLayer,
    LotusLayer,
    MapLayer,
    MountainsLayer,
    PeaksLayer,
    RegaliaLayer,
    RiverLayer,
    SailBoatLayer,
    ScrollLayer,
    StiltHouseLayer,
    SunLayer,
    TabletLayer,
    TempleLayer,
)

ORDER: Final[Mapping[str, int]] = MappingProxyType({"far": 0, "mid": 1, "near": 2})
LEVELS: Final[tuple[Depth, Depth, Depth]] = ("far", "mid", "near")

DEFAULT_DEPTH: Final[Mapping[type, Depth]] = MappingProxyType(
    {
        SunLayer: "far",
        CloudsLayer: "far",
        MountainsLayer: "far",
        PeaksLayer: "far",
        HillsLayer: "mid",
        RiverLayer: "mid",
        CitadelLayer: "mid",
        TempleLayer: "mid",
        BambooVillageLayer: "mid",
        StiltHouseLayer: "mid",
        MapLayer: "mid",
        BoatLayer: "mid",
        SailBoatLayer: "mid",
        ElephantLayer: "mid",
        HorseLayer: "mid",
        LonePathLayer: "mid",
        BannersLayer: "mid",
        BirdsLayer: "mid",
        GroundLayer: "near",
        CharactersLayer: "near",
        LotusLayer: "near",
        DrumLayer: "near",
        GongLayer: "near",
        ScrollLayer: "near",
        RegaliaLayer: "near",
        FallenFlagsLayer: "near",
        LanternsLayer: "near",
        TabletLayer: "near",
    }
)


def effective_depths(
    layers: Sequence[Layer], overrides: Sequence[Depth | None]
) -> tuple[tuple[Depth, ...], tuple[int, ...]]:
    """Each layer's plane, never nearer-to-farther down the list, so the living stack keeps
    the still slide's drawing order. Also returns the indices whose plane was raised."""
    depths: list[Depth] = []
    raised: list[int] = []
    floor = 0
    for index, layer in enumerate(layers):
        override = overrides[index] if index < len(overrides) else None
        wanted = override or DEFAULT_DEPTH[type(layer)]
        level = max(ORDER[wanted], floor)
        if level > ORDER[wanted]:
            raised.append(index)
        floor = level
        depths.append(LEVELS[level])
    return tuple(depths), tuple(raised)


def scene_layers(slide: Slide, theme: Theme) -> tuple[tuple[Layer, ...], tuple[Depth, ...]]:
    """A slide's scene layers (templates expanded) and their effective planes."""
    if slide.scene is None:
        return (), ()
    layers = expand(slide.scene, theme).layers
    overrides = slide.scene.depths if isinstance(slide.scene, LayerScene) else ()
    return layers, effective_depths(layers, overrides)[0]


def depth_warnings(script: Script) -> list[Issue]:
    """A warning for every layer of a living slide whose plane had to be raised (RF-3)."""
    issues: list[Issue] = []
    for index, slide in enumerate(script.slides):
        if not slide.living or not isinstance(slide.scene, LayerScene):
            continue
        layers = slide.scene.layers
        depths, raised = effective_depths(layers, slide.scene.depths)
        for k in raised:
            wanted = (slide.scene.depths[k] if k < len(slide.scene.depths) else None) or (
                DEFAULT_DEPTH[type(layers[k])]
            )
            where = f"slides[{index}].scene.layers[{k}].{PLANE_KEY}"
            message = f"plane raised from {wanted} to {depths[k]} to keep the drawing order"
            issues.append(Issue(script.path.name, where, message, "warning"))
    return issues
