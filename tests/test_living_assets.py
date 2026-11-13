"""Living slides (M9): plane and sprite files written for FFmpeg."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from history_shorts.config import LivingSpec, load_script
from history_shorts.living.assets import living_pad, render_living, write_png_rgba

REPO = Path(__file__).resolve().parents[1]
SPEC = LivingSpec()


def _living_script(*indices: int) -> Any:
    script = load_script(REPO / "examples" / "hai_ba_trung" / "script.json")[0]
    slides = tuple(dataclasses.replace(s, living=i in indices) for i, s in enumerate(script.slides))
    return dataclasses.replace(script, slides=slides)


def test_pad_covers_travel_shake_and_drift() -> None:
    px, py = living_pad("near", SPEC, 0.0, 5.0)
    assert px >= SPEC.travel_px["near"] + SPEC.shake_px
    assert px * 16 == py * 9
    drifting = living_pad("far", SPEC, 6.0, 5.0)[0]
    assert drifting >= SPEC.travel_px["far"] + SPEC.shake_px + 30


def test_png_rgba_is_unpremultiplied(tmp_path: Path) -> None:
    rgba = np.zeros((2, 2, 4), dtype=np.float32)
    rgba[0, 0] = (0.25, 0.1, 0.05, 0.5)
    path = tmp_path / "p.png"
    write_png_rgba(rgba, path)
    pixel = Image.open(path).getpixel((0, 0))
    assert pixel == (128, 51, 26, 128)


def test_render_living_files(tmp_path: Path, theme: Any) -> None:  # RF-4
    script = _living_script(0, 4)
    durations = [3.0] * len(script.slides)
    clips = render_living(script, theme, durations, tmp_path)
    assert [c is not None for c in clips] == [i in (0, 4) for i in range(len(clips))]
    first, fifth = clips[0], clips[4]
    assert first is not None and fifth is not None
    assert first.planes[0].path.parent != fifth.planes[0].path.parent
    for index, clip in ((0, first), (4, fifth)):
        for plane in clip.planes:
            if plane.kind == "sprite":
                files = sorted(plane.path.parent.glob("*.png"))
                assert len(files) == plane.frames
                assert Image.open(files[0]).size == (plane.size[1], plane.size[0])
            else:
                w, h = Image.open(plane.path).size
                assert (w, h) == (1080 + 2 * plane.pad[0], 1920 + 2 * plane.pad[1])
        for path in (clip.waves, clip.sheen, clip.chrome):
            assert path.is_file()
        assert (clip.text is not None) == (script.slides[index].text_in != "none")
    assert any(p.kind == "sprite" for p in fifth.planes)
    assert any(p.kind == "drift" for p in fifth.planes)
