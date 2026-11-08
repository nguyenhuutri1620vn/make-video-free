"""``gallery`` contact sheet of every role x facing x prop (FR-04, AC-07)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from history_shorts import gallery
from history_shorts.characters import ROLES, resolve_style
from history_shorts.characters.figure import Placement, figure_boxes
from history_shorts.cli import main
from history_shorts.compose import rng_for
from history_shorts.config import CharacterSpec, Theme
from history_shorts.primitives import Box
from history_shorts.textures import lacquer_ground

SHEET_SIZE = (1080, 3000)
PATCH = 6  # half-size of the pixel patch sampled at a cell's body centre
PATCH_MIN_DIFF = 30  # figure pixels differ from the ground by at least this (0..255)


def test_cli_writes_a_1080x3000_png(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "deep" / "g.png"
    assert main(["gallery", "--out", str(out)]) == 0
    assert out.is_file()
    with Image.open(out) as img:
        assert img.size == SHEET_SIZE
        assert img.mode == "RGB"
    text = capsys.readouterr().out
    assert str(out) in text
    assert " s" in text


def test_default_out_is_output_gallery_png(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["gallery"]) == 0
    assert (tmp_path / "output" / "gallery.png").is_file()
    capsys.readouterr()


def test_unwritable_out_reports_error_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    out = blocker / "g.png"  # the parent is a file, so it cannot be created
    assert main(["gallery", "--out", str(out)]) == 1
    text = capsys.readouterr().out
    assert text.startswith(f"ERROR cannot write gallery to {out}: ")


def test_bad_theme_exits_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "theme.json"
    bad.write_text("{}")
    assert main(["gallery", "--theme", str(bad), "--out", str(tmp_path / "g.png")]) == 3
    assert "ERROR" in capsys.readouterr().out
    assert not (tmp_path / "g.png").exists()


def test_grid_covers_every_role_facing_and_prop() -> None:
    cells = gallery.grid_cells()
    assert len(cells) == len(ROLES) * 2 * 4 == 32
    combos = {(c.role, c.facing, c.prop) for c in cells}
    assert len(combos) == 32
    assert {c.role for c in cells} == set(ROLES)
    assert {c.prop for c in cells} == {"flag", "spear", "oar", "none"}
    assert {c.facing for c in cells} == {1, -1}
    assert [c.role for c in cells[::4]] == [
        "leader",
        "leader",
        "general",
        "general",
        "general_alt",
        "general_alt",
        "boat_crew",
        "boat_crew",
    ]


def test_cells_tile_the_sheet_without_gaps() -> None:
    cells = gallery.grid_cells()
    assert all(c.box.width == gallery.CELL_W and c.box.height == gallery.CELL_H for c in cells)
    assert min(c.box.x0 for c in cells) == 0
    assert max(c.box.x1 for c in cells) == SHEET_SIZE[0]
    assert min(c.box.y0 for c in cells) == gallery.HEADER_H
    assert max(c.box.y1 for c in cells) == SHEET_SIZE[1]
    for a in cells:
        assert sum(a.box.intersects(b.box) for b in cells) == 1  # itself only


def test_no_figure_is_clipped_by_its_cell(theme: Theme) -> None:
    for cell in gallery.grid_cells():
        style = resolve_style(CharacterSpec(role=cell.role, prop=cell.prop), theme.palette)
        boxes = figure_boxes(style, cell.placement)
        for name, box in (("head", boxes.head), ("body", boxes.body), ("prop", boxes.prop)):
            if box is None:
                assert cell.prop == "none"
                continue
            assert box.inside(cell.box), (cell, name, box)


def test_no_figure_touches_its_label(theme: Theme) -> None:
    for cell in gallery.grid_cells():
        style = resolve_style(CharacterSpec(role=cell.role, prop=cell.prop), theme.palette)
        label = gallery.label_box(theme, cell)
        assert label.inside(cell.box), cell
        boxes = figure_boxes(style, cell.placement)
        for box in (boxes.head, boxes.body, boxes.prop):
            assert box is None or not box.intersects(label), (cell, box, label)


def test_feet_stand_above_the_label_and_centred() -> None:
    for cell in gallery.grid_cells():
        assert cell.placement.baseline == cell.box.y1 - gallery.FEET_MARGIN
        assert cell.placement.x == (cell.box.x0 + cell.box.x1) / 2
        assert cell.placement.height == gallery.FIGURE_H


def test_every_cell_holds_figure_pixels(theme: Theme) -> None:
    ground = np.asarray(
        lacquer_ground(
            rng_for(theme.seed, 0, 0), theme.palette, width=SHEET_SIZE[0], height=SHEET_SIZE[1]
        )
    )
    sheet = np.asarray(gallery.render_gallery(theme)).astype(np.float32) / 255
    for cell in gallery.grid_cells():
        style = resolve_style(CharacterSpec(role=cell.role, prop=cell.prop), theme.palette)
        body = figure_boxes(style, cell.placement).body
        cx, cy = round((body.x0 + body.x1) / 2), round((body.y0 + body.y1) / 2)
        window = (slice(cy - PATCH, cy + PATCH), slice(cx - PATCH, cx + PATCH))
        diff = np.abs(sheet[window] - ground[window]).max() * 255
        assert diff >= PATCH_MIN_DIFF, cell


def test_header_and_labels_use_gold_light(theme: Theme) -> None:
    sheet = np.asarray(gallery.render_gallery(theme))
    gold = np.array(theme.palette["gold_lt"])
    header = sheet[: gallery.HEADER_H]
    assert (np.abs(header.astype(int) - gold).sum(axis=2) < 30).any()
    cell = gallery.grid_cells()[0]
    strip = sheet[int(cell.box.y1) - gallery.FEET_MARGIN + 2 : int(cell.box.y1)]
    assert (np.abs(strip.astype(int) - gold).sum(axis=2) < 30).any()


def test_label_text() -> None:
    cells = gallery.grid_cells()
    assert gallery.cell_label(cells[0]) == "leader · +1 · flag"
    assert gallery.cell_label(cells[7]) == "leader · -1 · none"


def test_gallery_is_deterministic(theme: Theme, tmp_path: Path) -> None:
    first, second = tmp_path / "a.png", tmp_path / "b.png"
    assert main(["gallery", "--out", str(first)]) == 0
    assert main(["gallery", "--out", str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()
    assert gallery.render_gallery(theme).tobytes() == gallery.render_gallery(theme).tobytes()


def test_placement_type() -> None:
    assert isinstance(gallery.grid_cells()[0].placement, Placement)
    assert isinstance(gallery.grid_cells()[0].box, Box)
