"""Stylised folk-lacquer female figure. Local frame: feet at (0,0), height 100 units, y up = negative."""
from lac import P

ROLE = {
    "leader":  dict(robe=P["vermilion"], robe_dk=P["vermilion_dk"], trim=P["gold"], wrap=P["gold"], crown=True, prop="flag"),
    "general": dict(robe=P["vermilion_dk"], robe_dk=(70, 14, 10), trim=P["gold_dk"], wrap=P["vermilion"], crown=False, prop="spear"),
    "general_b": dict(robe=P["brown"], robe_dk=(56, 28, 16), trim=P["vermilion"], wrap=P["vermilion"], crown=False, prop="spear"),
    "boatwoman": dict(robe=P["jade"], robe_dk=(30, 50, 42), trim=P["gold_dk"], wrap=P["vermilion"], crown=False, prop="oar"),
}


def _hair_back(cv):
    cv.color(P["black"]).M(-6.6, -92).C(-8.8, -84, -9.2, -74, -7.6, -67).C(-3, -64.5, 3, -64.5, 7.6, -67) \
        .C(9.2, -74, 8.8, -84, 6.6, -92).Z().fill()


def _prop_back(cv, kind, t):
    gold, ver = P["gold"], P["vermilion"]
    if kind in ("spear", "flag"):
        top = -134 if kind == "spear" else -136
        cv.color(P["gold_dk"]).M(17, top).L(17, 1).stroke(0.9)
    if kind == "spear":
        cv.color(gold).M(17, -144).C(18.9, -139, 18.9, -136, 17, -133).C(15.1, -136, 15.1, -139, 17, -144).Z().fill()
        cv.color(P["gold_dk"]).M(17, -142).L(17, -134.5).stroke(0.25)
        cv.color(ver).M(17, -132).C(19.5, -129, 19.2, -125, 18, -121).C(17.4, -124, 16.2, -126, 15.6, -128) \
            .C(15.4, -130, 16, -131.5, 17, -132).Z().fill()
        cv.color(gold).ellipse(17, -133, 1.2, 0.7).fill()
    elif kind == "flag":
        cv.color(gold).ellipse(17, -137.5, 1.5, 1.5).fill()
        flag = lambda: cv.M(17, -135).C(28, -134, 38, -131, 50, -127).C(45, -124, 42, -121, 47, -116) \
            .C(37, -116, 27, -112, 17, -107).Z()
        flag(); cv.color(ver).fill()
        flag(); cv.color(gold).stroke(0.7)
        cv.color(gold).M(20, -131).C(28, -129.5, 35, -127.5, 41, -125.5).stroke(0.35)
        cv.M(20, -112).C(27, -114.5, 33, -116, 39, -117).stroke(0.35)
        cv.color(gold).ellipse(29, -121.5, 2.6, 2.6).stroke(0.5)
    elif kind == "oar":
        cv.color(P["gold_dk"]).M(19, -78).L(26, 6).stroke(1.0)
        cv.color(P["brown_lt"]).M(25, 0).C(28, 4, 29, 12, 27.5, 16).C(25.5, 14, 24, 6, 25, 0).Z().fill()


def _robe(cv, t):
    def body():
        cv.M(-12, -79).C(-14, -70, -13, -62, -11, -55).C(-15, -38, -21, -18, -25, -1.5) \
            .C(-12, 1.5, 12, 1.5, 25, -1.5).C(21, -18, 15, -38, 11, -55) \
            .C(13, -62, 14, -70, 12, -79).C(8, -82, -8, -82, -12, -79).Z()
    body(); cv.vgrad(-80, 0, [(0, t["robe"], 1), (0.7, t["robe"], 1), (1, t["robe_dk"], 1)]).fill()
    # back fold shading
    cv.color(t["robe_dk"], 0.55).M(-11, -55).C(-15, -38, -20, -18, -23, -1).C(-19, -2, -16, -2, -14, -1.5) \
        .C(-14, -20, -12, -38, -9, -54).Z().fill()
    # under-robe panel (áo trong) peeking at front
    cv.color(P["egg"]).M(-4.2, -81).L(0, -73.5).L(4.2, -81).C(1.5, -81.8, -1.5, -81.8, -4.2, -81).Z().fill()
    # hem band
    cv.color(t["trim"]).M(-24.2, -4.5).C(-12, -1.8, 12, -1.8, 24.2, -4.5).stroke(2.2)
    for k in range(-9, 10):
        x = k * 2.5
        cv.color(P["egg"] if t["trim"] != P["gold"] else P["vermilion"]).ellipse(x, -3.3 + abs(x) * 0.02, 0.45, 0.45).fill()
    # overlapping lapel (giao lĩnh)
    cv.color(t["trim"]).M(-5, -81).C(0, -72, 4, -63, 6.5, -56).C(7.5, -38, 8.5, -18, 9.5, -0.5).stroke(1.6)
    cv.color(P["gold_lt"], 0.8).M(5, -81).C(2.5, -78, 1, -76.5, 0.4, -74.8).stroke(0.6)
    body(); cv.color(P["gold"]).stroke(0.55)


