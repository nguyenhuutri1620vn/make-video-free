"""Building audio_manifest.json from recorded voice files (spec A.1.8)."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from history_shorts import audio, voice_manifest
from history_shorts.cli import main
from history_shorts.config import load_script
from history_shorts.errors import Issues

Make = Callable[..., Path]


@pytest.fixture
def exported(tmp_script: Make, tmp_path: Path) -> Path:
    """A narration folder exported from a two-voice script."""
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[
            {"title": "Mở đầu", "id": "s01", "narration": "Năm bốn mươi."},
            {"title": "Tiếp", "id": "s02", "narration": "Hai Bà Trưng khởi nghĩa."},
            {"title": "Không lời", "id": "s03"},
        ],
    )
    script, _ = load_script(path)
    out = tmp_path / "narration"
    audio.export_narration(script, out)
    return out


def _age(path: Path, seconds: float) -> None:
    """Move ``path``'s mtime ``seconds`` into the past."""
    stat = path.stat()
    os.utime(path, (stat.st_atime - seconds, stat.st_mtime - seconds))


def _voice(folder: Path, name: str) -> Path:
    path = folder / name
    path.write_bytes(b"RIFF fake")
    return path


def _build(narration: Path, voices: Path | None = None) -> tuple[Path | None, Issues]:
    issues = Issues()
    return voice_manifest.build(narration, voices or narration, issues), issues


def test_builds_manifest_with_hashes_copied_from_narration(exported: Path) -> None:
    for name in ("s01.wav", "s02.flac"):
        _voice(exported, name)
    path, issues = _build(exported)
    assert issues.errors == []
    assert path == exported / "audio_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    narration = json.loads((exported / "manifest.json").read_text(encoding="utf-8"))
    assert data["kind"] == "history-shorts.audio"
    assert data["schema_version"] == "1.0"
    assert [s["file"] for s in data["segments"]] == ["s01.wav", "s02.flac"]
    assert [s["text_sha256"] for s in data["segments"]] == [
        s["text_sha256"] for s in narration["segments"]
    ]


def test_result_loads_as_a_valid_audio_manifest(exported: Path) -> None:
    for name in ("s01.wav", "s02.wav"):
        _voice(exported, name)
    path, _ = _build(exported)
    assert path is not None
    issues = Issues()
    manifest = audio.load_manifest(path, issues)
    assert issues.errors == []
    assert manifest is not None and set(manifest.segments) == {"s01", "s02"}


def test_separate_voices_folder_uses_paths_relative_to_it(exported: Path, tmp_path: Path) -> None:
    voices = tmp_path / "voices"
    voices.mkdir()
    for name in ("s01.wav", "s02.wav"):
        _voice(voices, name)
    path, issues = _build(exported, voices)
    assert issues.errors == []
    assert path == voices / "audio_manifest.json"
    assert not (exported / "audio_manifest.json").exists()


def test_missing_voices_are_named_and_nothing_is_written(exported: Path) -> None:
    path, issues = _build(exported)
    assert path is None
    assert any("s01, s02" in i.message for i in issues.errors)
    assert not (exported / "audio_manifest.json").exists()


def test_voice_older_than_its_text_is_stale(exported: Path) -> None:
    old = _voice(exported, "s01.wav")
    _voice(exported, "s02.wav")
    _age(old, 3600)
    path, issues = _build(exported)
    assert path is None
    assert any("re-record: s01" in i.message for i in issues.errors)


def test_text_edited_after_export_is_an_error(exported: Path) -> None:
    for name in ("s01.wav", "s02.wav"):
        _voice(exported, name)
    (exported / "s02.txt").write_text("Khác.\n", encoding="utf-8")
    path, issues = _build(exported)
    assert path is None
    assert any("s02" in i.message and "export" in i.message for i in issues.errors)


def test_wav_and_flac_for_one_id_is_ambiguous(exported: Path) -> None:
    for name in ("s01.wav", "s01.flac", "s02.wav"):
        _voice(exported, name)
    path, issues = _build(exported)
    assert path is None
    assert any("s01" in i.message and "both" in i.message for i in issues.errors)


def test_gain_is_kept_for_unchanged_segments(exported: Path) -> None:
    for name in ("s01.wav", "s02.wav"):
        _voice(exported, name)
    path, _ = _build(exported)
    assert path is not None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["segments"][1]["gain_db"] = -3.0
    path.write_text(json.dumps(data), encoding="utf-8")
    _build(exported)
    rebuilt = json.loads(path.read_text(encoding="utf-8"))
    assert "gain_db" not in rebuilt["segments"][0]
    assert rebuilt["segments"][1]["gain_db"] == -3.0


def test_wrong_narration_kind_is_rejected(tmp_path: Path) -> None:
    folder = tmp_path / "n"
    folder.mkdir()
    (folder / "manifest.json").write_text(
        json.dumps({"kind": "other", "schema_version": "1.0", "segments": []}), encoding="utf-8"
    )
    path, issues = _build(folder)
    assert path is None
    assert any(i.path == "kind" for i in issues.errors)


def test_export_keeps_mtime_of_unchanged_files(exported: Path, tmp_script: Make) -> None:
    txt = exported / "s01.txt"
    _age(txt, 3600)
    before = txt.stat().st_mtime
    script, _ = load_script(
        tmp_script(
            extra={"schema_version": "2.1"},
            slides=[
                {"title": "Mở đầu", "id": "s01", "narration": "Năm bốn mươi."},
                {"title": "Tiếp", "id": "s02", "narration": "Đã sửa."},
            ],
        )
    )
    audio.export_narration(script, exported)
    assert txt.stat().st_mtime == before
    assert (exported / "s02.txt").read_text(encoding="utf-8") == "Đã sửa.\n"


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def test_cli_writes_manifest(exported: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ("s01.wav", "s02.wav"):
        _voice(exported, name)
    code = main(["audio-manifest", "--narration", str(exported)])
    out = capsys.readouterr().out
    assert code == 0
    assert "2 voices" in out and "audio_manifest.json" in out


def test_cli_missing_voices_exit_3(exported: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["audio-manifest", "--narration", str(exported)])
    out = capsys.readouterr().out
    assert code == 3
    assert out.startswith("ERROR")
