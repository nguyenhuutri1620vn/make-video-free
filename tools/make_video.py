"""One command from script.json to a finished video with voice and music.

Runs the history-shorts steps in order and stops at the first failure:

1. ``validate`` the script and theme;
2. ``export-narration`` into the work folder (skipped when no slide narrates);
3. record every missing or stale voice with ``--voice-cmd`` (the owner's sound project), or,
   without it, list the files to record and stop so the owner can record them and run again;
4. ``audio-manifest`` to pair the voices;
5. ``render --audio`` (plus ``--music``) to the video.

This file lives outside ``history_shorts/`` on purpose: history-shorts itself never starts the
sound project (spec A.1.1). ``--voice-cmd`` is a command template the owner supplies; it is
split like a shell line but run without a shell, with ``{text}``, ``{wav}`` and ``{id}``
replaced in each argument. Example:

    python tools/make_video.py --script examples/hai_ba_trung/script.json \\
        --music music/trong_dong.mp3 \\
        --voice-cmd "voicestudio-cli --input {text} --output {wav}"
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Run as ``python tools/make_video.py`` from a checkout: make the package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from history_shorts.errors import Issues  # noqa: E402
from history_shorts.voice_manifest import (  # noqa: E402
    AUDIO_MANIFEST,
    find_voice,
    read_narration_manifest,
)

EXIT_VALIDATION = 3
NARRATION_MANIFEST = "manifest.json"


@dataclass(frozen=True)
class VoiceJob:
    """One voice that has to be (re)recorded: read ``text``, write ``wav``."""

    id: str
    text: Path
    wav: Path


def has_narration(script: Path) -> bool:
    data = json.loads(script.read_text(encoding="utf-8-sig"))
    return any(isinstance(s, dict) and s.get("narration") for s in data.get("slides", []))


def default_work_dir(script: Path) -> Path:
    return Path("output") / "voice" / script.resolve().parent.name


def pending_voices(work: Path) -> list[VoiceJob]:
    """Segments whose voice file is missing or older than its ``.txt``."""
    issues = Issues()
    segments = read_narration_manifest(work / NARRATION_MANIFEST, issues)
    if segments is None:
        raise SystemExit(f"cannot read {work / NARRATION_MANIFEST}: {issues.items}")
    jobs: list[VoiceJob] = []
    for segment in segments:
        text = work / segment.file
        found = find_voice(work, segment.id)
        if not found or found[0].stat().st_mtime < text.stat().st_mtime:
            target = found[0] if found else work / f"{segment.id}.wav"
            jobs.append(VoiceJob(segment.id, text, target))
    return jobs


def voice_command(template: str, job: VoiceJob) -> list[str]:
    """The owner's command for one voice, as an argument list (never a shell string)."""
    values = {"text": str(job.text), "wav": str(job.wav), "id": job.id}
    return [part.format(**values) for part in shlex.split(template)]


def _run(cmd: list[str]) -> int:
    print("$ " + shlex.join(cmd), flush=True)
    return subprocess.run(cmd, check=False).returncode


def _hs(*args: str) -> list[str]:
    return [sys.executable, "-m", "history_shorts", *args]


def _record(work: Path, template: str | None) -> int:
    jobs = pending_voices(work)
    if not jobs:
        return 0
    if template is None:
        print(f"Record these voices into {work}, then run this command again:")
        for job in jobs:
            print(f"  {job.text.name} -> {job.wav.name}")
        return EXIT_VALIDATION
    for job in jobs:
        code = _run(voice_command(template, job))
        if code != 0:
            print(f"ERROR voice command failed for {job.id} (exit {code})")
            return code
    return 0


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--theme", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="video path")
    parser.add_argument("--music", type=Path, default=None)
    parser.add_argument("--music-volume", default=None)
    parser.add_argument("--sfx-volume", default=None)
    parser.add_argument("--voice-cmd", default=None, help="template with {text} {wav} {id}")
    parser.add_argument("--work", type=Path, default=None, help="narration and voice folder")
    return parser.parse_args(argv)


def _render_args(args: argparse.Namespace, audio: Path | None) -> list[str]:
    cmd = ["render", "--script", str(args.script)]
    for flag, value in (
        ("--theme", args.theme),
        ("--out", args.out),
        ("--music", args.music),
        ("--music-volume", args.music_volume),
        ("--sfx-volume", args.sfx_volume),
        ("--audio", audio),
    ):
        if value is not None:
            cmd += [flag, str(value)]
    return cmd


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    theme = ["--theme", str(args.theme)] if args.theme is not None else []
    code = _run(_hs("validate", "--script", str(args.script), *theme))
    if code != 0:
        return code
    if not has_narration(args.script):
        return _run(_hs(*_render_args(args, None)))
    work: Path = args.work or default_work_dir(args.script)
    code = _run(_hs("export-narration", "--script", str(args.script), "--out", str(work)))
    if code == 0:
        code = _record(work, args.voice_cmd)
    if code == 0:
        code = _run(_hs("audio-manifest", "--narration", str(work)))
    if code == 0:
        code = _run(_hs(*_render_args(args, work / AUDIO_MANIFEST)))
    return code


if __name__ == "__main__":
    sys.exit(main())
