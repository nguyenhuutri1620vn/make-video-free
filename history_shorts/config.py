"""Configuration loading and validation: JSON files become frozen dataclasses.

All validation lives here. ``Ctx`` is a small path-tracking validator: every problem it
records carries a path such as ``palette.gold`` or ``slides[2].scene.layers[4].x`` so that
all errors can be collected and reported together (FR-11). It is shared by the theme loader
below and by the script loader.
"""

from __future__ import annotations

import json
import math
from collections.abc import Collection, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from history_shorts.errors import Issue, Issues, ValidationFailed
from history_shorts.primitives import RGB

SCHEMA_VERSION = "2.0"

REQUIRED_PALETTE_KEYS: tuple[str, ...] = (
    "black",
    "deep",
    "vermilion",
    "vermilion_dk",
    "gold",
    "gold_lt",
    "gold_dk",
    "egg",
    "brown",
    "brown_lt",
    "skin_line",
    "pink",
    "jade",
)

# Optional palette key -> required key it falls back to when absent (spec 6.2).
PALETTE_FALLBACKS: dict[str, str] = {
    "robe_general_dk": "vermilion_dk",
    "robe_general_alt_dk": "brown",
    "robe_crew_dk": "jade",
    "egg_tone": "egg",
    "egg_gap": "brown",
    "sheen": "gold_lt",
    "shadow": "black",
    "deep_warm": "deep",
    "mountain_base": "deep",
    "peak_base": "deep",
    "river_top": "deep",
    "hull_dk": "black",
    "leaf_dk": "jade",
    "petal_tip": "pink",
}

# Upper bounds from C-08: surface finish is sheen + fine grain only.
MAX_SHEEN_STRENGTH = 0.10
MAX_GRAIN_STRENGTH = 0.025


# --------------------------------------------------------------------------------------
# Path-tracking validator
# --------------------------------------------------------------------------------------


def _range_text(lo: float | None, hi: float | None) -> str:
    if lo is not None and hi is not None:
        return f"{lo:g}–{hi:g}"
    if lo is not None:
        return f"≥ {lo:g}"
    if hi is not None:
        return f"≤ {hi:g}"
    return ""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


class Ctx:
    """Validation context: a file name, a shared issue list, and the current path.

    ``at`` and ``idx`` return child contexts, so a reader never builds path strings by
    hand. The typed readers (``int_``, ``num``, ``str_``, ``bool_``) record an error and
    return a harmless placeholder on failure; callers never use the result when
    ``Issues.errors`` is non-empty because loading raises at the end.
    """

    __slots__ = ("file", "issues", "path")

    def __init__(self, file: str, issues: Issues, path: str = "") -> None:
        self.file = file
        self.issues = issues
        self.path = path

    def at(self, key: str) -> Ctx:
        return Ctx(self.file, self.issues, f"{self.path}.{key}" if self.path else key)

    def idx(self, index: int) -> Ctx:
        return Ctx(self.file, self.issues, f"{self.path}[{index}]")

    def error(self, message: str) -> None:
        self.issues.error(self.file, self.path, message)

    def warning(self, message: str) -> None:
        self.issues.warning(self.file, self.path, message)

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
                self.at(key).error("required key missing")
            return {}
        return self.at(key).mapping(obj[key], allowed)

    def items(self, value: object, *, non_empty: bool = False) -> Iterator[tuple[Ctx, Any]]:
        """Iterate an array as ``(child context, element)`` pairs; empty on error."""
        if not isinstance(value, list):
            self.error("must be an array")
            return
        if non_empty and not value:
            self.error("must be a non-empty array")
        for index, element in enumerate(value):
            yield self.idx(index), element

    # -- scalars -------------------------------------------------------------------

    def _lookup(self, obj: Mapping[str, Any], key: str, default: object) -> tuple[Ctx, Any, bool]:
        """Return (child ctx, raw value, usable). Records "required key missing"."""
        child = self.at(key)
        if key in obj:
            return child, obj[key], True
        if default is None:
            child.error("required key missing")
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
            (lo is None or value >= lo) and (hi is None or value <= hi) if _is_int(value) else False
        )
        if not in_range:
            child.error(f"must be an integer {_range_text(lo, hi)}".rstrip())
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
        ok = _is_number(value)
        if ok and positive:
            ok = value > 0
        if ok:
            ok = (lo is None or value >= lo) and (hi is None or value <= hi)
        if not ok:
            rng = "> 0" if positive else _range_text(lo, hi)
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

    def toggle(self, obj: Mapping[str, Any], key: str, *, default: bool) -> bool:
        """A ``{"enabled": bool}`` child (a bare bool is accepted too)."""
        direct = obj.get(key)
        if isinstance(direct, bool):
            return direct
        section = self.section(obj, key, ("enabled",))
        return self.at(key).bool_(section, "enabled", default=default)


