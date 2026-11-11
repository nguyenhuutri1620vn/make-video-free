"""The theme's hook slide: a title slide put first in every video (theme ``hook`` block)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from history_shorts.cli import main
from history_shorts.config import HOOK_SLIDE_ID, load_script, load_theme, with_hook
from history_shorts.errors import ValidationFailed

HOOK_TITLE = "Chuyện Lịch sử Việt Nam không phải ai cũng biết"
TempTheme = Callable[..., Path]
ScriptFactory = Callable[..., Path]


def test_shipped_theme_has_the_hook_title(repo_root: Path) -> None:
    theme, _ = load_theme(repo_root / "themes" / "son_mai" / "theme.json")
    assert theme.hook is not None
    assert theme.hook.title == HOOK_TITLE


def test_theme_without_hook_block_has_no_hook(tmp_theme: TempTheme) -> None:
    path = tmp_theme()
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["hook"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    theme, _ = load_theme(path)
    assert theme.hook is None


def test_hook_block_without_title_is_an_error(tmp_theme: TempTheme) -> None:
    path = tmp_theme(extra={"hook": {}})
    with pytest.raises(ValidationFailed) as excinfo:
        load_theme(path)
    assert any("hook.title" in i.path for i in excinfo.value.issues.errors)


def test_with_hook_prepends_a_plain_title_slide(
    tmp_theme: TempTheme, tmp_script: ScriptFactory
) -> None:
    theme, _ = load_theme(tmp_theme())
    script, _ = load_script(tmp_script(slides=[{"title": "A", "duration": 2.0}, {"title": "B"}]))
    hooked = with_hook(script, theme)
    hook = hooked.slides[0]
    assert hook.id == HOOK_SLIDE_ID
    assert hook.title == HOOK_TITLE
    assert (hook.tag, hook.subtitle, hook.scene, hook.claim, hook.source) == (
        "",
        "",
        None,
        False,
        (),
    )
    assert hook.narration is None
    assert [s.id for s in hooked.slides[1:]] == [s.id for s in script.slides]
    assert hooked.slides[1].duration == 2.0


def test_with_hook_is_a_no_op_without_hook(tmp_theme: TempTheme, tmp_script: ScriptFactory) -> None:
    theme, _ = load_theme(tmp_theme())
    script, _ = load_script(tmp_script())
    assert with_hook(script, replace(theme, hook=None)) is script


def test_validate_reports_slide_paths_as_the_author_wrote_them(
    tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "W" * 40}])
    assert main(["validate", "--script", str(script)]) == 3
    out = capsys.readouterr().out
    assert "slides[0].title: does not fit" in out


def test_render_preview_puts_the_hook_first(
    tmp_path: Path, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(slides=[{"title": "A"}, {"title": "B"}])
    out = tmp_path / "v.mp4"
    assert main(["render", "--script", str(script), "--preview", "--out", str(out)]) == 0
    slides = sorted(p.name for p in (tmp_path / "slides").iterdir())
    assert slides == ["01.png", "02.png", "03.png"]


def test_render_without_hook_block_adds_no_slide(
    tmp_path: Path,
    tmp_theme: TempTheme,
    tmp_script: ScriptFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    theme_path = tmp_theme()
    data = json.loads(theme_path.read_text(encoding="utf-8"))
    del data["hook"]
    theme_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    script = tmp_script(slides=[{"title": "A"}, {"title": "B"}])
    out = tmp_path / "v.mp4"
    code = main(
        [
            "render",
            "--script",
            str(script),
            "--preview",
            "--out",
            str(out),
            "--theme",
            str(theme_path),
        ]
    )
    assert code == 0
    assert sorted(p.name for p in (tmp_path / "slides").iterdir()) == ["01.png", "02.png"]
