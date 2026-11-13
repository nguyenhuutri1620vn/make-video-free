"""Write a living slide's planes and sprite frames as PNG files for the FFmpeg clip.

Scene planes are padded by their travel margin with edge replication, so moving them never
shows an edge. PNG alpha is straight, so premultiplied planes are divided by alpha first.
Everything goes under a directory the caller owns (the render's temp area).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal

import numpy as np
from PIL import Image

from history_shorts import cues
from history_shorts.compose import EggshellCache, SlideContext
from history_shorts.config import LivingSpec, Script, Theme
from history_shorts.living.depth import scene_layers
from history_shorts.living.planes import LivingStack, build_stack
from history_shorts.living.types import (
    SHEEN_PNG_GAIN,
    AnyPlane,
    DriftPlane,
    FloatRGBA,
    LivingClip,
    PlaneFile,
    SpritePlane,
)
from history_shorts.primitives import FloatImage
from history_shorts.render import scene_expander
from history_shorts.scene_config import Depth

PNG_LEVEL: Final = 1  # fast: these files are read once by FFmpeg and then deleted
PAD_SLACK: Final = 2
ASPECT: Final = (9, 16)  # CANVAS_W : CANVAS_H in lowest terms


def living_pad(depth: Depth, spec: LivingSpec, drift: float, duration: float) -> tuple[int, int]:
    """Edge padding (px, py) of a plane: travel + shake + drift over the clip, aspect-locked."""
    need = spec.travel_px[depth] + spec.shake_px + abs(drift) * duration + PAD_SLACK
    unit = math.ceil(need / ASPECT[0])  # whole (9, 16) steps keep the padded image 9:16 exactly
    return unit * ASPECT[0], unit * ASPECT[1]


def write_png_rgba(rgba: FloatRGBA, path: Path) -> None:
    """Premultiplied float RGBA → straight-alpha 8-bit PNG."""
    alpha = rgba[..., 3:]
    rgb = np.divide(rgba[..., :3], alpha, out=np.zeros_like(rgba[..., :3]), where=alpha > 0)
    out = np.concatenate([np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)], axis=-1)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA").save(path, compress_level=PNG_LEVEL)


def _write_rgb(rgb: FloatImage, path: Path) -> None:
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(
        path, compress_level=PNG_LEVEL
    )


def _padded(rgba: FloatRGBA, pad: tuple[int, int]) -> FloatRGBA:
    px, py = pad
    return np.pad(rgba, ((py, py), (px, px), (0, 0)), mode="edge")


def _write_plane(
    plane: AnyPlane, index: int, directory: Path, spec: LivingSpec, duration: float
) -> PlaneFile:
    drift = plane.velocity[0] if isinstance(plane, DriftPlane) else 0.0
    pad = living_pad(plane.depth, spec, drift, duration)
    if isinstance(plane, SpritePlane):
        frames_dir = directory / f"sprite_{index:02d}"
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i in range(plane.frames):
            write_png_rgba(plane.frame(i / plane.frames), frames_dir / f"{i:03d}.png")
        origin = (plane.origin[0] + pad[0], plane.origin[1] + pad[1])
        first = frames_dir / "000.png"
        return PlaneFile(
            "sprite", plane.depth, first, plane.frames, origin, (0.0, 0.0), pad, plane.size
        )
    path = directory / f"plane_{index:02d}.png"
    padded = _padded(plane.rgba, pad)
    write_png_rgba(padded, path)
    kind: Literal["static", "drift"] = "drift" if isinstance(plane, DriftPlane) else "static"
    velocity = plane.velocity if isinstance(plane, DriftPlane) else (0.0, 0.0)
    size = (padded.shape[0], padded.shape[1])
    return PlaneFile(kind, plane.depth, path, 1, (0, 0), velocity, pad, size)


def write_living(
    stack: LivingStack,
    directory: Path,
    spec: LivingSpec,
    duration: float,
    shakes: tuple[float, ...],
) -> LivingClip:
    """Write ``stack`` under ``directory``; ``duration`` is the clip length (overlap included)."""
    directory.mkdir(parents=True, exist_ok=True)
    planes = tuple(
        _write_plane(plane, k, directory, spec, duration) for k, plane in enumerate(stack.scene)
    )
    top = stack.top
    write_png_rgba(top.waves, directory / "waves.png")
    _write_rgb(top.sheen * SHEEN_PNG_GAIN, directory / "sheen.png")
    write_png_rgba(top.chrome, directory / "chrome.png")
    text = None
    if top.text is not None:
        text = directory / "text.png"
        write_png_rgba(top.text, text)
    return LivingClip(
        planes,
        directory / "waves.png",
        directory / "sheen.png",
        directory / "chrome.png",
        text,
        shakes,
    )


def render_living(
    script: Script, theme: Theme, durations: Sequence[float], root: Path
) -> tuple[LivingClip | None, ...]:
    """The living clips of a script (None for still slides), written under ``root/NN/``.

    ``durations`` are the slide lengths; each clip is padded for the longest possible
    transition overlap on top of its slide."""
    cache = EggshellCache()
    clips: list[LivingClip | None] = []
    for index, slide in enumerate(script.slides):
        if not slide.living:
            clips.append(None)
            continue
        style, draw = scene_expander(slide, theme)
        ctx = SlideContext(script, theme, index, style, draw, False, cache)
        layers, depths = scene_layers(slide, theme)
        stack = build_stack(ctx, layers, depths)
        duration = durations[index] + theme.transition.duration
        target = root / f"{index + 1:02d}"
        clips.append(write_living(stack, target, theme.living, duration, cues.shake_times(slide)))
    return tuple(clips)
