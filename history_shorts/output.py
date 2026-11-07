"""Output paths: slugs, default video path and the slide PNG directory (spec §7, FR-90)."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Final

from history_shorts.config import Script

DEFAULT_OUT_DIR: Final = "output"
SLIDES_DIRNAME: Final = "slides"
FALLBACK_SLUG: Final = "video"
_NON_ALNUM: Final = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """ASCII slug: no diacritics, ``đ`` to ``d``, lowercase, other character runs to ``-``."""
    decomposed = unicodedata.normalize("NFD", title)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    ascii_like = stripped.replace("đ", "d").replace("Đ", "D").lower()
    return _NON_ALNUM.sub("-", ascii_like).strip("-") or FALLBACK_SLUG


def default_out_path(script: Script) -> Path:
    """``output/<slug(title)>.mp4``, relative to the current directory."""
    return Path(DEFAULT_OUT_DIR) / f"{slugify(script.title)}.mp4"


def slides_dir(out: Path) -> Path:
    """Where the slide PNGs go: next to the video, in ``slides/``."""
    return out.parent / SLIDES_DIRNAME


def slide_path(directory: Path, number: int) -> Path:
    """PNG path for the 1-based slide ``number``."""
    return directory / f"{number:02d}.png"


def stale_slides(directory: Path, slide_count: int) -> list[Path]:
    """Existing ``NN.png`` files numbered beyond ``slide_count``, sorted by name."""
    if not directory.is_dir():
        return []
    found = (p for p in directory.iterdir() if re.fullmatch(r"\d{2,}\.png", p.name))
    return sorted((p for p in found if int(p.stem) > slide_count), key=lambda p: p.name)
