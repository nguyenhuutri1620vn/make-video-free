"""Render report and sources block (FR-91, FR-92)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from history_shorts.config import Script, Theme, load_script
from history_shorts.errors import Issue
from history_shorts.ffmpeg import FfmpegInfo
from history_shorts.report import build_report, sources_block, write_report
from history_shorts.script_config import slide_duration
from history_shorts.video import RenderOptions

REPO = Path(__file__).resolve().parent.parent
INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))
TIMINGS = {
    "validate": 0.1, "render_slides": 2.0, "encode": 3.0, "concat": 0.2, "mux": 0.3, "total": 5.6,
}  # fmt: skip


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def example(name: str) -> Script:
    return load_script(REPO / "examples" / name / "script.json")[0]


def test_sources_block() -> None:
    script = example("nu_tuong")
    text = sources_block(script)
    lines = text.splitlines()
    assert lines[0] == "Sources:"
    assert lines[1:] == [f"[{i}] {s}" for i, s in enumerate(script.sources, start=1)]
    assert len(lines) == len(script.sources) + 1


def test_sources_block_empty_when_no_sources(tmp_script) -> None:  # type: ignore[no-untyped-def]
    script = load_script(tmp_script(sources=None))[0]
    assert sources_block(script) == ""


def build(tmp_path: Path, theme: Theme, music: Path | None = None) -> dict[str, object]:
    script = example("nu_tuong")
    out = tmp_path / "res" / "v.mp4"
    slides = [out.parent / "slides" / f"{i + 1:02d}.png" for i in range(len(script.slides))]
    durations = [slide_duration(s, 30) for s in script.slides]
    opts = RenderOptions(out=out, music=music)
    warnings = [Issue("script.json", "slides[0]", "careful", "warning")]
    return build_report(script, theme, opts, durations, slides, TIMINGS, warnings, INFO)


def test_report_contents(tmp_path: Path, theme: Theme) -> None:
    data = build(tmp_path, theme)
    script = example("nu_tuong")
    assert set(data) == {
        "script_sha256", "theme_sha256", "music_sha256", "slides", "total_duration", "warnings",
        "versions", "timings", "sources",
    }  # fmt: skip
    assert data["script_sha256"] == sha(script.path)
    assert data["theme_sha256"] == sha(theme.path)
    assert data["music_sha256"] is None
    slides = data["slides"]
    assert isinstance(slides, list) and len(slides) == len(script.slides)
    assert slides[0] == {
        "index": 1,
        "duration": round(slide_duration(script.slides[0], 30), 3),
        "png": "slides/01.png",
    }
    assert data["total_duration"] == pytest.approx(27.9)
    assert data["warnings"] == ["script.json › slides[0]: careful"]
    assert data["timings"] == TIMINGS
    assert data["sources"] == list(script.sources)
    versions = data["versions"]
    assert isinstance(versions, dict)
    assert set(versions) == {"python", "pycairo", "cairo", "numpy", "scipy", "Pillow", "ffmpeg"}
    assert all(isinstance(v, str) and v for v in versions.values())
    assert versions["ffmpeg"] == "8.1"


def test_report_music_hash_and_dev_ffmpeg(tmp_path: Path, theme: Theme) -> None:
    music = tmp_path / "m.mp3"
    music.write_bytes(b"not really audio")
    script = example("me_linh")
    out = tmp_path / "v.mp4"
    data = build_report(
        script, theme, RenderOptions(out=out, music=music), [], [], TIMINGS, ["w"],
        FfmpegInfo(Path("f"), Path("p"), None),
    )  # fmt: skip
    assert data["music_sha256"] == sha(music)
    assert data["warnings"] == ["w"]
    versions = data["versions"]
    assert isinstance(versions, dict) and versions["ffmpeg"] == "dev"


def test_write_report_atomic_utf8_sorted(tmp_path: Path, theme: Theme) -> None:
    data = build(tmp_path, theme)
    out = tmp_path / "Sử Việt" / "nu tuong.mp4"
    out.parent.mkdir()
    path = write_report(out, data)
    assert path == out.parent / "nu tuong.report.json"
    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == json.loads(json.dumps(data))
    assert "Nữ" in text or "nữ" in text or "ư" in text  # not escaped
    assert "\\u" not in text
    assert text.startswith('{\n  "music_sha256"')  # sorted keys, indent 2
    assert [p.name for p in out.parent.iterdir()] == ["nu tuong.report.json"]


def test_example_durations_are_whole_frames() -> None:
    for name in ("nu_tuong", "me_linh"):
        for slide in example(name).slides:
            frames = slide_duration(slide, 30) * 30
            assert abs(frames - round(frames)) < 1e-9
