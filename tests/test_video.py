"""``video.assemble``: command sequence, atomic output and cleanup (FR-80..82, FR-90, NFR-05)."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts import ffmpeg
from history_shorts.config import Theme
from history_shorts.errors import FfmpegFailed
from history_shorts.ffmpeg import FfmpegInfo
from history_shorts.video import RenderOptions, assemble, default_jobs

INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))
RunLog = list[list[str]]


@pytest.fixture
def temp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``tempfile`` at a fresh directory so leftovers are visible and isolated."""
    root = tmp_path / "tmproot"
    root.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(root))
    return root


def leftovers(root: Path) -> list[Path]:
    return sorted(root.glob("history-shorts-*"))


def fake_run(
    calls: RunLog, *, fail_on: int | None = None, error: Callable[[list[str]], BaseException]
) -> Callable[..., None]:
    """A ``ffmpeg.run`` stand-in: records the command, writes its output file (the last
    argument) and raises ``error(cmd)`` on the ``fail_on``-th call (1-based)."""

    def run(cmd: list[str], *, verbose: bool) -> None:
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"x")
        if fail_on == len(calls):
            raise error(cmd)

    return run


def options(out: Path, **fields: Any) -> RenderOptions:
    return RenderOptions(out=out, music=None, **fields)


def pngs(tmp_path: Path, n: int = 2) -> list[Path]:
    return [tmp_path / f"{i + 1:02d}.png" for i in range(n)]


def test_render_options_defaults_and_frozen(tmp_path: Path) -> None:
    opts = RenderOptions(out=tmp_path / "o.mp4", music=None)
    assert (opts.music_volume, opts.keep_temp, opts.jobs, opts.verbose) == (0.6, False, 1, False)
    with pytest.raises(AttributeError):
        opts.jobs = 2  # type: ignore[misc]


