"""Theme loading and validation (spec 6.2, FR-11)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts.config import (
    PALETTE_FALLBACKS,
    REQUIRED_PALETTE_KEYS,
    GoldLeafSpec,
    SheenSpec,
    load_theme,
)
from history_shorts.errors import ValidationFailed

DEFAULT = Path(__file__).resolve().parent.parent / "themes" / "son_mai" / "theme.json"
TmpTheme = Callable[..., Path]


def _messages(path: Path) -> list[str]:
    with pytest.raises(ValidationFailed) as exc:
        load_theme(path)
    return [i.format() for i in exc.value.issues.errors]


def _edit(tmp_theme: TmpTheme, mutate: Callable[[dict[str, Any]], None]) -> Path:
    path = tmp_theme()
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_default_theme_values() -> None:
    theme, warnings = load_theme(DEFAULT)
    assert warnings == []
    assert theme.seed == 40 and theme.palette["gold"] == (212, 166, 76)
    assert theme.palette["egg_tone"] == (226, 212, 184)
    assert theme.type_scale.title == 92 and theme.type_scale.subtitle_min == 34
    assert theme.textures.gold_leaf == GoldLeafSpec(tile=34, worn=0.05)
    assert theme.textures.sheen == SheenSpec(330, 760, 620, 0.10)
    assert theme.chrome.seal.lines == ("SỬ", "VIỆT")
    assert theme.fonts.title.is_absolute() and theme.fonts.title.exists()
    assert theme.path == DEFAULT.resolve()


def test_palette_constants_and_api() -> None:
    assert len(REQUIRED_PALETTE_KEYS) == 13
    assert len(PALETTE_FALLBACKS) == 14
    assert set(PALETTE_FALLBACKS.values()) <= set(REQUIRED_PALETTE_KEYS)
    theme, _ = load_theme(DEFAULT)
    assert set(theme.palette.keys()) == set(REQUIRED_PALETTE_KEYS) | set(PALETTE_FALLBACKS)
    assert theme.palette.rgb01("gold") == (212 / 255, 166 / 255, 76 / 255)
    with pytest.raises(KeyError):
        theme.palette["nope"]


def test_optional_palette_key_falls_back(tmp_theme: TmpTheme) -> None:
    theme, _ = load_theme(tmp_theme(drop_palette=["egg_tone"]))
    assert theme.palette["egg_tone"] == theme.palette["egg"]


def test_all_optional_palette_keys_fall_back(tmp_theme: TmpTheme) -> None:
    theme, _ = load_theme(tmp_theme(drop_palette=list(PALETTE_FALLBACKS)))
    for optional, required in PALETTE_FALLBACKS.items():
        assert theme.palette[optional] == theme.palette[required]


def test_all_errors_reported_with_paths(tmp_theme: TmpTheme) -> None:
    msgs = _messages(
        tmp_theme(
            drop_palette=["gold"],
            palette={"black": [300, 0, 0]},
            fonts={"title": "fonts/Missing.ttf"},
        )
    )
    assert "theme.json › palette.gold: required key missing" in msgs
    assert "theme.json › palette.black: each value must be an integer 0–255" in msgs
    assert any(m.startswith("theme.json › fonts.title: file not found: /") for m in msgs)


def test_unknown_key_warns(tmp_theme: TmpTheme) -> None:
    _, warnings = load_theme(tmp_theme(extra={"colour": 1}))
    assert [w.format() for w in warnings] == ["theme.json › colour: unknown key (ignored)"]


def test_unknown_nested_key_warns_with_path(tmp_theme: TmpTheme) -> None:
    path = _edit(tmp_theme, lambda d: d["chrome"]["seal"].update(colour=1))
    _, warnings = load_theme(path)
    assert [w.format() for w in warnings] == [
        "theme.json › chrome.seal.colour: unknown key (ignored)"
    ]


def test_utf8_bom_loads(tmp_theme: TmpTheme) -> None:
    load_theme(tmp_theme(bom=True))


def test_invalid_json_reports_line_and_column(tmp_path: Path) -> None:
    p = tmp_path / "theme.json"
    p.write_text('{\n  "name": ,\n}', encoding="utf-8")
    with pytest.raises(ValidationFailed) as exc:
        load_theme(p)
    assert (
        exc.value.issues.errors[0].format()
        == "theme.json › (json): invalid JSON at line 2, column 11: Expecting value"
    )


def test_missing_theme_file_shows_absolute_path(tmp_path: Path) -> None:
    msgs = _messages(tmp_path / "nope.json")
    assert msgs == [f"nope.json › (file): file not found: {tmp_path / 'nope.json'}"]


def test_root_must_be_object(tmp_path: Path) -> None:
    p = tmp_path / "theme.json"
    p.write_text("[1, 2]", encoding="utf-8")
    assert _messages(p) == ["theme.json › (json): top level must be an object"]


def test_optional_sections_take_defaults(tmp_theme: TmpTheme) -> None:
    def drop(d: dict[str, Any]) -> None:
        for key in ("textures", "chrome", "transition", "video"):
            del d[key]

    theme, warnings = load_theme(_edit(tmp_theme, drop))
    reference, _ = load_theme(DEFAULT)
    assert warnings == []
    assert theme.textures == reference.textures
    assert theme.chrome == reference.chrome
    assert theme.transition == reference.transition
    assert theme.video == reference.video
    assert theme.video.fps == 30 and theme.video.crf == 20


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d.update(schema_version="1.0"), "theme.json › schema_version: "),
        (lambda d: d.update(name=""), "theme.json › name: must be a non-empty string"),
        (lambda d: d.update(seed=1.5), "theme.json › seed: must be an integer ≥ 0"),
        (lambda d: d.update(seed=True), "theme.json › seed: must be an integer ≥ 0"),
        (
            lambda d: d["palette"].update(gold=[1, 2]),
            "theme.json › palette.gold: must be an array of 3 integers",
        ),
        (
            lambda d: d["palette"].update(gold="red"),
            "theme.json › palette.gold: must be an array of 3 integers",
        ),
        (
            lambda d: d["palette"].update(gold=[1, 2, 3.5]),
            "theme.json › palette.gold: each value must be an integer 0–255",
        ),
        (
            lambda d: d["type_scale"].update(title_min=100),
            "theme.json › type_scale.title_min: must be ≤ title (92)",
        ),
        (
            lambda d: d["type_scale"].update(subtitle_min=47),
            "theme.json › type_scale.subtitle_min: must be ≤ subtitle (46)",
        ),
        (
            lambda d: d["type_scale"].update(tag=0),
            "theme.json › type_scale.tag: must be an integer ≥ 1",
        ),
        (
            lambda d: d["type_scale"].pop("title"),
            "theme.json › type_scale.title: required key missing",
        ),
        (
            lambda d: d["textures"]["gold_leaf"].update(worn=1.5),
            "theme.json › textures.gold_leaf.worn: must be a number 0–1",
        ),
        (
            lambda d: d["textures"]["sheen"].update(strength=0.2),
            "theme.json › textures.sheen.strength: must be a number 0–0.1",
        ),
        (
            lambda d: d["textures"]["grain"].update(strength=0.5),
            "theme.json › textures.grain.strength: must be a number 0–0.025",
        ),
        (
            lambda d: d["textures"]["eggshell"].update(cell=0),
            "theme.json › textures.eggshell.cell: must be an integer ≥ 1",
        ),
        (
            lambda d: d["textures"]["sheen"].update(r=0),
            "theme.json › textures.sheen.r: must be a number > 0",
        ),
        (
            lambda d: d["chrome"]["seal"].update(lines=[]),
            "theme.json › chrome.seal.lines: must be a non-empty array of non-empty strings",
        ),
        (
            lambda d: d["chrome"]["seal"].update(lines=["A", 3]),
            "theme.json › chrome.seal.lines[1]: must be a non-empty string",
        ),
        (
            lambda d: d["chrome"]["waves"].update(rows=0),
            "theme.json › chrome.waves.rows: must be an integer ≥ 1",
        ),
        (
            lambda d: d["chrome"]["frame"].update(enabled="yes"),
            "theme.json › chrome.frame.enabled: must be true or false",
        ),
        (
            lambda d: d["transition"].update(fade_in=-1),
            "theme.json › transition.fade_in: must be a number ≥ 0",
        ),
        (lambda d: d["video"].update(fps=0), "theme.json › video.fps: must be an integer ≥ 1"),
        (lambda d: d["video"].update(crf=52), "theme.json › video.crf: must be an integer 0–51"),
        (lambda d: d.update(palette=[]), "theme.json › palette: must be an object"),
        (lambda d: d.pop("fonts"), "theme.json › fonts: required key missing"),
    ],
)
def test_validation_rules(
    tmp_theme: TmpTheme, mutate: Callable[[dict[str, Any]], None], expected: str
) -> None:
    msgs = _messages(_edit(tmp_theme, mutate))
    assert any(m.startswith(expected) for m in msgs), msgs
