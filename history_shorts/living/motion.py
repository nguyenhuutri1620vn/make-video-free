"""FFmpeg expressions and filter chains that move a living slide's planes.

Each scene plane is a padded image; ``zoompan`` cuts a 1080x1920 window out of it whose
position follows the camera (scaled by the plane's depth), its own drift and any hit shake.
All motion is eased (``(1 - cos(pi t)) / 2``), so it starts and stops softly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final, Literal

from history_shorts.config import LivingSpec
from history_shorts.layout import CANVAS_H, CANVAS_W
from history_shorts.living.types import PlaneFile
from history_shorts.scene_config import Depth

ZOOM_STEP: Final = 0.06  # zoom_in / zoom_out change, as in the still motions (FR-84)
SHAKE_HZ: Final = {"x": 9.0, "y": 7.0}
SHAKE_PHASE: Final = {"x": 0.0, "y": math.pi / 2}
SHAKE_SPAN: Final = 3.0  # a shake lasts this many time constants


def _f(value: float) -> str:
    return f"{value:.6g}"


def eased(frames: int) -> str:
    """Progress 0 → 1 over ``frames`` output frames, with soft ends."""
    return f"(1-cos(PI*min(on/{frames},1)))/2"


def camera(motion: str, depth: Depth, spec: LivingSpec) -> tuple[float, float, float]:
    """(dx, dy, dzoom) a plane reaches at the end of the clip: window offset in output px
    (positive = window moves right/down) and zoom change."""
    travel, factor = spec.travel_px[depth], spec.zoom_factor[depth]
    table = {
        "pan_left": (-travel, 0.0, 0.0),
        "pan_right": (travel, 0.0, 0.0),
        "pan_up": (0.0, -travel, 0.0),
        "pan_down": (0.0, travel, 0.0),
        "zoom_in": (0.0, 0.0, ZOOM_STEP * factor),
        "zoom_out": (0.0, 0.0, -ZOOM_STEP * factor),
        "none": (spec.idle_drift * travel, 0.0, 0.0),
    }
    if motion not in table:
        raise ValueError(f"unknown motion {motion!r}")
    return table[motion]


def shake_expr(
    times: tuple[float, ...], spec: LivingSpec, fps: int, axis: Literal["x", "y"]
) -> str:
    """Damped shake (output px) after each hit time, or ``0``."""
    if not times or spec.shake_px <= 0:
        return "0"
    tau = spec.shake_seconds / SHAKE_SPAN
    w, phase = 2 * math.pi * SHAKE_HZ[axis], SHAKE_PHASE[axis]
    terms = [
        f"between(on/{fps},{_f(t0)},{_f(t0 + SHAKE_SPAN * tau)})"
        f"*{_f(spec.shake_px)}*exp(-(on/{fps}-{_f(t0)})/{_f(tau)})"
        f"*sin({_f(w)}*(on/{fps}-{_f(t0)})+{_f(phase)})"
        for t0 in times
    ]
    return "+".join(terms)


def _zoom_expr(base: float, dzoom: float, progress: str) -> str:
    if dzoom >= 0:
        return f"{_f(base)}*(1+{_f(dzoom)}*{progress})"
    return f"{_f(base)}*(1+{_f(-dzoom)}*(1-{progress}))"


PLANE_FORMAT: Final = "yuva444p"  # full chroma: 4:2:0 per plane smears red and gold edges


def plane_groups(planes: Sequence[PlaneFile]) -> list[list[int]]:
    """Runs of consecutive planes that move together (same depth, drift and padding)."""
    groups: list[list[int]] = []
    for i, plane in enumerate(planes):
        key = (plane.depth, plane.velocity, plane.pad)
        if groups and _key(planes[groups[-1][0]]) == key:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def _key(plane: PlaneFile) -> tuple[str, tuple[float, float], tuple[int, int]]:
    return plane.depth, plane.velocity, plane.pad


def source(index: int, plane: PlaneFile | None = None) -> str:
    """The stream label of input ``index``: stills are looped in the graph (``still_loop``),
    sprite sequences are read as they are (``-stream_loop``)."""
    return f"{index}:v" if plane is not None and plane.kind == "sprite" else f"in{index}"


def still_loop(index: int, frames: int, fps: int) -> str:
    """Repeat a single decoded still ``frames`` times; looping the input instead re-decodes
    every frame and queues dozens of them (about 180 MB per 1184x2104 input)."""
    return f"[{index}:v]loop=loop={frames - 1}:size=1:start=0,setpts=N/{fps}/TB[in{index}]"


def _stack(indices: Sequence[int], planes: Sequence[PlaneFile], fps: int, duration: float) -> str:
    """Overlay one group's planes on their padded canvas; ends with an open chain."""
    first = planes[indices[0]]
    width, height = CANVAS_W + 2 * first.pad[0], CANVAS_H + 2 * first.pad[1]
    tag = f"g{indices[0]}"
    parts: list[str] = []
    rest = list(indices)
    if first.kind == "sprite":
        parts.append(
            f"color=c=black@0:s={width}x{height}:r={fps}:d={_f(duration)},"
            f"format={PLANE_FORMAT}[{tag}a]"
        )
    else:
        parts.append(f"[{source(indices[0], first)}]format={PLANE_FORMAT}[{tag}a]")
        rest = rest[1:]
    current = f"{tag}a"
    for n, i in enumerate(rest):
        x, y = planes[i].origin
        parts.append(f"[{source(i, planes[i])}]format={PLANE_FORMAT}[{tag}i{n}]")
        parts.append(f"[{current}][{tag}i{n}]overlay={x}:{y}:format=auto[{tag}o{n}]")
        current = f"{tag}o{n}"
    return ";".join(parts) + f";[{current}]"


def group_graph(
    indices: Sequence[int],
    planes: Sequence[PlaneFile],
    motion: str,
    duration: float,
    fps: int,
    spec: LivingSpec,
    shakes: tuple[float, ...],
    label: str,
) -> str:
    """One group of planes stacked, then cut as a moving 1080x1920 window into ``[label]``."""
    plane = planes[indices[0]]
    frames = max(round(duration * fps), 1)
    progress = eased(frames)
    dx, dy, dzoom = camera(motion, plane.depth, spec)
    width = CANVAS_W + 2 * plane.pad[0]
    height = CANVAS_H + 2 * plane.pad[1]
    k = spec.prescale
    vx, vy = plane.velocity
    shift_x = f"({_f(dx)}*{progress}-({_f(vx)})*on/{fps}+{shake_expr(shakes, spec, fps, 'x')})"
    shift_y = f"({_f(dy)}*{progress}-({_f(vy)})*on/{fps}+{shake_expr(shakes, spec, fps, 'y')})"
    x = f"iw/2-iw/zoom/2+{shift_x}*iw/(zoom*{CANVAS_W})"
    y = f"ih/2-ih/zoom/2+{shift_y}*ih/(zoom*{CANVAS_H})"
    z = _zoom_expr(width / CANVAS_W, dzoom, progress)
    return (
        f"{_stack(indices, planes, fps, duration)}scale={width * k}:{height * k}:flags=neighbor,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={CANVAS_W}x{CANVAS_H}:fps={fps},"
        f"format={PLANE_FORMAT}[{label}]"
    )
