"""Kit ``warrior_male``: Đại Việt and northern-army men, tenth to fourteenth century (M12).

Owner-approved look: ``docs/reference/approved/warrior_male_roles.png`` and
``warrior_male_faces.png``; the numbers come from ``docs/reference/prototype/
warrior_male_proto.py``. Local frame as every kit: feet at (0, 0), 100 units tall, y up
negative. Parts have the kit signature ``(cv, style, palette)``; the headwear and body parts
pick a variant from ``style.variant`` (slots ``helmet`` and ``body``). Both sides share one
male face; they differ only in headwear, armour, colours and banners.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from history_shorts.canvas import Canvas
from history_shorts.characters.kits import ancient_female as af
from history_shorts.characters.kits.base import Kit, KitExtents, PartFn
from history_shorts.config import Palette
from history_shorts.primitives import RGB, Point

if TYPE_CHECKING:
    from history_shorts.characters.roles import CharacterStyle

# Proportions (local units), from the prototype.
HAND_CENTER: Final[Point] = (19.0, -58.0)
SHOULDER_Y: Final = -77.0
SHOULDER_HALF: Final = 13.0
WAIST_Y: Final = -52.0
HEAD_CENTER_Y: Final = -88.5
CHIN_Y: Final = -81.8
HEAD_HALF_WIDTH: Final = 12.0  # the northern neck guard is the widest headwear
HEAD_TOP: Final = -106.0  # the northern helmet's point
CREST_TOP: Final = -113.0  # plume or tassel tip
BODY_HALF_WIDTH: Final = 25.0  # the cape
BODY_TOP: Final = -83.0
BODY_BOTTOM: Final = 1.0
FLAG_TOP: Final = -138.0
SPEAR_TOP: Final = -134.0
SHAFT_BOTTOM: Final = 1.0
OUTLINE: Final = "gold"
OUTLINE_WIDTH: Final = 0.55
LAMELLAR_ROWS: Final = 16
LAMELLAR_STEP: Final = (3.2, 4.0)  # plate pitch x, y
LAMELLAR_TOP: Final = -78.0
SWORD_ANCHOR: Final[Point] = (9.0, -50.0)
SWORD_TILT: Final = -24.0  # degrees
SHIELD: Final = (-20.0, -50.0, 13.0)  # centre x, y, radius on the far forearm
DEFAULT_HELMET: Final = "topknot_wrap"
DEFAULT_BODY: Final = "tunic"
PROPS: Final = frozenset({"flag", "spear", "sword_sheathed", "shield", "none"})
HELD: Final = frozenset({"flag", "spear"})  # props gripped in the near hand
PROP_EXTENT: Final[dict[str, tuple[float, float, float, float]]] = {
    "flag": (17.5, -141.0, 53.0, 1.0),
    "spear": (17.0, -146.0, 21.0, 1.0),
    "sword_sheathed": (5.0, -58.0, 24.0, -20.0),
    "shield": (-33.5, -63.5, -6.5, -36.5),
}


def _c(palette: Palette, key: str) -> RGB:
    return palette[key]


def _grad(cv: Canvas, y0: float, y1: float, top: RGB, bottom: RGB) -> Canvas:
    return cv.vgrad(y0, y1, [(0, top, 1), (1, bottom, 1)])


def _robe_dk(style: CharacterStyle) -> RGB:
    return style.robe_dk


def _armour(style: CharacterStyle, palette: Palette) -> RGB:
    return style.armour or palette["gold_dk"]


def _body_kind(style: CharacterStyle) -> str:
    return style.variant.get("body", DEFAULT_BODY)


def _plated(style: CharacterStyle) -> bool:
    return _body_kind(style).startswith("lamellar")


def shaft_segment(prop: str) -> tuple[Point, Point] | None:
    x = HAND_CENTER[0]
    if prop == "flag":
        return ((x, FLAG_TOP), (x, SHAFT_BOTTOM))
    if prop == "spear":
        return ((x, SPEAR_TOP), (x, SHAFT_BOTTOM))
    return None


# --------------------------------------------------------------------------------------
# Back: cape, prop behind the body, legs
# --------------------------------------------------------------------------------------


def cape(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if not _body_kind(style).endswith("cape"):
        return
    cv.M(-14, -79).C(-20, -60, -24, -35, -25, -12).C(-10, -9, 10, -9, 25, -12)
    cv.C(24, -35, 20, -60, 14, -79).Z()
    _grad(cv, -80, -10, style.robe, style.robe_dk).fill(keep=True)
    cv.color(style.trim).stroke(0.8)


def _flag_cloth(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    x = HAND_CENTER[0]
    cv.M(x, -137).C(x + 11, -136, x + 21, -133, x + 33, -129)
    cv.C(x + 28, -126, x + 25, -123, x + 30, -118).C(x + 20, -118, x + 10, -114, x, -109).Z()
    cv.color(style.banner or palette["vermilion"]).fill(keep=True)
    cv.color(palette["gold"]).stroke(0.7)
    cv.color(palette["gold"]).ellipse(x, -139.5, 1.5, 1.5).fill()


def _spear_head(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    x = HAND_CENTER[0]
    cv.color(palette["gold"]).M(x, -146).C(x + 1.9, -141, x + 1.9, -138, x, -135)
    cv.C(x - 1.9, -138, x - 1.9, -141, x, -146).Z().fill()
    cv.color(style.banner or palette["vermilion"]).M(x, -134).C(
        x + 2.5, -131, x + 2.2, -127, x + 1, -123
    )
    cv.C(x + 0.4, -126, x - 0.8, -128, x - 1.4, -130).Z().fill()


def prop_back(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    segment = shaft_segment(style.prop)
    if segment is None:
        return
    (x0, y0), (x1, y1) = segment
    cv.color(palette["gold_dk"]).M(x0, y0).L(x1, y1).stroke(0.9)
    if style.prop == "flag":
        _flag_cloth(cv, style, palette)
    else:
        _spear_head(cv, style, palette)


def legs(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    for s in (-1, 1):
        cv.M(s * 2, -18).L(s * 10, -18).L(s * 9, -5).L(s * 3, -5).Z()
        _grad(cv, -18, -5, palette["brown_lt"], palette["brown"]).fill(keep=True)
        cv.color(palette[OUTLINE]).stroke(OUTLINE_WIDTH)
        cv.M(s * 2.5, -5.5).L(s * 9.5, -5.5).C(s * 11, -3, s * 11.5, 0, s * 9, 0)
        cv.L(s * 2.5, 0).Z()
        cv.color(palette["black"]).fill(keep=True)
        cv.color(palette["gold_dk"]).stroke(0.4)


# --------------------------------------------------------------------------------------
# Body
# --------------------------------------------------------------------------------------


def torso_path(cv: Canvas) -> None:
    cv.M(-14, -79).C(-16, -70, -14, -60, -12, -52).C(-15, -40, -18, -28, -19, -16)
    cv.C(-8, -13, 8, -13, 19, -16).C(18, -28, 15, -40, 12, -52)
    cv.C(14, -60, 16, -70, 14, -79).C(8, -83, -8, -83, -14, -79).Z()


def _lamellar(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    px, py = LAMELLAR_STEP
    cv.save()
    torso_path(cv)
    cv.clip()
    for k in range(LAMELLAR_ROWS):
        y = LAMELLAR_TOP + k * py
        x = -20.0 + (1.5 if k % 2 else 0.0)
        while x < 20:
            cv.M(x, y).L(x + 3, y).L(x + 3, y + 3.2).C(x + 3, y + 4.2, x, y + 4.2, x, y + 3.2).Z()
            x += px
    cv.color(_armour(style, palette)).fill()
    for k in range(LAMELLAR_ROWS):
        y = LAMELLAR_TOP + k * py + 3.6
        cv.M(-20, y).L(20, y)
    cv.color(style.trim, 0.7).stroke(0.35)
    cv.restore()


def body(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Tunic or lamellar over the torso, outline, collar."""
    torso_path(cv)
    _grad(cv, -82, -14, style.robe, style.robe_dk).fill()
    if _plated(style):
        _lamellar(cv, style, palette)
    torso_path(cv)
    cv.color(palette[OUTLINE]).stroke(OUTLINE_WIDTH)
    cv.color(style.trim).M(-5, -81).L(0, -74).L(5, -81).stroke(1.2)


