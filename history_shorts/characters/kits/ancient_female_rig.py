"""Joints of the ``ancient_female`` kit (M10): the same parts, drawn from a ``Pose``.

Each part is drawn under one joint transform. Two parts span joints and draw themselves:
the robe is cut at the waist (the cut lies under the belt) and each hanging sleeve is cut
at its elbow (an elbow patch of sleeve colour covers the cut when the arm bends). A held
prop moves sideways and up with the hand without turning, so a spear stays upright and the
hand keeps its grip in every pose; when the hand drops, the shaft slides through it instead
of sinking into the ground. Angles follow ``Pose``: a raised shoulder lifts the arm out to its own
side; a bent elbow folds the forearm in toward the head; a positive lean tips the upper
body toward the facing direction.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from history_shorts.canvas import Canvas
from history_shorts.characters.kits import ancient_female as af
from history_shorts.characters.kits.base import KitRig
from history_shorts.characters.pose import Pose
from history_shorts.characters.rig import (
    IDENTITY,
    Affine,
    about,
    apply_to,
    rotate,
    scale,
    translate,
)
from history_shorts.config import Palette
from history_shorts.primitives import RGB, Point

if TYPE_CHECKING:
    from history_shorts.characters.roles import CharacterStyle

WAIST: Final[Point] = (0.0, af.WAIST_Y)
NECK: Final[Point] = (0.0, af.CHIN_Y)
SHOULDERS: Final[Mapping[str, Point]] = MappingProxyType(
    {"near": (11.0, -77.0), "far": (-11.0, -77.0)}
)
ELBOW_Y: Final = -60.0
ELBOWS: Final[Mapping[str, Point]] = MappingProxyType(
    {"near": (15.0, ELBOW_Y), "far": (-15.0, ELBOW_Y)}
)
ELBOW_PATCH_R: Final = 4.4  # inside the sleeve at rest (half width 4.7-5.5 there)
HEAD_DROP_FORWARD: Final = 0.3  # a bow moves the head this far forward per unit down
CLIP_REACH: Final = 400.0  # half size of the half-plane clip rectangles

HEAD_SEGMENT_PARTS: Final = ("hair_back", "face", "features", "hair_front", "bun", "headwrap",
                             "crest")  # fmt: skip
SEGMENTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        **{name: "head" for name in HEAD_SEGMENT_PARTS},
        "prop_back": "prop",
        "robe": "root",
        "belt": "torso",
        "sleeves": "root",
        "prop_front": "prop",
        "hand": "hand",
        "neck": "torso",
    }
)


def joints(style: CharacterStyle, pose: Pose) -> Mapping[str, Affine]:
    """Every segment's transform in the local frame for ``pose``."""
    torso = about(WAIST, rotate(pose.torso_lean) @ scale(1.0, 1.0 + pose.breath))
    drop = translate(HEAD_DROP_FORWARD * pose.head_drop, pose.head_drop)
    head = torso @ drop @ about(NECK, rotate(-pose.head_tilt))
    near = torso @ about(SHOULDERS["near"], rotate(-pose.near_shoulder))
    far = torso @ about(SHOULDERS["far"], rotate(pose.far_shoulder))
    dx = near.apply(af.HAND_CENTER)[0] - af.HAND_CENTER[0]
    dy = near.apply(af.HAND_CENTER)[1] - af.HAND_CENTER[1]
    held = style.prop != "none"
    hand = translate(dx, dy) if held else IDENTITY
    prop = translate(dx, min(dy, 0.0)) if held else IDENTITY
    return {
        "torso": torso,
        "head": head,
        "near_arm": near,
        "far_arm": far,
        "near_fore": near @ about(ELBOWS["near"], rotate(-pose.near_elbow)),
        "far_fore": far @ about(ELBOWS["far"], rotate(pose.far_elbow)),
        "hand": hand,
        "prop": prop,
    }


@contextmanager
def _frame(cv: Canvas, m: Affine, clip: tuple[float, float] | None = None) -> Iterator[None]:
    """Draw under ``m``, optionally clipped to the band ``clip`` = (y_top, y_bottom)."""
    cv.save()
    apply_to(cv, m)
    if clip is not None:
        top, bottom = clip
        cv.rect(-CLIP_REACH, top, 2 * CLIP_REACH, bottom - top).clip()
    yield
    cv.restore()


def _pose(style: CharacterStyle) -> Pose:
    assert style.pose is not None
    return style.pose


def robe(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """The skirt in place, the upper robe under the torso joint; the cut is under the belt."""
    m = joints(style, _pose(style))
    waist = af.WAIST_Y
    with _frame(cv, IDENTITY, (waist, CLIP_REACH)):
        af.robe(cv, style, palette)
    with _frame(cv, m["torso"], (-CLIP_REACH, waist)):
        af.robe(cv, style, palette)


Paint = Callable[[Canvas], None]


def _jointed_sleeve(
    cv: Canvas,
    m: Mapping[str, Affine],
    side: str,
    path: Callable[[Canvas], None],
    paint: Paint,
    cuff: Paint | None,
    gold: RGB,
) -> None:
    upper, fore = m[f"{side}_arm"], m[f"{side}_fore"]
    above, below = (-CLIP_REACH, ELBOW_Y), (ELBOW_Y, CLIP_REACH)
    with _frame(cv, fore, below):
        path(cv)
        paint(cv)
    with _frame(cv, upper, above):
        path(cv)
        paint(cv)
    with _frame(cv, upper):
        ex, ey = ELBOWS[side]
        cv.ellipse(ex, ey, ELBOW_PATCH_R, ELBOW_PATCH_R)
        paint(cv)
    if cuff is not None:
        with _frame(cv, fore):
            cuff(cv)
    for frame, band in ((fore, below), (upper, above)):
        with _frame(cv, frame, band):
            path(cv)
            cv.color(gold).stroke(0.5)


def sleeves(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Far sleeve, then the near one: jointed when hanging, rigid when holding the prop."""
    m = joints(style, _pose(style))
    gold = palette["gold"]

    def far_paint(c: Canvas) -> None:
        c.vgrad(-78, -41, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()

    def far_cuff(c: Canvas) -> None:
        c.color(style.trim).M(-21.5, -44).C(-19, -41.2, -13.5, -41.2, -10.5, -44.5).stroke(1.4)

    _jointed_sleeve(cv, m, "far", af._far_arm, far_paint, far_cuff, gold)  # noqa: SLF001
    if style.prop == "none":

        def near_paint(c: Canvas) -> None:
            c.color(style.robe).fill()

        _jointed_sleeve(cv, m, "near", af._hanging_arm, near_paint, None, gold)  # noqa: SLF001
        return
    with _frame(cv, m["near_arm"]):
        af._holding_arm(cv)  # noqa: SLF001
        cv.vgrad(-78, -54, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()
        cv.color(style.trim).M(20.5, -58).C(18.5, -54.8, 14.5, -54.8, 12.5, -57).stroke(1.3)
        af._holding_arm(cv)  # noqa: SLF001
        cv.color(gold).stroke(0.5)


RIG: Final = KitRig(
    segments=SEGMENTS,
    joints=joints,
    parts=MappingProxyType({"robe": robe, "sleeves": sleeves}),
)
