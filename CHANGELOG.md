# Changelog

## M1 — Foundation

Exit criteria met: AC-08 (Vietnamese glyph check) and AC-11 (`validate` reports every error and exits 3; missing sources only warn).

- Task 1: package scaffold, guard tests, `--version`, Liberation Serif fonts.
- Task 2: theme loading and validation (palette with optional fallbacks, fonts, type scale, textures, chrome).
- Task 3: script, scene, layer and character parsing with path-tracked, all-at-once errors.
- Task 4: layout regions and text anchors.
- Task 5: text wrapping, auto-shrink, Vietnamese glyph check and drawing.
- Task 6: typed pycairo canvas wrapper.
- Task 7: `validate` command with cross-file checks (theme font glyphs, glyphs used by the script, text fit and shrink warnings, palette keys in character overrides) and the runtime import check with per-OS install hints (exit 1).

## M2 — Textures & chrome

Slides now render end to end with chrome and text only (scenes arrive in M4). Covers AC-09 and AC-12 (partial: chrome and text, no scenes yet).

- Task 8: lacquer ground, gold leaf, eggshell and finish textures (deterministic, mask-contained).
- Task 9: compositing core and FR-21 slide assembly (`compose.py`).
- Task 10: frame, corner scrolls, waves, seal, tag pill, optional progress bar and footer.
- Task 11: `render --preview` writes `<out dir>/slides/NN.png` (1-based, atomic per file, never deletes stale files, which are reported as `WARN`). `render` validates first (exit 3 on errors) and accepts every spec §7 flag; `--music`, `--music-volume`, `--keep-temp` and `--jobs` are accepted and ignored with a `WARN`. Without `--preview` it renders the PNGs, then exits 1 with "video assembly is not implemented yet (milestone M5)". New modules: `output.py` (slug, default output path), `render.py`.

## M3 — Characters

Covers AC-06 (formations and figures never overlap seal, tag, text or another head) and AC-07 (every role x facing x prop x crest draws, with the hand on the shaft); FR-04 for characters.

- Task 12: role presets (`ROLES`) and style resolution; roles are data only.
- Task 13: figure parts in FR-41 drawing order, with the oar grip.
- Task 14: figure boxes, formations (`centre_pair`, `line`, `v_shape`) and FR-48 overlap checks.
- Task 15: `gallery [--theme PATH] [--out PATH]` writes a 1080x3000 contact sheet (default `output/gallery.png`): 4 props across, 8 role x facing rows down (roles in preset order, facing +1 then -1), on one lacquer ground, each cell labelled `role · facing · prop`. Figures use their role preset's crest. Layer-type rows were added in Task 20 (the sheet is now 1080x4080).
- Task 15b: costume kits (FR-45). The figure is drawn, boxed and masked through `KITS[style.kit]`; today's parts moved verbatim to the `ancient_female` kit (`characters/parts.py` re-exports it). Roles name their kit; `validate` rejects unknown kits and props a kit cannot draw. No visual change (byte-identical renders and gallery). Spec: FR-45 amended, Appendix B (era packs, planned after v2.0) added.

## M4 — Scenes & templates

Covers AC-03 and AC-04 (first slides match the approved references; automated part is a per-region ΔE76 of at most 8 on mean Lab colour, owner sign-off still required), AC-05 and AC-06 (template and layer scenes never overlap seal, tag, text or another head), AC-10 (`render --preview` never starts a process, now with scenes) and AC-12 (two full renders of each example are byte-identical).

- Tasks 16-19: layer registry and sun/moon, birds and eggshell clouds; mountains, peaks, hills, river and ground; boat with crew and lotus; characters layer; `group` and `landscape` templates that expand to the reference layers.
- Task 20 fix: `centre_pair` accepts exactly 1, 2, 4 or 6 characters (an odd extra character always stood in front of a head); other counts are a `validate` error pointing to `line` or `v_shape`. Snapshot baselines are written atomically.
- Task 20: `render --preview` draws every slide's scene (`render.scene_expander`). `validate` expands template scenes and runs the FR-48 overlap checks on their characters and boat crew with script paths (`slides[i].scene.characters[k]`, `slides[i].scene.boats[b].crew[k]`); `check_overlaps` now requires `tag` and `file`, so the tag-pill check cannot be skipped by accident. `gallery` grows to 1080x4080 with three rows of layer-type cells. New tests: ΔE76 region comparison against the approved references (`tests/helpers/visual.py`), first-slide SHA-256 snapshots keyed by library versions (`--update-snapshots`), full-run determinism. The `me_linh` example's first slide now uses the plain `landscape` template, so its second boat matches the approved image. The snapshot baseline for the pinned versions was written intentionally with `pytest --update-snapshots`.

