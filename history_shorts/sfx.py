"""Synthesized sound effects (M9): gong, drum, bell, whoosh, wind and water.

Every sound is built from sines and filtered noise with numpy/scipy, then given a small
synthesized room (convolution with a decaying-noise impulse response). Nothing is
downloaded or recorded and no model is involved (C-01). Each call draws a slight pitch,
level and timbre variation from its RNG, so two gongs never sound identical while the same
RNG key always gives the same samples (determinism).
"""

from __future__ import annotations

import wave
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final

import numpy as np
from numpy.typing import NDArray
from scipy.signal import butter, fftconvolve, sosfilt

from history_shorts.config import SfxSpec

Audio = NDArray[np.float32]
Mono = NDArray[np.float64]

PEAK_DBFS: Final = -1.0
END_FADE_SECONDS: Final = 0.02  # every sound ends on a short fade, so no click at the cut
BED_FADE_SECONDS: Final = 0.5  # wind and water swell in and out
NOMINAL_SECONDS: Final[Mapping[str, float]] = MappingProxyType(
    {"gong": 4.0, "drum": 1.5, "bell": 3.0, "whoosh": 0.9}
)
HITS: Final = ("gong", "drum", "bell")  # get a reverb tail after their nominal length

# Gong: (frequency ratio, amplitude, decay seconds, bloom seconds) per partial over GONG_F0.
GONG_F0: Final = 110.0
GONG_PARTIALS: Final = (
    (1.0, 1.0, 2.2, 0.02),
    (1.52, 0.7, 1.8, 0.06),
    (2.0, 0.45, 1.6, 0.10),
    (2.74, 0.5, 1.3, 0.14),
    (3.43, 0.3, 1.0, 0.18),
    (4.18, 0.25, 0.8, 0.22),
    (5.41, 0.15, 0.6, 0.25),
)
GONG_BEAT: Final = 0.0015  # each partial is a detuned pair: slow beating, a metallic shimmer
GONG_GLIDE: Final = 0.006  # pitch sinks by this fraction after the strike
GONG_GLIDE_SECONDS: Final = 0.8
GONG_MALLET: Final = (0.25, 0.03, 80.0, 900.0)  # level, decay s, band low/high Hz

# Drum: a falling-pitch thump, a skin slap, a body tone and faint bronze ring.
DRUM_PITCH: Final = (120.0, 55.0, 0.06)  # start Hz, end Hz, glide time constant
DRUM_THUMP_DECAY: Final = 0.35
DRUM_SKIN: Final = (0.3, 0.03, 150.0, 900.0)
DRUM_BODY: Final = (180.0, 0.3, 0.15)  # Hz, level, decay s
DRUM_RING: Final = ((420.0, 0.08, 0.5), (660.0, 0.05, 0.4))

# Temple bell: (ratio, amplitude, decay seconds) over BELL_F0, plus a bright strike.
BELL_F0: Final = 520.0
BELL_PARTIALS: Final = (
    (0.5, 0.35, 3.0),
    (1.0, 1.0, 2.4),
    (1.183, 0.5, 1.8),
    (1.506, 0.6, 1.6),
    (2.0, 0.4, 1.2),
    (2.514, 0.3, 0.9),
    (2.662, 0.2, 0.7),
    (3.011, 0.15, 0.5),
)
BELL_STRIKE: Final = (0.3, 0.005, 2000.0, 9000.0)

# Noise bands (centre Hz) for whoosh, wind and water; each band is a third of an octave.
BAND_WIDTH: Final = 1.25
WHOOSH_BANDS: Final = (300.0, 450.0, 700.0, 1000.0, 1500.0, 2200.0, 3300.0, 5000.0)
WHOOSH_SWEEP: Final = (450.0, 2600.0)  # band centre at the start and at the peak (Hz)
WHOOSH_SPREAD: Final = 0.55  # octaves: how many bands sound around the moving centre
WIND_BANDS: Final = (150.0, 220.0, 330.0, 500.0, 750.0, 1100.0, 1600.0)
WIND_GUSTS: Final = (0.08, 0.6, 3)  # slowest Hz, fastest Hz, number of sines per band
WIND_TILT: Final = 1.0  # band level falls as (lowest / centre) ** tilt: a dark, soft wind
WATER_BANDS: Final = (300.0, 450.0, 700.0, 1000.0, 1500.0, 2200.0, 3000.0)
WATER_SWELLS: Final = (0.25, 0.9, 3)
WATER_TILT: Final = 0.5
WATER_DROPS: Final = (6.0, (900.0, 1700.0), 0.02, 0.35)  # per s, Hz range, decay s, level
STEREO_SHARE: Final = 0.6  # wind/water: share of noise common to both channels
REVERB_DAMPING_HZ: Final = 4000.0
AMP_JITTER: Final = 0.08  # per-partial level variation of a hit


