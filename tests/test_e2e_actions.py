"""End-to-end: a schema 2.3 slide with timed actions rendered by real FFmpeg (M10)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from conftest import requires_ffmpeg
from helpers.visual import region_delta_e
from PIL import Image

from history_shorts.cli import main
from history_shorts.ffmpeg import find_ffmpeg, probe
from history_shorts.layout import REGIONS

pytestmark = [pytest.mark.ffmpeg, requires_ffmpeg]

DATA = Path(__file__).parent / "data" / "action_script.json"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("actions")
    out = root / "actions.mp4"
    assert main(["validate", "--script", str(DATA)]) == 0
    assert main(["render", "--script", str(DATA), "--out", str(out)]) == 0
    assert main(["render", "--script", str(DATA), "--out", str(root / "p.mp4"), "--preview"]) == 0
    return out


def _frame(video: Path, t: float) -> np.ndarray:
    target = video.with_name(f"f_{t:.3f}.png")
    info = find_ffmpeg()
    subprocess.run(
        [str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}",
         "-i", str(video), "-frames:v", "1", str(target)],
        check=True,
    )  # fmt: skip
    return np.asarray(Image.open(target).convert("RGB"))


def test_duration(rendered: Path) -> None:
    assert probe(find_ffmpeg(), rendered).duration == pytest.approx(3.0, abs=0.1)


def test_first_frame_matches_preview(rendered: Path) -> None:
    preview = np.asarray(Image.open(rendered.parent / "slides" / "01.png").convert("RGB"))
    assert max(region_delta_e(_frame(rendered, 0.35), preview, REGIONS).values()) <= 2


def test_rally_and_kneel_visible(rendered: Path) -> None:
    before, during, after = _frame(rendered, 0.4), _frame(rendered, 1.2), _frame(rendered, 2.8)
    rally = np.abs(during[400:900, 250:600].astype(float) - before[400:900, 250:600]).max(axis=2)
    assert (rally > 40).sum() > 2000  # the general's arm went up
    kneel = np.abs(after[500:1000, 560:840].astype(float) - before[500:1000, 560:840]).max(axis=2)
    assert (kneel > 40).sum() > 4000  # the villager knelt
