"""Script, scene, layer and character parsing (FR-10..13, FR-30..34, FR-83, AC-11)."""

from __future__ import annotations

import dataclasses
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts.config import (
    LAYER_TYPES,
    ROLE_NAMES,
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
    LotusLayer,
    MountainsLayer,
    PeakItem,
    PeaksLayer,
    RiverLayer,
    Script,
    SunLayer,
    TemplateScene,
    load_script,
    slide_duration,
)
from history_shorts.errors import ValidationFailed

ScriptFactory = Callable[..., Path]


def _errors(path: Path) -> list[str]:
    with pytest.raises(ValidationFailed) as exc:
        load_script(path)
    return [i.format() for i in exc.value.issues.errors]


def _layer_scene(tmp_script: ScriptFactory, *layers: dict[str, Any]) -> LayerScene:
    script, _ = load_script(tmp_script(slides=[{"title": "A", "scene": {"layers": list(layers)}}]))
    scene = script.slides[0].scene
    assert isinstance(scene, LayerScene)
    return scene


def _one_slide_errors(tmp_script: ScriptFactory, slide: dict[str, Any]) -> list[str]:
    return _errors(tmp_script(slides=[{"title": "A", **slide}]))


# -- examples and AC-11 ------------------------------------------------------------------


def test_examples_load(repo_root: Path) -> None:
    s, _ = load_script(repo_root / "examples/nu_tuong/script.json")
    assert len(s.slides) == 5
    m, _ = load_script(repo_root / "examples/me_linh/script.json")
    assert len(m.slides) == 6
    first = s.slides[0].scene
    assert isinstance(first, TemplateScene) and first.template == "group"
    assert first.characters is not None and len(first.characters) == 6
    assert first.sun is True and first.moon is True and first.seed is None
    landscape = m.slides[0].scene
    assert isinstance(landscape, TemplateScene) and landscape.boats is not None
    assert landscape.boats[0].crew[1] == CharacterSpec(role="boat_crew", facing=-1)
    assert m.slides[1].scene == TemplateScene(template="landscape", characters=None, boats=())
    assert m.slides[3].scene.moon is False  # type: ignore[union-attr]
    assert s.slides[4].scene is None


def test_examples_have_expected_warnings(repo_root: Path) -> None:
    _, warnings = load_script(repo_root / "examples/me_linh/script.json")
    assert warnings == []


def test_three_errors_all_reported(repo_root: Path) -> None:  # AC-11
    assert sorted(_errors(repo_root / "tests/data/three_errors.json")) == [
        "three_errors.json › slides[0].title: required",
        "three_errors.json › slides[1].duration: must be 0.5–15",
        "three_errors.json › slides[2].scene.layers[0].x: must be 0–1080",
    ]


def test_script_is_frozen_and_slotted(tmp_script: ScriptFactory) -> None:
    script, _ = load_script(tmp_script())
    assert isinstance(script, Script)
    with pytest.raises(dataclasses.FrozenInstanceError):
        script.title = "x"  # type: ignore[misc]
    assert not hasattr(script, "__dict__")
    assert script.path.name == "script.json" and script.path.is_absolute()


# -- warnings (FR-13) --------------------------------------------------------------------


def test_missing_sources_and_unsourced_claim_only_warn(tmp_script: ScriptFactory) -> None:
    slides = [{"title": "A", "duration": 15, "claim": True}]
    _, w = load_script(tmp_script(sources=None, slides=slides))
    assert {i.path for i in w} == {"sources", "slides[0].source"}
    assert all(i.severity == "warning" for i in w)


def test_unknown_keys_warn(tmp_script: ScriptFactory) -> None:
    path = tmp_script(
        slides=[
            {
                "title": "A",
                "duration": 15,
                "colour": "red",
                "scene": {"template": "group", "wat": 1},
            }
        ],
        extra={"author": "x"},
    )
    _, w = load_script(path)
    assert {(i.path, i.message) for i in w} == {
        ("author", "unknown key (ignored)"),
        ("slides[0].colour", "unknown key (ignored)"),
        ("slides[0].scene.wat", "unknown key (ignored)"),
    }


