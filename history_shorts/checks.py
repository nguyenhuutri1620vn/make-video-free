"""Cross-file checks: rules that need both the script and the theme (FR-11, AC-08).

``load_script`` and ``load_theme`` validate each file alone. Here the two are checked
against each other: font glyph coverage, text fit and auto-shrink, and palette keys named by
character overrides. Overlap checks join this module with the formations (milestone M3).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Final

from history_shorts.config import (
    BoatLayer,
    CharactersLayer,
    CharacterSpec,
    LayerScene,
    Script,
    Slide,
    TemplateScene,
    Theme,
)
from history_shorts.errors import Issue, Issues
from history_shorts.text import VIETNAMESE_CHARSET, TextFitError, missing_glyphs, plan_text

THEME_FONT_KEYS: Final = ("title", "subtitle", "tag")
# Slide text fields -> theme font that renders them.
TEXT_FIELD_FONTS: Final = (("tag", "tag"), ("title", "title"), ("subtitle", "subtitle"))
# CharacterSpec fields that name a palette key.
PALETTE_OVERRIDE_FIELDS: Final = ("robe", "robe_dk", "trim", "wrap")


def check_all(script: Script, theme: Theme) -> list[Issue]:
    """Every cross-file problem, errors and warnings, in a stable order."""
    issues = Issues()
    _check_theme_fonts(theme, issues)
    _check_used_glyphs(script, theme, issues)
    _check_text_fit(script, theme, issues)
    _check_palette_refs(script, theme, issues)
    return issues.items


# --------------------------------------------------------------------------------------
# Glyphs (AC-08)
# --------------------------------------------------------------------------------------


def _check_theme_fonts(theme: Theme, issues: Issues) -> None:
    """Each distinct font file must cover the whole Vietnamese character set."""
    seen: set[Path] = set()
    for key in THEME_FONT_KEYS:
        path: Path = getattr(theme.fonts, key)
        if path in seen:
            continue
        seen.add(path)
        missing = missing_glyphs(path, VIETNAMESE_CHARSET)
        if missing:
            issues.error(theme.path.name, f"fonts.{key}", f"missing glyphs: {', '.join(missing)}")


def _used_characters(text: str) -> str:
    """The distinct non-space characters of ``text`` in order of first appearance."""
    return "".join(dict.fromkeys(ch for ch in text if not ch.isspace()))


def _check_used_glyphs(script: Script, theme: Theme, issues: Issues) -> None:
    """Characters the script actually uses must exist in the font that renders their field."""
    name = script.path.name
    for field, font_key in TEXT_FIELD_FONTS:
        values = [getattr(slide, field) for slide in script.slides]
        union = _used_characters("".join(values))
        if not union:
            continue
        absent = set(missing_glyphs(getattr(theme.fonts, font_key), union))
        if not absent:
            continue
        for index, value in enumerate(values):
            here = [ch for ch in _used_characters(value) if ch in absent]
            if here:
                issues.error(name, f"slides[{index}].{field}", f"missing glyphs: {', '.join(here)}")


# --------------------------------------------------------------------------------------
# Text fit and shrink (FR-25)
# --------------------------------------------------------------------------------------


def _check_text_fit(script: Script, theme: Theme, issues: Issues) -> None:
    for index, slide in enumerate(script.slides):
        _check_slide_text(script.path.name, index, slide, theme, issues)


def _check_slide_text(name: str, index: int, slide: Slide, theme: Theme, issues: Issues) -> None:
    scale = theme.type_scale
    try:
        plan = plan_text(slide, theme)
    except TextFitError as exc:
        minimum = scale.title_min if exc.field == "title" else scale.subtitle_min
        issues.error(
            name,
            f"slides[{index}].{exc.field}",
            f"does not fit at {minimum} px; {exc.suggestion}",
        )
        return
    for field, full_size in (("title", scale.title), ("subtitle", scale.subtitle)):
        sizes = [ln.size for ln in plan.lines if ln.font_key == field]
        if sizes and sizes[0] < full_size:
            issues.warning(name, f"slides[{index}].{field}", f"text auto-shrunk to {sizes[0]} px")


# --------------------------------------------------------------------------------------
# Palette references (FR-11)
# --------------------------------------------------------------------------------------


def _check_palette_refs(script: Script, theme: Theme, issues: Issues) -> None:
    known = theme.palette.colors
    name = script.path.name
    for index, slide in enumerate(script.slides):
        if slide.scene is None:
            continue
        base = f"slides[{index}].scene"
        for path, spec in _scene_characters(slide.scene, base):
            for field in PALETTE_OVERRIDE_FIELDS:
                value: str | None = getattr(spec, field)
                if value is not None and value not in known:
                    issues.error(name, f"{path}.{field}", f"unknown palette key '{value}'")


def _scene_characters(
    scene: LayerScene | TemplateScene, base: str
) -> Iterator[tuple[str, CharacterSpec]]:
    """Every character spec in a scene with its JSON path, mirroring ``scene_config``."""
    if isinstance(scene, TemplateScene):
        yield from _indexed(f"{base}.characters", scene.characters or ())
        for b, boat in enumerate(scene.boats or ()):
            yield from _indexed(f"{base}.boats[{b}].crew", boat.crew)
        return
    for layer_index, layer in enumerate(scene.layers):
        path = f"{base}.layers[{layer_index}]"
        if isinstance(layer, CharactersLayer):
            yield from _indexed(f"{path}.items", layer.items)
        elif isinstance(layer, BoatLayer):
            yield from _indexed(f"{path}.crew", layer.crew)


def _indexed(path: str, specs: tuple[CharacterSpec, ...]) -> Iterator[tuple[str, CharacterSpec]]:
    for index, spec in enumerate(specs):
        yield f"{path}[{index}]", spec
