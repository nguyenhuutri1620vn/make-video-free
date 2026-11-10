"""Prototype library: Cairo (via ctypes) for vector shapes, numpy for lacquer textures."""
import ctypes
import math
import numpy as np
from scipy.ndimage import gaussian_filter, binary_dilation
from scipy.spatial import cKDTree
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920

# ---------------------------------------------------------------- palette
P = {
    "black": (16, 9, 7),
    "deep": (48, 14, 9),
    "vermilion": (176, 36, 24),
    "vermilion_dk": (112, 22, 14),
    "gold": (212, 166, 76),
    "gold_lt": (242, 210, 130),
    "gold_dk": (138, 96, 40),
    "egg": (236, 225, 200),
    "brown": (92, 50, 28),
    "brown_lt": (128, 74, 40),
    "skin_line": (96, 52, 32),
    "pink": (224, 140, 120),
    "jade": (52, 84, 70),
}
FONT_TITLE = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"
FONT_SUB = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
FONT_TAG = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"

# ---------------------------------------------------------------- cairo via ctypes
_c = ctypes.CDLL("libcairo.so.2")
_vp, _d, _i = ctypes.c_void_p, ctypes.c_double, ctypes.c_int


def _f(name, res, *args):
    fn = getattr(_c, name)
    fn.restype = res
    fn.argtypes = list(args)
    return fn


_surface_create = _f("cairo_image_surface_create", _vp, _i, _i, _i)
_create = _f("cairo_create", _vp, _vp)
_destroy = _f("cairo_destroy", None, _vp)
_surface_destroy = _f("cairo_surface_destroy", None, _vp)
_flush = _f("cairo_surface_flush", None, _vp)
_get_data = _f("cairo_image_surface_get_data", ctypes.POINTER(ctypes.c_ubyte), _vp)
_get_stride = _f("cairo_image_surface_get_stride", _i, _vp)
_rgba = _f("cairo_set_source_rgba", None, _vp, _d, _d, _d, _d)
_move = _f("cairo_move_to", None, _vp, _d, _d)
_line = _f("cairo_line_to", None, _vp, _d, _d)
_curve = _f("cairo_curve_to", None, _vp, _d, _d, _d, _d, _d, _d)
_close = _f("cairo_close_path", None, _vp)
_new_path = _f("cairo_new_path", None, _vp)
_new_sub = _f("cairo_new_sub_path", None, _vp)
_arc = _f("cairo_arc", None, _vp, _d, _d, _d, _d, _d)
_fill = _f("cairo_fill", None, _vp)
_fill_p = _f("cairo_fill_preserve", None, _vp)
_stroke = _f("cairo_stroke", None, _vp)
_stroke_p = _f("cairo_stroke_preserve", None, _vp)
_lw = _f("cairo_set_line_width", None, _vp, _d)
_cap = _f("cairo_set_line_cap", None, _vp, _i)
_join = _f("cairo_set_line_join", None, _vp, _i)
_save = _f("cairo_save", None, _vp)
_restore = _f("cairo_restore", None, _vp)
_translate = _f("cairo_translate", None, _vp, _d, _d)
_scale = _f("cairo_scale", None, _vp, _d, _d)
_rotate = _f("cairo_rotate", None, _vp, _d)
_clip = _f("cairo_clip", None, _vp)
_lin = _f("cairo_pattern_create_linear", _vp, _d, _d, _d, _d)
_rad = _f("cairo_pattern_create_radial", _vp, _d, _d, _d, _d, _d, _d)
_stop = _f("cairo_pattern_add_color_stop_rgba", None, _vp, _d, _d, _d, _d, _d)
_set_src = _f("cairo_set_source", None, _vp, _vp)
_pat_destroy = _f("cairo_pattern_destroy", None, _vp)


