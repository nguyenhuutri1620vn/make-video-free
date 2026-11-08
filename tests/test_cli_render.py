"""``render`` without ``--preview``: order of work, flags, exit codes, summary (FR-91, FR-92)."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from history_shorts import ffmpeg
from history_shorts.cli import main
from history_shorts.errors import FfmpegFailed, FfmpegMissing
from history_shorts.ffmpeg import FfmpegInfo

ScriptFactory = Callable[..., Path]
INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))
VERBOSE_FLAGS: list[bool] = []  # the ``verbose`` argument of each fake ffmpeg run
TWO = [{"title": "Mê Linh", "duration": 2.0}, {"title": "Hai Bà Trưng", "duration": 3.5}]


def run_cli(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(argv)
    return code, capsys.readouterr().out


@pytest.fixture
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "tmproot"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return root


@pytest.fixture
def fake_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Pretend FFmpeg is installed; every command just writes its output file."""
    calls: list[list[str]] = []
    VERBOSE_FLAGS.clear()

    def run(cmd: list[str], *, verbose: bool) -> None:
        calls.append(cmd)
        VERBOSE_FLAGS.append(verbose)
        Path(cmd[-1]).write_bytes(b"x")

    monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda: INFO)
    monkeypatch.setattr(ffmpeg, "run", run)
    return calls


def argv_for(script: Path, out: Path, *extra: str) -> list[str]:
    return ["render", "--script", str(script), "--out", str(out), *extra]


