"""Cross-file checks: rules that need both the script and the theme (FR-11, AC-08).

``load_script`` and ``load_theme`` validate each file alone. Here the two are checked
against each other: font glyph coverage, text fit and auto-shrink, and palette keys named by
character overrides, and costume kits (FR-45): each role's kit must exist and draw the
character's prop. FR-48 overlap checks live here too: character boxes against the seal,
tag and text, and pixel masks for "no character covers another character's head".
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Final

import numpy as np

from history_shorts.characters.figure import FigureBoxes, figure_boxes, figure_mask, head_mask
from history_shorts.characters.formations import PlacedCharacter, count_error
from history_shorts.characters.kits import kit_named
from history_shorts.characters.roles import (
    CharacterStyle,
    preset_for,
    resolve_style,
    resolved_prop,
)
from history_shorts.chrome import FRAME_INNER_INSET, seal_box, tag_box, tag_too_wide
from history_shorts.config import (
    BoatLayer,
    CharactersLayer,
    CharacterSpec,
    LayerScene,
    Palette,
    Script,
    Slide,
    TemplateScene,
    Theme,
)
from history_shorts.errors import Issue, Issues
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import Box, FloatMask
from history_shorts.scene.boat import CREW_COUNT_ERROR, MAX_CREW, crew_placements
from history_shorts.scene.people import placed_characters
from history_shorts.scene.templates import expand
from history_shorts.text import (
    VIETNAMESE_CHARSET,
    TextFitError,
    TextPlan,
    missing_glyphs,
    plan_text,
)

log = logging.getLogger(__name__)

THEME_FONT_KEYS: Final = ("title", "subtitle", "tag")
# Slide text fields -> theme font that renders them.
TEXT_FIELD_FONTS: Final = (("tag", "tag"), ("title", "title"), ("subtitle", "subtitle"))
# CharacterSpec fields that name a palette key.
PALETTE_OVERRIDE_FIELDS: Final = ("robe", "robe_dk", "trim", "wrap")
# Character heads stay inside the chrome frame. This is deliberately not the safe zone: the
# approved ``group`` composition puts the outer generals' heads past its right edge.
FRAME_INNER: Final = Box(
    FRAME_INNER_INSET, FRAME_INNER_INSET, CANVAS_W - FRAME_INNER_INSET, CANVAS_H - FRAME_INNER_INSET
)
# Pixels of a later character's mask allowed on an earlier character's head mask.
HEAD_OVERLAP_TOLERANCE_PX: Final = 0
MASK_ALPHA_THRESHOLD: Final = 0.5


def check_all(script: Script, theme: Theme) -> list[Issue]:
    """Every cross-file problem, errors and warnings, in a stable order."""
    issues = Issues()
    _check_theme_fonts(theme, issues)
    _check_used_glyphs(script, theme, issues)
    _check_theme_text_glyphs(theme, issues)
    _check_text_fit(script, theme, issues)
    _check_tag_width(script, theme, issues)
    _check_palette_refs(script, theme, issues)
    _check_kits(script, issues)
    _check_characters(script, theme, issues)
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


def _check_theme_text_glyphs(theme: Theme, issues: Issues) -> None:
    """Seal lines (title font) and an enabled footer (tag font) must be renderable."""
    name = theme.path.name
    chrome = theme.chrome
    targets: list[tuple[str, str, Path]] = [
        (f"chrome.seal.lines[{i}]", line, theme.fonts.title)
        for i, line in enumerate(chrome.seal.lines)
    ]
    if chrome.footer.enabled and chrome.footer.text:
        targets.append(("chrome.footer.text", chrome.footer.text, theme.fonts.tag))
    for where, text, font_path in targets:
        absent = missing_glyphs(font_path, _used_characters(text))
        if absent:
            issues.error(name, where, f"missing glyphs: {', '.join(absent)}")


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
# Tag pill (FR-70)
# --------------------------------------------------------------------------------------


def _check_tag_width(script: Script, theme: Theme, issues: Issues) -> None:
    for index, slide in enumerate(script.slides):
        box = tag_box(slide.tag, theme)
        if box is not None and tag_too_wide(box, theme):
            issues.error(
                script.path.name,
                f"slides[{index}].tag",
                f"tag too wide ({round(box.width)} px); shorten it",
            )


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


# --------------------------------------------------------------------------------------
# Costume kits (FR-45)
# --------------------------------------------------------------------------------------


def kit_problem(spec: CharacterSpec) -> tuple[str, str] | None:
    """(field, message) when the spec's role kit is unknown or cannot draw its prop.

    An unknown role is the script loader's error, so it is not reported here.
    """
    try:
        preset = preset_for(spec)
    except KeyError:
        return None
    try:
        kit = kit_named(preset.kit)
    except KeyError:
        return "role", f"role '{spec.role}' uses unknown kit '{preset.kit}'"
    prop = resolved_prop(spec, preset)
    if prop not in kit.props:
        return "prop", f"prop '{prop}' not supported by kit '{kit.name}'"
    return None


def _check_kits(script: Script, issues: Issues) -> None:
    for index, slide in enumerate(script.slides):
        if slide.scene is None:
            continue
        for path, spec in _scene_characters(slide.scene, f"slides[{index}].scene"):
            problem = kit_problem(spec)
            if problem is not None:
                field, message = problem
                issues.error(script.path.name, f"{path}.{field}", message)


# --------------------------------------------------------------------------------------
# Characters: counts and placement (FR-47, FR-48)
# --------------------------------------------------------------------------------------


Styled = tuple[PlacedCharacter, CharacterStyle, str]  # placement, style, JSON path


def _check_characters(script: Script, theme: Theme, issues: Issues) -> None:
    """Counts and FR-48 overlap checks for every scene's positioned characters and boat crew.

    Template scenes are expanded first (``templates.expand``), so the reference ``group`` and
    ``landscape`` compositions go through the same checks as hand-written layers. Placement
    comes from ``people.placed_characters`` and ``boat.crew_placements``, the functions the
    layer drawers use. Each slide is placed and checked once.
    """
    name = script.path.name
    for index, slide in enumerate(script.slides):
        if slide.scene is None:
            continue
        placed = _slide_placed(name, index, slide.scene, theme, issues)
        if not placed:
            continue
        try:
            text = plan_text(slide, theme)
        except TextFitError:
            continue  # reported by the text-fit check
        issues.items.extend(
            check_overlaps(index, placed, text, theme, theme.palette, tag=slide.tag, file=name)
        )


def _slide_placed(
    name: str, index: int, scene: LayerScene | TemplateScene, theme: Theme, issues: Issues
) -> list[Styled]:
    """Placed, styled characters of all character and boat layers, in draw order.

    JSON paths follow the script: ``scene.layers[k].items`` / ``.crew`` for a layer scene,
    ``scene.characters`` and ``scene.boats[b].crew`` for a template.
    """
    base = f"slides[{index}].scene"
    placed: list[Styled] = []
    boats = 0
    for layer_index, layer in enumerate(expand(scene, theme).layers):
        where = f"{base}.layers[{layer_index}]" if isinstance(scene, LayerScene) else base
        if isinstance(layer, CharactersLayer):
            items = f"{where}.items" if isinstance(scene, LayerScene) else f"{base}.characters"
            placed.extend(_characters_placed(name, items, layer, theme.palette, issues))
        elif isinstance(layer, BoatLayer):
            if isinstance(scene, TemplateScene):
                where = f"{base}.boats[{boats}]"
                boats += 1
            placed.extend(_boat_placed(name, f"{where}.crew", layer, theme.palette, issues))
    return placed


def _styled(
    placed: Sequence[PlacedCharacter], paths: Sequence[str], palette: Palette
) -> list[Styled]:
    """Pair each placement with its resolved style and JSON path; ``[]`` if a key is unknown."""
    try:
        styles = [resolve_style(p.spec, palette) for p in placed]
    except KeyError:
        return []  # unknown palette keys are reported by the palette check
    return list(zip(placed, styles, paths, strict=True))


def _characters_placed(
    name: str, items_path: str, layer: CharactersLayer, palette: Palette, issues: Issues
) -> list[Styled]:
    """Place a characters layer whose specs live at ``items_path``; problems become issues."""
    specs = layer.items
    if layer.formation is not None:
        message = count_error(layer.formation, len(specs))
        if message is not None:
            issues.error(name, items_path, message)
            return []
    else:
        missing = [k for k, spec in enumerate(specs) if spec.x is None]
        for k in missing:
            issues.error(name, f"{items_path}[{k}].x", "needs x without a formation")
        if missing:
            return []
    if any(kit_problem(spec) is not None for spec in specs):
        return []  # reported by the kit check
    try:
        placed = placed_characters(layer)
    except ValueError:
        return []
    # a formation reorders the specs into draw order, so paths follow the spec objects
    paths = {id(spec): f"{items_path}[{k}]" for k, spec in enumerate(specs)}
    return _styled(placed, [paths[id(p.spec)] for p in placed], palette)


def _boat_placed(
    name: str, crew_path: str, layer: BoatLayer, palette: Palette, issues: Issues
) -> list[Styled]:
    """Place a boat's crew, whose specs live at ``crew_path``; problems become issues."""
    if len(layer.crew) > MAX_CREW:
        issues.error(name, crew_path, CREW_COUNT_ERROR)
        return []
    if any(kit_problem(spec) is not None for spec in layer.crew):
        return []  # reported by the kit check
    placed = crew_placements(layer)  # in spec order
    return _styled(placed, [f"{crew_path}[{k}]" for k in range(len(placed))], palette)