def belt(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(style.trim).M(-12.3, -54).C(-4, -52.6, 4, -52.6, 12.3, -54).L(12.2, -50.5)
    cv.C(4, -49.2, -4, -49.2, -12.2, -50.5).Z().fill()
    cv.color(style.banner or palette["vermilion"]).ellipse(0, -51.8, 1.6, 1.3).fill()


def sword(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """A sword in its scabbard, hanging at the near hip; never drawn out."""
    if style.prop != "sword_sheathed":
        return
    cv.save()
    cv.translate(*SWORD_ANCHOR)
    cv.rotate(math.radians(SWORD_TILT))
    cv.rect(-1.6, 0, 3.2, 30)
    _grad(cv, 0, 30, palette["brown_lt"], palette["brown"]).fill(keep=True)
    cv.color(palette["gold_dk"]).stroke(0.5)
    cv.color(palette["gold"]).rect(-3.2, -1.6, 6.4, 1.6).fill()
    cv.color(palette["brown"]).rect(-1, -7, 2, 5.4).fill()
    cv.color(palette["gold"]).ellipse(0, -7.6, 1.4, 1.2).fill()
    cv.restore()


# --------------------------------------------------------------------------------------
# Arms, shield, hand
# --------------------------------------------------------------------------------------


def hanging_arm_path(cv: Canvas) -> None:
    """The near hanging sleeve; the far one is its mirror."""
    cv.M(12, -79).C(19, -72, 22.5, -60, 22, -46).C(19.5, -43, 14, -43, 11.5, -46)
    cv.C(11.5, -58, 10.5, -68, 9, -74).Z()


def holding_arm_path(cv: Canvas) -> None:
    cv.M(12, -79).C(19, -74, 22.5, -66, 21.5, -59).C(19.5, -55.5, 15.5, -55.5, 13.5, -58)
    cv.C(13.3, -64, 12.3, -71, 10.5, -75).Z()


def shoulder_guard(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if not _plated(style):
        return
    cv.M(10, -80).C(16, -80, 21, -74, 21, -68).C(17, -69, 13, -71, 10, -74).Z()
    cv.color(_armour(style, palette)).fill(keep=True)
    cv.color(style.trim).stroke(0.5)


def paint_hanging(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    hanging_arm_path(cv)
    _grad(cv, -79, -43, style.robe, style.robe_dk).fill(keep=True)
    cv.color(palette[OUTLINE]).stroke(OUTLINE_WIDTH)
    cv.color(style.trim).M(22, -46).C(19.5, -43.2, 14, -43.2, 11.5, -46).stroke(1.3)
    shoulder_guard(cv, style, palette)


def far_sleeve(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.save()
    cv.scale(-1, 1)  # mirroring only through scale(-1, 1)
    paint_hanging(cv, style, palette)
    cv.restore()


def shield(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if style.prop != "shield":
        return
    cx, cy, r = SHIELD
    cv.ellipse(cx, cy, r, r)
    _grad(cv, cy - r, cy + r, style.robe, style.robe_dk).fill(keep=True)
    cv.color(style.trim).stroke(1.0)
    cv.color(_armour(style, palette)).ellipse(cx, cy, r * 0.73, r * 0.73).stroke(0.8)
    cv.color(palette["gold"]).ellipse(cx, cy, 2.6, 2.6).fill()


def near_sleeve(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if style.prop not in HELD:
        paint_hanging(cv, style, palette)
        return
    holding_arm_path(cv)
    _grad(cv, -79, -55, style.robe, style.robe_dk).fill(keep=True)
    cv.color(palette[OUTLINE]).stroke(OUTLINE_WIDTH)
    cv.color(style.trim).M(21.5, -59).C(19.5, -55.8, 15.5, -55.8, 13.5, -58).stroke(1.3)
    shoulder_guard(cv, style, palette)


def prop_front(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """The shaft over the sleeve where the hand grips it (FR-41)."""
    if style.prop not in HELD:
        return
    x = HAND_CENTER[0]
    cv.color(palette["gold_dk"]).M(x, -66).L(x, -50).stroke(0.9)
    cv.color(palette["gold_lt"], 0.5).M(x - 0.2, -66).L(x - 0.2, -50).stroke(0.25)


def hand(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if style.prop not in HELD:
        return
    cv.save()
    cv.translate(HAND_CENTER[0] - af.HAND_CENTER[0], HAND_CENTER[1] - af.HAND_CENTER[1])
    af.hand(cv, style, palette)
    cv.restore()


# --------------------------------------------------------------------------------------
# Head: the shared male face, then headwear
# --------------------------------------------------------------------------------------


def neck(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(palette["egg"]).M(-2.1, -83).L(2.1, -83).L(2.5, -78).L(-2.5, -78).Z().fill()


def face(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """A squarer jaw than the female oval; no cheek blush (owner-approved, 2026-11-22)."""
    cv.M(0, -95).C(3.7, -95, 5.9, -92.6, 5.9, -88.8).C(5.9, -85.4, 4.8, -82.7, 2.8, -81.8)
    cv.L(-2.8, -81.8).C(-4.8, -82.7, -5.9, -85.4, -5.9, -88.8).C(-5.9, -92.6, -3.7, -95, 0, -95)
    cv.Z().color(palette["egg"]).fill()


def features(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Level brows, flatter closed eyes, a nose line and a thin lip line; nothing else."""
    for s in (-1, 1):
        cv.color(palette["black"], 0.8).M(s * 1.1, -90.9)
        cv.C(s * 2.2, -91.5, s * 3.4, -91.5, s * 4.4, -91.0).stroke(0.52)
        cv.color(palette["black"]).M(s * 1.3, -88.3)
        cv.C(s * 2.1, -87.9, s * 3.1, -87.9, s * 3.9, -88.3).stroke(0.45)
    cv.color(palette["skin_line"], 0.5).M(0.2, -88).C(0.5, -86.8, 0.6, -85.8, 0.1, -85.2)
    cv.stroke(0.28)
    cv.color(palette["vermilion_dk"], 0.85).M(-1.4, -83.8)
    cv.C(-0.5, -83.65, 0.5, -83.65, 1.4, -83.8).stroke(0.42)


def _topknot_wrap(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(palette["black"]).M(-5.6, -88).C(-6.2, -94, -3.2, -97, 0, -97)
    cv.C(3.2, -97, 6.2, -94, 5.6, -88).C(4.6, -92, 2.6, -93.2, 0, -93)
    cv.C(-2.6, -93.2, -4.6, -92, -5.6, -88).Z().fill()
    cv.color(palette["black"]).ellipse(0, -99.5, 2.8, 2.4).fill()
    cv.M(-6.1, -93.5).C(-3, -97, 3, -97, 6.1, -93.5).L(6, -90.8)
    cv.C(3, -93.4, -3, -93.4, -6, -90.8).Z()
    cv.color(style.wrap).fill()
    cv.color(style.wrap).M(5.6, -92).C(8, -91, 9, -88, 8.6, -85).stroke(1.0)


def _viet_helmet(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Rounded bowl with cheek flaps, a gold brim band and, with ``crest``, a plume."""
    cv.M(-7.4, -86).C(-8.2, -94, -4.6, -100.5, 0, -100.5).C(4.6, -100.5, 8.2, -94, 7.4, -86)
    cv.L(5.6, -86).C(5.8, -90, 3.6, -92.4, 0, -92.4).C(-3.6, -92.4, -5.8, -90, -5.6, -86).Z()
    _grad(cv, -101, -86, _armour(style, palette), palette["brown"]).fill(keep=True)
    cv.color(palette["gold"]).stroke(0.45)
    cv.M(-6.6, -92.6).C(-3, -95.2, 3, -95.2, 6.6, -92.6).color(palette["gold"]).stroke(1.0)
    cv.color(palette["gold"]).ellipse(0, -101.3, 1.3, 1.0).fill()
    if style.crest:
        cv.M(0, -101.5).C(-2.4, -105, -1.6, -110, 1.4, -113).C(1, -109, 2.4, -105, 0.8, -101.5)
        cv.Z().color(style.wrap).fill()


def _northern_helmet(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Pointed bowl above the brows, a neck guard flaring beside the face, a tassel."""
    steel = _armour(style, palette)
    dark = palette["steel_dk"]
    for s in (-1, 1):
        cv.M(s * 6.4, -91.6).C(s * 9, -90.5, s * 11.5, -87.5, s * 12, -83.5).L(s * 8.2, -84.5)
        cv.C(s * 7.4, -87.5, s * 6.8, -89.4, s * 6.2, -90.2).Z()
    _grad(cv, -92, -83, steel, dark).fill(keep=True)
    cv.color(style.trim).stroke(0.45)
    cv.M(-7, -91.2).C(-7, -98, -3.4, -103, 0, -106).C(3.4, -103, 7, -98, 7, -91.2)
    cv.C(3.5, -92.4, -3.5, -92.4, -7, -91.2).Z()
    _grad(cv, -106, -91, steel, dark).fill(keep=True)
    cv.color(style.trim).stroke(0.45)
    cv.color(style.trim).M(-7, -91.6).C(-3.5, -93, 3.5, -93, 7, -91.6).stroke(0.9)
    cv.color(style.trim).M(0, -105.5).L(0, -93).stroke(0.4)
    if style.crest:
        cv.M(0, -106).C(-1.4, -108, -1.8, -110.5, 0, -112).C(1.8, -110.5, 1.4, -108, 0, -106)
        cv.Z().color(style.trim).fill()


def _cap(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.M(-6.2, -90).C(-6.4, -97, 6.4, -97, 6.2, -90).Z().color(style.wrap).fill()


HELMETS: Final[Mapping[str, PartFn]] = MappingProxyType(
    {
        "topknot_wrap": _topknot_wrap,
        "viet_helmet": _viet_helmet,
        "northern_helmet": _northern_helmet,
        "cap": _cap,
    }
)
VARIANTS: Final[Mapping[str, Mapping[str, PartFn]]] = MappingProxyType({"helmet": HELMETS})


def headwear(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    HELMETS[style.variant.get("helmet", DEFAULT_HELMET)](cv, style, palette)


DRAW_ORDER: Final[tuple[str, ...]] = (
    "cape",
    "prop_back",
    "legs",
    "body",
    "belt",
    "sword",
    "far_sleeve",
    "shield",
    "near_sleeve",
    "prop_front",
    "hand",
    "neck",
    "face",
    "features",
    "headwear",
)
HEAD_PARTS: Final = frozenset({"neck", "face", "features", "headwear"})
PARTS: Final[Mapping[str, Callable[[Canvas, CharacterStyle, Palette], None]]] = MappingProxyType(
    {
        "cape": cape,
        "prop_back": prop_back,
        "legs": legs,
        "body": body,
        "belt": belt,
        "sword": sword,
        "far_sleeve": far_sleeve,
        "shield": shield,
        "near_sleeve": near_sleeve,
        "prop_front": prop_front,
        "hand": hand,
        "neck": neck,
        "face": face,
        "features": features,
        "headwear": headwear,
    }
)

KIT: Final = Kit(
    name="warrior_male",
    draw_order=DRAW_ORDER,
    parts=PARTS,
    head_parts=HEAD_PARTS,
    props=PROPS,
    hand_center=HAND_CENTER,
    shaft_segment=shaft_segment,
    extents=KitExtents(
        head_half_width=HEAD_HALF_WIDTH,
        head_top=HEAD_TOP,
        crest_top=CREST_TOP,
        chin_y=CHIN_Y,
        body=(-BODY_HALF_WIDTH, BODY_TOP, BODY_HALF_WIDTH, BODY_BOTTOM),
        props=MappingProxyType(PROP_EXTENT),
    ),
)
