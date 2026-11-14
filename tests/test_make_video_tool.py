"""tools/make_video.py: the one-command pipeline from script to voiced video."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from history_shorts import audio
from history_shorts.config import load_script

Make = Callable[..., Path]
TOOL = Path(__file__).resolve().parent.parent / "tools" / "make_video.py"

# A stand-in for the sound project: writes a 1 s silent 16-bit mono WAV to argv[1].
FAKE_VOICE = """
import sys, wave
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\\x00\\x00" * 16000)
"""


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_video", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_video"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script(tmp_script: Make) -> Path:
    return tmp_script(
        extra={"schema_version": "2.1"},
        slides=[
            {"title": "Mở đầu", "id": "s01", "narration": "Năm bốn mươi."},
            {"title": "Không lời", "id": "s02"},
        ],
    )


def test_voice_command_substitutes_each_argument(tool: ModuleType, tmp_path: Path) -> None:
    job = tool.VoiceJob("s01", tmp_path / "a b" / "s01.txt", tmp_path / "s01.wav")
    cmd = tool.voice_command("tts --in {text} --out {wav} --name 'voice {id}'", job)
    assert cmd == ["tts", "--in", str(job.text), "--out", str(job.wav), "--name", "voice s01"]


def test_pending_voices_lists_missing_and_stale(
    tool: ModuleType, script: Path, tmp_path: Path
) -> None:
    work = tmp_path / "work"
    loaded, _ = load_script(script)
    audio.export_narration(loaded, work)
    assert [j.id for j in tool.pending_voices(work)] == ["s01"]
    wav = work / "s01.wav"
    wav.write_bytes(b"x")
    assert tool.pending_voices(work) == []
    stat = wav.stat()
    os.utime(wav, (stat.st_atime - 3600, stat.st_mtime - 3600))
    assert [j.wav for j in tool.pending_voices(work)] == [wav]


def test_without_voice_cmd_lists_files_and_stops(
    tool: ModuleType, script: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    work = tmp_path / "work"
    code = tool.main(["--script", str(script), "--work", str(work)])
    out = capsys.readouterr().out
    assert code == 3
    assert "s01.txt -> s01.wav" in out
    assert not (work / "audio_manifest.json").exists()


def test_has_narration(tool: ModuleType, script: Path, tmp_script: Make) -> None:
    assert tool.has_narration(script)
    assert not tool.has_narration(tmp_script())


@pytest.mark.ffmpeg
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg not on PATH")
def test_full_pipeline_records_pairs_and_renders(
    tool: ModuleType, script: Path, tmp_path: Path
) -> None:
    work, out = tmp_path / "work", tmp_path / "video.mp4"
    fake = tmp_path / "fake_voice.py"
    fake.write_text(FAKE_VOICE, encoding="utf-8")
    template = f"{sys.executable} {fake} {{wav}}"
    argv = ["--script", str(script), "--work", str(work), "--out", str(out)]
    assert tool.main([*argv, "--voice-cmd", template]) == 0
    assert out.is_file() and (work / "audio_manifest.json").is_file()
    assert (work / "s01.wav").is_file()