def _fmt(box: Box) -> str:
    return f"({round(box.x0)},{round(box.y0)},{round(box.x1)},{round(box.y1)})"


def _figure_overlaps(
    boxes: FigureBoxes, targets: Sequence[tuple[str, Box | None]]
) -> Iterator[tuple[str, Box, Box]]:
    """(target name, character box, target box) for the first character box hit per target."""
    own = [box for box in (boxes.head, boxes.body, boxes.prop) if box is not None]
    for label, target in targets:
        if target is None:
            continue
        hit = next((box for box in own if box.intersects(target)), None)
        if hit is not None:
            yield label, hit, target


def check_overlaps(
    slide_index: int,
    placed: list[Styled],
    text: TextPlan,
    theme: Theme,
    palette: Palette,
    *,
    tag: str,
    file: str,
) -> list[Issue]:
    """FR-48 for one slide. ``placed`` is in draw order; each ``str`` is the JSON path.

    ``tag`` is the slide's tag text and ``file`` the script name for issues; both are
    required, because an omitted tag would silently skip the tag-pill check.

    Errors: a head box outside the frame; a head, body or prop box on the seal, tag pill,
    title or subtitle box; a later-drawn character whose pixels cover an earlier
    character's head (pixel masks, so boxes of the approved composition do not trip it).
    """
    targets = (
        ("seal", seal_box(theme)),
        ("tag", tag_box(tag, theme)),
        ("title", text.title_box),
        ("subtitle", text.subtitle_box),
    )
    issues: list[Issue] = []
    for item, style, path in placed:
        boxes = figure_boxes(style, item.placement)
        if not boxes.head.inside(FRAME_INNER):
            issues.append(
                Issue(
                    file,
                    path,
                    f"head box {_fmt(boxes.head)} is outside the frame {_fmt(FRAME_INNER)}",
                    "error",
                )
            )
        for label, mine, other in _figure_overlaps(boxes, targets):
            msg = f"overlaps {label} (character box {_fmt(mine)}, {label} box {_fmt(other)})"
            issues.append(Issue(file, path, msg, "error"))
    issues.extend(_head_cover_issues(placed, palette, file))
    log.debug("slide %d: %d overlap issue(s)", slide_index, len(issues))
    return issues


