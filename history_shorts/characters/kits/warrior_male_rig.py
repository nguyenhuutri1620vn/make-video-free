"""Joints of the ``warrior_male`` kit (M12): the same joint names and maths as the female rig.

The body and the cape are cut at the waist (the cut lies under the belt); legs, boots and a
sheathed sword belong to the skirt segment, so kneeling squashes them toward the feet; a
shield rides on the far forearm; hanging sleeves bend at the elbow with a covering patch.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from history_shorts.canvas import Canvas
from history_shorts.characters.kits import ancient_female as af
from history_shorts.characters.kits import ancient_female_rig as fr
from history_shorts.characters.kits import warrior_male as wm
from history_shorts.characters.kits.base import KitRig
from history_shorts.characters.pose import Pose
from history_shorts.characters.rig import Affine
from history_shorts.config import Palette
from history_shorts.primitives import Point

if TYPE_CHECKING:
    from history_shorts.characters.roles import CharacterStyle

WAIST: Final[Point] = (0.0, wm.WAIST_Y)
NECK: Final[Point] = (0.0, wm.CHIN_Y)
SHOULDERS: Final[Mapping[str, Point]] = MappingProxyType(
    {"near": (12.0, -77.0), "far": (-12.0, -77.0)}
)
ELBOWS: Final[Mapping[str, Point]] = MappingProxyType(
    {"near": (16.0, -60.0), "far": (-16.0, -60.0)}
)
ELBOW_PATCH_R: Final = 4.2  # inside the sleeve at rest (half width 4.6-5.2 there)
FIST_AT: Final[Mapping[str, Point]] = MappingProxyType(
    {"near": (16.7, -41.5), "far": (-16.7, -41.5)}
)
CROUCH_DROP: Final = 22.0
CROUCH_SPREAD: Final = 8.0
HEM_HALF: Final = 19.0

GEOMETRY: Final = fr.JointGeometry(
    waist=WAIST,
    neck=NECK,
    shoulders=SHOULDERS,
    elbows=ELBOWS,
    hand_center=wm.HAND_CENTER,
    bottom=wm.BODY_BOTTOM,
    hem_half=HEM_HALF,
    crouch_drop=CROUCH_DROP,
    crouch_spread=CROUCH_SPREAD,
    held=lambda prop: prop in wm.HELD,
)


def joints(style: CharacterStyle, pose: Pose) -> Mapping[str, Affine]:
    return fr.build_joints(GEOMETRY, style, pose)


def _pose(style: CharacterStyle) -> Pose:
    assert style.pose is not None
    return style.pose


def _split(
    cv: Canvas,
    style: CharacterStyle,
    palette: Palette,
    part: Callable[..., None],
    overlap: float = 0.0,
) -> None:
    """``part`` below the waist in the skirt frame and above it in the torso frame; the
    upper half reaches ``overlap`` units below the cut (only where nothing shows twice)."""
    m = joints(style, _pose(style))
    waist = wm.WAIST_Y
    with fr._frame(cv, m["skirt"], (waist, fr.CLIP_REACH)):  # noqa: SLF001
        part(cv, style, palette)
    with fr._frame(cv, m["torso"], (-fr.CLIP_REACH, waist + overlap)):  # noqa: SLF001
        part(cv, style, palette)


CAPE_OVERLAP: Final = 4.0  # the cape is wider than the belt, so its cut needs cover


def _cape_fill(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if not wm._body_kind(style).endswith("cape"):  # noqa: SLF001
        return
    cv.M(-14, -79).C(-20, -60, -24, -35, -25, -12).C(-10, -9, 10, -9, 25, -12)
    cv.C(24, -35, 20, -60, 14, -79).Z()
    cv.vgrad(-80, -10, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()


def cape(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """The upper cape's colour reaches under the waist cut first (fill only, no outline),
    so a leaning torso opens no gap; then the two halves as usual."""
    m = joints(style, _pose(style))
    waist = wm.WAIST_Y
    with fr._frame(cv, m["torso"], (waist, waist + CAPE_OVERLAP)):  # noqa: SLF001
        _cape_fill(cv, style, palette)
    _split(cv, style, palette, wm.cape)


def body(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    _split(cv, style, palette, wm.body)


def _fist(side: str, style: CharacterStyle, palette: Palette) -> fr.Paint | None:
    """The kit's fist at the cuff of a raised sleeve (as the female rig)."""
    if getattr(_pose(style), f"{side}_shoulder") <= fr.FIST_SHOW_DEG:
        return None
    hx, hy = af.HAND_CENTER
    fx, fy = FIST_AT[side]

    def draw(c: Canvas) -> None:
        c.translate(fx, fy)
        if side == "far":
            c.scale(-1, 1)
        c.translate(-hx, -hy)
        af._fist(c)  # noqa: SLF001
        c.color(palette["egg"]).fill()
        af._fist(c)  # noqa: SLF001
        c.color(palette["skin_line"], 0.55).stroke(0.18)

    return draw


