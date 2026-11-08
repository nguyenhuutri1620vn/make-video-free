"""Snapshot baselines keyed by the versions of the libraries that draw (spec R-02)."""

from __future__ import annotations

import importlib.metadata
import json
import os
from pathlib import Path
from typing import Final

import pytest

SNAPSHOT_PACKAGES: Final = ("pycairo", "numpy", "scipy", "Pillow")


class SnapshotDb:
    """SHA-256 baselines of the examples' first slides, keyed by the library versions (R-02)."""

    def __init__(self, path: Path, update: bool) -> None:
        self.path = path
        self.update = update
        self.key = ";".join(
            f"{name}={importlib.metadata.version(name)}" for name in SNAPSHOT_PACKAGES
        )

    def _read(self) -> dict[str, dict[str, str]]:
        data: dict[str, dict[str, str]] = json.loads(self.path.read_text(encoding="utf-8"))
        return data

    def check(self, example: str, digest: str) -> None:
        """Assert ``digest`` equals the baseline; skip when this version set has none."""
        if self.update:
            data = self._read() if self.path.is_file() else {}
            data.setdefault(self.key, {})[example] = digest
            text = json.dumps(data, indent=2, sort_keys=True) + "\n"
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.path)
            return
        baseline = self._read().get(self.key, {}) if self.path.is_file() else {}
        if example not in baseline:
            pytest.skip(f"no snapshot for {self.key}: run pytest --update-snapshots")
        assert digest == baseline[example], f"{example} first slide changed for {self.key}"
