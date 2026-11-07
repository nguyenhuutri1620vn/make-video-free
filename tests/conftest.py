"""Shared pytest configuration."""

from __future__ import annotations

import itertools
import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_UNSET: Any = object()  # distinguishes "use the default" from an explicit ``None``


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def theme() -> Any:
    """The shipped ``son_mai`` theme, loaded once per session."""
    from history_shorts.config import load_theme

    loaded, _warnings = load_theme(REPO_ROOT / "themes" / "son_mai" / "theme.json")
    return loaded


@pytest.fixture
def tmp_theme(tmp_path: Path) -> Callable[..., Path]:
    """Factory: copy the default theme directory into ``tmp_path``, edit it, return theme.json.

    Keyword args: ``drop_palette`` (keys to delete), ``palette`` (keys to set),
    ``fonts`` (font entries to set), ``extra`` (top-level keys to add), ``bom`` (write a
    UTF-8 byte-order mark). Each call gets its own directory.
    """
    counter = itertools.count()

    def make(
        *,
        drop_palette: Sequence[str] = (),
        palette: Mapping[str, Any] | None = None,
        fonts: Mapping[str, Any] | None = None,
        extra: Mapping[str, Any] | None = None,
        bom: bool = False,
    ) -> Path:
        directory = tmp_path / f"theme_{next(counter)}"
        shutil.copytree(REPO_ROOT / "themes" / "son_mai", directory)
        target = directory / "theme.json"
        data = json.loads(target.read_text(encoding="utf-8"))
        for key in drop_palette:
            del data["palette"][key]
        data["palette"].update(palette or {})
        data["fonts"].update(fonts or {})
        data.update(extra or {})
        encoding = "utf-8-sig" if bom else "utf-8"
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding=encoding)
        return target

    return make


@pytest.fixture
def tmp_script(tmp_path: Path) -> Callable[..., Path]:
    """Factory: write a ``script.json`` into a fresh directory under ``tmp_path``.

    Keyword args: ``slides`` (default one slide ``{"title": "A"}``), ``sources`` (default
    one citation; ``None`` omits the key), ``title``, ``extra`` (top-level keys to add or
    override, e.g. ``schema_version``), ``bom`` (write a UTF-8 byte-order mark).
    """
    counter = itertools.count()

    def make(
        *,
        slides: Any = _UNSET,
        sources: Any = _UNSET,
        title: str = "Test script",
        extra: Mapping[str, Any] | None = None,
        bom: bool = False,
    ) -> Path:
        directory = tmp_path / f"script_{next(counter)}"
        directory.mkdir()
        data: dict[str, Any] = {"schema_version": "2.0", "title": title}
        if sources is _UNSET:
            data["sources"] = ["Nguồn thử nghiệm"]
        elif sources is not None:
            data["sources"] = sources
        data["slides"] = [{"title": "A"}] if slides is _UNSET else slides
        data.update(extra or {})
        target = directory / "script.json"
        encoding = "utf-8-sig" if bom else "utf-8"
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding=encoding)
        return target

    return make


@pytest.fixture
def make_slide() -> Callable[..., Any]:
    """Factory: ``make_slide(title, subtitle="", **fields)`` builds a ``Slide`` directly."""
    from history_shorts.config import Slide

    def make(title: str, subtitle: str = "", **fields: Any) -> Slide:
        values: dict[str, Any] = {
            "tag": "",
            "title": title,
            "subtitle": subtitle,
            "duration": None,
            "scene": None,
            "motion": "none",
            "claim": False,
            "source": None,
        }
        values.update(fields)
        return Slide(**values)

    return make