def test_total_duration_warning(tmp_script: ScriptFactory) -> None:
    _, w = load_script(tmp_script(slides=[{"title": "A"}, {"title": "B"}]))
    assert [i.message for i in w] == ["total duration 5.0 s is outside 15–90 s"]


def test_total_duration_in_range_is_silent(tmp_script: ScriptFactory) -> None:
    slides = [{"title": "A", "duration": 5}] * 4
    assert load_script(tmp_script(slides=slides))[1] == []


def test_sourced_claim_is_silent(tmp_script: ScriptFactory) -> None:
    slides = [{"title": "A", "duration": 15, "claim": True, "source": 0}]
    assert load_script(tmp_script(slides=slides))[1] == []


# -- top-level and slide fields ----------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "msg"),
    [
        ("tag", "X" * 29, "must be at most 28 characters"),
        ("title", "X" * 61, "must be at most 60 characters"),
        ("subtitle", "X" * 121, "must be at most 120 characters"),
        ("title", "Hai Bà 🔥", "emoji are not supported (U+1F525)"),
        ("tag", "A‍B", "emoji are not supported (U+200D)"),
        ("subtitle", "Sao ★ ☀", "emoji are not supported (U+2605)"),
        ("source", 5, "index out of range (sources has 1 item)"),
        ("source", -1, "must be an integer ≥ 0"),
        ("duration", 0.4, "must be 0.5–15"),
        ("motion", "pan", "must be one of none, zoom_in"),
        ("claim", "yes", "must be true or false"),
        ("title", "", "must be a non-empty string"),
        ("scene", [], "must be an object"),
    ],
)
def test_slide_field_errors(tmp_script: ScriptFactory, field: str, value: object, msg: str) -> None:
    errors = _one_slide_errors(tmp_script, {field: value})
    assert errors == [f"script.json › slides[0].{field}: {msg}"]


def test_max_lengths_are_accepted(tmp_script: ScriptFactory) -> None:
    slide = {"tag": "X" * 28, "title": "X" * 60, "subtitle": "X" * 120}
    script, _ = load_script(tmp_script(slides=[slide]))
    assert len(script.slides[0].title) == 60


def test_source_range_with_empty_sources(tmp_script: ScriptFactory) -> None:
    errors = _errors(tmp_script(sources=[], slides=[{"title": "A", "source": 0}]))
    assert errors == ["script.json › slides[0].source: index out of range (sources has 0 items)"]


def test_slide_defaults(tmp_script: ScriptFactory) -> None:
    script, _ = load_script(tmp_script())
    slide = script.slides[0]
    assert (slide.tag, slide.subtitle, slide.duration, slide.scene) == ("", "", None, None)
    assert (slide.motion, slide.claim, slide.source) == ("none", False, None)
    assert script.sources == ("Nguồn thử nghiệm",)


def test_nfd_text_normalised_to_nfc(tmp_script: ScriptFactory) -> None:  # Review Focus 2
    nfd = unicodedata.normalize("NFD", "Trưng Trắc")
    assert nfd != "Trưng Trắc"
    s, _ = load_script(
        tmp_script(
            title=unicodedata.normalize("NFD", "Hai Bà"),
            sources=[unicodedata.normalize("NFD", "Nguồn")],
            slides=[{"title": nfd, "tag": nfd, "subtitle": nfd}],
        )
    )
    slide = s.slides[0]
    assert (slide.title, slide.tag, slide.subtitle) == ("Trưng Trắc",) * 3
    assert s.title == "Hai Bà" and s.sources == ("Nguồn",)


def test_length_is_measured_after_nfc(tmp_script: ScriptFactory) -> None:
    nfd = unicodedata.normalize("NFD", "ế" * 60)
    assert len(nfd) > 60
    script, _ = load_script(tmp_script(slides=[{"title": nfd}]))
    assert len(script.slides[0].title) == 60