class Canvas:
    """Transparent ARGB32 Cairo canvas with a small path API."""

    def __init__(self, w=W, h=H):
        self.w, self.h = w, h
        self.s = _surface_create(0, w, h)
        self.cr = _create(self.s)
        _cap(self.cr, 1)
        _join(self.cr, 1)

    # state
    def save(self): _save(self.cr)
    def restore(self): _restore(self.cr)
    def translate(self, x, y): _translate(self.cr, x, y)
    def scale(self, sx, sy): _scale(self.cr, sx, sy)
    def rotate(self, a): _rotate(self.cr, a)

    # paths
    def M(self, x, y): _move(self.cr, x, y); return self
    def L(self, x, y): _line(self.cr, x, y); return self
    def C(self, x1, y1, x2, y2, x3, y3): _curve(self.cr, x1, y1, x2, y2, x3, y3); return self
    def Z(self): _close(self.cr); return self
    def new(self): _new_path(self.cr); return self

    def ellipse(self, cx, cy, rx, ry):
        _new_sub(self.cr)
        _save(self.cr)
        _translate(self.cr, cx, cy)
        _scale(self.cr, rx, ry)
        _arc(self.cr, 0, 0, 1, 0, 2 * math.pi)
        _restore(self.cr)
        return self

    def rect(self, x, y, w, h):
        return self.M(x, y).L(x + w, y).L(x + w, y + h).L(x, y + h).Z()

    # paint
    def color(self, c, a=1.0):
        _rgba(self.cr, c[0] / 255, c[1] / 255, c[2] / 255, a)
        return self

    def vgrad(self, y0, y1, stops):
        pat = _lin(0, y0, 0, y1)
        for off, c, a in stops:
            _stop(pat, off, c[0] / 255, c[1] / 255, c[2] / 255, a)
        _set_src(self.cr, pat)
        _pat_destroy(pat)
        return self

    def rgrad(self, cx, cy, r, stops):
        pat = _rad(cx, cy, 0, cx, cy, r)
        for off, c, a in stops:
            _stop(pat, off, c[0] / 255, c[1] / 255, c[2] / 255, a)
        _set_src(self.cr, pat)
        _pat_destroy(pat)
        return self

    def fill(self, keep=False):
        (_fill_p if keep else _fill)(self.cr)
        return self

    def stroke(self, width, keep=False):
        _lw(self.cr, width)
        (_stroke_p if keep else _stroke)(self.cr)
        return self

    def clip(self): _clip(self.cr); return self

    def to_premul(self):
        """Return (rgb_premultiplied, alpha) as float32 arrays in 0..1."""
        _flush(self.s)
        stride = _get_stride(self.s)
        ptr = _get_data(self.s)
        buf = np.ctypeslib.as_array(ptr, shape=(self.h * stride,)).copy()
        arr = buf.reshape(self.h, stride // 4, 4)[:, : self.w].astype(np.float32) / 255
        rgb = arr[..., [2, 1, 0]]
        a = arr[..., 3]
        return rgb, a

    def mask(self):
        return self.to_premul()[1]

    def __del__(self):
        try:
            _destroy(self.cr)
            _surface_destroy(self.s)
        except Exception:
            pass


# ---------------------------------------------------------------- compositing
def col(c):
    return np.array(c, dtype=np.float32) / 255


def over(base, canvas):
    rgb, a = canvas.to_premul()
    return rgb + base * (1 - a[..., None])


def fill_mask(base, tex, mask):
    m = mask[..., None]
    return tex * m + base * (1 - m)


# ---------------------------------------------------------------- textures
def noise(h, w, sigma, rng):
    n = gaussian_filter(rng.standard_normal((h, w)).astype(np.float32), sigma)
    n -= n.mean()
    return n / (np.abs(n).max() + 1e-6)


def lacquer_ground(rng, top=P["black"], mid=P["deep"], bottom=P["black"]):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    k = np.clip(np.sin(y * math.pi), 0, 1) ** 1.5
    base = col(top) * (1 - k[..., None]) + col(mid) * k[..., None]
    base = base * (1 - y[..., None] * 0.3) + col(bottom) * (y[..., None] * 0.3)
    base = np.broadcast_to(base, (H, W, 3)).copy()
    # depth: low-frequency variation like layered lacquer
    lo = noise(H // 4, W // 4, 18, rng)
    lo = np.kron(lo, np.ones((4, 4), dtype=np.float32))[:H, :W]
    base *= (1 + 0.10 * lo)[..., None]
    return np.clip(base, 0, 1)


def gold_leaf(rng, tile=34, worn=0.10, under=P["vermilion_dk"]):
    """Gold leaf squares with varied tone, seams, and worn spots showing red under-layer."""
    th, tw = H // tile + 2, W // tile + 2
    tone = rng.uniform(-0.09, 0.07, (th, tw)).astype(np.float32)
    tone = np.kron(tone, np.ones((tile, tile), dtype=np.float32))[:H, :W]
    g = col(P["gold"])[None, None, :] * (1 + tone[..., None])
    # gentle diagonal sheen
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    g *= (1 + 0.10 * np.sin((xx + yy) / 260.0))[..., None]
    # fine grain
    g *= (1 + 0.04 * noise(H, W, 0.8, rng))[..., None]
    # seams
    seam = ((xx % tile) < 1.2) | ((yy % tile) < 1.2)
    g[seam] *= 0.82
    # worn spots, concentrated along seams
    wn = noise(H // 2, W // 2, 6, rng)
    wn = np.kron(wn, np.ones((2, 2), dtype=np.float32))[:H, :W]
    near_seam = binary_dilation(seam, iterations=3)
    worn_mask = (wn > 1 - worn * 2.2) & near_seam
    g[worn_mask] = g[worn_mask] * 0.35 + col(under) * 0.65
    return np.clip(g, 0, 1)


def eggshell(rng, mask, cell=16, gap=1.0, tone=(226, 212, 184), ground=(58, 30, 20)):
    """Voronoi eggshell mosaic inside `mask` (cẩn vỏ trứng)."""
    out = np.zeros((H, W, 3), dtype=np.float32)
    ys, xs = np.nonzero(mask > 0.01)
    if len(ys) == 0:
        return out
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    gy, gx = np.mgrid[y0:y1:cell, x0:x1:cell]
    pts = np.stack([gy.ravel(), gx.ravel()], 1).astype(np.float32)
    pts += rng.uniform(0, cell, pts.shape)
    tree = cKDTree(pts)
    py, px = np.mgrid[y0:y1, x0:x1]
    q = np.stack([py.ravel(), px.ravel()], 1)
    d, idx = tree.query(q, k=2)
    edge = (d[:, 1] - d[:, 0]) < gap
    shade = rng.uniform(-0.16, 0.02, len(pts)).astype(np.float32)
    region = col(tone)[None, :] * (1 + shade[idx[:, 0]])[:, None]
    region[edge] = col(ground)
    out[y0:y1, x0:x1] = region.reshape(y1 - y0, x1 - x0, 3)
    return out


def finish(img, rng, sheen=(330, 760, 620, 0.10)):
    """Polished lacquer sheen + very fine grain (no crackle lines)."""
    cx, cy, r, s = sheen
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    img = img + (np.clip(1 - d, 0, 1) ** 2 * s)[..., None] * col((255, 210, 160))
    img *= (1 + 0.025 * noise(H, W, 0.7, rng))[..., None]
    return np.clip(img, 0, 1)


# ---------------------------------------------------------------- text + frame (Pillow)
def to_pil(img):
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")


def frame(cv):
    cv.color(P["gold"]).rect(40, 40, W - 80, H - 80).stroke(5)
    cv.color(P["gold_dk"]).rect(58, 58, W - 116, H - 116).stroke(1.5)
    # corner cloud scrolls
    for sx, sy, fx, fy in [(58, 58, 1, 1), (W - 58, 58, -1, 1), (58, H - 58, 1, -1), (W - 58, H - 58, -1, -1)]:
        cv.save(); cv.translate(sx, sy); cv.scale(fx, fy)
        cv.color(P["gold"]).M(0, 70).C(0, 20, 20, 0, 70, 0).stroke(2.5)
        cv.M(18, 54).C(18, 30, 30, 18, 54, 18).stroke(1.5)
        cv.new().ellipse(30, 30, 6, 6).fill()
        cv.restore()


def text_block(pil, items):
    """items: (text, y, font_path, size, rgb, shadow, cx)."""
    d = ImageDraw.Draw(pil)
    for text, y, fp, size, rgb, shadow, cx in items:
        f = ImageFont.truetype(fp, size)
        w = d.textlength(text, font=f)
        if shadow:
            d.text((cx - w / 2 + 3, y + 3), text, font=f, fill=(10, 4, 2))
        d.text((cx - w / 2, y), text, font=f, fill=rgb)


def tag_pill(pil, text, cx, y, size=34):
    d = ImageDraw.Draw(pil)
    f = ImageFont.truetype(FONT_TAG, size)
    w = d.textlength(text, font=f)
    d.rounded_rectangle([cx - w / 2 - 26, y, cx + w / 2 + 26, y + size + 26], radius=30,
                        fill=P["vermilion"], outline=P["gold"], width=2)
    d.text((cx - w / 2, y + 10), text, font=f, fill=P["gold_lt"])


def seal(pil, x, y, size=118):
    d = ImageDraw.Draw(pil)
    d.rounded_rectangle([x, y, x + size, y + size], radius=10, fill=P["vermilion"], outline=P["gold"], width=3)
    d.rounded_rectangle([x + 8, y + 8, x + size - 8, y + size - 8], radius=6, outline=P["egg"], width=1)
    f = ImageFont.truetype(FONT_TITLE, 36)
    for i, ch in enumerate(["SỬ", "VIỆT"]):
        w = d.textlength(ch, font=f)
        d.text((x + (size - w) / 2, y + 14 + i * 46), ch, font=f, fill=P["egg"])
