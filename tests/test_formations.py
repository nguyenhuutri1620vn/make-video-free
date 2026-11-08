"""Figure boxes, formations and FR-48 overlap checks (FR-47, FR-48, AC-06)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.characters import CharacterStyle, resolve_style
from history_shorts.characters.figure import (
    Placement,
    figure_boxes,
    figure_mask,
    head_mask,
)
from history_shorts.characters.formations import PlacedCharacter, place
from history_shorts.checks import check_all, check_overlaps
from history_shorts.config import CharacterSpec, Palette, Theme, load_script
from history_shorts.errors import Issue
from history_shorts.primitives import Box
from history_shorts.text import TextPlan, plan_text

REF_ROLES = ["leader", "leader", "general_alt", "general_alt", "general", "general"]
REF_SPECS = [CharacterSpec(role=r) for r in REF_ROLES]
REF_TITLE = "Những nữ tướng\nbên Hai Bà Trưng"
REF_SUBTITLE = "Khi phụ nữ cầm quân giữ nước"
REF_TAG = "NĂM 40 SAU CÔNG NGUYÊN"
FRAME_INNER = Box(58, 58, 1022, 1862)

SlideFactory = Callable[..., Any]
ScriptFactory = Callable[..., Path]


def summary(placed: Sequence[PlacedCharacter]) -> list[tuple[float, float, float, int]]:
    return [
        (p.placement.x, p.placement.baseline, p.placement.height, p.placement.facing)
        for p in placed
    ]


def styled(
    placed: Sequence[PlacedCharacter], palette: Palette, base: str = "slides[0].scene.characters"
) -> list[tuple[PlacedCharacter, CharacterStyle, str]]:
    return [(p, resolve_style(p.spec, palette), f"{base}[{k}]") for k, p in enumerate(placed)]


def ref_text(make_slide: SlideFactory, theme: Theme, tag: str = REF_TAG) -> TextPlan:
    return plan_text(make_slide(REF_TITLE, REF_SUBTITLE, tag=tag), theme)


# --------------------------------------------------------------------------------------
# Formations (FR-47)
# --------------------------------------------------------------------------------------


def test_centre_pair_reference_positions() -> None:
    placed = place("centre_pair", REF_SPECS, baseline=1100)
    assert summary(placed) == [
        (150, 1096, 420, -1),
        (930, 1096, 420, 1),
        (285, 1100, 475, -1),
        (795, 1100, 475, 1),
        (432, 1106, 565, -1),
        (648, 1106, 565, 1),
    ]
    # draw order is back rows first, which means the outer pair holds the last input specs
    assert [p.spec.role for p in placed] == [
        "general",
        "general",
        "general_alt",
        "general_alt",
        "leader",
        "leader",
    ]


def test_two_characters_take_front_slots() -> None:
    placed = place("centre_pair", REF_SPECS[:2], baseline=1100)
    assert summary(placed) == [(432, 1106, 565, -1), (648, 1106, 565, 1)]


def test_centre_pair_odd_last_character_is_centred_in_its_tier() -> None:
    one = place("centre_pair", REF_SPECS[:1], baseline=1100)
    assert summary(one) == [(540, 1106, 565, 1)]
    three = place("centre_pair", REF_SPECS[:3], baseline=1100)
    assert summary(three) == [(540, 1100, 475, 1), (432, 1106, 565, -1), (648, 1106, 565, 1)]
    five = place("centre_pair", REF_SPECS[:1] * 5, baseline=1000)
    assert summary(five)[0] == (540, 996, 420, 1)


def test_explicit_values_override_slots_and_facing() -> None:
    specs = [CharacterSpec(role="leader", x=300, baseline=900, height=300, facing=1)]
    assert summary(place("centre_pair", specs, baseline=1100)) == [(300, 900, 300, 1)]


def test_facing_defaults_outward_for_x_below_or_above_centre() -> None:
    specs = [CharacterSpec(role="general", x=100), CharacterSpec(role="general", x=700)]
    placed = place("line", specs, baseline=1100)
    assert [p.placement.facing for p in placed] == [-1, 1]
    # but a spec that sets facing wins
    forced = place("line", [CharacterSpec(role="general", facing=1)] * 2, baseline=1100)
    assert [p.placement.facing for p in forced] == [1, 1]


def test_line_and_v_shape_face_outward() -> None:
    for formation in ("line", "v_shape"):
        for n in range(2, 8):
            for p in place(formation, [CharacterSpec(role="general")] * n, baseline=1100):
                assert p.placement.facing == (-1 if p.placement.x < 540 else 1)


def test_line_is_evenly_spaced() -> None:
    placed = place("line", [CharacterSpec(role="general")] * 5, baseline=1100)
    assert [p.placement.x for p in placed] == [150, 345, 540, 735, 930]
    assert {(p.placement.baseline, p.placement.height) for p in placed} == {(1100, 475)}
    assert summary(place("line", [CharacterSpec(role="general")], baseline=1100)) == [
        (540, 1100, 475, 1)
    ]


def test_v_shape_steps_outward() -> None:
    placed = place("v_shape", [CharacterSpec(role="general")] * 5, baseline=1100)
    by_x = sorted(summary(placed))
    assert [x for x, *_ in by_x] == pytest.approx([270, 405, 540, 675, 810])
    centre = next(s for s in summary(placed) if s[0] == 540)
    assert centre[1:] == (1106, 565, 1)
    step1 = next(s for s in summary(placed) if s[0] == 405)
    assert step1[1] == 1102 and step1[2] == pytest.approx(565 * 0.88)
    step2 = next(s for s in summary(placed) if s[0] == 270)
    assert step2[1] == 1098 and step2[2] == pytest.approx(565 * 0.88**2)
    # back rows first: the outermost characters are drawn first, the centre last
    assert placed[-1].placement.x == 540
    assert {placed[0].placement.x, placed[1].placement.x} == {270, 810}


@pytest.mark.parametrize(
    ("formation", "count"),
    [
        ("centre_pair", 0),
        ("centre_pair", 7),
        ("line", 0),
        ("line", 8),
        ("v_shape", 0),
        ("v_shape", 8),
    ],
)
def test_wrong_counts_raise(formation: str, count: int) -> None:
    with pytest.raises(ValueError, match=f"formation {formation} supports"):
        place(formation, [CharacterSpec(role="general")] * count, baseline=1100)


def test_unknown_formation_raises() -> None:
    with pytest.raises(ValueError, match="unknown formation"):
        place("circle", REF_SPECS, baseline=1100)


def test_no_formation_places_explicit_items() -> None:
    specs = [CharacterSpec(role="general", x=200, height=400), CharacterSpec(role="general", x=800)]
    placed = place(None, specs, baseline=1000)
    assert summary(placed) == [(200, 1000, 400, -1), (800, 1000, 475, 1)]


def test_no_formation_without_x_raises() -> None:
    with pytest.raises(ValueError, match="needs x"):
        place(None, [CharacterSpec(role="general")], baseline=1000)


# --------------------------------------------------------------------------------------
# Boxes and masks
# --------------------------------------------------------------------------------------


def test_boxes_scale_with_height_and_mirror_with_facing(palette: Palette) -> None:
    style = resolve_style(CharacterSpec(role="leader"), palette)
    right = figure_boxes(style, Placement(540, 1000, 500, 1))
    left = figure_boxes(style, Placement(540, 1000, 500, -1))
    assert right.head.x1 - 540 == pytest.approx(540 - left.head.x0)
    assert right.body.x1 - 540 == pytest.approx(540 - left.body.x0)
    assert right.prop is not None and left.prop is not None
    assert right.prop.x1 == pytest.approx(540 + 5 * 50)  # flag cloth reaches 50 units out
    assert left.prop.x0 == pytest.approx(540 - 5 * 50)
    assert right.prop.y0 < right.head.y0  # flag tip rises above the crest
    assert right.body.y1 == pytest.approx(1000 + 1.5 * 5)
    assert right.head.height > 0


def test_no_prop_gives_no_prop_box(palette: Palette) -> None:
    style = resolve_style(CharacterSpec(role="general", prop="none"), palette)
    assert figure_boxes(style, Placement(540, 1000, 500, 1)).prop is None


def test_crest_raises_the_head_box(palette: Palette) -> None:
    plain = resolve_style(CharacterSpec(role="general", crest=False), palette)
    crowned = resolve_style(CharacterSpec(role="general", crest=True), palette)
    place_at = Placement(540, 1000, 500, 1)
    assert figure_boxes(crowned, place_at).head.y0 < figure_boxes(plain, place_at).head.y0


@pytest.mark.parametrize("role", ["leader", "general", "general_alt", "boat_crew"])
@pytest.mark.parametrize("facing", [-1, 1])
def test_boxes_enclose_every_drawn_pixel_closely(role: str, facing: int, palette: Palette) -> None:
    style = resolve_style(CharacterSpec(role=role), palette)
    placement = Placement(540, 1100, 565, facing)
    boxes = figure_boxes(style, placement)
    mask, origin = figure_mask(style, placement, palette)
    ys, xs = np.nonzero(mask > 0.02)
    drawn = Box(
        origin.x0 + xs.min(),
        origin.y0 + ys.min(),
        origin.x0 + xs.max() + 1,
        origin.y0 + ys.max() + 1,
    )
    union = boxes.head.union(boxes.body)
    if boxes.prop is not None:
        union = union.union(boxes.prop)
    tol = 4  # stroke widths are not part of the extreme points
    assert drawn.x0 >= union.x0 - tol and drawn.y0 >= union.y0 - tol
    assert drawn.x1 <= union.x1 + tol and drawn.y1 <= union.y1 + tol
    # and the box is not loose either
    assert drawn.x0 <= union.x0 + 20 and drawn.x1 >= union.x1 - 20
    assert drawn.y0 <= union.y0 + 20 and drawn.y1 >= union.y1 - 20


def test_head_mask_is_a_subset_of_the_figure(palette: Palette) -> None:
    style = resolve_style(CharacterSpec(role="leader"), palette)
    placement = Placement(540, 1100, 565, -1)
    full, full_origin = figure_mask(style, placement, palette)
    head, head_origin = head_mask(style, placement, palette)
    assert 0 < (head > 0.5).sum() < (full > 0.5).sum() / 4
    # head pixels fall on figure pixels at canvas-absolute positions
    ys, xs = np.nonzero(head > 0.5)
    fy = (ys + int(head_origin.y0) - int(full_origin.y0)).astype(int)
    fx = (xs + int(head_origin.x0) - int(full_origin.x0)).astype(int)
    assert (full[fy, fx] > 0.5).mean() > 0.98
    boxes = figure_boxes(style, placement)
    assert head_origin.x0 <= boxes.head.x0 and head_origin.x1 >= boxes.head.x1


# --------------------------------------------------------------------------------------
# Overlap checks (FR-48, AC-06)
# --------------------------------------------------------------------------------------


def overlaps(
    index: int,
    placed: list[Any],
    text: Any,
    theme: Theme,
    palette: Palette,
    *,
    tag: str = "",
) -> list[Issue]:
    """``check_overlaps`` with the file name filled in (``tag`` and ``file`` are required there)."""
    return check_overlaps(index, placed, text, theme, palette, tag=tag, file="script.json")


def test_reference_group_has_no_overlaps(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:  # AC-06
    placed = place("centre_pair", REF_SPECS, 1100)
    issues = overlaps(
        0, styled(placed, palette), ref_text(make_slide, theme), theme, palette, tag=REF_TAG
    )
    assert issues == []


def test_reference_head_boxes_are_inside_the_frame(palette: Palette) -> None:
    for p in place("centre_pair", REF_SPECS, 1100):
        head = figure_boxes(resolve_style(p.spec, palette), p.placement).head
        assert head.inside(FRAME_INNER)


def test_flag_over_seal_reported(theme: Theme, palette: Palette, make_slide: SlideFactory) -> None:
    spec = CharacterSpec(role="leader", x=100, baseline=1000, height=565, facing=1)
    placed = place(None, [spec], 1000)
    text = plan_text(make_slide("A"), theme)
    issues = overlaps(0, styled(placed, palette), text, theme, palette)
    assert any("overlaps seal" in i.message for i in issues)
    assert all(i.path == "slides[0].scene.characters[0]" and i.severity == "error" for i in issues)


def test_overlap_message_names_both_boxes(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    spec = CharacterSpec(role="leader", x=100, baseline=1000, height=565, facing=1)
    issues = overlaps(
        0,
        styled(place(None, [spec], 1000), palette),
        plan_text(make_slide("A"), theme),
        theme,
        palette,
    )
    seal = next(i for i in issues if "overlaps seal" in i.message)
    assert "character box (" in seal.message and "seal box (92" in seal.message


def test_character_over_tag_reported(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    spec = CharacterSpec(role="leader", x=700, baseline=700, height=565, facing=1)
    issues = overlaps(
        0,
        styled(place(None, [spec], 700), palette),
        plan_text(make_slide("A"), theme),
        theme,
        palette,
        tag=REF_TAG,
    )
    assert any("overlaps tag" in i.message for i in issues)


def test_character_over_title_reported(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    spec = CharacterSpec(role="general", x=540, baseline=1350, height=475, facing=1)
    issues = overlaps(
        0, styled(place(None, [spec], 1350), palette), ref_text(make_slide, theme), theme, palette
    )
    assert any("overlaps title" in i.message for i in issues)


def test_character_over_subtitle_reported(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    text = ref_text(make_slide, theme)
    assert text.subtitle_box is not None
    spec = CharacterSpec(
        role="general", x=540, baseline=text.subtitle_box.y1 + 5, height=200, facing=1, prop="none"
    )
    issues = overlaps(0, styled(place(None, [spec], 0), palette), text, theme, palette)
    assert any("overlaps subtitle" in i.message for i in issues)


@pytest.mark.parametrize("x", [20, 1060])
def test_head_outside_frame_reported(
    x: float, theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    spec = CharacterSpec(role="general", x=x, baseline=1100, height=475, facing=1, prop="none")
    issues = overlaps(
        0,
        styled(place(None, [spec], 1100), palette),
        plan_text(make_slide("A"), theme),
        theme,
        palette,
    )
    assert any("outside the frame" in i.message for i in issues)


def test_head_overlap_reported(theme: Theme, palette: Palette, make_slide: SlideFactory) -> None:
    back = CharacterSpec(role="general", x=540, baseline=1100, height=475, facing=1)
    # the front character stands right in front of the back one and covers its head
    front = CharacterSpec(role="leader", x=540, baseline=1106, height=700, facing=1)
    placed = place(None, [back, front], 1100)
    issues = overlaps(0, styled(placed, palette), plan_text(make_slide("A"), theme), theme, palette)
    covers = [i for i in issues if "covers the head" in i.message]
    assert len(covers) == 1
    assert covers[0].path == "slides[0].scene.characters[1]"
    assert "slides[0].scene.characters[0]" in covers[0].message


def test_head_behind_a_later_character_head_order_matters(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    back = CharacterSpec(role="general", x=540, baseline=1100, height=475, facing=1)
    front = CharacterSpec(role="leader", x=540, baseline=1106, height=700, facing=1)
    # drawn the other way round, the tall one is behind and nothing covers its head
    placed = place(None, [front, back], 1100)
    issues = overlaps(0, styled(placed, palette), plan_text(make_slide("A"), theme), theme, palette)
    assert not [i for i in issues if "covers the head" in i.message]


def test_empty_tag_adds_no_tag_check(
    theme: Theme, palette: Palette, make_slide: SlideFactory
) -> None:
    spec = CharacterSpec(role="leader", x=700, baseline=700, height=565, facing=1)
    issues = overlaps(
        0,
        styled(place(None, [spec], 700), palette),
        plan_text(make_slide("A"), theme),
        theme,
        palette,
        tag="",
    )
    assert not any("overlaps tag" in i.message for i in issues)


# --------------------------------------------------------------------------------------
# check_all integration
# --------------------------------------------------------------------------------------


def load(tmp_script: ScriptFactory, slides: list[dict[str, Any]]) -> Any:
    return load_script(tmp_script(slides=slides))[0]


def layer_slide(layers: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"title": "Hai Bà Trưng", "scene": {"layers": layers}, **extra}


def issue_pairs(issues: list[Issue]) -> list[tuple[str, str]]:
    return [(i.path, i.message) for i in issues]


def test_check_all_accepts_reference_formation(tmp_script: ScriptFactory, theme: Theme) -> None:
    items = [{"role": r} for r in REF_ROLES]
    slide = layer_slide([{"type": "characters", "formation": "centre_pair", "items": items}])
    slide.update(tag=REF_TAG, subtitle=REF_SUBTITLE, title=REF_TITLE)
    assert check_all(load(tmp_script, [slide]), theme) == []


def test_check_all_reports_layer_item_path(tmp_script: ScriptFactory, theme: Theme) -> None:
    items = [
        {"role": "general", "x": 540, "baseline": 1100, "height": 475},
        {"role": "leader", "x": 540, "baseline": 1106, "height": 700},
    ]
    slide = layer_slide([{"type": "ground", "y": 1100}, {"type": "characters", "items": items}])
    issues = check_all(load(tmp_script, [slide]), theme)
    paths = [i.path for i in issues if "covers the head" in i.message]
    assert paths == ["slides[0].scene.layers[1].items[1]"]


def test_check_all_formation_count(tmp_script: ScriptFactory, theme: Theme) -> None:
    items = [{"role": "general"}] * 7
    slide = layer_slide([{"type": "characters", "formation": "centre_pair", "items": items}])
    issues = check_all(load(tmp_script, [slide]), theme)
    assert issue_pairs(issues) == [
        ("slides[0].scene.layers[0].items", "formation centre_pair supports 1–6 characters")
    ]


def test_check_all_items_without_formation_need_x(tmp_script: ScriptFactory, theme: Theme) -> None:
    slide = layer_slide([{"type": "characters", "items": [{"role": "general"}]}])
    issues = check_all(load(tmp_script, [slide]), theme)
    assert issue_pairs(issues) == [
        ("slides[0].scene.layers[0].items[0].x", "needs x without a formation")
    ]


def test_check_all_layer_baseline_applies_to_items(tmp_script: ScriptFactory, theme: Theme) -> None:
    items = [{"role": "general", "x": 540, "height": 475}]
    slide = layer_slide([{"type": "characters", "baseline": 1400, "items": items}])
    issues = check_all(load(tmp_script, [slide]), theme)
    assert any(
        i.path == "slides[0].scene.layers[0].items[0]" and "overlaps title" in i.message
        for i in issues
    )


def test_check_all_expands_template_scenes(tmp_script: ScriptFactory, theme: Theme) -> None:
    roles = [{"role": "leader"}] * 2 + [{"role": "general_alt"}] * 2
    slide = {"title": "A", "scene": {"template": "group", "characters": roles}}
    assert check_all(load(tmp_script, [slide]), theme) == []


def test_check_all_reports_template_overlaps_with_script_paths(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    """A third character in a centre pair stands in the middle, in front of a head (FR-48)."""
    slide = {"title": "A", "scene": {"template": "group", "characters": [{"role": "leader"}] * 3}}
    issues = check_all(load(tmp_script, [slide]), theme)
    assert issues
    assert all(i.severity == "error" and "head" in i.message for i in issues)
    assert {i.path for i in issues} <= {f"slides[0].scene.characters[{k}]" for k in range(3)}


def test_check_all_passes_the_slide_tag_to_the_overlap_check(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    """The tag pill sits in the header; a tall flag on the right runs into it (FR-48)."""
    crew = {"role": "leader", "x": 700, "baseline": 700, "height": 565, "facing": 1}
    layers = [{"type": "characters", "items": [crew]}]
    with_tag = layer_slide(layers, tag=REF_TAG)
    without = layer_slide(layers)
    hit = [i.message for i in check_all(load(tmp_script, [with_tag]), theme)]
    assert any("overlaps tag" in m for m in hit)
    assert not any(
        "overlaps tag" in i.message for i in check_all(load(tmp_script, [without]), theme)
    )
