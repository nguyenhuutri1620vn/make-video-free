"""The snapshot baseline store: keys, skip on a missing key, update, mismatch (R-02)."""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

import cairo
import pytest
from helpers.snapshots import SNAPSHOT_PACKAGES, SnapshotDb
from PIL import features


def _key() -> str:
    versions = [f"{n}={importlib.metadata.version(n)}" for n in SNAPSHOT_PACKAGES]
    versions.append(f"cairo_c={cairo.cairo_version_string()}")
    versions.append(f"freetype={features.version('freetype2')}")
    return ";".join(versions)


def test_key_names_the_four_drawing_libraries_with_their_versions() -> None:
    db = SnapshotDb(Path("unused.json"), update=False)
    assert db.key == _key()
    assert db.key.startswith("pycairo=") and ";numpy=" in db.key
    assert ";scipy=" in db.key and ";Pillow=" in db.key
    assert ";cairo_c=" in db.key and ";freetype=" in db.key  # the bundled C libraries too


def test_missing_file_or_key_skips_with_the_update_hint(tmp_path: Path) -> None:
    db = SnapshotDb(tmp_path / "baselines.json", update=False)
    with pytest.raises(pytest.skip.Exception, match="run pytest --update-snapshots"):
        db.check("nu_tuong", "abc")
    (tmp_path / "baselines.json").write_text(json.dumps({"other=1": {"nu_tuong": "abc"}}))
    with pytest.raises(pytest.skip.Exception, match="run pytest --update-snapshots"):
        db.check("nu_tuong", "abc")


def test_update_writes_this_key_and_keeps_other_entries(tmp_path: Path) -> None:
    path = tmp_path / "baselines.json"
    path.write_text(json.dumps({"other=1": {"me_linh": "old"}}))
    SnapshotDb(path, update=True).check("nu_tuong", "abc")
    SnapshotDb(path, update=True).check("me_linh", "def")
    data = json.loads(path.read_text())
    assert data == {"other=1": {"me_linh": "old"}, _key(): {"nu_tuong": "abc", "me_linh": "def"}}


def test_check_passes_on_equal_digest_and_fails_on_a_changed_one(tmp_path: Path) -> None:
    path = tmp_path / "baselines.json"
    SnapshotDb(path, update=True).check("nu_tuong", "abc")
    db = SnapshotDb(path, update=False)
    db.check("nu_tuong", "abc")
    with pytest.raises(AssertionError, match="nu_tuong first slide changed"):
        db.check("nu_tuong", "abd")


def test_update_is_atomic_and_leaves_no_tmp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "baselines.json"
    path.write_text(json.dumps({"other=1": {"me_linh": "old"}}))
    before = path.read_text()

    def broken_replace(src: object, dst: object) -> None:
        raise OSError("rename failed")

    monkeypatch.setattr("helpers.snapshots.os.replace", broken_replace)
    with pytest.raises(OSError, match="rename failed"):
        SnapshotDb(path, update=True).check("nu_tuong", "abc")
    assert path.read_text() == before  # the old file is intact
    monkeypatch.undo()
    SnapshotDb(path, update=True).check("nu_tuong", "abc")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["baselines.json"]
