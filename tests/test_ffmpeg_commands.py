"""FFmpeg discovery, command builders and the safe runner (FR-80..82, 85, 86, NFR-09)."""

from __future__ import annotations

import logging
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import requires_ffmpeg

from history_shorts.errors import FfmpegFailed, FfmpegMissing, FfmpegTooOld
from history_shorts.ffmpeg import (
    MIN_VERSION,
    FfmpegInfo,
    clip_cmd,
    concat_cmd,
    concat_list_text,
    find_ffmpeg,
    mux_cmd,
    parse_version,
    probe,
    run,
)

INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))


@pytest.mark.parametrize(
    "banner,version",
    [
        ("ffmpeg version 8.1 Copyright", (8, 1)),
        ("ffmpeg version n4.4.2-0ubuntu", (4, 4)),
        ("ffmpeg version 6.0.1-static", (6, 0)),
        ("ffmpeg version N-112233-gabc", None),
        ("garbage", None),
    ],
)
def test_parse_version(banner: str, version: tuple[int, int] | None) -> None:
    assert parse_version(banner) == version


def test_min_version_constant() -> None:
    assert MIN_VERSION == (4, 4)


def test_clip_cmd_exact() -> None:
    cmd = clip_cmd(INFO, Path("/t/01.png"), Path("/t/clip_01.mp4"), 4.0, 30, 20, 0.3, 0.3)
    assert cmd == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "30",
        "-t", "4.000", "-i", "/t/01.png", "-vf",
        "fade=t=in:st=0:d=0.300,fade=t=out:st=3.700:d=0.300,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-an", "/t/clip_01.mp4",
    ]  # fmt: skip


def test_clip_cmd_threads_exact() -> None:
    args = (INFO, Path("/t/01.png"), Path("/t/clip_01.mp4"), 4.0, 30, 20, 0.3, 0.3)
    cmd = clip_cmd(*args, threads=2)
    base = clip_cmd(*args)
    at = base.index("libx264") + 1
    assert cmd == [*base[:at], "-threads", "2", *base[at:]]
    assert clip_cmd(*args, threads=None) == base


def test_clip_cmd_fades_scaled_down_when_longer_than_clip() -> None:
    cmd = clip_cmd(INFO, Path("a.png"), Path("a.mp4"), 0.4, 30, 20, 0.3, 0.3)
    vf = cmd[cmd.index("-vf") + 1]
    assert vf == "fade=t=in:st=0:d=0.200,fade=t=out:st=0.200:d=0.200,format=yuv420p"


def test_clip_cmd_fade_out_start_never_negative() -> None:
    cmd = clip_cmd(INFO, Path("a.png"), Path("a.mp4"), 1.0, 30, 20, 0.0, 5.0)
    vf = cmd[cmd.index("-vf") + 1]
    assert "fade=t=out:st=0.000:d=1.000" in vf


def test_clip_cmd_zero_fades_are_omitted_safely() -> None:
    cmd = clip_cmd(INFO, Path("a.png"), Path("a.mp4"), 2.0, 30, 20, 0.0, 0.0)
    vf = cmd[cmd.index("-vf") + 1]
    assert vf == "format=yuv420p"


def test_zoom_in_filter_exact() -> None:
    cmd = clip_cmd(
        INFO, Path("/t/01.png"), Path("/t/clip_01.mp4"), 4.0, 30, 20, 0.3, 0.3, motion="zoom_in"
    )
    assert cmd == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "30",
        "-t", "4.000", "-i", "/t/01.png", "-vf",
        "scale=2160:3840,"
        "zoompan=z='min(1+0.06*on/120,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d=1:s=1080x1920:fps=30,"
        "fade=t=in:st=0:d=0.300,fade=t=out:st=3.700:d=0.300,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-an", "/t/clip_01.mp4",
    ]  # fmt: skip


def test_zoom_in_keeps_threads_and_other_args() -> None:
    args = (INFO, Path("a.png"), Path("a.mp4"), 4.0, 30, 20, 0.3, 0.3)
    zoom = clip_cmd(*args, motion="zoom_in", threads=2)
    plain = clip_cmd(*args, threads=2)
    at = zoom.index("-vf")
    assert zoom[:at] == plain[:at]
    assert zoom[at + 2 :] == plain[at + 2 :]
    assert "-threads" in zoom


