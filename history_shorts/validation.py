"""Generic path-tracking validation and JSON reading, shared by theme and script loaders.

``Ctx`` records every problem with a path such as ``palette.gold`` or
``slides[2].scene.layers[4].x`` so that all errors can be collected and reported together
(FR-11). It knows nothing about themes or scripts.
"""

from __future__ import annotations

import json
import math
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import Any

from history_shorts.errors import Issues


def range_text(lo: float | None, hi: float | None) -> str:
    if lo is not None and hi is not None:
        return f"{lo:g}–{hi:g}"
    if lo is not None:
        return f"≥ {lo:g}"
    if hi is not None:
        return f"≤ {hi:g}"
    return ""


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: object) -> bool:
    """A finite int or float (not bool). Ints beyond float range are not numbers."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        return False


class Ctx:
    """Validation context: a file name, a shared issue list, and the current path.

    ``at`` and ``idx`` return child contexts, so a reader never builds path strings by
    hand. The typed readers (``int_``, ``num``, ``str_``, ``bool_``, ``choice``) record an
    error and return a harmless placeholder on failure; callers never use the result when
    ``Issues.errors`` is non-empty because loading raises at the end.

    ``terse`` selects the script message style: a missing key reads ``required`` and a
    numeric range error reads ``must be 0–1080`` (AC-11). The default (theme) style reads
    ``required key missing`` and ``must be a number 0–1``. The flag is inherited by
    children.
    """

    __slots__ = ("file", "issues", "path", "terse")

    def __init__(self, file: str, issues: Issues, path: str = "", *, terse: bool = False) -> None:
        self.file = file
        self.issues = issues
        self.path = path
        self.terse = terse

    def at(self, key: str) -> Ctx:
        path = f"{self.path}.{key}" if self.path else key
        return Ctx(self.file, self.issues, path, terse=self.terse)

    def idx(self, index: int) -> Ctx:
        return Ctx(self.file, self.issues, f"{self.path}[{index}]", terse=self.terse)

    def error(self, message: str) -> None:
        self.issues.error(self.file, self.path, message)

    def warning(self, message: str) -> None:
        self.issues.warning(self.file, self.path, message)

    def missing(self) -> None:
        """Record that the value at this path is required but absent."""
        self.error("required" if self.terse else "required key missing")

    # -- structure -----------------------------------------------------------------

    def mapping(self, value: object, allowed: Collection[str] | None = None) -> dict[str, Any]:
        """Return ``value`` as a dict (empty on error); warn about keys not in ``allowed``."""
        if not isinstance(value, dict):
            self.error("must be an object")
            return {}
        if allowed is not None:
            for key in value:
                if key not in allowed:
                    self.at(str(key)).warning("unknown key (ignored)")
        return value

    def section(
        self, obj: Mapping[str, Any], key: str, allowed: Collection[str], *, required: bool = False
    ) -> dict[str, Any]:
        """Read an object-valued child. An absent optional section yields ``{}``."""
        if key not in obj:
            if required:
                self.at(key).missing()
            return {}
        return self.at(key).mapping(obj[key], allowed)

    def items(self, value: object, *, non_empty: bool = False) -> list[tuple[Ctx, Any]]:
        """Return an array as ``(child context, element)`` pairs; empty on error.

        Returns a list, not a generator, so "must be an array" / "non-empty" errors are
        recorded as soon as the call returns even if the caller never iterates.
        """
        if not isinstance(value, list):
            self.error("must be an array")
            return []
        if non_empty and not value:
            self.error("must be a non-empty array")
        return [(self.idx(index), element) for index, element in enumerate(value)]

    # -- scalars -------------------------------------------------------------------

    def _lookup(self, obj: Mapping[str, Any], key: str, default: object) -> tuple[Ctx, Any, bool]:
        """Return (child ctx, raw value, usable). Records a missing required key."""
        child = self.at(key)
        if key in obj:
            return child, obj[key], True
        if default is None:
            child.missing()
        return child, default, False

    def int_(
        self,
        obj: Mapping[str, Any],
        key: str,
        *,
        default: int | None = None,
        lo: int | None = None,
        hi: int | None = None,
    ) -> int:
        child, value, present = self._lookup(obj, key, default)
        if not present:
            return default if default is not None else 0
        in_range = (
            (lo is None or value >= lo) and (hi is None or value <= hi) if is_int(value) else False
        )
        if not in_range:
            child.error(f"must be an integer {range_text(lo, hi)}".rstrip())
            return default if default is not None else 0
        return int(value)

    def num(
        self,
        obj: Mapping[str, Any],
        key: str,
        *,
        default: float | None = None,
        lo: float | None = None,
        hi: float | None = None,
        positive: bool = False,
    ) -> float:
        child, value, present = self._lookup(obj, key, default)
        fallback = default if default is not None else 0.0
        if not present:
            return fallback
        ok = is_number(value)
        if ok and positive:
            ok = value > 0
        if ok:
            ok = (lo is None or value >= lo) and (hi is None or value <= hi)
        if not ok:
            rng = "> 0" if positive else range_text(lo, hi)
            if self.terse:
                child.error(f"must be {rng}" if rng else "must be a number")
            else:
                child.error(f"must be a number {rng}".rstrip())
            return fallback
        return float(value)

    def str_(
        self,
        obj: Mapping[str, Any],
        key: str,
        *,
        default: str | None = None,
        non_empty: bool = True,
    ) -> str:
        child, value, present = self._lookup(obj, key, default)
        if not present:
            return default if default is not None else ""
        if not isinstance(value, str) or (non_empty and not value):
            child.error("must be a non-empty string" if non_empty else "must be a string")
            return default if default is not None else ""
        return value

    def bool_(self, obj: Mapping[str, Any], key: str, *, default: bool | None = None) -> bool:
        child, value, present = self._lookup(obj, key, default)
        if not present:
            return default if default is not None else False
        if not isinstance(value, bool):
            child.error("must be true or false")
            return default if default is not None else False
        return value

    def choice(
        self,
        obj: Mapping[str, Any],
        key: str,
        allowed: Sequence[str],
        *,
        default: str | None = None,
    ) -> str:
        """A string that must be one of ``allowed`` (reported in the given order)."""
        child, value, present = self._lookup(obj, key, default)
        if not present:
            return default if default is not None else ""
        if not isinstance(value, str) or value not in allowed:
            child.error(f"must be one of {', '.join(allowed)}")
            return default if default is not None else ""
        return value

    def toggle(self, obj: Mapping[str, Any], key: str, *, default: bool) -> bool:
        """A ``{"enabled": bool}`` child (a bare bool is accepted too)."""
        direct = obj.get(key)
        if isinstance(direct, bool):
            return direct
        section = self.section(obj, key, ("enabled",))
        return self.at(key).bool_(section, "enabled", default=default)


def read_json_object(path: Path, issues: Issues) -> dict[str, Any] | None:
    """Read a JSON file (UTF-8, BOM tolerated); record an issue and return None on failure."""
    name = path.name
    resolved = path.resolve()
    try:
        text = resolved.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        issues.error(name, "(file)", f"file not found: {resolved}")
        return None
    except UnicodeDecodeError:
        issues.error(name, "(json)", "file is not valid UTF-8")
        return None
    except OSError as exc:
        issues.error(name, "(file)", f"cannot read file: {exc.strerror or exc}")
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        issues.error(
            name, "(json)", f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        )
        return None
    if not isinstance(data, dict):
        issues.error(name, "(json)", "top level must be an object")
        return None
    return data
