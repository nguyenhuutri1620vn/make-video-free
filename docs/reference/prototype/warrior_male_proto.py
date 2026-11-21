"""M12a prototype of the warrior_male kit (owner-approved 2026-11-22).

Reference only: copy its numbers (proportions, paths, colours), not its structure. Never import
from docs/. Produced docs/reference/approved/warrior_male_roles.png and warrior_male_faces.png.
Proposed palette keys approved with it: steel (126,128,122), steel_dk (74,78,78),
indigo (46,58,92), indigo_dk (28,34,58).
"""


from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from history_shorts.canvas import Canvas
from history_shorts.characters import resolve_style
from history_shorts.characters.kits import ancient_female as af
from history_shorts.config import CharacterSpec, load_theme
from history_shorts.gallery import canvas_ground, label_font

THEME = load_theme(Path("themes/son_mai/theme.json"))[0]
PAL = dict(THEME.palette.colors)
# proposed new palette keys (owner reviews them with these images)
PAL.update({"steel": (126, 128, 122), "steel_dk": (74, 78, 78), "indigo": (46, 58, 92), "indigo_dk": (28, 34, 58)})
FACE_STYLE = resolve_style(CharacterSpec(role="general"), THEME.palette)


def C(key: str) -> tuple[int, int, int]:
    return PAL[key]


@dataclass(frozen=True)
class Role:
    name: str
    title: str
    helmet: str  # viet_helmet | northern_helmet | topknot_wrap | cap
    body: str  # tunic | lamellar | lamellar_cape
    prop: str  # flag | spear | sword | shield
    robe: str
    robe_dk: str
    trim: str
    wrap: str
    armour: str
    banner: str
    plume: str


ROLES = [
    Role("viet_general", "Tướng Việt (kiểu Ngô Quyền)", "viet_helmet", "lamellar_cape", "flag",
         "vermilion", "vermilion_dk", "gold", "vermilion", "gold_dk", "vermilion", "vermilion"),
    Role("viet_soldier", "Lính Việt", "topknot_wrap", "tunic", "spear",
         "jade", "robe_crew_dk", "gold_dk", "vermilion", "gold_dk", "vermilion", "vermilion"),
    Role("northern_general", "Tướng phương Bắc", "northern_helmet", "lamellar_cape", "sword",
         "indigo", "indigo_dk", "gold_dk", "indigo", "steel", "indigo", "gold"),
    Role("northern_soldier", "Lính phương Bắc", "northern_helmet", "lamellar", "spear",
         "indigo", "indigo_dk", "steel_dk", "indigo", "steel", "indigo", "steel_dk"),
    Role("northern_shield", "Lính phương Bắc (khiên)", "northern_helmet", "lamellar", "shield",
         "indigo", "indigo_dk", "steel_dk", "indigo", "steel", "indigo", "steel_dk"),
]

OUT, W = "gold", 0.55  # outline colour and width (the female kit's)
HAND = (19.0, -58.0)  # near hand centre (prop grip)
SHOULDER_NEAR, SHOULDER_FAR = (13.0, -77.0), (-13.0, -77.0)
WAIST = (0.0, -52.0)


def grad(cv: Canvas, y0: float, y1: float, a: str, b: str) -> Canvas:
    return cv.vgrad(y0, y1, [(0, C(a), 1), (1, C(b), 1)])


# --- body -------------------------------------------------------------------------------


def legs(cv: Canvas, r: Role) -> None:
    for s in (-1, 1):
        cv.M(s * 2, -18).L(s * 10, -18).L(s * 9, -5).L(s * 3, -5).Z()
        grad(cv, -18, -5, "brown_lt", "brown").fill(keep=True)
        cv.color(C(OUT)).stroke(W)
        cv.M(s * 2.5, -5.5).L(s * 9.5, -5.5).C(s * 11, -3, s * 11.5, 0, s * 9, 0).L(s * 2.5, 0).Z()
        cv.color(C("black")).fill(keep=True)
        cv.color(C("gold_dk")).stroke(0.4)


def cape(cv: Canvas, r: Role) -> None:
    if not r.body.endswith("cape"):
        return
    cv.M(-14, -79).C(-20, -60, -24, -35, -25, -12).C(-10, -9, 10, -9, 25, -12)
    cv.C(24, -35, 20, -60, 14, -79).Z()
    grad(cv, -80, -10, r.robe, r.robe_dk).fill(keep=True)
    cv.color(C(r.trim)).stroke(0.8)


