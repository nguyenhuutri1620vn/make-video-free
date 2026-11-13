"""Living slides (M9): motion expressions and the FFmpeg living clip command."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import pytest

from history_shorts.config import LivingSpec
from history_shorts.ffmpeg import FfmpegInfo, living_clip_cmd
from history_shorts.living.motion import camera, eased, plane_groups, shake_expr
from history_shorts.living.types import LivingClip, PlaneFile

SPEC = LivingSpec()
INFO = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))


def _eval(expr: str, on: float) -> float:
    py = expr.replace("PI", "math.pi").replace("on", f"({on})")
    env = {"math": math, "cos": math.cos, "sin": math.sin, "exp": math.exp, "min": min}
    env["between"] = lambda v, a, b: 1.0 if a <= v <= b else 0.0
    return float(eval(py, env))  # noqa: S307 - test-only evaluation of our own expressions


@pytest.mark.parametrize(
    ("motion", "expected"),
    [
        ("pan_left", (-90.0, 0.0, 0.0)),
        ("pan_right", (90.0, 0.0, 0.0)),
        ("pan_up", (0.0, -90.0, 0.0)),
        ("pan_down", (0.0, 90.0, 0.0)),
        ("zoom_in", (0.0, 0.0, 0.06)),
        ("zoom_out", (0.0, 0.0, -0.06)),
        ("none", (13.5, 0.0, 0.0)),
    ],
)
def test_camera_near(motion: str, expected: tuple[float, float, float]) -> None:
    assert camera(motion, "near", SPEC) == pytest.approx(expected)


def test_camera_scales_with_depth() -> None:
    assert camera("pan_right", "far", SPEC)[0] == 30.0
    assert camera("zoom_in", "mid", SPEC)[2] == pytest.approx(0.06 * 0.7)


def test_eased_endpoints() -> None:
    expr = eased(120)
    assert _eval(expr, 0) == pytest.approx(0.0)
    assert _eval(expr, 60) == pytest.approx(0.5)
    assert _eval(expr, 120) == pytest.approx(1.0)
    assert _eval(expr, 200) == pytest.approx(1.0)  # clips that run on hold the end


def test_shake_zero_without_hits() -> None:
    assert shake_expr((), SPEC, 30, "x") == "0"


def test_shake_decays_and_stays_small() -> None:
    expr = shake_expr((1.0,), SPEC, 30, "x")
    values = [_eval(expr, n) for n in range(0, 90)]
    assert max(abs(v) for v in values) <= SPEC.shake_px
    assert all(v == 0 for v in values[:29])
    assert abs(_eval(expr, 30 * (1.0 + SPEC.shake_seconds) + 1)) == 0
    assert max(abs(v) for v in values[30:36]) > 1


def _plane(kind: str, depth: str, velocity: tuple[float, float] = (0.0, 0.0)) -> PlaneFile:
    return PlaneFile(
        kind,
        depth,
        Path(f"/t/{kind}_{depth}.png"),
        60 if kind == "sprite" else 1,
        (10, 20),
        velocity,
        (54, 96),
        (100, 100),
    )  # type: ignore[arg-type]


def test_plane_groups() -> None:
    planes = [
        _plane("static", "far"),
        _plane("sprite", "far"),
        _plane("drift", "far", (6.0, 0.0)),
        _plane("static", "mid"),
        _plane("sprite", "mid"),
        _plane("static", "near"),
    ]
    assert plane_groups(planes) == [[0, 1], [2], [3, 4], [5]]


def _clip(text: bool) -> LivingClip:
    planes = (_plane("static", "far"), _plane("sprite", "mid"), _plane("static", "near"))
    t = Path("/t")
    return LivingClip(
        planes, t / "w.png", t / "s.png", t / "c.png", t / "x.png" if text else None, (1.0,)
    )


def test_living_cmd_structure() -> None:
    cmd = living_clip_cmd(
        INFO, _clip(False), Path("/o.mp4"), 4.0, 30, 20, 0.3, 0.3, "pan_right", SPEC
    )
    assert all(isinstance(arg, str) for arg in cmd)
    assert cmd.count("-i") == 3 + 3
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.count("zoompan=") == 3
    assert "blend=all_mode=addition" in graph
    assert graph.endswith("format=yuv420p[v]")
    assert "/t/sprite_mid.png" not in cmd and "/t/%03d.png" in cmd
    assert re.search(r"between\(on/30,1,", graph)


def test_living_cmd_text_fades_in() -> None:
    from history_shorts.ffmpeg import TextLayer

    layer = TextLayer(Path("/t/x.png"), 0.3, 0.5)
    cmd = living_clip_cmd(
        INFO, _clip(True), Path("/o.mp4"), 4.0, 30, 20, 0.0, 0.0, "none", SPEC, text=layer
    )
    assert cmd.count("-i") == 3 + 4
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "fade=t=in:st=0.300:d=0.500:alpha=1" in graph


def test_living_clip_uses_extended_duration(theme: Any, tmp_path: Path) -> None:  # RF-1
    from history_shorts.video import RenderOptions, _clip_cmds

    pngs = [tmp_path / "01.png", tmp_path / "02.png"]
    opts = RenderOptions(
        out=tmp_path / "o.mp4",
        music=None,
        transitions=("cut", "slideleft"),
        living=(_clip(False), None),
        motions=("pan_right", "none"),
    )
    cmds = _clip_cmds(INFO, pngs, [3.0, 3.0], theme, opts, [tmp_path / "a.mp4", tmp_path / "b.mp4"])
    graph = cmds[0][cmds[0].index("-filter_complex") + 1]
    assert f"on/{round(3.5 * 30)}" in graph
    assert "-filter_complex" not in cmds[1]