@dataclass(frozen=True, slots=True)
class SynthJob:
    """A synthesized cue on the timeline (M9); the RNG key is (seed, slide, cue)."""

    name: str
    slide_index: int
    cue_index: int
    delay_ms: int
    gain_db: float
    duration: float | None
    pan: tuple[float, float]
    auto: bool


# --------------------------------------------------------------------------------------
# Building blocks
# --------------------------------------------------------------------------------------


def _time(seconds: float, sr: int) -> Mono:
    return np.arange(round(seconds * sr), dtype=np.float64) / sr


def _band(x: Mono, lo: float, hi: float, sr: int) -> Mono:
    sos = butter(2, [lo, min(hi, sr * 0.45)], btype="bandpass", fs=sr, output="sos")
    return np.asarray(sosfilt(sos, x), dtype=np.float64)


def _burst(rng: np.random.Generator, t: Mono, sr: int, spec: tuple[float, ...]) -> Mono:
    """A noise transient (mallet, skin, strike): ``(level, decay s, low Hz, high Hz)``."""
    level, decay, lo, hi = spec
    noise = _band(rng.standard_normal(len(t)), lo, hi, sr)
    noise /= np.abs(noise).max() + 1e-12
    return level * noise * np.exp(-t / decay)


def _partial(t: Mono, freq: Mono | float, amp: float, decay: float, phase: float) -> Mono:
    """A decaying sine whose (possibly time-varying) frequency is integrated into phase."""
    inc = np.broadcast_to(np.asarray(freq, dtype=np.float64), t.shape)
    step = t[1] - t[0] if len(t) > 1 else 0.0
    angle = 2 * np.pi * np.cumsum(inc) * step + phase
    return amp * np.sin(angle) * np.exp(-t / decay)


def _bands(rng: np.random.Generator, n: int, centres: Sequence[float], sr: int) -> Mono:
    """Unit-RMS band-passed noise, one row per centre frequency."""
    noise = rng.standard_normal(n)
    rows = [_band(noise, f / BAND_WIDTH, f * BAND_WIDTH, sr) for f in centres]
    out = np.stack(rows)
    rms = np.sqrt(np.mean(np.square(out), axis=1, keepdims=True)) + 1e-12
    return np.asarray(out / rms, dtype=np.float64)


def _slow(rng: np.random.Generator, t: Mono, spec: tuple[float, float, int]) -> Mono:
    """Smooth random modulation in 0…1: a few slow sines with random phases."""
    lo, hi, count = spec
    freqs = rng.uniform(lo, hi, count)
    phases = rng.uniform(0, 2 * np.pi, count)
    wave_sum = np.sin(2 * np.pi * freqs[:, None] * t[None, :] + phases[:, None]).sum(axis=0)
    return np.asarray(0.5 + 0.5 * wave_sum / count, dtype=np.float64)


