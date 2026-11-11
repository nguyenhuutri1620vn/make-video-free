"""Narration export, audio manifest checks and voice timing (spec A.1.3–A.1.7, AC-16..18)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from history_shorts import audio
from history_shorts.config import AudioSpec, load_script
from history_shorts.errors import Issues

Make = Callable[..., Path]


def _narrated_script(make: Make, slides: list[dict[str, Any]]) -> Any:
    path = make(extra={"schema_version": "2.1"}, slides=slides)
    script, _ = load_script(path)
    return script


@pytest.fixture
def narrated(tmp_script: Make) -> Any:
    return _narrated_script(
        tmp_script,
        [
            {"title": "Mở đầu", "id": "s01", "narration": "Năm bốn mươi.\n[pause 400ms]"},
            {"title": "Tiếp", "id": "s02", "narration": "Hai Bà Trưng khởi nghĩa."},
            {"title": "Không lời", "id": "s03"},
        ],
    )


# --------------------------------------------------------------------------------------
# Export (AC-16)
# --------------------------------------------------------------------------------------


def test_export_writes_one_txt_per_narrated_slide(narrated: Any, tmp_path: Path) -> None:
    out = tmp_path / "narration"
    manifest_path = audio.export_narration(narrated, out)
    assert sorted(p.name for p in out.iterdir()) == ["manifest.json", "s01.txt", "s02.txt"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["kind"] == "history-shorts.narration"
    assert manifest["schema_version"] == "1.0"
    assert [seg["id"] for seg in manifest["segments"]] == ["s01", "s02"]


def test_export_sha_matches_file_bytes(narrated: Any, tmp_path: Path) -> None:
    out = tmp_path / "narration"
    manifest = json.loads(audio.export_narration(narrated, out).read_text(encoding="utf-8"))
    for seg in manifest["segments"]:
        data = (out / seg["file"]).read_bytes()
        assert seg["text_sha256"] == hashlib.sha256(data).hexdigest()
        assert data.endswith(b"\n") and not data.endswith(b"\n\n")


def test_export_second_run_is_byte_identical(narrated: Any, tmp_path: Path) -> None:
    out = tmp_path / "narration"
    first = audio.export_narration(narrated, out)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    second = audio.export_narration(narrated, out)
    assert first == second
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_export_text_is_utf8_without_bom(narrated: Any, tmp_path: Path) -> None:
    out = tmp_path / "narration"
    audio.export_narration(narrated, out)
    data = (out / "s02.txt").read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8") == "Hai Bà Trưng khởi nghĩa.\n"


# --------------------------------------------------------------------------------------
# Manifest loading
# --------------------------------------------------------------------------------------


def _write_audio_manifest(folder: Path, **overrides: Any) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "kind": "history-shorts.audio",
        "schema_version": "1.0",
        "segments": [],
    }
    data.update(overrides)
    path = folder / "audio_manifest.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _segment(file: str = "s01.wav", sid: str = "s01", digest: str = "0" * 64) -> dict[str, Any]:
    return {"id": sid, "file": file, "text_sha256": digest}


def test_manifest_loads_valid_file(tmp_path: Path) -> None:
    path = _write_audio_manifest(tmp_path, segments=[_segment()])
    issues = Issues()
    manifest = audio.load_manifest(path, issues)
    assert issues.errors == []
    assert manifest is not None and set(manifest.segments) == {"s01"}


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"kind": "other"}, 'must be "history-shorts.audio"'),
        ({"schema_version": "2.0"}, "unsupported schema_version"),
        ({"segments": [_segment(file="/etc/x.wav")]}, "relative path"),
        ({"segments": [_segment(file="../x.wav")]}, "relative path"),
        ({"segments": [_segment(), _segment()]}, 'duplicate segment id "s01"'),
        ({"segments": [{"id": "s01"}]}, "required"),
    ],
)
def test_manifest_rejects_bad_content(
    tmp_path: Path, overrides: dict[str, Any], fragment: str
) -> None:
    base = {"kind": "history-shorts.audio", "schema_version": "1.0", "segments": []}
    path = _write_audio_manifest(tmp_path, **{**base, **overrides})
    issues = Issues()
    assert audio.load_manifest(path, issues) is None
    assert any(fragment in i.message for i in issues.errors)


def test_manifest_missing_segments_key(tmp_path: Path) -> None:
    path = tmp_path / "audio_manifest.json"
    path.write_text('{"kind": "history-shorts.audio", "schema_version": "1.0"}', encoding="utf-8")
    issues = Issues()
    assert audio.load_manifest(path, issues) is None
    assert any(i.path == "segments" for i in issues.errors)


def test_gain_outside_range_is_an_error(tmp_path: Path) -> None:
    seg = {**_segment(), "gain_db": 20}
    path = _write_audio_manifest(tmp_path, segments=[seg])
    issues = Issues()
    assert audio.load_manifest(path, issues) is None
    assert any("must be" in i.message for i in issues.errors)


# --------------------------------------------------------------------------------------
# Matching voices to the script and timing (AC-17, AC-18)
# --------------------------------------------------------------------------------------


def _manifest_for(
    script: Any, folder: Path, lengths: dict[str, float] | None = None
) -> tuple[Path, audio.AudioManifest]:
    """Write a manifest with matching hashes and a placeholder WAV for every narrated slide."""
    folder.mkdir(parents=True, exist_ok=True)
    segments = []
    for slide in script.slides:
        if slide.narration is None:
            continue
        wav = folder / f"{slide.id}.wav"
        wav.write_bytes(b"RIFF")
        segments.append(
            {
                "id": slide.id,
                "file": wav.name,
                "text_sha256": audio.narration.text_sha256(slide.narration),
            }
        )
    path = _write_audio_manifest(folder, segments=segments)
    issues = Issues()
    manifest = audio.load_manifest(path, issues)
    assert manifest is not None, issues.items
    return path, manifest


def _lengths(lengths: dict[str, float]) -> Callable[[Path], float]:
    def measure(path: Path) -> float:
        return lengths[path.stem]

    return measure


def test_timing_uses_required_length_and_frame_grid(
    narrated: Any, theme: Any, tmp_path: Path
) -> None:
    _, manifest = _manifest_for(narrated, tmp_path / "voice")
    issues = Issues()
    plan = audio.plan_audio(narrated, theme, manifest, _lengths({"s01": 2.0, "s02": 3.0}), issues)
    assert issues.errors == [] and plan is not None
    fps = theme.video.fps
    lead, tail = theme.audio.lead_in, theme.audio.tail
    assert plan.durations[0] == audio.ceil_to_frame(lead + 2.0 + tail, fps)
    assert plan.durations[1] == audio.ceil_to_frame(lead + 3.0 + tail, fps)
    # slide without voice keeps FR-83 timing
    assert plan.durations[2] == pytest.approx(2.5)


def test_ceil_to_frame_is_exact_on_frame_boundaries() -> None:
    assert audio.ceil_to_frame(2.0, 30) == pytest.approx(2.0)
    assert audio.ceil_to_frame(2.0000001, 30) == pytest.approx(2.0333333, abs=1e-6)
    assert audio.ceil_to_frame(2.01, 30) == pytest.approx(2.0333333, abs=1e-6)


def test_explicit_duration_wins_when_long_enough(
    tmp_script: Make, theme: Any, tmp_path: Path
) -> None:
    script = _narrated_script(
        tmp_script, [{"title": "A", "id": "a", "narration": "Ngắn.", "duration": 6.0}]
    )
    _, manifest = _manifest_for(script, tmp_path / "voice")
    issues = Issues()
    plan = audio.plan_audio(script, theme, manifest, _lengths({"a": 1.0}), issues)
    assert issues.errors == [] and plan is not None
    assert plan.durations == (6.0,)


def test_explicit_duration_shorter_than_voice_is_an_error(
    tmp_script: Make, theme: Any, tmp_path: Path
) -> None:
    script = _narrated_script(
        tmp_script, [{"title": "A", "id": "a", "narration": "Dài.", "duration": 2.0}]
    )
    _, manifest = _manifest_for(script, tmp_path / "voice")
    issues = Issues()
    assert audio.plan_audio(script, theme, manifest, _lengths({"a": 5.0}), issues) is None
    assert any("shorter than the voice needs" in i.message for i in issues.errors)


def test_slide_longer_than_15_seconds_is_an_error(
    tmp_script: Make, theme: Any, tmp_path: Path
) -> None:
    # 14 s is the longest voice; only a long theme tail can push a slide past 15 s
    long_tail = replace(theme, audio=replace(theme.audio, tail=1.5))
    script = _narrated_script(tmp_script, [{"title": "A", "id": "a", "narration": "Rất dài."}])
    _, manifest = _manifest_for(script, tmp_path / "voice")
    issues = Issues()
    assert audio.plan_audio(script, long_tail, manifest, _lengths({"a": 14.0}), issues) is None
    assert any("limit is 15 s" in i.message for i in issues.errors)


def test_stale_narration_names_every_stale_slide(narrated: Any, theme: Any, tmp_path: Path) -> None:
    path, manifest = _manifest_for(narrated, tmp_path / "voice")
    edited = _narrated_script(
        _maker(tmp_path / "edit"),
        [
            {"title": "Mở đầu", "id": "s01", "narration": "Năm bốn mươi, đổi lời."},
            {"title": "Tiếp", "id": "s02", "narration": "Hai Bà Trưng khởi nghĩa."},
            {"title": "Không lời", "id": "s03"},
        ],
    )
    issues = Issues()
    assert (
        audio.plan_audio(edited, theme, manifest, _lengths({"s01": 2.0, "s02": 2.0}), issues)
        is None
    )
    stale = [i for i in issues.errors if "narration changed since recording" in i.message]
    assert stale and "s01" in stale[0].message and "s02" not in stale[0].message


def test_missing_segment_names_the_slide(narrated: Any, theme: Any, tmp_path: Path) -> None:
    folder = tmp_path / "voice"
    folder.mkdir()
    path = _write_audio_manifest(folder, segments=[])
    manifest = audio.load_manifest(path, Issues())
    assert manifest is not None
    issues = Issues()
    assert audio.plan_audio(narrated, theme, manifest, _lengths({}), issues) is None
    assert any("no audio segment for slide s01" in i.message for i in issues.errors)


def test_voice_length_outside_range_is_an_error(narrated: Any, theme: Any, tmp_path: Path) -> None:
    _, manifest = _manifest_for(narrated, tmp_path / "voice")
    issues = Issues()
    audio.plan_audio(narrated, theme, manifest, _lengths({"s01": 0.1, "s02": 2.0}), issues)
    assert any("outside 0.3–14 s" in i.message for i in issues.errors)


def test_missing_audio_file_is_an_error(narrated: Any, theme: Any, tmp_path: Path) -> None:
    _, manifest = _manifest_for(narrated, tmp_path / "voice")
    (tmp_path / "voice" / "s02.wav").unlink()
    issues = Issues()
    audio.plan_audio(narrated, theme, manifest, _lengths({"s01": 2.0, "s02": 2.0}), issues)
    assert any("audio file not found" in i.message for i in issues.errors)


def test_unknown_segment_and_unnarrated_slide_warn(
    narrated: Any, theme: Any, tmp_path: Path
) -> None:
    path, manifest = _manifest_for(narrated, tmp_path / "voice")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["segments"].append(_segment(file="zz.wav", sid="ghost", digest="1" * 64))
    path.write_text(json.dumps(data), encoding="utf-8")
    fresh = audio.load_manifest(path, Issues())
    assert fresh is not None
    issues = Issues()
    plan = audio.plan_audio(narrated, theme, fresh, _lengths({"s01": 2.0, "s02": 2.0}), issues)
    assert plan is not None and issues.errors == []
    assert any("ghost" in w.path for w in issues.warnings)


def test_voice_placement_starts_after_lead_in(narrated: Any, theme: Any, tmp_path: Path) -> None:
    _, manifest = _manifest_for(narrated, tmp_path / "voice")
    issues = Issues()
    plan = audio.plan_audio(narrated, theme, manifest, _lengths({"s01": 2.0, "s02": 3.0}), issues)
    assert plan is not None
    inputs = audio.voice_inputs(plan, list(plan.durations), theme.audio)
    lead = theme.audio.lead_in
    assert inputs[0].delay_ms == round(lead * 1000)
    assert inputs[1].delay_ms == round((plan.durations[0] + lead) * 1000)
    assert inputs[0].gain_db == theme.audio.voice_gain_db


def test_voice_gain_adds_theme_trim_and_segment_gain(
    tmp_path: Path, theme: Any, tmp_script: Make
) -> None:
    script = _narrated_script(tmp_script, [{"title": "A", "id": "a", "narration": "Thử."}])
    folder = tmp_path / "voice"
    folder.mkdir()
    wav = folder / "a.wav"
    wav.write_bytes(b"RIFF")
    path = _write_audio_manifest(
        folder,
        segments=[
            {
                **_segment(file="a.wav", sid="a"),
                "text_sha256": audio.narration.text_sha256("Thử."),
                "gain_db": -3,
            }
        ],
    )
    manifest = audio.load_manifest(path, Issues())
    assert manifest is not None
    plan = audio.plan_audio(script, theme, manifest, _lengths({"a": 2.0}), Issues())
    assert plan is not None
    spec = AudioSpec(voice_gain_db=1.5)
    (voice_input,) = audio.voice_inputs(plan, list(plan.durations), spec)
    assert voice_input.gain_db == pytest.approx(-1.5)


def test_narration_without_audio_warns(narrated: Any) -> None:
    issue = audio.narration_without_audio(narrated, "script.json")
    assert issue is not None and issue.severity == "warning"


def test_script_without_narration_gives_no_warning(script_one_slide: Any) -> None:
    assert audio.narration_without_audio(script_one_slide, "script.json") is None


def _maker(folder: Path) -> Make:
    """A second script factory for a test that edits the narration, like ``tmp_script``."""
    folder.mkdir(parents=True, exist_ok=True)

    def make(*, slides: list[dict[str, Any]], extra: dict[str, Any]) -> Path:
        data = {"title": "Edit", "sources": ["x"], "slides": slides, **extra}
        path = folder / "script.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    return make
