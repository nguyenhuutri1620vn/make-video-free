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
from history_shorts.cloth import ClothWave
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
# A raised sleeve shows the kit's closed fist just beyond its cuff (owner call, 2026-11-20).
FIST_SHOW_DEG: Final = 60.0  # shoulder angle above which the fist shows
FIST_AT: Final[Mapping[str, Point]] = MappingProxyType(
    {"near": (16.0, -39.8), "far": (-16.0, -39.8)}  # fist centre in the sleeve's frame
)
# Kneeling and sitting (FR-50): the skirt squashes toward the feet and widens while the
# upper body drops by the same amount, so the waist stays joined; the feet do not move.
CROUCH_DROP: Final = 22.0  # units the waist and everything above it drop at crouch 1
CROUCH_SPREAD: Final = 9.0  # units the hem widens on each side at crouch 1
# A held flag waves (M10): the M10 cloth wave from the pole at PROP_X out to the flag tip.
FLAG_WAVE_AMP: Final = 0.08  # wave height as a fraction of the flag's length
FLAG_LENGTH: Final = 33.0  # pole to the flag's free edge
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


def free_arm(style: CharacterStyle) -> str:
    """The arm that can gesture: the far one when the near hand holds a prop."""
    return "far" if style.prop != "none" else "near"


def joints(style: CharacterStyle, pose: Pose) -> Mapping[str, Affine]:
    """Every segment's transform in the local frame for ``pose``."""
    drop = pose.crouch * CROUCH_DROP
    bottom = af.BODY_BOTTOM
    squash = (bottom - af.WAIST_Y - drop) / (bottom - af.WAIST_Y)
    widen = 1.0 + pose.crouch * CROUCH_SPREAD / af.HEM_HALF_WIDTH
    skirt = about((0.0, bottom), scale(widen, squash))
    lean = rotate(pose.torso_lean - pose.lean_back) @ scale(1.0, 1.0 + pose.breath)
    torso = translate(0.0, drop) @ about(WAIST, lean)
    bow = translate(HEAD_DROP_FORWARD * pose.head_drop, pose.head_drop)
    head = torso @ bow @ about(NECK, rotate(-pose.head_tilt))
    near = torso @ about(SHOULDERS["near"], rotate(-pose.near_shoulder))
    far = torso @ about(SHOULDERS["far"], rotate(pose.far_shoulder))
    dx = near.apply(af.HAND_CENTER)[0] - af.HAND_CENTER[0]
    dy = near.apply(af.HAND_CENTER)[1] - af.HAND_CENTER[1]
    held = style.prop != "none"
    hand = translate(dx, dy) if held else IDENTITY
    prop = translate(dx, min(dy, 0.0)) if held else IDENTITY
    return {
        "skirt": skirt,
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
    """The skirt (squashed when kneeling), the upper robe under the torso joint; the cut is
    under the belt."""
    m = joints(style, _pose(style))
    waist = af.WAIST_Y
    with _frame(cv, m["skirt"], (waist, CLIP_REACH)):
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
    fist: Paint | None = None,
) -> None:
    upper, fore = m[f"{side}_arm"], m[f"{side}_fore"]
    above, below = (-CLIP_REACH, ELBOW_Y), (ELBOW_Y, CLIP_REACH)
    if fist is not None:
        with _frame(cv, fore):
            fist(cv)
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


def _fist(side: str, style: CharacterStyle, palette: Palette) -> Paint | None:
    """The kit's fist drawn at the cuff of a raised sleeve, else None."""
    if getattr(_pose(style), f"{side}_shoulder") <= FIST_SHOW_DEG:
        return None
    hx, hy = af.HAND_CENTER
    fx, fy = FIST_AT[side]

    def draw(c: Canvas) -> None:
        c.translate(fx, fy)
        if side == "far":
            c.scale(-1, 1)  # mirroring only through scale(-1, 1)
        c.translate(-hx, -hy)
        af._fist(c)  # noqa: SLF001
        c.color(palette["egg"]).fill()
        af._fist(c)  # noqa: SLF001
        c.color(palette["skin_line"], 0.55).stroke(0.18)

    return draw


