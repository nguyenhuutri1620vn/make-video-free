"""M11: artwork in validate, the ``artwork`` commands and the gallery sheet."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from history_shorts.cli import main
from history_shorts.errors import ValidationFailed
from history_shorts.gallery import PREVIEW_CELL_W

ScriptFactory = Callable[..., Path]
TORCH = {
    "artwork": "1",
    "title": "Đuốc thử",
    "parts": [
        {"id": "pole", "rect": [-4, -120, 8, 120], "fill": {"color": "brown"}},
        {"id": "flame", "ellipse": [0, -140, 12, 22], "fill": {"color": "vermilion"},
         "motion": {"kind": "flicker", "amp": 4}},
    ],
}  # fmt: skip


@pytest.fixture
def theme_dir(tmp_theme: Callable[..., Path]) -> Path:
    path = tmp_theme()
    folder = path.parent / "artwork"
    if folder.exists():
        shutil.rmtree(folder)  # start from an empty library, independent of the shipped files
    folder.mkdir()
    (folder / "torch.json").write_text(json.dumps(TORCH), encoding="utf-8")
    return path


def _script(tmp_script: ScriptFactory, name: str) -> Path:
    layer = {"type": "artwork", "name": name, "x": 540, "y": 1100, "scale": 2}
    slides = [{"title": "A", "duration": 15, "scene": {"layers": [layer]}}]
    return tmp_script(slides=slides, extra={"schema_version": "2.3"})


def test_validate_suggests_close_names(
    tmp_script: ScriptFactory, theme_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["validate", "--script", str(_script(tmp_script, "torhc")), "--theme", str(theme_dir)]
    )
    out = capsys.readouterr().out
    assert code == ValidationFailed.exit_code
    assert "layers[0].name: unknown artwork 'torhc'; did you mean: torch" in out


def test_validate_reports_broken_file(
    tmp_script: ScriptFactory, theme_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = {"artwork": "1", "parts": [{"id": "x", "rect": [0, 0, 1, 1], "fill": {"color": "nope"}}]}
    (theme_dir.parent / "artwork" / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    code = main(
        ["validate", "--script", str(_script(tmp_script, "bad")), "--theme", str(theme_dir)]
    )
    out = capsys.readouterr().out
    assert code == ValidationFailed.exit_code
    assert "artwork/bad.json › parts[0].fill.color: unknown palette key 'nope'" in out


def test_validate_ok(tmp_script: ScriptFactory, theme_dir: Path) -> None:
    assert (
        main(["validate", "--script", str(_script(tmp_script, "torch")), "--theme", str(theme_dir)])
        == 0
    )


def test_artwork_check(theme_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["artwork", "check", "--theme", str(theme_dir)]) == 0
    assert "torch: ok" in capsys.readouterr().out
    (theme_dir.parent / "artwork" / "bad.json").write_text("{", encoding="utf-8")
    assert main(["artwork", "check", "--theme", str(theme_dir)]) == ValidationFailed.exit_code
    assert main(["artwork", "check", "--theme", str(theme_dir), "--name", "torch"]) == 0


def test_artwork_check_empty_library(
    theme_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # Review Focus 4
    shutil.rmtree(theme_dir.parent / "artwork")
    assert main(["artwork", "check", "--theme", str(theme_dir)]) == 0
    assert "no artwork in" in capsys.readouterr().out


def test_artwork_check_unknown_name(theme_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["artwork", "check", "--theme", str(theme_dir), "--name", "torhc"]) == 1
    assert "did you mean: torch" in capsys.readouterr().out


def test_artwork_preview(theme_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "torch.png"
    args = ["artwork", "preview", "--name", "torch", "--out", str(out), "--theme", str(theme_dir)]
    assert main(args) == 0
    image = Image.open(out)
    assert image.size[0] == 4 * PREVIEW_CELL_W
    cells = [
        image.crop((k * PREVIEW_CELL_W, 0, (k + 1) * PREVIEW_CELL_W, image.size[1]))
        for k in range(4)
    ]
    assert cells[0].tobytes() != cells[1].tobytes()  # the flame moves between phases


def test_gallery_writes_artwork_sheet(theme_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "gallery.png"
    assert main(["gallery", "--out", str(out), "--theme", str(theme_dir)]) == 0
    sheet = tmp_path / "gallery_artwork.png"
    assert sheet.is_file() and Image.open(sheet).size[0] > 0
