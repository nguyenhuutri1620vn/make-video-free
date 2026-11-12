"""Configuration loading and validation: JSON files become frozen dataclasses.

All validation lives under ``history_shorts`` config modules: the generic path-tracking
validator in ``validation``, scene/layer/character parsing in ``scene_config``, script and
slide parsing in ``script_config``, and the theme loader here. This module re-exports every
public name so callers import from ``history_shorts.config`` only.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from PIL import ImageFont

from history_shorts.errors import Issue, Issues, ValidationFailed
from history_shorts.primitives import RGB
from history_shorts.scene_config import (
    LAYER_TYPES,
    ROLE_NAMES,
    BirdItem,
    BirdsLayer,
    BoatLayer,
    CharactersLayer,
    CharacterSpec,
    CloudItem,
    CloudsLayer,
    DrumLayer,
    GongLayer,
    GroundLayer,
    HillsLayer,
    Layer,
    LayerScene,
    LotusLayer,
    MountainsLayer,
    PeakItem,
    PeaksLayer,
    RiverLayer,
    SunLayer,
    TemplateScene,
    TempleLayer,
)
from history_shorts.script_config import Script, Slide, Source, load_script, slide_duration
from history_shorts.validation import Ctx, is_int, read_json_object

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
    duration: float = 0.5  # overlap of a slide ``transition`` (spec A.2.3)


@dataclass(frozen=True, slots=True)
class TextInSpec:
    """Title/subtitle fade-in for ``text_in: fade`` slides (spec A.2.2)."""

    delay: float = 0.3
    duration: float = 0.5


@dataclass(frozen=True, slots=True)
class ToneSpec:
    """One colour grade: saturation and brightness factors, then a tint mixed in (A.2.2)."""

    saturation: float
    brightness: float
    tint: RGB
    strength: float


DEFAULT_TONES: Final[Mapping[str, ToneSpec]] = MappingProxyType(
    {
        "warm": ToneSpec(1.1, 1.05, (255, 190, 120), 0.10),
        "cold": ToneSpec(0.55, 0.85, (90, 120, 150), 0.25),
        "gray": ToneSpec(0.0, 0.9, (128, 128, 128), 0.0),
    }
)
TONE_NAMES: Final = tuple(DEFAULT_TONES)


@dataclass(frozen=True, slots=True)
class VideoSpec:
    fps: int
    crf: int


@dataclass(frozen=True, slots=True)
class DuckSpec:
    """Music ducking under the voice: a sidechain compressor (spec A.1.7)."""

    threshold: float
    ratio: float
    attack_ms: float
    release_ms: float


@dataclass(frozen=True, slots=True)
class AudioSpec:
    """Voice and loudness settings, the theme's optional ``audio`` block (spec A.1.7)."""

    lead_in: float = 0.3
    tail: float = 0.5
    voice_gain_db: float = 0.0
    duck: DuckSpec = DuckSpec(threshold=0.05, ratio=8.0, attack_ms=20.0, release_ms=300.0)
    loudness_lufs: float = -14.0
    true_peak_db: float = -1.5


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
    audio: AudioSpec = field(default_factory=AudioSpec)
    text_in: TextInSpec = field(default_factory=TextInSpec)
    tones: Mapping[str, ToneSpec] = field(default_factory=lambda: DEFAULT_TONES)


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
    "audio",
    "text_in",
    "tones",
)


def _read_rgb(ctx: Ctx, value: object) -> RGB | None:
    if not isinstance(value, list) or len(value) != 3:
        ctx.error("must be an array of 3 integers")
        return None
    if not all(is_int(v) and 0 <= v <= 255 for v in value):
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


FONT_PROBE_SIZE: Final = 12


def _parse_fonts(ctx: Ctx, obj: Mapping[str, Any], base: Path) -> Fonts:
    raw = ctx.section(obj, "fonts", ("title", "subtitle", "tag"), required=True)
    fonts_ctx = ctx.at("fonts")
    resolved: dict[str, Path] = {}
    for key in ("title", "subtitle", "tag"):
        name = fonts_ctx.str_(raw, key) if isinstance(obj.get("fonts"), dict) else ""
        target = (base / name).resolve()
        if name and not target.is_file():
            fonts_ctx.at(key).error(f"file not found: {target}")
        elif name:
            try:
                ImageFont.truetype(
                    str(target), FONT_PROBE_SIZE, layout_engine=ImageFont.Layout.BASIC
                )
            except OSError as exc:
                fonts_ctx.at(key).error(f"cannot load font {target}: {exc}")
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
            lines.append(unicodedata.normalize("NFC", element))
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
            text=unicodedata.normalize(
                "NFC", footer_ctx.str_(footer, "text", default="", non_empty=False)
            ),
        ),
    )


AUDIO_KEYS = (
    "lead_in",
    "tail",
    "voice_gain_db",
    "duck",
    "loudness_lufs",
    "true_peak_db",
)
DUCK_KEYS = ("threshold", "ratio", "attack_ms", "release_ms")


