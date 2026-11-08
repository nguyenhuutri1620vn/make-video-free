"""Tests for history_shorts.compose: compositing core, RNG derivation, FR-21 assembly."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from PIL import Image

from history_shorts import compose
from history_shorts.canvas import Canvas
from history_shorts.compose import (
    FINISH_LAYER,
    GROUND_LAYER,
    SLIDE_STEPS,
    DrawContext,
    SceneStyle,
    SlideContext,
    default_style,
    eggshell_rng,
    fill_mask,
    over,
    render_slide,
    rng_for,
)
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.primitives import FloatImage
from history_shorts.text import plan_text


def test_over_uses_premultiplied_alpha() -> None:
    base = np.full((4, 4, 3), 0.5, np.float32)
    cv = Canvas(4, 4)
    cv.color((255, 0, 0), 0.5).rect(0, 0, 4, 4).fill()
    assert np.allclose(over(base, cv)[0, 0], [0.75, 0.25, 0.25], atol=2 / 255)


def test_over_empty_canvas_is_identity() -> None:
    base = np.random.default_rng(1).random((6, 5, 3), dtype=np.float32)
    assert np.array_equal(over(base, Canvas(5, 6)), base)


def test_fill_mask_never_leaks() -> None:
    base = np.random.default_rng(0).random((10, 10, 3), dtype=np.float32)
    tex = np.ones_like(base)
    mask = np.zeros((10, 10), np.float32)
    mask[2:5, 2:5] = 1
    out = fill_mask(base, tex, mask)
    assert np.array_equal(out[mask == 0], base[mask == 0])
    assert np.array_equal(out[mask == 1], tex[mask == 1])


def test_rng_for_is_deterministic_and_distinct() -> None:
    assert rng_for(40, 0, 1).random() == rng_for(40, 0, 1).random()
    assert rng_for(40, 0, 1).random() != rng_for(40, 0, 2).random()
    assert rng_for(40, 0, 1).random() != rng_for(40, 1, 1).random()
    assert rng_for(40, 0, 1).random() != rng_for(41, 0, 1).random()


def test_layer_constants() -> None:
    assert GROUND_LAYER == 0
    assert FINISH_LAYER == 999


def test_eggshell_rng_ignores_slide_index_but_tracks_mask(cloud_mask: Any) -> None:
    a = eggshell_rng(40, 3, cloud_mask).random()
    assert a == eggshell_rng(40, 3, cloud_mask).random()
    # the draw context exposes it without a slide index, so any slide gets the same stream
    assert DrawContext(None, None, 40, 0).eggshell_rng(3, cloud_mask).random() == a  # type: ignore[arg-type]
    assert DrawContext(None, None, 40, 7).eggshell_rng(3, cloud_mask).random() == a  # type: ignore[arg-type]
    other = cloud_mask.copy()
    other[0:50, 0:50] = 1
    assert eggshell_rng(40, 3, other).random() != a
    assert eggshell_rng(40, 4, cloud_mask).random() != a
    assert eggshell_rng(41, 3, cloud_mask).random() != a


def test_eggshell_rng_thresholds_mask_at_half(cloud_mask: Any) -> None:
    soft = np.where(cloud_mask > 0.5, 0.9, 0.1).astype(np.float32)
    assert eggshell_rng(1, 1, soft).random() == eggshell_rng(1, 1, cloud_mask).random()


def test_draw_context_rng_matches_rng_for(theme: Any) -> None:
    dc = DrawContext(theme, theme.palette, 40, 2)
    assert dc.rng(5).random() == rng_for(40, 2, 5).random()


def test_steps_order_is_fr21() -> None:
    assert SLIDE_STEPS == (
        "ground",
        "scene",
        "waves",
        "finish",
        "frame",
        "seal",
        "tag",
        "title",
        "subtitle",
        "progress_bar",
        "footer",
    )


def test_default_style(theme: Any) -> None:
    style = default_style(theme)
    assert style == SceneStyle(("black", "deep", "black"), theme.textures.sheen, theme.seed)


def test_chrome_and_text_slide(theme: Any, script_one_slide: Any) -> None:
    img = render_slide(SlideContext(script_one_slide, theme, 0, default_style(theme), None, False))
    assert img.size == (CANVAS_W, CANVAS_H) and img.mode == "RGB"
    # text was drawn: some pixel in the title band is much lighter than the dark ground
    band = np.asarray(img)[1200:1400]
    assert band.max() > 150


def test_render_is_deterministic(theme: Any, script_one_slide: Any) -> None:
    ctx = SlideContext(script_one_slide, theme, 0, default_style(theme), None, False)
    assert render_slide(ctx).tobytes() == render_slide(ctx).tobytes()


def test_steps_run_in_fr21_order(
    theme: Any, script_one_slide: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    steps = dict(compose.STEP_FUNCTIONS)
    for name in SLIDE_STEPS:
        original = steps[name]

        def spy(ctx: SlideContext, state: Any, _n: str = name, _o: Any = original) -> None:
            calls.append(_n)
            _o(ctx, state)

        steps[name] = spy
    monkeypatch.setattr(compose, "STEP_FUNCTIONS", steps)
    render_slide(SlideContext(script_one_slide, theme, 0, default_style(theme), None, False))
    assert calls == list(SLIDE_STEPS)


def test_scene_callback_gets_draw_context_and_result_is_used(
    theme: Any, script_one_slide: Any
) -> None:
    seen: list[DrawContext] = []

    def draw(img: FloatImage, dc: DrawContext) -> FloatImage:
        seen.append(dc)
        out = img.copy()
        out[600:700, 100:200] = 1.0
        return out

    ctx = SlideContext(script_one_slide, theme, 0, default_style(theme), draw, False)
    img = render_slide(ctx)
    assert len(seen) == 1
    assert (seen[0].seed, seen[0].slide_index) == (theme.seed, 0)
    assert seen[0].palette is theme.palette
    assert np.asarray(img)[650, 150].min() > 200  # survives finish (clip at 1) and is white-ish


def test_ground_style_changes_output(theme: Any, script_one_slide: Any) -> None:
    base = default_style(theme)
    a = render_slide(SlideContext(script_one_slide, theme, 0, base, None, False))
    flipped = replace(base, ground=("deep", "black", "deep"))
    b = render_slide(SlideContext(script_one_slide, theme, 0, flipped, None, False))
    assert a.tobytes() != b.tobytes()


def test_debug_safe_zone_draws_pink_outline(theme: Any, script_one_slide: Any) -> None:
    plain = SlideContext(script_one_slide, theme, 0, default_style(theme), None, False)
    debug = replace(plain, debug_safe_zone=True)
    a = np.asarray(render_slide(plain))
    b = np.asarray(render_slide(debug))
    assert not np.array_equal(a, b)
    pink = theme.palette["pink"]
    # safe zone top edge (y=160, x in 80..930) is pink
    assert tuple(b[160, 500]) == pink or tuple(b[161, 500]) == pink
    # nothing outside the outlines changed: a pixel far from any outline is identical
    assert np.array_equal(a[1000, 500], b[1000, 500])


def test_image_is_converted_once_and_float_steps_cannot_follow(
    theme: Any, script_one_slide: Any
) -> None:
    state = compose.SlideState(np.zeros((4, 4, 3), np.float32))
    arr = state.array()
    assert arr.shape == (4, 4, 3)
    image = state.image()
    assert isinstance(image, Image.Image)
    assert state.image() is image
    with pytest.raises(RuntimeError, match="after PIL conversion"):
        state.array()
    with pytest.raises(RuntimeError, match="after PIL conversion"):
        state.set_array(arr)


def test_step_registry_covers_all_steps() -> None:
    assert set(compose.STEP_FUNCTIONS) == set(SLIDE_STEPS)


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        (np.zeros((CANVAS_H, CANVAS_W, 3), np.float64), TypeError),
        (np.zeros((CANVAS_H, CANVAS_W), np.float32), ValueError),
        (np.zeros((10, 10, 3), np.float32), ValueError),
    ],
)
def test_scene_callback_result_is_validated(
    theme: Any, script_one_slide: Any, bad: Any, error: type[Exception]
) -> None:
    ctx = SlideContext(script_one_slide, theme, 0, default_style(theme), lambda img, dc: bad, False)
    with pytest.raises(error):
        render_slide(ctx)


def test_text_is_drawn_after_finish_and_carries_no_grain(theme: Any, script_one_slide: Any) -> None:
    base = default_style(theme)
    other = replace(base, seed=base.seed + 1)  # different ground and grain RNG
    a = np.asarray(
        render_slide(SlideContext(script_one_slide, theme, 0, base, None, False))
    ).astype(int)
    b = np.asarray(
        render_slide(SlideContext(script_one_slide, theme, 0, other, None, False))
    ).astype(int)
    plan = plan_text(script_one_slide.slides[0], theme)
    title_color = np.array(theme.palette[plan.lines[0].color_key])
    box = plan.title_box
    ys, xs = slice(int(box.y0), int(box.y1)), slice(int(box.x0), int(box.x1))
    interior = (a[ys, xs] == title_color).all(axis=-1)
    assert interior.sum() > 500  # glyph interiors hold the exact palette colour
    # the same pixels are exactly the palette colour in the render with other grain
    assert (b[ys, xs][interior] == title_color).all()
    # while the background (outside the text boxes) does differ between the two renders
    assert (a[300:900] != b[300:900]).any()


# --------------------------------------------------------------------------------------
# Eggshell cache (FR-66)
# --------------------------------------------------------------------------------------


def _blob_mask() -> Any:
    cv = Canvas(CANVAS_W, CANVAS_H)
    cv.color((255, 255, 255)).ellipse(400, 600, 120, 60).fill()
    return cv.mask()


def test_cache_hit_returns_identical_array_and_skips_compute(
    theme: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from history_shorts import textures
    from history_shorts.compose import EggshellCache
    from history_shorts.scene import inlay

    calls: list[int] = []
    real = textures.eggshell

    def counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(inlay, "eggshell", counting)
    cache = EggshellCache()
    ctx = DrawContext(theme, theme.palette, theme.seed, 0, cache)
    other = DrawContext(theme, theme.palette, theme.seed, 5, cache)  # another slide
    mask = _blob_mask()
    first = inlay.eggshell_texture(ctx, 3, mask, 15, 1.0)
    second = inlay.eggshell_texture(other, 3, mask, 15, 1.0)
    assert second is first
    assert len(calls) == 1
    assert (cache.hits, cache.misses) == (1, 1)
    assert not first.flags.writeable


def test_cache_key_changes_with_each_component(theme: Any) -> None:
    from history_shorts.compose import EggshellCache

    mask = _blob_mask()
    other = mask.copy()
    other[0, 0] = 1.0
    base = EggshellCache.key(mask, 15, 1.0, 40, 3)
    assert base == EggshellCache.key(mask.copy(), 15, 1.0, 40, 3)
    for changed in (
        EggshellCache.key(other, 15, 1.0, 40, 3),
        EggshellCache.key(mask, 16, 1.0, 40, 3),
        EggshellCache.key(mask, 15, 1.5, 40, 3),
        EggshellCache.key(mask, 15, 1.0, 41, 3),
        EggshellCache.key(mask, 15, 1.0, 40, 4),
        EggshellCache.key(mask[:, :-1], 15, 1.0, 40, 3),
    ):
        assert changed != base


def test_cache_without_context_cache_computes_directly(theme: Any) -> None:
    from history_shorts.scene import inlay

    ctx = DrawContext(theme, theme.palette, theme.seed, 0)
    mask = _blob_mask()
    a = inlay.eggshell_texture(ctx, 3, mask, 15, 1.0)
    b = inlay.eggshell_texture(ctx, 3, mask, 15, 1.0)
    assert a is not b
    assert np.array_equal(a, b)


def test_render_identical_with_and_without_cache(repo_root: Any, theme: Any, tmp_path: Any) -> None:
    from history_shorts.config import load_script
    from history_shorts.render import render_slides, scene_expander

    script, _ = load_script(repo_root / "examples" / "nu_tuong" / "script.json")
    with_cache = render_slides(
        script, theme, tmp_path / "a" / "v.mp4", debug_safe_zone=False, expand=scene_expander
    )
    without = render_slides(
        script,
        theme,
        tmp_path / "b" / "v.mp4",
        debug_safe_zone=False,
        expand=scene_expander,
        eggshell_cache=False,
    )
    assert len(with_cache) == len(without) == len(script.slides)
    assert all(x.read_bytes() == y.read_bytes() for x, y in zip(with_cache, without, strict=True))