def _sleeves(cv, t, prop):
    # far arm hangs, hand hidden
    def far():
        cv.M(-12, -78).C(-19, -70, -22.5, -55, -21.5, -44).C(-19, -41, -13.5, -41, -10.5, -44.5) \
            .C(-10.5, -55, -9.5, -66, -8, -72).Z()
    far(); cv.vgrad(-78, -41, [(0, t["robe"], 1), (1, t["robe_dk"], 1)]).fill()
    cv.color(t["trim"]).M(-21.5, -44).C(-19, -41.2, -13.5, -41.2, -10.5, -44.5).stroke(1.4)
    far(); cv.color(P["gold"]).stroke(0.5)
    # near arm: holds prop at x=17
    if prop in ("spear", "flag", "oar"):
        def near():
            cv.M(12, -78).C(18, -73, 21.5, -65, 20.5, -58).C(18.5, -54.5, 14.5, -54.5, 12.5, -57) \
                .C(12.3, -63, 11.3, -70, 9.5, -74).Z()
        near(); cv.vgrad(-78, -54, [(0, t["robe"], 1), (1, t["robe_dk"], 1)]).fill()
        cv.color(t["trim"]).M(20.5, -58).C(18.5, -54.8, 14.5, -54.8, 12.5, -57).stroke(1.3)
        near(); cv.color(P["gold"]).stroke(0.5)
        if prop in ("spear", "flag"):
            top = -134 if prop == "spear" else -136
            cv.color(P["gold_dk"]).M(17, top).L(17, 1).stroke(0.9)
            cv.color(P["gold_lt"], 0.5).M(16.8, top).L(16.8, 1).stroke(0.25)
        def hand():
            cv.M(15.0, -62.4).C(15.6, -63.6, 18.6, -63.8, 19.4, -62.4).C(19.9, -61.0, 19.7, -59.0, 18.9, -58.0) \
                .C(18.0, -57.2, 16.0, -57.4, 15.3, -58.4).C(14.8, -59.6, 14.7, -61.2, 15.0, -62.4).Z()
        hand(); cv.color(P["egg"]).fill()
        hand(); cv.color(P["skin_line"], 0.55).stroke(0.18)
        for fy in (-61.4, -60.1, -58.8):
            cv.color(P["skin_line"], 0.5).M(16.6, fy).C(17.6, fy + 0.25, 18.6, fy + 0.25, 19.4, fy - 0.1).stroke(0.16)
        cv.color(P["skin_line"], 0.5).M(15.4, -61.8).C(16.2, -61.0, 16.4, -60.0, 16.0, -59.2).stroke(0.16)
    else:
        def near():
            cv.M(12, -78).C(19, -70, 22.5, -55, 21.5, -44).C(19, -41, 13.5, -41, 10.5, -44.5) \
                .C(10.5, -55, 9.5, -66, 8, -72).Z()
        near(); cv.color(t["robe"]).fill()
        near(); cv.color(P["gold"]).stroke(0.5)


def _belt(cv, t):
    cv.color(t["trim"]).M(-11.4, -56.6).C(-4, -55.4, 4, -55.4, 11.4, -56.6).L(11.2, -53.6) \
        .C(4, -52.4, -4, -52.4, -11.2, -53.6).Z().fill()
    cv.color(P["gold_lt"], 0.9).M(-11.3, -56.5).C(-4, -55.3, 4, -55.3, 11.3, -56.5).stroke(0.3)
    ribbon = t["wrap"] if t["wrap"] != t["trim"] else P["vermilion"]
    cv.color(ribbon).M(-1, -54).C(-3, -46, -1.5, -38, -3.8, -29).C(-2.6, -29.6, -1.6, -29.4, -0.8, -28.5) \
        .C(0.4, -37, -0.6, -46, 0.6, -54).Z().fill()
    cv.color(ribbon).M(1.4, -54).C(2.6, -47, 4.8, -40, 4.2, -32).C(5.2, -32.6, 6, -32.2, 6.4, -31.4) \
        .C(6.2, -40, 4.6, -47, 3, -54).Z().fill()
    cv.color(P["gold"]).ellipse(0.8, -54.6, 1.6, 1.3).fill()


