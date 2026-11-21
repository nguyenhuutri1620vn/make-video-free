"""Load and validate artwork files, and the per-theme artwork library (M11)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal, cast

from history_shorts.artwork.model import (
    Artwork,
    Fill,
    Gradient,
    Motion,
    MotionKind,
    Part,
    Solid,
    Stroke,
    Texture,
    TextureKind,
)
from history_shorts.artwork.path import Op, PathError, count_numbers, parse_path
from history_shorts.config import Palette, Theme
from history_shorts.errors import Issue, Issues
from history_shorts.scene_config import DEPTH_NAMES, Depth
from history_shorts.validation import Ctx, read_json_object

FORMAT_VERSION: Final = "1"
NAME_RE: Final = re.compile(r"[a-z0-9_]{1,40}")
MAX_PARTS: Final = 300
MAX_NUMBERS: Final = 20_000
MAX_COORD: Final = 2000.0
STROKE_WIDTH: Final = (0.2, 20.0)
STOPS: Final = (2, 6)
MOTION_KINDS: Final[tuple[MotionKind, ...]] = ("flicker", "wave", "sway", "rise", "pulse")
TEXTURE_KINDS: Final[tuple[TextureKind, ...]] = ("gold_leaf", "eggshell")
GEOMETRY_KEYS: Final = ("d", "ellipse", "rect")
_PART_KEYS: Final = ("id", *GEOMETRY_KEYS, "fill", "stroke", "alpha", "clip", "motion")
_FILE_KEYS: Final = ("artwork", "title", "description", "plane", "parts")
KAPPA: Final = 0.5522847498  # cubic approximation of a quarter ellipse


def _ellipse_ops(cx: float, cy: float, rx: float, ry: float) -> tuple[Op, ...]:
    kx, ky = rx * KAPPA, ry * KAPPA
    return (
        ("M", (cx + rx, cy)),
        ("C", (cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry)),
        ("C", (cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy)),
        ("C", (cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry)),
        ("C", (cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy)),
        ("Z", ()),
    )


def _rect_ops(x: float, y: float, w: float, h: float, r: float) -> tuple[Op, ...]:
    r = min(max(r, 0.0), w / 2, h / 2)
    if r == 0:
        return (
            ("M", (x, y)),
            ("L", (x + w, y)),
            ("L", (x + w, y + h)),
            ("L", (x, y + h)),
            ("Z", ()),
        )
    k = r * (1 - KAPPA)
    return (
        ("M", (x + r, y)),
        ("L", (x + w - r, y)),
        ("C", (x + w - k, y, x + w, y + k, x + w, y + r)),
        ("L", (x + w, y + h - r)),
        ("C", (x + w, y + h - k, x + w - k, y + h, x + w - r, y + h)),
        ("L", (x + r, y + h)),
        ("C", (x + k, y + h, x, y + h - k, x, y + h - r)),
        ("L", (x, y + r)),
        ("C", (x, y + k, x + k, y, x + r, y)),
        ("Z", ()),
    )


def _numbers(ctx: Ctx, obj: Mapping[str, Any], key: str, sizes: tuple[int, ...]) -> list[float]:
    value = obj[key]
    ok = isinstance(value, list) and len(value) in sizes
    ok = ok and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
    if not ok:
        ctx.at(key).error(f"must be a list of {' or '.join(map(str, sizes))} numbers")
        return []
    return [float(v) for v in value]


class _Budget:
    def __init__(self) -> None:
        self.numbers = 0


def _geometry(ctx: Ctx, obj: Mapping[str, Any], budget: _Budget) -> tuple[Op, ...]:
    present = [k for k in GEOMETRY_KEYS if k in obj]
    if len(present) != 1:
        ctx.error("needs exactly one of d, ellipse, rect")
        return ()
    key = present[0]
    if key == "d":
        d = ctx.str_(obj, "d")
        try:
            budget.numbers += count_numbers(d)
            ops = parse_path(d)
        except PathError as exc:
            ctx.at("d").error(str(exc))
            return ()
    elif key == "ellipse":
        n = _numbers(ctx, obj, "ellipse", (4,))
        ops = _ellipse_ops(*n) if n else ()
        budget.numbers += 4
    else:
        n = _numbers(ctx, obj, "rect", (4, 5))
        ops = _rect_ops(n[0], n[1], n[2], n[3], n[4] if len(n) == 5 else 0.0) if n else ()
        budget.numbers += len(n)
    if any(abs(v) > MAX_COORD for _, values in ops for v in values):
        ctx.at(key).error(f"coordinates must be within ±{MAX_COORD:g}")
    return ops


def _palette_key(ctx: Ctx, value: object, palette: Palette) -> str:
    if not isinstance(value, str) or value not in palette.keys():
        ctx.error(f"unknown palette key '{value}'")
        return ""
    return value


def _stops(
    ctx: Ctx, obj: Mapping[str, Any], palette: Palette
) -> tuple[tuple[str, float, float], ...]:
    sc = ctx.at("stops")
    raw = obj["stops"]
    if not isinstance(raw, list) or not STOPS[0] <= len(raw) <= STOPS[1]:
        sc.error(f"must hold {STOPS[0]} to {STOPS[1]} stops")
        return ()
    out: list[tuple[str, float, float]] = []
    for k, stop in enumerate(raw):
        here = sc.idx(k)
        if not (isinstance(stop, list) and len(stop) == 3):
            here.error("must be [palette key, alpha, offset]")
            continue
        key = _palette_key(here, stop[0], palette)
        alpha, offset = stop[1], stop[2]
        numeric = all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in (alpha, offset)
        )
        if not numeric or not all(0 <= v <= 1 for v in (alpha, offset)):
            here.error("alpha and offset must be 0 to 1")
            continue
        out.append((key, float(alpha), float(offset)))
    offsets = [s[2] for s in out]
    if len(out) == len(raw) and (offsets != sorted(offsets) or offsets[0] != 0 or offsets[-1] != 1):
        sc.error("offsets must rise from 0 to 1")
    return tuple(out)


FILL_KINDS: Final = ("color", "gradient", "stops", "texture")
FILL_KEYS: Final[Mapping[str, tuple[str, ...]]] = {
    "color": ("color", "alpha"),
    "gradient": ("gradient", "dir", "radial"),
    "stops": ("stops", "dir", "radial"),
    "texture": ("texture", "tile", "worn", "cell", "gap"),
}


def _fill_kind(ctx: Ctx, obj: Mapping[str, Any]) -> str | None:
    """The one fill kind ``obj`` gives; every other key must belong to that kind."""
    kinds = [k for k in FILL_KINDS if k in obj]
    if len(kinds) != 1:
        ctx.error(f"give one of {', '.join(FILL_KINDS)}")
        return None
    kind = kinds[0]
    for key in obj:
        if key not in FILL_KEYS[kind]:
            ctx.at(key).error(f"'{key}' does not apply to a {kind} fill")
    return kind


def _radial(ctx: Ctx, obj: Mapping[str, Any]) -> tuple[float, float, float] | None:
    if "radial" not in obj:
        return None
    n = _numbers(ctx, obj, "radial", (3,))
    if not n:
        return None
    if n[2] <= 0:
        ctx.at("radial").error("radius must be > 0")
        return None
    return (n[0], n[1], n[2])


def _fill(ctx: Ctx, raw: object, palette: Palette) -> Fill | None:
    obj = ctx.mapping(raw, tuple(k for keys in FILL_KEYS.values() for k in keys))
    if not obj:
        return None
    kind = _fill_kind(ctx, obj)
    if kind == "texture":
        texture = cast(TextureKind, ctx.choice(obj, "texture", TEXTURE_KINDS))
        opt = {k: ctx.num(obj, k, positive=True) if k in obj else None for k in ("tile", "cell")}
        worn = ctx.num(obj, "worn", lo=0, hi=1) if "worn" in obj else None
        gap = ctx.num(obj, "gap", lo=0, hi=10) if "gap" in obj else None
        return Texture(texture, opt["tile"], worn, opt["cell"], gap)
    if kind in ("gradient", "stops"):
        radial = _radial(ctx, obj)
        direction = cast(Literal["v", "h"], ctx.choice(obj, "dir", ("v", "h"), default="v"))
        if kind == "stops":
            return Gradient(_stops(ctx, obj, palette), None if radial else direction, radial)
        pair = obj["gradient"]
        gc = ctx.at("gradient")
        if not (isinstance(pair, list) and len(pair) == 2):
            gc.error("must be [palette key, palette key]")
            return None
        a, b = (_palette_key(gc.idx(k), pair[k], palette) for k in (0, 1))
        return Gradient(((a, 1.0, 0.0), (b, 1.0, 1.0)), None if radial else direction, radial)
    if kind == "color":
        color = _palette_key(ctx.at("color"), obj.get("color"), palette)
        return Solid(color, ctx.num(obj, "alpha", default=1.0, lo=0, hi=1))
    return None


def _stroke(ctx: Ctx, raw: object, palette: Palette) -> Stroke | None:
    obj = ctx.mapping(raw, ("color", "width", "alpha"))
    if not obj:
        return None
    color = _palette_key(ctx.at("color"), obj.get("color"), palette)
    lo, hi = STROKE_WIDTH
    width = ctx.num(obj, "width", default=1.0, lo=lo, hi=hi)
    return Stroke(color, width, ctx.num(obj, "alpha", default=1.0, lo=0, hi=1))


def _motion(ctx: Ctx, raw: object) -> Motion | None:
    obj = ctx.mapping(raw, ("kind", "amp", "deg", "pole", "pivot"))
    if not obj:
        return None
    kind = cast(MotionKind, ctx.choice(obj, "kind", MOTION_KINDS))
    amp_hi = {"wave": 0.5, "pulse": 0.5}.get(kind, 200.0)
    amp = ctx.num(obj, "amp", default=0.0, lo=0, hi=amp_hi)
    deg = ctx.num(obj, "deg", default=0.0, lo=0, hi=45)
    pole, pivot = 0.0, (0.0, 0.0)
    if kind == "wave":
        if "pole" not in obj:
            ctx.at("pole").missing()
        pole = ctx.num(obj, "pole", default=0.0, lo=-MAX_COORD, hi=MAX_COORD)
    if kind == "sway":
        if "pivot" not in obj:
            ctx.at("pivot").missing()
        else:
            n = _numbers(ctx, obj, "pivot", (2,))
            pivot = (n[0], n[1]) if n else pivot
    return Motion(kind, amp, deg, pole, pivot)


def _part(ctx: Ctx, raw: object, palette: Palette, budget: _Budget) -> Part | None:
    obj = ctx.mapping(raw, _PART_KEYS)
    if not obj:
        return None
    pid = ctx.str_(obj, "id")
    ops = _geometry(ctx, obj, budget)
    fill = _fill(ctx.at("fill"), obj["fill"], palette) if "fill" in obj else None
    stroke = _stroke(ctx.at("stroke"), obj["stroke"], palette) if "stroke" in obj else None
    alpha = ctx.num(obj, "alpha", default=1.0, lo=0, hi=1)
    clip = ctx.str_(obj, "clip") if "clip" in obj else None
    motion = _motion(ctx.at("motion"), obj["motion"]) if "motion" in obj else None
    return Part(pid, ops, fill, stroke, alpha, clip, motion)


def _check_links(ctx: Ctx, parts: list[tuple[Ctx, Part]]) -> None:
    """Duplicate ids, clip targets, and which parts may move or carry a texture."""
    seen: dict[str, Part] = {}
    for pc, part in parts:
        if part.id in seen:
            pc.at("id").error(f"duplicate part id '{part.id}'")
        textured = isinstance(part.fill, Texture)
        target = seen.get(part.clip) if part.clip is not None else None
        if part.clip is not None and target is None:
            pc.at("clip").error("must name an earlier part")
        if part.motion is not None and textured:
            pc.at("motion").error("a textured part cannot move")
        elif part.motion is not None and target is not None and isinstance(target.fill, Texture):
            pc.at("motion").error(f"a part clipped to textured part '{target.id}' cannot move")
        if textured and target is not None and target.motion is not None:
            pc.at("fill").error(f"a part clipped to moving part '{target.id}' cannot be textured")
        seen.setdefault(part.id, part)


def _parse(ctx: Ctx, data: Mapping[str, Any], name: str, palette: Palette) -> Artwork:
    obj = ctx.mapping(data, _FILE_KEYS)
    version = obj.get("artwork")
    if version != FORMAT_VERSION:
        ctx.at("artwork").error(f'must be "{FORMAT_VERSION}"')
    title = ctx.str_(obj, "title", default=name)
    plane = cast(Depth, ctx.choice(obj, "plane", DEPTH_NAMES, default="mid"))
    budget = _Budget()
    pairs = ctx.at("parts").items(obj.get("parts"), non_empty=True)
    if len(pairs) > MAX_PARTS:
        ctx.at("parts").error(f"must hold at most {MAX_PARTS} parts")
    parsed = [(pc, _part(pc, raw, palette, budget)) for pc, raw in pairs]
    parts = [(pc, p) for pc, p in parsed if p is not None]
    if budget.numbers > MAX_NUMBERS:
        ctx.at("parts").error(f"must hold at most {MAX_NUMBERS} path numbers")
    _check_links(ctx, parts)
    return Artwork(name, title, plane, tuple(p for _, p in parts))


def load_artwork(path: Path, palette: Palette) -> tuple[Artwork, list[Issue]]:
    """Load and validate one artwork file; raises ``ValidationFailed`` with every error."""
    issues = Issues()
    data = read_json_object(path, issues)
    if data is None:
        issues.raise_if_errors()
        raise AssertionError("unreachable")  # pragma: no cover
    art = _parse(Ctx(f"artwork/{path.name}", issues, terse=True), data, path.stem, palette)
    issues.raise_if_errors()
    return art, issues.warnings


class ArtworkLibrary:
    """Artwork files in one directory, loaded on demand and reloaded when they change."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._cache: dict[str, tuple[tuple[int, int], Artwork]] = {}

    def names(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(p.stem for p in self.directory.glob("*.json") if NAME_RE.fullmatch(p.stem))

    def path(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def get(self, name: str, palette: Palette) -> Artwork:
        """The parsed file ``name``; raises ``ValidationFailed`` or ``FileNotFoundError``."""
        path = self.path(name)
        stat = path.stat()
        key = (stat.st_mtime_ns, stat.st_size)
        hit = self._cache.get(name)
        if hit is not None and hit[0] == key:
            return hit[1]
        art, _ = load_artwork(path, palette)
        self._cache[name] = (key, art)
        return art


_LIBRARIES: dict[Path, ArtworkLibrary] = {}


def library_for(theme: Theme) -> ArtworkLibrary:
    """The artwork library next to the theme file (one instance per directory)."""
    directory = (theme.path.parent / "artwork").resolve()
    if directory not in _LIBRARIES:
        _LIBRARIES[directory] = ArtworkLibrary(directory)
    return _LIBRARIES[directory]
