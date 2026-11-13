"""Synthesized sound effects (M9, AC-26)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from history_shorts.config import SfxSpec
from history_shorts.script_config import SOUND_NAMES
from history_shorts.sfx import synth, write_wav

SPEC = SfxSpec()
SR = SPEC.sample_rate
BEDS = {"wind": 3.0, "water": 3.0}


def _rng(*key: int) -> np.random.Generator:
    return np.random.default_rng([7, *key])


def _make(name: str, *key: int) -> np.ndarray:
    return synth(name, _rng(0, 0, *key), SPEC, duration=BEDS.get(name))


def _db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12))


def centroid_hz(x: np.ndarray, sr: int) -> float:
    """Power-weighted spectral centroid (robust to the long, quiet noise floor of a tail)."""
    mono = x.mean(axis=1)
    spectrum = np.abs(np.fft.rfft(mono)) ** 2
    freqs = np.fft.rfftfreq(len(mono), 1 / sr)
    return float((spectrum * freqs).sum() / spectrum.sum())


@pytest.mark.parametrize("name", SOUND_NAMES)
def test_deterministic(name: str) -> None:
    assert np.array_equal(_make(name), _make(name))


@pytest.mark.parametrize("name", SOUND_NAMES)
def test_finite_stereo_and_peak(name: str) -> None:
    x = _make(name)
    assert x.dtype == np.float32 and x.ndim == 2 and x.shape[1] == 2
    assert np.isfinite(x).all()
    peak = 20 * np.log10(np.abs(x).max())
    assert -3.0 < peak <= -1.0 + 1e-3


def test_jitter_varies() -> None:
    a, b = _make("gong"), _make("gong", 1)
    assert not np.array_equal(a, b)
    assert centroid_hz(a, SR) == pytest.approx(centroid_hz(b, SR), rel=0.10)


@pytest.mark.parametrize(
    ("name", "lo", "hi"),
    [
        ("gong", 100, 600),
        ("drum", 50, 300),
        ("bell", 400, 2000),
        ("whoosh", 800, 4000),
        ("wind", 120, 800),
        ("water", 400, 2000),
    ],
)
def test_centroid_ranges(name: str, lo: float, hi: float) -> None:
    assert lo <= centroid_hz(_make(name), SR) <= hi


def test_gong_decays() -> None:
    x = _make("gong")
    half = SR // 2
    assert _db(x[-half:]) < _db(x[:half]) - 20


def test_drum_is_short() -> None:
    x = _make("drum")
    energy = np.square(x).sum(axis=1)
    assert energy[SR:].sum() < 0.05 * energy.sum()


def test_bed_length_and_fades() -> None:
    x = synth("wind", _rng(0, 0), SPEC, duration=3.0)
    assert len(x) == 3 * SR
    edge = SR // 100
    assert _db(x[:edge]) < -40 and _db(x[-edge:]) < -40


def test_whoosh_duration_follows_request() -> None:
    assert len(synth("whoosh", _rng(0, 0), SPEC, duration=1.2)) == round(1.2 * SR)


def test_pan_moves() -> None:
    x = synth("whoosh", _rng(0, 0), SPEC, pan=(1.0, -1.0))
    third = len(x) // 3
    first, last = x[:third], x[-third:]
    assert np.square(first[:, 1]).sum() > 2 * np.square(first[:, 0]).sum()
    assert np.square(last[:, 0]).sum() > 2 * np.square(last[:, 1]).sum()


def test_write_wav_roundtrip(tmp_path: Path) -> None:
    x = _make("bell")
    path = tmp_path / "bell.wav"
    write_wav(x, path, SR)
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, SR)
        assert w.getnframes() == len(x)


def test_unknown_sound_raises() -> None:
    with pytest.raises(ValueError, match="trumpet"):
        synth("trumpet", _rng(0, 0), SPEC)
