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
    DrawContext,
    EggshellCache,
    SceneDrawer,
    SceneStyle,
    SlideContext,
    default_style,
    render_layers,
    render_slide,
)
from history_shorts.config import Script, Slide, Theme
from history_shorts.output import layer_paths, slide_path, slides_dir
from history_shorts.primitives import FloatImage
from history_shorts.scene import draw_layers
from history_shorts.scene.templates import expand as expand_scene

log = logging.getLogger(__name__)

PNG_COMPRESS_LEVEL: Final = 6  # fixed, so equal pixels give equal bytes (NFR-02)

Expand = Callable[[Slide, Theme], tuple[SceneStyle, SceneDrawer | None]]


def scene_expander(slide: Slide, theme: Theme) -> tuple[SceneStyle, SceneDrawer | None]:
    """The ``Expand`` used by ``render``: a slide's scene (template or layers) becomes its style
    and a drawing callback; a slide without a scene stays chrome and text on the plain ground."""
    if slide.scene is None:
        return default_style(theme), None
    expanded = expand_scene(slide.scene, theme)

    def draw_scene(img: FloatImage, ctx: DrawContext) -> FloatImage:
        return draw_layers(img, expanded.layers, ctx)

    return expanded.style, draw_scene


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
    eggshell_cache: bool = True,
) -> list[Path]:
    """Write ``<out dir>/slides/NN.png`` (1-based) for every slide and return the paths.

    ``expand`` maps a slide to its scene style and drawing callback (``scene_expander`` is the
    one ``render`` uses); without it every slide is chrome and text on the plain lacquer
    ground. One eggshell cache serves the whole run (FR-66) unless ``eggshell_cache`` is false.
    Stale ``NN.png`` files beyond the slide count are left alone (the CLI reports
    them).
    """
    directory = slides_dir(out)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    cache = EggshellCache() if eggshell_cache else None
    for index, slide in enumerate(script.slides):
        started = time.perf_counter()
        style, draw_scene = expand(slide, theme) if expand else (default_style(theme), None)
        ctx = SlideContext(script, theme, index, style, draw_scene, debug_safe_zone, cache)
        target = slide_path(directory, index + 1)
        write_png(render_slide(ctx), target)
        if slide.text_in != "none":
            background, text = render_layers(ctx)
            bg_path, text_path = layer_paths(target)
            write_png(background, bg_path)
            write_png(text, text_path)
        written.append(target)
        log.debug(
            "slide %d rendered in %.2f s: %s", index + 1, time.perf_counter() - started, target
        )
    if cache is not None:
        log.debug("eggshell cache: %d hits, %d misses", cache.hits, cache.misses)
    return written
