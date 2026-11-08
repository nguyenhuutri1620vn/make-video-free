"""Layer registry, sun/moon, birds and eggshell clouds (FR-23, FR-34, FR-36)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from scipy.ndimage import binary_dilation

from history_shorts.canvas import Canvas
from history_shorts.config import BirdItem, BirdsLayer, CloudItem, CloudsLayer, SunLayer
from history_shorts.primitives import FloatImage
from history_shorts.scene import LAYER_DRAWERS, draw_layers
from history_shorts.scene.clouds import cloud_path, draw_clouds
from history_shorts.scene.sky import draw_birds, draw_sun

Base = Callable[[], FloatImage]
HEIGHT, WIDTH = 1920, 1080
SLACK = 4  # px of anti-alias and stroke slack around a drawn shape


def _circle_outside(x: float, y: float, radius: float) -> Any:
    yy, xx = np.mgrid[:HEIGHT, :WIDTH]
    return (xx - x) ** 2 + (yy - y) ** 2 > radius**2


def _ring_band(x: float, y: float, radius: float, half: float) -> Any:
    yy, xx = np.mgrid[:HEIGHT, :WIDTH]
    d = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
    return np.abs(d - radius) <= half


def _changed(after: FloatImage, before: FloatImage) -> Any:
    return np.any(after != before, axis=-1)


def test_sun_texture_contained(ctx: Any, flat_base: Base) -> None:  # FR-36
    before = flat_base()
    after = draw_sun(before.copy(), SunLayer("sun", 540, 650, 300, 2, None, None), ctx, 1)
    outside = _circle_outside(540, 650, 300 + 18 + 3)
    assert np.array_equal(after[outside], before[outside])
    assert not np.array_equal(after[~outside], before[~outside])


def test_sun_uses_theme_defaults_and_layer_overrides(ctx: Any, flat_base: Base) -> None:
    layer = SunLayer("sun", 540, 650, 300, 0, None, None)
    default = draw_sun(flat_base(), layer, ctx, 1)
    explicit = SunLayer("sun", 540, 650, 300, 0, ctx.theme.textures.gold_leaf.tile, None)
    assert np.array_equal(default, draw_sun(flat_base(), explicit, ctx, 1))
    other = SunLayer("sun", 540, 650, 300, 0, 20, 0.05)
    assert not np.array_equal(default, draw_sun(flat_base(), other, ctx, 1))


def test_sun_rings(ctx: Any, palette: Any, flat_base: Base) -> None:
    base = flat_base()
    two = draw_sun(base.copy(), SunLayer("sun", 540, 650, 300, 2, None, None), ctx, 1)
    zero = draw_sun(base.copy(), SunLayer("sun", 540, 650, 300, 0, None, None), ctx, 1)
    outer = _ring_band(540, 650, 318, 1.0)
    assert np.array_equal(zero[outer], base[outer])  # no ring 2 when rings == 0
    assert _changed(two, base)[outer].mean() > 0.85
    dk = np.array(palette.rgb01("gold_dk"), dtype=np.float32)
    assert np.abs(two[650 + 318, 540] - dk).max() < 0.15  # the ring is gold_dk


def test_moon_single_ring(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    moon = draw_sun(base.copy(), SunLayer("moon", 770, 450, 125, 1, 26, 0.03), ctx, 1)
    outer = _ring_band(770, 450, 125 + 18, 2.0)
    assert np.array_equal(moon[outer], base[outer])  # no gold_dk ring at r + 18
    outside = _circle_outside(770, 450, 125 + SLACK)
    assert np.array_equal(moon[outside], base[outside])
    inner = _ring_band(770, 450, 125, 1.0)
    assert _changed(moon, base)[inner].all()


def test_moon_ring_is_thinner_than_sun_ring(ctx: Any, flat_base: Base) -> None:
    base = flat_base()
    outside = _circle_outside(540, 650, 300)
    hits = {}
    for kind in ("sun", "moon"):
        out = draw_sun(base.copy(), SunLayer(kind, 540, 650, 300, 1, None, None), ctx, 1)  # type: ignore[arg-type]
        hits[kind] = int((_changed(out, base) & outside).sum())
    # the stroke reaches width / 2 beyond r: 1.5 px for the sun, 1.25 px for the moon
    assert hits["sun"] > hits["moon"] > 0


def test_sun_deterministic(ctx: Any, flat_base: Base) -> None:
    layer = SunLayer("sun", 540, 650, 300, 2, 34, 0.05)
    a = draw_sun(flat_base(), layer, ctx, 1)
    b = draw_sun(flat_base(), layer, ctx, 1)
    assert a.dtype == np.float32 and a.shape == (HEIGHT, WIDTH, 3)
    assert np.array_equal(a, b)


CLOUDS = CloudsLayer((CloudItem(270, 318, 0.8, 1), CloudItem(860, 318, 0.8, -1)), "gold", 12, 0.9)


def _cloud_mask(layer: CloudsLayer) -> Any:
    cv = Canvas()
    cv.color((255, 255, 255))
    for item in layer.items:
        cloud_path(cv, item)
        cv.fill()
    return cv.mask()


def test_clouds_texture_contained(ctx: Any, flat_base: Base) -> None:  # FR-36
    before = flat_base()
    after = draw_clouds(before.copy(), CLOUDS, ctx, 2)
    near = binary_dilation(_cloud_mask(CLOUDS) > 0, iterations=SLACK)
    assert np.array_equal(after[~near], before[~near])
    assert _changed(after, before)[near].sum() > 1000


def test_cloud_flip_mirrors_about_item_x(ctx: Any, flat_base: Base) -> None:
    cv_a, cv_b = Canvas(), Canvas()
    for cv, flip in ((cv_a, 1), (cv_b, -1)):
        cv.color((255, 255, 255))
        cloud_path(cv, CloudItem(540, 600, 1.0, flip))
        cv.fill()
    a, b = cv_a.mask(), cv_b.mask()
    assert np.abs(a[:, ::-1] - b).max() < 0.1  # mirrored about x = 540
    assert np.abs(a - b).max() > 0.5  # the cloud is asymmetric, so a flip changes it


def test_cloud_outline_colour_follows_layer(ctx: Any, flat_base: Base) -> None:
    gold = draw_clouds(flat_base(), CLOUDS, ctx, 2)
    dark = draw_clouds(flat_base(), CloudsLayer(CLOUDS.items, "gold_dk", 12, 0.9), ctx, 2)
    assert not np.array_equal(gold, dark)
    # same eggshell fill: only the outline and curls differ
    diff = _changed(gold, dark)
    mask = _cloud_mask(CLOUDS)
    assert diff.sum() < 0.5 * (mask > 0.5).sum()
    assert not diff[~binary_dilation(mask > 0, iterations=SLACK)].any()


def test_clouds_deterministic_and_theme_defaults(ctx: Any, flat_base: Base) -> None:
    a = draw_clouds(flat_base(), CLOUDS, ctx, 2)
    assert np.array_equal(a, draw_clouds(flat_base(), CLOUDS, ctx, 2))
    spec = ctx.theme.textures.eggshell
    defaulted = CloudsLayer(CLOUDS.items, "gold", None, None)
    explicit = CloudsLayer(CLOUDS.items, "gold", spec.cell, spec.gap)
    assert np.array_equal(
        draw_clouds(flat_base(), defaulted, ctx, 2), draw_clouds(flat_base(), explicit, ctx, 2)
    )


def test_birds_drawn_at_positions(ctx: Any, flat_base: Base) -> None:
    items = (BirdItem(300, 400, 1.6), BirdItem(360, 440, 1.2))
    before = flat_base()
    after = draw_birds(before.copy(), BirdsLayer(items), ctx, 3)
    changed = _changed(after, before)
    yy, xx = np.nonzero(changed)
    assert changed.sum() > 40
    for item in items:  # each bird's wings span x +-12 s and rise no higher than 4.5 s
        near = (np.abs(xx - item.x) <= 12 * item.scale + 3) & (
            (yy - item.y >= -4.5 * item.scale - 3) & (yy - item.y <= 3)
        )
        assert near.sum() > 10
    far = ~(
        (np.abs(xx - 300) < 40) & (np.abs(yy - 400) < 20)
        | (np.abs(xx - 360) < 40) & (np.abs(yy - 440) < 20)
    )
    assert not far.any()


def test_registry_contains_sky_drawers() -> None:
    assert {SunLayer, CloudsLayer, BirdsLayer} <= set(LAYER_DRAWERS)
    with pytest.raises(TypeError):
        LAYER_DRAWERS[SunLayer] = draw_sun  # type: ignore[index]


def test_draw_layers_dispatches_with_index_k_plus_one(ctx: Any, flat_base: Base) -> None:
    sun = SunLayer("sun", 540, 650, 300, 2, 34, 0.05)
    clouds = CLOUDS
    birds = BirdsLayer((BirdItem(300, 400, 1.6),))
    combined = draw_layers(flat_base(), (sun, clouds, birds), ctx)
    step = draw_sun(flat_base(), sun, ctx, 1)
    step = draw_clouds(step, clouds, ctx, 2)
    step = draw_birds(step, birds, ctx, 3)
    assert np.array_equal(combined, step)


def test_draw_layers_unknown_type_names_class(ctx: Any, flat_base: Base) -> None:
    class Strange:
        pass

    with pytest.raises(TypeError, match="Strange"):
        draw_layers(flat_base(), (Strange(),), ctx)  # type: ignore[arg-type]