def _torso(cv: Canvas) -> None:
    cv.M(-14, -79).C(-16, -70, -14, -60, -12, -52).C(-15, -40, -18, -28, -19, -16)
    cv.C(-8, -13, 8, -13, 19, -16).C(18, -28, 15, -40, 12, -52)
    cv.C(14, -60, 16, -70, 14, -79).C(8, -83, -8, -83, -14, -79).Z()


def body(cv: Canvas, r: Role) -> None:
    _torso(cv)
    grad(cv, -82, -14, r.robe, r.robe_dk).fill()
    if r.body.startswith("lamellar"):
        cv.save()
        _torso(cv)
        cv.clip()
        top, rows = -78.0, 16
        for k in range(rows):
            y = top + k * 4.0
            off = 1.5 if k % 2 else 0.0
            x = -20.0 + off
            while x < 20:
                cv.M(x, y).L(x + 3, y).L(x + 3, y + 3.2).C(x + 3, y + 4.2, x, y + 4.2, x, y + 3.2).Z()
                x += 3.2
        cv.color(C(r.armour)).fill()
        cv.restore()
        cv.save()
        _torso(cv)
        cv.clip()
        for k in range(16):
            y = -78.0 + k * 4.0 + 3.6
            cv.M(-20, y).L(20, y)
        cv.color(C(r.trim), 0.7).stroke(0.35)
        cv.restore()
    _torso(cv)
    cv.color(C(OUT)).stroke(W)
    # collar
    cv.color(C(r.trim)).M(-5, -81).L(0, -74).L(5, -81).stroke(1.2)


def belt(cv: Canvas, r: Role) -> None:
    cv.color(C(r.trim)).M(-12.3, -54).C(-4, -52.6, 4, -52.6, 12.3, -54).L(12.2, -50.5)
    cv.C(4, -49.2, -4, -49.2, -12.2, -50.5).Z().fill()
    cv.color(C("vermilion" if r.name.startswith("viet") else "gold_dk")).ellipse(0, -51.8, 1.6, 1.3).fill()


def sword(cv: Canvas, r: Role) -> None:
    if r.prop != "sword":
        return
    cv.save()
    cv.translate(9, -50)
    cv.rotate(math.radians(-24))
    cv.rect(-1.6, 0, 3.2, 30)
    grad(cv, 0, 30, "brown_lt", "brown").fill(keep=True)
    cv.color(C("gold_dk")).stroke(0.5)
    cv.color(C("gold")).rect(-3.2, -1.6, 6.4, 1.6).fill()
    cv.color(C("brown")).rect(-1, -7, 2, 5.4).fill()
    cv.color(C("gold")).ellipse(0, -7.6, 1.4, 1.2).fill()
    cv.restore()


# --- arms -------------------------------------------------------------------------------


def _arm_path(cv: Canvas) -> None:  # a hanging arm on the near side, shoulder at (13, -77)
    cv.M(12, -79).C(19, -72, 22.5, -60, 22, -46).C(19.5, -43, 14, -43, 11.5, -46)
    cv.C(11.5, -58, 10.5, -68, 9, -74).Z()


def _arm(cv: Canvas, r: Role, angle: float, side: int) -> None:
    cv.save()
    if side < 0:
        cv.scale(-1, 1)
    sx, sy = SHOULDER_NEAR
    cv.translate(sx, sy)
    cv.rotate(math.radians(-angle))
    cv.translate(-sx, -sy)
    if angle > 60:  # raised: fist at the cuff
        cv.save()
        cv.translate(17, -40.5)
        cv.translate(-af.HAND_CENTER[0], -af.HAND_CENTER[1])
        af._fist(cv)
        cv.color(C("egg")).fill()
        cv.restore()
    _arm_path(cv)
    grad(cv, -79, -43, r.robe, r.robe_dk).fill(keep=True)
    cv.color(C(OUT)).stroke(W)
    cv.color(C(r.trim)).M(22, -46).C(19.5, -43.2, 14, -43.2, 11.5, -46).stroke(1.3)
    if r.body.startswith("lamellar"):  # shoulder guard
        cv.M(10, -80).C(16, -80, 21, -74, 21, -68).C(17, -69, 13, -71, 10, -74).Z()
        cv.color(C(r.armour)).fill(keep=True)
        cv.color(C(r.trim)).stroke(0.5)
    cv.restore()


