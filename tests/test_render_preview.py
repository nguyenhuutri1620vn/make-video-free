"""``render --preview``, slide PNG output and output-path helpers (FR-02, FR-90, AC-10, AC-12)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import numpy as np
import pytest
from PIL import Image

from history_shorts.cli import main
from history_shorts.compose import DrawContext, SceneStyle, default_style
from history_shorts.config import Script, Slide, Theme, load_script
from history_shorts.output import default_out_path, slides_dir, slugify, stale_slides
from history_shorts.primitives import FloatImage
from history_shorts.render import render_slides

ScriptFactory = Callable[..., Path]

TWO_SLIDES = [
    {"tag": "Mở đầu", "title": "Hai Bà Trưng", "subtitle": "Năm 40"},
    {"title": "Mê Linh"},
]


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(argv)
    return code, capsys.readouterr().out


def example(repo_root: Path, name: str) -> Path:
    return repo_root / "examples" / name / "script.json"


def pngs(directory: Path) -> list[str]:
    return sorted(p.name for p in directory.iterdir())


# --------------------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------------------


def test_slugify() -> None:
    assert slugify("Nữ tướng thời Hai Bà Trưng") == "nu-tuong-thoi-hai-ba-trung"
    assert slugify("Đền Nghè, Hải Phòng!") == "den-nghe-hai-phong"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("đỉnh ĐÈO", "dinh-deo"),
        ("  --A__b..C--  ", "a-b-c"),
        ("Năm 40", "nam-40"),
        ("???", "video"),
        ("", "video"),
        ("ｆｕｌｌ", "video"),  # fullwidth latin has no ASCII form once marks are removed
    ],
)
def test_slugify_edges(title: str, expected: str) -> None:
    assert slugify(title) == expected


def test_slugify_caps_length_at_a_word_boundary() -> None:
    title = " ".join(["trưng"] * 40)  # slug "trung-trung-..." is 239 characters
    slug = slugify(title)
    assert len(slug) <= 80
    assert slug == "-".join(["trung"] * 13)  # 77 characters, cut between words
    assert not slug.endswith("-")


def test_slugify_cap_edge_cases() -> None:
    assert slugify("a" * 200) == "a" * 80  # no hyphen to cut at
    exact = "-".join(["abcd"] * 16)  # 79 characters
    assert slugify(exact) == exact
    boundary = "a" * 79 + " b"  # the 80th character of the slug is "-"
    assert slugify(boundary) == "a" * 79


def test_default_out_path_and_slides_dir(repo_root: Path) -> None:
    script, _ = load_script(example(repo_root, "nu_tuong"))
    assert default_out_path(script) == Path("output") / "nu-tuong-thoi-hai-ba-trung.mp4"
    assert slides_dir(Path("a/b/v.mp4")) == Path("a/b/slides")
    assert slides_dir(Path("v.mp4")) == Path("slides")


# --------------------------------------------------------------------------------------
# render_slides
# --------------------------------------------------------------------------------------


def load(path: Path) -> Script:
    script, _ = load_script(path)
    return script


def test_render_slides_writes_numbered_pngs(
    tmp_path: Path, tmp_script: ScriptFactory, theme: Theme
) -> None:
    script = load(tmp_script(slides=TWO_SLIDES))
    written = render_slides(script, theme, tmp_path / "out" / "v.mp4", debug_safe_zone=False)
    assert written == [
        tmp_path / "out" / "slides" / "01.png",
        tmp_path / "out" / "slides" / "02.png",
    ]
    for path in written:
        with Image.open(path) as image:
            assert image.size == (1080, 1920)
            assert image.mode == "RGB"
    assert pngs(tmp_path / "out" / "slides") == ["01.png", "02.png"]  # no .tmp left behind


def test_two_renders_byte_identical(
    tmp_path: Path, tmp_script: ScriptFactory, theme: Theme
) -> None:  # AC-12 (partial: chrome + text)
    script = load(tmp_script(slides=TWO_SLIDES))
    a = render_slides(script, theme, tmp_path / "a" / "v.mp4", debug_safe_zone=False)
    b = render_slides(script, theme, tmp_path / "b" / "v.mp4", debug_safe_zone=False)
    assert len(a) == len(b) == 2
    assert all(x.read_bytes() == y.read_bytes() for x, y in zip(a, b, strict=True))
    assert a[0].read_bytes() != a[1].read_bytes()


def test_debug_safe_zone_changes_output(
    tmp_path: Path, tmp_script: ScriptFactory, theme: Theme
) -> None:
    script = load(tmp_script(slides=[{"title": "A"}]))
    plain = render_slides(script, theme, tmp_path / "a" / "v.mp4", debug_safe_zone=False)
    debug = render_slides(script, theme, tmp_path / "b" / "v.mp4", debug_safe_zone=True)
    assert plain[0].read_bytes() != debug[0].read_bytes()


def test_stale_pngs_are_left_alone(tmp_path: Path, tmp_script: ScriptFactory, theme: Theme) -> None:
    script = load(tmp_script(slides=TWO_SLIDES))
    directory = tmp_path / "slides"
    directory.mkdir()
    (directory / "03.png").write_bytes(b"old")
    (directory / "07.png").write_bytes(b"old")
    (directory / "notes.txt").write_bytes(b"keep")
    render_slides(script, theme, tmp_path / "v.mp4", debug_safe_zone=False)
    assert (directory / "03.png").read_bytes() == b"old"
    assert (directory / "07.png").read_bytes() == b"old"
    assert (directory / "notes.txt").read_bytes() == b"keep"
    assert [p.name for p in stale_slides(directory, 2)] == ["03.png", "07.png"]


def _one_slide_with_old_png(
    tmp_path: Path, tmp_script: ScriptFactory, theme: Theme
) -> tuple[Script, Path]:
    script = load(tmp_script(slides=[{"title": "A"}]))
    directory = tmp_path / "slides"
    directory.mkdir()
    (directory / "01.png").write_bytes(b"old")
    return script, directory


def test_failed_save_leaves_old_png_and_removes_partial_tmp(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    theme: Theme,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script, directory = _one_slide_with_old_png(tmp_path, tmp_script, theme)
    partial: list[Path] = []

    def broken_save(self: Image.Image, fp: Any, *args: Any, **kwargs: Any) -> NoReturn:
        Path(fp).write_bytes(b"partial")  # a half-written file, as a full disk would leave
        partial.append(Path(fp))
        raise OSError("disk full")

    monkeypatch.setattr(Image.Image, "save", broken_save)
    with pytest.raises(OSError, match="disk full"):
        render_slides(script, theme, tmp_path / "v.mp4", debug_safe_zone=False)
    assert [p.name for p in partial] == ["01.png.tmp"]  # the partial file really existed
    assert pngs(directory) == ["01.png"]
    assert (directory / "01.png").read_bytes() == b"old"


def test_failed_replace_leaves_old_png_and_removes_tmp(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    theme: Theme,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script, directory = _one_slide_with_old_png(tmp_path, tmp_script, theme)
    seen_tmp: list[bool] = []

    def broken_replace(src: Any, dst: Any) -> NoReturn:
        seen_tmp.append(Path(src).is_file())  # the save succeeded before the rename failed
        raise OSError("rename failed")

    monkeypatch.setattr("history_shorts.render.os.replace", broken_replace)
    with pytest.raises(OSError, match="rename failed"):
        render_slides(script, theme, tmp_path / "v.mp4", debug_safe_zone=False)
    assert seen_tmp == [True]
    assert pngs(directory) == ["01.png"]
    assert (directory / "01.png").read_bytes() == b"old"


def test_expand_hook_supplies_style_and_scene(
    tmp_path: Path, tmp_script: ScriptFactory, theme: Theme
) -> None:
    script = load(tmp_script(slides=TWO_SLIDES))
    seen: list[Slide] = []

    def paint(base: FloatImage, ctx: DrawContext) -> FloatImage:
        out = base.copy()
        out[300:400, 100:200] = (1.0, 0.0, 0.0)
        return out

    def expand(slide: Slide, th: Theme) -> tuple[SceneStyle, Any]:
        seen.append(slide)
        return default_style(th), (paint if slide.title == "Mê Linh" else None)

    written = render_slides(script, theme, tmp_path / "v.mp4", debug_safe_zone=False, expand=expand)
    assert [s.title for s in seen] == ["Hai Bà Trưng", "Mê Linh"]
    with Image.open(written[0]) as first, Image.open(written[1]) as second:
        assert np.asarray(first)[350, 150, 0] < 100
        assert np.asarray(second)[350, 150, 0] > 150  # sheen/grain barely move a solid fill


# --------------------------------------------------------------------------------------
# CLI: render --preview
# --------------------------------------------------------------------------------------


def forbid(*args: Any, **kwargs: Any) -> NoReturn:
    raise AssertionError("render --preview must not spawn a process")


def test_preview_writes_pngs_and_never_spawns_ffmpeg(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # AC-10, FR-02
    monkeypatch.setattr(subprocess, "run", forbid)
    monkeypatch.setattr(subprocess, "Popen", forbid)
    out = tmp_path / "v.mp4"
    argv = [
        "render",
        "--script",
        str(example(repo_root, "me_linh")),
        "--preview",
        "--out",
        str(out),
    ]
    code, text = run(argv, capsys)
    assert code == 0, text
    assert pngs(tmp_path / "slides") == [f"{i:02d}.png" for i in range(1, 7)]
    assert not out.exists()


def test_preview_summary(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=TWO_SLIDES, sources=["Nguồn một", "Nguồn hai"])
    out = tmp_path / "v.mp4"
    code, text = run(["render", "--script", str(script), "--preview", "--out", str(out)], capsys)
    assert code == 0, text
    lines = text.splitlines()
    assert any("2 slides" in ln and str(tmp_path / "slides") in ln for ln in lines)
    assert any(ln.rstrip().endswith("s") and "in " in ln for ln in lines)
    assert "Sources:" in lines
    assert "[1] Nguồn một" in lines
    assert "[2] Nguồn hai" in lines
    assert lines.index("Sources:") < lines.index("[1] Nguồn một")


def test_preview_without_sources_omits_block(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}], sources=None)
    argv = ["render", "--script", str(script), "--preview", "--out", str(tmp_path / "v.mp4")]
    code, text = run(argv, capsys)
    assert code == 0
    assert "Sources:" not in text
    assert "WARN" in text  # the missing-sources warning from validation


def test_render_validates_first_and_writes_nothing(
    tmp_path: Path, repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = repo_root / "tests" / "data" / "three_errors.json"
    out = tmp_path / "out" / "v.mp4"
    code, text = run(["render", "--script", str(bad), "--preview", "--out", str(out)], capsys)
    assert code == 3
    assert text.count("ERROR ") == 3
    assert not (tmp_path / "out").exists()


def test_render_missing_script_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["render", "--script", str(tmp_path / "nope.json"), "--preview"]
    code, text = run(argv, capsys)
    assert code == 3
    assert "ERROR" in text


def test_default_out_is_output_slug_under_cwd(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # spec §7
    monkeypatch.chdir(tmp_path)
    script = tmp_script(slides=[{"title": "A"}], title="Đền Nghè, Hải Phòng!")
    code, _ = run(["render", "--script", str(script), "--preview"], capsys)
    assert code == 0
    assert (tmp_path / "output" / "slides" / "01.png").is_file()


def test_stale_pngs_reported_as_warn(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}])
    directory = tmp_path / "slides"
    directory.mkdir()
    (directory / "02.png").write_bytes(b"old")
    (directory / "05.png").write_bytes(b"old")
    argv = ["render", "--script", str(script), "--preview", "--out", str(tmp_path / "v.mp4")]
    code, text = run(argv, capsys)
    assert code == 0
    warn = [ln for ln in text.splitlines() if ln.startswith("WARN ") and "stale" in ln]
    assert len(warn) == 1
    assert "02.png" in warn[0]
    assert "05.png" in warn[0]
    assert (directory / "02.png").read_bytes() == b"old"


def test_without_preview_renders_pngs_then_fails_loudly(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}])
    out = tmp_path / "v.mp4"
    code, text = run(["render", "--script", str(script), "--out", str(out)], capsys)
    assert code == 1
    assert "ERROR video assembly is not implemented yet (milestone M5)" in text
    assert (tmp_path / "slides" / "01.png").is_file()
    assert not out.exists()


def test_unimplemented_flags_warn_and_are_ignored(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}])
    argv = [
        "render",
        "--script",
        str(script),
        "--preview",
        "--out",
        str(tmp_path / "v.mp4"),
        "--music",
        str(tmp_path / "song.mp3"),
        "--music-volume",
        "0.4",
        "--keep-temp",
        "--jobs",
        "2",
        "--verbose",
    ]
    code, text = run(argv, capsys)
    assert code == 0
    warns = [ln for ln in text.splitlines() if ln.startswith("WARN ") and "not implemented" in ln]
    joined = " ".join(warns)
    for flag in ("--music", "--music-volume", "--keep-temp", "--jobs"):
        assert flag in joined


def test_debug_safe_zone_flag(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}])
    plain, debug = tmp_path / "a" / "v.mp4", tmp_path / "b" / "v.mp4"
    base = ["render", "--script", str(script), "--preview"]
    assert run([*base, "--out", str(plain)], capsys)[0] == 0
    assert run([*base, "--out", str(debug), "--debug-safe-zone"], capsys)[0] == 0
    assert (plain.parent / "slides" / "01.png").read_bytes() != (
        debug.parent / "slides" / "01.png"
    ).read_bytes()


def test_unicode_and_apostrophe_paths(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:  # NFR-04
    target = tmp_path / "Sử Việt 'test'" / "đầu ra" / "v.mp4"
    script = tmp_script(slides=TWO_SLIDES)
    code, text = run(["render", "--script", str(script), "--preview", "--out", str(target)], capsys)
    assert code == 0, text
    assert pngs(target.parent / "slides") == ["01.png", "02.png"]


def test_cli_render_matches_api_bytes(
    tmp_path: Path,
    tmp_script: ScriptFactory,
    theme: Theme,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script_path = tmp_script(slides=TWO_SLIDES)
    api = render_slides(load(script_path), theme, tmp_path / "a" / "v.mp4", debug_safe_zone=False)
    code, _ = run(
        [
            "render",
            "--script",
            str(script_path),
            "--preview",
            "--out",
            str(tmp_path / "b" / "v.mp4"),
        ],
        capsys,
    )
    assert code == 0
    for path in api:
        other = tmp_path / "b" / "slides" / path.name
        assert other.read_bytes() == path.read_bytes()


def test_zero_valued_ignored_flags_still_warn(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}])
    argv = ["render", "--script", str(script), "--preview", "--out", str(tmp_path / "v.mp4")]
    code, text = run([*argv, "--jobs", "0", "--music-volume", "0"], capsys)
    assert code == 0
    assert "WARN --music-volume is not implemented yet" in text
    assert "WARN --jobs is not implemented yet" in text
    code, text = run(argv, capsys)  # nothing given, nothing to warn about
    assert "not implemented" not in text


def test_out_parent_is_a_file_reports_write_error(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    script = tmp_script(slides=[{"title": "A"}])
    argv = ["render", "--script", str(script), "--preview", "--out", str(blocker / "v.mp4")]
    code, text = run(argv, capsys)
    assert code == 1
    line = next(ln for ln in text.splitlines() if ln.startswith("ERROR "))
    assert line.startswith(f"ERROR cannot write slides to {blocker / 'slides'}: ")
    assert "internal" not in text
    assert blocker.read_text(encoding="utf-8") == "not a directory"


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions")
def test_unwritable_out_dir_reports_write_error(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        script = tmp_script(slides=[{"title": "A"}])
        argv = ["render", "--script", str(script), "--preview", "--out", str(locked / "v.mp4")]
        code, text = run(argv, capsys)
    finally:
        locked.chmod(0o700)
    assert code == 1
    assert f"ERROR cannot write slides to {locked / 'slides'}: " in text
    assert "Permission denied" in text