# --------------------------------------------------------------------------------------
# Theme dataclasses
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Palette:
    """Colour name -> RGB, with optional keys already filled from their fallbacks."""

    colors: Mapping[str, RGB] = field(hash=False)

    def __getitem__(self, key: str) -> RGB:
        return self.colors[key]

    def rgb01(self, key: str) -> tuple[float, float, float]:
        r, g, b = self.colors[key]
        return (r / 255, g / 255, b / 255)

    def keys(self) -> list[str]:
        return list(self.colors)


@dataclass(frozen=True, slots=True)
class GoldLeafSpec:
    tile: int
    worn: float


@dataclass(frozen=True, slots=True)
class EggshellSpec:
    cell: int
    gap: float


@dataclass(frozen=True, slots=True)
class SheenSpec:
    x: float
    y: float
    r: float
    strength: float


@dataclass(frozen=True, slots=True)
class Textures:
    gold_leaf: GoldLeafSpec
    eggshell: EggshellSpec
    sheen: SheenSpec
    grain: float


@dataclass(frozen=True, slots=True)
class Fonts:
    title: Path
    subtitle: Path
    tag: Path


@dataclass(frozen=True, slots=True)
class TypeScale:
    tag: int
    title: int
    title_min: int
    subtitle: int
    subtitle_min: int


@dataclass(frozen=True, slots=True)
class SealSpec:
    lines: tuple[str, ...]
    x: float
    y: float
    size: float


@dataclass(frozen=True, slots=True)
class TagSpec:
    cx: float
    y: float


@dataclass(frozen=True, slots=True)
class WavesSpec:
    y: float
    rows: int


@dataclass(frozen=True, slots=True)
class FooterSpec:
    enabled: bool
    text: str


@dataclass(frozen=True, slots=True)
class Chrome:
    frame: bool
    seal: SealSpec
    tag: TagSpec
    waves: WavesSpec
    progress_bar: bool
    footer: FooterSpec


@dataclass(frozen=True, slots=True)
class Transition:
    fade_in: float
    fade_out: float


@dataclass(frozen=True, slots=True)
class VideoSpec:
    fps: int
    crf: int


@dataclass(frozen=True, slots=True)
class Theme:
    schema_version: str
    name: str
    seed: int
    palette: Palette
    fonts: Fonts
    type_scale: TypeScale
    textures: Textures
    chrome: Chrome
    transition: Transition
    video: VideoSpec
    path: Path


# --------------------------------------------------------------------------------------
# JSON reading
# --------------------------------------------------------------------------------------


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


# --------------------------------------------------------------------------------------
# Theme parsing
# --------------------------------------------------------------------------------------

_THEME_KEYS = (
    "schema_version",
    "name",
    "seed",
    "palette",
    "fonts",
    "type_scale",
    "textures",
    "chrome",
    "transition",
    "video",
)


def _read_rgb(ctx: Ctx, value: object) -> RGB | None:
    if not isinstance(value, list) or len(value) != 3:
        ctx.error("must be an array of 3 integers")
        return None
    if not all(_is_int(v) and 0 <= v <= 255 for v in value):
        ctx.error("each value must be an integer 0–255")
        return None
    return (int(value[0]), int(value[1]), int(value[2]))


def _parse_palette(ctx: Ctx, obj: Mapping[str, Any]) -> Palette:
    raw = ctx.section(obj, "palette", (*REQUIRED_PALETTE_KEYS, *PALETTE_FALLBACKS), required=True)
    colors: dict[str, RGB] = {}
    if not isinstance(obj.get("palette"), dict):
        return Palette(colors)  # already reported as missing / not an object
    palette_ctx = ctx.at("palette")
    for key in (*REQUIRED_PALETTE_KEYS, *PALETTE_FALLBACKS):
        if key not in raw:
            if key in REQUIRED_PALETTE_KEYS:
                palette_ctx.at(key).error("required key missing")
            continue
        rgb = _read_rgb(palette_ctx.at(key), raw[key])
        if rgb is not None:
            colors[key] = rgb
    for optional, required in PALETTE_FALLBACKS.items():
        if optional not in colors and required in colors:
            colors[optional] = colors[required]
    return Palette(colors)


