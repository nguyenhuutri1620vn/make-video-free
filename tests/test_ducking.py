"""Music ducking under the voice, measured on real FFmpeg output (AC-20, spec A.1.7).

Two muxes share the same video, music and timing. In the reference mux the voice is at -60 dB,
so the sidechain key stays silent and the music is not ducked; in the ducked mux the voice is
at 0 dB. Each file's music band (440 Hz) is compared between a voiced window and a voice-free
window. Dividing one ratio by the other cancels the global ``loudnorm`` gain, and the 1 kHz voice
is kept out of the measurement by the band-pass filter.
"""

from __future__ import annotations

import array
import math
import subprocess
import wave
from pathlib import Path

import pytest
from conftest import requires_ffmpeg

from history_shorts.config import AudioSpec
from history_shorts.ffmpeg import FfmpegInfo, VoiceInput, find_ffmpeg, probe, voice_mux_cmd

pytestmark = [pytest.mark.ffmpeg, requires_ffmpeg]

TOTAL = 6.0
VOICE_START = 2.0  # seconds; the voice is 1 s long
VOICED = (2.2, 0.6)  # inside the voice
FREE = (3.6, 1.0)  # after the 300 ms release, before the end


def _tone(info: FfmpegInfo, path: Path, freq: int, seconds: float) -> Path:
    cmd = [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
        "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(path),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def _silent_video(info: FfmpegInfo, path: Path) -> Path:
    cmd = [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=108x192:r=30:d={TOTAL}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    return path


def _mux(
    info: FfmpegInfo, video: Path, music: Path, voice: Path, gain_db: float, out: Path
) -> Path:
    clip = VoiceInput(path=voice, delay_ms=round(VOICE_START * 1000), gain_db=gain_db)
    cmd = voice_mux_cmd(info, video, out, TOTAL, [clip], music, 1.0, AudioSpec())
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _band_rms_db(info: FfmpegInfo, media: Path, start: float, length: float, wav: Path) -> float:
    """RMS level in dB of the 440 Hz band of the media's audio over a window."""
    cmd = [
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(media),
        "-vn", "-af", "bandpass=f=440:width_type=h:w=100",
        "-ac", "1", "-ar", "16000", "-f", "wav", str(wav),
    ]  # fmt: skip
    subprocess.run(cmd, check=True, capture_output=True)
    with wave.open(str(wav), "rb") as handle:
        samples = array.array("h")
        samples.frombytes(handle.readframes(handle.getnframes()))
    assert len(samples) > 0
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    return 20 * math.log10(max(rms, 1e-9) / 32768)


def test_voice_ducks_music_by_several_dB(tmp_path: Path) -> None:  # AC-20
    info = find_ffmpeg()
    video = _silent_video(info, tmp_path / "video.mp4")
    music = _tone(info, tmp_path / "music.wav", 440, TOTAL)
    voice = _tone(info, tmp_path / "voice.wav", 1000, 1.0)
    ducked = _mux(info, video, music, voice, 0.0, tmp_path / "ducked.mp4")
    plain = _mux(info, video, music, voice, -60.0, tmp_path / "plain.mp4")

    def swing(media: Path, name: str) -> float:
        """Music level in the voiced window relative to the voice-free window, in dB."""
        voiced = _band_rms_db(info, media, *VOICED, tmp_path / f"{name}_v.wav")
        free = _band_rms_db(info, media, *FREE, tmp_path / f"{name}_f.wav")
        return voiced - free

    drop = swing(ducked, "ducked") - swing(plain, "plain")
    assert drop <= -2.0, f"music only dropped {drop:.2f} dB under the voice"
    assert drop >= -12.0, f"ducking {drop:.2f} dB is stronger than the theme's ratio allows"


def test_mix_keeps_the_audio_for_the_whole_video(tmp_path: Path) -> None:
    """Regression: the sidechain used to stop at the last voice, so the music and the audio
    stream ended early (a 1 s voice at 2 s left 3 s of audio in a 6 s video)."""
    info = find_ffmpeg()
    video = _silent_video(info, tmp_path / "video.mp4")
    music = _tone(info, tmp_path / "music.wav", 440, TOTAL)
    voice = _tone(info, tmp_path / "voice.wav", 1000, 1.0)
    out = _mux(info, video, music, voice, 0.0, tmp_path / "out.mp4")
    result = probe(info, out)
    assert result.audio_duration == pytest.approx(TOTAL, abs=0.1)
