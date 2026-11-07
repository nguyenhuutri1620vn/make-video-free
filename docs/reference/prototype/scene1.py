import numpy as np
from lac import *
from figures import figure
from elements import *

rng = np.random.default_rng(40)
img = lacquer_ground(rng)

# gold-leaf sun
m = Canvas(); m.color((255, 255, 255)).ellipse(540, 650, 300, 300).fill()
img = fill_mask(img, gold_leaf(rng, tile=34, worn=0.05), m.mask())
cv = Canvas()
cv.color(P["gold_lt"]).ellipse(540, 650, 300, 300).stroke(3)
cv.color(P["gold_dk"]).ellipse(540, 650, 318, 318).stroke(1.5)
img = over(img, cv)

# eggshell clouds
m = Canvas(); m.color((255,255,255))
cloud_path(m, 270, 318, 0.8); m.fill()
cloud_path(m, 860, 318, 0.8, -1); m.fill()
img = fill_mask(img, eggshell(rng, m.mask(), cell=12, gap=0.9), m.mask())
cv = Canvas(); cloud_lines(cv, 270, 318, 0.8); cloud_lines(cv, 860, 318, 0.8, -1); img = over(img, cv)

# far mountains
cv = Canvas()
far_mountains(cv, 900); cv.vgrad(800, 1100, [(0, P["vermilion_dk"], 1), (1, (60, 14, 10), 1)]).fill()
far_ridge(cv, 900); cv.color(P["gold"]).stroke(2.5)
img = over(img, cv)

# near eggshell hills
m = Canvas(); m.color((255,255,255)); hill_left(m, 1100, 880); m.fill(); hill_right(m, 1100, 900); m.fill()
img = fill_mask(img, eggshell(rng, m.mask(), cell=16, gap=1.0), m.mask())
cv = Canvas(); hill_left(cv, 1100, 880); cv.color(P["gold"]).stroke(2.5); hill_right(cv, 1100, 900); cv.color(P["gold"]).stroke(2.5)
img = over(img, cv)

# ground
cv = Canvas(); ground_band(cv, 1092); img = over(img, cv)

# characters: back to front
base = 1100
cv = Canvas()
figure(cv, 150, base - 4, 420, "general", -1)
figure(cv, 930, base - 4, 420, "general", 1)
figure(cv, 285, base, 475, "general_b", -1)
figure(cv, 795, base, 475, "general_b", 1)
figure(cv, 432, base + 6, 565, "leader", -1)
figure(cv, 648, base + 6, 565, "leader", 1)
img = over(img, cv)

# bottom water waves (chrome area, outside safe zone)
cv = Canvas(); waves(cv, 1600, rows=4); img = over(img, cv)

img = finish(img, rng, sheen=(360, 700, 640, 0.10))
cv = Canvas(); frame(cv); img = over(img, cv)

pil = to_pil(img)
seal(pil, 92, 160)
tag_pill(pil, "NĂM 40 SAU CÔNG NGUYÊN", 590, 180)
text_block(pil, [
    ("Những nữ tướng", 1190, FONT_TITLE, 92, P["egg"], True, 505),
    ("bên Hai Bà Trưng", 1292, FONT_TITLE, 92, P["gold_lt"], True, 505),
    ("Khi phụ nữ cầm quân giữ nước", 1420, FONT_SUB, 46, P["egg"], False, 505),
])
pil.save("sample_1_nu_tuong.png")
print("ok")