@pytest.mark.parametrize(("count", "ok"), [(0, False), (1, True), (30, True), (31, False)])
def test_slide_count_bounds(tmp_script: ScriptFactory, count: int, ok: bool) -> None:
    path = tmp_script(slides=[{"title": "A"}] * count)
    if ok:
        assert len(load_script(path)[0].slides) == count
    else:
        assert _errors(path) == ["script.json › slides: must contain 1–30 slides"]


def test_top_level_errors(tmp_script: ScriptFactory) -> None:
    path = tmp_script(slides="nope", sources=[1, ""], extra={"schema_version": "1.1", "title": ""})
    assert sorted(_errors(path)) == [
        'script.json › schema_version: unsupported schema_version "1.1" (expected "2.0")',
        "script.json › slides: must be an array",
        "script.json › sources[0]: must be a non-empty string",
        "script.json › sources[1]: must be a non-empty string",
        "script.json › title: must be a non-empty string",
    ]


def test_missing_required_top_level_keys(tmp_path: Path) -> None:
    path = tmp_path / "script.json"
    path.write_text("{}", encoding="utf-8")
    assert sorted(_errors(path)) == [
        "script.json › schema_version: required",
        "script.json › slides: required",
        "script.json › title: required",
    ]


def test_bad_json_and_missing_file(tmp_path: Path) -> None:
    bad = tmp_path / "script.json"
    bad.write_text("{", encoding="utf-8")
    assert "invalid JSON at line 1" in _errors(bad)[0]
    assert "file not found" in _errors(tmp_path / "nope.json")[0]


def test_utf8_bom_script_loads(tmp_script: ScriptFactory) -> None:  # Review Focus 3
    script, _ = load_script(tmp_script(bom=True, title="Mê Linh"))
    assert script.title == "Mê Linh"


def test_slides_collect_errors_across_slides(tmp_script: ScriptFactory) -> None:
    slides = [{"title": "A", "duration": 0}, {"title": "B", "duration": 16}]
    assert sorted(_errors(tmp_script(slides=slides))) == [
        "script.json › slides[0].duration: must be 0.5–15",
        "script.json › slides[1].duration: must be 0.5–15",
    ]


# -- auto-duration (FR-83) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "subtitle", "expected"),
    [("Ab", "", 2.5), ("X" * 40, "Y" * 40, 6.0), ("X" * 30, "Y" * 10, 3.2)],
)
def test_auto_duration(
    make_slide: Callable[..., Any], title: str, subtitle: str, expected: float
) -> None:
    assert slide_duration(make_slide(title, subtitle), fps=30) == pytest.approx(expected)


def test_auto_duration_ignores_newlines(make_slide: Callable[..., Any]) -> None:
    plain = make_slide("X" * 30, "Y" * 10)
    broken = make_slide("X" * 15 + "\n" + "X" * 15, "Y" * 5 + "\n" + "Y" * 5)
    assert slide_duration(plain, fps=30) == slide_duration(broken, fps=30)


def test_duration_rounds_to_frame(make_slide: Callable[..., Any]) -> None:
    assert slide_duration(make_slide("A", duration=3.14), fps=10) == pytest.approx(3.1)
    assert slide_duration(make_slide("A", duration=3.14), fps=30) == pytest.approx(94 / 30)
    # 34 chars * 0.08 = 2.72 s -> 2.7 at 10 fps
    assert slide_duration(make_slide("X" * 34), fps=10) == pytest.approx(2.7)


def test_explicit_duration_beats_auto(make_slide: Callable[..., Any]) -> None:
    assert slide_duration(make_slide("X" * 80, duration=1.0), fps=30) == pytest.approx(1.0)


# -- templates (FR-30, FR-33) ------------------------------------------------------------


def test_template_scene_params(tmp_script: ScriptFactory) -> None:
    scene = {
        "template": "group",
        "characters": [{"role": "leader", "facing": -1, "robe": "gold", "prop": "none"}],
        "sun": False,
        "seed": 7,
    }
    script, _ = load_script(tmp_script(slides=[{"title": "A", "scene": scene}]))
    parsed = script.slides[0].scene
    assert parsed == TemplateScene(
        template="group",
        characters=(CharacterSpec(role="leader", facing=-1, robe="gold", prop="none"),),
        boats=None,
        sun=False,
        moon=True,
        seed=7,
    )


