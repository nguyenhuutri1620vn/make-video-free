"""Shared pytest configuration."""

from __future__ import annotations

import itertools
import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from helpers.snapshots import SnapshotDb

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINES = REPO_ROOT / "tests" / "snapshots" / "baselines.json"

_UNSET: Any = object()  # distinguishes "use the default" from an explicit ``None``


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="write the snapshot baselines for the installed library versions (intentional "
        "visual changes only)",
    )


requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are not on PATH",
)
"""Reusable marker: skip when FFmpeg is unavailable (pair with ``@pytest.mark.ffmpeg``)."""


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def snapshot_db(request: pytest.FixtureRequest) -> SnapshotDb:
    return SnapshotDb(BASELINES, bool(request.config.getoption("--update-snapshots")))


@pytest.fixture(scope="session")
def first_slide_png(theme: Any, tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    """Factory: render slide 01 of ``examples/<name>`` with its scene; cached per session."""
    from dataclasses import replace

    from history_shorts.config import load_script
    from history_shorts.render import render_slides, scene_expander

    cache: dict[str, Path] = {}

    def render(example: str) -> Path:
        if example not in cache:
            script, _warnings = load_script(REPO_ROOT / "examples" / example / "script.json")
            first = replace(script, slides=script.slides[:1])
            out = tmp_path_factory.mktemp(f"first_{example}") / "v.mp4"
            cache[example] = render_slides(
                first, theme, out, debug_safe_zone=False, expand=scene_expander
            )[0]
        return cache[example]

    return render


@pytest.fixture(scope="session")
def theme() -> Any:
    """The shipped ``son_mai`` theme, loaded once per session."""
    from history_shorts.config import load_theme

    loaded, _warnings = load_theme(REPO_ROOT / "themes" / "son_mai" / "theme.json")
    return loaded


@pytest.fixture(scope="session")
def palette(theme: Any) -> Any:
    """The default theme's palette."""
    return theme.palette


@pytest.fixture(scope="session")
def cloud_mask() -> Any:
    """A 1080x1920 float mask holding a cloud-like blob (overlapping ellipses)."""
    from history_shorts.canvas import Canvas

    cv = Canvas(1080, 1920)
    cv.color((255, 255, 255))
    for cx, cy, rx, ry in [(400, 600, 220, 110), (560, 560, 180, 120), (700, 620, 200, 100)]:
        cv.ellipse(cx, cy, rx, ry).fill()
    return cv.mask()


@pytest.fixture
def ctx(theme: Any) -> Any:
    """A draw context for the default theme, slide 0."""
    from history_shorts.compose import DrawContext

    return DrawContext(theme, theme.palette, theme.seed, 0)


@pytest.fixture
def flat_base(palette: Any) -> Callable[[], Any]:
    """Factory: a fresh float32 1920x1080x3 buffer filled with a mid lacquer colour."""
    import numpy as np

    def make() -> Any:
        r, g, b = palette["deep"]
        return np.full((1920, 1080, 3), (r / 255, g / 255, b / 255), dtype=np.float32)

    return make


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


@pytest.fixture
def script_one_slide(tmp_script: Callable[..., Path]) -> Any:
    """A loaded ``Script`` with one slide that has a title and a subtitle."""
    from history_shorts.config import load_script

    path = tmp_script(slides=[{"title": "Hai Bà Trưng khởi nghĩa", "subtitle": "Năm 40"}])
    script, _warnings = load_script(path)
    return script
