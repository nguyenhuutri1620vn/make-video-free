"""FFmpeg command for narration voices and ducked music (spec A.1.7, AC-19)."""

from __future__ import annotations

from pathlib import Path

import pytest

from history_shorts.config import AudioSpec
from history_shorts.ffmpeg import FfmpegInfo, VoiceInput, mux_cmd, voice_mux_cmd

INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))
VIDEO = Path("/t/v.mp4")
OUT = Path("/t/o.mp4")


def _graph(cmd: list[str]) -> str:
    return cmd[cmd.index("-filter_complex") + 1]


def test_voice_only_exact_graph() -> None:
    voices = [VoiceInput(Path("/n/s01.wav"), 300, 0.0)]
    cmd = voice_mux_cmd(INFO, VIDEO, OUT, 4.0, voices, None, 0.6, AudioSpec())
    assert cmd == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", "/t/v.mp4", "-i", "/n/s01.wav",
        "-filter_complex",
        "[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=0dB,adelay=300|300[v1];"
        "[v1]anull[voice];"
        "[voice]apad=whole_dur=4.000[padded];"
        "[padded]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=channel_layouts=stereo[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", "4.000", "-movflags", "+faststart", "/t/o.mp4",
    ]  # fmt: skip


def test_several_voices_are_summed_with_amix() -> None:
    voices = [VoiceInput(Path("a.wav"), 300, -2.0), VoiceInput(Path("b.wav"), 2300, 0.0)]
    graph = _graph(voice_mux_cmd(INFO, VIDEO, OUT, 5.0, voices, None, 0.6, AudioSpec()))
    assert "[1:a]" in graph and "[2:a]" in graph
    assert "volume=-2dB,adelay=300|300[v1]" in graph
    assert "[v1][v2]amix=inputs=2:normalize=0:duration=longest[voice]" in graph


def test_music_is_ducked_by_the_voice() -> None:
    voices = [VoiceInput(Path("a.wav"), 300, 0.0)]
    cmd = voice_mux_cmd(INFO, VIDEO, OUT, 6.0, voices, Path("m.mp3"), 0.6, AudioSpec())
    graph = _graph(cmd)
    assert cmd[cmd.index("-stream_loop") + 1] == "-1"
    assert "[2:a]atrim=0:6.000" in graph
    assert "[padded]asplit=2[vk][vm]" in graph
    assert (
        "[mus][vk]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[ducked]" in graph
    )
    assert "[ducked][vm]amix=inputs=2:normalize=0:duration=longest[mix]" in graph
    assert "[mix]loudnorm=I=-14:TP=-1.5" in graph


def test_theme_audio_settings_reach_the_graph() -> None:
    from history_shorts.config import DuckSpec

    spec = AudioSpec(
        loudness_lufs=-16.0,
        true_peak_db=-2.0,
        duck=DuckSpec(threshold=0.1, ratio=4.0, attack_ms=10.0, release_ms=250.0),
    )
    cmd = voice_mux_cmd(
        INFO, VIDEO, OUT, 6.0, [VoiceInput(Path("a.wav"), 0, 0.0)], Path("m.mp3"), 0.6, spec
    )
    graph = _graph(cmd)
    assert "loudnorm=I=-16:TP=-2:LRA=11" in graph
    assert "threshold=0.1:ratio=4:attack=10:release=250" in graph


def test_no_voice_needs_the_old_mux_command() -> None:
    with pytest.raises(ValueError):
        voice_mux_cmd(INFO, VIDEO, OUT, 4.0, [], None, 0.6, AudioSpec())


def test_v2_mux_command_untouched_without_voices() -> None:
    """AC-19: without voices the command is the one ``mux_cmd`` always built."""
    cmd = mux_cmd(INFO, VIDEO, OUT, 12.0, None, 0.6)
    assert "anullsrc=r=48000:cl=stereo" in cmd
    assert "loudnorm" not in " ".join(cmd)
