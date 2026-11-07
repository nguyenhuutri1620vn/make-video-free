"""Command-line interface. The only module allowed to print."""

from __future__ import annotations

import argparse
import sys

from history_shorts import __version__
from history_shorts.errors import HistoryShortsError

COMMANDS = ("render", "validate", "gallery")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="history-shorts",
        description="Render Vietnamese-history lacquer-style vertical videos offline.",
    )
    parser.add_argument("--version", action="version", version=f"history-shorts {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="{render,validate,gallery}")
    for name in COMMANDS:
        sub.add_parser(name, help=f"{name} (not implemented yet)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        # Sub-commands are stubs until later milestones fill them in.
        print(f"history-shorts {args.command}: not implemented yet", file=sys.stderr)
        return 1
    except HistoryShortsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