def _parse_fonts(ctx: Ctx, obj: Mapping[str, Any], base: Path) -> Fonts:
    raw = ctx.section(obj, "fonts", ("title", "subtitle", "tag"), required=True)
    fonts_ctx = ctx.at("fonts")
    resolved: dict[str, Path] = {}
    for key in ("title", "subtitle", "tag"):
        name = fonts_ctx.str_(raw, key) if isinstance(obj.get("fonts"), dict) else ""
        target = (base / name).resolve()
        if name and not target.is_file():
            fonts_ctx.at(key).error(f"file not found: {target}")
        resolved[key] = target
    return Fonts(resolved["title"], resolved["subtitle"], resolved["tag"])


def _parse_type_scale(ctx: Ctx, obj: Mapping[str, Any]) -> TypeScale:
    raw = ctx.section(
        obj, "type_scale", ("tag", "title", "title_min", "subtitle", "subtitle_min"), required=True
    )
    if not isinstance(obj.get("type_scale"), dict):
        return TypeScale(0, 0, 0, 0, 0)  # already reported as missing / not an object
    ts = ctx.at("type_scale")
    scale = TypeScale(
        tag=ts.int_(raw, "tag", lo=1),
        title=ts.int_(raw, "title", lo=1),
        title_min=ts.int_(raw, "title_min", lo=1),
        subtitle=ts.int_(raw, "subtitle", lo=1),
        subtitle_min=ts.int_(raw, "subtitle_min", lo=1),
    )
    if scale.title and scale.title_min > scale.title:
        ts.at("title_min").error(f"must be ≤ title ({scale.title})")
    if scale.subtitle and scale.subtitle_min > scale.subtitle:
        ts.at("subtitle_min").error(f"must be ≤ subtitle ({scale.subtitle})")
    return scale


def _parse_textures(ctx: Ctx, obj: Mapping[str, Any]) -> Textures:
    raw = ctx.section(obj, "textures", ("gold_leaf", "eggshell", "sheen", "grain"))
    tx = ctx.at("textures")
    gold = tx.section(raw, "gold_leaf", ("tile", "worn"))
    egg = tx.section(raw, "eggshell", ("cell", "gap"))
    sheen = tx.section(raw, "sheen", ("x", "y", "r", "strength"))
    grain = tx.section(raw, "grain", ("strength",))
    return Textures(
        gold_leaf=GoldLeafSpec(
            tile=tx.at("gold_leaf").int_(gold, "tile", default=34, lo=1),
            worn=tx.at("gold_leaf").num(gold, "worn", default=0.05, lo=0, hi=1),
        ),
        eggshell=EggshellSpec(
            cell=tx.at("eggshell").int_(egg, "cell", default=16, lo=1),
            gap=tx.at("eggshell").num(egg, "gap", default=1.0, positive=True),
        ),
        sheen=SheenSpec(
            x=tx.at("sheen").num(sheen, "x", default=330.0),
            y=tx.at("sheen").num(sheen, "y", default=760.0),
            r=tx.at("sheen").num(sheen, "r", default=620.0, positive=True),
            strength=tx.at("sheen").num(
                sheen, "strength", default=MAX_SHEEN_STRENGTH, lo=0, hi=MAX_SHEEN_STRENGTH
            ),
        ),
        grain=tx.at("grain").num(grain, "strength", default=0.025, lo=0, hi=MAX_GRAIN_STRENGTH),
    )


