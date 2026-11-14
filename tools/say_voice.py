"""Draft voice for one narration file with the macOS ``say`` voice "Linh" (vi_VN).

A stand-in for the owner's sound project while VoiceStudio is not available. It reads one
``<id>.txt`` written by ``export-narration``, turns each ``[pause Nms]`` marker into the
``say`` silence command ``[[slnc N]]`` (otherwise ``say`` would read the marker aloud) and
writes a 16-bit mono WAV. Use it as the ``--voice-cmd`` of ``tools/make_video.py``:

    python tools/make_video.py --script examples/hai_ba_trung/script.json \\
        --voice-cmd "python tools/say_voice.py {text} {wav}"

This file lives outside ``history_shorts/`` on purpose: history-shorts itself never runs a
speech synthesiser (C-01, spec A.1.1). ``say`` runs offline and is part of macOS.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_VOICE = "Linh"
SAMPLE_RATE = 24000
DEFAULT_RATE = 200  # words per minute; the default Linh pace makes long slides exceed 14 s
_PAUSE_RE = re.compile(r"\[pause (\d+)ms\]")


def to_say_text(narration: str) -> str:
    """Narration text with ``[pause Nms]`` rewritten as ``say``'s ``[[slnc N]]``."""
    return _PAUSE_RE.sub(lambda m: f" [[slnc {m.group(1)}]] ", narration).strip()


def say_command(say: str, wav: Path, voice: str, rate: int | None) -> list[str]:
    """The ``say`` argument list; the text is passed on stdin (``-f -``)."""
    cmd = [say, "-v", voice, "-f", "-", "-o", str(wav)]
    cmd += ["--file-format=WAVE", f"--data-format=LEI16@{SAMPLE_RATE}"]
    if rate is not None:
        cmd += ["-r", str(rate)]
    return cmd


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("text", type=Path, help="narration .txt from export-narration")
    parser.add_argument("wav", type=Path, help="voice file to write")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="say voice name")
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE, help="words per minute")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    say = shutil.which("say")
    if say is None:
        print("ERROR the macOS 'say' command was not found", file=sys.stderr)
        return 4
    text = to_say_text(args.text.read_text(encoding="utf-8"))
    partial = args.wav.with_name(args.wav.stem + ".partial.wav")
    result = subprocess.run(
        say_command(say, partial, args.voice, args.rate),
        input=text.encode("utf-8"),
        check=False,
    )
    if result.returncode != 0 or not partial.exists():
        partial.unlink(missing_ok=True)
        print(f"ERROR say failed for {args.text.name} (exit {result.returncode})", file=sys.stderr)
        return result.returncode or 1
    partial.replace(args.wav)
    return 0


if __name__ == "__main__":
    sys.exit(main())