def test_template_landscape_boats(tmp_script: ScriptFactory) -> None:
    boat = {
        "x": 290,
        "y": 1056,
        "scale": 1.5,
        "crew": [{"role": "boat_crew", "x": 300, "baseline": 1000, "height": 400, "crew": 1}],
    }
    script, w = load_script(
        tmp_script(slides=[{"title": "A", "scene": {"template": "landscape", "boats": [boat]}}])
    )
    scene = script.slides[0].scene
    assert isinstance(scene, TemplateScene) and scene.boats is not None
    assert scene.boats[0].crew == (
        CharacterSpec(role="boat_crew", x=300.0, baseline=1000.0, height=400.0),
    )
    assert any(i.path == "slides[0].scene.boats[0].crew[0].crew" for i in w)


def test_template_errors(tmp_script: ScriptFactory) -> None:
    base = {"title": "A"}
    assert _errors(tmp_script(slides=[{**base, "scene": {"template": "zebra"}}])) == [
        "script.json › slides[0].scene.template: must be one of group, landscape"
    ]
    assert _errors(tmp_script(slides=[{**base, "scene": {}}])) == [
        "script.json › slides[0].scene: needs 'template' or 'layers'"
    ]
    both = {"template": "group", "layers": []}
    assert _errors(tmp_script(slides=[{**base, "scene": both}])) == [
        "script.json › slides[0].scene: give either 'template' or 'layers', not both"
    ]
    assert _errors(tmp_script(slides=[{**base, "scene": {"template": "group", "sun": 1}}])) == [
        "script.json › slides[0].scene.sun: must be true or false"
    ]


def test_template_mismatched_params_warn(tmp_script: ScriptFactory) -> None:
    scene = {"template": "landscape", "characters": [{"role": "leader"}]}
    _, w = load_script(tmp_script(slides=[{"title": "A", "scene": scene}]))
    assert [(i.path, i.message) for i in w if i.path.endswith("characters")] == [
        ("slides[0].scene.characters", "not used by template landscape (ignored)")
    ]


# -- characters --------------------------------------------------------------------------


def test_unknown_role(tmp_script: ScriptFactory) -> None:
    scene = {"template": "group", "characters": [{"role": "king"}]}
    assert _one_slide_errors(tmp_script, {"scene": scene}) == [
        "script.json › slides[0].scene.characters[0].role: "
        "must be one of leader, general, general_alt, boat_crew"
    ]
    assert ROLE_NAMES == ("leader", "general", "general_alt", "boat_crew")


def test_character_field_errors(tmp_script: ScriptFactory) -> None:
    character = {
        "role": "leader",
        "facing": 0,
        "prop": "sword",
        "crest": "yes",
        "robe": "",
        "x": 1081,
        "baseline": -1,
        "height": 0,
        "seed": -3,
    }
    scene = {"template": "group", "characters": [character]}
    prefix = "script.json › slides[0].scene.characters[0]."
    assert sorted(_one_slide_errors(tmp_script, {"scene": scene})) == sorted(
        [
            prefix + "facing: must be -1 or 1",
            prefix + "prop: must be one of flag, spear, oar, none",
            prefix + "crest: must be true or false",
            prefix + "robe: must be a non-empty string",
            prefix + "x: must be 0–1080",
            prefix + "baseline: must be 0–1920",
            prefix + "height: must be > 0",
            prefix + "seed: must be an integer ≥ 0",
        ]
    )


def test_character_role_is_required_and_must_be_object(tmp_script: ScriptFactory) -> None:
    scene = {"template": "group", "characters": [{}, "leader"]}
    assert sorted(_one_slide_errors(tmp_script, {"scene": scene})) == [
        "script.json › slides[0].scene.characters[0].role: required",
        "script.json › slides[0].scene.characters[1]: must be an object",
    ]


