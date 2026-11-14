"""Build ``audio_manifest.json`` from recorded voice files (v2.1, spec A.1.8).

The sound project only has to save ``<id>.wav`` (or ``<id>.flac``) for every ``<id>.txt``
that ``export-narration`` wrote. This module pairs each voice with its narration segment and
copies the segment's ``text_sha256`` unchanged (A.1.4). It reads and writes files only; it
never records, synthesises or starts anything (C-01, C-02).

A voice file older than its ``.txt`` was recorded from an earlier text, so it is reported as
stale instead of being paired; ``export_narration`` keeps the mtime of unchanged files, which
makes this check reliable across re-exports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from history_shorts.audio import (
    AUDIO_KIND,
    MANIFEST_SCHEMA,
    NARRATION_KIND,
    NARRATION_MANIFEST,
)
from history_shorts.errors import Issues
from history_shorts.validation import Ctx, read_json_object

AUDIO_MANIFEST: Final = "audio_manifest.json"
VOICE_EXTENSIONS: Final = (".wav", ".flac")


@dataclass(frozen=True, slots=True)
class NarrationSegment:
    id: str
    file: str
    text_sha256: str


def read_narration_manifest(path: Path, issues: Issues) -> list[NarrationSegment] | None:
    """The segments of an ``export-narration`` manifest; None (with issues) when unusable."""
    data = read_json_object(path, issues)
    if data is None:
        return None
    ctx = Ctx(path.name, issues)
    errors = len(issues.errors)
    if ctx.str_(data, "kind") not in ("", NARRATION_KIND):
        ctx.at("kind").error(f'must be "{NARRATION_KIND}"')
    version = ctx.str_(data, "schema_version")
    if version and version.split(".")[0] != MANIFEST_SCHEMA.split(".")[0]:
        ctx.at("schema_version").error(f'unsupported schema_version "{version}"')
    segments: list[NarrationSegment] = []
    for child, raw in ctx.at("segments").items(data.get("segments", [])):
        obj = child.mapping(raw)
        sid, file = child.str_(obj, "id"), child.str_(obj, "file")
        digest = child.str_(obj, "text_sha256")
        if sid and file and digest:
            segments.append(NarrationSegment(sid, file, digest))
    return None if len(issues.errors) > errors else segments


def find_voice(voices: Path, segment_id: str) -> list[Path]:
    """Every ``<id>.<ext>`` voice file for the segment, in ``VOICE_EXTENSIONS`` order."""
    return [p for ext in VOICE_EXTENSIONS if (p := voices / f"{segment_id}{ext}").is_file()]


def _text_matches(narration: Path, segment: NarrationSegment) -> bool:
    txt = narration / segment.file
    return txt.is_file() and hashlib.sha256(txt.read_bytes()).hexdigest() == segment.text_sha256


def _old_gains(path: Path) -> dict[tuple[str, str], float]:
    """``gain_db`` of the previous manifest by (id, text_sha256), so manual fixes survive."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return {
            (s["id"], s["text_sha256"]): float(s["gain_db"])
            for s in data.get("segments", [])
            if isinstance(s, dict) and "gain_db" in s
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def _pair(
    narration: Path, voices: Path, segments: list[NarrationSegment], issues: Issues
) -> list[tuple[NarrationSegment, Path]]:
    name = NARRATION_MANIFEST
    pairs: list[tuple[NarrationSegment, Path]] = []
    edited: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    for segment in segments:
        if not _text_matches(narration, segment):
            edited.append(segment.id)
            continue
        found = find_voice(voices, segment.id)
        if not found:
            missing.append(segment.id)
        elif len(found) > 1:
            issues.error(name, segment.id, f"both {found[0].name} and {found[1].name}; keep one")
        elif found[0].stat().st_mtime < (narration / segment.file).stat().st_mtime:
            stale.append(segment.id)
        else:
            pairs.append((segment, found[0]))
    problems = (
        (edited, "text differs from manifest; run export-narration: "),
        (missing, f"no voice file ({'/'.join(VOICE_EXTENSIONS)}) in {voices} for: "),
        (stale, "voice is older than its narration text; re-record: "),
    )
    for ids, message in problems:
        if ids:
            issues.error(name, "segments", message + ", ".join(ids))
    return pairs


def build(narration: Path, voices: Path, issues: Issues) -> Path | None:
    """Write ``voices/audio_manifest.json`` for the export in ``narration``.

    Returns the manifest path, or None (nothing written) when any segment has no fresh voice.
    """
    segments = read_narration_manifest(narration / NARRATION_MANIFEST, issues)
    if segments is None:
        return None
    pairs = _pair(narration, voices, segments, issues)
    if issues.errors:
        return None
    out = voices / AUDIO_MANIFEST
    gains = _old_gains(out)
    entries: list[dict[str, Any]] = []
    for segment, path in pairs:
        entry: dict[str, Any] = {
            "id": segment.id,
            "file": path.relative_to(voices).as_posix(),
            "text_sha256": segment.text_sha256,
        }
        gain = gains.get((segment.id, segment.text_sha256))
        if gain is not None:
            entry["gain_db"] = gain
        entries.append(entry)
    data = {"kind": AUDIO_KIND, "schema_version": MANIFEST_SCHEMA, "segments": entries}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
