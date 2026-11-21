"""SVG path strings (the ``d`` attribute syntax) for artwork files (M11).

``parse_path`` turns a string into absolute operations of four kinds only: ``M`` (x, y),
``L`` (x, y), ``C`` (x1, y1, x2, y2, x, y) and ``Z``. ``H``/``V`` become lines, ``S``/``Q``/``T``
become cubics and arcs become cubics of at most 90 degrees each. A mistake raises
``PathError`` with the character position of the command it belongs to.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Final

from history_shorts.canvas import Canvas

Op = tuple[str, tuple[float, ...]]

_TOKEN: Final = re.compile(
    r"\s*,?\s*(?:([MmLlHhVvCcSsQqTtAaZz])|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?))"
)
_ARITY: Final = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


class PathError(ValueError):
    """A path string mistake at character ``position``."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} at {position}")
        self.position = position
        self.message = message


def _tokens(d: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    pos = 0
    while pos < len(d):
        if d[pos:].strip(" \t\r\n,") == "":
            break
        match = _TOKEN.match(d, pos)
        if match is None or match.end() == pos:
            start = pos + len(d[pos:]) - len(d[pos:].lstrip(" \t\r\n,"))
            raise PathError(f"bad command '{d[start]}'", start)
        token = match.group(1) or match.group(2)
        out.append((token, match.start(1) if match.group(1) else match.start(2)))
        pos = match.end()
    return out


def count_numbers(d: str) -> int:
    """How many numbers a path string holds (for the per-file limit)."""
    return sum(1 for token, _ in _tokens(d) if not token.isalpha())


def _groups(d: str) -> list[tuple[str, int, list[float]]]:
    """(command, position, numbers) with each repeated argument group split out."""
    groups: list[tuple[str, int, list[float]]] = []
    tokens = _tokens(d)
    k = 0
    while k < len(tokens):
        cmd, pos = tokens[k]
        if not cmd.isalpha():
            raise PathError(f"bad command '{cmd}'", pos)
        k += 1
        numbers: list[float] = []
        while k < len(tokens) and not tokens[k][0].isalpha():
            numbers.append(float(tokens[k][0]))
            k += 1
        arity = _ARITY[cmd.upper()]
        if arity == 0:
            if numbers:
                raise PathError(f"'{cmd}' takes no numbers", pos)
            groups.append((cmd, pos, []))
            continue
        if not numbers or len(numbers) % arity:
            raise PathError(f"'{cmd}' needs groups of {arity} numbers", pos)
        for i in range(0, len(numbers), arity):
            name = cmd
            if i and cmd in "Mm":
                name = "L" if cmd == "M" else "l"  # extra pairs after a moveto are linetos
            groups.append((name, pos, numbers[i : i + arity]))
    return groups


def _arc(
    p0: tuple[float, float], args: list[float], pos: int
) -> list[tuple[float, float, float, float, float, float]]:
    """SVG endpoint arc as cubics of at most 90 degrees (SVG 1.1 F.6.5)."""
    rx, ry, angle, large, sweep, x, y = args
    if large not in (0.0, 1.0) or sweep not in (0.0, 1.0):
        raise PathError("arc flags must be 0 or 1", pos)
    x0, y0 = p0
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or (x0, y0) == (x, y):
        return [(x0, y0, x, y, x, y)]
    phi = math.radians(angle)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (x0 - x) / 2, (y0 - y) / 2
    x1p, y1p = cos_p * dx + sin_p * dy, -sin_p * dx + cos_p * dy
    scale = (x1p / rx) ** 2 + (y1p / ry) ** 2
    if scale > 1:
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(num / den, 0.0)) * (-1 if large == sweep else 1)
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x0 + x) / 2
    cy = sin_p * cxp + cos_p * cyp + (y0 + y) / 2

    def ang(ux: float, uy: float, vx: float, vy: float) -> float:
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    pieces = max(1, math.ceil(abs(dt) / (math.pi / 2) - 1e-9))
    step = dt / pieces
    k = 4 / 3 * math.tan(step / 4)

    def point(t: float) -> tuple[float, float]:
        ex, ey = rx * math.cos(t), ry * math.sin(t)
        return cos_p * ex - sin_p * ey + cx, sin_p * ex + cos_p * ey + cy

    def deriv(t: float) -> tuple[float, float]:
        ex, ey = -rx * math.sin(t), ry * math.cos(t)
        return cos_p * ex - sin_p * ey, sin_p * ex + cos_p * ey

    out = []
    for i in range(pieces):
        a, b = t1 + i * step, t1 + (i + 1) * step
        (ax, ay), (bx, by) = point(a), point(b)
        (dax, day), (dbx, dby) = deriv(a), deriv(b)
        end = (x, y) if i == pieces - 1 else (bx, by)
        out.append((ax + k * dax, ay + k * day, bx - k * dbx, by - k * dby, *end))
    return out


