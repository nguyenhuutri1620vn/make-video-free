"""Spec A.2 (M8): motions, transitions, tones, text fade-in, sound effects and music cuts."""

from __future__ import annotations

import array
import math
import subprocess
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import requires_ffmpeg

from history_shorts import cues
from history_shorts.config import AudioSpec, ToneSpec, load_script, load_theme
from history_shorts.errors import ValidationFailed
from history_shorts.ffmpeg import (
    MOTIONS,
    FfmpegInfo,
    MixPlan,
    TextLayer,
    VoiceInput,
    clip_cmd,
    find_ffmpeg,
    mix_cmd,
    mux_cmd,
    probe,
    voice_mux_cmd,
    xfade_cmd,
)
from history_shorts.textures import tone_grade
from history_shorts.video import overlaps

INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))
ScriptFactory = Callable[..., Path]


def _v21(tmp_script: ScriptFactory, *slides: dict[str, Any]) -> Path:
    return tmp_script(slides=list(slides), extra={"schema_version": "2.1"})


# --- script and theme contract ------------------------------------------------------------


def test_a2_fields_parse(tmp_script: ScriptFactory) -> None:
    path = _v21(
        tmp_script,
        {"title": "A"},
        {
            "title": "B",
            "motion": "pan_left",
            "transition": "dissolve",
            "tone": "cold",
            "text_in": "fade",
            "music_cut": {"at": 0.5, "duration": 1.0},
        },
    )
    slide = load_script(path)[0].slides[1]
    assert (slide.motion, slide.transition, slide.tone, slide.text_in) == (
        "pan_left",
        "dissolve",
        "cold",
        "fade",
    )
    assert slide.music_cut is not None and slide.music_cut.duration == 1.0


def test_a2_defaults_keep_v20_behaviour(tmp_script: ScriptFactory) -> None:
    slide = load_script(tmp_script())[0].slides[0]
    assert (slide.transition, slide.tone, slide.text_in, slide.sfx, slide.music_cut) == (
        "cut",
        "none",
        "none",
        (),
        None,
    )


@pytest.mark.parametrize(
    "field", [{"transition": "fade"}, {"tone": "warm"}, {"motion": "zoom_out"}]
)
def test_a2_fields_need_schema_21(tmp_script: ScriptFactory, field: dict[str, Any]) -> None:
    path = tmp_script(slides=[{"title": "A"}, {"title": "B", **field}])
    with pytest.raises(ValidationFailed) as exc:
        load_script(path)
    assert '"2.1"' in str(exc.value.issues.items[0].message)


def test_unknown_transition_is_an_error(tmp_script: ScriptFactory) -> None:
    with pytest.raises(ValidationFailed):
        load_script(_v21(tmp_script, {"title": "A"}, {"title": "B", "transition": "spin"}))


def test_first_slide_transition_warns(tmp_script: ScriptFactory) -> None:
    _, warnings = load_script(_v21(tmp_script, {"title": "A", "transition": "fade"}))
    assert any("first slide" in w.message for w in warnings)


def test_sfx_resolves_relative_to_script(tmp_script: ScriptFactory) -> None:
    path = _v21(tmp_script, {"title": "A", "sfx": [{"file": "fx/drum.wav", "at": 0.2}]})
    (path.parent / "fx").mkdir()
    (path.parent / "fx" / "drum.wav").write_bytes(b"RIFF")
    cue = load_script(path)[0].slides[0].sfx[0]
    assert cue.path == (path.parent / "fx" / "drum.wav").resolve()
    assert (cue.at, cue.gain_db) == (0.2, 0.0)


def test_sfx_missing_file_is_an_error(tmp_script: ScriptFactory) -> None:
    path = _v21(tmp_script, {"title": "A", "sfx": [{"file": "nope.wav"}]})
    with pytest.raises(ValidationFailed) as exc:
        load_script(path)
    assert "file not found" in exc.value.issues.items[0].message


def test_too_many_sfx_is_an_error(tmp_script: ScriptFactory) -> None:
    path = _v21(tmp_script, {"title": "A", "sfx": [{"file": "a.wav"}] * 5})
    (path.parent / "a.wav").write_bytes(b"RIFF")
    with pytest.raises(ValidationFailed):
        load_script(path)


def test_theme_a2_defaults(theme: Any) -> None:
    assert theme.transition.duration == 0.5
    assert (theme.text_in.delay, theme.text_in.duration) == (0.3, 0.5)
    assert set(theme.tones) == {"warm", "cold", "gray"}


def test_theme_tone_override(tmp_theme: Callable[..., Path]) -> None:
    path = tmp_theme(extra={"tones": {"cold": {"saturation": 0.3, "tint": [0, 0, 255]}}})
    theme, _ = load_theme(path)
    assert theme.tones["cold"].saturation == 0.3
    assert theme.tones["cold"].tint == (0, 0, 255)
    assert theme.tones["cold"].brightness == 0.85  # default kept


# --- tone grade and text layer ------------------------------------------------------------