def test_motion_none_is_unchanged() -> None:
    args = (INFO, Path("a.png"), Path("a.mp4"), 2.0, 30, 20, 0.3, 0.3)
    assert clip_cmd(*args, motion="none") == clip_cmd(*args)
    assert "zoompan" not in " ".join(clip_cmd(*args))


def test_unknown_motion_rejected() -> None:
    with pytest.raises(ValueError, match="motion"):
        clip_cmd(INFO, Path("a.png"), Path("a.mp4"), 2.0, 30, 20, 0.3, 0.3, motion="pan")


def test_concat_list_escapes_quotes_and_uses_posix_paths() -> None:
    text = concat_list_text([Path("/tmp/Sử Việt/bà 'Trưng'/clip_01.mp4")])
    assert text == "file '/tmp/Sử Việt/bà '\\''Trưng'\\''/clip_01.mp4'\n"


def test_concat_list_one_line_per_clip() -> None:
    text = concat_list_text([Path("/t/a.mp4"), Path("/t/b.mp4")])
    assert text == "file '/t/a.mp4'\nfile '/t/b.mp4'\n"


def test_concat_cmd_exact() -> None:
    assert concat_cmd(INFO, Path("/t/list.txt"), Path("/t/v.mp4")) == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", "/t/list.txt", "-c", "copy", "/t/v.mp4",
    ]  # fmt: skip


def test_mux_with_music_exact() -> None:
    cmd = mux_cmd(INFO, Path("/t/v.mp4"), Path("/t/o.mp4"), 12.0, Path("/m/a.mp3"), 0.6)
    graph = (
        "[1:a]atrim=0:12.000,asetpts=N/SR/TB,volume=0.60,afade=t=in:st=0:d=0.5,"
        "afade=t=out:st=10.500:d=1.5,aresample=48000,aformat=channel_layouts=stereo[a]"
    )
    assert cmd == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "/t/v.mp4",
        "-stream_loop", "-1", "-i", "/m/a.mp3", "-filter_complex", graph,
        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-t", "12.000", "-movflags", "+faststart", "/t/o.mp4",
    ]  # fmt: skip


def test_mux_music_fades_scaled_down_for_short_videos() -> None:
    cmd = mux_cmd(INFO, Path("v.mp4"), Path("o.mp4"), 1.0, Path("a.mp3"), 0.6)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "afade=t=in:st=0:d=0.25" in graph
    assert "afade=t=out:st=0.250:d=0.75" in graph  # fades never overlap or go negative


def test_mux_music_fades_unchanged_from_two_seconds() -> None:
    cmd = mux_cmd(INFO, Path("v.mp4"), Path("o.mp4"), 2.0, Path("a.mp3"), 0.6)
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "afade=t=in:st=0:d=0.5" in graph
    assert "afade=t=out:st=0.500:d=1.5" in graph


def test_mux_silent_uses_anullsrc() -> None:
    cmd = mux_cmd(INFO, Path("/t/v.mp4"), Path("/t/o.mp4"), 12.0, None, 0.6)
    assert cmd == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "/t/v.mp4",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", "12.000", "-movflags", "+faststart", "/t/o.mp4",
    ]  # fmt: skip


def test_paths_are_plain_strings_without_quoting() -> None:
    cmd = clip_cmd(INFO, Path("/a b/ü 'x'.png"), Path("/a b/o.mp4"), 2.0, 30, 20, 0.3, 0.3)
    assert "/a b/ü 'x'.png" in cmd
    assert all(isinstance(part, str) for part in cmd)


# ---------------------------------------------------------------- discovery


def _runner(stdout: str, code: int = 0) -> Any:
    def fake(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert isinstance(cmd, list)
        assert kwargs.get("shell") is not True
        return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr="")

    return fake


def _which(found: dict[str, str]) -> Any:
    return lambda name: found.get(name)


BOTH = {"ffmpeg": "/usr/bin/ffmpeg", "ffprobe": "/usr/bin/ffprobe"}


