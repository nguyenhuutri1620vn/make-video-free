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

## Unreleased

### Docs

- Spec amended to 2.0.1: optional palette keys, sheen position, per-layer texture overrides, oar grip, text and chrome placement, eggshell RNG, dependency pinning note, and Appendix A (v2.1 storyboard, planned).
- README: macOS setup and decisions log.