def _read_seal_lines(ctx: Ctx, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        ctx.error("must be a non-empty array of non-empty strings")
        return ()
    lines: list[str] = []
    for item_ctx, element in ctx.items(value):
        if isinstance(element, str) and element:
            lines.append(element)
        else:
            item_ctx.error("must be a non-empty string")
    return tuple(lines)


def _parse_seal(ctx: Ctx, obj: Mapping[str, Any]) -> SealSpec:
    raw = ctx.section(obj, "seal", ("lines", "x", "y", "size"))
    seal = ctx.at("seal")
    lines = _read_seal_lines(seal.at("lines"), raw["lines"]) if "lines" in raw else ("SỬ", "VIỆT")
    return SealSpec(
        lines=lines,
        x=seal.num(raw, "x", default=92.0, lo=0),
        y=seal.num(raw, "y", default=160.0, lo=0),
        size=seal.num(raw, "size", default=118.0, positive=True),
    )


def _parse_chrome(ctx: Ctx, obj: Mapping[str, Any]) -> Chrome:
    raw = ctx.section(obj, "chrome", ("frame", "seal", "tag", "waves", "progress_bar", "footer"))
    ch = ctx.at("chrome")
    tag = ch.section(raw, "tag", ("cx", "y"))
    waves = ch.section(raw, "waves", ("y", "rows"))
    footer = ch.section(raw, "footer", ("enabled", "text"))
    footer_ctx = ch.at("footer")
    return Chrome(
        frame=ch.toggle(raw, "frame", default=True),
        seal=_parse_seal(ch, raw),
        tag=TagSpec(
            cx=ch.at("tag").num(tag, "cx", default=590.0, lo=0),
            y=ch.at("tag").num(tag, "y", default=180.0, lo=0),
        ),
        waves=WavesSpec(
            y=ch.at("waves").num(waves, "y", default=1600.0, lo=0),
            rows=ch.at("waves").int_(waves, "rows", default=4, lo=1),
        ),
        progress_bar=ch.toggle(raw, "progress_bar", default=False),
        footer=FooterSpec(
            enabled=footer_ctx.bool_(footer, "enabled", default=False),
            text=footer_ctx.str_(footer, "text", default="", non_empty=False),
        ),
    )


def _parse_theme(ctx: Ctx, data: Mapping[str, Any], path: Path) -> Theme:
    for key in data:
        if key not in _THEME_KEYS:
            ctx.at(str(key)).warning("unknown key (ignored)")
    version = ctx.str_(data, "schema_version")
    if version and version != SCHEMA_VERSION:
        ctx.at("schema_version").error(
            f'unsupported schema_version "{version}" (expected "{SCHEMA_VERSION}")'
        )
    transition = ctx.section(data, "transition", ("fade_in", "fade_out"))
    video = ctx.section(data, "video", ("fps", "crf"))
    tr, vd = ctx.at("transition"), ctx.at("video")
    return Theme(
        schema_version=version,
        name=ctx.str_(data, "name"),
        seed=ctx.int_(data, "seed", lo=0),
        palette=_parse_palette(ctx, data),
        fonts=_parse_fonts(ctx, data, path.parent),
        type_scale=_parse_type_scale(ctx, data),
        textures=_parse_textures(ctx, data),
        chrome=_parse_chrome(ctx, data),
        transition=Transition(
            fade_in=tr.num(transition, "fade_in", default=0.3, lo=0),
            fade_out=tr.num(transition, "fade_out", default=0.3, lo=0),
        ),
        video=VideoSpec(
            fps=vd.int_(video, "fps", default=30, lo=1),
            crf=vd.int_(video, "crf", default=20, lo=0, hi=51),
        ),
        path=path,
    )


def load_theme(path: Path) -> tuple[Theme, list[Issue]]:
    """Load and validate a theme file.

    Returns the theme and its warnings. Raises ``ValidationFailed`` carrying every error.
    """
    resolved = path.resolve()
    issues = Issues()
    data = read_json_object(path, issues)
    if data is None:
        issues.raise_if_errors()
        raise AssertionError("unreachable")  # pragma: no cover
    theme = _parse_theme(Ctx(path.name, issues), data, resolved)
    issues.raise_if_errors()
    return theme, issues.warnings


__all__ = [
    "PALETTE_FALLBACKS",
    "REQUIRED_PALETTE_KEYS",
    "Chrome",
    "Ctx",
    "EggshellSpec",
    "FooterSpec",
    "Fonts",
    "GoldLeafSpec",
    "Palette",
    "SealSpec",
    "SheenSpec",
    "TagSpec",
    "Textures",
    "Theme",
    "Transition",
    "TypeScale",
    "ValidationFailed",
    "VideoSpec",
    "WavesSpec",
    "load_theme",
    "read_json_object",
]
