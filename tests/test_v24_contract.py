"""M12: schema 2.4 warrior fields and the new palette keys."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts.checks import check_all
from history_shorts.config import load_script, load_theme
from history_shorts.errors import ValidationFailed
from history_shorts.script_config import SUPPORTED_SCHEMA_VERSIONS, WARRIOR_SCHEMA_VERSION

ScriptFactory = Callable[..., Path]
NEW_KEYS = {
    "steel": (126, 128, 122),
    "steel_dk": (74, 78, 78),
    "indigo": (46, 58, 92),
    "indigo_dk": (28, 34, 58),
}


def _slide(item: dict[str, Any]) -> dict[str, Any]:
    layer = {"type": "characters", "items": [{"x": 540, "height": 400, **item}]}
    return {"title": "A", "scene": {"layers": [layer]}}


def _load(tmp_script: ScriptFactory, item: dict[str, Any], version: str = "2.4") -> Any:
    return load_script(tmp_script(slides=[_slide(item)], extra={"schema_version": version}))


def test_version() -> None:
    assert WARRIOR_SCHEMA_VERSION == "2.4" and SUPPORTED_SCHEMA_VERSIONS[-1] == "2.4"


def test_fields_load(tmp_script: ScriptFactory) -> None:
    item = {
        "role": "general",
        "helmet": "cap",
        "body": "tunic",
        "armour": "steel",
        "banner": "indigo",
    }
    script, _ = _load(tmp_script, item)
    spec = script.slides[0].scene.layers[0].items[0]
    assert (spec.helmet, spec.body, spec.armour, spec.banner) == ("cap", "tunic", "steel", "indigo")


@pytest.mark.parametrize(
    ("item", "where"),
    [
        ({"role": "general", "helmet": "cap"}, "helmet"),
        ({"role": "general", "body": "tunic"}, "body"),
        ({"role": "general", "armour": "steel"}, "armour"),
        ({"role": "general", "banner": "indigo"}, "banner"),
        ({"role": "general", "prop": "shield"}, "prop"),
        ({"role": "general", "prop": "sword_sheathed"}, "prop"),
    ],
)
def test_new_fields_need_24(item: dict[str, Any], where: str, tmp_script: ScriptFactory) -> None:
    with pytest.raises(ValidationFailed) as exc:
        _load(tmp_script, item, "2.3")  # Review Focus 1
    assert any(
        i.path.endswith(f"items[0].{where}") and 'requires schema_version "2.4"' in i.message
        for i in exc.value.issues.items
    ), exc.value.issues.items


@pytest.mark.parametrize(("key", "value"), [("helmet", "crown"), ("body", "robe")])
def test_variant_names(key: str, value: str, tmp_script: ScriptFactory) -> None:
    with pytest.raises(ValidationFailed) as exc:
        _load(tmp_script, {"role": "general", key: value})
    assert any(i.path.endswith(f"items[0].{key}") for i in exc.value.issues.items)


def test_colour_keys_checked(tmp_script: ScriptFactory, theme: Any) -> None:
    script, _ = _load(tmp_script, {"role": "general", "armour": "chrome", "banner": "indigo"})
    messages = [f"{i.path}: {i.message}" for i in check_all(script, theme)]
    assert any("items[0].armour" in m and "unknown palette key 'chrome'" in m for m in messages)


def test_shipped_theme_has_new_keys(theme: Any) -> None:
    for key, rgb in NEW_KEYS.items():
        assert theme.palette[key] == rgb


def test_theme_without_new_keys_loads(tmp_theme: Callable[..., Path]) -> None:  # Review Focus 3
    path = tmp_theme(drop_palette=tuple(NEW_KEYS))
    palette = load_theme(path)[0].palette
    for key in NEW_KEYS:
        assert key in palette.keys()


def test_theme_json_lists_keys() -> None:
    data = json.loads(
        (Path(__file__).resolve().parents[1] / "themes/son_mai/theme.json").read_text()
    )
    assert set(NEW_KEYS) <= set(data["palette"])


def test_24_keeps_23_motion(tmp_path: Path, theme: Any, tmp_script: ScriptFactory) -> None:
    """A 2.4 script still gets every 2.3 feature: redrawn layers and moving characters."""
    import dataclasses

    from history_shorts.living.assets import render_living

    item = {"role": "viet_soldier", "id": "a", "x": 540, "baseline": 1100, "height": 380}
    slide = {
        "title": "A",
        "duration": 2,
        "living": True,
        "scene": {"layers": [{"type": "characters", "items": [item]}]},
        "actions": [{"who": "a", "do": "rally", "at": 0.2}],
    }
    script = load_script(tmp_script(slides=[slide], extra={"schema_version": "2.4"}))[0]
    fast = dataclasses.replace(
        theme, living=dataclasses.replace(theme.living, loop_seconds=0.5, idle_loop_seconds=1.0)
    )
    (clip,) = render_living(script, fast, [2.0], tmp_path)
    assert clip is not None
    assert any(p.kind == "sprite" for p in clip.planes)
