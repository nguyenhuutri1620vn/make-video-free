"""Scene templates: ``group`` and ``landscape`` expand to the reference layers (FR-30 to FR-34).

A template is a short scene spec such as ``{"template": "group"}``. ``expand`` turns it into
the exact layers and scene style that reproduce the owner-approved reference image; whatever
the spec leaves open takes the reference value (FR-33). The numbers below come from the
prototype scenes ``scene1.py`` (group) and ``scene3.py`` (landscape). A new template is a new
entry in ``TEMPLATES``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from history_shorts.compose import SceneStyle, default_style
from history_shorts.config import (
    BirdItem,
    BirdsLayer,
    BoatLayer,
    CharactersLayer,
    CharacterSpec,
    CloudItem,
    CloudsLayer,
    GroundLayer,
    HillsLayer,
    Layer,
    LayerScene,
    MountainsLayer,
    PeakItem,
    PeaksLayer,
    RiverLayer,
    SheenSpec,
    SunLayer,
    TemplateScene,
    Theme,
)

# -- group (scene1.py) ----------------------------------------------------------------------
GROUP_SUN: Final = SunLayer(kind="sun", x=540, y=650, r=300, rings=2, tile=34, worn=0.05)
GROUP_CLOUDS: Final = CloudsLayer(
    items=(CloudItem(270, 318, 0.8, 1), CloudItem(860, 318, 0.8, -1)),
    outline="gold",
    cell=12,
    gap=0.9,
)
GROUP_MOUNTAINS: Final = MountainsLayer(y=900, amp=1.0)
GROUP_HILL_LEFT: Final = HillsLayer(side="left", base=1100, top=880, cell=16, gap=1.0)
GROUP_HILL_RIGHT: Final = HillsLayer(side="right", base=1100, top=900, cell=16, gap=1.0)
GROUP_GROUND: Final = GroundLayer(y=1092, height=52)
GROUP_FORMATION: Final = "centre_pair"
GROUP_BASELINE: Final = 1100.0
# front tier first, as the centre_pair formation expects (leaders, then generals, then outer)
GROUP_ROLES: Final = ("leader", "leader", "general_alt", "general_alt", "general", "general")
GROUP_CHARACTERS: Final = tuple(CharacterSpec(role=role) for role in GROUP_ROLES)
GROUP_GROUND_COLORS: Final = ("black", "deep", "black")
GROUP_SHEEN: Final = SheenSpec(x=360, y=700, r=640, strength=0.10)

# -- landscape (scene3.py) --------------------------------------------------------------------
LANDSCAPE_MOON: Final = SunLayer(kind="moon", x=770, y=450, r=125, rings=1, tile=26, worn=0.03)
LANDSCAPE_BIRDS: Final = BirdsLayer(
    items=(
        BirdItem(300, 400, 1.6),
        BirdItem(360, 440, 1.2),
        BirdItem(250, 470, 1.0),
        BirdItem(420, 380, 0.9),
    )
)
# farthest (tallest) first; terrain shades them by index
LANDSCAPE_BACK_PEAKS: Final = PeaksLayer(
    y=900,
    items=(
        PeakItem(470, 380, 120),
        PeakItem(860, 360, 130),
        PeakItem(120, 330, 120),
        PeakItem(660, 290, 115),
        PeakItem(300, 250, 105),
        PeakItem(1030, 260, 100),
    ),
    fill="gradient",
    cell=None,
    gap=None,
)
LANDSCAPE_CLOUDS: Final = CloudsLayer(
    items=(CloudItem(230, 720, 1.1, 1), CloudItem(640, 650, 0.9, -1), CloudItem(960, 760, 0.8, 1)),
    outline="gold_dk",
    cell=11,
    gap=1.0,
)
LANDSCAPE_MID_PEAKS: Final = PeaksLayer(
    y=945,
    items=(PeakItem(80, 200, 140), PeakItem(400, 150, 150), PeakItem(990, 220, 160)),
    fill="eggshell",
    cell=15,
    gap=1.0,
)
LANDSCAPE_RIVER: Final = RiverLayer(y=940, height=290)
# Crew positions are explicit so they match the prototype exactly (not the boat slots).
LANDSCAPE_BOATS: Final = (
    BoatLayer(
        x=290,
        y=1056,
        scale=1.5,
        crew=(
            CharacterSpec("leader", facing=1, x=300, baseline=1048, height=150),
            CharacterSpec("boat_crew", facing=-1, x=250, baseline=1050, height=120),
        ),
    ),
    BoatLayer(
        x=780,
        y=1104,
        scale=1.25,
        crew=(
            CharacterSpec("general", facing=1, x=760, baseline=1098, height=125),
            CharacterSpec("boat_crew", facing=1, x=815, baseline=1100, height=110),
        ),
    ),
)
LANDSCAPE_GROUND_COLORS: Final = ("black", "deep_warm", "black")
# The owner chose a template sheen of 0.08 (FR-63 amended): the template carries it.
LANDSCAPE_SHEEN: Final = SheenSpec(x=700, y=520, r=520, strength=0.08)


@dataclass(frozen=True, slots=True)
class ExpandedScene:
    """The layers to draw, back to front, and the scene style."""

    layers: tuple[Layer, ...]
    style: SceneStyle


def _style(
    ground: tuple[str, str, str], sheen: SheenSpec, scene: TemplateScene, theme: Theme
) -> SceneStyle:
    return SceneStyle(ground, sheen, theme.seed if scene.seed is None else scene.seed)


def expand_group(scene: TemplateScene, theme: Theme) -> ExpandedScene:
    characters = GROUP_CHARACTERS if scene.characters is None else scene.characters
    layers: list[Layer] = [GROUP_SUN] if scene.sun else []
    layers += [
        GROUP_CLOUDS,
        GROUP_MOUNTAINS,
        GROUP_HILL_LEFT,
        GROUP_HILL_RIGHT,
        GROUP_GROUND,
        CharactersLayer(GROUP_FORMATION, GROUP_BASELINE, characters),
    ]
    return ExpandedScene(tuple(layers), _style(GROUP_GROUND_COLORS, GROUP_SHEEN, scene, theme))


def expand_landscape(scene: TemplateScene, theme: Theme) -> ExpandedScene:
    boats = LANDSCAPE_BOATS if scene.boats is None else scene.boats
    layers: list[Layer] = [LANDSCAPE_MOON] if scene.moon else []
    layers += [
        LANDSCAPE_BIRDS,
        LANDSCAPE_BACK_PEAKS,
        LANDSCAPE_CLOUDS,
        LANDSCAPE_MID_PEAKS,
        LANDSCAPE_RIVER,
        *boats,
    ]
    return ExpandedScene(
        tuple(layers), _style(LANDSCAPE_GROUND_COLORS, LANDSCAPE_SHEEN, scene, theme)
    )


TEMPLATES: Mapping[str, Callable[[TemplateScene, Theme], ExpandedScene]] = MappingProxyType(
    {"group": expand_group, "landscape": expand_landscape}
)


def expand(scene: TemplateScene | LayerScene, theme: Theme) -> ExpandedScene:
    """Expand a slide's scene into layers and style; a layer scene keeps its own layers."""
    if isinstance(scene, LayerScene):
        return ExpandedScene(scene.layers, default_style(theme))
    return TEMPLATES[scene.template](scene, theme)
