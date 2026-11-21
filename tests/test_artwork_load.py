"""M11: artwork file model, loader and library."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from history_shorts.artwork.load import ArtworkLibrary, load_artwork
from history_shorts.artwork.model import Gradient, Motion, Solid, Texture
from history_shorts.errors import ValidationFailed

VALID: dict[str, Any] = {
    "artwork": "1",
    "title": "Thử",
    "plane": "near",
    "parts": [
        {
            "id": "pole",
            "d": "M -4 0 L -3 -120 L 3 -120 L 4 0 Z",
            "fill": {"gradient": ["brown_lt", "brown"], "dir": "v"},
            "stroke": {"color": "gold_dk", "width": 1.2},
        },
        {
            "id": "flame",
            "ellipse": [0, -135, 6, 12],
            "fill": {"color": "gold_lt"},
            "motion": {"kind": "flicker", "amp": 3},
        },  # fmt: skip
        {"id": "plate", "rect": [-20, -10, 40, 10, 2], "fill": {"texture": "gold_leaf"}},
        {
            "id": "glow",
            "ellipse": [0, -135, 30, 30],
            "alpha": 0.8,
            "fill": {"stops": [["gold_lt", 0.4, 0], ["gold_lt", 0, 1]], "radial": [0, -135, 30]},
            "motion": {"kind": "pulse", "amp": 0.2},
        },  # fmt: skip
        {"id": "inner", "ellipse": [0, -135, 3, 3], "clip": "flame", "fill": {"color": "egg"}},
    ],
}


def _write(tmp_path: Path, data: Any, name: str = "thu") -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _errors(tmp_path: Path, palette: Any, data: Any) -> list[str]:
    try:
        load_artwork(_write(tmp_path, data), palette)
    except ValidationFailed as exc:
        return [f"{i.file} › {i.path}: {i.message}" for i in exc.issues.items]
    return []


def _with(**part: Any) -> dict[str, Any]:
    data = copy.deepcopy(VALID)
    data["parts"].append({"id": "extra", **part})
    return data


def test_valid_file_round_trip(tmp_path: Path, palette: Any) -> None:
    art, warnings = load_artwork(_write(tmp_path, VALID), palette)
    assert warnings == []
    assert art.name == "thu" and art.title == "Thử" and art.plane == "near"
    pole, flame, plate, glow, inner = art.parts
    assert pole.ops[0] == ("M", (-4.0, 0.0)) and pole.ops[-1] == ("Z", ())
    assert isinstance(pole.fill, Gradient) and pole.fill.stops == (
        ("brown_lt", 1.0, 0.0),
        ("brown", 1.0, 1.0),
    )
    assert pole.stroke is not None and pole.stroke.width == 1.2
    assert isinstance(flame.fill, Solid) and flame.motion == Motion("flicker", amp=3.0)
    assert isinstance(plate.fill, Texture) and plate.fill.kind == "gold_leaf"
    assert isinstance(glow.fill, Gradient) and glow.fill.radial == (0.0, -135.0, 30.0)
    assert glow.alpha == 0.8 and inner.clip == "flame"
    assert art.moves


@pytest.mark.parametrize(
    ("part", "where", "message"),
    [
        (
            {"d": "M 0 0 L 1 1", "fill": {"color": "nope"}},
            "fill.color",
            "unknown palette key 'nope'",
        ),
        ({"d": "M 0 0 L 1 1", "ellipse": [0, 0, 1, 1]}, "", "exactly one of d, ellipse, rect"),
        ({"fill": {"color": "gold"}}, "", "exactly one of d, ellipse, rect"),
        ({"d": "M 0 0 X 1"}, "d", "bad command 'X' at 6"),
        ({"d": "M 0 0 L 1 1", "clip": "later"}, "clip", "must name an earlier part"),
        (
            {"d": "M 0 0 L 1 1", "fill": {"stops": [["gold", 1, 0.5], ["gold", 1, 0.2]]}},
            "fill.stops",
            "offsets must rise from 0 to 1",
        ),  # fmt: skip
        ({"d": "M 0 0 L 1 1", "fill": {"stops": [["gold", 1, 0]]}}, "fill.stops", "2 to 6 stops"),
        ({"d": "M 0 0 L 1 1", "alpha": 1.5}, "alpha", "0–1"),
        (
            {"d": "M 0 0 L 1 1", "stroke": {"color": "gold", "width": 30}},
            "stroke.width",
            "0.2–20",
        ),
        ({"d": "M 0 0 L 3000 1"}, "d", "within ±2000"),
        ({"d": "M 0 0 L 1 1", "motion": {"kind": "spin"}}, "motion.kind", "one of"),
        ({"d": "M 0 0 L 1 1", "motion": {"kind": "wave", "amp": 0.1}}, "motion.pole", "required"),
        ({"d": "M 0 0 L 1 1", "motion": {"kind": "sway", "deg": 3}}, "motion.pivot", "required"),
        (
            {
                "d": "M 0 0 L 1 1",
                "fill": {"texture": "gold_leaf"},
                "motion": {"kind": "flicker", "amp": 1},
            },
            "motion",
            "a textured part cannot move",
        ),  # fmt: skip
        (
            {"d": "M 0 0 L 1 1", "clip": "plate", "motion": {"kind": "flicker", "amp": 1}},
            "motion",
            "clipped to textured part 'plate' cannot move",
        ),  # fmt: skip
        (
            {"d": "M 0 0 L 1 1", "clip": "flame", "fill": {"texture": "eggshell"}},
            "fill",
            "clipped to moving part 'flame' cannot be textured",
        ),  # fmt: skip
    ],
)
def test_part_rules(
    part: dict[str, Any], where: str, message: str, tmp_path: Path, palette: Any
) -> None:
    errors = _errors(tmp_path, palette, _with(**part))
    path = "parts[5]" + (f".{where}" if where else "")
    assert any(f"artwork/thu.json › {path}: " in e and message in e for e in errors), errors


def test_duplicate_part_id(tmp_path: Path, palette: Any) -> None:
    data = _with(d="M 0 0 L 1 1")
    data["parts"][5]["id"] = "pole"
    assert any(
        "parts[5].id: duplicate part id 'pole'" in e for e in _errors(tmp_path, palette, data)
    )


def test_file_level_rules(tmp_path: Path, palette: Any) -> None:
    bad = copy.deepcopy(VALID)
    bad["artwork"] = "2"
    bad["plane"] = "middle"
    errors = _errors(tmp_path, palette, bad)
    assert any("› artwork: " in e and '"1"' in e for e in errors)
    assert any("› plane: " in e for e in errors)


def test_part_limit(tmp_path: Path, palette: Any) -> None:
    data = copy.deepcopy(VALID)
    data["parts"] = [{"id": f"p{k}", "d": "M 0 0 L 1 1"} for k in range(301)]
    assert any("at most 300 parts" in e for e in _errors(tmp_path, palette, data))


def test_number_limit(tmp_path: Path, palette: Any) -> None:
    data = copy.deepcopy(VALID)
    data["parts"] = [{"id": "big", "d": "M 0 0 " + "L 1 1 " * 10_000}]
    assert any("at most 20000 path numbers" in e for e in _errors(tmp_path, palette, data))


def test_library_reloads_changed_file(tmp_path: Path, palette: Any) -> None:  # Review Focus 1
    _write(tmp_path, VALID, "torch")
    library = ArtworkLibrary(tmp_path)
    assert library.names() == ["torch"]
    first = library.get("torch", palette)
    changed = copy.deepcopy(VALID)
    changed["parts"][1]["fill"]["color"] = "vermilion"
    path = _write(tmp_path, changed, "torch")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))
    second = library.get("torch", palette)
    assert isinstance(first.parts[1].fill, Solid) and first.parts[1].fill.color == "gold_lt"
    assert isinstance(second.parts[1].fill, Solid) and second.parts[1].fill.color == "vermilion"
    assert library.get("torch", palette) is second  # unchanged file: cached


def test_library_missing_dir(tmp_path: Path) -> None:
    assert ArtworkLibrary(tmp_path / "none").names() == []