def test_characters_must_be_array(tmp_script: ScriptFactory) -> None:
    scene = {"template": "group", "characters": {"role": "leader"}}
    assert _one_slide_errors(tmp_script, {"scene": scene}) == [
        "script.json › slides[0].scene.characters: must be an array"
    ]


# -- layers ------------------------------------------------------------------------------


def test_every_layer_type_parses(tmp_script: ScriptFactory) -> None:
    scene = _layer_scene(
        tmp_script,
        {"type": "sun", "x": 540, "y": 650, "r": 300, "rings": 2, "tile": 20, "worn": 0.1},
        {"type": "moon", "x": 770, "y": 450, "r": 125},
        {
            "type": "clouds",
            "items": [
                {"x": 200, "y": 300, "scale": 1.2, "flip": -1},
                {"x": 800, "y": 320, "scale": 1},
            ],
            "outline": "gold_dk",
            "cell": 12,
            "gap": 0.8,
        },
        {"type": "mountains", "y": 780, "amp": 60},
        {
            "type": "peaks",
            "y": 900,
            "items": [{"x": 300, "height": 400, "width": 200}],
            "fill": "eggshell",
            "cell": 10,
        },
        {"type": "hills", "side": "left", "base": 1100, "top": 700, "gap": 1.5},
        {"type": "river", "y": 940},
        {"type": "ground", "y": 1092, "height": 60},
        {
            "type": "characters",
            "formation": "centre_pair",
            "items": [{"role": "leader"}, {"role": "general", "x": 100}],
        },
        {"type": "boat", "x": 290, "y": 1056, "scale": 1.5, "crew": [{"role": "boat_crew"}]},
        {"type": "birds", "items": [{"x": 100, "y": 200, "scale": 0.8}]},
        {"type": "lotus", "x": 900, "y": 1500, "scale": 2},
    )
    sun, moon, clouds, mountains, peaks, hills, river, ground, chars, boat, birds, lotus = (
        scene.layers
    )
    assert sun == SunLayer(kind="sun", x=540, y=650, r=300, rings=2, tile=20, worn=0.1)
    assert moon == SunLayer(kind="moon", x=770, y=450, r=125, rings=0, tile=None, worn=None)
    assert clouds == CloudsLayer(
        items=(CloudItem(200, 300, 1.2, -1), CloudItem(800, 320, 1.0, 1)),
        outline="gold_dk",
        cell=12,
        gap=0.8,
    )
    assert mountains == MountainsLayer(y=780, amp=60)
    assert peaks == PeaksLayer(
        y=900, items=(PeakItem(300, 400, 200),), fill="eggshell", cell=10, gap=None
    )
    assert hills == HillsLayer(side="left", base=1100, top=700, cell=None, gap=1.5)
    assert river == RiverLayer(y=940, height=290)
    assert ground == GroundLayer(y=1092, height=60)
    assert chars == CharactersLayer(
        formation="centre_pair",
        baseline=1100,
        items=(CharacterSpec(role="leader"), CharacterSpec(role="general", x=100)),
    )
    assert boat == BoatLayer(x=290, y=1056, scale=1.5, crew=(CharacterSpec(role="boat_crew"),))
    assert birds == BirdsLayer(items=(BirdItem(100, 200, 0.8),))
    assert lotus == LotusLayer(x=900, y=1500, scale=2)


def test_layer_defaults(tmp_script: ScriptFactory) -> None:
    scene = _layer_scene(
        tmp_script,
        {"type": "river", "y": 940},
        {"type": "ground", "y": 1092},
        {"type": "characters", "items": [{"role": "leader", "x": 540}]},
        {"type": "clouds", "items": []},
        {"type": "peaks", "y": 900, "items": []},
    )
    river, ground, chars, clouds, peaks = scene.layers
    assert isinstance(river, RiverLayer) and river.height == 290
    assert isinstance(ground, GroundLayer) and ground.height == 52
    assert isinstance(chars, CharactersLayer)
    assert chars.baseline == 1100 and chars.formation is None
    assert isinstance(clouds, CloudsLayer) and clouds.outline == "gold"
    assert isinstance(peaks, PeaksLayer) and peaks.fill == "gradient"


