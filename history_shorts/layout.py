"""Canvas, safe zone, regions and text anchors (spec §8.2 regions, §8.4 typography)."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from history_shorts.primitives import Box

CANVAS_W: Final = 1080
CANVAS_H: Final = 1920

SAFE_ZONE: Final = Box(80, 160, 930, 1500)

TEXT_CENTER_X: Final = 505
TEXT_MAX_WIDTH: Final = 850

REGIONS: Final[Mapping[str, Box]] = MappingProxyType(
    {
        "header": Box(0, 160, 1080, 290),
        "visual": Box(0, 290, 1080, 1150),
        "title": Box(0, 1170, 1080, 1400),
        "subtitle": Box(0, 1400, 1080, 1500),
        "chrome": Box(0, 1540, 1080, 1920),
    }
)

TITLE_TOP_ONE_LINE: Final = 1215
TITLE_TOP_TWO_LINES: Final = 1190
TITLE_STEP_RATIO: Final = 102 / 92

SUBTITLE_GAP: Final = 128
SUBTITLE_STEP_RATIO: Final = 56 / 46