def _fade_edges(x: Mono, sr: int, fade_in: float, fade_out: float) -> Mono:
    n = len(x)
    env = np.ones(n)
    a, b = min(round(fade_in * sr), n), min(round(fade_out * sr), n)
    if a:
        env[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2
    if b:
        env[n - b :] = np.minimum(env[n - b :], np.cos(np.linspace(0, np.pi / 2, b)) ** 2)
    return x * env if x.ndim == 1 else x * env[:, None]


def _pan(x: Mono, pan: tuple[float, float]) -> Mono:
    """Constant-power pan from ``pan[0]`` to ``pan[1]`` (−1 left … +1 right)."""
    p = np.linspace(pan[0], pan[1], len(x))
    return np.stack([x * np.sqrt((1 - p) / 2), x * np.sqrt((1 + p) / 2)], axis=1)


def _reverb(x: Mono, rng: np.random.Generator, spec: SfxSpec) -> Mono:
    """A synthesized room: decaying noise IR (−60 dB at ``reverb_seconds``), one per channel."""
    sr, n = spec.sample_rate, len(x)
    t = _time(spec.reverb_seconds, sr)
    damp = butter(1, REVERB_DAMPING_HZ, btype="lowpass", fs=sr, output="sos")
    out = np.empty_like(x)
    for ch in range(x.shape[1]):
        ir = sosfilt(damp, rng.standard_normal(len(t))) * np.exp(-6.9 * t / spec.reverb_seconds)
        ir /= np.sqrt(np.sum(np.square(ir))) + 1e-12
        wet = fftconvolve(x[:, ch], ir)[:n]
        dry_rms = np.sqrt(np.mean(np.square(x[:, ch]))) + 1e-12
        wet *= dry_rms / (np.sqrt(np.mean(np.square(wet))) + 1e-12)
        out[:, ch] = (1 - spec.reverb_wet) * x[:, ch] + spec.reverb_wet * wet
    return out


def _normalise(x: Mono) -> Audio:
    peak = np.abs(x).max()
    target = 10 ** (PEAK_DBFS / 20)
    return np.asarray(x * (target / peak) if peak > 0 else x, dtype=np.float32)


# --------------------------------------------------------------------------------------
# Sounds (mono dry signals)
# --------------------------------------------------------------------------------------


def _gong(rng: np.random.Generator, t: Mono, sr: int, jitter: float) -> Mono:
    f0 = GONG_F0 * jitter
    glide = 1 - GONG_GLIDE * (1 - np.exp(-t / GONG_GLIDE_SECONDS))
    out = _burst(rng, t, sr, GONG_MALLET)
    for ratio, amp, decay, bloom in GONG_PARTIALS:
        level = amp * rng.uniform(1 - AMP_JITTER, 1 + AMP_JITTER)
        rise = 1 - np.exp(-t / bloom)
        phase = rng.uniform(0, 2 * np.pi)  # shared: the pair starts in phase, then beats
        for detune in (1 - GONG_BEAT, 1 + GONG_BEAT):
            freq = f0 * ratio * detune * glide
            out = out + rise * _partial(t, freq, level / 2, decay, phase)
    return out


def _drum(rng: np.random.Generator, t: Mono, sr: int, jitter: float) -> Mono:
    start, end, tau = DRUM_PITCH
    freq = (end + (start - end) * np.exp(-t / tau)) * jitter
    out = _partial(t, freq, 1.0, DRUM_THUMP_DECAY, 0.0)
    out = out + _burst(rng, t, sr, DRUM_SKIN)
    hz, level, decay = DRUM_BODY
    out = out + _partial(t, hz * jitter, level, decay, rng.uniform(0, 2 * np.pi))
    for hz, level, decay in DRUM_RING:
        out = out + _partial(t, hz * jitter, level, decay, rng.uniform(0, 2 * np.pi))
    return out


def _bell(rng: np.random.Generator, t: Mono, sr: int, jitter: float) -> Mono:
    out = _burst(rng, t, sr, BELL_STRIKE)
    for ratio, amp, decay in BELL_PARTIALS:
        level = amp * rng.uniform(1 - AMP_JITTER, 1 + AMP_JITTER)
        out = out + _partial(t, BELL_F0 * jitter * ratio, level, decay, rng.uniform(0, 2 * np.pi))
    return out


def _whoosh(rng: np.random.Generator, t: Mono, sr: int, jitter: float) -> Mono:
    """Noise whose bright band rises to the middle and falls back, swelling then fading."""
    p = t / t[-1] if len(t) > 1 else t
    lo, hi = (f * jitter for f in WHOOSH_SWEEP)
    centre = np.log2(lo) + (np.log2(hi) - np.log2(lo)) * np.sin(np.pi * p)
    bands = _bands(rng, len(t), WHOOSH_BANDS, sr)
    weights = np.exp(-(((np.log2(WHOOSH_BANDS)[:, None] - centre[None, :]) / WHOOSH_SPREAD) ** 2))
    swell = np.sin(np.pi * p) ** 1.5
    return np.asarray((bands * weights).sum(axis=0) * swell, dtype=np.float64)


def _bed(
    rng: np.random.Generator,
    t: Mono,
    sr: int,
    centres: Sequence[float],
    mod: tuple[float, float, int],
    tilt: float,
) -> Mono:
    """Stereo noise bands, each swelling on its own slow, smooth curve."""
    levels = (min(centres) / np.asarray(centres))[:, None] ** tilt
    common = _bands(rng, len(t), centres, sr)
    channels = []
    for _ in range(2):
        own = _bands(rng, len(t), centres, sr)
        mix = STEREO_SHARE * common + (1 - STEREO_SHARE) * own
        gains = np.stack([_slow(rng, t, mod) for _ in centres])
        channels.append((mix * levels * gains**2).sum(axis=0))
    return np.stack(channels, axis=1)


def _wind(rng: np.random.Generator, t: Mono, sr: int, jitter: float) -> Mono:
    return _bed(rng, t, sr, [f * jitter for f in WIND_BANDS], WIND_GUSTS, WIND_TILT)


def _water(rng: np.random.Generator, t: Mono, sr: int, jitter: float) -> Mono:
    out = _bed(rng, t, sr, [f * jitter for f in WATER_BANDS], WATER_SWELLS, WATER_TILT)
    rate, (lo, hi), decay, level = WATER_DROPS
    count = rng.poisson(rate * t[-1]) if len(t) else 0
    rms = np.sqrt(np.mean(np.square(out))) + 1e-12
    span = round(decay * 6 * sr)
    dt = t[:span]
    for _ in range(count):
        start = int(rng.integers(0, max(len(t) - span, 1)))
        f = rng.uniform(lo, hi)
        drop = np.sin(2 * np.pi * f * dt * (1 + dt / (2 * decay * 6))) * np.exp(-dt / decay)
        side = rng.uniform(0.2, 0.8)
        seg = out[start : start + span]
        amp = level * rms * rng.uniform(0.4, 1.0) * 3
        seg += amp * np.stack([drop * (1 - side), drop * side], axis=1)[: len(seg)]
    return out


Recipe = Callable[[np.random.Generator, Mono, int, float], Mono]
_RECIPES: Final[Mapping[str, Recipe]] = MappingProxyType(
    {
        "gong": _gong,
        "drum": _drum,
        "bell": _bell,
        "whoosh": _whoosh,
        "wind": _wind,
        "water": _water,
    }
)
BEDS: Final = ("wind", "water")


def _seconds(name: str, spec: SfxSpec, duration: float | None) -> float:
    if name in BEDS:
        if duration is None:
            raise ValueError(f"{name} needs a duration")
        return duration
    if name in HITS:
        return NOMINAL_SECONDS[name] + spec.reverb_seconds
    return duration if duration is not None else NOMINAL_SECONDS[name]


def synth(
    name: str,
    rng: np.random.Generator,
    spec: SfxSpec,
    *,
    duration: float | None = None,
    pan: tuple[float, float] = (0.0, 0.0),
) -> Audio:
    """One sound as float32 stereo ``(frames, 2)``, peaking at ``PEAK_DBFS``.

    ``duration`` sets the length of a bed (``wind``, ``water``, required) or a ``whoosh``;
    hits (``gong``, ``drum``, ``bell``) last their nominal length plus the reverb tail.
    ``pan`` moves the source from ``pan[0]`` to ``pan[1]`` (−1 left … +1 right).
    """
    recipe = _RECIPES.get(name)
    if recipe is None:
        raise ValueError(f"unknown sound {name!r}; allowed: {', '.join(_RECIPES)}")
    sr = spec.sample_rate
    t = _time(_seconds(name, spec, duration), sr)
    jitter = 1 + rng.uniform(-spec.jitter, spec.jitter)
    dry = recipe(rng, t, sr, jitter)
    stereo = dry if dry.ndim == 2 else _pan(dry, pan)
    wet = _reverb(stereo, rng, spec)
    fade = BED_FADE_SECONDS if name in BEDS else 0.0
    return _normalise(_fade_edges(wet, sr, fade, max(fade, END_FADE_SECONDS)))


def write_wav(samples: Audio, path: Path, sample_rate: int) -> None:
    """Write float stereo samples as 16-bit PCM WAV (clipped to ±1)."""
    pcm = (np.clip(samples, -1, 1) * 32767).round().astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(samples.shape[1])
        out.setsampwidth(2)
        out.setframerate(sample_rate)
        out.writeframes(pcm.tobytes())