def test_character_baseline_precedence(tmp_script: ScriptFactory) -> None:
    scene = _layer_scene(
        tmp_script,
        {"type": "characters", "items": [{"role": "leader", "x": 100}]},
        {"type": "characters", "baseline": 900, "items": [{"role": "leader", "baseline": 800}]},
    )
    plain, explicit = scene.layers
    assert isinstance(plain, CharactersLayer) and isinstance(explicit, CharactersLayer)
    assert plain.items[0].baseline is None  # item without baseline: resolved later
    assert plain.baseline == 1100  # layer default
    assert explicit.baseline == 900  # explicit layer baseline preserved
    assert explicit.items[0].baseline == 800  # item's own baseline preserved


def test_characters_layer_positional_field_order() -> None:
    specs = (CharacterSpec(role="leader"),)
    layer = CharactersLayer("centre_pair", 1100, specs)
    assert (layer.formation, layer.baseline, layer.items) == ("centre_pair", 1100, specs)
    assert CharactersLayer("line").items == () and CharactersLayer("line").baseline == 1100


def test_layer_types_registry() -> None:
    assert list(LAYER_TYPES) == [
        "sun",
        "moon",
        "clouds",
        "mountains",
        "peaks",
        "hills",
        "river",
        "ground",
        "characters",
        "boat",
        "birds",
        "lotus",
    ]
    assert LAYER_TYPES["sun"] is SunLayer and LAYER_TYPES["moon"] is SunLayer
    assert LAYER_TYPES["boat"] is BoatLayer


def test_unknown_layer_type_lists_allowed(tmp_script: ScriptFactory) -> None:
    scene = {"layers": [{"type": "dragon"}]}
    (error,) = _one_slide_errors(tmp_script, {"scene": scene})
    assert error.startswith("script.json › slides[0].scene.layers[0].type: unknown layer type")
    assert error.endswith(
        "allowed: sun, moon, clouds, mountains, peaks, hills, river, ground, "
        "characters, boat, birds, lotus"
    )


def test_layer_missing_type_and_not_object(tmp_script: ScriptFactory) -> None:
    scene = {"layers": [{"x": 1}, 5]}
    assert sorted(_one_slide_errors(tmp_script, {"scene": scene})) == [
        "script.json › slides[0].scene.layers[0].type: required",
        "script.json › slides[0].scene.layers[1]: must be an object",
    ]


def test_empty_layers_rejected(tmp_script: ScriptFactory) -> None:
    assert _one_slide_errors(tmp_script, {"scene": {"layers": []}}) == [
        "script.json › slides[0].scene.layers: must be a non-empty array"
    ]
    assert _one_slide_errors(tmp_script, {"scene": {"layers": "x"}}) == [
        "script.json › slides[0].scene.layers: must be an array"
    ]


