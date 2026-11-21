"""M11: the SVG path-string parser of artwork files."""

from __future__ import annotations

import math

import pytest

from history_shorts.artwork.path import PathError, count_numbers, parse_path, path_bounds


def _bez(p0: tuple[float, float], op: tuple[float, ...], t: float) -> tuple[float, float]:
    x1, y1, x2, y2, x3, y3 = op
    u = 1 - t
    x = u**3 * p0[0] + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3
    y = u**3 * p0[1] + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3
    return x, y


def test_lines_absolute_and_relative() -> None:
    assert parse_path("M 0 0 h 10 v 5 H 0 Z") == (
        ("M", (0.0, 0.0)),
        ("L", (10.0, 0.0)),
        ("L", (10.0, 5.0)),
        ("L", (0.0, 5.0)),
        ("Z", ()),
    )
    assert parse_path("m 1 1 l 2 0 L 5 5 V 0") == (
        ("M", (1.0, 1.0)),
        ("L", (3.0, 1.0)),
        ("L", (5.0, 5.0)),
        ("L", (5.0, 0.0)),
    )


def test_implicit_lineto_after_moveto() -> None:
    assert parse_path("M 0 0 10 0 10 10") == (
        ("M", (0.0, 0.0)),
        ("L", (10.0, 0.0)),
        ("L", (10.0, 10.0)),
    )
    assert parse_path("m 0 0 10 0")[1] == ("L", (10.0, 0.0))


def test_cubic_and_smooth() -> None:
    ops = parse_path("M 0 0 C 0 10 10 10 10 0 S 20 -10 20 0")
    assert ops[1] == ("C", (0.0, 10.0, 10.0, 10.0, 10.0, 0.0))
    assert ops[2] == ("C", (10.0, -10.0, 20.0, -10.0, 20.0, 0.0))  # reflected first control
    rel = parse_path("M 0 0 c 0 10 10 10 10 0 s 10 -10 10 0")
    assert rel == ops


def test_quadratic_to_cubic() -> None:
    ops = parse_path("M 0 0 Q 3 6 6 0 T 12 0")
    assert ops[1][0] == "C"
    assert ops[1][1] == pytest.approx((2.0, 4.0, 4.0, 4.0, 6.0, 0.0))
    kind, c = ops[2]
    assert kind == "C" and c[4:] == (12.0, 0.0)
    assert c[0] == pytest.approx(8.0) and c[1] == pytest.approx(-4.0)  # reflected control (9,-6)


def test_arc_quarter_circle() -> None:
    ops = parse_path("M 10 0 A 10 10 0 0 1 0 10")
    assert ops[-1][1][-2:] == pytest.approx((0.0, 10.0))
    start = (10.0, 0.0)
    for _, op in ops[1:]:
        for k in range(9):
            x, y = _bez(start, op, k / 8)
            assert math.hypot(x, y) == pytest.approx(10.0, abs=0.05)
        start = (op[4], op[5])


def test_arc_large_and_relative() -> None:
    ops = parse_path("M 0 0 a 5 5 0 1 0 10 0")
    assert ops[-1][1][-2:] == pytest.approx((10.0, 0.0))
    assert len(ops) >= 3  # more than 90 degrees is split


def test_number_forms() -> None:
    assert parse_path("M1e1-.5L3-4")[0] == ("M", (10.0, -0.5))
    assert parse_path("M1e1-.5L3-4")[1] == ("L", (3.0, -4.0))
    assert count_numbers("M 0 0 C 1 2 3 4 5 6") == 8


@pytest.mark.parametrize(
    ("d", "position"),
    [("M 0 0 X 1", 6), ("L 0 0", 0), ("M 0 0 L 1", 6), ("M 0", 0), ("M 0 0 A 1 1 0 2 0 3 3", 6)],
)
def test_errors_report_position(d: str, position: int) -> None:
    with pytest.raises(PathError) as exc:
        parse_path(d)
    assert exc.value.position == position


def test_bounds_include_controls() -> None:
    assert path_bounds(parse_path("M 0 0 C 0 -10 10 -10 10 0")) == (0.0, -10.0, 10.0, 0.0)
