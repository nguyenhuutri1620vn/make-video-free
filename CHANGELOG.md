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
- Task 15: `gallery [--theme PATH] [--out PATH]` writes a 1080x3000 contact sheet (default `output/gallery.png`): 4 props across, 8 role x facing rows down (roles in preset order, facing +1 then -1), on one lacquer ground, each cell labelled `role · facing · prop`. Figures use their role preset's crest. Layer-type rows arrive with the scene layers (Task 20).

## Unreleased

### Docs

- Spec amended to 2.0.1: optional palette keys, sheen position, per-layer texture overrides, oar grip, text and chrome placement, eggshell RNG, dependency pinning note, and Appendix A (v2.1 storyboard, planned).
- README: macOS setup and decisions log.
