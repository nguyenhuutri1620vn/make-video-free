"""Reusable scene elements drawn with Cairo."""
from lac import P, Canvas


def cloud_path(cv, x, y, s, flip=1):
    cv.save(); cv.translate(x, y); cv.scale(s * flip, s)
    cv.M(-62, 0).C(-74, -18, -56, -36, -38, -27).C(-36, -48, -6, -54, 4, -35) \
        .C(14, -52, 46, -48, 47, -27).C(64, -35, 80, -16, 66, 0).C(30, 6, -26, 6, -62, 0).Z()
    cv.restore()


def cloud_lines(cv, x, y, s, flip=1, color=P["gold"]):
    cv.save(); cv.translate(x, y); cv.scale(s * flip, s)
    cv.color(color).M(-62, 0).C(-74, -18, -56, -36, -38, -27).C(-36, -48, -6, -54, 4, -35) \
        .C(14, -52, 46, -48, 47, -27).C(64, -35, 80, -16, 66, 0).C(30, 6, -26, 6, -62, 0).Z().stroke(2.2 / s)
    cv.color(color).M(-38, -27).C(-30, -22, -30, -12, -40, -10).stroke(1.6 / s)
    cv.M(4, -35).C(10, -28, 8, -18, -2, -17).stroke(1.6 / s)
    cv.M(47, -27).C(52, -20, 50, -12, 42, -11).stroke(1.6 / s)
    cv.restore()


def far_mountains(cv, y, amp=1.0):
    cv.M(0, y + 80 * amp).C(80, y - 20 * amp, 140, y - 90 * amp, 210, y - 40 * amp) \
        .C(270, y + 5 * amp, 320, y - 60 * amp, 410, y - 20 * amp) \
        .C(480, y + 15 * amp, 560, y - 100 * amp, 650, y - 50 * amp) \
        .C(730, y - 5 * amp, 790, y - 80 * amp, 880, y - 40 * amp) \
        .C(960, y - 5 * amp, 1020, y - 70 * amp, 1080, y - 30 * amp).L(1080, y + 220).L(0, y + 220).Z()


def far_ridge(cv, y, amp=1.0):
    cv.M(0, y + 80 * amp).C(80, y - 20 * amp, 140, y - 90 * amp, 210, y - 40 * amp) \
        .C(270, y + 5 * amp, 320, y - 60 * amp, 410, y - 20 * amp) \
        .C(480, y + 15 * amp, 560, y - 100 * amp, 650, y - 50 * amp) \
        .C(730, y - 5 * amp, 790, y - 80 * amp, 880, y - 40 * amp) \
        .C(960, y - 5 * amp, 1020, y - 70 * amp, 1080, y - 30 * amp)


def hill_left(cv, base, top):
    cv.M(0, base).L(0, top + 40).C(60, top - 10, 150, top - 20, 220, top + 60) \
        .C(260, top + 110, 300, base - 40, 340, base).Z()


def hill_right(cv, base, top):
    cv.M(1080, base).L(1080, top + 20).C(1010, top - 30, 930, top - 10, 860, top + 70) \
        .C(820, top + 120, 780, base - 40, 740, base).Z()


def waves(cv, y0, rows=4, width=1080, step=104, color_a=P["gold"], color_b=P["gold_dk"]):
    for r in range(rows):
        y = y0 + r * 46
        off = 0 if r % 2 == 0 else step / 2
        c = color_a if r % 2 == 0 else color_b
        x = -step + off
        while x < width + step:
            for k, rr in enumerate((46, 32, 18)):
                cv.color(c, 0.9 - k * 0.15).M(x - rr, y).C(x - rr, y - rr * 1.1, x + rr, y - rr * 1.1, x + rr, y).stroke(2.0)
            x += step


def ground_band(cv, y, h=52):
    cv.vgrad(y, y + h, [(0, P["vermilion_dk"], 1), (1, P["black"], 1)]).rect(0, y, 1080, h).fill()
    cv.color(P["gold"]).M(0, y).L(1080, y).stroke(3)
    x = -40
    while x < 1120:
        cv.color(P["gold_dk"]).M(x, y + 34).C(x + 10, y + 12, x + 46, y + 12, x + 56, y + 30) \
            .C(x + 60, y + 38, x + 48, y + 44, x + 42, y + 36).stroke(2)
        x += 120


