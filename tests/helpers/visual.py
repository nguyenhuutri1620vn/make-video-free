"""Perceptual comparison against the owner-approved reference images (AC-03, AC-04).

Each region's mean sRGB colour is converted to CIE Lab (D65 white) and compared with the
reference's by ΔE76, the Euclidean distance in Lab. A mean colour is deliberately coarse: it
checks palette, ground and overall composition balance, not line quality. Owner sign-off on
the preview PNGs is still required.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import numpy as np
import numpy.typing as npt

from history_shorts.primitives import Box

FloatArray = npt.NDArray[np.float64]

# sRGB (D65) to XYZ, IEC 61966-2-1, and the D65 reference white.
_RGB_TO_XYZ: Final = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ]
)
_WHITE_D65: Final = np.array([0.95047, 1.0, 1.08883])
_LAB_EPSILON: Final = 216 / 24389  # (6/29) ** 3
_LAB_KAPPA: Final = 24389 / 27


def srgb_to_lab(rgb: npt.NDArray[np.uint8]) -> FloatArray:
    """CIE Lab (D65) of 8-bit sRGB values; the last axis (3) is replaced by L, a, b."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    linear = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = linear @ _RGB_TO_XYZ.T / _WHITE_D65
    f = np.where(xyz > _LAB_EPSILON, np.cbrt(xyz), (_LAB_KAPPA * xyz + 16) / 116)
    lightness = 116 * f[..., 1] - 16
    return np.stack([lightness, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def _mean_lab(img: npt.NDArray[np.uint8], box: Box) -> FloatArray:
    """Lab of the region's mean colour (not the mean of per-pixel Lab values)."""
    region = img[int(box.y0) : int(box.y1), int(box.x0) : int(box.x1)]
    mean = region.reshape(-1, 3).astype(np.float64).mean(axis=0)
    return srgb_to_lab(mean)


def region_delta_e(
    img: npt.NDArray[np.uint8], ref: npt.NDArray[np.uint8], regions: Mapping[str, Box]
) -> dict[str, float]:
    """ΔE76 between the mean colours of ``img`` and ``ref``, per named region."""
    if img.shape != ref.shape:
        raise ValueError(f"image shapes differ: {img.shape} vs {ref.shape}")
    return {
        name: float(np.linalg.norm(_mean_lab(img, box) - _mean_lab(ref, box)))
        for name, box in regions.items()
    }
