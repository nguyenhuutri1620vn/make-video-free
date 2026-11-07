"""Drawing parts of the stylised folk-lacquer female figure (FR-40 to FR-46).

Local frame: feet at (0, 0), height 100 units, y up is negative. Every function draws one
part with the signature ``(cv, style, palette)``; ``figure.draw_figure`` calls them in the
FR-41 order. Proportions are named constants; path control points are geometry copied from
the approved prototype. Colours come only from ``palette`` or ``style``.
"""

from __future__ import annotations

from typing import Final

from history_shorts.canvas import Canvas
from history_shorts.characters.roles import CharacterStyle
from history_shorts.config import Palette
from history_shorts.primitives import Point

# Proportions (local units).
HEAD_CENTER_Y: Final = -88.5
SHOULDER_Y: Final = -79
WAIST_Y: Final = -55
HEM_HALF_WIDTH: Final = 25
PROP_X: Final = 17
HAND_CENTER: Final[Point] = (17.3, -60.5)
SPEAR_TOP: Final = -134
FLAG_TOP: Final = -136
OAR_SHAFT: Final[tuple[Point, Point]] = ((15.07, -78.0), (25.76, 6.0))
OAR_BLADE_TOP: Final[Point] = (25.0, 0.0)

# The front part of the oar shaft is redrawn over the near arm between these two heights.
OAR_GRIP_Y: Final = (-66.0, -55.0)
SHAFT_BOTTOM: Final = 1
HEM_DOT_COUNT_HALF: Final = 9
HEM_DOT_SPACING: Final = 2.5
HEM_DOT_RADIUS: Final = 0.45


def shaft_segment(prop: str) -> tuple[Point, Point] | None:
    """End points of the prop shaft in the local frame, or None when there is no prop."""
    if prop == "flag":
        return ((PROP_X, FLAG_TOP), (PROP_X, SHAFT_BOTTOM))
    if prop == "spear":
        return ((PROP_X, SPEAR_TOP), (PROP_X, SHAFT_BOTTOM))
    if prop == "oar":
        return OAR_SHAFT
    return None


def _oar_x(y: float) -> float:
    (x0, y0), (x1, y1) = OAR_SHAFT
    return x0 + (y - y0) / (y1 - y0) * (x1 - x0)


# --------------------------------------------------------------------------------------
# Hair, props
# --------------------------------------------------------------------------------------


