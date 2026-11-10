"""Entry point for ``python -m history_shorts``."""

from __future__ import annotations

import sys

from history_shorts.cli import main

if __name__ == "__main__":
    sys.exit(main())