def test_missing_ffmpeg_raises_with_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(FfmpegMissing) as exc:
        find_ffmpeg()
    assert exc.value.exit_code == 4
    assert "ffmpeg" in str(exc.value)


@pytest.mark.parametrize(
    "platform,hint",
    [
        ("darwin", "brew install ffmpeg"),
        ("linux", "sudo apt install ffmpeg"),
        ("win32", "winget install Gyan.FFmpeg"),
    ],
)
def test_missing_hint_per_platform(platform: str, hint: str) -> None:
    with pytest.raises(FfmpegMissing, match=hint):
        find_ffmpeg(which=_which({}), platform=platform)


def test_missing_ffprobe_alone_raises() -> None:
    with pytest.raises(FfmpegMissing, match="ffprobe"):
        find_ffmpeg(which=_which({"ffmpeg": "/usr/bin/ffmpeg"}), platform="linux")


def test_find_ffmpeg_success() -> None:
    info = find_ffmpeg(
        which=_which(BOTH), platform="linux", runner=_runner("ffmpeg version 6.1.1 Copyright\n")
    )
    assert info == FfmpegInfo(Path("/usr/bin/ffmpeg"), Path("/usr/bin/ffprobe"), (6, 1))


def test_too_old_raises_with_hint() -> None:
    with pytest.raises(FfmpegTooOld, match="brew install ffmpeg") as exc:
        find_ffmpeg(
            which=_which(BOTH), platform="darwin", runner=_runner("ffmpeg version 4.3.1 x\n")
        )
    assert exc.value.exit_code == 4


def test_minimum_version_accepted() -> None:
    info = find_ffmpeg(which=_which(BOTH), platform="linux", runner=_runner("ffmpeg version 4.4\n"))
    assert info.version == (4, 4)


def test_dev_build_accepted_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="history_shorts.ffmpeg"):
        info = find_ffmpeg(
            which=_which(BOTH), platform="linux", runner=_runner("ffmpeg version N-112233-gabc\n")
        )
    assert info.version is None
    assert any("version" in r.message.lower() for r in caplog.records)


def test_unrunnable_ffmpeg_is_missing() -> None:
    with pytest.raises(FfmpegMissing):
        find_ffmpeg(which=_which(BOTH), platform="linux", runner=_runner("", code=1))


# ---------------------------------------------------------------- run


def test_run_failure_keeps_last_20_stderr_lines() -> None:
    cmd = [
        sys.executable,
        "-c",
        "import sys; [print(i, file=sys.stderr) for i in range(30)]; sys.exit(1)",
    ]
    with pytest.raises(FfmpegFailed) as exc:
        run(cmd, verbose=False)
    assert exc.value.exit_code == 5
    assert exc.value.command == cmd
    assert exc.value.stderr_tail.splitlines() == [str(i) for i in range(10, 30)]


def test_run_success_returns_none() -> None:
    assert run([sys.executable, "-c", "pass"], verbose=False) is None


def test_run_verbose_logs_full_command(caplog: pytest.LogCaptureFixture) -> None:
    cmd = [sys.executable, "-c", "print('a b')"]
    with caplog.at_level(logging.DEBUG, logger="history_shorts.ffmpeg"):
        run(cmd, verbose=True)
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]
    assert messages == [f"running: {shlex.join(cmd)}"]


def test_run_not_verbose_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="history_shorts.ffmpeg"):
        run([sys.executable, "-c", "pass"], verbose=False)
    assert [r for r in caplog.records if r.levelno == logging.DEBUG] == []


def test_run_oserror_becomes_ffmpeg_failed(tmp_path: Path) -> None:
    not_executable = tmp_path / "ffmpeg"
    not_executable.write_text("#!/bin/sh\n", encoding="utf-8")  # no exec bit
    with pytest.raises(FfmpegFailed) as exc:
        run([str(not_executable), "-version"], verbose=False)
    assert exc.value.exit_code == 5
    assert exc.value.command == [str(not_executable), "-version"]
    assert exc.value.stderr_tail


def test_probe_oserror_becomes_ffmpeg_failed(tmp_path: Path) -> None:
    info = FfmpegInfo(tmp_path / "nope", tmp_path / "nope-probe", (8, 1))
    with pytest.raises(FfmpegFailed):
        probe(info, tmp_path / "v.mp4")