def _holding_arm(cv: Canvas, r: Role) -> None:
    cv.M(12, -79).C(19, -74, 22.5, -66, 21.5, -59).C(19.5, -55.5, 15.5, -55.5, 13.5, -58)
    cv.C(13.3, -64, 12.3, -71, 10.5, -75).Z()
    grad(cv, -79, -55, r.robe, r.robe_dk).fill(keep=True)
    cv.color(C(OUT)).stroke(W)
    cv.color(C(r.trim)).M(21.5, -59).C(19.5, -55.8, 15.5, -55.8, 13.5, -58).stroke(1.3)
    if r.body.startswith("lamellar"):
        cv.M(10, -80).C(16, -80, 21, -74, 21, -68).C(17, -69, 13, -71, 10, -74).Z()
        cv.color(C(r.armour)).fill(keep=True)
        cv.color(C(r.trim)).stroke(0.5)


def shaft(cv: Canvas, r: Role, top: float) -> None:
    cv.color(C("gold_dk")).M(HAND[0], top).L(HAND[0], 1).stroke(0.9)


def flag(cv: Canvas, r: Role) -> None:
    shaft(cv, r, -138)
    x = HAND[0]
    cv.M(x, -137).C(x + 11, -136, x + 21, -133, x + 33, -129).C(x + 28, -126, x + 25, -123, x + 30, -118)
    cv.C(x + 20, -118, x + 10, -114, x, -109).Z()
    cv.color(C(r.banner)).fill(keep=True)
    cv.color(C("gold")).stroke(0.7)
    cv.color(C("gold")).ellipse(x, -139.5, 1.5, 1.5).fill()


def spear(cv: Canvas, r: Role) -> None:
    shaft(cv, r, -134)
    x = HAND[0]
    cv.color(C("gold")).M(x, -146).C(x + 1.9, -141, x + 1.9, -138, x, -135).C(x - 1.9, -138, x - 1.9, -141, x, -146).Z().fill()
    cv.color(C(r.banner)).M(x, -134).C(x + 2.5, -131, x + 2.2, -127, x + 1, -123).C(x + 0.4, -126, x - 0.8, -128, x - 1.4, -130).Z().fill()


def shield(cv: Canvas, r: Role, far_angle: float) -> None:
    cv.save()
    sx, sy = SHOULDER_FAR
    cv.translate(sx, sy)
    cv.rotate(math.radians(far_angle))
    cv.translate(-sx, -sy)
    cv.ellipse(-20, -50, 13, 13)
    grad(cv, -63, -37, r.robe, r.robe_dk).fill(keep=True)
    cv.color(C(r.trim)).stroke(1.0)
    cv.color(C(r.armour)).ellipse(-20, -50, 9.5, 9.5).stroke(0.8)
    cv.color(C("gold")).ellipse(-20, -50, 2.6, 2.6).fill()
    cv.restore()


def hand(cv: Canvas) -> None:
    cv.save()
    cv.translate(HAND[0] - af.HAND_CENTER[0], HAND[1] - af.HAND_CENTER[1])
    af._fist(cv)
    cv.color(C("egg")).fill()
    af._fist(cv)
    cv.color(C("skin_line"), 0.55).stroke(0.18)
    cv.restore()


# --- head -------------------------------------------------------------------------------


def head(cv: Canvas, r: Role) -> None:
    cv.color(C("egg")).M(-2.1, -83).L(2.1, -83).L(2.5, -78).L(-2.5, -78).Z().fill()
    male_face(cv)
    male_features(cv)
    getattr(sys.modules[__name__], f"_{r.helmet}")(cv, r)


def male_face(cv: Canvas) -> None:
    """A squarer jaw than the female oval; no cheek blush."""
    cv.M(0, -95).C(3.7, -95, 5.9, -92.6, 5.9, -88.8).C(5.9, -85.4, 4.8, -82.7, 2.8, -81.8)
    cv.L(-2.8, -81.8).C(-4.8, -82.7, -5.9, -85.4, -5.9, -88.8).C(-5.9, -92.6, -3.7, -95, 0, -95).Z()
    cv.color(C("egg")).fill()