def sleeves(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Far sleeve, then the near one: jointed when hanging, rigid when holding the prop."""
    m = joints(style, _pose(style))
    gold = palette["gold"]

    def far_paint(c: Canvas) -> None:
        c.vgrad(-78, -41, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()

    def far_cuff(c: Canvas) -> None:
        c.color(style.trim).M(-21.5, -44).C(-19, -41.2, -13.5, -41.2, -10.5, -44.5).stroke(1.4)

    far_fist = _fist("far", style, palette)
    _jointed_sleeve(cv, m, "far", af._far_arm, far_paint, far_cuff, gold, far_fist)  # noqa: SLF001
    if style.prop == "none":

        def near_paint(c: Canvas) -> None:
            c.color(style.robe).fill()

        near_fist = _fist("near", style, palette)
        _jointed_sleeve(
            cv,
            m,
            "near",
            af._hanging_arm,
            near_paint,
            None,
            gold,
            near_fist,  # noqa: SLF001
        )
        return
    with _frame(cv, m["near_arm"]):
        af._holding_arm(cv)  # noqa: SLF001
        cv.vgrad(-78, -54, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()
        cv.color(style.trim).M(20.5, -58).C(18.5, -54.8, 14.5, -54.8, 12.5, -57).stroke(1.3)
        af._holding_arm(cv)  # noqa: SLF001
        cv.color(gold).stroke(0.5)


def _waved_flag(cv: Canvas, palette: Palette, phase: float, banner: RGB | None = None) -> None:
    """``ancient_female._flag`` with every point passed through the cloth wave."""
    w = ClothWave(af.PROP_X, FLAG_LENGTH, phase, FLAG_WAVE_AMP, 0.0).pt
    gold = palette["gold"]
    cv.color(gold).ellipse(17, -137.5, 1.5, 1.5).fill()

    def cloth(c: Canvas) -> None:
        c.M(*w(17, -135)).C(*w(28, -134), *w(38, -131), *w(50, -127))
        c.C(*w(45, -124), *w(42, -121), *w(47, -116)).C(*w(37, -116), *w(27, -112), *w(17, -107))
        c.Z()

    cloth(cv)
    cv.color(banner or palette["vermilion"]).fill()
    cloth(cv)
    cv.color(gold).stroke(0.7)
    cv.color(gold).M(*w(20, -131)).C(*w(28, -129.5), *w(35, -127.5), *w(41, -125.5)).stroke(0.35)
    cv.M(*w(20, -112)).C(*w(27, -114.5), *w(33, -116), *w(39, -117)).stroke(0.35)
    cv.color(gold).ellipse(*w(29, -121.5), 2.6, 2.6).stroke(0.5)


def prop_back(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """``ancient_female.prop_back`` with a waving flag."""
    if style.prop != "flag":
        af.prop_back(cv, style, palette)
        return
    segment = af.shaft_segment(style.prop)
    assert segment is not None
    (x0, y0), (x1, y1) = segment
    cv.color(palette["gold_dk"]).M(x0, y0).L(x1, y1).stroke(0.9)
    _waved_flag(cv, palette, _pose(style).flag_wave, style.banner)


# The body extent split by joint, for posed FR-48 boxes; at rest the union is the kit's body.
BODY_BOXES: Final[Mapping[str, tuple[float, float, float, float]]] = MappingProxyType(
    {
        "skirt": (-af.BODY_HALF_WIDTH, af.WAIST_Y, af.BODY_HALF_WIDTH, af.BODY_BOTTOM),
        "torso": (-14.0, af.BODY_TOP, 14.0, af.WAIST_Y),
        "far_arm": (-22.5, -78.0, -8.0, ELBOW_Y),
        "far_fore": (-22.5, ELBOW_Y, -8.0, -35.0),
        "near_arm": (8.0, -78.0, 22.5, -54.0),
        "near_fore": (8.0, ELBOW_Y, 22.5, -35.0),
    }
)

RIG: Final = KitRig(
    segments=SEGMENTS,
    joints=joints,
    parts=MappingProxyType({"robe": robe, "sleeves": sleeves, "prop_back": prop_back}),
    body_boxes=BODY_BOXES,
)