def test_find_ffmpeg_oserror_is_missing() -> None:
    def broken(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise PermissionError(13, "Permission denied")

    with pytest.raises(FfmpegMissing, match="brew install ffmpeg") as exc:
        find_ffmpeg(which=_which(BOTH), platform="darwin", runner=broken)
    assert exc.value.exit_code == 4


@pytest.mark.parametrize("payload", ["[]", "null", '{"streams": null}', '{"streams": [1]}'])
def test_probe_unexpected_json_is_ffmpeg_failed(
    monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    def fake(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr="")

    monkeypatch.setattr("history_shorts.ffmpeg._run_text", fake)
    with pytest.raises(FfmpegFailed, match="unexpected ffprobe output"):
        probe(INFO, Path("v.mp4"))


def test_run_propagates_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(KeyboardInterrupt):
        run(["ffmpeg"], verbose=False)


# ---------------------------------------------------------------- smoke


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_clip_smoke_and_probe(tmp_path: Path) -> None:
    from PIL import Image

    png = tmp_path / "s.png"
    Image.new("RGB", (1080, 1920), (120, 30, 30)).save(png)
    info = find_ffmpeg()
    out = tmp_path / "clip.mp4"
    run(clip_cmd(info, png, out, 2 / 30, 30, 20, 0.0, 0.0), verbose=False)
    result = probe(info, out)
    assert (result.width, result.height) == (1080, 1920)
    assert result.codec == "h264"
    assert result.pix_fmt == "yuv420p"
    assert result.fps == "30/1"
    assert result.audio_codec is None
    assert result.duration > 0


def _grid_png(path: Path) -> None:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1080, 1920), (240, 240, 240))
    draw = ImageDraw.Draw(img)
    for offset in range(-400, 401, 100):  # vertical lines around the centre column
        draw.line([(540 + offset, 0), (540 + offset, 1919)], fill=(0, 0, 0), width=6)
    draw.rectangle([520, 940, 560, 980], fill=(200, 30, 30))  # centre marker
    img.save(path)


def _frame(info: FfmpegInfo, video: Path, seek: float, out: Path) -> Any:
    from PIL import Image

    cmd = [str(info.ffmpeg), "-hide_banner", "-loglevel", "error", "-y"]
    cmd += ["-ss", f"{seek:.3f}", "-i", str(video), "-frames:v", "1", str(out)]
    run(cmd, verbose=False)
    return Image.open(out).convert("RGB")


def _line_distance(img: Any) -> int:
    """Distance from the centre column to the outermost grid line on the right, on row 200."""
    row = [img.getpixel((x, 200))[0] for x in range(1080)]
    return max(x for x in range(540, 1080) if row[x] < 100) - 540


@pytest.mark.ffmpeg
@requires_ffmpeg
def test_zoom_in_clip_probe_and_magnification(tmp_path: Path) -> None:
    png = tmp_path / "grid.png"
    _grid_png(png)
    info = find_ffmpeg()
    out = tmp_path / "zoom.mp4"
    run(clip_cmd(info, png, out, 2.0, 30, 20, 0.0, 0.0, motion="zoom_in"), verbose=False)
    result = probe(info, out)
    assert (result.width, result.height) == (1080, 1920)
    assert (result.codec, result.pix_fmt, result.fps) == ("h264", "yuv420p", "30/1")
    assert result.duration == pytest.approx(2.0, abs=0.05)
    count = subprocess.run(
        [str(info.ffprobe), "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(out)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    assert abs(int(count.stdout.strip()) - 60) <= 1

    first = _frame(info, out, 0.0, tmp_path / "first.png")
    last = _frame(info, out, 1.9, tmp_path / "last.png")
    # outermost line at +400 px in the source grows with the zoom
    ratio = _line_distance(last) / _line_distance(first)
    assert ratio == pytest.approx(1.06, abs=0.015)
    for img in (first, last):  # the centre stays put
        r, g, b = img.getpixel((540, 960))
        assert (r, g, b) == pytest.approx((200, 30, 30), abs=25)
