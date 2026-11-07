import numpy as np
from lac import *
from figures import figure
from elements import *

rng = np.random.default_rng(42)
img = lacquer_ground(rng, top=P["black"], mid=(70, 20, 12), bottom=P["black"])

# gold-leaf moon
m = Canvas(); m.color((255,255,255)).ellipse(770, 450, 125, 125).fill()
img = fill_mask(img, gold_leaf(rng, tile=26, worn=0.03), m.mask())
cv = Canvas(); cv.color(P["gold_lt"]).ellipse(770, 450, 125, 125).stroke(2.5); img = over(img, cv)

# birds
cv = Canvas()
for bx, by, bs in [(300, 400, 1.6), (360, 440, 1.2), (250, 470, 1.0), (420, 380, 0.9)]:
    bird(cv, bx, by, bs)
img = over(img, cv)

# back karst range: one peak at a time, tallest (farthest) first
back = [(470, 380, 120), (860, 360, 130), (120, 330, 120), (660, 290, 115), (300, 250, 105), (1030, 260, 100)]
cv = Canvas()
for i, (px, ph, pw) in enumerate(back):
    shade = 1.0 - i * 0.06
    top_c = tuple(int(v * shade) for v in P["vermilion_dk"])
    peak(cv, px, ph, pw, 900); cv.vgrad(900 - ph, 900, [(0, top_c, 1), (1, (44, 11, 8), 1)]).fill()
    peak(cv, px, ph, pw, 900); cv.color(P["gold"]).stroke(1.8)
img = over(img, cv)

# eggshell clouds drifting across peaks
m = Canvas(); m.color((255,255,255))
cloud_path(m, 230, 720, 1.1); m.fill(); cloud_path(m, 640, 650, 0.9, -1); m.fill(); cloud_path(m, 960, 760, 0.8); m.fill()
img = fill_mask(img, eggshell(rng, m.mask(), cell=11), m.mask())
cv = Canvas(); cloud_lines(cv, 230, 720, 1.1, color=P["gold_dk"]); cloud_lines(cv, 640, 650, 0.9, -1, color=P["gold_dk"]); cloud_lines(cv, 960, 760, 0.8, color=P["gold_dk"]); img = over(img, cv)

# middle range with eggshell faces, drawn peak by peak
mid = [(80, 200, 140), (400, 150, 150), (990, 220, 160)]
for px, ph, pw in mid:
    m = Canvas(); m.color((255,255,255)); peak(m, px, ph, pw, 945); m.fill()
    img = fill_mask(img, eggshell(rng, m.mask(), cell=15), m.mask())
    cv = Canvas(); peak(cv, px, ph, pw, 945); cv.color(P["gold"]).stroke(2.5); img = over(img, cv)

# river
cv = Canvas()
cv.vgrad(940, 1230, [(0, (40, 12, 8), 1), (0.65, P["black"], 0.9), (1, P["black"], 0)]).rect(0, 940, 1080, 290).fill()
cv.color(P["gold"]).M(0, 940).L(1080, 940).stroke(2)
for row, y in enumerate(range(970, 1150, 30)):
    x = -60 + (row % 2) * 45
    while x < 1120:
        cv.color(P["gold_dk"] if row % 2 else P["gold"], 0.75).M(x, y).C(x + 15, y - 8, x + 35, y - 8, x + 50, y).stroke(1.6)
        x += 90
img = over(img, cv)

# boats with small figures
cv = Canvas()
figure(cv, 300, 1048, 150, "leader", 1)
figure(cv, 250, 1050, 120, "boatwoman", -1)
boat(cv, 290, 1056, 1.5)
figure(cv, 760, 1098, 125, "general", 1)
figure(cv, 815, 1100, 110, "boatwoman", 1)
boat(cv, 780, 1104, 1.25)
img = over(img, cv)

cv = Canvas(); waves(cv, 1600, rows=4); img = over(img, cv)
img = finish(img, rng, sheen=(700, 520, 520, 0.08))
cv = Canvas(); frame(cv); img = over(img, cv)

pil = to_pil(img)
seal(pil, 92, 160)
tag_pill(pil, "KHỞI NGHĨA HAI BÀ TRƯNG", 590, 180)
text_block(pil, [
    ("Mê Linh, năm 40", 1215, FONT_TITLE, 96, P["egg"], True, 505),
    ("Nơi cuộc khởi nghĩa bắt đầu", 1345, FONT_SUB, 48, P["gold_lt"], False, 505),
])
pil.save("sample_3_me_linh.png")
print("ok")