def test_tone_gray_removes_colour() -> None:
    img = np.random.default_rng(1).random((4, 4, 3), dtype=np.float32)
    out = tone_grade(img, ToneSpec(0.0, 1.0, (0, 0, 0), 0.0))
    assert np.allclose(out[..., 0], out[..., 1]) and np.allclose(out[..., 1], out[..., 2])


def test_tone_identity() -> None:
    img = np.random.default_rng(2).random((4, 4, 3), dtype=np.float32)
    out = tone_grade(img, ToneSpec(1.0, 1.0, (0, 0, 0), 0.0))
    assert np.allclose(out, img, atol=1e-6)


def test_tone_changes_scene_but_not_text(tmp_script: ScriptFactory, theme: Any) -> None:  # AC-23
    from history_shorts.compose import SlideContext, default_style, render_slide
    from history_shorts.text import plan_text

    plain = load_script(_v21(tmp_script, {"title": "Mê Linh"}))[0]
    toned = load_script(_v21(tmp_script, {"title": "Mê Linh", "tone": "gray"}))[0]

    def draw(script: Any) -> Any:
        ctx = SlideContext(script, theme, 0, default_style(theme), None, False)
        return np.asarray(render_slide(ctx), dtype=np.int16)

    a, b = draw(plain), draw(toned)
    assert np.abs(a - b).max() > 10
    line = plan_text(plain.slides[0], theme).lines[0]
    # fully covered title glyph pixels keep the exact title colour in both renders
    row = slice(line.y, line.y + 120)
    glyph = theme.palette[line.color_key]
    mask = np.all(a[row] == glyph, axis=2)
    assert mask.sum() > 500 and np.all(b[row][mask] == glyph)


def test_render_layers_split_text(tmp_script: ScriptFactory, theme: Any) -> None:
    from history_shorts.compose import SlideContext, default_style, render_layers

    script = load_script(_v21(tmp_script, {"title": "Mê Linh", "text_in": "fade"}))[0]
    background, text = render_layers(
        SlideContext(script, theme, 0, default_style(theme), None, False)
    )
    assert background.mode == "RGB" and text.mode == "RGBA"
    alpha = np.asarray(text)[..., 3]
    ys = np.nonzero(alpha)[0]
    assert ys.min() > 1100 and ys.max() < 1500  # only the title/subtitle band


# --- FFmpeg commands ----------------------------------------------------------------------


@pytest.mark.parametrize("motion", [m for m in MOTIONS if m != "none"])
def test_every_motion_builds_a_zoompan(motion: str) -> None:
    cmd = clip_cmd(INFO, Path("a.png"), Path("a.mp4"), 3.0, 30, 20, 0.3, 0.3, motion=motion)
    assert "zoompan" in cmd[cmd.index("-vf") + 1]


def test_pan_moves_the_view() -> None:
    left = clip_cmd(INFO, Path("a.png"), Path("a.mp4"), 3.0, 30, 20, 0, 0, motion="pan_left")
    vf = left[left.index("-vf") + 1]
    assert "z='1.10'" in vf and "(iw-iw/zoom)*(1-on/90)" in vf


def test_text_layer_clip_overlays_a_fading_layer() -> None:
    text = TextLayer(Path("t.png"), 0.3, 0.5)
    cmd = clip_cmd(
        INFO, Path("bg.png"), Path("a.mp4"), 3.0, 30, 20, 0.3, 0.3, "zoom_in", None, text
    )
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert cmd.count("-i") == 2 and "t.png" in cmd
    assert "fade=t=in:st=0.300:d=0.500:alpha=1" in graph
    assert "overlay=0:0" in graph and "zoompan" in graph


def test_overlaps_clamp_and_cut() -> None:
    gaps = overlaps([4.0, 0.6, 4.0, 4.0], ["cut", "fade", "cut", "dissolve"], 0.5, 30)
    assert gaps == [0.3, 0.0, 0.5]


def test_xfade_offsets_are_slide_starts() -> None:
    cmd = xfade_cmd(
        INFO,
        [Path("1.mp4"), Path("2.mp4"), Path("3.mp4")],
        [0.0, 4.0, 7.0],
        ["cut", "fade", "cut"],
        [0.5, 0.0],
        Path("o.mp4"),
        30,
        20,
    )
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.500:offset=4.000" in graph
    assert "[j1][s2]concat=n=2" in graph


def test_mix_cmd_without_a2_cues_is_unchanged() -> None:  # AC-25
    video, out, music = Path("v.mp4"), Path("o.mp4"), Path("m.mp3")
    voice = VoiceInput(Path("s01.wav"), 300, 0.0)
    audio = AudioSpec()
    assert mix_cmd(INFO, video, out, 9.0, MixPlan(), music, 0.6, audio) == mux_cmd(
        INFO, video, out, 9.0, music, 0.6
    )
    assert mix_cmd(INFO, video, out, 9.0, MixPlan(voices=(voice,)), music, 0.6, audio) == (
        voice_mux_cmd(INFO, video, out, 9.0, [voice], music, 0.6, audio)
    )
    # a cut without music changes nothing
    cut_only = MixPlan(cuts=((1.0, 2.0),))
    assert mix_cmd(INFO, video, out, 9.0, cut_only, None, 0.6, audio) == mux_cmd(
        INFO, video, out, 9.0, None, 0.6
    )


