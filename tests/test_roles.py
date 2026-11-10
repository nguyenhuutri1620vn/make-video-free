"""Role presets and style resolution (FR-45, FR-46)."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from history_shorts.characters import ROLES, CharacterStyle, RolePreset, resolve_style
from history_shorts.config import ROLE_NAMES, CharacterSpec


def test_role_presets_match_prototype() -> None:
    assert ROLES["leader"] == RolePreset("vermilion", "vermilion_dk", "gold", "gold", True, "flag")
    assert ROLES["general"] == RolePreset(
        "vermilion_dk", "robe_general_dk", "gold_dk", "vermilion", False, "spear"
    )
    assert ROLES["general_alt"] == RolePreset(
        "brown", "robe_general_alt_dk", "vermilion", "vermilion", False, "spear"
    )
    assert ROLES["boat_crew"] == RolePreset(
        "jade", "robe_crew_dk", "gold_dk", "vermilion", False, "oar"
    )


def test_roles_agree_with_config_role_names() -> None:
    assert set(ROLES) == set(ROLE_NAMES)


def test_roles_is_read_only() -> None:
    with pytest.raises(TypeError):
        ROLES["x"] = ROLES["leader"]  # type: ignore[index]


def test_preset_and_style_are_frozen(palette: Any) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ROLES["leader"].robe = "jade"  # type: ignore[misc]
    style = resolve_style(CharacterSpec(role="leader"), palette)
    with pytest.raises(dataclasses.FrozenInstanceError):
        style.crest = False  # type: ignore[misc]


def test_every_preset_key_exists_in_palette(palette: Any) -> None:
    for preset in ROLES.values():
        for key in (preset.robe, preset.robe_dk, preset.trim, preset.wrap):
            assert key in palette.keys()


@pytest.mark.parametrize("role", ROLE_NAMES)
def test_defaults_resolve_to_preset_colours(role: str, palette: Any) -> None:
    preset = ROLES[role]
    style = resolve_style(CharacterSpec(role=role), palette)
    assert style == CharacterStyle(
        palette[preset.robe],
        palette[preset.robe_dk],
        palette[preset.trim],
        palette[preset.wrap],
        palette[preset.trim] == palette["gold"],
        preset.crest,
        preset.prop,
    )


def test_prototype_dark_robe_tuples(palette: Any) -> None:
    assert resolve_style(CharacterSpec(role="general"), palette).robe_dk == (70, 14, 10)
    assert resolve_style(CharacterSpec(role="general_alt"), palette).robe_dk == (56, 28, 16)
    assert resolve_style(CharacterSpec(role="boat_crew"), palette).robe_dk == (30, 50, 42)


def test_overrides_apply(palette: Any) -> None:
    s = resolve_style(CharacterSpec(role="general", robe="jade", prop="flag", crest=True), palette)
    assert s.robe == palette["jade"] and s.prop == "flag" and s.crest


def test_colour_overrides_each_field(palette: Any) -> None:
    spec = CharacterSpec(role="general", robe_dk="jade", trim="egg", wrap="brown")
    s = resolve_style(spec, palette)
    assert (s.robe_dk, s.trim, s.wrap) == (palette["jade"], palette["egg"], palette["brown"])


def test_explicit_false_crest_and_none_prop_override(palette: Any) -> None:
    s = resolve_style(CharacterSpec(role="leader", prop="none", crest=False), palette)
    assert s.prop == "none" and s.crest is False


def test_trim_is_gold_follows_resolved_trim(palette: Any) -> None:
    assert resolve_style(CharacterSpec(role="leader"), palette).trim_is_gold
    assert not resolve_style(CharacterSpec(role="general"), palette).trim_is_gold
    assert resolve_style(CharacterSpec(role="general", trim="gold"), palette).trim_is_gold
    assert not resolve_style(CharacterSpec(role="leader", trim="gold_dk"), palette).trim_is_gold


def test_new_role_is_data_only(palette: Any) -> None:
    roles = {**ROLES, "scholar": RolePreset("egg", "brown", "gold_dk", "jade", False, "none")}
    assert resolve_style(CharacterSpec(role="scholar"), palette, roles).prop == "none"


def test_unknown_role_raises_clear_key_error(palette: Any) -> None:
    with pytest.raises(KeyError, match="unknown role 'bard'"):
        resolve_style(CharacterSpec(role="bard"), palette)


def test_unknown_palette_key_raises_clear_key_error(palette: Any) -> None:
    with pytest.raises(KeyError, match="unknown palette key 'teal'"):
        resolve_style(CharacterSpec(role="general", robe="teal"), palette)