@pytest.mark.parametrize(
    ("layer", "path", "msg"),
    [
        ({"type": "sun", "x": 2000, "y": 1, "r": 1}, "x", "must be 0–1080"),
        ({"type": "sun", "x": 1, "y": 1921, "r": 1}, "y", "must be 0–1920"),
        ({"type": "sun", "x": 1, "y": 1, "r": 0}, "r", "must be > 0"),
        ({"type": "sun", "x": 1, "y": 1, "r": 1, "rings": 3}, "rings", "must be an integer 0–2"),
        ({"type": "sun", "x": 1, "y": 1, "r": 1, "worn": 2}, "worn", "must be 0–1"),
        ({"type": "sun", "x": 1, "y": 1, "r": 1, "tile": 0}, "tile", "must be an integer ≥ 1"),
        ({"type": "sun", "x": 1, "y": 1}, "r", "required"),
        ({"type": "sun", "x": "1", "y": 1, "r": 1}, "x", "must be 0–1080"),
        ({"type": "river"}, "y", "required"),
        ({"type": "river", "y": 5, "height": -4}, "height", "must be > 0"),
        (
            {"type": "hills", "side": "middle", "base": 1, "top": 1},
            "side",
            "must be one of left, right",
        ),
        ({"type": "mountains", "y": 1, "amp": 0}, "amp", "must be > 0"),
        (
            {"type": "clouds", "items": [], "outline": "red"},
            "outline",
            "must be one of gold, gold_dk",
        ),
        (
            {"type": "peaks", "y": 1, "items": [], "fill": "x"},
            "fill",
            "must be one of gradient, eggshell",
        ),
        (
            {"type": "clouds", "items": [{"x": 1, "y": 1, "scale": 1, "flip": 2}]},
            "items[0].flip",
            "must be -1 or 1",
        ),
        (
            {"type": "clouds", "items": [{"x": 1, "y": 1, "scale": 0}]},
            "items[0].scale",
            "must be > 0",
        ),
        (
            {"type": "peaks", "y": 1, "items": [{"x": 1, "height": 1}]},
            "items[0].width",
            "required",
        ),
        ({"type": "birds", "items": [{"y": 1}]}, "items[0].x", "required"),
        ({"type": "birds"}, "items", "required"),
        (
            {"type": "boat", "x": 1, "y": 1, "crew": [{"role": "nope"}]},
            "crew[0].role",
            "must be one of leader, general, general_alt, boat_crew",
        ),
        ({"type": "lotus", "x": 1, "y": 1, "scale": -1}, "scale", "must be > 0"),
        (
            {"type": "characters", "formation": "circle", "items": []},
            "formation",
            "must be one of centre_pair, line, v_shape",
        ),
        ({"type": "characters", "baseline": 3000, "items": []}, "baseline", "must be 0–1920"),
    ],
)
def test_layer_field_errors(
    tmp_script: ScriptFactory, layer: dict[str, Any], path: str, msg: str
) -> None:
    errors = _one_slide_errors(tmp_script, {"scene": {"layers": [layer]}})
    assert f"script.json › slides[0].scene.layers[0].{path}: {msg}" in errors


def test_characters_layer_needs_formation_or_items(tmp_script: ScriptFactory) -> None:
    errors = _one_slide_errors(tmp_script, {"scene": {"layers": [{"type": "characters"}]}})
    assert errors == ["script.json › slides[0].scene.layers[0]: needs 'formation' or 'items'"]


def test_formation_alone_is_accepted(tmp_script: ScriptFactory) -> None:
    scene = _layer_scene(tmp_script, {"type": "characters", "formation": "v_shape"})
    layer = scene.layers[0]
    assert isinstance(layer, CharactersLayer) and layer.items == ()


def test_peaks_cell_with_gradient_fill_warns(tmp_script: ScriptFactory) -> None:
    layer = {"type": "peaks", "y": 1, "items": [], "cell": 8}
    path = tmp_script(slides=[{"title": "A", "scene": {"layers": [layer]}}])
    _, w = load_script(path)
    assert [(i.path, i.message) for i in w if "cell" in i.path] == [
        ("slides[0].scene.layers[0].cell", "only used with fill eggshell (ignored)")
    ]


def test_unknown_layer_key_warns(tmp_script: ScriptFactory) -> None:
    layer = {"type": "lotus", "x": 1, "y": 1, "scale": 1, "glow": True}
    path = tmp_script(slides=[{"title": "A", "scene": {"layers": [layer]}}])
    _, w = load_script(path)
    assert ("slides[0].scene.layers[0].glow", "unknown key (ignored)") in {
        (i.path, i.message) for i in w
    }


def test_layer_coordinate_boundaries_are_inclusive(tmp_script: ScriptFactory) -> None:
    scene = _layer_scene(
        tmp_script,
        {"type": "lotus", "x": 0, "y": 0, "scale": 0.1},
        {"type": "lotus", "x": 1080, "y": 1920, "scale": 0.1},
    )
    assert len(scene.layers) == 2


# -- numeric edge cases: no crash, always a path-tracked error ---------------------------

HUGE = 10**400  # beyond float range

_NUMERIC_BAD_VALUES = [
    pytest.param(float("nan"), id="NaN"),
    pytest.param(float("inf"), id="Infinity"),
    pytest.param(True, id="bool"),
    pytest.param(HUGE, id="huge-int"),
]


