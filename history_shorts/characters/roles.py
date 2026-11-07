"""Role presets and style resolution (FR-45, FR-46).

A role is pure data: palette keys, a prop and a crest flag. Adding a role means adding
a ``RolePreset`` to a mapping; no drawing code changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from history_shorts.config import CharacterSpec, Palette
from history_shorts.primitives import RGB


@dataclass(frozen=True, slots=True)
class RolePreset:
    """Default look of a role; every colour is a palette key."""

    robe: str
    robe_dk: str
    trim: str
    wrap: str
    crest: bool
    prop: str


@dataclass(frozen=True, slots=True)
class CharacterStyle:
    """Concrete colours and flags for drawing one character."""

    robe: RGB
    robe_dk: RGB
    trim: RGB
    wrap: RGB
    trim_is_gold: bool
    crest: bool
    prop: str


ROLES: Mapping[str, RolePreset] = MappingProxyType(
    {
        "leader": RolePreset("vermilion", "vermilion_dk", "gold", "gold", True, "flag"),
        "general": RolePreset(
            "vermilion_dk", "robe_general_dk", "gold_dk", "vermilion", False, "spear"
        ),
        "general_alt": RolePreset(
            "brown", "robe_general_alt_dk", "vermilion", "vermilion", False, "spear"
        ),
        "boat_crew": RolePreset("jade", "robe_crew_dk", "gold_dk", "vermilion", False, "oar"),
    }
)


def _colour(palette: Palette, key: str) -> RGB:
    try:
        return palette[key]
    except KeyError:
        raise KeyError(f"unknown palette key '{key}'") from None


def resolve_style(
    spec: CharacterSpec,
    palette: Palette,
    roles: Mapping[str, RolePreset] = ROLES,
) -> CharacterStyle:
    """Role preset plus the spec's overrides, with palette keys turned into RGB.

    Raises ``KeyError`` for an unknown role or palette key; validation reports those
    earlier, so this is the programming-error path.
    """
    try:
        preset = roles[spec.role]
    except KeyError:
        raise KeyError(f"unknown role '{spec.role}'") from None
    trim = _colour(palette, spec.trim or preset.trim)
    return CharacterStyle(
        robe=_colour(palette, spec.robe or preset.robe),
        robe_dk=_colour(palette, spec.robe_dk or preset.robe_dk),
        trim=trim,
        wrap=_colour(palette, spec.wrap or preset.wrap),
        trim_is_gold=trim == _colour(palette, "gold"),
        crest=preset.crest if spec.crest is None else spec.crest,
        prop=preset.prop if spec.prop is None else spec.prop,
    )
