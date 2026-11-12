"""Scene, layer and character contracts (spec 6.3) and their parsers.

A slide's ``scene`` is either a template (``{"template": ...}``) or an explicit list of
layers (``{"layers": [...]}``). Everything here is pure data: the drawing code receives
these frozen dataclasses and never reads JSON.

Range rules (canvas pixels): layer ``x`` is 0-1080 and layer ``y`` is 0-1920; ``r``,
``scale``, ``height`` and ``width`` are positive; ``rings`` is 0-2; ``facing`` and ``flip``
are -1 or 1. Palette-key overrides on a character (``robe``, ``trim``, ...) are only
checked to be strings here; they are cross-checked against the theme later.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, fields
from typing import Any, Literal, TypeVar, cast

from history_shorts.validation import Ctx, is_int, is_number

CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920
DEFAULT_BASELINE = 1100.0
DEFAULT_RIVER_HEIGHT = 290.0
DEFAULT_GROUND_HEIGHT = 52.0

ROLE_NAMES: tuple[str, ...] = ("leader", "general", "general_alt", "boat_crew")
PROP_NAMES: tuple[str, ...] = ("flag", "spear", "oar", "none")
FORMATION_NAMES: tuple[str, ...] = ("centre_pair", "line", "v_shape")
TEMPLATE_NAMES: tuple[str, ...] = ("group", "landscape")
OUTLINE_NAMES: tuple[str, ...] = ("gold", "gold_dk")
FILL_NAMES: tuple[str, ...] = ("gradient", "eggshell")
SIDE_NAMES: tuple[str, ...] = ("left", "right")

T = TypeVar("T")

Prop = Literal["flag", "spear", "oar", "none"]
Formation = Literal["centre_pair", "line", "v_shape"]


# --------------------------------------------------------------------------------------
# Dataclasses
# --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CharacterSpec:
    """One character. ``None`` means "use the role preset" or "let the formation decide"."""

    role: str
    facing: int | None = None
    robe: str | None = None
    robe_dk: str | None = None
    trim: str | None = None
    wrap: str | None = None
    prop: Prop | None = None
    crest: bool | None = None
    x: float | None = None
    baseline: float | None = None
    height: float | None = None
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class CloudItem:
    x: float
    y: float
    scale: float
    flip: int


@dataclass(frozen=True, slots=True)
class PeakItem:
    x: float
    height: float
    width: float


@dataclass(frozen=True, slots=True)
class BirdItem:
    x: float
    y: float
    scale: float


@dataclass(frozen=True, slots=True)
class SunLayer:
    kind: Literal["sun", "moon"]
    x: float
    y: float
    r: float
    rings: int
    tile: int | None
    worn: float | None


@dataclass(frozen=True, slots=True)
class CloudsLayer:
    items: tuple[CloudItem, ...]
    outline: Literal["gold", "gold_dk"]
    cell: int | None
    gap: float | None


@dataclass(frozen=True, slots=True)
class MountainsLayer:
    y: float
    amp: float


@dataclass(frozen=True, slots=True)
class PeaksLayer:
    y: float
    items: tuple[PeakItem, ...]
    fill: Literal["gradient", "eggshell"]
    cell: int | None
    gap: float | None


@dataclass(frozen=True, slots=True)
class HillsLayer:
    side: Literal["left", "right"]
    base: float
    top: float
    cell: int | None
    gap: float | None


@dataclass(frozen=True, slots=True)
class RiverLayer:
    y: float
    height: float = DEFAULT_RIVER_HEIGHT


@dataclass(frozen=True, slots=True)
class GroundLayer:
    y: float
    height: float = DEFAULT_GROUND_HEIGHT


@dataclass(frozen=True, slots=True)
class CharactersLayer:
    """Characters placed by a ``formation`` or by explicit ``items``.

    Baseline precedence: an item's own ``baseline`` wins; an item without one uses this
    layer's ``baseline`` (default 1100); a formation may then override both for the
    characters it positions.
    """

    formation: Formation | None
    baseline: float = DEFAULT_BASELINE
    items: tuple[CharacterSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class BoatLayer:
    x: float
    y: float
    scale: float
    crew: tuple[CharacterSpec, ...]


@dataclass(frozen=True, slots=True)
class BirdsLayer:
    items: tuple[BirdItem, ...]


@dataclass(frozen=True, slots=True)
class LotusLayer:
    x: float
    y: float
    scale: float


@dataclass(frozen=True, slots=True)
class DrumLayer:
    """A bronze-drum face (backlog #1): centre, radius, birds in the ring, gold-leaf overrides."""

    x: float
    y: float
    r: float
    birds: int = 8
    tile: int | None = None
    worn: float | None = None


@dataclass(frozen=True, slots=True)
class GongLayer:
    """A gong in a wooden frame with its mallet (backlog #2): face centre and radius."""

    x: float
    y: float
    r: float
    tile: int | None = None


@dataclass(frozen=True, slots=True)
class MapLayer:
    """A delta map panel (backlog #4): its box in px, dots in map units (0-1), scattered dots,
    and an arrow from the north."""

    x: float
    y: float
    w: float
    h: float
    dots: tuple[tuple[float, float], ...] = ()
    scatter: int = 0
    arrow: bool = False


@dataclass(frozen=True, slots=True)
class ScrollLayer:
    """A half-unrolled scroll with ink marks and a brush (backlog #5): centre and scale."""

    x: float
    y: float
    scale: float


@dataclass(frozen=True, slots=True)
class ElephantLayer:
    """A war elephant, no rider (backlog #6): feet x and ground y, scale, facing, flag."""

    x: float
    y: float
    scale: float
    facing: int = 1
    flag: bool = True


@dataclass(frozen=True, slots=True)
class TempleLayer:
    """A temple gate (backlog #3): centre x, ground y, scale, optional incense burners."""

    x: float
    y: float
    scale: float
    incense: bool = True


Layer = (
    SunLayer
    | CloudsLayer
    | MountainsLayer
    | PeaksLayer
    | HillsLayer
    | RiverLayer
    | GroundLayer
    | CharactersLayer
    | BoatLayer
    | BirdsLayer
    | LotusLayer
    | DrumLayer
    | GongLayer
    | TempleLayer
    | MapLayer
    | ScrollLayer
    | ElephantLayer
)

# Layer ``type`` name -> class, in the order shown in error messages.
LAYER_TYPES: Mapping[str, type[Layer]] = {
    "sun": SunLayer,
    "moon": SunLayer,
    "clouds": CloudsLayer,
    "mountains": MountainsLayer,
    "peaks": PeaksLayer,
    "hills": HillsLayer,
    "river": RiverLayer,
    "ground": GroundLayer,
    "characters": CharactersLayer,
    "boat": BoatLayer,
    "birds": BirdsLayer,
    "lotus": LotusLayer,
    "drum": DrumLayer,
    "gong": GongLayer,
    "temple": TempleLayer,
    "map": MapLayer,
    "scroll": ScrollLayer,
    "elephant": ElephantLayer,
}


@dataclass(frozen=True, slots=True)
class LayerScene:
    layers: tuple[Layer, ...]


@dataclass(frozen=True, slots=True)
class TemplateScene:
    template: Literal["group", "landscape"]
    characters: tuple[CharacterSpec, ...] | None
    boats: tuple[BoatLayer, ...] | None
    sun: bool = True
    moon: bool = True
    seed: int | None = None


# --------------------------------------------------------------------------------------
# Readers
# --------------------------------------------------------------------------------------


def _keys(cls: type[Any]) -> tuple[str, ...]:
    """JSON keys of a layer class: its field names, with ``kind`` spelled ``type``."""
    return tuple("type" if f.name == "kind" else f.name for f in fields(cls))


def _object(ctx: Ctx, raw: object, allowed: Collection[str]) -> dict[str, Any] | None:
    """``raw`` as a dict with unknown-key warnings, or None (error recorded) if not an object."""
    if not isinstance(raw, dict):
        ctx.error("must be an object")
        return None
    return ctx.mapping(raw, allowed)


def _x(ctx: Ctx, obj: Mapping[str, Any], key: str = "x") -> float:
    return ctx.num(obj, key, lo=0, hi=CANVAS_WIDTH)


def _y(ctx: Ctx, obj: Mapping[str, Any], key: str = "y") -> float:
    return ctx.num(obj, key, lo=0, hi=CANVAS_HEIGHT)


def _scale(ctx: Ctx, obj: Mapping[str, Any]) -> float:
    return ctx.num(obj, "scale", default=1.0, positive=True)


def _opt_num(ctx: Ctx, obj: Mapping[str, Any], key: str, **kw: Any) -> float | None:
    return ctx.num(obj, key, **kw) if key in obj else None


def _opt_int(ctx: Ctx, obj: Mapping[str, Any], key: str, **kw: Any) -> int | None:
    return ctx.int_(obj, key, **kw) if key in obj else None


def _sign(ctx: Ctx, obj: Mapping[str, Any], key: str, default: int | None) -> int | None:
    """An optional -1 / 1 value."""
    if key not in obj:
        return default
    value = obj[key]
    if is_int(value) and value in (-1, 1):
        return int(value)
    ctx.at(key).error("must be -1 or 1")
    return default


def _opt_choice(ctx: Ctx, obj: Mapping[str, Any], key: str, allowed: tuple[str, ...]) -> str | None:
    return ctx.choice(obj, key, allowed) if key in obj else None


# --------------------------------------------------------------------------------------
# Characters
# --------------------------------------------------------------------------------------

_CHARACTER_KEYS = tuple(f.name for f in fields(CharacterSpec))


def parse_character(ctx: Ctx, raw: object) -> CharacterSpec:
    obj = _object(ctx, raw, _CHARACTER_KEYS)
    if obj is None:
        return CharacterSpec(role="")
    return CharacterSpec(
        role=ctx.choice(obj, "role", ROLE_NAMES),
        facing=_sign(ctx, obj, "facing", None),
        robe=ctx.str_(obj, "robe") if "robe" in obj else None,
        robe_dk=ctx.str_(obj, "robe_dk") if "robe_dk" in obj else None,
        trim=ctx.str_(obj, "trim") if "trim" in obj else None,
        wrap=ctx.str_(obj, "wrap") if "wrap" in obj else None,
        prop=cast("Prop | None", _opt_choice(ctx, obj, "prop", PROP_NAMES)),
        crest=ctx.bool_(obj, "crest") if "crest" in obj else None,
        x=_opt_num(ctx, obj, "x", lo=0, hi=CANVAS_WIDTH),
        baseline=_opt_num(ctx, obj, "baseline", lo=0, hi=CANVAS_HEIGHT),
        height=_opt_num(ctx, obj, "height", positive=True),
        seed=_opt_int(ctx, obj, "seed", lo=0),
    )


def _parse_characters(ctx: Ctx, value: object) -> tuple[CharacterSpec, ...]:
    return tuple(parse_character(c, v) for c, v in ctx.items(value))


# --------------------------------------------------------------------------------------
# Layers
# --------------------------------------------------------------------------------------


def _items(
    ctx: Ctx,
    obj: Mapping[str, Any],
    cls: type[T],
    parse: Callable[[Ctx, dict[str, Any]], T],
) -> tuple[T, ...]:
    """Parse the required ``items`` array of ``obj`` into ``cls`` records."""
    if "items" not in obj:
        ctx.at("items").missing()
        return ()
    out: list[T] = []
    for child, raw in ctx.at("items").items(obj["items"]):
        item = _object(child, raw, _keys(cls))
        if item is not None:
            out.append(parse(child, item))
    return tuple(out)


def _parse_cloud_item(ctx: Ctx, obj: dict[str, Any]) -> CloudItem:
    flip = _sign(ctx, obj, "flip", 1)
    return CloudItem(_x(ctx, obj), _y(ctx, obj), _scale(ctx, obj), 1 if flip is None else flip)


def _parse_peak_item(ctx: Ctx, obj: dict[str, Any]) -> PeakItem:
    return PeakItem(
        _x(ctx, obj), ctx.num(obj, "height", positive=True), ctx.num(obj, "width", positive=True)
    )


def _parse_bird_item(ctx: Ctx, obj: dict[str, Any]) -> BirdItem:
    return BirdItem(_x(ctx, obj), _y(ctx, obj), _scale(ctx, obj))


def _texture_overrides(ctx: Ctx, obj: Mapping[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    """Optional per-layer texture overrides: ``tile``/``worn`` or ``cell``/``gap``."""
    out: dict[str, Any] = dict.fromkeys(names)
    if "tile" in names:
        out["tile"] = _opt_int(ctx, obj, "tile", lo=1)
        out["worn"] = _opt_num(ctx, obj, "worn", lo=0, hi=1)
    else:
        out["cell"] = _opt_int(ctx, obj, "cell", lo=1)
        out["gap"] = _opt_num(ctx, obj, "gap", positive=True)
    return out


_GOLD = ("tile", "worn")
_EGG = ("cell", "gap")


def _parse_sun(kind: Literal["sun", "moon"]) -> Callable[[Ctx, dict[str, Any]], Layer]:
    def parse(ctx: Ctx, obj: dict[str, Any]) -> Layer:
        gold = _texture_overrides(ctx, obj, _GOLD)
        return SunLayer(
            kind=kind,
            x=_x(ctx, obj),
            y=_y(ctx, obj),
            r=ctx.num(obj, "r", positive=True),
            rings=ctx.int_(obj, "rings", default=0, lo=0, hi=2),
            tile=gold["tile"],
            worn=gold["worn"],
        )

    return parse


def _parse_clouds(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    egg = _texture_overrides(ctx, obj, _EGG)
    return CloudsLayer(
        items=_items(ctx, obj, CloudItem, _parse_cloud_item),
        outline=cast(
            "Literal['gold', 'gold_dk']", ctx.choice(obj, "outline", OUTLINE_NAMES, default="gold")
        ),
        cell=egg["cell"],
        gap=egg["gap"],
    )


def _parse_mountains(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return MountainsLayer(y=_y(ctx, obj), amp=ctx.num(obj, "amp", positive=True))


def _parse_peaks(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    fill = ctx.choice(obj, "fill", FILL_NAMES, default="gradient")
    egg = _texture_overrides(ctx, obj, _EGG)
    if fill != "eggshell":
        for key in _EGG:
            if key in obj:
                ctx.at(key).warning("only used with fill eggshell (ignored)")
    return PeaksLayer(
        y=_y(ctx, obj),
        items=_items(ctx, obj, PeakItem, _parse_peak_item),
        fill=cast("Literal['gradient', 'eggshell']", fill),
        cell=egg["cell"],
        gap=egg["gap"],
    )


def _parse_hills(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    egg = _texture_overrides(ctx, obj, _EGG)
    return HillsLayer(
        side=cast("Literal['left', 'right']", ctx.choice(obj, "side", SIDE_NAMES)),
        base=_y(ctx, obj, "base"),
        top=_y(ctx, obj, "top"),
        cell=egg["cell"],
        gap=egg["gap"],
    )


def _parse_river(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    height = ctx.num(obj, "height", default=DEFAULT_RIVER_HEIGHT, positive=True)
    return RiverLayer(y=_y(ctx, obj), height=height)


def _parse_ground(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    height = ctx.num(obj, "height", default=DEFAULT_GROUND_HEIGHT, positive=True)
    return GroundLayer(y=_y(ctx, obj), height=height)


def _parse_characters_layer(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    formation = _opt_choice(ctx, obj, "formation", FORMATION_NAMES)
    items = _parse_characters(ctx.at("items"), obj["items"]) if "items" in obj else ()
    if formation is None and "items" not in obj:
        ctx.error("needs 'formation' or 'items'")
    return CharactersLayer(
        formation=cast("Formation | None", formation),
        items=items,
        baseline=ctx.num(obj, "baseline", default=DEFAULT_BASELINE, lo=0, hi=CANVAS_HEIGHT),
    )


def parse_boat(ctx: Ctx, obj: dict[str, Any]) -> BoatLayer:
    crew = _parse_characters(ctx.at("crew"), obj["crew"]) if "crew" in obj else ()
    return BoatLayer(x=_x(ctx, obj), y=_y(ctx, obj), scale=_scale(ctx, obj), crew=crew)


def _parse_birds(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return BirdsLayer(items=_items(ctx, obj, BirdItem, _parse_bird_item))


def _parse_lotus(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return LotusLayer(x=_x(ctx, obj), y=_y(ctx, obj), scale=_scale(ctx, obj))


DRUM_BIRDS: tuple[int, int] = (0, 16)


MAP_SCATTER_MAX = 80


def _map_dot(ctx: Ctx, raw: object) -> tuple[float, float] | None:
    if not isinstance(raw, list) or len(raw) != 2 or not all(is_number(v) for v in raw):
        ctx.error("must be [u, v], two numbers")
        return None
    u, v = float(raw[0]), float(raw[1])
    if not (0 <= u <= 1 and 0 <= v <= 1):
        ctx.error("must be inside the map, 0–1")
        return None
    return u, v


def _parse_map(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    dots = [_map_dot(c, raw) for c, raw in ctx.at("dots").items(obj.get("dots", []))]
    return MapLayer(
        x=_x(ctx, obj),
        y=_y(ctx, obj),
        w=ctx.num(obj, "w", positive=True, hi=CANVAS_WIDTH),
        h=ctx.num(obj, "h", positive=True, hi=CANVAS_HEIGHT),
        dots=tuple(d for d in dots if d is not None),
        scatter=ctx.int_(obj, "scatter", default=0, lo=0, hi=MAP_SCATTER_MAX),
        arrow=ctx.bool_(obj, "arrow", default=False),
    )


def _parse_scroll(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return ScrollLayer(x=_x(ctx, obj), y=_y(ctx, obj), scale=_scale(ctx, obj))


def _parse_elephant(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return ElephantLayer(
        x=_x(ctx, obj),
        y=_y(ctx, obj),
        scale=_scale(ctx, obj),
        facing=_sign(ctx, obj, "facing", 1) or 1,
        flag=ctx.bool_(obj, "flag", default=True),
    )


def _parse_temple(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return TempleLayer(
        x=_x(ctx, obj),
        y=_y(ctx, obj),
        scale=_scale(ctx, obj),
        incense=ctx.bool_(obj, "incense", default=True),
    )


def _parse_gong(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    return GongLayer(
        x=_x(ctx, obj),
        y=_y(ctx, obj),
        r=ctx.num(obj, "r", positive=True),
        tile=ctx.int_(obj, "tile", lo=1) if "tile" in obj else None,
    )


def _parse_drum(ctx: Ctx, obj: dict[str, Any]) -> Layer:
    gold = _texture_overrides(ctx, obj, _GOLD)
    return DrumLayer(
        x=_x(ctx, obj),
        y=_y(ctx, obj),
        r=ctx.num(obj, "r", positive=True),
        birds=ctx.int_(obj, "birds", default=8, lo=DRUM_BIRDS[0], hi=DRUM_BIRDS[1]),
        tile=gold["tile"],
        worn=gold["worn"],
    )


_LAYER_PARSERS: dict[str, Callable[[Ctx, dict[str, Any]], Layer]] = {
    "sun": _parse_sun("sun"),
    "moon": _parse_sun("moon"),
    "clouds": _parse_clouds,
    "mountains": _parse_mountains,
    "peaks": _parse_peaks,
    "hills": _parse_hills,
    "river": _parse_river,
    "ground": _parse_ground,
    "characters": _parse_characters_layer,
    "boat": parse_boat,
    "birds": _parse_birds,
    "lotus": _parse_lotus,
    "drum": _parse_drum,
    "gong": _parse_gong,
    "temple": _parse_temple,
    "map": _parse_map,
    "scroll": _parse_scroll,
    "elephant": _parse_elephant,
}


def _parse_layer(ctx: Ctx, raw: object) -> Layer | None:
    if not isinstance(raw, dict):
        ctx.error("must be an object")
        return None
    if "type" not in raw:
        ctx.at("type").missing()
        return None
    kind = raw["type"]
    if not isinstance(kind, str) or kind not in _LAYER_PARSERS:
        allowed = ", ".join(LAYER_TYPES)
        ctx.at("type").error(f'unknown layer type "{kind}"; allowed: {allowed}')
        return None
    obj = ctx.mapping(raw, {*_keys(LAYER_TYPES[kind]), "type"})
    return _LAYER_PARSERS[kind](ctx, obj)


# --------------------------------------------------------------------------------------
# Scenes
# --------------------------------------------------------------------------------------

_TEMPLATE_KEYS = ("template", "characters", "boats", "sun", "moon", "seed")


def _parse_template(ctx: Ctx, obj: dict[str, Any]) -> TemplateScene:
    template = ctx.choice(obj, "template", TEMPLATE_NAMES)
    unused = {"group": "boats", "landscape": "characters"}.get(template)
    if unused in obj:
        ctx.at(str(unused)).warning(f"not used by template {template} (ignored)")
    characters = (
        _parse_characters(ctx.at("characters"), obj["characters"]) if "characters" in obj else None
    )
    boats: tuple[BoatLayer, ...] | None = None
    if "boats" in obj:
        boats_ctx = ctx.at("boats")
        parsed: list[BoatLayer] = []
        for child, raw in boats_ctx.items(obj["boats"]):
            boat = _object(child, raw, _keys(BoatLayer))
            if boat is not None:
                parsed.append(parse_boat(child, boat))
        boats = tuple(parsed)
    return TemplateScene(
        template=cast("Literal['group', 'landscape']", template),
        characters=characters,
        boats=boats,
        sun=ctx.bool_(obj, "sun", default=True),
        moon=ctx.bool_(obj, "moon", default=True),
        seed=_opt_int(ctx, obj, "seed", lo=0),
    )


def _parse_layer_scene(ctx: Ctx, obj: dict[str, Any]) -> LayerScene:
    layers: list[Layer] = []
    for child, raw in ctx.at("layers").items(obj["layers"], non_empty=True):
        layer = _parse_layer(child, raw)
        if layer is not None:
            layers.append(layer)
    return LayerScene(layers=tuple(layers))


def parse_scene(ctx: Ctx, raw: object) -> LayerScene | TemplateScene | None:
    """Parse a slide's ``scene`` value; None if it is malformed (error recorded)."""
    if not isinstance(raw, dict):
        ctx.error("must be an object")
        return None
    has_template, has_layers = "template" in raw, "layers" in raw
    if has_template and has_layers:
        ctx.error("give either 'template' or 'layers', not both")
        return None
    if has_template:
        return _parse_template(ctx, ctx.mapping(raw, _TEMPLATE_KEYS))
    if has_layers:
        return _parse_layer_scene(ctx, ctx.mapping(raw, ("layers",)))
    ctx.error("needs 'template' or 'layers'")
    return None
