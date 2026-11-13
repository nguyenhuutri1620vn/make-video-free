"""Living slides (M9): ambient sprite loops, drift planes and particles (AC-29)."""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest

from history_shorts.compose import SlideContext
from history_shorts.config import LivingSpec, load_script
from history_shorts.layout import REGIONS
from history_shorts.living.animate import Motion, animate_crop, transform_frame
from history_shorts.living.particles import particle_sprite
from history_shorts.living.planes import (
    DriftPlane,
    ScenePlane,
    SpritePlane,
    build_stack,
    recompose,
)
from history_shorts.render import scene_expander
from history_shorts.scene_config import LayerScene

SPEC = LivingSpec()
FRAMES = 60


def _blob(h: int = 80, w: int = 120) -> np.ndarray:
    """An opaque red ellipse in a transparent crop, with room to move."""
    yy, xx = np.mgrid[0:h, 0:w]
    inside = ((yy - h / 2) / (h / 4)) ** 2 + ((xx - w / 2) / (w / 4)) ** 2 <= 1
    rgba = np.zeros((h, w, 4), dtype=np.float32)
    rgba[inside] = (0.7, 0.1, 0.1, 1.0)
    return rgba


def _centroid_y(rgba: np.ndarray) -> float:
    a = rgba[..., 3]
    return float((a * np.arange(a.shape[0])[:, None]).sum() / a.sum())


@pytest.mark.parametrize("kind", ["bob", "sway", "ripple", "pulse", "float"])
def test_loop_seamless(kind: str) -> None:
    motion = Motion(kind, anchor=(60.0, 60.0), freq=2, sign=-1.0, flicker=(0.3, 1.1, 2.0))
    crop = _blob()
    start = transform_frame(crop, 0.0, motion, SPEC)
    end = transform_frame(crop, 1.0, motion, SPEC)
    assert np.allclose(start, end, atol=1e-5)
    assert not np.allclose(start, transform_frame(crop, 0.125, motion, SPEC), atol=1e-3)


def test_bob_amplitude() -> None:
    motion = Motion("bob", anchor=(60.0, 60.0))
    crop = _blob()
    ys = [_centroid_y(transform_frame(crop, i / FRAMES, motion, SPEC)) for i in range(FRAMES)]
    assert max(ys) - min(ys) == pytest.approx(2 * SPEC.bob_px, abs=0.5)


def test_ripple_keeps_alpha_mass() -> None:
    crop = _blob()
    out = transform_frame(crop, 0.3, Motion("ripple", anchor=(0, 0)), SPEC)
    assert out[..., 3].sum() == pytest.approx(crop[..., 3].sum(), rel=0.01)


def test_pulse_changes_only_brightness() -> None:
    crop = _blob()
    out = transform_frame(crop, 0.25, Motion("pulse", anchor=(0, 0)), SPEC)
    assert np.array_equal(out[..., 3], crop[..., 3])
    assert out[..., 0].max() == pytest.approx(0.7 * (1 + SPEC.glow_pulse), rel=1e-4)


def test_animate_crop_pads_and_origin() -> None:
    full = np.zeros((300, 400, 4), dtype=np.float32)
    full[100:180, 150:270] = _blob()
    ys, xs = np.nonzero(full[..., 3] > 0)
    crop, origin = animate_crop(full, margin=10)
    assert origin == (int(xs.min()) - 10, int(ys.min()) - 10)
    assert crop.shape[:2] == (int(ys.max() - ys.min()) + 21, int(xs.max() - xs.min()) + 21)
    assert crop[..., 3].sum() == pytest.approx(full[..., 3].sum())


def test_particles_stay_in_region(theme: Any) -> None:
    region = REGIONS["visual"]
    rng = np.random.default_rng(3)
    sprite = particle_sprite("petals", SPEC, theme.palette, rng, FRAMES, region)
    assert sprite.origin == (int(region.x0), int(region.y0))
    for i in (0, 13, 41):
        frame = sprite.frame(i / FRAMES)
        assert frame.shape[:2] == (int(region.y1 - region.y0), int(region.x1 - region.x0))
        assert frame[..., 3].max() > 0
    assert np.allclose(sprite.frame(0.0), sprite.frame(1.0), atol=1e-5)


def _river_script(theme: Any) -> Any:
    from pathlib import Path

    script = load_script(Path("examples/hai_ba_trung/script.json"))[0]
    for slide in script.slides:
        if isinstance(slide.scene, LayerScene) and any(
            type(layer).__name__ in ("BoatLayer", "RiverLayer", "SailBoatLayer")
            for layer in slide.scene.layers
        ):
            return dataclasses.replace(script, slides=(dataclasses.replace(slide, living=True),))
    pytest.skip("no water slide in the example")


def test_build_stack_pulls_out_animated_layers(theme: Any) -> None:
    from history_shorts.compose import render_slide
    from history_shorts.living.depth import scene_layers

    script = _river_script(theme)
    style, draw = scene_expander(script.slides[0], theme)
    ctx = SlideContext(script, theme, 0, style, draw, False, None)
    layers, depths = scene_layers(script.slides[0], theme)
    stack = build_stack(ctx, layers, depths, animated=True)
    kinds = [type(p).__name__ for p in stack.scene]
    assert "SpritePlane" in kinds
    assert isinstance(stack.scene[0], ScenePlane) and stack.scene[0].opaque
    flat = np.asarray(render_slide(ctx), dtype=np.float32)
    diff = np.abs(recompose(stack) * 255 - flat)
    assert diff.mean() <= 1.0 and np.percentile(diff, 99.99) <= 3
    again = build_stack(ctx, layers, depths, animated=True)
    for a, b in zip(stack.scene, again.scene, strict=True):
        if isinstance(a, SpritePlane) and isinstance(b, SpritePlane):
            assert np.array_equal(a.frame(0.4), b.frame(0.4))
        elif isinstance(a, DriftPlane | ScenePlane):
            assert np.array_equal(a.rgba, b.rgba)  # type: ignore[union-attr]
