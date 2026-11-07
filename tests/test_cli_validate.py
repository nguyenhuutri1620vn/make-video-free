"""``validate`` command, cross-file checks and the runtime import check (AC-08, AC-11)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from history_shorts import checks
from history_shorts.cli import main
from history_shorts.config import Script, Theme, load_script

ScriptFactory = Callable[..., Path]
ThemeFactory = Callable[..., Path]


def raise_for(*names: str) -> Callable[[str], ModuleType]:
    """An ``_import_module`` stand-in that fails for the given top-level modules."""
    import importlib

    def fake(name: str) -> ModuleType:
        if name in names:
            raise ImportError(f"No module named {name!r}")
        return importlib.import_module(name)

    return fake


def run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(argv)
    return code, capsys.readouterr().out


def example(repo_root: Path, name: str) -> str:
    return str(repo_root / "examples" / name / "script.json")


# --------------------------------------------------------------------------------------
# validate: end to end
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["me_linh", "nu_tuong"])
def test_validate_examples_exit_0(
    name: str, repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(["validate", "--script", example(repo_root, name)], capsys)
    assert code == 0
    assert "0 errors" in out
    assert "ERROR" not in out


def test_validate_examples_report_shrink_warnings(
    repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = run(["validate", "--script", example(repo_root, "nu_tuong")], capsys)
    assert code == 0
    assert any(
        line.startswith("WARN ") and "text auto-shrunk to" in line and " px" in line
        for line in out.splitlines()
    )


def test_validate_three_errors_exit_3(
    repo_root: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # AC-11
    script = repo_root / "tests" / "data" / "three_errors.json"
    code, out = run(["validate", "--script", str(script)], capsys)
    assert code == 3
    assert out.count("three_errors.json ›") == 3
    assert out.rstrip().splitlines()[-1].startswith("3 errors")
    assert out.count("ERROR ") == 3


def test_validate_missing_sources_only_warns(
    tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:  # AC-11
    script = tmp_script(sources=None, slides=[{"title": "A", "claim": True}])
    code, out = run(["validate", "--script", str(script)], capsys)
    assert code == 0
    assert "WARN script.json › sources: missing" in out
    assert "0 errors" in out


def test_errors_are_printed_before_warnings_then_summary(
    tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    script = tmp_script(sources=None, slides=[{"title": "A", "duration": 99}])
    code, out = run(["validate", "--script", str(script)], capsys)
    assert code == 3
    lines = out.rstrip().splitlines()
    assert lines[0].startswith("ERROR ")
    assert lines[1].startswith("WARN ")
    assert lines[-1] == "1 errors, 1 warnings"


def test_missing_font_exit_3_names_path(
    repo_root: Path, tmp_theme: ThemeFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    theme = tmp_theme(fonts={"title": "fonts/X.ttf"})
    argv = ["validate", "--script", example(repo_root, "me_linh"), "--theme", str(theme)]
    code, out = run(argv, capsys)
    assert code == 3
    assert "fonts/X.ttf" in out
    assert "theme.json › fonts.title" in out


def test_theme_and_script_errors_are_all_reported(
    tmp_theme: ThemeFactory, tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    theme = tmp_theme(fonts={"title": "fonts/X.ttf"})
    script = tmp_script(slides=[{"tag": "A"}])
    code, out = run(["validate", "--script", str(script), "--theme", str(theme)], capsys)
    assert code == 3
    assert "theme.json › fonts.title" in out
    assert "script.json › slides[0].title: required" in out
    assert "2 errors" in out


def test_missing_script_file_exit_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(["validate", "--script", str(tmp_path / "nope.json")], capsys)
    assert code == 3
    assert "nope.json" in out
    assert "file not found" in out


def test_default_theme_does_not_depend_on_cwd(
    repo_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    code, out = run(["validate", "--script", example(repo_root, "me_linh")], capsys)
    assert code == 0, out


def test_validate_requires_script_argument() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["validate"])
    assert exc.value.code == 2


def test_cross_file_checks_run_through_cli(
    tmp_script: ScriptFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    long_word = "W" * 40
    script = tmp_script(slides=[{"title": long_word, "subtitle": "ok"}])
    code, out = run(["validate", "--script", str(script)], capsys)
    assert code == 3
    assert "ERROR script.json › slides[0].title: does not fit at" in out


# --------------------------------------------------------------------------------------
# checks.check_all
# --------------------------------------------------------------------------------------


def load(tmp_script: ScriptFactory, theme: Theme, **kw: Any) -> tuple[Script, Theme]:
    script, _ = load_script(tmp_script(**kw))
    return script, theme


def messages(script: Script, theme: Theme) -> list[tuple[str, str, str, str]]:
    return [(i.file, i.path, i.message, i.severity) for i in checks.check_all(script, theme)]


def test_check_all_clean_for_short_text(tmp_script: ScriptFactory, theme: Theme) -> None:
    script, _ = load(tmp_script, theme, slides=[{"title": "Ngắn", "subtitle": "Gọn"}])
    assert checks.check_all(script, theme) == []


def test_text_does_not_fit_is_error_with_min_size_and_suggestion(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    script, _ = load(tmp_script, theme, slides=[{"title": "A"}, {"title": "W" * 40}])
    (file, path, message, severity), *rest = messages(script, theme)
    assert not rest
    assert (file, path, severity) == ("script.json", "slides[1].title", "error")
    assert message.startswith(f"does not fit at {theme.type_scale.title_min} px; ")
    assert "shorten the title to about" in message


def test_subtitle_does_not_fit_is_error(tmp_script: ScriptFactory, theme: Theme) -> None:
    script, _ = load(tmp_script, theme, slides=[{"title": "A", "subtitle": "W" * 60}])
    ((_, path, message, severity),) = messages(script, theme)
    assert (path, severity) == ("slides[0].subtitle", "error")
    assert message.startswith(f"does not fit at {theme.type_scale.subtitle_min} px; ")


def test_shrunk_title_warns_with_size(tmp_script: ScriptFactory, theme: Theme) -> None:
    # Longest unbreakable run that fits at the minimum size but not at the full size.
    word = "W" * 11
    script, _ = load(tmp_script, theme, slides=[{"title": word}])
    result = messages(script, theme)
    assert len(result) == 1
    _, path, message, severity = result[0]
    assert (path, severity) == ("slides[0].title", "warning")
    assert message.startswith("text auto-shrunk to ")
    assert message.endswith(" px")


def test_missing_theme_font_glyphs_are_listed(
    tmp_script: ScriptFactory, theme: Theme, monkeypatch: pytest.MonkeyPatch
) -> None:  # AC-08
    def fake(font_path: Path, chars: str = checks.VIETNAMESE_CHARSET) -> list[str]:
        return ["ơ", "ư"] if font_path == theme.fonts.title and chars else []

    monkeypatch.setattr(checks, "missing_glyphs", fake)
    script, _ = load(tmp_script, theme)
    assert messages(script, theme) == [
        ("theme.json", "fonts.title", "missing glyphs: ơ, ư", "error")
    ]


def test_each_distinct_font_is_checked_once(
    tmp_script: ScriptFactory, theme: Theme, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []

    def fake(font_path: Path, chars: str = checks.VIETNAMESE_CHARSET) -> list[str]:
        if chars == checks.VIETNAMESE_CHARSET:
            seen.append(font_path)
        return []

    monkeypatch.setattr(checks, "missing_glyphs", fake)
    script, _ = load(tmp_script, theme)
    checks.check_all(script, theme)
    assert len(seen) == len(set(seen))
    assert set(seen) == {theme.fonts.title, theme.fonts.subtitle, theme.fonts.tag}


def test_used_character_missing_from_font_is_reported_on_its_slide(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    script, _ = load(
        tmp_script, theme, slides=[{"title": "ok"}, {"tag": "漢", "title": "ok", "subtitle": "字"}]
    )
    result = messages(script, theme)
    assert ("script.json", "slides[1].tag", "missing glyphs: 漢", "error") in result
    assert ("script.json", "slides[1].subtitle", "missing glyphs: 字", "error") in result
    assert all(path.startswith("slides[1]") for _, path, _, _ in result)


def palette_script(tmp_script: ScriptFactory, theme: Theme, scene: dict[str, Any]) -> Script:
    return load(tmp_script, theme, slides=[{"title": "A"}, {"title": "B", "scene": scene}])[0]


def test_unknown_palette_key_in_characters_layer_items(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    scene = {
        "layers": [
            {"type": "ground", "y": 1100},
            {
                "type": "characters",
                "items": [{"role": "general"}, {"role": "leader", "robe": "teal"}],
            },
        ]
    }
    script = palette_script(tmp_script, theme, scene)
    assert messages(script, theme) == [
        (
            "script.json",
            "slides[1].scene.layers[1].items[1].robe",
            "unknown palette key 'teal'",
            "error",
        )
    ]


def test_unknown_palette_key_in_boat_layer_crew(tmp_script: ScriptFactory, theme: Theme) -> None:
    scene = {
        "layers": [
            {
                "type": "boat",
                "x": 500,
                "y": 1200,
                "crew": [{"role": "boat_crew", "trim": "nope"}, {"role": "boat_crew", "wrap": "x"}],
            }
        ]
    }
    script = palette_script(tmp_script, theme, scene)
    assert [(p, m) for _, p, m, _ in messages(script, theme)] == [
        ("slides[1].scene.layers[0].crew[0].trim", "unknown palette key 'nope'"),
        ("slides[1].scene.layers[0].crew[1].wrap", "unknown palette key 'x'"),
    ]


def test_unknown_palette_key_in_template_characters_and_boats(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    group = {"template": "group", "characters": [{"role": "leader", "robe_dk": "zzz"}]}
    landscape = {
        "template": "landscape",
        "boats": [
            {"x": 300, "y": 1200, "crew": [{"role": "boat_crew"}]},
            {"x": 600, "y": 1200, "crew": [{"role": "boat_crew", "robe": "qqq"}]},
        ],
    }
    script, _ = load(
        tmp_script,
        theme,
        slides=[{"title": "A", "scene": group}, {"title": "B", "scene": landscape}],
    )
    assert [(p, m) for _, p, m, _ in messages(script, theme)] == [
        ("slides[0].scene.characters[0].robe_dk", "unknown palette key 'zzz'"),
        ("slides[1].scene.boats[1].crew[0].robe", "unknown palette key 'qqq'"),
    ]


def test_known_palette_keys_including_optional_ones_pass(
    tmp_script: ScriptFactory, theme: Theme
) -> None:
    scene = {
        "template": "group",
        "characters": [
            {"role": "leader", "robe": "vermilion", "robe_dk": "robe_general_dk", "trim": "gold"}
        ],
    }
    script, _ = load(tmp_script, theme, slides=[{"title": "A", "scene": scene}])
    assert checks.check_all(script, theme) == []


# --------------------------------------------------------------------------------------
# Runtime import check and error mapping
# --------------------------------------------------------------------------------------


def test_missing_pycairo_exit_1_with_hint(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("history_shorts.cli._import_module", raise_for("cairo"))
    monkeypatch.setattr("history_shorts.cli.sys.platform", "darwin")
    code, out = run(["validate", "--script", example(repo_root, "me_linh")], capsys)
    assert code == 1
    assert out.startswith("ERROR ")
    assert "cairo" in out
    assert "brew install cairo pkg-config && pip install pycairo" in out


@pytest.mark.parametrize(
    ("platform", "hint"),
    [
        ("linux", "sudo apt install libcairo2-dev && pip install pycairo"),
        ("win32", "pip install pycairo"),
    ],
)
def test_pycairo_hint_per_os(
    platform: str,
    hint: str,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("history_shorts.cli._import_module", raise_for("cairo"))
    monkeypatch.setattr("history_shorts.cli.sys.platform", platform)
    code, out = run(["validate", "--script", example(repo_root, "me_linh")], capsys)
    assert code == 1
    assert hint in out
    assert "brew" not in out or platform == "darwin"


@pytest.mark.parametrize("module", ["numpy", "scipy", "PIL"])
def test_missing_other_runtime_module_hint(
    module: str,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("history_shorts.cli._import_module", raise_for(module))
    code, out = run(["validate", "--script", example(repo_root, "me_linh")], capsys)
    assert code == 1
    assert module in out
    assert 'pip install -e ".[dev]"' in out


@pytest.mark.parametrize("command", ["render", "gallery"])
def test_other_commands_also_check_runtime(
    command: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("history_shorts.cli._import_module", raise_for("scipy"))
    code, out = run([command], capsys)
    assert code == 1
    assert "scipy" in out


def test_unexpected_exception_is_internal_error_exit_1(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def boom(script: Script, theme: Theme) -> list[Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr(checks, "check_all", boom)
    code, out = run(["validate", "--script", example(repo_root, "me_linh")], capsys)
    assert code == 1
    assert "ERROR internal: RuntimeError: boom" in out


def test_keyboard_interrupt_exit_130(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupt(script: Script, theme: Theme) -> list[Any]:
        raise KeyboardInterrupt

    monkeypatch.setattr(checks, "check_all", interrupt)
    code, _ = run(["validate", "--script", example(repo_root, "me_linh")], capsys)
    assert code == 130


def test_three_errors_file_is_valid_json(repo_root: Path) -> None:
    json.loads((repo_root / "tests" / "data" / "three_errors.json").read_text(encoding="utf-8"))
