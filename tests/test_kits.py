"""Costume kits: pluggable part sets so new eras add data, not figure code (FR-45)."""

from __future__ import annotations

import ast
import dataclasses
import math
from collections.abc import Callable
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest

from history_shorts import gallery
from history_shorts.canvas import Canvas
from history_shorts.characters import figure, kits, parts, roles
from history_shorts.characters.figure import (
    FigureBoxes,
    Placement,
    draw_figure,
    figure_boxes,
    figure_mask,
    head_mask,
)
from history_shorts.characters.kits import KITS, Kit, KitExtents, kit_for, kit_named
from history_shorts.characters.roles import ROLES, CharacterStyle, RolePreset, resolve_style
from history_shorts.checks import check_all
from history_shorts.config import CharacterSpec, Palette, Theme, load_script
from history_shorts.primitives import Box

ScriptFactory = Callable[..., Path]
ANCIENT_PROPS = frozenset({"flag", "spear", "oar", "none"})

# --------------------------------------------------------------------------------------
# A one-figure test kit: a body slab and a cap that hangs 10 units below the chin line.
# --------------------------------------------------------------------------------------

SLAB = (-10.0, -60.0, 20.0, 60.0)  # x, y, w, h in local units: x -10..10, y -60..0
CAP = (-5.0, -80.0, 10.0, 30.0)  # x -5..5, y -80..-50; the chin is at -60
TEST_CHIN = -60.0


