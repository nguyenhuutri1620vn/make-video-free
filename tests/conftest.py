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


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


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
