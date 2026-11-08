"""Mountains, peaks, hills, river and ground (FR-35, FR-36, AC-05)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from scipy.ndimage import binary_dilation

from history_shorts.canvas import Canvas
from history_shorts.compose import fill_mask, over
from history_shorts.config import (
    GroundLayer,
    HillsLayer,
    MountainsLayer,
    PeakItem,
    PeaksLayer,
    RiverLayer,
)
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS
from history_shorts.scene.registry import WHITE, entry, merge
from history_shorts.scene.terrain import (
    CURL_X_START,
    CURL_X_STEP,
    PEAK_BASE_COLOR,
    PEAK_GRADIENT_OUTLINE_WIDTH,
    PEAK_OUTLINE_COLOR,
    PEAK_SHADE_STEP,
    draw_ground,
    draw_hills,
    draw_mountains,
    draw_peaks,
    draw_river,
    hill_path,
    peak_path,
    peak_top_color,
)
from history_shorts.textures import eggshell

Base = Callable[[], FloatImage]
HEIGHT, WIDTH = 1920, 1080
SLACK = 4
BACK = (
    PeakItem(470, 380, 120),
    PeakItem(860, 360, 130),
    PeakItem(120, 330, 120),
    PeakItem(660, 290, 115),
    PeakItem(300, 250, 105),
    PeakItem(1030, 260, 100),
)
BACK_Y = 900.0
GRADIENT = PeaksLayer(BACK_Y, BACK, "gradient", None, None)
MID = (PeakItem(80, 200, 140), PeakItem(400, 150, 150), PeakItem(990, 220, 160))
EGGSHELL = PeaksLayer(945, MID, "eggshell", 15, None)
Point = tuple[float, float]


# -- helpers: the analytic outline of a peak, independent of the drawing code ------------


def _bezier(p0: Point, p1: Point, p2: Point, p3: Point, n: int = 160) -> Any:
    t = np.linspace(0.0, 1.0, n)[:, None]
    pts = (
        (1 - t) ** 3 * np.array(p0)
        + 3 * (1 - t) ** 2 * t * np.array(p1)
        + 3 * (1 - t) * t**2 * np.array(p2)
        + t**3 * np.array(p3)
    )
    return pts


def peak_outline(item: PeakItem, y: float) -> Any:
    """The two curved sides of a peak (the base line is left out): (n, 2) array of x, y."""
    px, ph, pw = item.x, item.height, item.width
    left = _bezier(
        (px - pw, y + 2), (px - pw * 0.6, y - ph * 0.5), (px - pw * 0.55, y - ph), (px, y - ph)
    )
    right = _bezier(
        (px, y - ph), (px + pw * 0.55, y - ph), (px + pw * 0.6, y - ph * 0.5), (px + pw, y + 2)
    )
    return np.vstack([left, right])


def inside_with_margin(item: PeakItem, y: float, pts: Any, margin: float) -> Any:
    """Which of ``pts`` lie inside the peak polygon and at least ``margin`` px from its edge."""
    poly = np.vstack([peak_outline(item, y), [[item.x + item.width, y + 2]]])
    poly = np.vstack([poly, [[item.x - item.width, y + 2]]])
    x, yy = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), dtype=bool)
    a, b = poly, np.roll(poly, -1, axis=0)
    for (x0, y0), (x1, y1) in zip(a, b, strict=True):
        if y0 == y1:
            continue
        crosses = (y0 > yy) != (y1 > yy)
        x_at = x0 + (yy - y0) * (x1 - x0) / (y1 - y0)
        inside ^= crosses & (x < x_at)
    return inside & (_dist_to_polyline(poly, pts) >= margin)


def _dist_to_polyline(poly: Any, pts: Any) -> Any:
    best = np.full(len(pts), np.inf)
    a, b = poly, np.roll(poly, -1, axis=0)
    for p, q in zip(a, b, strict=True):
        d = q - p
        denom = float(d @ d)
        t = np.clip(((pts - p) @ d) / denom, 0, 1) if denom else np.zeros(len(pts))
        best = np.minimum(best, np.linalg.norm(pts - (p + t[:, None] * d), axis=1))
    return best


def gold_near(img: FloatImage, x: float, y: float, gold: Any, tol: float = 0.1) -> bool:
    """True when any pixel of the 3x3 block around (x, y) is within ``tol`` of gold."""
    xi, yi = int(x), int(y)
    block = img[yi - 1 : yi + 2, xi - 1 : xi + 2]
    return bool((np.abs(block - gold).max(axis=-1) < tol).any())


def crossing_gold_points(
    img: FloatImage, items: tuple[PeakItem, ...], y: float, gold: Any
) -> tuple[int, int]:
    """(points checked, points where gold shows) for outlines of peak i inside a later peak j."""
    checked = shown = 0
    for i, j in itertools.combinations(range(len(items)), 2):
        pts = peak_outline(items[i], y)
        keep = inside_with_margin(items[j], y, pts, margin=3)
        for k in range(j + 1, len(items)):  # a later outline may legitimately cross the point
            keep &= _dist_to_polyline(peak_outline(items[k], y), pts) >= 3
        for x, yy in pts[keep]:
            checked += 1
            shown += gold_near(img, x, yy, gold)
    return checked, shown


def wrong_order_peaks(img: FloatImage, items: tuple[PeakItem, ...], y: float, pal: Any) -> Any:
    """Negative control: every fill first, then every outline (what FR-35 forbids)."""
    cv = Canvas()
    for i, it in enumerate(items):
        peak_path(cv, it, y)
        stops = [(0, peak_top_color(pal, i), 1), (1, pal[PEAK_BASE_COLOR], 1)]
        cv.vgrad(y - it.height, y, stops).fill()
    for it in items:
        peak_path(cv, it, y)
        cv.color(pal[PEAK_OUTLINE_COLOR]).stroke(PEAK_GRADIENT_OUTLINE_WIDTH)
    return over(img, cv)


# -- registry ----------------------------------------------------------------------------


def test_merge_rejects_duplicate_layer_types() -> None:
    first = dict([entry(RiverLayer, draw_river)])
    second = dict([entry(RiverLayer, draw_river)])
    with pytest.raises(ValueError, match="RiverLayer"):
        merge(first, second)
    assert set(merge(first, dict([entry(GroundLayer, draw_ground)]))) == {RiverLayer, GroundLayer}


def test_registry_contains_terrain_drawers() -> None:
    expected = {MountainsLayer, PeaksLayer, HillsLayer, RiverLayer, GroundLayer}
    assert expected <= set(LAYER_DRAWERS)


# -- peaks -------------------------------------------------------------------------------


def test_no_crossing_peak_outlines(ctx: Any, palette: Any, flat_base: Base) -> None:  # AC-05
    img = draw_peaks(flat_base(), GRADIENT, ctx, 1)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    checked, shown = crossing_gold_points(img, BACK, BACK_Y, gold)
    assert checked > 100  # the sampler really found outlines hidden behind later peaks
    assert shown == 0


def test_crossing_check_catches_fills_then_outlines(
    ctx: Any, palette: Any, flat_base: Base
) -> None:
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    bad = wrong_order_peaks(flat_base(), BACK, BACK_Y, palette)
    checked, shown = crossing_gold_points(bad, BACK, BACK_Y, gold)
    assert checked > 100
    assert shown > checked * 0.5


def test_peak_top_color_truncates_each_channel(palette: Any) -> None:
    r, g, b = palette["vermilion_dk"]
    assert peak_top_color(palette, 0) == (r, g, b)
    for i in range(6):
        shade = 1 - i * PEAK_SHADE_STEP
        assert peak_top_color(palette, i) == (int(r * shade), int(g * shade), int(b * shade))
    assert peak_top_color(palette, 3) == (int(112 * 0.82), int(22 * 0.82), int(14 * 0.82))


def test_gradient_peak_top_shade_steps_down(ctx: Any, palette: Any, flat_base: Base) -> None:
    img = draw_peaks(flat_base(), GRADIENT, ctx, 1)
    for index, (x, apex) in ((0, (470, 520)), (3, (660, 610))):
        want = np.array(peak_top_color(palette, index), dtype=np.float32) / 255
        got = img[apex + 1, x]  # right under the apex the gradient is still at its top colour
        assert np.abs(got - want).max() <= 1 / 255 + 1e-6, index
    assert img[525, 470].sum() > img[615, 660].sum()  # farther peaks are brighter


def test_peaks_above_their_apex_untouched(ctx: Any, flat_base: Base) -> None:
    before = flat_base()
    after = draw_peaks(before.copy(), GRADIENT, ctx, 1)
    assert np.array_equal(after[:515], before[:515])
    assert np.array_equal(after[905:], before[905:])


def _peak_union_mask(items: tuple[PeakItem, ...], y: float) -> Any:
    cv = Canvas()
    cv.color(WHITE)
    for it in items:
        peak_path(cv, it, y)
        cv.fill()
    return cv.mask() > 0


def test_eggshell_peaks_contained(ctx: Any, flat_base: Base) -> None:  # FR-36
    before = flat_base()
    after = draw_peaks(before.copy(), EGGSHELL, ctx, 2)
    near = binary_dilation(_peak_union_mask(MID, 945), iterations=SLACK)
    assert np.array_equal(after[~near], before[~near])
    assert np.any(after[near] != before[near], axis=-1).sum() > 5000


def test_eggshell_peaks_one_mask_each(ctx: Any, palette: Any, flat_base: Base) -> None:
    """Each peak gets its own eggshell texture, then its own gold outline, in order."""
    img = flat_base()
    for it in MID:
        cv = Canvas()
        cv.color(WHITE)
        peak_path(cv, it, 945)
        cv.fill()
        mask = cv.mask()
        tex = eggshell(
            ctx.eggshell_rng(2, mask), mask, palette, 15, ctx.theme.textures.eggshell.gap
        )
        img = fill_mask(img, tex, mask)
        cv = Canvas()
        peak_path(cv, it, 945)
        cv.color(palette["gold"]).stroke(2.5)
        img = over(img, cv)
    assert np.array_equal(img, draw_peaks(flat_base(), EGGSHELL, ctx, 2))


def test_peaks_deterministic_and_theme_defaults(ctx: Any, flat_base: Base) -> None:
    spec = ctx.theme.textures.eggshell
    defaulted = PeaksLayer(945, MID, "eggshell", None, None)
    explicit = PeaksLayer(945, MID, "eggshell", spec.cell, spec.gap)
    a = draw_peaks(flat_base(), defaulted, ctx, 2)
    assert a.dtype == np.float32
    assert np.array_equal(a, draw_peaks(flat_base(), explicit, ctx, 2))
    assert np.array_equal(a, draw_peaks(flat_base(), defaulted, ctx, 2))


# -- hills -------------------------------------------------------------------------------


@pytest.mark.parametrize("side,base,top", [("left", 1100, 880), ("right", 1100, 900)])
def test_hills_contained(ctx: Any, flat_base: Base, side: Any, base: float, top: float) -> None:
    layer = HillsLayer(side, base, top, 16, 1.0)
    before = flat_base()
    after = draw_hills(before.copy(), layer, ctx, 3)
    cv = Canvas()
    cv.color(WHITE)
    hill_path(cv, side, base, top)
    cv.fill()
    near = binary_dilation(cv.mask() > 0, iterations=SLACK)
    assert np.array_equal(after[~near], before[~near])
    assert np.any(after[near] != before[near], axis=-1).sum() > 5000


def test_hill_sides_sit_at_opposite_edges(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    left = draw_hills(base.copy(), HillsLayer("left", 1100, 880, 16, 1.0), ctx, 3)
    right = draw_hills(base.copy(), HillsLayer("right", 1100, 900, 16, 1.0), ctx, 3)
    cols_l = np.nonzero(np.any(left != base, axis=(0, 2)))[0]
    cols_r = np.nonzero(np.any(right != base, axis=(0, 2)))[0]
    assert cols_l.min() == 0 and cols_l.max() < 360
    assert cols_r.max() == WIDTH - 1 and cols_r.min() > 720


def test_hill_outline_is_gold(ctx: Any, palette: Any, flat_base: Base) -> None:
    out = draw_hills(flat_base(), HillsLayer("left", 1100, 880, 16, 1.0), ctx, 3)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    assert gold_near(out, 1, 1000, gold)  # the left edge runs straight down from top + 40


# -- mountains ---------------------------------------------------------------------------


@pytest.mark.parametrize("amp", [1.0, 0.5])
def test_mountains_ridge_and_fill(ctx: Any, palette: Any, flat_base: Base, amp: float) -> None:
    before = flat_base()
    after = draw_mountains(before.copy(), MountainsLayer(900, amp), ctx, 1)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    assert gold_near(after, 1, 900 + 80 * amp, gold)  # the ridge starts at (0, y + 80 amp)
    base_colour = np.array(palette["mountain_base"], dtype=np.float32) / 255
    assert np.abs(after[1105, 540] - base_colour).max() < 0.02  # gradient has reached its end
    assert np.array_equal(after[1125:], before[1125:])  # the fill stops at y + 220
    assert np.array_equal(after[: 900 - int(100 * amp) - 5], before[: 900 - int(100 * amp) - 5])


def test_mountains_amp_changes_shape(ctx: Any, flat_base: Base) -> None:
    a = draw_mountains(flat_base(), MountainsLayer(900, 1.0), ctx, 1)
    b = draw_mountains(flat_base(), MountainsLayer(900, 0.5), ctx, 1)
    assert not np.array_equal(a, b)


# -- river -------------------------------------------------------------------------------


def test_river_fades_to_transparent(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    out = draw_river(base.copy(), RiverLayer(940, 290), ctx, 1)
    assert np.allclose(out[1229], base[1229], atol=1 / 255)
    assert not np.allclose(out[1100], base[1100], atol=0.05)
    assert np.array_equal(out[1235:], base[1235:])
    assert np.array_equal(out[:935], base[:935])


def test_river_top_line_is_gold(ctx: Any, palette: Any, flat_base: Base) -> None:
    out = draw_river(flat_base(), RiverLayer(940, 290), ctx, 1)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    assert gold_near(out, 540, 940, gold)


def test_river_wave_rows_alternate_colour(ctx: Any, palette: Any, flat_base: Base) -> None:
    out = draw_river(flat_base(), RiverLayer(940, 290), ctx, 1)
    # row 0 (gold) strokes span x 30..80 at y + 30 and peak 6 px above it at x = 55
    # row 1 (gold_dk) strokes span x -15..35 and 75..125, so their crest is at x = 100, y + 54
    for (x, y), key, other in (((55, 964), "gold", "gold_dk"), ((100, 994), "gold_dk", "gold")):
        under = out[y + 8, x]  # the gradient just below the stroke, which shows through it
        block = out[y - 1 : y + 2, x - 1 : x + 2].reshape(-1, 3)
        got = block[block.sum(axis=1).argmax()]  # the pixel the thin stroke covers best

        want = 0.75 * np.array(palette.rgb01(key)) + 0.25 * under
        wrong = 0.75 * np.array(palette.rgb01(other)) + 0.25 * under
        assert np.abs(got - want).max() < np.abs(got - wrong).max(), key
        assert np.abs(got - want).max() < 0.15, key


def test_river_has_six_wave_rows_whatever_the_height(ctx: Any, flat_base: Base) -> None:
    for height in (290, 400):
        out = draw_river(flat_base(), RiverLayer(940, height), ctx, 1)
        bright = out[945 : 940 + 200, :, 0].max(axis=1) > 0.3
        edges = np.flatnonzero(np.diff(bright.astype(int)) == 1) + 1
        assert len(edges) + int(bright[0]) == 6, height


# -- ground ------------------------------------------------------------------------------


def test_ground_gold_line(ctx: Any, palette: Any, flat_base: Base) -> None:
    out = draw_ground(flat_base(), GroundLayer(1092, 52), ctx, 1)
    gold = np.array(palette.rgb01("gold"), dtype=np.float32)
    for x in (100, 540, 1000):
        assert gold_near(out, x, 1092, gold)


def test_ground_band_bounds_and_gradient(ctx: Any, palette: Any, flat_base: Base) -> None:
    before = flat_base()
    out = draw_ground(before.copy(), GroundLayer(1092, 52), ctx, 1)
    assert np.array_equal(out[:1088], before[:1088])
    assert np.array_equal(out[1146:], before[1146:])
    black = np.array(palette.rgb01("black"), dtype=np.float32)
    assert np.abs(out[1143, 300] - black).max() < 0.04  # the band ends at black
    assert out[1100, 300].sum() > out[1140, 300].sum()  # and gets darker going down


def test_ground_curls_are_gold_dk_every_120px(ctx: Any, palette: Any, flat_base: Base) -> None:
    out = draw_ground(flat_base(), GroundLayer(1092, 52), ctx, 1)
    dk = np.array(palette.rgb01("gold_dk"), dtype=np.float32)
    # the curl that starts at x = -40 + 120 n is jointed at (x + 56, y + 30)
    # and its second segment passes (x + 52.75, y + 39) at t = 1/2
    for n in range(8):
        x = CURL_X_START + CURL_X_STEP * n
        assert gold_near(out, x + 56, 1092 + 30, dk, tol=0.12), n
        assert gold_near(out, x + 52.75, 1092 + 39, dk, tol=0.12), n