def test_mix_graph_places_sfx_after_music() -> None:
    plan = MixPlan(
        voices=(VoiceInput(Path("s.wav"), 300, 0.0),),
        sfx=(VoiceInput(Path("drum.wav"), 1500, -3.0),),
        cuts=((2.0, 3.0),),
    )
    cmd = mix_cmd(INFO, Path("v.mp4"), Path("o.mp4"), 9.0, plan, Path("m.mp3"), 0.6, AudioSpec())
    graph = cmd[cmd.index("-filter_complex") + 1]
    inputs = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-i"]
    assert inputs == ["v.mp4", "s.wav", "m.mp3", "drum.wav"]
    assert "[3:a]" in graph and "adelay=1500|1500" in graph and "volume=-3dB" in graph
    assert "abs(t-2.500)-0.500" in graph and "sidechaincompress" in graph
    assert "[ducked][vm][fx]amix=inputs=3" in graph


# --- cues ---------------------------------------------------------------------------------


def test_cue_timing(tmp_script: ScriptFactory) -> None:
    path = _v21(
        tmp_script,
        {"title": "A"},
        {
            "title": "B",
            "sfx": [{"file": "d.wav", "at": 0.5}],
            "music_cut": {"at": 1, "duration": 1},
        },
    )
    (path.parent / "d.wav").write_bytes(b"RIFF")
    script = load_script(path)[0]
    assert cues.sfx_inputs(script, [3.0, 4.0])[0].delay_ms == 3500
    assert cues.music_cuts(script, [3.0, 4.0]) == ((4.0, 5.0),)
    assert cues.cue_problems(script, [3.0, 4.0]) == []
    problems = cues.cue_problems(script, [3.0, 0.5], has_audio=lambda _p: False)
    assert {p.path for p in problems} == {
        "slides[1].sfx[0].at",
        "slides[1].sfx[0].file",
        "slides[1].music_cut",
    }


# --- real FFmpeg (AC-22, AC-24) -----------------------------------------------------------


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _tone(info: FfmpegInfo, path: Path, freq: int, seconds: float) -> Path:
    _run([
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
        "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(path),
    ])  # fmt: skip
    return path


def _rms_db(info: FfmpegInfo, media: Path, start: float, length: float, wav: Path) -> float:
    _run([
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(media),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(wav),
    ])  # fmt: skip
    with wave.open(str(wav), "rb") as handle:
        samples = array.array("h")
        samples.frombytes(handle.readframes(handle.getnframes()))
    rms = math.sqrt(sum(s * s for s in samples) / max(len(samples), 1))
    return 20 * math.log10(max(rms, 1e-9) / 32768)


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_transitions_keep_the_total(tmp_path: Path) -> None:  # AC-22
    info = find_ffmpeg()
    clips = []
    for n, (seconds, colour) in enumerate([(2.5, "red"), (1.5, "blue"), (2.0, "green")]):
        clip = tmp_path / f"c{n}.mp4"
        _run([
            str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={colour}:s=108x192:r=30:d={seconds}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip),
        ])  # fmt: skip
        clips.append(clip)
    # clip 0 runs 0.5 s past slide 1's start; slide durations are 2.0, 1.5, 2.0
    out = tmp_path / "joined.mp4"
    _run(xfade_cmd(info, clips, [0.0, 2.0, 3.5], ["cut", "fade", "cut"], [0.5, 0.0], out, 30, 20))
    assert probe(info, out).duration == pytest.approx(5.5, abs=0.1)


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_sfx_and_music_cut_are_audible(tmp_path: Path) -> None:  # AC-24
    info = find_ffmpeg()
    video = tmp_path / "v.mp4"
    _run([
        str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=108x192:r=30:d=6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
    ])  # fmt: skip
    drum = _tone(info, tmp_path / "drum.wav", 200, 0.4)
    music = _tone(info, tmp_path / "music.wav", 440, 6.0)
    fx_out = tmp_path / "fx.mp4"
    plan = MixPlan(sfx=(VoiceInput(drum, 3000, 0.0),))
    _run(mix_cmd(info, video, fx_out, 6.0, plan, None, 1.0, AudioSpec()))
    before = _rms_db(info, fx_out, 2.7, 0.2, tmp_path / "a.wav")
    after = _rms_db(info, fx_out, 3.05, 0.2, tmp_path / "b.wav")
    assert after > before + 20

    cut_out = tmp_path / "cut.mp4"
    _run(mix_cmd(info, video, cut_out, 6.0, MixPlan(cuts=((2.0, 3.0),)), music, 1.0, AudioSpec()))
    playing = _rms_db(info, cut_out, 1.0, 0.5, tmp_path / "c.wav")
    silent = _rms_db(info, cut_out, 2.2, 0.6, tmp_path / "d.wav")
    assert silent < playing - 30