def _parse_audio(ctx: Ctx, data: Mapping[str, Any]) -> AudioSpec:
    """The optional ``audio`` block; every key has a default (spec A.1.7)."""
    obj = ctx.section(data, "audio", AUDIO_KEYS)
    au = ctx.at("audio")
    defaults = AudioSpec()
    duck_obj = au.section(obj, "duck", DUCK_KEYS)
    du = au.at("duck")
    return AudioSpec(
        lead_in=au.num(obj, "lead_in", default=defaults.lead_in, lo=0, hi=5),
        tail=au.num(obj, "tail", default=defaults.tail, lo=0, hi=5),
        voice_gain_db=au.num(obj, "voice_gain_db", default=0.0, lo=-12, hi=12),
        duck=DuckSpec(
            threshold=du.num(duck_obj, "threshold", default=defaults.duck.threshold, lo=0, hi=1),
            ratio=du.num(duck_obj, "ratio", default=defaults.duck.ratio, lo=1, hi=20),
            attack_ms=du.num(
                duck_obj, "attack_ms", default=defaults.duck.attack_ms, lo=0.01, hi=2000
            ),
            release_ms=du.num(
                duck_obj, "release_ms", default=defaults.duck.release_ms, lo=0.01, hi=9000
            ),
        ),
        loudness_lufs=au.num(obj, "loudness_lufs", default=defaults.loudness_lufs, lo=-70, hi=-5),
        true_peak_db=au.num(obj, "true_peak_db", default=defaults.true_peak_db, lo=-9, hi=0),
    )


TONE_KEYS = ("saturation", "brightness", "tint", "strength")


def _parse_text_in(ctx: Ctx, data: Mapping[str, Any]) -> TextInSpec:
    obj = ctx.section(data, "text_in", ("delay", "duration"))
    ti, defaults = ctx.at("text_in"), TextInSpec()
    return TextInSpec(
        delay=ti.num(obj, "delay", default=defaults.delay, lo=0, hi=5),
        duration=ti.num(obj, "duration", default=defaults.duration, lo=0.05, hi=5),
    )


def _parse_tone(ctx: Ctx, obj: Mapping[str, Any], default: ToneSpec) -> ToneSpec:
    tint = _read_rgb(ctx.at("tint"), obj["tint"]) if "tint" in obj else None
    return ToneSpec(
        saturation=ctx.num(obj, "saturation", default=default.saturation, lo=0, hi=2),
        brightness=ctx.num(obj, "brightness", default=default.brightness, lo=0.2, hi=2),
        tint=tint or default.tint,
        strength=ctx.num(obj, "strength", default=default.strength, lo=0, hi=1),
    )


def _parse_tones(ctx: Ctx, data: Mapping[str, Any]) -> Mapping[str, ToneSpec]:
    """The optional ``tones`` block: per-name overrides of ``DEFAULT_TONES`` (spec A.2.2)."""
    obj = ctx.section(data, "tones", TONE_NAMES)
    tones = dict(DEFAULT_TONES)
    for name in TONE_NAMES:
        tc = ctx.at("tones").at(name)
        if name in obj:
            tones[name] = _parse_tone(tc, tc.mapping(obj[name], TONE_KEYS), DEFAULT_TONES[name])
    return MappingProxyType(tones)


def _parse_theme(ctx: Ctx, data: Mapping[str, Any], path: Path) -> Theme:
    for key in data:
        if key not in _THEME_KEYS:
            ctx.at(str(key)).warning("unknown key (ignored)")
    version = ctx.str_(data, "schema_version")
    if version and version != SCHEMA_VERSION:
        ctx.at("schema_version").error(
            f'unsupported schema_version "{version}" (expected "{SCHEMA_VERSION}")'
        )
    transition = ctx.section(data, "transition", ("fade_in", "fade_out", "duration"))
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
            duration=tr.num(transition, "duration", default=0.5, lo=0.1, hi=2),
        ),
        video=VideoSpec(
            fps=vd.int_(video, "fps", default=30, lo=1),
            crf=vd.int_(video, "crf", default=20, lo=0, hi=51),
        ),
        path=path,
        audio=_parse_audio(ctx, data),
        text_in=_parse_text_in(ctx, data),
        tones=_parse_tones(ctx, data),
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
    "LAYER_TYPES",
    "PALETTE_FALLBACKS",
    "REQUIRED_PALETTE_KEYS",
    "ROLE_NAMES",
    "BirdItem",
    "BirdsLayer",
    "BoatLayer",
    "CharacterSpec",
    "CharactersLayer",
    "Chrome",
    "CloudItem",
    "CloudsLayer",
    "Ctx",
    "EggshellSpec",
    "FooterSpec",
    "Fonts",
    "GoldLeafSpec",
    "GroundLayer",
    "HillsLayer",
    "Issue",
    "Layer",
    "LayerScene",
    "LotusLayer",
    "DrumLayer",
    "GongLayer",
    "TempleLayer",
    "MountainsLayer",
    "Palette",
    "PeakItem",
    "PeaksLayer",
    "RiverLayer",
    "Script",
    "SealSpec",
    "SheenSpec",
    "Slide",
    "Source",
    "SunLayer",
    "TagSpec",
    "TemplateScene",
    "Textures",
    "TextInSpec",
    "Theme",
    "ToneSpec",
    "Transition",
    "TypeScale",
    "ValidationFailed",
    "VideoSpec",
    "WavesSpec",
    "load_script",
    "load_theme",
    "read_json_object",
    "slide_duration",
]
