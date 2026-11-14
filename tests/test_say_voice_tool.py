"""tools/say_voice.py: draft voices with the macOS ``say`` voice for make_video.py."""

from __future__ import annotations

import importlib.util
import shutil
import sys
import wave
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "say_voice.py"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("say_voice", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["say_voice"] = module
    spec.loader.exec_module(module)
    return module


def test_pause_markers_become_say_silence(tool: ModuleType) -> None:
    text = "Năm bốn mươi, [pause 400ms] hai bà khởi nghĩa.[pause 1200ms]\n"
    assert tool.to_say_text(text) == (
        "Năm bốn mươi,  [[slnc 400]]  hai bà khởi nghĩa. [[slnc 1200]]"
    )


def test_text_without_pause_is_unchanged(tool: ModuleType) -> None:
    assert tool.to_say_text("Mê Linh.\n") == "Mê Linh."


def test_say_command_is_an_argument_list(tool: ModuleType, tmp_path: Path) -> None:
    cmd = tool.say_command("/usr/bin/say", tmp_path / "a b.wav", "Linh", 170)
    assert cmd[:6] == ["/usr/bin/say", "-v", "Linh", "-f", "-", "-o"]
    assert cmd[6] == str(tmp_path / "a b.wav")
    assert "--file-format=WAVE" in cmd
    assert cmd[-2:] == ["-r", "170"]


@pytest.mark.skipif(shutil.which("say") is None, reason="macOS say not available")
def test_writes_a_wav_and_no_partial(tool: ModuleType, tmp_path: Path) -> None:
    text = tmp_path / "s01.txt"
    text.write_text("Xin chào. [pause 300ms] Mê Linh.\n", encoding="utf-8")
    wav = tmp_path / "s01.wav"
    try:
        code = tool.main([str(text), str(wav)])
    except FileNotFoundError:  # pragma: no cover - say present but voice missing
        pytest.skip("say voice unavailable")
    if code != 0:
        pytest.skip("Linh voice not installed")
    with wave.open(str(wav), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getnframes() / w.getframerate() > 0.3
    assert not list(tmp_path.glob("*.partial.wav"))