def test_command_sequence_and_result(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: RunLog = []
    monkeypatch.setattr(ffmpeg, "run", fake_run(calls, error=lambda c: AssertionError()))
    out = tmp_path / "Sử Việt 'x'" / "o.mp4"  # parent does not exist yet
    timings: dict[str, float] = {}
    result = assemble(INFO, pngs(tmp_path), [3.0, 4.5], theme, options(out), timings)
    assert result == out
    assert out.read_bytes() == b"x"
    assert not out.with_name("o.mp4.partial.mp4").exists()
    assert len(calls) == 4  # two clips, concat, mux
    clip1, clip2, concat, mux = calls
    fade_in, fade_out = theme.transition.fade_in, theme.transition.fade_out
    expected = ffmpeg.clip_cmd(
        INFO, tmp_path / "01.png", Path(clip1[-1]), 3.0, theme.video.fps, theme.video.crf,
        fade_in, fade_out,
    )  # fmt: skip
    assert clip1 == expected
    assert Path(clip1[-1]).name == "clip_01.mp4"
    assert Path(clip2[-1]).name == "clip_02.mp4"
    assert clip2[clip2.index("-t") + 1] == "4.500"
    assert concat[concat.index("-f") + 1] == "concat"
    assert concat[-1].endswith("video.mp4")
    assert mux[-1] == str(out.with_name("o.mp4.partial.mp4"))
    assert mux[mux.index("-t") + 1] == "7.500"
    assert "anullsrc" in " ".join(mux)
    assert set(timings) == {"encode", "concat", "mux"}
    assert leftovers(temp_root) == []


def test_list_file_content(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, str] = {}

    def run(cmd: list[str], *, verbose: bool) -> None:
        Path(cmd[-1]).write_bytes(b"x")
        if "concat" in cmd:
            seen["list"] = Path(cmd[cmd.index("-i") + 1]).read_text(encoding="utf-8")

    monkeypatch.setattr(ffmpeg, "run", run)
    assemble(INFO, pngs(tmp_path), [2.0, 2.0], theme, options(tmp_path / "o.mp4"))
    lines = seen["list"].splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("file '") and lines[0].endswith("clip_01.mp4'")
    assert lines[1].endswith("clip_02.mp4'")


def test_music_and_volume_reach_the_mux(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: RunLog = []
    monkeypatch.setattr(ffmpeg, "run", fake_run(calls, error=lambda c: AssertionError()))
    music = tmp_path / "m.mp3"
    opts = RenderOptions(out=tmp_path / "o.mp4", music=music, music_volume=0.3)
    assemble(INFO, pngs(tmp_path, 1), [3.0], theme, opts)
    mux = calls[-1]
    assert str(music) in mux
    assert "volume=0.30" in mux[mux.index("-filter_complex") + 1]


def test_mismatched_lengths_rejected(tmp_path: Path, theme: Theme, temp_root: Path) -> None:
    with pytest.raises(ValueError, match="durations"):
        assemble(INFO, pngs(tmp_path, 2), [3.0], theme, options(tmp_path / "o.mp4"))
    assert leftovers(temp_root) == []


def test_keep_temp_keeps_the_directory_and_its_files(
    tmp_path: Path,
    theme: Theme,
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: RunLog = []
    monkeypatch.setattr(ffmpeg, "run", fake_run(calls, error=lambda c: AssertionError()))
    with caplog.at_level(logging.INFO, logger="history_shorts.video"):
        assemble(
            INFO, pngs(tmp_path), [2.0, 2.0], theme, options(tmp_path / "o.mp4", keep_temp=True)
        )
    kept = leftovers(temp_root)
    assert len(kept) == 1
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.INFO] == [
        f"kept temporary files in {kept[0]}"
    ]
    assert sorted(p.name for p in kept[0].iterdir()) == [
        "clip_01.mp4", "clip_02.mp4", "list.txt", "video.mp4",
    ]  # fmt: skip


def test_verbose_is_passed_to_run(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    flags: list[bool] = []

    def run(cmd: list[str], *, verbose: bool) -> None:
        flags.append(verbose)
        Path(cmd[-1]).write_bytes(b"x")

    monkeypatch.setattr(ffmpeg, "run", run)
    assemble(INFO, pngs(tmp_path, 1), [2.0], theme, options(tmp_path / "o.mp4", verbose=True))
    assert flags == [True, True, True]


# ------------------------------------------------------------------ failure and cleanup


@pytest.mark.parametrize("call", [1, 2, 3, 4])
@pytest.mark.parametrize("keep_temp", [False, True])
def test_interrupt_cleans_temp_and_partial(
    tmp_path: Path,
    theme: Theme,
    temp_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    call: int,
    keep_temp: bool,
) -> None:  # Review Focus 5, NFR-05
    calls: RunLog = []
    monkeypatch.setattr(
        ffmpeg, "run", fake_run(calls, fail_on=call, error=lambda c: KeyboardInterrupt())
    )
    out = tmp_path / "o.mp4"
    with pytest.raises(KeyboardInterrupt):
        assemble(INFO, pngs(tmp_path), [3.0, 3.0], theme, options(out, keep_temp=keep_temp))
    assert len(calls) == call
    assert not out.exists()
    assert not out.with_name("o.mp4.partial.mp4").exists()
    assert len(leftovers(temp_root)) == (1 if keep_temp else 0)


def test_ffmpeg_failure_midway_leaves_no_partial_and_keeps_old_output(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: RunLog = []
    monkeypatch.setattr(
        ffmpeg, "run", fake_run(calls, fail_on=4, error=lambda c: FfmpegFailed(c, "boom"))
    )
    out = tmp_path / "o.mp4"
    out.write_bytes(b"previous good video")
    with pytest.raises(FfmpegFailed):
        assemble(INFO, pngs(tmp_path), [3.0, 3.0], theme, options(out))
    assert out.read_bytes() == b"previous good video"  # NFR-05: never replaced by a partial
    assert not out.with_name("o.mp4.partial.mp4").exists()
    assert leftovers(temp_root) == []


def test_existing_output_is_replaced_on_success(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: RunLog = []
    monkeypatch.setattr(ffmpeg, "run", fake_run(calls, error=lambda c: AssertionError()))
    out = tmp_path / "o.mp4"
    out.write_bytes(b"old")
    assemble(INFO, pngs(tmp_path, 1), [2.0], theme, options(out))
    assert out.read_bytes() == b"x"


def test_only_expected_files_are_touched(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: RunLog = []
    monkeypatch.setattr(ffmpeg, "run", fake_run(calls, error=lambda c: AssertionError()))
    out_dir = tmp_path / "res"
    out_dir.mkdir()
    bystander = out_dir / "notes.txt"
    bystander.write_text("keep", encoding="utf-8")
    assemble(INFO, pngs(tmp_path, 1), [2.0], theme, options(out_dir / "o.mp4"))
    assert sorted(p.name for p in out_dir.iterdir()) == ["notes.txt", "o.mp4"]
    assert bystander.read_text(encoding="utf-8") == "keep"


def test_default_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    for cpus, expected in ((8, 7), (None, 1), (1, 1), (2, 1)):
        monkeypatch.setattr(os, "cpu_count", lambda cpus=cpus: cpus)  # type: ignore[misc]
        assert default_jobs() == expected


def clip_number(cmd: list[str]) -> int | None:
    name = Path(cmd[-1]).name
    return int(name[5:7]) if name.startswith("clip_") else None


def test_parallel_preserves_order(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, str] = {}
    finished: list[int] = []

    def run(cmd: list[str], *, verbose: bool) -> None:
        number = clip_number(cmd)
        if number is not None:
            time.sleep(0.05 * (5 - number))  # earlier slides finish last
        Path(cmd[-1]).write_bytes(b"x")
        if number is not None:
            finished.append(number)
        if "concat" in cmd:
            seen["list"] = Path(cmd[cmd.index("-i") + 1]).read_text(encoding="utf-8")

    monkeypatch.setattr(ffmpeg, "run", run)
    assemble(INFO, pngs(tmp_path, 4), [2.0] * 4, theme, options(tmp_path / "o.mp4", jobs=4))
    assert finished != sorted(finished)  # the clips really did finish out of order
    names = [Path(line.split("'")[1]).name for line in seen["list"].splitlines()]
    assert names == [f"clip_{i:02d}.mp4" for i in range(1, 5)]


def test_jobs_1_is_serial(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    threads: list[int] = []

    def run(cmd: list[str], *, verbose: bool) -> None:
        threads.append(threading.get_ident())
        Path(cmd[-1]).write_bytes(b"x")

    monkeypatch.setattr(ffmpeg, "run", run)
    assemble(INFO, pngs(tmp_path, 3), [2.0] * 3, theme, options(tmp_path / "o.mp4", jobs=1))
    assert len(threads) == 5  # three clips, concat, mux
    assert set(threads) == {threading.get_ident()}


def test_failure_cancels_pending_and_cleans_up(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[int] = []
    active: list[int] = []
    lock = threading.Lock()

    def run(cmd: list[str], *, verbose: bool) -> None:
        number = clip_number(cmd)
        assert number is not None, "concat must not start after a failure"
        with lock:
            started.append(number)
            active.append(number)
        try:
            time.sleep(0.3 if number != 1 else 0.05)
            if number == 1:
                raise FfmpegFailed(cmd, "boom")
            Path(cmd[-1]).write_bytes(b"x")
        finally:
            with lock:
                active.remove(number)

    monkeypatch.setattr(ffmpeg, "run", run)
    out = tmp_path / "o.mp4"
    with pytest.raises(FfmpegFailed):
        assemble(INFO, pngs(tmp_path, 5), [2.0] * 5, theme, options(out, jobs=2))
    assert active == []  # nothing still running when assemble returned
    assert len(started) < 5  # pending clips were cancelled
    assert not out.exists()
    assert not out.with_name("o.mp4.partial.mp4").exists()
    assert leftovers(temp_root) == []


def test_first_failure_in_slide_order_is_raised(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run(cmd: list[str], *, verbose: bool) -> None:
        number = clip_number(cmd)
        time.sleep(0.05 * (3 - (number or 0)))  # slide 3 fails first in time
        raise FfmpegFailed(cmd, f"clip {number}")

    monkeypatch.setattr(ffmpeg, "run", run)
    with pytest.raises(FfmpegFailed) as caught:
        assemble(INFO, pngs(tmp_path, 3), [2.0] * 3, theme, options(tmp_path / "o.mp4", jobs=3))
    assert caught.value.stderr_tail == "clip 1"


def test_parallel_caps_threads_per_clip(
    tmp_path: Path, theme: Theme, temp_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    seen: list[list[str]] = []

    def run(cmd: list[str], *, verbose: bool) -> None:
        if clip_number(cmd) is not None:
            seen.append(cmd)
        Path(cmd[-1]).write_bytes(b"x")

    monkeypatch.setattr(ffmpeg, "run", run)
    assemble(INFO, pngs(tmp_path, 2), [2.0] * 2, theme, options(tmp_path / "o.mp4", jobs=4))
    assert all(c[c.index("-threads") + 1] == "2" for c in seen) and len(seen) == 2
    seen.clear()
    assemble(INFO, pngs(tmp_path, 2), [2.0] * 2, theme, options(tmp_path / "o.mp4", jobs=1))
    assert all("-threads" not in c for c in seen) and len(seen) == 2
