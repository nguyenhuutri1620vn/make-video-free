"""Costume kits: pluggable part sets, one module per kit (FR-45).

A role preset names its kit; ``figure.py`` draws, boxes and masks any character through
``kit_for(style)``. A new era is a new kit module registered in ``KITS`` plus role data;
``figure.py`` never changes.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from history_shorts.characters.kits import ancient_female
from history_shorts.characters.kits.base import Kit, KitExtents, LocalBox, PartFn, ShaftFn
from history_shorts.characters.roles import CharacterStyle

KITS: Mapping[str, Kit] = MappingProxyType({kit.name: kit for kit in (ancient_female.KIT,)})


def kit_named(name: str) -> Kit:
    """The registered kit called ``name``; ``KeyError`` with a clear message otherwise."""
    try:
        return KITS[name]
    except KeyError:
        raise KeyError(f"unknown kit '{name}'") from None


def kit_for(style: CharacterStyle) -> Kit:
    """The kit a resolved style is drawn with."""
    return kit_named(style.kit)


__all__ = ["KITS", "Kit", "KitExtents", "LocalBox", "PartFn", "ShaftFn", "kit_for", "kit_named"]
