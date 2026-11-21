"""Publish a finished video into the one shared ``final/`` folder.

``output/`` (in the main checkout and in every worktree) is scratch: drafts, retries,
checkpoints. When the owner approves a video, publish it:

    python /Users/<you>/Documents/Code/make-video-free/tools/publish_final.py \\
        --video output/co_loa.mp4 --script examples/co_loa/script.json

This copies the video, its ``.report.json`` and the ``script.json`` into
``<main checkout>/final/<name>/`` (``<name>`` defaults to the script's folder name, e.g.
``co_loa``) and writes ``final.json``. Publishing the same name again replaces the previous
final: there is only ever one final per video. Run it from any worktree: the destination is
always the main checkout's ``final/``. Clip Publisher shows only what is in ``final/``.

Standard library only, so any checkout can run it with any Python 3.10+.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
WORKTREE_MARKER = (".claude", "worktrees")


class PublishError(Exception):
    """A video cannot be published (missing file, bad name)."""


def final_dir_for(tool_path: Path) -> Path:
    """``final/`` of the main checkout, also when this file runs from a worktree copy."""
    path = tool_path.resolve() if tool_path.exists() else tool_path
    parts = path.parts
    for i in range(len(parts) - 1):
        if (parts[i], parts[i + 1]) == WORKTREE_MARKER:
            return Path(*parts[:i]) / "final"
    return Path(*parts[:-2]) / "final"


def _report_for(video: Path) -> Path:
    return video.with_name(video.stem + ".report.json")


def publish(video: Path, script: Path, name: str | None, final_dir: Path) -> Path:
    """Copy video + report + script into ``final_dir/<name>/``, replacing any previous final."""
    name = name or script.parent.name
    if not NAME_RE.match(name):
        raise PublishError(
            f"bad name {name!r}: use lowercase letters, digits, '-' or '_' (pass --name)"
        )
    report = _report_for(video)
    for label, path in (("video", video), ("report", report), ("script", script)):
        if not path.is_file():
            raise PublishError(f"{label} not found: {path}")
    try:
        title = json.loads(script.read_text(encoding="utf-8-sig")).get("title", name)
    except (OSError, ValueError) as exc:
        raise PublishError(f"script is not valid JSON: {script}: {exc}") from exc

    final_dir.mkdir(parents=True, exist_ok=True)
    dest = final_dir / name
    staging = Path(tempfile.mkdtemp(prefix=f".{name}.publishing-", dir=final_dir))
    try:
        shutil.copy2(video, staging / f"{name}.mp4")
        shutil.copy2(report, staging / f"{name}.report.json")
        shutil.copy2(script, staging / "script.json")
        manifest = {
            "name": name,
            "title": title,
            "video": f"{name}.mp4",
            "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_video": str(video.resolve()),
            "source_script": str(script.resolve()),
        }
        text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        (staging / "final.json").write_text(text, encoding="utf-8")
        backup = final_dir / f".{name}.previous"
        if dest.exists():
            if backup.exists():
                shutil.rmtree(backup)
            dest.rename(backup)
        staging.rename(dest)
        if backup.exists():
            shutil.rmtree(backup)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--video", type=Path, required=True, help="the .mp4 (its .report.json sits next to it)"
    )
    parser.add_argument("--script", type=Path, required=True, help="the script.json it used")
    parser.add_argument(
        "--name", default=None, help="folder name in final/ (default: the script's folder)"
    )
    parser.add_argument("--final-dir", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    final_dir = args.final_dir or final_dir_for(Path(__file__))
    try:
        dest = publish(args.video, args.script, args.name, final_dir)
    except PublishError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 3
    print(f"Published {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
