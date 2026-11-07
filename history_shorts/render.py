"""Render every slide of a script to a PNG (FR-02, FR-90)."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

from PIL import Image

from history_shorts.compose import (
    SceneDrawer,
    SceneStyle,
    SlideContext,
    default_style,
    render_slide,
)
from history_shorts.config import Script, Slide, Theme
from history_shorts.output import slide_path, slides_dir

log = logging.getLogger(__name__)

PNG_COMPRESS_LEVEL: Final = 6  # fixed, so equal pixels give equal bytes (NFR-02)

Expand = Callable[[Slide, Theme], tuple[SceneStyle, SceneDrawer | None]]


def write_png(image: Image.Image, path: Path) -> None:
    """Write ``image`` to ``path`` atomically: a sibling ``.tmp`` file, then ``os.replace``."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        image.save(tmp, format="PNG", compress_level=PNG_COMPRESS_LEVEL)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def render_slides(
    script: Script,
    theme: Theme,
    out: Path,
    *,
    debug_safe_zone: bool,
    expand: Expand | None = None,
) -> list[Path]:
    """Write ``<out dir>/slides/NN.png`` (1-based) for every slide and return the paths.

    ``expand`` maps a slide to its scene style and drawing callback; without it every slide
    is chrome and text on the plain lacquer ground. Stale ``NN.png`` files beyond the slide
    count are left alone (the CLI reports them).
    """
    directory = slides_dir(out)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, slide in enumerate(script.slides):
        started = time.perf_counter()
        style, draw_scene = expand(slide, theme) if expand else (default_style(theme), None)
        ctx = SlideContext(script, theme, index, style, draw_scene, debug_safe_zone)
        target = slide_path(directory, index + 1)
        write_png(render_slide(ctx), target)
        written.append(target)
        log.debug(
            "slide %d rendered in %.2f s: %s", index + 1, time.perf_counter() - started, target
        )
    return written
