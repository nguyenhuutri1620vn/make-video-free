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

## Usage

```bash
python -m history_shorts validate --script examples/nu_tuong/script.json
python -m history_shorts render --script examples/nu_tuong/script.json --preview
python -m history_shorts render --script examples/me_linh/script.json --preview --out output/me_linh.mp4 --debug-safe-zone
```

`render --preview` validates the script first (exit 3 and nothing written on any error), then writes one PNG per slide to `slides/NN.png` (1-based) in the directory of `--out` and prints the slide count, that directory, the elapsed time and the sources. It never starts FFmpeg. `--out` defaults to `output/<slug of the title>.mp4` relative to the current directory; the video itself is not produced yet (milestone M5), so without `--preview` the command renders the PNGs and then exits 1 with a clear message. Slides are chrome and text only until the scenes arrive in M4.

PNGs are written atomically (`NN.png.tmp`, then rename). Existing `NN.png` files numbered beyond the slide count are never deleted; a `WARN` line lists them. `--music`, `--music-volume`, `--keep-temp` and `--jobs` are accepted but ignored for now (a `WARN` says so). `--verbose` logs the time per slide; `--debug-safe-zone` outlines the safe zone and regions.

## Fonts

Liberation Serif 2.1.5 (SIL Open Font License 1.1; licence text in `themes/son_mai/fonts/LICENSE`), copied from the official release tarball:

`https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz` (linked from the release page `https://github.com/liberationfonts/liberation-fonts/releases/tag/2.1.5`; tarball SHA-256 `7191c669bf38899f73a2094ed00f7b800553364f90e2637010a69c0e268f25d0`)

| File in `themes/son_mai/fonts/` | SHA-256 |
|---|---|
| `LiberationSerif-Bold.ttf` | `d754ba427cfe0bca54ae052384baa8f842da5bd6550ad4da024ac441e7a7d5ce` |
| `LiberationSerif-Italic.ttf` | `0e3dea9f8d613e006ccfa62201f33e265d19167bd0907725c3e145368b04fc2e` |
| `LICENSE` | `93fed46019c38bbe566b479d22148e2e8a1e85ada614accb0211c37b2c61c19b` |

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
