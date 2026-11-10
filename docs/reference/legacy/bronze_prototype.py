import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1920
SERIF_B = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

RED = (168, 36, 30)
GOLD = (222, 172, 70)
GOLD_DK = (120, 72, 24)
IVORY = (244, 230, 200)
BRONZE = (74, 96, 84)   # patina xanh đồng
BRONZE_LT = (110, 140, 120)

# nền: gradient nâu đất -> nâu tối
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
for y in range(H):
    t = y / (H - 1)
    c = (int(92 * (1 - t) + 30 * t), int(56 * (1 - t) + 16 * t), int(34 * (1 - t) + 12 * t))
    d.line([(0, y), (W, y)], fill=c)

# họa tiết hạt nhẹ như mặt giấy cổ
import random
random.seed(7)
for _ in range(2500):
    x, y = random.randrange(W), random.randrange(H)
    v = random.randint(-14, 14)
    r, g, b = img.getpixel((x, y))
    img.putpixel((x, y), (max(0, min(255, r + v)), max(0, min(255, g + v)), max(0, min(255, b + v))))

d = ImageDraw.Draw(img)

# khung kép vàng
d.rectangle([50, 50, W - 50, H - 50], outline=GOLD, width=6)
d.rectangle([72, 72, W - 72, H - 72], outline=GOLD_DK, width=2)

# góc trang trí (đường xoắn đơn giản)
def corner(cx, cy, sx, sy):
    for k in range(3):
        r = 26 + k * 14
        d.arc([cx - r, cy - r, cx + r, cy + r], start=0 if sx > 0 else 90, end=270 if sx > 0 else 360, fill=GOLD, width=3)
for cx, cy, sx, sy in [(100, 100, 1, 1), (W - 100, 100, -1, 1), (100, H - 100, 1, -1), (W - 100, H - 100, -1, -1)]:
    corner(cx, cy, sx, sy)

# tiêu đề phía trên
f_top = ImageFont.truetype(SERIF, 40)
f_title = ImageFont.truetype(SERIF_B, 84)
f_sub = ImageFont.truetype(SERIF, 46)

def center_text(y, text, font, fill):
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)

center_text(170, "LỊCH SỬ VIỆT NAM", f_top, GOLD)
d.line([(240, 240), (W - 240, 240)], fill=GOLD_DK, width=2)

# trống đồng: vẽ bằng vòng tròn đồng tâm
cx, cy, R = W // 2, 860, 330
d.ellipse([cx - R - 22, cy - R - 22, cx + R + 22, cy + R + 22], fill=(40, 28, 18))   # bóng
d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=BRONZE)
for k, rr in enumerate([R - 20, R - 50, R - 85, R - 120, R - 160, R - 200, R - 240]):
    col = BRONZE_LT if k % 2 == 0 else (60, 80, 70)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=col, width=5)

# các vòng chấm (họa tiết trống đồng)
for rr in [R - 35, R - 105, R - 185]:
    n = 36
    for i in range(n):
        a = 2 * math.pi * i / n
        x = cx + rr * math.cos(a)
        y = cy + rr * math.sin(a)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=GOLD)

# tâm: ngôi sao mặt trời 14 cánh
inner, outer = 40, 95
pts = []
for i in range(28):
    a = math.pi * i / 14 - math.pi / 2
    r = outer if i % 2 == 0 else inner
    pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
d.polygon(pts, fill=GOLD)
d.ellipse([cx - 22, cy - 22, cx + 22, cy + 22], fill=GOLD_DK)

# chim (hình đơn giản) quanh trống
def bird(x, y, s, flip=False):
    sgn = -1 if flip else 1
    body = [(x, y), (x + sgn * 40 * s, y - 14 * s), (x + sgn * 80 * s, y), (x + sgn * 40 * s, y + 10 * s)]
    d.polygon(body, fill=GOLD)
    x1, x2 = sorted([x + sgn * 60 * s, x + sgn * 72 * s])
    d.ellipse([x1, y - 6 * s, x2, y + 4 * s], fill=GOLD)
bird(190, 1240, 1.2)
bird(W - 190, 1240, 1.2, flip=True)

# nhãn phụ và tiêu đề chính
center_text(1430, "TRỐNG ĐỒNG", f_title, IVORY)
center_text(1530, "ĐÔNG SƠN", f_title, GOLD)
center_text(1650, "Văn hóa thời đồ đồng", f_sub, IVORY)

# con dấu đỏ góc dưới
seal_w, seal_h = 210, 210
sx, sy = 120, 300
d.rounded_rectangle([sx, sy, sx + seal_w, sy + seal_h], radius=14, fill=RED, outline=GOLD, width=4)
f_seal = ImageFont.truetype(SERIF_B, 58)
for i, ch in enumerate(["SỬ", "VIỆT"]):
    w = d.textlength(ch, font=f_seal)
    d.text((sx + (seal_w - w) / 2, sy + 22 + i * 84), ch, font=f_seal, fill=IVORY)

img.save("sample_trong_dong.png")
print("ok", img.size)
