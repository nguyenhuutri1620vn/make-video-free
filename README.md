# make-video-free

`history-shorts`: an offline Python CLI that turns a `script.json` and a `theme.json` into a 1080x1920 vertical video about Vietnamese history, illustrated in the style of Vietnamese lacquer painting. See `docs/raw_requirement.md` for the specification and `CLAUDE.md` for working rules.

## Setup (macOS)

```bash
python3 -m venv .venv && source .venv/bin/activate
brew install cairo pkg-config
pip install -e ".[dev]" -c constraints.txt
```

FFmpeg and ffprobe must also be on PATH (for example `brew install ffmpeg`).

`constraints.txt` pins the dev versions (pycairo 1.29.2, numpy 2.4.6, scipy 1.17.1, Pillow 13.0.0), which need Python 3.11 or newer. `pyproject.toml` itself declares ranges that are valid on Python 3.10.

Known issue: Homebrew `freetype` 2.15.0 bottles link `/usr/lib/libhvf.dylib`, which is missing on macOS 15.0.1. Symptom: Cairo or Pillow fails to load freetype. Fix:

```bash
brew reinstall --build-from-source freetype
```

## Decisions

Owner decisions recorded in the spec (v2.0.1), one line each:

- Palette: the 13 required keys stay required; 14 optional keys (`robe_general_dk`, `robe_general_alt_dk`, `robe_crew_dk`, `egg_tone`, `egg_gap`, `sheen`, `shadow`, `deep_warm`, `mountain_base`, `peak_base`, `river_top`, `hull_dk`, `leaf_dk`, `petal_tip`) fall back to a required key when absent (spec §6.2).
- Textures: `sheen` is `{x, y, r, strength}`, default `{330, 760, 620, 0.10}` from prototype `lac.finish` (§6.2).
- Layers: optional per-layer texture overrides (`tile`/`worn` on sun and moon; `cell`/`gap` on clouds, hills, and eggshell peaks); `characters.baseline` defaults to 1100; boat crew `x`/`baseline`/`height` are canvas px, computed from boat slots when omitted (§6.3).
- Oar grip: the oar shaft runs through the hand centre (17.3, -60.5) and the blade top (25, 0), from y -78 to y 6, with a front shaft segment like the spear and flag (FR-44, AC-07).
- Text placement: one-line title top at y 1215; two-line title tops at 1190 and 1190 + round(size x 102 / 92); subtitle top = last title line top + 128, extra lines step round(size x 56 / 46); subtitle colour continues the title alternation (`egg` after two lines, `gold_lt` after one) (§8.2, §8.4).
- Safe zone applies to text, seal, tag, and character head boxes; robes and props may extend past it (FR-26, §8.2).
- Optional chrome, off by default: progress bar at y 1540, height 4, x 80-930 (track `gold_dk` at alpha 0.4, fill `gold`); footer in the `tag` font, `gold_dk`, centred at x 540, top y 1830 (§8.2).
- Eggshell RNG is `default_rng([seed, layer_index, mask_crc32])`, independent of slide index, so repeated clouds and hills match across slides and the cache hits; all other RNGs keep `[seed, slide_index, layer_index]` (FR-65, FR-66).
- Dependencies: `pyproject.toml` declares Python 3.10-compatible ranges, `constraints.txt` pins dev versions, and snapshot baselines exist only for pinned sets (§16 R-02).
- Planned for v2.1, not implemented: narration export for the owner's VoiceStudio, extra motions, and extra poses (Appendix A).