def _slab(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(style.robe).rect(*SLAB).fill()


def _cap(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(style.wrap).rect(*CAP).fill()


TEST_KIT = Kit(
    name="test_kit",
    draw_order=("slab", "cap"),
    parts=MappingProxyType({"slab": _slab, "cap": _cap}),
    head_parts=frozenset({"cap"}),
    props=frozenset({"rifle", "none"}),
    hand_center=(0.0, -30.0),
    shaft_segment=lambda prop: ((0.0, -70.0), (0.0, 0.0)) if prop == "rifle" else None,
    extents=KitExtents(
        head_half_width=5.0,
        head_top=-80.0,
        crest_top=-80.0,
        chin_y=TEST_CHIN,
        body=(-10.0, -60.0, 10.0, 0.0),
        props=MappingProxyType({"rifle": (-1.0, -70.0, 1.0, 0.0)}),
    ),
)
TEST_ROLE = RolePreset("jade", "jade", "gold", "vermilion", False, "none", kit="test_kit")
# unit = 1 px per local unit, feet at (100, 200)
TEST_PLACEMENT = Placement(100, 200, 100, 1)


@pytest.fixture
def test_kit(monkeypatch: pytest.MonkeyPatch) -> Kit:
    monkeypatch.setattr(kits, "KITS", MappingProxyType({**KITS, "test_kit": TEST_KIT}))
    return TEST_KIT


def _test_style(palette: Palette, prop: str | None = None) -> CharacterStyle:
    roles_map = {**ROLES, "test_role": TEST_ROLE}
    return resolve_style(CharacterSpec(role="test_role", prop=prop), palette, roles_map)  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------
# figure.py is kit-agnostic
# --------------------------------------------------------------------------------------

PATH_METHODS = {"M", "L", "C", "Z", "ellipse", "rect", "fill", "stroke", "vgrad", "rgrad"}
ALLOWED_NUMBERS = {0, 1, -1}


def _figure_tree() -> ast.Module:
    return ast.parse(Path(figure.__file__).read_text(encoding="utf-8"))


def _module_constant_values(tree: ast.Module) -> set[int]:
    """ids of literal nodes that are the whole value of a module-level named constant."""
    ids: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.AnnAssign | ast.Assign) and isinstance(node.value, ast.Constant):
            ids.add(id(node.value))
    return ids


def test_figure_py_has_no_kit_geometry() -> None:
    tree = _figure_tree()
    named = _module_constant_values(tree)
    part_names = {name for kit in KITS.values() for name in kit.draw_order}
    kit_names = set(KITS)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in part_names, f"part name {node.value!r} in figure.py"
            assert node.value not in kit_names, f"kit name {node.value!r} in figure.py"
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            assert node.value in ALLOWED_NUMBERS or id(node) in named, (
                f"geometry literal {node.value!r} at figure.py:{node.lineno}"
            )
        if isinstance(node, ast.Attribute):
            assert node.attr not in PATH_METHODS, f"path call .{node.attr} in figure.py"
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "parts" not in imported


def test_dummy_kit_draws_without_touching_figure_py(test_kit: Kit, palette: Palette) -> None:
    style = _test_style(palette)
    assert style.kit == "test_kit"
    cv = Canvas(200, 250)
    draw_figure(cv, style, TEST_PLACEMENT, palette)
    alpha = cv.mask()
    assert alpha.max() == 1.0
    # exactly the slab (20 x 60) plus the part of the cap above it (10 x 20), nothing else
    assert alpha.sum() == pytest.approx(20 * 60 + 10 * 20)
    assert alpha[140:200, 90:110].min() == 1.0
    assert alpha[120:140, 95:105].min() == 1.0


def test_dummy_kit_boxes_come_from_its_extents(test_kit: Kit, palette: Palette) -> None:
    boxes = figure_boxes(_test_style(palette), TEST_PLACEMENT)
    assert boxes == FigureBoxes(Box(95, 120, 105, 140), Box(90, 140, 110, 200), None)
    mirrored = figure_boxes(_test_style(palette, "rifle"), Placement(100, 200, 200, -1))
    assert mirrored.prop == Box(98, 60, 102, 200)


def test_dummy_kit_masks(test_kit: Kit, palette: Palette) -> None:
    style = _test_style(palette)
    whole, _ = figure_mask(style, TEST_PLACEMENT, palette)
    assert whole.sum() == pytest.approx(20 * 60 + 10 * 20)
    head, box = head_mask(style, TEST_PLACEMENT, palette)
    # only the cap, cut at the test kit's chin (canvas y 140): 10 x 20 of its 10 x 30
    assert head.sum() == pytest.approx(10 * 20)
    chin_row = 140 - int(box.y0)
    assert head[chin_row:, :].max() == 0
    assert head[chin_row - 1, :].max() == 1.0


# --------------------------------------------------------------------------------------
# Registry and roles
# --------------------------------------------------------------------------------------


def test_every_role_kit_exists() -> None:
    for name, preset in ROLES.items():
        assert preset.kit in KITS, name
        assert preset.prop in KITS[preset.kit].props, name


def test_existing_roles_use_ancient_female() -> None:
    assert {preset.kit for preset in ROLES.values()} == {"ancient_female"}
    assert RolePreset("egg", "brown", "gold_dk", "jade", False, "none").kit == "ancient_female"


def test_resolve_style_sets_kit(palette: Palette) -> None:
    assert resolve_style(CharacterSpec(role="leader"), palette).kit == "ancient_female"
    assert _test_style(palette).kit == "test_kit"


def test_ancient_female_kit() -> None:
    kit = KITS["ancient_female"]
    assert kit.name == "ancient_female"
    assert kit.props == ANCIENT_PROPS
    assert kit.draw_order == figure.DRAW_ORDER
    assert kit.hand_center == parts.HAND_CENTER
    assert kit.shaft_segment is parts.shaft_segment
    assert kit.extents.chin_y == parts.CHIN_Y
    assert kit.parts["hand"] is parts.hand
    assert kit.head_parts == frozenset(
        {"hair_back", "neck", "face", "features", "hair_front", "bun", "headwrap", "crest"}
    )


def _distance(point: tuple[float, float], segment: Any) -> float:
    (x0, y0), (x1, y1) = segment
    px, py = point
    return abs((y1 - y0) * px - (x1 - x0) * py + x1 * y0 - y1 * x0) / math.hypot(x1 - x0, y1 - y0)


@pytest.mark.parametrize("name", sorted(KITS))
def test_every_kit_hand_centre_lies_on_each_shaft(name: str) -> None:
    kit = KITS[name]
    for prop in sorted(kit.props):
        segment = kit.shaft_segment(prop)
        if segment is not None:
            assert _distance(kit.hand_center, segment) <= 0.5, prop


def test_kits_is_read_only() -> None:
    with pytest.raises(TypeError):
        KITS["x"] = TEST_KIT  # type: ignore[index]


def test_kit_lookup_errors_are_clear(palette: Palette) -> None:
    with pytest.raises(KeyError, match="unknown kit 'ly_tran'"):
        kit_named("ly_tran")
    style = dataclasses.replace(resolve_style(CharacterSpec(role="leader"), palette), kit="ly_tran")
    with pytest.raises(KeyError, match="unknown kit 'ly_tran'"):
        kit_for(style)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"draw_order": ("slab", "cap", "sash")}, "no part 'sash'"),
        ({"head_parts": frozenset({"hat"})}, "head part 'hat' is not in the draw order"),
        ({"props": frozenset({"none"})}, "extent for prop 'rifle' not in props"),
    ],
)
def test_kit_validates_itself(change: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        dataclasses.replace(TEST_KIT, **change)


# --------------------------------------------------------------------------------------
# Validation (checks.py)
# --------------------------------------------------------------------------------------


def _load_layer_script(tmp_script: ScriptFactory, item: dict[str, Any]) -> Any:
    layer = {"type": "characters", "formation": "centre_pair", "items": [item]}
    slide = {"title": "Hai Bà Trưng", "scene": {"layers": [layer]}}
    return load_script(tmp_script(slides=[slide]))[0]


def _patch_role(monkeypatch: pytest.MonkeyPatch, role: str, **change: Any) -> None:
    patched = {**ROLES, role: dataclasses.replace(ROLES[role], **change)}
    monkeypatch.setattr(roles, "ROLES", MappingProxyType(patched))


def _pairs(script: Any, theme: Theme) -> list[tuple[str, str]]:
    return [(i.path, i.message) for i in check_all(script, theme)]


def test_role_prop_must_be_supported_by_kit(
    tmp_script: ScriptFactory, theme: Theme, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_role(monkeypatch, "general", prop="rifle")
    script = _load_layer_script(tmp_script, {"role": "general"})
    assert _pairs(script, theme) == [
        (
            "slides[0].scene.layers[0].items[0].prop",
            "prop 'rifle' not supported by kit 'ancient_female'",
        )
    ]


def test_spec_prop_checked_against_role_kit(
    tmp_script: ScriptFactory, theme: Theme, monkeypatch: pytest.MonkeyPatch, test_kit: Kit
) -> None:
    _patch_role(monkeypatch, "general", kit="test_kit", prop="rifle")
    ok = _load_layer_script(tmp_script, {"role": "general"})
    assert not any(".prop" in path for path, _ in _pairs(ok, theme))
    bad = _load_layer_script(tmp_script, {"role": "general", "prop": "flag"})
    assert (
        "slides[0].scene.layers[0].items[0].prop",
        "prop 'flag' not supported by kit 'test_kit'",
    ) in _pairs(bad, theme)


def test_role_with_unknown_kit_is_reported(
    tmp_script: ScriptFactory, theme: Theme, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_role(monkeypatch, "general", kit="ly_tran")
    script = _load_layer_script(tmp_script, {"role": "general"})
    assert _pairs(script, theme) == [
        ("slides[0].scene.layers[0].items[0].role", "role 'general' uses unknown kit 'ly_tran'")
    ]


def test_template_scene_characters_are_kit_checked(
    tmp_script: ScriptFactory, theme: Theme, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_role(monkeypatch, "leader", prop="rifle")
    slide = {"title": "A", "scene": {"template": "group", "characters": [{"role": "leader"}]}}
    script = load_script(tmp_script(slides=[slide]))[0]
    assert _pairs(script, theme) == [
        (
            "slides[0].scene.characters[0].prop",
            "prop 'rifle' not supported by kit 'ancient_female'",
        )
    ]


# --------------------------------------------------------------------------------------
# Gallery
# --------------------------------------------------------------------------------------


def test_gallery_skips_props_the_role_kit_cannot_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    narrow = dataclasses.replace(
        KITS["ancient_female"],
        props=frozenset({"flag", "none"}),
        extents=dataclasses.replace(
            KITS["ancient_female"].extents,
            props=MappingProxyType({"flag": KITS["ancient_female"].extents.props["flag"]}),
        ),
    )
    monkeypatch.setattr(kits, "KITS", MappingProxyType({**KITS, "ancient_female": narrow}))
    cells = gallery.grid_cells()
    assert {cell.prop for cell in cells} == {"flag", "none"}
    assert len(cells) == len(ROLES) * len(gallery.FACINGS) * 2
    # columns keep their place: "none" is still the fourth column
    assert {cell.box.x0 for cell in cells if cell.prop == "none"} == {3 * gallery.CELL_W}


def test_gallery_has_every_cell_for_ancient_female() -> None:
    cells = gallery.grid_cells()
    assert len(cells) == len(ROLES) * len(gallery.FACINGS) * len(gallery.PROPS)
    assert np.unique([cell.prop for cell in cells]).tolist() == sorted(ANCIENT_PROPS)
