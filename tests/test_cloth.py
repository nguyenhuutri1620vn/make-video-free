"""M10: the flag-cloth wave used by banners, the elephant flag and character flags."""

from __future__ import annotations

import pytest

from history_shorts.scene.cloth import ClothWave, wave_point

POLE, WIDTH, AMP = 100.0, 80.0, 0.12


@pytest.mark.parametrize("phase", [0.0, 0.2, 0.5, 0.9])
def test_wave_zero_at_pole(phase: float) -> None:
    assert wave_point(POLE, 40.0, POLE, WIDTH, phase, AMP, 0.3) == (POLE, 40.0)


@pytest.mark.parametrize("x", [110.0, 140.0, 180.0, 60.0])
def test_wave_identity_at_phase0(x: float) -> None:
    assert wave_point(x, 40.0, POLE, WIDTH, 0.0, AMP, 1.1) == (x, 40.0)


def test_wave_periodic() -> None:
    a = wave_point(170.0, 40.0, POLE, WIDTH, 0.0, AMP, 0.7)
    b = wave_point(170.0, 40.0, POLE, WIDTH, 1.0, AMP, 0.7)
    assert b == pytest.approx(a, abs=1e-9)


def test_wave_bounded_and_moving() -> None:
    ys = [wave_point(180.0, 40.0, POLE, WIDTH, p / 20, AMP, 0.0)[1] - 40.0 for p in range(20)]
    assert max(abs(y) for y in ys) <= 2 * AMP * WIDTH + 1e-9
    assert max(abs(y) for y in ys) > 0.5 * AMP * WIDTH


def test_cloth_wave_maps_points() -> None:
    cloth = ClothWave(POLE, WIDTH, 0.25, AMP, 0.0)
    assert cloth.pt(POLE, 10.0) == (POLE, 10.0)
    assert cloth.pt(POLE + WIDTH, 10.0) == wave_point(POLE + WIDTH, 10.0, POLE, WIDTH, 0.25, AMP, 0)
