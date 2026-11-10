from __future__ import annotations

import math

import numpy as np
import pytest

from history_shorts.canvas import Canvas

GOLD = (212, 166, 76)


def test_premultiplied_bgra_to_rgb() -> None:
    cv = Canvas(8, 8)
    cv.color(GOLD).rect(0, 0, 8, 8).fill()
    rgb, a = cv.to_premul()
    assert np.allclose(rgb[4, 4], np.array(GOLD) / 255, atol=1 / 255)
    assert a[4, 4] == 1


def test_half_alpha_is_premultiplied() -> None:
    cv = Canvas(8, 8)
    cv.color(GOLD, 0.5).rect(0, 0, 8, 8).fill()
    rgb, a = cv.to_premul()
    assert np.allclose(rgb[4, 4], np.array(GOLD) / 255 * 0.5, atol=2 / 255)
    assert a[4, 4] == pytest.approx(0.5, abs=0.01)


def test_mask_of_ellipse() -> None:
    cv = Canvas(100, 100)
    cv.color((255, 255, 255)).ellipse(50, 50, 30, 10).fill()
    m = cv.mask()
    assert m[50, 50] == 1
    assert m[2, 2] == 0
    assert m.dtype == np.float32
    # rx=30 along x, ry=10 along y: swapped radii would invert these probes
    assert m[50, 75] == 1
    assert m[50, 90] == 0
    assert m[35, 50] == 0
    assert m[58, 50] == 1


def test_vgrad_endpoints() -> None:
    cv = Canvas(4, 100)
    cv.vgrad(0, 100, [(0, (255, 0, 0), 1), (1, (0, 0, 255), 1)]).rect(0, 0, 4, 100).fill()
    rgb, _ = cv.to_premul()
    assert rgb[0, 0, 0] > 0.95
    assert rgb[99, 0, 2] > 0.95


def test_odd_width_stride_padding() -> None:
    cv = Canvas(7, 5)
    cv.color(GOLD).rect(0, 0, 7, 5).fill()
    rgb, a = cv.to_premul()
    assert rgb.shape == (5, 7, 3)
    assert a.shape == (5, 7)
    assert rgb.dtype == np.float32
    assert np.allclose(rgb[:, 6], np.array(GOLD) / 255, atol=1 / 255)
    assert cv.mask().shape == (5, 7)


def test_to_premul_returns_copy() -> None:
    cv = Canvas(8, 8)
    cv.color(GOLD).rect(0, 0, 8, 8).fill()
    rgb, _ = cv.to_premul()
    rgb[:] = 0
    rgb2, _ = cv.to_premul()
    assert rgb2[4, 4, 0] > 0.5


def test_default_size() -> None:
    cv = Canvas()
    assert (cv.surface.get_width(), cv.surface.get_height()) == (1080, 1920)


def test_rgrad_center_and_outside() -> None:
    cv = Canvas(50, 50)
    cv.rgrad(25, 25, 10, [(0, (255, 255, 255), 1), (1, (255, 255, 255), 0)])
    cv.rect(0, 0, 50, 50).fill()
    _, a = cv.to_premul()
    assert a[25, 25] > 0.9
    assert a[0, 0] == 0


def test_clip_restricts_fill() -> None:
    cv = Canvas(20, 20)
    cv.save()
    cv.rect(0, 0, 10, 20).clip()
    cv.color(GOLD).rect(0, 0, 20, 20).fill()
    cv.restore()
    m = cv.mask()
    assert m[10, 5] == 1
    assert m[10, 15] == 0


def test_transforms_and_stroke() -> None:
    cv = Canvas(40, 40)
    cv.save()
    cv.translate(20, 20)
    cv.scale(2, 2)
    cv.rotate(math.pi / 2)
    # horizontal stroke in local space, thin enough to tell axes apart
    cv.color(GOLD).M(-8, 0).L(8, 0).stroke(2)
    cv.restore()
    m = cv.mask()
    assert m[20, 20] == 1
    assert m[8, 20] == 1  # vertical extent: 16 local units * 2 scale / 2 = +-16
    assert m[32, 20] == 1
    assert m[20, 8] == 0  # no horizontal extent after rotation
    assert m[20, 32] == 0
    assert m[5, 5] == 0


def test_zero_radius_ellipse_is_noop_and_canvas_stays_usable() -> None:
    cv = Canvas(10, 10)
    cv.color(GOLD).ellipse(5, 5, 0, 3).fill()
    cv.ellipse(5, 5, 3, 0).fill()
    cv.ellipse(5, 5, -2, 2).fill()
    assert cv.mask().max() == 0
    cv.rect(0, 0, 10, 10).fill()
    assert cv.mask()[5, 5] == 1
    cv.save()
    cv.restore()


def test_new_path_discards_and_keep_preserves() -> None:
    cv = Canvas(20, 20)
    cv.color(GOLD).rect(0, 0, 10, 10).fill(keep=True).stroke(1)
    cv.rect(12, 12, 6, 6).new_path()
    cv.fill()
    m = cv.mask()
    assert m[5, 5] == 1
    assert m[15, 15] == 0