def parse_path(d: str) -> tuple[Op, ...]:
    """Absolute M/L/C/Z operations of an SVG path string."""
    ops: list[Op] = []
    cur = start = (0.0, 0.0)
    last_c: tuple[float, float] | None = None  # previous cubic's second control
    last_q: tuple[float, float] | None = None  # previous quadratic control
    for index, (cmd, pos, n) in enumerate(_groups(d)):
        if index == 0 and cmd not in "Mm":
            raise PathError("a path must start with M", pos)
        rel = cmd.islower()
        up = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        c_ctrl, q_ctrl = None, None
        if up == "M":
            cur = start = (n[0] + ox, n[1] + oy)
            ops.append(("M", cur))
        elif up == "L":
            cur = (n[0] + ox, n[1] + oy)
            ops.append(("L", cur))
        elif up == "H":
            cur = (n[0] + ox, cur[1])
            ops.append(("L", cur))
        elif up == "V":
            cur = (cur[0], n[0] + (cur[1] if rel else 0.0))
            ops.append(("L", cur))
        elif up in "CS":
            if up == "C":
                c1 = (n[0] + ox, n[1] + oy)
                rest = n[2:]
            else:
                c1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
                rest = n
            c2 = (rest[0] + ox, rest[1] + oy)
            end = (rest[2] + ox, rest[3] + oy)
            ops.append(("C", (*c1, *c2, *end)))
            cur, c_ctrl = end, c2
        elif up in "QT":
            if up == "Q":
                q = (n[0] + ox, n[1] + oy)
                end = (n[2] + ox, n[3] + oy)
            else:
                q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
                end = (n[0] + ox, n[1] + oy)
            c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
            c2 = (end[0] + 2 / 3 * (q[0] - end[0]), end[1] + 2 / 3 * (q[1] - end[1]))
            ops.append(("C", (*c1, *c2, *end)))
            cur, q_ctrl = end, q
        elif up == "A":
            args = [*n[:5], n[5] + ox, n[6] + oy]
            for piece in _arc(cur, args, pos):
                ops.append(("C", piece))
            cur = (args[5], args[6])
        else:  # Z
            ops.append(("Z", ()))
            cur = start
        last_c, last_q = c_ctrl, q_ctrl
    return tuple(ops)


def path_bounds(ops: Iterable[Op]) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) of every point and control point."""
    xs: list[float] = []
    ys: list[float] = []
    for _, values in ops:
        xs += values[0::2]
        ys += values[1::2]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def trace(cv: Canvas, ops: Iterable[Op]) -> None:
    """Add ``ops`` to the canvas's current path."""
    for kind, v in ops:
        if kind == "M":
            cv.M(v[0], v[1])
        elif kind == "L":
            cv.L(v[0], v[1])
        elif kind == "C":
            cv.C(v[0], v[1], v[2], v[3], v[4], v[5])
        else:
            cv.Z()