## M5 — Video

Covers AC-01 and AC-02 (1080x1920, 30 fps, h264, yuv420p, duration = sum of slides within 0.1 s), AC-13 (`--music` audio equals the video length and fades out) and AC-14 (no FFmpeg: exit 4 with an install hint, before any slide is rendered); FR-80..83, FR-85, FR-86, FR-90..92, NFR-04, NFR-05.

- Task 21: `ffmpeg.py` with discovery (>= 4.4, per-OS install hint), exact command builders for clips, concat and mux, a shell-free runner that keeps the last 20 stderr lines, and `probe`.
- Task 22: `video.assemble` (temp dir, serial clip encodes, concat, mux to `<out>.partial.mp4`, atomic rename; partial file and temp dir removed on any error or Ctrl-C), `report.py` (`<video>.report.json`, `sources_block`), and `render` end to end: validate, find FFmpeg, render slides, assemble, report, summary. `--music`, `--music-volume` (0 to 2), `--keep-temp` and `--verbose` now work; `--jobs` still waits for Task 23 and `--music`, `--music-volume`, `--keep-temp` warn that they have no effect with `--preview`. Hardening from the Task 21 review: an `OSError` from a binary that cannot run becomes `FfmpegMissing` (discovery) or `FfmpegFailed` (run, probe), `probe` also rejects `AttributeError` and `TypeError` parse failures, and music fades are scaled down together for videos shorter than 2 s.

## M6 — Polish

- Task 23: `--jobs N` encodes clips in parallel (FR-87) with a thread pool; the default is CPU count - 1 (`video.default_jobs`), `--jobs 0` is a usage error (exit 2), `--jobs 1` is serial. The concat order is always slide order. The first failure cancels pending clips, waits for running ones, raises the first error in slide order, then cleans up as before.
- Task 24: `"motion": "zoom_in"` (FR-84). `clip_cmd` pre-scales the slide 4x and runs `zoompan` from 100 % to 106 % about the centre, then the usual fades; `RenderOptions.motions` carries each slide's motion to the clip encoder and the "not implemented" `WARN` is gone. Slide 2 of both examples uses it.
- Task 25: eggshell cache (FR-66): `compose.EggshellCache` is created once per `render_slides` run and shared by every slide through `DrawContext.cache`; identical masks (same crc32, cell, gap, seed, layer, shape) are computed once and the arrays are read-only. Per-character `seed` (FR-49): `Variation(bun, sash, dot_spacing)` from `variation_for(seed)`, carried by `CharacterStyle.variation` and applied by the `ancient_female` kit; no seed leaves the figure exactly as before.

- Task 26: final QA. Performance measured against NFR-01 and NFR-03 (all targets met), line coverage measured against NFR-08 (every required group at least 98 %, no tests needed), the AC-01..AC-15 walkthrough, and the README completed (setup per OS, data contracts, sources workflow, performance, coverage, acceptance). `pytest-cov` added as an owner-approved dev dependency (pinned 7.1.0; spec C-03, CLAUDE.md and README updated); it is not part of the default `pytest -q` run.

## v2.0.0

First complete release. `history-shorts` turns a `script.json` and a `theme.json` into a 1080x1920, 30 fps H.264 video in the style of Vietnamese lacquer painting, entirely offline and without any AI.

- M1 foundation: strict config validation with path-tracked errors, layout, text and the Vietnamese glyph check.
- M2 textures and chrome: lacquer ground, gold leaf, eggshell and surface finish; frame, scrolls, waves, seal and tag.
- M3 characters: role presets, costume kits, formations and FR-48 overlap checks, the `gallery` command.
- M4 scenes: layer registry, `group` and `landscape` templates matching the approved references, `render --preview`.
- M5 video: FFmpeg discovery and commands, clip encode, concat, music mix, atomic output, render report.
- M6 polish: parallel encoding, `zoom_in` motion, eggshell cache, per-character variety, final QA.

Acceptance: AC-01..AC-15 met (see the README); owner sign-off on AC-03 and AC-04 given 2026-11-08.

## Unreleased

### Docs

- Spec amended to 2.0.1: optional palette keys, sheen position, per-layer texture overrides, oar grip, text and chrome placement, eggshell RNG, dependency pinning note, and Appendix A (v2.1 storyboard, planned).
- README: macOS setup and decisions log.
