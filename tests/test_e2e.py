"""End-to-end: real FFmpeg, real slides (AC-01, AC-02, AC-13, AC-14, FR-86)."""

from __future__ import annotations

import array
import json
import math
import subprocess
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from conftest import requires_ffmpeg

from history_shorts.cli import main
from history_shorts.config import load_script
from history_shorts.ffmpeg import FfmpegInfo, ProbeResult, find_ffmpeg, probe
from history_shorts.script_config import slide_duration

pytestmark = [pytest.mark.ffmpeg, requires_ffmpeg]

ScriptFactory = Callable[..., Path]


def ffprobe(path: Path) -> ProbeResult:
    return probe(find_ffmpeg(), path)


def expected_durations(repo_root: Path, name: str) -> list[float]:
    script, _ = load_script(repo_root / "examples" / name / "script.json")
    return [slide_duration(s, 30) for s in script.slides]


def make_sine(info: FfmpegInfo, path: Path, seconds: int) -> Path:
    cmd = [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:a", "aac", str(path),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def rms(info: FfmpegInfo, video: Path, start: float, length: float, wav: Path) -> float:
    cmd = [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(wav),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    with wave.open(str(wav), "rb") as handle:
        samples = array.array("h")
        samples.frombytes(handle.readframes(handle.getnframes()))
    assert len(samples) > 0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def test_render_nu_tuong(tmp_path: Path, repo_root: Path) -> None:  # AC-01, AC-02, FR-86
    out = tmp_path / "Sử Việt 'x'" / "nu tuong.mp4"
    script = repo_root / "examples" / "nu_tuong" / "script.json"
    assert main(["render", "--script", str(script), "--out", str(out)]) == 0
    p = ffprobe(out)
    assert (p.width, p.height, p.codec, p.pix_fmt, p.fps) == (1080, 1920, "h264", "yuv420p", "30/1")
    assert p.duration == pytest.approx(sum(expected_durations(repo_root, "nu_tuong")), abs=0.1)
    assert p.audio_codec == "aac"  # silent track (FR-86)
    assert not out.with_name(out.name + ".partial.mp4").exists()
    report = json.loads((out.parent / "nu tuong.report.json").read_text(encoding="utf-8"))
    assert report["total_duration"] == pytest.approx(p.duration, abs=0.1)
    assert sorted(f.name for f in (out.parent / "slides").iterdir()) == [
        f"{i:02d}.png" for i in range(1, 6)
    ]


def test_music_matches_length_and_fades(  # AC-13
    tmp_path: Path, repo_root: Path, tmp_script: ScriptFactory
) -> None:
    info = find_ffmpeg()
    music = make_sine(info, tmp_path / "m.m4a", seconds=7)  # generated; no bundled music
    source = json.loads((repo_root / "examples/me_linh/script.json").read_text(encoding="utf-8"))
    slides: list[dict[str, Any]] = [dict(s, duration=5.0) for s in source["slides"][:2]]
    script = tmp_script(slides=slides, sources=source["sources"], title=source["title"])
    out = tmp_path / "res" / "me linh.mp4"
    argv = ["render", "--script", str(script), "--out", str(out), "--music", str(music)]
    assert main(argv) == 0
    p = ffprobe(out)
    assert p.duration == pytest.approx(10.0, abs=0.1)
    assert p.audio_codec == "aac"
    assert p.audio_duration is not None
    assert p.audio_duration == pytest.approx(p.duration, abs=0.1)
    middle = rms(info, out, p.duration / 2, 1.0, tmp_path / "mid.wav")
    tail = rms(info, out, p.duration - 0.2, 0.2, tmp_path / "tail.wav")
    assert middle > 100  # the music is really there
    assert tail < 0.2 * middle  # faded out


def test_without_ffmpeg_on_path_exit_4(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # AC-14
    monkeypatch.setenv("PATH", "")
    script = repo_root / "examples" / "me_linh" / "script.json"
    code = main(["render", "--script", str(script), "--out", str(tmp_path / "x.mp4")])
    assert code == 4
    assert "install" in capsys.readouterr().out.lower()
    assert not (tmp_path / "slides").exists()


def test_jobs_4_probes_like_jobs_1(tmp_path: Path, repo_root: Path) -> None:  # FR-87
    script = repo_root / "examples" / "nu_tuong" / "script.json"
    info = find_ffmpeg()
    results = []
    for jobs in (1, 4):
        out = tmp_path / f"j{jobs}" / "v.mp4"
        assert (
            main(["render", "--script", str(script), "--out", str(out), "--jobs", str(jobs)]) == 0
        )
        p = ffprobe(out)
        frames = subprocess.run(
            [str(info.ffprobe), "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(out)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()  # fmt: skip
        results.append((p.codec, p.width, p.height, p.fps, round(p.duration, 2), frames))
    assert results[0] == results[1]
