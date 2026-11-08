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
python -m history_shorts render --script examples/nu_tuong/script.json --out output/nu_tuong.mp4
python -m history_shorts render --script examples/me_linh/script.json --music song.mp3 --music-volume 0.5
python -m history_shorts render --script examples/nu_tuong/script.json --preview
python -m history_shorts render --script examples/me_linh/script.json --preview --out output/me_linh.mp4 --debug-safe-zone
python -m history_shorts gallery --out output/gallery.png
```

`render` validates the script first (exit 3 and nothing written on any error). Without `--preview` it then looks for FFmpeg (exit 4 with an install hint when it is missing or older than 4.4, before any slide is drawn), renders the slide PNGs, encodes one H.264 clip per slide with the theme's fades, joins the clips, adds the audio track and writes the MP4 (1080x1920, 30 fps, `yuv420p`, CRF from the theme, `+faststart`), a render report and a console summary. `--out` defaults to `output/<slug of the title>.mp4` relative to the current directory; its folder is created when missing, and paths with spaces, apostrophes and Vietnamese characters work.

- Audio: without `--music` the video carries a silent AAC track. `--music FILE` (must exist, otherwise exit 3) is looped or trimmed to the video length, faded in over 0.5 s and out over 1.5 s (both scaled down together for videos shorter than 2 s) and mixed at `--music-volume` (0 to 2, default 0.6; outside that range is a usage error, exit 2). Output is AAC 192 kbps, 48 kHz, stereo.
- Output is atomic: the audio mux writes `<out>.partial.mp4` next to the output (a temporary file; do not keep anything of that name there), which is renamed onto `--out` only when complete. On any error or Ctrl-C (exit 130) the partial file and the temp directory are removed and an existing `--out` is left untouched. An existing `--out` is replaced after a successful render.
- Temp files (clips, concat list, silent video) live in a `history-shorts-*` directory under the system temp dir and are removed afterwards; `--keep-temp` keeps it and logs its path. `--verbose` also logs every FFmpeg command and the time per slide. FFmpeg failures exit 5 and print the last 20 lines of its stderr.
- `--jobs` is accepted but ignored for now (a `WARN` says so); clips are encoded one after the other. A slide's `"motion": "zoom_in"` is not implemented yet and is ignored with a `WARN`.
- Console summary: slide count, total duration, video path, report path, elapsed time and the `Sources:` block ready to paste into a caption.

`render --preview` writes one PNG per slide to `slides/NN.png` (1-based) in the directory of `--out` and prints the slide count, that directory, the elapsed time and the sources. It never starts FFmpeg; `--music`, `--music-volume` and `--keep-temp` are ignored with a `WARN`. A slide's `scene` (a `group` or `landscape` template, or explicit layers) is drawn between the ground and the chrome; a slide without a scene is chrome and text on the lacquer ground.

PNGs are always written to `<out dir>/slides/` (also without `--preview`), atomically (`NN.png.tmp`, then rename). Existing `NN.png` files numbered beyond the slide count are never deleted; a `WARN` line lists them. `--debug-safe-zone` outlines the safe zone and regions.

### Render report

Next to the video, `render` writes `<video name>.report.json` (UTF-8, indented, sorted keys, written atomically):

| Key | Content |
|---|---|
| `script_sha256`, `theme_sha256`, `music_sha256` | SHA-256 of the input files (`music_sha256` is `null` without music) |
| `slides` | `[{index, duration, png}]`; `png` is relative to the report's folder (`slides/01.png`) |
| `total_duration` | seconds, the sum of the slide durations (each a whole number of frames) |
| `warnings` | validation warnings, formatted like the console lines |
| `versions` | `python`, `pycairo`, `cairo`, `numpy`, `scipy`, `Pillow`, `ffmpeg` (`"dev"` for a development build) |
| `timings` | seconds per phase: `validate`, `render_slides`, `encode`, `concat`, `mux`, `total` |
| `sources` | the script's `sources`, in order |

`gallery` renders a 1080x4080 contact sheet. The top block is every role x facing x prop (4 props across, 8 role x facing rows down, each cell labelled `role · facing · prop`) so the characters can be reviewed at a glance. Below it, three rows of 270x360 cells show each scene layer type with the reference template's parameters (sun, moon, clouds, mountains, peaks gradient, peaks eggshell, hills left, river, ground, boat, birds, lotus); each is the layer drawn at full canvas scale, with a fixed 3:4 crop scaled into its cell (`gallery.LAYER_SPECS`). `--out` defaults to `output/gallery.png` relative to the current directory; parent directories are created and the PNG is written atomically. Figures use their role's default crest.

## Tests and snapshots

```bash
pytest -q                        # everything; E2E tests marked `ffmpeg` skip without FFmpeg
pytest --update-snapshots        # write the snapshot baselines for the installed library versions
```

Snapshot tests hash the first slide's PNG of both examples (`tests/test_compose_snapshot.py`). Baselines live in `tests/snapshots/baselines.json`, keyed by `pycairo=...;numpy=...;scipy=...;Pillow=...` (spec R-02): a pixel is only reproducible for one set of library versions. On any other set the snapshot tests skip with "run pytest --update-snapshots". Use that flag only for an intentional visual change (or a deliberate version bump), say so in the change, and review the new PNGs by eye before committing `baselines.json`.

`tests/test_visual.py` also compares the first slide of each example with the approved references in `docs/reference/approved/`: the mean colour of each layout region (header, visual, title, subtitle, chrome) is converted to CIE Lab (D65) and the ΔE76 must stay at or below 8 (AC-03, AC-04). This is a coarse automated gate; owner sign-off on the preview PNGs is still required.

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
- Safe zone applies to text, seal, and tag. Character head boxes stay inside the frame (inset 58); the approved `group` composition extends past the safe zone's right edge, and the approved look wins (FR-26, §8.2).
- Overlaps (FR-48): a character's head, body or prop box may not touch the seal, tag pill or a text box. "Covers another head" is decided on rendered pixels (a later-drawn character's mask against an earlier head mask, zero tolerance), because box-against-box would reject the approved `group` composition. Formations draw back rows first (FR-47).
- Optional chrome, off by default: progress bar at y 1540, height 4, x 80-930 (track `gold_dk` at alpha 0.4, fill `gold`); footer in the `tag` font, `gold_dk`, centred at x 540, top y 1830 (§8.2).
- Eggshell RNG is `default_rng([seed, layer_index, mask_crc32])`, independent of slide index, so repeated clouds and hills match across slides and the cache hits; all other RNGs keep `[seed, slide_index, layer_index]` (FR-65, FR-66).
- Dependencies: `pyproject.toml` declares Python 3.10-compatible ranges, `constraints.txt` pins dev versions, and snapshot baselines exist only for pinned sets (§16 R-02).
- Costume kits (FR-45): each role preset names a kit (`characters/kits/`); all v2.0 roles use `ancient_female`, whose props are flag, spear, oar and none. A prop the role's kit cannot draw is a `validate` error at `<character>.prop`, a role naming an unknown kit one at `<character>.role`. `figure.py` holds no part names or geometry. The refactor is pixel-identical (Task 15b). Era packs are planned (spec Appendix B).
- Formations (FR-47): `centre_pair` takes exactly 1, 2, 4 or 6 characters. An odd extra character (3 or 5) would stand in the centre in front of another character's head and always fail the FR-48 check, so it is a count error that points to `line` or `v_shape`.
- Video (FR-80..92): the video length is the sum of the slide durations, each already a whole number of frames, so the mux uses `-t` of that sum rounded to 3 decimals. FFmpeg is located before any slide is rendered (AC-14). The report's `ffmpeg` version is `major.minor`, or `dev` for builds without a release number.
- Planned for v2.1, not implemented: narration export for the owner's VoiceStudio, extra motions, and extra poses (Appendix A).