def lotus(cv, x, y, s, open_=1.0):
    import math as _m
    cv.save(); cv.translate(x, y); cv.scale(s, s)
    # leaf
    cv.vgrad(-6, 16, [(0, P["jade"], 1), (1, (24, 40, 34), 1)]).ellipse(0, 6, 46, 11).fill()
    cv.color(P["gold"]).ellipse(0, 6, 46, 11).stroke(1.2)
    for a in (-30, -15, 0, 15, 30):
        cv.color(P["gold_dk"]).M(0, 6).L(a * 1.4, 6 + (8 if a else 0) * 0).stroke(0.8)
    def petal(rot, length, width, fill):
        cv.save(); cv.rotate(_m.radians(rot))
        cv.M(0, 0).C(-width, -length * 0.35, -width * 0.7, -length * 0.85, 0, -length) \
            .C(width * 0.7, -length * 0.85, width, -length * 0.35, 0, 0).Z()
        cv.vgrad(-length, 0, [(0, (240, 170, 150), 1), (0.45, fill, 1), (1, P["vermilion_dk"], 1)]).fill()
        cv.M(0, 0).C(-width, -length * 0.35, -width * 0.7, -length * 0.85, 0, -length) \
            .C(width * 0.7, -length * 0.85, width, -length * 0.35, 0, 0).Z()
        cv.color(P["gold"]).stroke(1.0)
        cv.color(P["gold_dk"], 0.6).M(0, -2).L(0, -length * 0.8).stroke(0.5)
        cv.restore()
    for r in (-62 * open_, 62 * open_):
        petal(r, 34, 13, P["vermilion_dk"])
    for r in (-32 * open_, 32 * open_):
        petal(r, 42, 15, P["vermilion"])
    petal(0, 48, 16, P["vermilion"])
    cv.restore()


def karst(cv, y, peaks):
    """Limestone peaks: list of (x, height, width)."""
    cv.M(0, y)
    for px, ph, pw in peaks:
        cv.L(px - pw, y).C(px - pw * 0.6, y - ph * 0.5, px - pw * 0.55, y - ph, px, y - ph) \
            .C(px + pw * 0.55, y - ph, px + pw * 0.6, y - ph * 0.5, px + pw, y)
    cv.L(1080, y).L(1080, y + 400).L(0, y + 400).Z()


def karst_ridge(cv, y, peaks):
    for px, ph, pw in peaks:
        cv.M(px - pw, y).C(px - pw * 0.6, y - ph * 0.5, px - pw * 0.55, y - ph, px, y - ph) \
            .C(px + pw * 0.55, y - ph, px + pw * 0.6, y - ph * 0.5, px + pw, y)


def boat(cv, x, y, s):
    cv.save(); cv.translate(x, y); cv.scale(s, s)
    def hull():
        cv.M(-70, -10).C(-40, 8, 40, 8, 74, -14).C(60, 6, 30, 16, 0, 16).C(-30, 16, -58, 8, -70, -10).Z()
    hull(); cv.vgrad(-14, 16, [(0, P["brown_lt"], 1), (1, (40, 20, 12), 1)]).fill()
    hull(); cv.color(P["gold"]).stroke(1.4)
    cv.color(P["gold"]).M(-62, -4).C(-30, 7, 30, 7, 66, -8).stroke(0.8)
    cv.color(P["gold_lt"]).ellipse(62, -6, 2.4, 2.4).fill()
    cv.restore()


def bird(cv, x, y, s, color=P["gold"]):
    cv.save(); cv.translate(x, y); cv.scale(s, s)
    cv.color(color).M(-12, 0).C(-8, -6, -3, -6, 0, 0).C(3, -6, 8, -6, 12, 0).stroke(1.6 / s)
    cv.restore()


def peak(cv, px, ph, pw, y):
    cv.M(px - pw, y + 2).C(px - pw * 0.6, y - ph * 0.5, px - pw * 0.55, y - ph, px, y - ph) \
        .C(px + pw * 0.55, y - ph, px + pw * 0.6, y - ph * 0.5, px + pw, y + 2).Z()