def hair_back(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(palette["black"]).M(-6.6, -92).C(-8.8, -84, -9.2, -74, -7.6, -67).C(
        -3, -64.5, 3, -64.5, 7.6, -67
    ).C(9.2, -74, 8.8, -84, 6.6, -92).Z().fill()


def _spear_head(cv: Canvas, palette: Palette) -> None:
    gold, vermilion = palette["gold"], palette["vermilion"]
    cv.color(gold).M(17, -144).C(18.9, -139, 18.9, -136, 17, -133).C(
        15.1, -136, 15.1, -139, 17, -144
    )
    cv.Z().fill()
    cv.color(palette["gold_dk"]).M(17, -142).L(17, -134.5).stroke(0.25)
    cv.color(vermilion).M(17, -132).C(19.5, -129, 19.2, -125, 18, -121).C(
        17.4, -124, 16.2, -126, 15.6, -128
    ).C(15.4, -130, 16, -131.5, 17, -132).Z().fill()
    cv.color(gold).ellipse(17, -133, 1.2, 0.7).fill()


def _flag_cloth(cv: Canvas) -> None:
    cv.M(17, -135).C(28, -134, 38, -131, 50, -127).C(45, -124, 42, -121, 47, -116).C(
        37, -116, 27, -112, 17, -107
    ).Z()


def _flag(cv: Canvas, palette: Palette) -> None:
    gold = palette["gold"]
    cv.color(gold).ellipse(17, -137.5, 1.5, 1.5).fill()
    _flag_cloth(cv)
    cv.color(palette["vermilion"]).fill()
    _flag_cloth(cv)
    cv.color(gold).stroke(0.7)
    cv.color(gold).M(20, -131).C(28, -129.5, 35, -127.5, 41, -125.5).stroke(0.35)
    cv.M(20, -112).C(27, -114.5, 33, -116, 39, -117).stroke(0.35)
    cv.color(gold).ellipse(29, -121.5, 2.6, 2.6).stroke(0.5)


def _oar(cv: Canvas, palette: Palette) -> None:
    (x0, y0), (x1, y1) = OAR_SHAFT
    cv.color(palette["gold_dk"]).M(x0, y0).L(x1, y1).stroke(1.0)
    bx, by = OAR_BLADE_TOP
    cv.color(palette["brown_lt"]).M(bx, by).C(28, 4, 29, 12, 27.5, 16).C(
        25.5, 14, 24, 6, bx, by
    ).Z()
    cv.fill()


def prop_back(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Shaft and head of the prop behind the body."""
    segment = shaft_segment(style.prop)
    if segment is not None and style.prop != "oar":
        (x0, y0), (x1, y1) = segment
        cv.color(palette["gold_dk"]).M(x0, y0).L(x1, y1).stroke(0.9)
    if style.prop == "spear":
        _spear_head(cv, palette)
    elif style.prop == "flag":
        _flag(cv, palette)
    elif style.prop == "oar":
        _oar(cv, palette)


def prop_front(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Shaft segment drawn over the near arm so the hand visibly grips the prop."""
    segment = shaft_segment(style.prop)
    if segment is not None and style.prop != "oar":
        (x0, y0), (x1, y1) = segment
        cv.color(palette["gold_dk"]).M(x0, y0).L(x1, y1).stroke(0.9)
        cv.color(palette["gold_lt"], 0.5).M(x0 - 0.2, y0).L(x1 - 0.2, y1).stroke(0.25)
    elif style.prop == "oar":
        top, bottom = OAR_GRIP_Y
        cv.color(palette["gold_dk"]).M(_oar_x(top), top).L(_oar_x(bottom), bottom).stroke(0.9)
        cv.color(palette["gold_lt"], 0.5).M(_oar_x(top) - 0.2, top).L(
            _oar_x(bottom) - 0.2, bottom
        ).stroke(0.25)


# --------------------------------------------------------------------------------------
# Body
# --------------------------------------------------------------------------------------


def _robe_body(cv: Canvas) -> None:
    cv.M(-12, -79).C(-14, -70, -13, -62, -11, -55).C(-15, -38, -21, -18, -25, -1.5).C(
        -12, 1.5, 12, 1.5, 25, -1.5
    ).C(21, -18, 15, -38, 11, -55).C(13, -62, 14, -70, 12, -79).C(8, -82, -8, -82, -12, -79).Z()


def _hem(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(style.trim).M(-24.2, -4.5).C(-12, -1.8, 12, -1.8, 24.2, -4.5).stroke(2.2)
    dot = palette["vermilion"] if style.trim_is_gold else palette["egg"]
    for k in range(-HEM_DOT_COUNT_HALF, HEM_DOT_COUNT_HALF + 1):
        x = k * HEM_DOT_SPACING
        cv.color(dot).ellipse(x, -3.3 + abs(x) * 0.02, HEM_DOT_RADIUS, HEM_DOT_RADIUS).fill()


def robe(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    _robe_body(cv)
    cv.vgrad(-80, 0, [(0, style.robe, 1), (0.7, style.robe, 1), (1, style.robe_dk, 1)]).fill()
    cv.color(style.robe_dk, 0.55).M(-11, -55).C(-15, -38, -20, -18, -23, -1).C(
        -19, -2, -16, -2, -14, -1.5
    ).C(-14, -20, -12, -38, -9, -54).Z().fill()
    # under-robe panel (ao trong) peeking at the front
    cv.color(palette["egg"]).M(-4.2, -81).L(0, -73.5).L(4.2, -81).C(
        1.5, -81.8, -1.5, -81.8, -4.2, -81
    )
    cv.Z().fill()
    _hem(cv, style, palette)
    # overlapping lapel (giao linh)
    cv.color(style.trim).M(-5, -81).C(0, -72, 4, -63, 6.5, -56).C(7.5, -38, 8.5, -18, 9.5, -0.5)
    cv.stroke(1.6)
    cv.color(palette["gold_lt"], 0.8).M(5, -81).C(2.5, -78, 1, -76.5, 0.4, -74.8).stroke(0.6)
    _robe_body(cv)
    cv.color(palette["gold"]).stroke(0.55)


def belt(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(style.trim).M(-11.4, -56.6).C(-4, -55.4, 4, -55.4, 11.4, -56.6).L(11.2, -53.6).C(
        4, -52.4, -4, -52.4, -11.2, -53.6
    ).Z().fill()
    cv.color(palette["gold_lt"], 0.9).M(-11.3, -56.5).C(-4, -55.3, 4, -55.3, 11.3, -56.5).stroke(
        0.3
    )
    ribbon = style.wrap if style.wrap != style.trim else palette["vermilion"]
    cv.color(ribbon).M(-1, -54).C(-3, -46, -1.5, -38, -3.8, -29).C(
        -2.6, -29.6, -1.6, -29.4, -0.8, -28.5
    ).C(0.4, -37, -0.6, -46, 0.6, -54).Z().fill()
    cv.color(ribbon).M(1.4, -54).C(2.6, -47, 4.8, -40, 4.2, -32).C(
        5.2, -32.6, 6, -32.2, 6.4, -31.4
    ).C(6.2, -40, 4.6, -47, 3, -54).Z().fill()
    cv.color(palette["gold"]).ellipse(0.8, -54.6, 1.6, 1.3).fill()


# --------------------------------------------------------------------------------------
# Arms and hand
# --------------------------------------------------------------------------------------


def _far_arm(cv: Canvas) -> None:
    cv.M(-12, -78).C(-19, -70, -22.5, -55, -21.5, -44).C(-19, -41, -13.5, -41, -10.5, -44.5).C(
        -10.5, -55, -9.5, -66, -8, -72
    ).Z()


def _holding_arm(cv: Canvas) -> None:
    cv.M(12, -78).C(18, -73, 21.5, -65, 20.5, -58).C(18.5, -54.5, 14.5, -54.5, 12.5, -57).C(
        12.3, -63, 11.3, -70, 9.5, -74
    ).Z()


def _hanging_arm(cv: Canvas) -> None:
    cv.M(12, -78).C(19, -70, 22.5, -55, 21.5, -44).C(19, -41, 13.5, -41, 10.5, -44.5).C(
        10.5, -55, 9.5, -66, 8, -72
    ).Z()


def sleeves(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Both arm shapes; the near arm holds the prop or hangs when there is none."""
    _far_arm(cv)
    cv.vgrad(-78, -41, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()
    cv.color(style.trim).M(-21.5, -44).C(-19, -41.2, -13.5, -41.2, -10.5, -44.5).stroke(1.4)
    _far_arm(cv)
    cv.color(palette["gold"]).stroke(0.5)
    if style.prop == "none":
        _hanging_arm(cv)
        cv.color(style.robe).fill()
        _hanging_arm(cv)
        cv.color(palette["gold"]).stroke(0.5)
        return
    _holding_arm(cv)
    cv.vgrad(-78, -54, [(0, style.robe, 1), (1, style.robe_dk, 1)]).fill()
    cv.color(style.trim).M(20.5, -58).C(18.5, -54.8, 14.5, -54.8, 12.5, -57).stroke(1.3)
    _holding_arm(cv)
    cv.color(palette["gold"]).stroke(0.5)


def _fist(cv: Canvas) -> None:
    cv.M(15.0, -62.4).C(15.6, -63.6, 18.6, -63.8, 19.4, -62.4).C(
        19.9, -61.0, 19.7, -59.0, 18.9, -58.0
    ).C(18.0, -57.2, 16.0, -57.4, 15.3, -58.4).C(14.8, -59.6, 14.7, -61.2, 15.0, -62.4).Z()


def hand(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Closed fist with finger and thumb lines; only drawn when a prop is held."""
    if style.prop == "none":
        return
    _fist(cv)
    cv.color(palette["egg"]).fill()
    _fist(cv)
    cv.color(palette["skin_line"], 0.55).stroke(0.18)
    for fy in (-61.4, -60.1, -58.8):
        cv.color(palette["skin_line"], 0.5).M(16.6, fy).C(
            17.6, fy + 0.25, 18.6, fy + 0.25, 19.4, fy - 0.1
        )
        cv.stroke(0.16)
    cv.color(palette["skin_line"], 0.5).M(15.4, -61.8).C(
        16.2, -61.0, 16.4, -60.0, 16.0, -59.2
    ).stroke(0.16)


# --------------------------------------------------------------------------------------
# Head
# --------------------------------------------------------------------------------------


def neck(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(palette["egg"]).M(-1.9, -83).L(1.9, -83).L(2.2, -78.5).L(-2.2, -78.5).Z().fill()
    cv.color(palette["skin_line"], 0.25).M(-1.9, -80.2).C(0, -79.4, 0, -79.4, 1.9, -80.2).stroke(
        0.3
    )


def face(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.M(0, -95).C(3.4, -95, 5.4, -92.5, 5.4, -88.5).C(5.4, -84.6, 3, -81.7, 0, -81.7).C(
        -3, -81.7, -5.4, -84.6, -5.4, -88.5
    ).C(-5.4, -92.5, -3.4, -95, 0, -95).Z()
    cv.color(palette["egg"]).fill()
    cv.color(palette["pink"], 0.22).ellipse(-3, -85.8, 1.6, 1.0).fill()
    cv.color(palette["pink"], 0.22).ellipse(3, -85.8, 1.6, 1.0).fill()


def features(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Brows, downcast closed eyes with tails, nose line and lips; nothing else (FR-43)."""
    line = palette["skin_line"]
    for s in (-1, 1):
        cv.color(line, 0.85).M(s * 1.1, -90.7).C(
            s * 2.2, -91.5, s * 3.3, -91.4, s * 4.1, -90.6
        ).stroke(0.32)
        cv.color(palette["black"]).M(s * 1.1, -88.4).C(
            s * 1.9, -87.5, s * 3.1, -87.5, s * 3.9, -88.3
        )
        cv.stroke(0.45)
        cv.color(palette["black"], 0.5).M(s * 3.9, -88.3).L(s * 4.3, -88.6).stroke(0.3)
    cv.color(line, 0.45).M(0.1, -87.6).C(0.4, -86.6, 0.5, -85.9, 0.1, -85.3).stroke(0.25)
    cv.color(palette["vermilion"]).M(-1.3, -83.9).C(-0.6, -84.5, 0.6, -84.5, 1.3, -83.9).C(
        0.6, -83.1, -0.6, -83.1, -1.3, -83.9
    ).Z().fill()


def hair_front(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Front hair with centre parting; no loose side locks."""
    cv.color(palette["black"]).M(-5.6, -87.5).C(-6.3, -93.5, -3.2, -97, 0, -97).C(
        3.2, -97, 6.3, -93.5, 5.6, -87.5
    ).C(4.9, -91.5, 2.6, -93, 0.1, -92.6).C(-2.6, -93, -4.9, -91.5, -5.6, -87.5).Z().fill()
    cv.color(palette["gold"], 0.45).M(-3.5, -95.4).C(-1.5, -96.4, 1.5, -96.4, 3.5, -95.4).stroke(
        0.3
    )


def bun(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    cv.color(palette["black"]).ellipse(0, -99.6, 3.6, 2.7).fill()
    cv.color(palette["gold"]).M(-5.4, -100.6).L(5.6, -99.2).stroke(0.45)
    cv.color(palette["gold_lt"]).ellipse(5.8, -99.2, 0.7, 0.7).fill()


def _wrap_band(cv: Canvas) -> None:
    cv.M(-5.9, -93.2).C(-3, -96, 3, -96, 5.9, -93.2).L(5.8, -91.0).C(
        3, -93.4, -3, -93.4, -5.8, -91.0
    ).Z()


def headwrap(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    _wrap_band(cv)
    cv.color(style.wrap).fill()
    _wrap_band(cv)
    cv.color(palette["gold_dk"]).stroke(0.25)


def _fan(cv: Canvas) -> None:
    cv.M(-4.6, -101.2).C(-5.4, -105.5, -2.6, -109.4, 0, -109.8).C(
        2.6, -109.4, 5.4, -105.5, 4.6, -101.2
    ).C(2.2, -102.4, -2.2, -102.4, -4.6, -101.2).Z()


def crest(cv: Canvas, style: CharacterStyle, palette: Palette) -> None:
    """Gold fan crest; only drawn when the style asks for it."""
    if not style.crest:
        return
    _fan(cv)
    cv.color(palette["gold"]).fill()
    for a in (-3.2, -1.6, 0, 1.6, 3.2):
        cv.color(palette["gold_dk"]).M(a * 0.55, -102.2).L(a, -108.2).stroke(0.22)
    _fan(cv)
    cv.color(palette["gold_dk"]).stroke(0.25)
    cv.color(palette["vermilion"]).ellipse(0, -103.6, 1.0, 1.0).fill()
    cv.color(palette["gold_lt"]).ellipse(0, -109.8, 0.8, 0.8).fill()