def _head(cv, t):
    cv.color(P["egg"]).M(-1.9, -83).L(1.9, -83).L(2.2, -78.5).L(-2.2, -78.5).Z().fill()
    cv.color(P["skin_line"], 0.25).M(-1.9, -80.2).C(0, -79.4, 0, -79.4, 1.9, -80.2).stroke(0.3)
    # face
    cv.M(0, -95).C(3.4, -95, 5.4, -92.5, 5.4, -88.5).C(5.4, -84.6, 3, -81.7, 0, -81.7) \
        .C(-3, -81.7, -5.4, -84.6, -5.4, -88.5).C(-5.4, -92.5, -3.4, -95, 0, -95).Z()
    cv.color(P["egg"]).fill()
    cv.color(P["pink"], 0.22).ellipse(-3, -85.8, 1.6, 1.0).fill()
    cv.color(P["pink"], 0.22).ellipse(3, -85.8, 1.6, 1.0).fill()
    # brows, eyes (downcast), nose, lips
    ln = P["skin_line"]
    for s in (-1, 1):
        cv.color(ln, 0.85).M(s * 1.1, -90.7).C(s * 2.2, -91.5, s * 3.3, -91.4, s * 4.1, -90.6).stroke(0.32)
        cv.color(P["black"]).M(s * 1.1, -88.4).C(s * 1.9, -87.5, s * 3.1, -87.5, s * 3.9, -88.3).stroke(0.45)
        cv.color(P["black"], 0.5).M(s * 3.9, -88.3).L(s * 4.3, -88.6).stroke(0.3)
    cv.color(ln, 0.45).M(0.1, -87.6).C(0.4, -86.6, 0.5, -85.9, 0.1, -85.3).stroke(0.25)
    cv.color(P["vermilion"]).M(-1.3, -83.9).C(-0.6, -84.5, 0.6, -84.5, 1.3, -83.9) \
        .C(0.6, -83.1, -0.6, -83.1, -1.3, -83.9).Z().fill()
    # hair front with centre parting
    cv.color(P["black"]).M(-5.6, -87.5).C(-6.3, -93.5, -3.2, -97, 0, -97).C(3.2, -97, 6.3, -93.5, 5.6, -87.5) \
        .C(4.9, -91.5, 2.6, -93, 0.1, -92.6).C(-2.6, -93, -4.9, -91.5, -5.6, -87.5).Z().fill()
    cv.color(P["gold"], 0.45).M(-3.5, -95.4).C(-1.5, -96.4, 1.5, -96.4, 3.5, -95.4).stroke(0.3)
    # bun + hairpin
    cv.color(P["black"]).ellipse(0, -99.6, 3.6, 2.7).fill()
    cv.color(P["gold"]).M(-5.4, -100.6).L(5.6, -99.2).stroke(0.45)
    cv.color(P["gold_lt"]).ellipse(5.8, -99.2, 0.7, 0.7).fill()
    # headwrap (khăn vấn)
    def wrap():
        cv.M(-5.9, -93.2).C(-3, -96, 3, -96, 5.9, -93.2).L(5.8, -91.0).C(3, -93.4, -3, -93.4, -5.8, -91.0).Z()
    wrap(); cv.color(t["wrap"]).fill()
    wrap(); cv.color(P["gold_dk"]).stroke(0.25)
    if t["crown"]:
        def fan():
            cv.M(-4.6, -101.2).C(-5.4, -105.5, -2.6, -109.4, 0, -109.8).C(2.6, -109.4, 5.4, -105.5, 4.6, -101.2) \
                .C(2.2, -102.4, -2.2, -102.4, -4.6, -101.2).Z()
        fan(); cv.color(P["gold"]).fill()
        for a in (-3.2, -1.6, 0, 1.6, 3.2):
            cv.color(P["gold_dk"]).M(a * 0.55, -102.2).L(a, -108.2).stroke(0.22)
        fan(); cv.color(P["gold_dk"]).stroke(0.25)
        cv.color(P["vermilion"]).ellipse(0, -103.6, 1.0, 1.0).fill()
        cv.color(P["gold_lt"]).ellipse(0, -109.8, 0.8, 0.8).fill()


def figure(cv, x, feet_y, height, role="general", facing=1):
    """Draw one character. facing: +1 = prop on the right, -1 = prop on the left."""
    t = ROLE[role]
    u = height / 100.0
    cv.save()
    cv.translate(x, feet_y)
    cv.scale(facing * u, u)
    _hair_back(cv)
    _prop_back(cv, t["prop"], t)
    _robe(cv, t)
    _belt(cv, t)
    _sleeves(cv, t, t["prop"])
    _head(cv, t)
    cv.restore()