def test_full_render_summary_and_report(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = tmp_script(slides=TWO, sources=["Nguồn A", "Nguồn B"])
    out = tmp_path / "res" / "v.mp4"
    code, text = run_cli(argv_for(script, out), capsys)
    assert code == 0, text
    assert out.is_file()
    report = out.parent / "v.report.json"
    assert report.is_file()
    lines = text.splitlines()
    assert any(ln.startswith("Slides: 2") for ln in lines)
    assert any(ln.startswith("Duration: 5.5 s") for ln in lines)
    assert f"Video: {out}" in lines
    assert f"Report: {report}" in lines
    assert any(ln.startswith("Elapsed: ") and ln.endswith(" s") for ln in lines)
    assert lines[-3:] == ["Sources:", "[1] Nguồn A", "[2] Nguồn B"]
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["total_duration"] == 5.5
    assert [s["png"] for s in data["slides"]] == ["slides/01.png", "slides/02.png"]
    assert data["timings"].keys() == {
        "validate", "render_slides", "encode", "concat", "mux", "total",
    }  # fmt: skip
    mux = fake_ffmpeg[-1]
    assert mux[mux.index("-t") + 1] == "5.500"
    assert (out.parent / "slides" / "02.png").is_file()
    assert list(temp_root.iterdir()) == []


def test_music_options_reach_ffmpeg(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    music = tmp_path / "song.mp3"
    music.write_bytes(b"audio")
    script = tmp_script(slides=TWO)
    out = tmp_path / "v.mp4"
    code, text = run_cli(
        argv_for(script, out, "--music", str(music), "--music-volume", "0.25"), capsys
    )
    assert code == 0, text
    mux = fake_ffmpeg[-1]
    assert str(music) in mux
    assert "volume=0.25" in mux[mux.index("-filter_complex") + 1]
    data = json.loads((tmp_path / "v.report.json").read_text(encoding="utf-8"))
    assert len(data["music_sha256"]) == 64


def test_keep_temp_keeps_clips_and_list_file(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = tmp_script(slides=TWO)
    code, _ = run_cli(argv_for(script, tmp_path / "v.mp4", "--keep-temp"), capsys)
    assert code == 0
    kept = list(temp_root.glob("history-shorts-*"))
    assert len(kept) == 1 and (kept[0] / "list.txt").is_file()


def test_missing_music_is_validation_error_exit_3(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = tmp_script(slides=TWO)
    out = tmp_path / "v.mp4"
    code, text = run_cli(argv_for(script, out, "--music", str(tmp_path / "nope.mp3")), capsys)
    assert code == 3
    assert any(ln.startswith("ERROR ") and "nope.mp3" in ln for ln in text.splitlines())
    assert fake_ffmpeg == []
    assert not (tmp_path / "slides").exists()


@pytest.mark.parametrize("value", ["-0.1", "2.5", "loud", "nan"])
def test_music_volume_out_of_range_is_usage_error(
    tmp_path: Path, tmp_script: ScriptFactory, value: str
) -> None:
    script = tmp_script(slides=TWO)
    with pytest.raises(SystemExit) as exc:
        main(argv_for(script, tmp_path / "v.mp4", "--music-volume", value))
    assert exc.value.code == 2


@pytest.mark.parametrize("value", ["0", "2", "0.6"])
def test_music_volume_bounds_accepted(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
    value: str,
) -> None:
    music = tmp_path / "m.mp3"
    music.write_bytes(b"a")
    script = tmp_script(slides=[{"title": "A", "duration": 2.0}])
    code, _ = run_cli(
        argv_for(script, tmp_path / "v.mp4", "--music", str(music), "--music-volume", value),
        capsys,
    )
    assert code == 0


def test_ffmpeg_is_located_before_slides_are_rendered(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # AC-14 fail fast
    def missing() -> FfmpegInfo:
        raise FfmpegMissing("ffmpeg was not found on PATH. Install it: brew install ffmpeg")

    monkeypatch.setattr(ffmpeg, "find_ffmpeg", missing)
    script = tmp_script(slides=TWO)
    code, text = run_cli(argv_for(script, tmp_path / "res" / "v.mp4"), capsys)
    assert code == 4
    assert "Install it: brew install ffmpeg" in text
    assert not (tmp_path / "res").exists()


def test_without_ffmpeg_exit_4(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # AC-14
    monkeypatch.setenv("PATH", "")
    script = tmp_script(slides=TWO)
    code, text = run_cli(argv_for(script, tmp_path / "x.mp4"), capsys)
    assert code == 4
    assert "install" in text.lower()
    assert not (tmp_path / "x.mp4").exists()


def test_ffmpeg_failure_exit_5_prints_stderr_and_leaves_nothing(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    monkeypatch: pytest.MonkeyPatch,
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []

    def run(cmd: list[str], *, verbose: bool) -> None:
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"x")
        if len(calls) == 4:  # the mux, after the partial file exists
            raise FfmpegFailed(cmd, "first line\nencoder exploded")

    monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda: INFO)
    monkeypatch.setattr(ffmpeg, "run", run)
    script = tmp_script(slides=TWO)
    out = tmp_path / "v.mp4"
    code, text = run_cli(argv_for(script, out), capsys)
    assert code == 5
    assert "encoder exploded" in text
    assert not out.exists() and not (tmp_path / "v.mp4.partial.mp4").exists()
    assert not (tmp_path / "v.report.json").exists()
    assert list(temp_root.iterdir()) == []


def test_interrupt_exits_130_and_cleans_up(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    monkeypatch: pytest.MonkeyPatch,
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []

    def run(cmd: list[str], *, verbose: bool) -> None:
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"x")
        if len(calls) == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda: INFO)
    monkeypatch.setattr(ffmpeg, "run", run)
    script = tmp_script(slides=TWO)
    out = tmp_path / "v.mp4"
    code, _ = run_cli(argv_for(script, out), capsys)
    assert code == 130
    assert not out.exists()
    assert list(temp_root.iterdir()) == []


def test_jobs_zero_is_a_usage_error(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A", "duration": 2.0}])
    with pytest.raises(SystemExit) as caught:
        main(argv_for(script, tmp_path / "v.mp4", "--jobs", "0"))
    assert caught.value.code == 2
    assert "--jobs" in capsys.readouterr().err


def test_jobs_reaches_render_options(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from history_shorts import cli, video

    seen: list[int] = []
    real = video.assemble

    def spy(*args: object, **kwargs: object) -> Path:
        opts = args[4]
        assert isinstance(opts, video.RenderOptions)
        seen.append(opts.jobs)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(cli, "assemble", spy)
    script = tmp_script(slides=[{"title": "A", "duration": 2.0}])
    code, text = run_cli(argv_for(script, tmp_path / "v.mp4", "--jobs", "3"), capsys)
    assert code == 0
    assert "not implemented" not in text
    code, _ = run_cli(argv_for(script, tmp_path / "w.mp4"), capsys)
    assert seen == [3, video.default_jobs()]


def test_verbose_flag_reaches_every_ffmpeg_run(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = tmp_script(slides=[{"title": "A", "duration": 2.0}])
    assert run_cli(argv_for(script, tmp_path / "a.mp4", "--verbose"), capsys)[0] == 0
    assert VERBOSE_FLAGS == [True, True, True]
    VERBOSE_FLAGS.clear()
    assert run_cli(argv_for(script, tmp_path / "b.mp4"), capsys)[0] == 0
    assert VERBOSE_FLAGS == [False, False, False]


def test_out_is_a_directory_fails_before_any_work(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "dir.mp4"
    out.mkdir()
    code, text = run_cli(argv_for(tmp_script(slides=TWO), out), capsys)
    assert code == 1
    assert f"ERROR cannot write video to {out}: it is a directory" in text
    assert fake_ffmpeg == [] and not (tmp_path / "slides").exists()


def test_write_failure_is_a_clear_error_not_internal(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(
        "history_shorts.video.os", SimpleNamespace(replace=boom, cpu_count=os.cpu_count)
    )
    out = tmp_path / "v.mp4"
    code, text = run_cli(argv_for(tmp_script(slides=TWO), out), capsys)
    assert code == 1
    assert f"ERROR cannot write video to {out}: Permission denied" in text
    assert "internal" not in text
    assert list(temp_root.iterdir()) == []


def test_report_write_failure_is_a_clear_error(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "v.mp4"
    (tmp_path / "v.report.json").mkdir()  # a directory where the report file belongs
    code, text = run_cli(argv_for(tmp_script(slides=TWO), out), capsys)
    assert code == 1
    assert f"ERROR cannot write report to {tmp_path / 'v.report.json'}: " in text
    assert "internal" not in text


def test_zoom_in_motion_reaches_clip_cmd_without_warning(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = tmp_script(
        slides=[
            {"title": "A", "duration": 2.0, "motion": "zoom_in"},
            {"title": "B", "duration": 2.0},
        ]
    )
    code, text = run_cli(argv_for(script, tmp_path / "v.mp4"), capsys)
    assert code == 0
    assert ".motion" not in text
    clips = [c for c in fake_ffmpeg if "-loop" in c]
    zoomed = {Path(c[c.index("-i") + 1]).name: "zoompan" in c[c.index("-vf") + 1] for c in clips}
    assert zoomed == {"01.png": True, "02.png": False}


def test_preview_ignores_video_flags_with_a_warning(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}])
    argv = argv_for(script, tmp_path / "v.mp4", "--preview", "--music", str(tmp_path / "x.mp3"))
    code, text = run_cli([*argv, "--music-volume", "0.4", "--keep-temp"], capsys)
    assert code == 0
    for flag in ("--music", "--music-volume", "--keep-temp"):
        assert f"WARN {flag} has no effect with --preview" in text


def test_report_goes_next_to_output_for_unicode_paths(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    fake_ffmpeg: list[list[str]],
    temp_root: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "Sử Việt 'x'" / "nu tuong.mp4"
    script = tmp_script(slides=[{"title": "A", "duration": 2.0}])
    code, _ = run_cli(argv_for(script, out), capsys)
    assert code == 0
    assert (out.parent / "nu tuong.report.json").is_file()
