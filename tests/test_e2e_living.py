"""End-to-end: living slides rendered by real FFmpeg (M9, AC-28)."""

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

DATA = Path(__file__).parent / "data" / "living_script.json"


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("living")
    out = root / "living.mp4"
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


def _shift(a: np.ndarray, b: np.ndarray, x0: int, x1: int) -> int:
    """Horizontal shift (px) of columns x0:x1 from frame a to frame b (least abs difference)."""
    ga, gb = a.mean(axis=-1), b.mean(axis=-1)
    span = range(-80, 81)
    return min(span, key=lambda dx: float(np.abs(ga[:, x0:x1] - gb[:, x0 + dx : x1 + dx]).mean()))


def test_living_render_duration(rendered: Path) -> None:
    assert probe(find_ffmpeg(), rendered).duration == pytest.approx(7.0, abs=0.1)


def test_early_frame_matches_preview(rendered: Path) -> None:
    preview = np.asarray(Image.open(rendered.parent / "slides" / "01.png").convert("RGB"))
    frame = _frame(rendered, 0.35)  # after the 0.3 s theme fade-in, before the shake
    assert max(region_delta_e(frame, preview, REGIONS).values()) <= 2


def test_chrome_region_stable(rendered: Path) -> None:
    a, b = _frame(rendered, 0.6), _frame(rendered, 3.5)
    band = slice(1540, 1920)
    assert np.abs(a[band].astype(float) - b[band].astype(float)).mean() <= 3


def test_nearer_planes_move_more(rendered: Path) -> None:
    a, b = _frame(rendered, 0.35), _frame(rendered, 3.8)
    far = abs(_shift(a[820:925], b[820:925], 150, 930))
    mid = abs(_shift(a[880:1000], b[880:1000], 90, 400))
    assert mid > far > 0
    assert far == pytest.approx(30 * 0.976, abs=4)  # travel x eased progress at 3.8 s of 4.5 s
    assert mid == pytest.approx(60 * 0.976, abs=6)


def test_no_holes(rendered: Path) -> None:
    preview = np.asarray(Image.open(rendered.parent / "slides" / "01.png").convert("RGB"))
    scene = (slice(300, 1150), slice(40, 1040))  # the moving picture; text is fixed chrome
    dark_in_preview = (preview[scene] <= 2).all(axis=-1)
    for t in (0.5, 1.5, 2.5, 3.5):
        frame = _frame(rendered, t)[scene]
        holes = (frame <= 2).all(axis=-1) & ~dark_in_preview
        assert holes.sum() == 0, t


def test_shake_visible_then_settles(rendered: Path) -> None:
    def motion(t0: float) -> float:
        frames = [_frame(rendered, t0 + i / 30).astype(float) for i in range(4)]
        return float(
            np.mean([np.abs(x - y).mean() for x, y in zip(frames, frames[1:], strict=False)])
        )

    assert motion(0.55) > 2 * motion(1.6)


def test_edge_sprite_has_no_gap_when_panning(rendered: Path) -> None:  # review finding 1
    """The river sprite spans the canvas width; panning right must not uncover its edge."""
    preview = np.asarray(Image.open(rendered.parent / "slides" / "01.png").convert("RGB"))
    frame = _frame(rendered, 3.8)
    band = (slice(1000, 1140), slice(1040, 1080))  # right edge of the dark river

    def redness(img: np.ndarray) -> float:  # the red mountains behind show up as R - G
        mean = img[band].reshape(-1, 3).astype(float).mean(axis=0)
        return float(mean[0] - mean[1])

    assert redness(frame) <= redness(preview) + 15