def _sleeve(cv: Canvas, style: CharacterStyle, palette: Palette, side: str) -> None:
    m = joints(style, _pose(style))
    mirror = side == "far"

    def path(c: Canvas) -> None:
        c.save()
        if mirror:
            c.scale(-1, 1)  # mirroring only through scale(-1, 1)
        wm.hanging_arm_path(c)
        c.restore()

    def paint(c: Canvas) -> None:
        c.vgrad(-79, -43, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()

    def cuff(c: Canvas) -> None:
        c.save()
        if mirror:
            c.scale(-1, 1)
        c.color(style.trim).M(22, -46).C(19.5, -43.2, 14, -43.2, 11.5, -46).stroke(1.3)
        c.restore()

    fist = _fist(side, style, palette)
    fr._jointed_sleeve(  # noqa: SLF001
        cv,
        m,
        side,
        path,
        paint,
        cuff,
        palette[wm.OUTLINE],
        fist,
        ELBOWS[side],
        ELBOW_PATCH_R,
        cuff_last=True,
        outline=wm.OUTLINE_WIDTH,
    )
    with fr._frame(cv, m[f"{side}_arm"]):  # noqa: SLF001
        cv.save()
        if mirror:
            cv.scale(-1, 1)
        wm.shoulder_guard(cv, style, palette)
        cv.restore()


def far_sleeve(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    _sleeve(cv, style, palette, "far")


def near_sleeve(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    if style.prop not in wm.HELD:
        _sleeve(cv, style, palette, "near")
        return
    with fr._frame(cv, joints(style, _pose(style))["near_arm"]):  # noqa: SLF001
        wm.near_sleeve(cv, style, palette)


SEGMENTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "cape": "root",
        "prop_back": "prop",
        "legs": "skirt",
        "body": "root",
        "belt": "torso",
        "sword": "skirt",
        "far_sleeve": "root",
        "shield": "far_fore",
        "near_sleeve": "root",
        "prop_front": "prop",
        "hand": "hand",
        "neck": "torso",
        "face": "head",
        "features": "head",
        "headwear": "head",
    }
)
BODY_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = MappingProxyType(
    {
        "skirt": (-wm.BODY_HALF_WIDTH, wm.WAIST_Y, wm.BODY_HALF_WIDTH, wm.BODY_BOTTOM),
        "torso": (-wm.BODY_HALF_WIDTH, wm.BODY_TOP, wm.BODY_HALF_WIDTH, wm.WAIST_Y),
        "far_arm": (-22.5, -80.0, -8.0, -60.0),
        "far_fore": (-33.5, -63.5, -8.0, -36.5),  # includes the shield
        "near_arm": (8.0, -80.0, 22.5, -55.0),
        "near_fore": (8.0, -60.0, 22.5, -40.0),
    }
)

RIG: Final = KitRig(
    segments=SEGMENTS,
    joints=joints,
    parts=MappingProxyType(
        {"cape": cape, "body": body, "far_sleeve": far_sleeve, "near_sleeve": near_sleeve}
    ),
    body_boxes=BODY_BOXES,
)
