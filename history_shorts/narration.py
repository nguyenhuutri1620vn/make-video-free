"""Narration text rules (v2.1, spec A.1.2): normalisation, pause markers and file bytes.

Pure string functions with no I/O, so the script loader, the exporter and the audio-manifest
check all hash and compare the same bytes. Narration is spoken Vietnamese text; the only
bracket tag allowed is ``[pause Nms]``.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Final

MAX_NARRATION_CHARS: Final = 600
MIN_PAUSE_MS: Final = 50
MAX_PAUSE_MS: Final = 3000

_PAUSE_RE: Final = re.compile(r"\[pause (\d+)ms\]")
_BRACKET_RE: Final = re.compile(r"\[[^\]\n]*\]?")


def normalise(text: str) -> str:
    """Unicode NFC, LF line endings, no trailing spaces per line, no leading or trailing blank
    lines (A.1.2). The result is what goes into the ``.txt`` file and into the hash."""
    value = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in value.split("\n")]
    return "\n".join(lines).strip("\n")


def file_bytes(text: str) -> bytes:
    """The exact bytes of a narration ``.txt``: UTF-8, no BOM, LF, one final LF."""
    return (normalise(text) + "\n").encode("utf-8")


def text_sha256(text: str) -> str:
    """SHA-256 of ``file_bytes(text)``; the sound project copies it unchanged (A.1.4)."""
    return hashlib.sha256(file_bytes(text)).hexdigest()


def pause_problems(text: str) -> list[str]:
    """Human-readable problems with the bracket tags in ``text``, empty when all are valid.

    Only ``[pause Nms]`` with N from 50 to 3000 is accepted; any other ``[...]`` is an error.
    """
    problems: list[str] = []
    for match in _BRACKET_RE.finditer(text):
        tag = match.group(0)
        pause = _PAUSE_RE.fullmatch(tag)
        if pause is None or not tag.endswith("]"):
            problems.append(f"unknown tag {tag!r}; only [pause Nms] is allowed")
        elif not MIN_PAUSE_MS <= int(pause.group(1)) <= MAX_PAUSE_MS:
            problems.append(f"pause {pause.group(1)}ms is outside {MIN_PAUSE_MS}–{MAX_PAUSE_MS} ms")
    return problems
