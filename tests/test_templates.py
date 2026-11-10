"""Scene templates: group and landscape expansion (FR-30 to FR-34, FR-63)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts.checks import check_all
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
    LayerScene,
    MountainsLayer,
    PeakItem,
    PeaksLayer,
    RiverLayer,
    SheenSpec,
    SunLayer,
    TemplateScene,
    Theme,
    load_script,
)
from history_shorts.errors import Issue
from history_shorts.scene import LAYER_DRAWERS, boat, clouds, lotus, people, sky, terrain
from history_shorts.scene.boat import BOAT_CREW_SLOTS, crew_placements
from history_shorts.scene.templates import TEMPLATES, ExpandedScene, expand
from history_shorts.scene_config import LAYER_TYPES, LotusLayer

REF_ROLES = ["leader", "leader", "general_alt", "general_alt", "general", "general"]
BACK_PEAKS = tuple(
    PeakItem(x, h, w)
    for x, h, w in [
        (470, 380, 120),
        (860, 360, 130),
        (120, 330, 120),
        (660, 290, 115),
        (300, 250, 105),
        (1030, 260, 100),
    ]
)


def group(**kw: Any) -> TemplateScene:
    return TemplateScene("group", kw.pop("characters", None), kw.pop("boats", None), **kw)


def landscape(**kw: Any) -> TemplateScene:
    return TemplateScene("landscape", kw.pop("characters", None), kw.pop("boats", None), **kw)


def kinds(ex: ExpandedScene) -> list[str]:
    return [type(layer).__name__ for layer in ex.layers]


# --------------------------------------------------------------------------------------
# group
# --------------------------------------------------------------------------------------


def test_group_reference_expansion(theme: Theme) -> None:
    ex = expand(group(), theme)
    assert kinds(ex) == [
        "SunLayer",
        "CloudsLayer",
        "MountainsLayer",
        "HillsLayer",
        "HillsLayer",
        "GroundLayer",
        "CharactersLayer",
    ]
    assert ex.layers[0] == SunLayer("sun", 540, 650, 300, 2, 34, 0.05)
    assert ex.layers[1] == CloudsLayer(
        (CloudItem(270, 318, 0.8, 1), CloudItem(860, 318, 0.8, -1)), "gold", 12, 0.9
    )
    assert ex.layers[2] == MountainsLayer(900, 1.0)
    assert ex.layers[3] == HillsLayer("left", 1100, 880, 16, 1.0)
    assert ex.layers[4] == HillsLayer("right", 1100, 900, 16, 1.0)
    assert ex.layers[5] == GroundLayer(1092, 52)
    chars = ex.layers[6]
    assert isinstance(chars, CharactersLayer)
    assert chars.formation == "centre_pair" and chars.baseline == 1100
    assert [c.role for c in chars.items] == REF_ROLES
    assert ex.style.sheen == SheenSpec(360, 700, 640, 0.10)
    assert ex.style.ground == ("black", "deep", "black")
    assert ex.style.seed == theme.seed


# --------------------------------------------------------------------------------------
# landscape
# --------------------------------------------------------------------------------------


def test_landscape_reference_expansion(theme: Theme) -> None:
    ex = expand(landscape(), theme)
    assert kinds(ex) == [
        "SunLayer",
        "BirdsLayer",
        "PeaksLayer",
        "CloudsLayer",
        "PeaksLayer",
        "RiverLayer",
        "BoatLayer",
        "BoatLayer",
    ]
    assert ex.layers[0] == SunLayer("moon", 770, 450, 125, 1, 26, 0.03)
    assert ex.layers[1] == BirdsLayer(
        (
            BirdItem(300, 400, 1.6),
            BirdItem(360, 440, 1.2),
            BirdItem(250, 470, 1.0),
            BirdItem(420, 380, 0.9),
        )
    )
    assert ex.layers[2] == PeaksLayer(900, BACK_PEAKS, "gradient", None, None)
    assert ex.layers[3] == CloudsLayer(
        (CloudItem(230, 720, 1.1, 1), CloudItem(640, 650, 0.9, -1), CloudItem(960, 760, 0.8, 1)),
        "gold_dk",
        11,
        1.0,
    )
    assert ex.layers[4] == PeaksLayer(
        945,
        (PeakItem(80, 200, 140), PeakItem(400, 150, 150), PeakItem(990, 220, 160)),
        "eggshell",
        15,
        1.0,
    )
    assert ex.layers[5] == RiverLayer(940, 290)
    assert ex.style.sheen == SheenSpec(700, 520, 520, 0.08)
    assert ex.style.ground == ("black", "deep_warm", "black")


def test_landscape_reference_boats_match_the_prototype(theme: Theme) -> None:
    ex = expand(landscape(), theme)
    boats = [layer for layer in ex.layers if isinstance(layer, BoatLayer)]
    assert [(b.x, b.y, b.scale) for b in boats] == [(290, 1056, 1.5), (780, 1104, 1.25)]
    placed = [
        [
            (
                p.spec.role,
                p.placement.x,
                p.placement.baseline,
                p.placement.height,
                p.placement.facing,
            )
            for p in crew_placements(b)
        ]
        for b in boats
    ]
    assert placed == [
        [("leader", 300, 1048, 150, 1), ("boat_crew", 250, 1050, 120, -1)],
        [("general", 760, 1098, 125, 1), ("boat_crew", 815, 1100, 110, 1)],
    ]


def test_landscape_boat_without_crew_coordinates_uses_slots(theme: Theme) -> None:
    boat_layer = BoatLayer(500, 1000, 2.0, (CharacterSpec("leader"), CharacterSpec("boat_crew")))
    ex = expand(landscape(boats=(boat_layer,)), theme)
    boats = [layer for layer in ex.layers if isinstance(layer, BoatLayer)]
    assert boats == [boat_layer]
    placed = crew_placements(boats[0])
    for member, slot in zip(placed, BOAT_CREW_SLOTS, strict=True):
        assert member.placement.x == 500 + slot.dx * 2.0
        assert member.placement.baseline == 1000 + slot.dy * 2.0
        assert member.placement.height == slot.height * 2.0


# --------------------------------------------------------------------------------------
# parameters
# --------------------------------------------------------------------------------------


def test_template_params(theme: Theme) -> None:
    assert "SunLayer" not in kinds(expand(group(sun=False), theme))
    assert kinds(expand(group(sun=False), theme)) == kinds(expand(group(), theme))[1:]
    assert "SunLayer" not in kinds(expand(landscape(moon=False), theme))
    no_boats = expand(landscape(boats=()), theme)
    assert "BoatLayer" not in kinds(no_boats)
    assert kinds(no_boats)[-1] == "RiverLayer"
    two = expand(group(characters=(CharacterSpec("leader"), CharacterSpec("general"))), theme)
    last = two.layers[-1]
    assert isinstance(last, CharactersLayer)
    assert last.formation == "centre_pair" and last.baseline == 1100
    assert [c.role for c in last.items] == ["leader", "general"]
    assert expand(group(seed=7), theme).style.seed == 7
    assert expand(landscape(seed=0), theme).style.seed == 0


def test_expansion_is_deterministic(theme: Theme) -> None:
    for scene in (group(), landscape(), group(sun=False, seed=3)):
        assert expand(scene, theme) == expand(scene, theme)


def test_seed_changes_style_not_layers(theme: Theme) -> None:
    for make in (group, landscape):
        base, seeded = expand(make(), theme), expand(make(seed=7), theme)
        assert seeded.layers == base.layers
        assert seeded.style == dataclasses.replace(base.style, seed=7)
        assert seeded.style.seed != base.style.seed


def test_group_with_two_characters_keeps_other_layers(theme: Theme) -> None:
    full = expand(group(), theme)
    two = expand(group(characters=(CharacterSpec("leader"), CharacterSpec("general"))), theme)
    assert two.layers[:-1] == full.layers[:-1]
    assert two.style == full.style


def test_layer_scene_gets_default_style(theme: Theme) -> None:
    layers = (GroundLayer(1092), LotusLayer(540, 1500, 1.0))
    ex = expand(LayerScene(layers), theme)
    assert ex.layers == layers
    assert ex.style == default_style(theme)
    assert isinstance(ex.style, SceneStyle)


def test_expanded_scene_is_frozen_and_registry_is_read_only(theme: Theme) -> None:
    ex = expand(group(), theme)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ex.layers = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        TEMPLATES["x"] = lambda scene, th: ex  # type: ignore[index]
    assert set(TEMPLATES) == {"group", "landscape"}


def test_template_registry_covers_template_names() -> None:
    from history_shorts.scene_config import TEMPLATE_NAMES

    assert set(TEMPLATES) == set(TEMPLATE_NAMES)


# --------------------------------------------------------------------------------------
# registry completeness
# --------------------------------------------------------------------------------------


def test_every_layer_type_has_a_drawer() -> None:
    assert set(LAYER_DRAWERS) == set(LAYER_TYPES.values())


def test_every_layer_class_has_its_intended_drawer() -> None:
    expected = {
        SunLayer: sky.draw_sun,
        BirdsLayer: sky.draw_birds,
        CloudsLayer: clouds.draw_clouds,
        MountainsLayer: terrain.draw_mountains,
        PeaksLayer: terrain.draw_peaks,
        HillsLayer: terrain.draw_hills,
        RiverLayer: terrain.draw_river,
        GroundLayer: terrain.draw_ground,
        BoatLayer: boat.draw_boat,
        LotusLayer: lotus.draw_lotus,
        CharactersLayer: people.draw_characters,
    }
    assert len(expected) == 11
    for layer_class, drawer in expected.items():
        assert LAYER_DRAWERS[layer_class] is drawer


# --------------------------------------------------------------------------------------
# validation of template characters (FR-47) goes through check_all
# --------------------------------------------------------------------------------------


def _template_issues(
    tmp_script: Callable[..., Path], theme: Theme, scene: dict[str, Any]
) -> list[Issue]:
    script = load_script(tmp_script(slides=[{"title": "Hai Bà Trưng", "scene": scene}]))[0]
    return check_all(script, theme)


def test_group_template_character_count_is_checked(
    tmp_script: Callable[..., Path], theme: Theme
) -> None:
    message = (
        "formation centre_pair supports 1, 2, 4 or 6 characters (use line or v_shape for 3 or 5)"
    )
    for count in (0, 3, 5, 7):
        issues = _template_issues(
            tmp_script, theme, {"template": "group", "characters": [{"role": "general"}] * count}
        )
        assert [(i.path, i.message) for i in issues] == [("slides[0].scene.characters", message)]
    for count in (1, 2, 4, 6):
        scene = {"template": "group", "characters": [{"role": "general"}] * count}
        assert _template_issues(tmp_script, theme, scene) == []


def test_landscape_template_crew_count_is_checked(
    tmp_script: Callable[..., Path], theme: Theme
) -> None:
    boats = [{"x": 540, "y": 1100, "crew": [{"role": "boat_crew"}] * 3}]
    issues = _template_issues(tmp_script, theme, {"template": "landscape", "boats": boats})
    assert [(i.path, i.message) for i in issues] == [
        ("slides[0].scene.boats[0].crew", "boat supports at most 2 crew")
    ]