def male_features(cv: Canvas) -> None:
    """Straight, firmer brows, flatter closed eyes, a nose line and a thin lip line."""
    for s in (-1, 1):
        cv.color(C("black"), 0.8).M(s * 1.1, -90.9).C(s * 2.2, -91.5, s * 3.4, -91.5, s * 4.4, -91.0)
        cv.stroke(0.52)
        cv.color(C("black")).M(s * 1.3, -88.3).C(s * 2.1, -87.9, s * 3.1, -87.9, s * 3.9, -88.3)
        cv.stroke(0.45)
    cv.color(C("skin_line"), 0.5).M(0.2, -88).C(0.5, -86.8, 0.6, -85.8, 0.1, -85.2).stroke(0.28)
    cv.color(C("vermilion_dk"), 0.85).M(-1.4, -83.8).C(-0.5, -83.65, 0.5, -83.65, 1.4, -83.8).stroke(0.42)


def face_compare(out: Path) -> None:
    """Female face (left) and male face (right), large."""
    cv = Canvas(520, 320)
    for k, draw in enumerate((lambda c: (af.face(c, FACE_STYLE, THEME.palette), af.features(c, FACE_STYLE, THEME.palette)),
                              lambda c: (male_face(c), male_features(c)))):
        cv.save()
        cv.translate(130 + k * 260, 160 + 88.5 * 18)
        cv.scale(18, 18)
        draw(cv)
        cv.restore()
    rgb, a = cv.to_premul()
    bg = np.ones((320, 520, 3), dtype=np.float32) * (np.array(PAL["deep"]) / 255)
    Image.fromarray((np.clip(rgb + bg * (1 - a[..., None]), 0, 1) * 255).astype(np.uint8)).save(out)


def _topknot_wrap(cv: Canvas, r: Role) -> None:
    cv.color(C("black")).M(-5.6, -88).C(-6.2, -94, -3.2, -97, 0, -97).C(3.2, -97, 6.2, -94, 5.6, -88)
    cv.C(4.6, -92, 2.6, -93.2, 0, -93).C(-2.6, -93.2, -4.6, -92, -5.6, -88).Z().fill()
    cv.color(C("black")).ellipse(0, -99.5, 2.8, 2.4).fill()
    cv.M(-6.1, -93.5).C(-3, -97, 3, -97, 6.1, -93.5).L(6, -90.8).C(3, -93.4, -3, -93.4, -6, -90.8).Z()
    cv.color(C(r.wrap)).fill()
    cv.color(C(r.wrap)).M(5.6, -92).C(8, -91, 9, -88, 8.6, -85).stroke(1.0)


def _viet_helmet(cv: Canvas, r: Role) -> None:
    # rounded bowl with cheek flaps, a gold brim band and a plume
    cv.M(-7.4, -86).C(-8.2, -94, -4.6, -100.5, 0, -100.5).C(4.6, -100.5, 8.2, -94, 7.4, -86)
    cv.L(5.6, -86).C(5.8, -90, 3.6, -92.4, 0, -92.4).C(-3.6, -92.4, -5.8, -90, -5.6, -86).Z()
    grad(cv, -101, -86, r.armour, "brown").fill(keep=True)
    cv.color(C("gold")).stroke(0.45)
    cv.M(-6.6, -92.6).C(-3, -95.2, 3, -95.2, 6.6, -92.6).color(C("gold")).stroke(1.0)
    cv.color(C("gold")).ellipse(0, -101.3, 1.3, 1.0).fill()
    cv.M(0, -101.5).C(-2.4, -105, -1.6, -110, 1.4, -113).C(1, -109, 2.4, -105, 0.8, -101.5).Z()
    cv.color(C(r.plume)).fill()


def _northern_helmet(cv: Canvas, r: Role) -> None:
    # pointed bowl above the brows, and a wide neck guard that flares out beside the face
    cv.M(-6.4, -91.6).C(-9, -90.5, -11.5, -87.5, -12, -83.5).L(-8.2, -84.5)
    cv.C(-7.4, -87.5, -6.8, -89.4, -6.2, -90.2).Z()
    cv.M(6.4, -91.6).C(9, -90.5, 11.5, -87.5, 12, -83.5).L(8.2, -84.5)
    cv.C(7.4, -87.5, 6.8, -89.4, 6.2, -90.2).Z()
    grad(cv, -92, -83, r.armour, "steel_dk").fill(keep=True)
    cv.color(C(r.trim)).stroke(0.45)
    cv.M(-7, -91.2).C(-7, -98, -3.4, -103, 0, -106).C(3.4, -103, 7, -98, 7, -91.2)
    cv.C(3.5, -92.4, -3.5, -92.4, -7, -91.2).Z()
    grad(cv, -106, -91, r.armour, "steel_dk").fill(keep=True)
    cv.color(C(r.trim)).stroke(0.45)
    cv.color(C(r.trim)).M(-7, -91.6).C(-3.5, -93, 3.5, -93, 7, -91.6).stroke(0.9)
    cv.color(C(r.trim)).M(0, -105.5).L(0, -93).stroke(0.4)
    cv.color(C(r.plume)).M(0, -106).C(-1.4, -108, -1.8, -110.5, 0, -112).C(1.8, -110.5, 1.4, -108, 0, -106).Z().fill()


