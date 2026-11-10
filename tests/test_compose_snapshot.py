"""Snapshot of the examples' first slides and full-run determinism (R-02, AC-12)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from helpers.snapshots import SnapshotDb

from history_shorts.config import load_script
from history_shorts.render import render_slides, scene_expander


@pytest.mark.parametrize("example", ["nu_tuong", "me_linh"])
def test_first_slide_snapshot(
    example: str, first_slide_png: Callable[[str], Path], snapshot_db: SnapshotDb
) -> None:
    digest = hashlib.sha256(first_slide_png(example).read_bytes()).hexdigest()
    snapshot_db.check(example, digest)


@pytest.mark.parametrize("example", ["nu_tuong", "me_linh"])
def test_full_slides_byte_identical(
    example: str, repo_root: Path, theme: Any, tmp_path: Path
) -> None:
    """AC-12: two complete renders into different directories give identical PNGs."""
    script, _warnings = load_script(repo_root / "examples" / example / "script.json")
    first = render_slides(
        script, theme, tmp_path / "a" / "v.mp4", debug_safe_zone=False, expand=scene_expander
    )
    second = render_slides(
        script, theme, tmp_path / "b" / "v.mp4", debug_safe_zone=False, expand=scene_expander
    )
    assert len(first) == len(second) == len(script.slides)
    for a, b in zip(first, second, strict=True):
        assert a.read_bytes() == b.read_bytes(), a.name
