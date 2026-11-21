"""M11: the ``artwork`` scene layer draws library files in the lacquer style."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from history_shorts.compose import DrawContext, EggshellCache
from history_shorts.config import load_script, load_theme
from history_shorts.errors import ValidationFailed
from history_shorts.living.depth import scene_layers
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene_config import ArtworkLayer

ScriptFactory = Callable[..., Path]


def _part(pid: str, **kw: Any) -> dict[str, Any]:
    return {"id": pid, **kw}


FILES: dict[str, list[dict[str, Any]]] = {
    "square": [_part("sq", rect=[0, -100, 100, 100], fill={"color": "gold_lt"})],
    "fade": [
        _part(
            "band",
            rect=[0, -100, 100, 100],
            fill={"stops": [["gold_lt", 1, 0], ["gold_lt", 0, 1]], "dir": "v"},
        )  # fmt: skip
    ],
    "glow": [
        _part(
            "halo",
            ellipse=[0, -50, 50, 50],
            fill={"stops": [["gold_lt", 0.6, 0], ["gold_lt", 0, 1]], "radial": [0, -50, 50]},
        )  # fmt: skip
    ],
    "leaf": [_part("disc", ellipse=[0, -60, 60, 60], fill={"texture": "gold_leaf", "tile": 20})],
    "shell": [_part("disc", ellipse=[0, -60, 60, 60], fill={"texture": "eggshell", "cell": 12})],
    "clipped": [
        _part("ring", ellipse=[0, -50, 30, 30], fill={"color": "vermilion"}),
        _part("bar", rect=[-100, -60, 200, 20], clip="ring", fill={"color": "gold_lt"}),
    ],
    "slant": [
        _part(
            "tri",
            d="M 0 0 L 80 0 L 0 -120 Z",
            fill={"gradient": ["gold_lt", "vermilion"], "dir": "h"},
            stroke={"color": "gold_dk", "width": 2},
        )  # fmt: skip
    ],
}


@pytest.fixture
def art_theme(tmp_theme: Callable[..., Path]) -> Any:
    path = tmp_theme()
    folder = path.parent / "artwork"
    folder.mkdir(exist_ok=True)
    for name, parts in FILES.items():
        data = {
            "artwork": "1",
            "title": name,
            "plane": "near" if name == "square" else "mid",
            "parts": parts,
        }
        (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    return load_theme(path)[0]


def _ctx(theme: Any) -> DrawContext:
    return DrawContext(theme, theme.palette, theme.seed, 0, EggshellCache())


def _draw(
    theme: Any, name: str, x: float = 540, y: float = 1000, scale: float = 1.0, flip: int = 1
) -> Any:
    base = np.zeros((1920, 1080, 3), dtype=np.float32)
    layer = ArtworkLayer(name, x, y, scale, flip)
    return LAYER_DRAWERS[ArtworkLayer](base, layer, _ctx(theme), 3)


def _changed(img: Any) -> Any:
    return img.max(axis=2) > 1 / 255


@pytest.mark.parametrize("name", ["../theme", "Torch", "torch.json", ""])
def test_name_pattern(name: str, tmp_script: ScriptFactory) -> None:  # Review Focus 2
    slide = {"title": "A", "scene": {"layers": [{"type": "artwork", "name": name, "x": 1, "y": 1}]}}
    with pytest.raises(ValidationFailed) as exc:
        load_script(tmp_script(slides=[slide], extra={"schema_version": "2.3"}))
    assert any(i.path.endswith("layers[0].name") for i in exc.value.issues.items)


def test_artwork_needs_23(tmp_script: ScriptFactory) -> None:
    slide = {
        "title": "A",
        "scene": {"layers": [{"type": "artwork", "name": "torch", "x": 1, "y": 1}]},
    }
    with pytest.raises(ValidationFailed) as exc:
        load_script(tmp_script(slides=[slide], extra={"schema_version": "2.2"}))
    assert any('requires schema_version "2.3"' in i.message for i in exc.value.issues.items)


def test_solid_square_pixels(art_theme: Any) -> None:
    img = _draw(art_theme, "square")
    ys, xs = np.nonzero(_changed(img))
    assert (xs.min(), xs.max(), ys.min(), ys.max()) == (540, 639, 900, 999)
    assert np.allclose(img[950, 590], np.array(art_theme.palette["gold_lt"]) / 255, atol=1 / 255)


def test_gradient_alpha_fade(art_theme: Any) -> None:
    img = _draw(art_theme, "fade")
    assert img[901, 590].max() > 0.8
    assert img[998, 590].max() < 0.05


def test_radial_glow(art_theme: Any) -> None:
    img = _draw(art_theme, "glow")
    gold = np.array(art_theme.palette["gold_lt"]) / 255
    assert np.allclose(img[950, 540], gold * 0.6, atol=0.02)
    assert img[950, 588].max() < 0.05


@pytest.mark.parametrize("name", ["leaf", "shell"])
def test_texture_inside_mask_and_deterministic(name: str, art_theme: Any) -> None:  # AC-41
    img = _draw(art_theme, name)
    ys, xs = np.nonzero(_changed(img))
    assert ((xs - 540) ** 2 + (ys - 940) ** 2 <= 62**2).all()  # 1 px of anti-aliasing
    assert np.array_equal(img, _draw(art_theme, name))
    assert np.std(img[ys, xs]) > 0.02  # a texture, not a flat colour


def test_clip_to_part(art_theme: Any) -> None:
    img = _draw(art_theme, "clipped")
    ys, xs = np.nonzero(_changed(img))
    assert ((xs - 540) ** 2 + (ys - 950) ** 2 <= 32**2).all()  # 1 px of anti-aliasing


def test_flip_mirrors(art_theme: Any) -> None:  # Review Focus 3 (still)
    right = _draw(art_theme, "slant", flip=1)
    left = _draw(art_theme, "slant", flip=-1)
    mirrored = right[:, ::-1]
    assert np.abs(left[:, 1:] - mirrored[:, :-1]).mean() < 0.002


@pytest.mark.parametrize("scale", [0.1, 5.0])
def test_tiny_and_huge_scale(scale: float, art_theme: Any) -> None:  # Review Focus 5
    img = _draw(art_theme, "leaf", y=1500, scale=scale)
    assert _changed(img).any()


def test_default_plane_from_file(art_theme: Any, tmp_script: ScriptFactory) -> None:
    layers = [
        {"type": "artwork", "name": "square", "x": 540, "y": 1000},
        {"type": "artwork", "name": "fade", "x": 540, "y": 1000, "plane": "near"},
    ]
    slide = {"title": "A", "living": True, "scene": {"layers": layers}}
    script = load_script(tmp_script(slides=[slide], extra={"schema_version": "2.3"}))[0]
    _, depths = scene_layers(script.slides[0], art_theme)
    assert depths == ("near", "near")
    one = {"title": "A", "living": True, "scene": {"layers": [layers[1] | {"plane": "far"}]}}
    script = load_script(tmp_script(slides=[one], extra={"schema_version": "2.3"}))[0]
    assert scene_layers(script.slides[0], art_theme)[1] == ("far",)