def _cap(cv: Canvas, r: Role) -> None:
    cv.M(-6.2, -90).C(-6.4, -97, 6.4, -97, 6.2, -90).Z().color(C(r.wrap)).fill()


# --- figure -----------------------------------------------------------------------------


def figure(cv: Canvas, r: Role, x: float, base: float, h: float, facing: int, pose: str) -> None:
    lean = 18.0 if pose == "bow" else (3.0 if pose == "rally" else 0.0)
    raise_free = 125.0 if pose == "rally" else 0.0
    cv.save()
    cv.translate(x, base)
    cv.scale(facing * h / 100, h / 100)
    cape(cv, r)
    if r.prop in ("flag", "spear") and pose != "bow":
        (flag if r.prop == "flag" else spear)(cv, r)
    legs(cv, r)
    cv.save()  # the skirt below the waist stays put
    cv.rect(-60, WAIST[1], 120, 80).clip()
    body(cv, r)
    cv.restore()
    cv.save()  # the upper body leans about the waist
    cv.translate(*WAIST)
    cv.rotate(math.radians(lean))
    cv.translate(-WAIST[0], -WAIST[1])
    cv.save()
    cv.rect(-60, -140, 120, 140 + WAIST[1]).clip()
    body(cv, r)
    cv.restore()
    belt(cv, r)
    holds = r.prop in ("flag", "spear")
    far_angle = raise_free if holds else 0.0
    near_angle = raise_free if not holds else 0.0
    _arm(cv, r, far_angle, -1)
    if r.prop == "shield":
        shield(cv, r, far_angle)
    sword(cv, r)
    if holds:
        _holding_arm(cv, r)
    else:
        _arm(cv, r, near_angle if r.prop != "shield" else raise_free, 1)
    cv.save()
    cv.translate(0, -83)
    cv.rotate(math.radians(-8 if pose == "rally" else (10 if pose == "bow" else 0)))
    cv.translate(0, 83)
    head(cv, r)
    cv.restore()
    cv.restore()
    if holds and pose == "bow":
        (flag if r.prop == "flag" else spear)(cv, r)
    if holds:
        hand(cv)
    cv.restore()


def sheet(out: Path) -> None:
    cell_w, cell_h, h = 300, 640, 380
    poses = [("rest", 1), ("rest", -1), ("rally", 1), ("bow", 1)]
    rows = len(ROLES)
    ground = canvas_ground(THEME)
    img_w, img_h = cell_w * len(poses), cell_h * rows
    base = np.asarray(Image.fromarray((np.clip(ground, 0, 1) * 255).astype(np.uint8)).resize((img_w, img_h)), dtype=np.float32) / 255
    cv = Canvas(img_w, img_h)
    for ri, r in enumerate(ROLES):
        for ci, (pose, facing) in enumerate(poses):
            figure(cv, r, ci * cell_w + cell_w / 2, ri * cell_h + cell_h - 40, h, facing, pose)
    rgb, a = cv.to_premul()
    comp = rgb + base * (1 - a[..., None])
    im = Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    font = label_font(THEME)
    for ri, r in enumerate(ROLES):
        d.text((12, ri * cell_h + 10), f"{r.name} · {r.title}", font=font, fill=PAL["gold_lt"])
        for ci, (pose, facing) in enumerate(poses):
            d.text((ci * cell_w + 12, ri * cell_h + 40), f"{pose} {'→' if facing > 0 else '←'}", font=font, fill=PAL["gold_dk"])
    im.save(out)


if __name__ == "__main__":
    sheet(Path(sys.argv[1]))
    face_compare(Path(sys.argv[1]).with_name("faces.png"))