def _edge_script(tmp_script: ScriptFactory, where: str, key: str, value: object) -> Path:
    """A script with ``value`` at ``key`` in a slide / layer / character / template."""
    slide: dict[str, Any] = {"title": "A"}
    layer = {"type": "lotus", "x": 1, "y": 1, "scale": 1}
    character = {"role": "leader"}
    if where == "slide":
        slide[key] = value
    elif where == "layer":
        slide["scene"] = {"layers": [{**layer, key: value}]}
    elif where == "character":
        slide["scene"] = {"template": "group", "characters": [{**character, key: value}]}
    else:
        slide["scene"] = {"template": "group", key: value}
    return tmp_script(slides=[slide])


@pytest.mark.parametrize("value", _NUMERIC_BAD_VALUES)
@pytest.mark.parametrize(
    ("where", "key", "path", "msg"),
    [
        ("slide", "duration", "slides[0].duration", "must be 0.5–15"),
        ("layer", "x", "slides[0].scene.layers[0].x", "must be 0–1080"),
        ("layer", "y", "slides[0].scene.layers[0].y", "must be 0–1920"),
        ("layer", "scale", "slides[0].scene.layers[0].scale", "must be > 0"),
        ("character", "x", "slides[0].scene.characters[0].x", "must be 0–1080"),
        ("character", "height", "slides[0].scene.characters[0].height", "must be > 0"),
    ],
)
def test_bad_numbers_are_validation_errors(
    tmp_script: ScriptFactory, where: str, key: str, path: str, msg: str, value: object
) -> None:
    assert _errors(_edge_script(tmp_script, where, key, value)) == [f"script.json › {path}: {msg}"]


@pytest.mark.parametrize(
    ("where", "key", "value", "path", "msg"),
    [
        ("slide", "source", True, "slides[0].source", "must be an integer ≥ 0"),
        ("slide", "source", HUGE, "slides[0].source", "index out of range (sources has 1 item)"),
        ("character", "seed", True, "slides[0].scene.characters[0].seed", "must be an integer ≥ 0"),
        (
            "character",
            "seed",
            float("nan"),
            "slides[0].scene.characters[0].seed",
            "must be an integer ≥ 0",
        ),
        ("template", "seed", True, "slides[0].scene.seed", "must be an integer ≥ 0"),
        ("layer", "rings", True, "slides[0].scene.layers[0].rings", "must be an integer 0–2"),
        ("character", "facing", True, "slides[0].scene.characters[0].facing", "must be -1 or 1"),
    ],
)
def test_bad_integers_are_validation_errors(
    tmp_script: ScriptFactory, where: str, key: str, value: object, path: str, msg: str
) -> None:
    if where == "layer":  # rings only exists on sun/moon
        slide = {
            "title": "A",
            "scene": {"layers": [{"type": "sun", "x": 1, "y": 1, "r": 1, key: value}]},
        }
        script = tmp_script(slides=[slide])
    else:
        script = _edge_script(tmp_script, where, key, value)
    assert _errors(script) == [f"script.json › {path}: {msg}"]


def test_bool_where_number_expected_in_ctx() -> None:
    from history_shorts.errors import Issues
    from history_shorts.validation import Ctx, is_number

    assert not is_number(True) and not is_number(HUGE) and is_number(10**300)
    issues = Issues()
    Ctx("f", issues).num({"a": HUGE}, "a")
    assert [i.format() for i in issues.errors] == ["f › a: must be a number"]


# -- cascades ----------------------------------------------------------------------------


@pytest.mark.parametrize("sources", [[1], ["ok", ""], "not a list", {"a": 1}])
def test_invalid_sources_do_not_cascade_into_source_index_errors(
    tmp_script: ScriptFactory, sources: object
) -> None:
    errors = _errors(tmp_script(sources=sources, slides=[{"title": "A", "source": 0}]))
    assert errors and all(e.startswith("script.json › sources") for e in errors)
    assert not any("index out of range" in e for e in errors)
