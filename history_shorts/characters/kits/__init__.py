"""Costume kits: pluggable part sets, one module per kit (FR-45).

A role preset names its kit; ``figure.py`` draws, boxes and masks any character through
``kit_for(style)``. A new era is a new kit module registered in ``KITS`` plus role data;
``figure.py`` never changes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING

from history_shorts.characters.kits import ancient_female, ancient_female_rig
from history_shorts.characters.kits.base import (
    Kit,
    KitExtents,
    LocalBox,
    PartFn,
    ShaftFn,
    Variation,
    variation_for,
)

if TYPE_CHECKING:
    from history_shorts.characters.roles import CharacterStyle

# Kits with their rigs attached (M10); a kit without a rig still draws still figures.
_ANCIENT_FEMALE = dataclasses.replace(ancient_female.KIT, rig=ancient_female_rig.RIG)
KITS: Mapping[str, Kit] = MappingProxyType({kit.name: kit for kit in (_ANCIENT_FEMALE,)})


def kit_named(name: str) -> Kit:
    """The registered kit called ``name``; ``KeyError`` with a clear message otherwise."""
    try:
        return KITS[name]
    except KeyError:
        raise KeyError(f"unknown kit '{name}'") from None


def kit_for(style: CharacterStyle) -> Kit:
    """The kit a resolved style is drawn with."""
    return kit_named(style.kit)


__all__ = [
    "KITS",
    "Kit",
    "KitExtents",
    "LocalBox",
    "PartFn",
    "ShaftFn",
    "Variation",
    "kit_for",
    "kit_named",
    "variation_for",
]