def _overlap_pixels(upper: tuple[FloatMask, Box], lower: tuple[FloatMask, Box]) -> int:
    """Pixels where both masks exceed the threshold, in canvas coordinates."""
    (a, abox), (b, bbox) = upper, lower
    x0, y0 = int(max(abox.x0, bbox.x0)), int(max(abox.y0, bbox.y0))
    x1, y1 = int(min(abox.x1, bbox.x1)), int(min(abox.y1, bbox.y1))
    if x1 <= x0 or y1 <= y0:
        return 0
    sa = a[y0 - int(abox.y0) : y1 - int(abox.y0), x0 - int(abox.x0) : x1 - int(abox.x0)]
    sb = b[y0 - int(bbox.y0) : y1 - int(bbox.y0), x0 - int(bbox.x0) : x1 - int(bbox.x0)]
    return int(np.count_nonzero((sa > MASK_ALPHA_THRESHOLD) & (sb > MASK_ALPHA_THRESHOLD)))


def _head_cover_issues(placed: list[Styled], palette: Palette, file: str) -> list[Issue]:
    if len(placed) < 2:
        return []
    bodies = [figure_mask(style, item.placement, palette) for item, style, _ in placed]
    heads = [head_mask(style, item.placement, palette) for item, style, _ in placed]
    issues: list[Issue] = []
    for upper in range(1, len(placed)):  # drawn later = in front
        for lower in range(upper):
            count = _overlap_pixels(bodies[upper], heads[lower])
            if count > HEAD_OVERLAP_TOLERANCE_PX:
                msg = f"covers the head of {placed[lower][2]} ({count} px)"
                issues.append(Issue(file, placed[upper][2], msg, "error"))
    return issues
