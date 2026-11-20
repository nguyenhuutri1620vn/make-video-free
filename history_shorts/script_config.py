"""Script contract (spec 6.1): ``script.json`` becomes a frozen ``Script``.

All text fields are NFC-normalised before any check, so a decomposed (NFD) Vietnamese
string is measured, validated and rendered the same as its composed form. Messages use the
terse style of AC-11, e.g. ``script.json › slides[2].scene.layers[0].x: must be 0–1080``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal, cast

from history_shorts.errors import Issue, Issues
from history_shorts.narration import MAX_NARRATION_CHARS, normalise, pause_problems
from history_shorts.scene_config import (
    PLANE_KEY,
    V23_CHARACTER_KEYS,
    LayerScene,
    TemplateScene,
    parse_scene,
)
from history_shorts.validation import Ctx, is_int, read_json_object

SCRIPT_SCHEMA_VERSION = "2.0"  # the version every v2.0 script declares
NARRATED_SCHEMA_VERSION = "2.1"  # adds slide ``id`` and ``narration`` (spec A.1.2)
LIVING_SCHEMA_VERSION = "2.2"  # adds living slides and synthesized sound cues (M9)
ANIMATED_SCHEMA_VERSION = "2.3"  # adds redrawn scene motion and character animation (M10)
SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = (
    SCRIPT_SCHEMA_VERSION,
    NARRATED_SCHEMA_VERSION,
    LIVING_SCHEMA_VERSION,
    ANIMATED_SCHEMA_VERSION,
)
SCHEMA_LEVELS: Mapping[str, int] = {v: n for n, v in enumerate(SUPPORTED_SCHEMA_VERSIONS)}
NARRATED_LEVEL = 1
LIVING_LEVEL = 2
ANIMATED_LEVEL = 3
SLIDE_ID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")

MAX_TAG_CHARS = 28
MAX_TITLE_CHARS = 60
MAX_SUBTITLE_CHARS = 120
MIN_SLIDES = 1
MAX_SLIDES = 30
MIN_SLIDE_SECONDS = 0.5
MAX_SLIDE_SECONDS = 15.0

# FR-83: auto-duration = clamp(chars x SECONDS_PER_CHAR, AUTO_MIN, AUTO_MAX).
SECONDS_PER_CHAR = 0.08
AUTO_MIN_SECONDS = 2.5
AUTO_MAX_SECONDS = 6.0

# FR-13: warn when the total length leaves this range. The theme's fps is not known while
# the script loads, so the total is estimated at DEFAULT_FPS.
MIN_TOTAL_SECONDS = 15.0
MAX_TOTAL_SECONDS = 90.0
DEFAULT_FPS = 30

MOTION_NAMES: tuple[str, ...] = (
    "none", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down",
)  # fmt: skip
V20_MOTIONS: tuple[str, ...] = ("none", "zoom_in")

# Spec A.2: slide transitions, tones, text fade-in, sound effects and music cuts (2.1 only).
TRANSITION_NAMES: tuple[str, ...] = (
    "cut", "fade", "fadeblack", "dissolve", "slideleft", "slideright", "slideup",
    "wipeleft", "wiperight", "circleopen",
)  # fmt: skip
TONE_NAMES: tuple[str, ...] = ("none", "warm", "cold", "gray")
TEXT_IN_NAMES: tuple[str, ...] = ("none", "fade")
MAX_SFX = 4
SFX_GAIN_DB = (-24.0, 12.0)
MUSIC_CUT_SECONDS = (0.1, 5.0)
A2_KEYS: tuple[str, ...] = ("transition", "tone", "text_in", "sfx", "music_cut")

# M9 (2.2): living slides and synthesized sound cues.
V22_KEYS: tuple[str, ...] = ("living", "particles", "auto_sfx")
V23_KEYS: tuple[str, ...] = ("actions",)
# characters.actions.ACTIONS; kept here so the script parser does not import drawing code
ACTION_NAMES: tuple[str, ...] = ("rally", "bow", "kneel", "sit", "stand_up", "raise_flag", "look")
_ACTION_KEYS = ("who", "do", "at", "duration")
ACTION_SECONDS: tuple[float, float] = (0.3, 10.0)
SOUND_NAMES: tuple[str, ...] = ("gong", "drum", "bell", "whoosh", "wind", "water")
BED_SOUNDS: tuple[str, ...] = ("wind", "water")  # need a ``duration``
HIT_SOUNDS: tuple[str, ...] = ("gong", "drum")  # may ``shake`` the scene
PARTICLE_NAMES: tuple[str, ...] = ("none", "petals", "dust", "embers")
BED_SECONDS = (0.5, 14.0)
V22_CUE_KEYS: tuple[str, ...] = ("sound", "duration", "shake")

# Optional kind of a citation in ``sources`` (spec 6.1), shown in the sources block.
SOURCE_TYPES: tuple[str, ...] = ("book", "journal", "news", "web", "other")

# Emoji and pictographs (spec 8.4), by code point: ranges are inclusive.
_EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0xFE0F, 0xFE0F),
    (0x200D, 0x200D),
)

_SCRIPT_KEYS = ("schema_version", "title", "sources", "slides")
_SOURCE_KEYS = ("text", "type")
_SLIDE_KEYS = (
    "tag",
    "title",
    "subtitle",
    "duration",
    "scene",
    "motion",
    "claim",
    "source",
    "id",
    "narration",
    *A2_KEYS,
    *V22_KEYS,
    *V23_KEYS,
)
_SFX_KEYS = ("file", "at", "gain_db", *V22_CUE_KEYS)
_MUSIC_CUT_KEYS = ("at", "duration")


@dataclass(frozen=True, slots=True)
class Source:
    """One citation: its text and, optionally, its kind (one of ``SOURCE_TYPES``)."""

    text: str
    type: str | None = None


Motion = Literal["none", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]


@dataclass(frozen=True, slots=True)
class SfxCue:
    """A sound effect: the owner's file or a synthesized ``sound`` (2.2), its start after the
    slide start and its gain. Exactly one of ``path`` and ``sound`` is set."""

    path: Path | None
    at: float
    gain_db: float = 0.0
    sound: str | None = None
    duration: float | None = None  # length of a bed sound (``BED_SOUNDS``)
    shake: bool = False  # a hit shakes a living slide's scene (``HIT_SOUNDS``)


@dataclass(frozen=True, slots=True)
class MusicCut:
    """Music is silent from slide start + ``at`` for ``duration`` seconds (spec A.2.1)."""

    at: float
    duration: float


@dataclass(frozen=True, slots=True)
class SlideAction:
    """Character ``who`` performs action ``do`` from ``at`` seconds into the slide (2.3)."""

    who: str
    do: str
    at: float
    duration: float | None = None  # None: the action's default length


@dataclass(frozen=True, slots=True)
class Slide:
    tag: str
    title: str
    subtitle: str
    duration: float | None
    scene: LayerScene | TemplateScene | None
    motion: Motion
    claim: bool
    source: tuple[int, ...]
    id: str = ""  # "sNN" unless the script gives one (2.1); set by the parser
    narration: str | None = None  # normalised spoken text (2.1), None when absent
    transition: str = "cut"  # how this slide enters from the previous one (A.2)
    tone: str = "none"
    text_in: str = "none"
    sfx: tuple[SfxCue, ...] = ()
    music_cut: MusicCut | None = None
    living: bool = False  # parallax planes and ambient motion (2.2)
    particles: str = "none"
    auto_sfx: bool = True  # a whoosh on moving transitions into this slide (2.2)
    actions: tuple[SlideAction, ...] = ()  # timed character actions (2.3)


@dataclass(frozen=True, slots=True)
class Script:
    schema_version: str
    title: str
    sources: tuple[Source, ...]
    slides: tuple[Slide, ...]
    path: Path


# --------------------------------------------------------------------------------------
# Durations
# --------------------------------------------------------------------------------------


def slide_duration(slide: Slide, fps: int) -> float:
    """Seconds this slide is shown, rounded to the nearest frame (FR-83).

    An explicit ``duration`` wins; otherwise ``clamp(chars x 0.08, 2.5, 6.0)`` where
    ``chars`` counts the title and subtitle without line breaks.
    """
    if slide.duration is not None:
        seconds = slide.duration
    else:
        chars = len((slide.title + slide.subtitle).replace("\n", ""))
        seconds = min(max(chars * SECONDS_PER_CHAR, AUTO_MIN_SECONDS), AUTO_MAX_SECONDS)
    return round(seconds * fps) / fps


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------


def _first_emoji(text: str) -> str | None:
    for ch in text:
        code = ord(ch)
        if any(lo <= code <= hi for lo, hi in _EMOJI_RANGES):
            return f"U+{code:04X}"
    return None


def _text(
    ctx: Ctx,
    obj: Mapping[str, Any],
    key: str,
    *,
    required: bool = False,
    max_chars: int | None = None,
) -> str:
    """Read a text field: NFC-normalise, then reject emoji and over-long values."""
    child = ctx.at(key)
    raw = ctx.str_(obj, key) if required else ctx.str_(obj, key, default="", non_empty=False)
    value = unicodedata.normalize("NFC", raw)
    if value and not value.strip():
        child.error("must not be blank")
        return value
    emoji = _first_emoji(value)
    if emoji is not None:
        child.error(f"emoji are not supported ({emoji})")
    elif max_chars is not None and len(value) > max_chars:
        child.error(f"must be at most {max_chars} characters")
    return value


def _parse_source(ctx: Ctx, raw: object) -> Source | None:
    """A citation: a non-empty string, or ``{"text": ..., "type": ...}``."""
    if isinstance(raw, str) and raw:
        return Source(unicodedata.normalize("NFC", raw))
    if not isinstance(raw, dict):
        ctx.error("must be a non-empty string or an object")
        return None
    obj = ctx.mapping(raw, _SOURCE_KEYS)
    errors = len(ctx.issues.errors)
    text = ctx.str_(obj, "text")
    kind = ctx.choice(obj, "type", SOURCE_TYPES) if "type" in obj else None
    if len(ctx.issues.errors) > errors:
        return None
    return Source(unicodedata.normalize("NFC", text), kind)


def _parse_sources(ctx: Ctx, obj: Mapping[str, Any]) -> tuple[Source, ...] | None:
    """The citations, or None when ``sources`` itself is invalid (errors recorded).

    None tells slides to skip their ``source`` range check: with a broken ``sources`` list
    the length is unknown and a range error would be a spurious follow-on.
    """
    if "sources" not in obj:
        ctx.at("sources").warning("missing: factual claims cannot be traced to a source")
        return ()
    sources: list[Source] = []
    valid = True
    for child, raw in ctx.at("sources").items(obj["sources"]):
        source = _parse_source(child, raw)
        if source is None:
            valid = False
        else:
            sources.append(source)
    if not valid or not isinstance(obj["sources"], list):
        return None
    if not sources:
        ctx.at("sources").warning("empty: factual claims cannot be traced to a source")
    return tuple(sources)


def _source_index(ctx: Ctx, value: object, sources: tuple[Source, ...] | None) -> int | None:
    if not is_int(value) or cast(int, value) < 0:
        ctx.error("must be an integer ≥ 0")
        return None
    index = cast(int, value)
    if sources is not None and index >= len(sources):
        noun = "item" if len(sources) == 1 else "items"
        ctx.error(f"index out of range (sources has {len(sources)} {noun})")
    return index


def _parse_source_indices(
    ctx: Ctx, obj: Mapping[str, Any], sources: tuple[Source, ...] | None
) -> tuple[int, ...]:
    """``source``: one index into ``sources`` or a non-empty array of them."""
    if "source" not in obj:
        return ()
    child, value = ctx.at("source"), obj["source"]
    pairs = child.items(value, non_empty=True) if isinstance(value, list) else [(child, value)]
    indices = (_source_index(c, v, sources) for c, v in pairs)
    return tuple(i for i in indices if i is not None)


def _narration(ctx: Ctx, obj: Mapping[str, Any]) -> str | None:
    """Spoken text (2.1): normalised, 1–600 characters, no emoji, only ``[pause Nms]`` tags."""
    if "narration" not in obj:
        return None
    text = normalise(ctx.str_(obj, "narration", default="", non_empty=False))
    if not text:
        ctx.at("narration").error("must not be blank")
        return None
    emoji = _first_emoji(text)
    if emoji is not None:
        ctx.at("narration").error(f"emoji are not supported ({emoji})")
    elif len(text) > MAX_NARRATION_CHARS:
        ctx.at("narration").error(f"must be at most {MAX_NARRATION_CHARS} characters")
    for problem in pause_problems(text):
        ctx.at("narration").error(problem)
    return text


def _sound_fields(ctx: Ctx, obj: Mapping[str, Any]) -> tuple[str, float | None, bool]:
    """``sound``, ``duration`` and ``shake`` of a synthesized cue (2.2)."""
    sound = ctx.choice(obj, "sound", SOUND_NAMES)
    duration: float | None = None
    if sound in BED_SOUNDS:
        if "duration" not in obj:
            ctx.at("duration").error(f"required for {sound}")
        duration = ctx.num(obj, "duration", default=1.0, lo=BED_SECONDS[0], hi=BED_SECONDS[1])
    elif sound == "whoosh" and "duration" in obj:
        duration = ctx.num(obj, "duration", lo=BED_SECONDS[0], hi=BED_SECONDS[1])
    elif "duration" in obj:
        ctx.at("duration").error(f"only {', '.join((*BED_SOUNDS, 'whoosh'))} take a duration")
    shake = ctx.bool_(obj, "shake", default=False)
    if shake and sound not in HIT_SOUNDS:
        ctx.at("shake").error(f"only {' and '.join(HIT_SOUNDS)} can shake")
    return sound, duration, shake


def _parse_sfx_cue(ctx: Ctx, raw: object, base: Path, level: int) -> SfxCue | None:
    obj = ctx.mapping(raw, _SFX_KEYS)
    if not obj:
        return None
    errors = len(ctx.issues.errors)
    if level < LIVING_LEVEL:
        for key in V22_CUE_KEYS:
            if key in obj:
                ctx.at(key).error(f'requires schema_version "{LIVING_SCHEMA_VERSION}"')
    at = ctx.num(obj, "at", default=0.0, lo=0, hi=MAX_SLIDE_SECONDS)
    gain = ctx.num(obj, "gain_db", default=0.0, lo=SFX_GAIN_DB[0], hi=SFX_GAIN_DB[1])
    if ("file" in obj) == ("sound" in obj):
        ctx.error("give either 'file' or 'sound'")
        return None
    if "sound" in obj:
        sound, duration, shake = _sound_fields(ctx, obj)
        ok = len(ctx.issues.errors) == errors
        return SfxCue(None, at, gain, sound, duration, shake) if ok else None
    name = ctx.str_(obj, "file")
    path = (base / name).resolve() if name else base
    if name and not path.is_file():
        ctx.at("file").error(f"file not found: {path}")
    return SfxCue(path, at, gain) if len(ctx.issues.errors) == errors else None


def _parse_sfx(ctx: Ctx, obj: Mapping[str, Any], base: Path, level: int) -> tuple[SfxCue, ...]:
    """``sfx``: up to ``MAX_SFX`` cues; files resolve relative to the script (spec A.2.1)."""
    if "sfx" not in obj:
        return ()
    pairs = ctx.at("sfx").items(obj["sfx"])
    if len(pairs) > MAX_SFX:
        ctx.at("sfx").error(f"must contain at most {MAX_SFX} cues")
    cues = (_parse_sfx_cue(child, raw, base, level) for child, raw in pairs)
    return tuple(cue for cue in cues if cue is not None)


def _parse_music_cut(ctx: Ctx, obj: Mapping[str, Any]) -> MusicCut | None:
    if "music_cut" not in obj:
        return None
    mc = ctx.at("music_cut")
    raw = mc.mapping(obj["music_cut"], _MUSIC_CUT_KEYS)
    lo, hi = MUSIC_CUT_SECONDS
    return MusicCut(
        at=mc.num(raw, "at", default=0.0, lo=0, hi=MAX_SLIDE_SECONDS),
        duration=mc.num(raw, "duration", default=1.0, lo=lo, hi=hi),
    )


def _motion(ctx: Ctx, obj: Mapping[str, Any], narrated: bool) -> Motion:
    """2.0 scripts keep the v2.0 motions and message; 2.1 adds the A.2 motions."""
    value = obj.get("motion")
    if not narrated and value in MOTION_NAMES and value not in V20_MOTIONS:
        ctx.at("motion").error(f'"{value}" requires schema_version "{NARRATED_SCHEMA_VERSION}"')
        return "none"
    allowed = MOTION_NAMES if narrated else V20_MOTIONS
    return cast("Motion", ctx.choice(obj, "motion", allowed, default="none"))


def _slide_id(ctx: Ctx, obj: Mapping[str, Any]) -> str:
    """The explicit ``id`` (2.1) or ``""`` when absent; the parser fills in ``sNN`` later."""
    if "id" not in obj:
        return ""
    value = ctx.str_(obj, "id")
    if not SLIDE_ID_RE.fullmatch(value):
        ctx.at("id").error("must match ^[a-z0-9][a-z0-9_-]{0,31}$")
    return value


def _check_layer_depths(ctx: Ctx, obj: Mapping[str, Any]) -> None:
    """A layer ``plane`` needs schema 2.2; the scene parser does not know the version."""
    scene = obj.get("scene")
    layers = scene.get("layers") if isinstance(scene, dict) else None
    if not isinstance(layers, list):
        return
    for index, layer in enumerate(layers):
        if isinstance(layer, dict) and PLANE_KEY in layer:
            where = ctx.at("scene").at("layers").idx(index).at(PLANE_KEY)
            where.error(f'requires schema_version "{LIVING_SCHEMA_VERSION}"')


def _scene_character_objects(
    obj: Mapping[str, Any],
) -> list[tuple[tuple[str | int, ...], dict[str, Any]]]:
    """(JSON path parts, raw character object) for every character in a raw slide scene."""
    scene = obj.get("scene")
    if not isinstance(scene, dict):
        return []
    found: list[tuple[tuple[str | int, ...], dict[str, Any]]] = []

    def collect(path: tuple[str | int, ...], items: object) -> None:
        if isinstance(items, list):
            for k, item in enumerate(items):
                if isinstance(item, dict):
                    found.append(((*path, k), item))

    collect(("characters",), scene.get("characters"))
    for b, boat in enumerate(scene.get("boats") or []):
        if isinstance(boat, dict):
            collect(("boats", b, "crew"), boat.get("crew"))
    for n, layer in enumerate(scene.get("layers") or []):
        if isinstance(layer, dict):
            collect(("layers", n, "items"), layer.get("items"))
            collect(("layers", n, "crew"), layer.get("crew"))
    return found


def _check_v23_keys(ctx: Ctx, obj: Mapping[str, Any]) -> None:
    message = f'requires schema_version "{ANIMATED_SCHEMA_VERSION}"'
    for key in V23_KEYS:
        if key in obj:
            ctx.at(key).error(message)
    for path, item in _scene_character_objects(obj):
        where = ctx.at("scene")
        for part in path:
            where = where.idx(part) if isinstance(part, int) else where.at(part)
        for key in V23_CHARACTER_KEYS:
            if key in item:
                where.at(key).error(message)


def _parse_action(ctx: Ctx, raw: object) -> SlideAction | None:
    obj = ctx.mapping(raw, _ACTION_KEYS)
    if not obj:
        return None
    errors = len(ctx.issues.errors)
    who = ctx.str_(obj, "who")
    do = ctx.choice(obj, "do", ACTION_NAMES)
    at = ctx.num(obj, "at", default=0.0, lo=0, hi=MAX_SLIDE_SECONDS)
    lo, hi = ACTION_SECONDS
    duration = ctx.num(obj, "duration", lo=lo, hi=hi) if "duration" in obj else None
    return SlideAction(who, do, at, duration) if len(ctx.issues.errors) == errors else None


def _parse_actions(ctx: Ctx, obj: Mapping[str, Any]) -> tuple[SlideAction, ...]:
    if "actions" not in obj:
        return ()
    parsed = (_parse_action(c, raw) for c, raw in ctx.at("actions").items(obj["actions"]))
    return tuple(a for a in parsed if a is not None)


def _check_version_keys(ctx: Ctx, obj: Mapping[str, Any], level: int) -> None:
    if level < NARRATED_LEVEL:
        for key in ("id", "narration", *A2_KEYS):
            if key in obj:
                ctx.at(key).error(f'requires schema_version "{NARRATED_SCHEMA_VERSION}"')
    if level < LIVING_LEVEL:
        for key in V22_KEYS:
            if key in obj:
                ctx.at(key).error(f'requires schema_version "{LIVING_SCHEMA_VERSION}"')
        _check_layer_depths(ctx, obj)
    if level < ANIMATED_LEVEL:
        _check_v23_keys(ctx, obj)


def _parse_slide(
    ctx: Ctx, raw: object, sources: tuple[Source, ...] | None, level: int, base: Path
) -> Slide | None:
    if not isinstance(raw, dict):
        ctx.error("must be an object")
        return None
    obj = ctx.mapping(raw, _SLIDE_KEYS)
    narrated = level >= NARRATED_LEVEL
    _check_version_keys(ctx, obj, level)
    claim = ctx.bool_(obj, "claim", default=False)
    source = _parse_source_indices(ctx, obj, sources)
    if claim and "source" not in obj:
        ctx.at("source").warning("claim is true but no source index is given")
    duration = (
        ctx.num(obj, "duration", lo=MIN_SLIDE_SECONDS, hi=MAX_SLIDE_SECONDS)
        if "duration" in obj
        else None
    )
    return Slide(
        tag=_text(ctx, obj, "tag", max_chars=MAX_TAG_CHARS),
        title=_text(ctx, obj, "title", required=True, max_chars=MAX_TITLE_CHARS),
        subtitle=_text(ctx, obj, "subtitle", max_chars=MAX_SUBTITLE_CHARS),
        duration=duration,
        scene=parse_scene(ctx.at("scene"), obj["scene"]) if "scene" in obj else None,
        motion=_motion(ctx, obj, narrated),
        claim=claim,
        source=source,
        id=_slide_id(ctx, obj),
        narration=_narration(ctx, obj),
        transition=ctx.choice(obj, "transition", TRANSITION_NAMES, default="cut"),
        tone=ctx.choice(obj, "tone", TONE_NAMES, default="none"),
        text_in=ctx.choice(obj, "text_in", TEXT_IN_NAMES, default="none"),
        sfx=_parse_sfx(ctx, obj, base, level),
        music_cut=_parse_music_cut(ctx, obj),
        living=ctx.bool_(obj, "living", default=False),
        particles=ctx.choice(obj, "particles", PARTICLE_NAMES, default="none"),
        auto_sfx=ctx.bool_(obj, "auto_sfx", default=True),
        actions=_parse_actions(ctx, obj),
    )


def _check_slide_ids(pairs: list[tuple[Ctx, Slide | None]]) -> None:
    """Narrated scripts need an explicit, unique ``id`` on every slide (A.1.2)."""
    slides = [(child, slide) for child, slide in pairs if slide is not None]
    any_narration = any(slide.narration is not None for _, slide in slides)
    seen: dict[str, int] = {}
    for position, (child, slide) in enumerate(slides, start=1):
        if any_narration and not slide.id:
            child.at("id").error("required when any slide has narration")
        if slide.id and slide.id in seen:
            child.at("id").error(f'duplicate id "{slide.id}" (also on slide {seen[slide.id]})')
        seen.setdefault(slide.id, position)


def _parse_slides(
    ctx: Ctx,
    obj: Mapping[str, Any],
    sources: tuple[Source, ...] | None,
    level: int,
    base: Path,
) -> tuple[Slide, ...]:
    slides_ctx = ctx.at("slides")
    if "slides" not in obj:
        slides_ctx.missing()
        return ()
    pairs = slides_ctx.items(obj["slides"])
    if isinstance(obj["slides"], list) and not MIN_SLIDES <= len(pairs) <= MAX_SLIDES:
        slides_ctx.error(f"must contain {MIN_SLIDES}–{MAX_SLIDES} slides")
    parsed = [(child, _parse_slide(child, raw, sources, level, base)) for child, raw in pairs]
    _check_slide_ids(parsed)
    if parsed and parsed[0][1] is not None and parsed[0][1].transition != "cut":
        parsed[0][0].at("transition").warning("the first slide has no previous slide (ignored)")
    return tuple(
        replace(slide, id=slide.id or f"s{index:02d}")
        for index, (_, slide) in enumerate(parsed, start=1)
        if slide is not None
    )


def _check_total_duration(ctx: Ctx, slides: tuple[Slide, ...]) -> None:
    total = sum(slide_duration(s, DEFAULT_FPS) for s in slides)
    if not MIN_TOTAL_SECONDS <= total <= MAX_TOTAL_SECONDS:
        ctx.at("slides").warning(
            f"total duration {total:.1f} s is outside {MIN_TOTAL_SECONDS:g}–{MAX_TOTAL_SECONDS:g} s"
        )


def _parse_script(ctx: Ctx, data: Mapping[str, Any], path: Path) -> Script:
    for key in data:
        if key not in _SCRIPT_KEYS:
            ctx.at(str(key)).warning("unknown key (ignored)")
    version = ctx.str_(data, "schema_version")
    if version and version not in SUPPORTED_SCHEMA_VERSIONS:
        expected = " or ".join(f'"{v}"' for v in SUPPORTED_SCHEMA_VERSIONS)
        ctx.at("schema_version").error(
            f'unsupported schema_version "{version}" (expected {expected})'
        )
    title = _text(ctx, data, "title", required=True)
    sources = _parse_sources(ctx, data)
    level = SCHEMA_LEVELS.get(version, 0)
    slides = _parse_slides(ctx, data, sources, level, path.parent)
    if not ctx.issues.errors:
        _check_total_duration(ctx, slides)
    return Script(version, title, sources or (), slides, path)


def load_script(path: Path) -> tuple[Script, list[Issue]]:
    """Load and validate a script file.

    Returns the script and its warnings. Raises ``ValidationFailed`` carrying every error.
    """
    issues = Issues()
    data = read_json_object(path, issues)
    if data is None:
        issues.raise_if_errors()
        raise AssertionError("unreachable")  # pragma: no cover
    script = _parse_script(Ctx(path.name, issues, terse=True), data, path.resolve())
    issues.raise_if_errors()
    return script, issues.warnings
