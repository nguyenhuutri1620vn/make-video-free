# make-video-free

`history-shorts`: an offline Python CLI that turns a `script.json` and a `theme.json` into a 1080x1920 vertical video about Vietnamese history, illustrated in the style of Vietnamese lacquer painting. See `docs/raw_requirement.md` for the specification and `CLAUDE.md` for working rules.

## Setup

Requirements: Python 3.10 or newer (3.11 or newer to use the pinned `constraints.txt`), the Cairo library, and FFmpeg and ffprobe 4.4 or newer on PATH. Nothing is downloaded at runtime.

### macOS (verified on this machine)

```bash
python3 -m venv .venv && source .venv/bin/activate
brew install cairo pkg-config
pip install -e ".[dev]" -c constraints.txt
```

FFmpeg and ffprobe must also be on PATH (for example `brew install ffmpeg`).

`constraints.txt` pins the runtime versions (pycairo 1.29.2, numpy 2.4.6, scipy 1.17.1, Pillow 13.0.0) and the dev tools (pytest 9.2.0, ruff 0.17.4, mypy 2.4.1, pytest-cov 7.1.0), which need Python 3.11 or newer. `pyproject.toml` itself declares ranges that are valid on Python 3.10.

Known issue: Homebrew `freetype` 2.15.0 bottles link `/usr/lib/libhvf.dylib`, which is missing on macOS 15.0.1. Symptom: Cairo or Pillow fails to load freetype. Fix:

```bash
brew reinstall --build-from-source freetype
```

### Ubuntu / Debian (not verified on this machine)

```bash
sudo apt install python3-venv python3-dev libcairo2-dev pkg-config ffmpeg
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" -c constraints.txt
```

> **Install note (v2.0):** `pip install -e .` from a checkout of this repository is the supported install. The default theme (`themes/son_mai/`) is found relative to the source tree, so a plain `pip install` of a built wheel, which does not ship `themes/`, is not supported; pass `--theme PATH` there.

### Windows (not verified on this machine)

```bat
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]" -c constraints.txt
```

pycairo, numpy, scipy and Pillow ship Windows wheels on PyPI, so no Cairo install is needed. Install FFmpeg (a release build that includes `ffprobe`) and put its `bin` folder on PATH. If a wheel cannot be installed on a restricted machine, use conda-forge packages, `pip install --user`, or a portable FFmpeg build.

On Windows, when stdout or stderr is redirected to a file or pipe and the console code page is not UTF-8 (for example cp1252), the CLI switches those streams to UTF-8 so Vietnamese text (the Sources block) never crashes a finished render; on a real console it keeps the console encoding and replaces unencodable characters with `?`. Use a UTF-8 capable terminal (Windows Terminal) for readable output.

`python -m history_shorts validate` checks the runtime imports first and prints a per-OS install hint (exit 1) if one is missing.

## Usage

```bash
python -m history_shorts validate --script examples/nu_tuong/script.json
python -m history_shorts render --script examples/nu_tuong/script.json --out output/nu_tuong.mp4
python -m history_shorts render --script examples/me_linh/script.json --music song.mp3 --music-volume 0.5
python -m history_shorts render --script examples/nu_tuong/script.json --preview
python -m history_shorts render --script examples/me_linh/script.json --preview --out output/me_linh.mp4 --debug-safe-zone
python -m history_shorts gallery --out output/gallery.png
python -m history_shorts export-narration --script examples/hai_ba_trung/script.json --out output/voice/hai_ba_trung
python -m history_shorts audio-manifest --narration output/voice/hai_ba_trung
python -m history_shorts render --script examples/hai_ba_trung/script.json --audio output/voice/hai_ba_trung/audio_manifest.json
python tools/make_video.py --script examples/hai_ba_trung/script.json --music song.mp3 --voice-cmd "my-tts {text} {wav}"
```

`render` validates the script first (exit 3 and nothing written on any error). Without `--preview` it then looks for FFmpeg (exit 4 with an install hint when it is missing or older than 4.4, before any slide is drawn), renders the slide PNGs, encodes one H.264 clip per slide with the theme's fades, joins the clips, adds the audio track and writes the MP4 (1080x1920, 30 fps, `yuv420p`, CRF from the theme, `+faststart`), a render report and a console summary. `--out` defaults to `output/<slug of the title>.mp4` relative to the current directory; its folder is created when missing, and paths with spaces, apostrophes and Vietnamese characters work.

- Audio: without `--music` the video carries a silent AAC track. `--music FILE` (must exist, otherwise exit 3) is looped or trimmed to the video length, faded in over 0.5 s and out over 1.5 s (both scaled down together for videos shorter than 2 s) and mixed at `--music-volume` (0 to 2, default 0.6; outside that range is a usage error, exit 2). Output is AAC 192 kbps, 48 kHz, stereo.
- Output is atomic: the audio mux writes `<out>.partial.mp4` next to the output (a temporary file; do not keep anything of that name there), which is renamed onto `--out` only when complete. On any error or Ctrl-C (exit 130) the partial file and the temp directory are removed and an existing `--out` is left untouched. An existing `--out` is replaced after a successful render.
- Temp files (clips, concat list, silent video) live in a `history-shorts-*` directory under the system temp dir and are removed afterwards; `--keep-temp` keeps it and logs its path. `--verbose` also logs every FFmpeg command and the time per slide. FFmpeg failures exit 5 and print the last 20 lines of its stderr.
- `--jobs N` encodes clips in parallel (default: CPU count - 1, at least 1; `--jobs 1` is serial). The clips are always joined in slide order. On a failure or Ctrl-C the clips already encoding finish first, which takes a few seconds. Each parallel clip encode is capped to CPU count / jobs libx264 threads. For short still-image clips `--jobs 1` can be about as fast (x264 already uses several cores), so the gain is small. A slide with `"motion": "zoom_in"` zooms slowly from 100 % to 106 % about the centre over its duration (FFmpeg `zoompan` on a 4x pre-scaled image); the default `"none"` keeps the slide still.
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
| `sources` | the script's `sources`, in order, each as `{text, type}` (`type` is `null` when not given) |

### Data contracts

The full contracts are in [`docs/raw_requirement.md`](docs/raw_requirement.md) section 6 (script 6.1, theme 6.2, scene 6.3). In short:

- `script.json`: `schema_version` (`"2.0"`), `title`, `sources` (citation strings, or `{"text": ..., "type": "book" | "journal" | "news" | "web" | "other"}`) and `slides`. A slide has `tag`, `title`, `subtitle`, and optionally `duration` (seconds; otherwise derived from the text), `motion` (`none` or `zoom_in`), `claim` (true for a factual statement), `source` (an index into `sources`, or an array of indices) and `scene`. A `scene` is either `{"template": "group" | "landscape", ...overrides}` or explicit `layers`; no `scene` gives chrome and text on the lacquer ground. Look at `examples/nu_tuong/script.json` and `examples/me_linh/script.json`.
- `theme.json` (`themes/son_mai/theme.json`): `seed`, `palette` (13 required colour keys and 14 optional ones), `fonts`, `type_scale`, `textures`, `chrome`, `transition`, `video`. No colour, font or size is hardcoded in drawing code, so changing `palette.gold` recolours every gold element.
- Validation reports every error at once with its JSON path (exit 3); warnings (text auto-shrunk, total duration outside 15-90 s, missing `sources`, `claim` without `source`, unknown keys) never fail.

### Narration workflow (v2.1)

Narration is voiced by the owner's separate sound project (VoiceStudio). history-shorts and that project exchange files only: no imports, no subprocess calls and no network between them. The contract is spec Appendix A.1.

1. Add `"schema_version": "2.1"` and, on each slide, `narration` (Vietnamese, 1 to 600 characters, `[pause Nms]` with N from 50 to 3000 is the only bracket tag) and an explicit `id` (`^[a-z0-9][a-z0-9_-]{0,31}$`, unique). `id` is required on every slide once any slide has `narration`.
2. `python -m history_shorts export-narration --script S --out DIR` writes `DIR/<id>.txt` (UTF-8, LF, one final newline) and `DIR/manifest.json`, which records the SHA-256 of each file. Re-running on an unchanged script gives byte-identical output. Only files named in the manifest are written.
3. The sound project turns each `.txt` into `<id>.wav` or `<id>.flac` (0.3 to 14.0 s) in the same folder (or any folder). Then `python -m history_shorts audio-manifest --narration DIR [--voices VOICES]` writes `audio_manifest.json` into the voices folder, copying each `text_sha256` unchanged. It exits 3 and writes nothing when a voice is missing, when one id has both `.wav` and `.flac`, when a `.txt` was edited by hand, or when a voice is older than its `.txt` (re-record). A `gain_db` you added by hand is kept while that text is unchanged. `export-narration` leaves unchanged files untouched, so only edited narrations count as stale.
4. `validate --audio PATH` and `render --audio PATH` check the manifest. Editing a narration after export fails with exit 3 and names the stale slide ids (re-record those). A voice file that is missing, outside the manifest folder, unreadable or out of range also exits 3.

#### One-command pipeline

`tools/make_video.py` runs every step and stops at the first failure:

```bash
python tools/make_video.py --script examples/hai_ba_trung/script.json --music music/nhac.mp3 --voice-cmd "voicestudio-cli --input {text} --output {wav}"
```

`--voice-cmd` is your sound project's command for one voice; `{text}`, `{wav}` and `{id}` are replaced in each argument and it runs without a shell. It is called only for voices that are missing or older than their text, so re-runs are quick. Without `--voice-cmd` the tool lists the `.txt` → `.wav` files to record in `output/voice/<script folder>/` and exits 3; record them and run the same command again. Other options: `--out`, `--theme`, `--music-volume`, `--sfx-volume`, `--work` (narration and voice folder). A script without narration goes straight to `render`.

**Draft voice without VoiceStudio (macOS).** `tools/say_voice.py` voices one `.txt` with the built-in offline `say` voice "Linh" (vi_VN), turning `[pause Nms]` into silence and writing a 16-bit mono WAV:

```bash
.venv/bin/python tools/make_video.py --script examples/hai_ba_trung/script.json --voice-cmd ".venv/bin/python tools/say_voice.py {text} {wav}"
```

It speaks at 200 words per minute by default (`--rate N` to change; `--voice NAME` for another `say` voice), because Linh's default pace pushed the longest `hai_ba_trung` slide to 16.6 s, over the 14 s limit. It is a placeholder voice: delete the `.wav` files (or re-record them) when the real voices exist. Use the venv's Python explicitly if `python` is a shell alias, since `--voice-cmd` runs without a shell.

Timing: a voiced slide lasts `ceil_to_frame(lead_in + voice + tail)` (defaults 0.3 s and 0.5 s, from the theme's `audio` block). An explicit `duration` is kept when it is at least that long, and is an error when shorter. A slide cannot exceed 15 s. The voice starts `lead_in` after the slide starts.

Mix: each voice is delayed to its slide, the voices are summed, the music (if any) is ducked by the voice with a sidechain compressor, and the result goes through one `loudnorm` pass to `loudness_lufs` and `true_peak_db`. Without `--audio` the FFmpeg commands are the v2.0 commands, unchanged. A script with `narration` rendered without `--audio` gives a `WARN` and no voice.

The report adds an `audio` block (manifest path and SHA-256, and per slide `id`, `voice_file`, `voice_seconds`, `duration`). The console summary adds the voiced-slide count.

### Motions, transitions and sound cues (v2.1, M8)

Optional slide fields in a `"2.1"` script (spec Appendix A.2):

- `motion`: `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `pan_up`, `pan_down`.
- `transition`: how the slide enters: `fade`, `fadeblack`, `dissolve`, `slideleft`, `slideright`, `slideup`, `wipeleft`, `wiperight`, `circleopen` (default `cut`). The overlap is the theme's `transition.duration` (0.5 s); total length is unchanged.
- `tone`: `warm`, `cold`, `gray`, graded from the theme's `tones` block; text keeps its colours.
- `text_in`: `fade`: title and subtitle fade in on a still layer while the scene moves.
- `sfx`: up to 4 `{ "file": "sfx/drum.wav", "at": 0.0, "gain_db": 0 }` per slide; files are yours, relative to the script.
- `music_cut`: `{ "at": 0.0, "duration": 1.0 }` silences `--music` for that window.

`examples/vuong_trieu_nu/script.json` uses every visual effect and one music cut. Its suggested sound cues (add the files, then the `sfx` entries): a drum hit at `vua-nu` 0.0 s, a short "tách" at `65-thanh` 0.0 s, a low drum at `ma-vien` 0.0 s.

### Living slides and synthesized sound (v2.2, M9)

With `"schema_version": "2.2"` (spec Appendix A.4):

- `"living": true` turns a slide into moving planes: far, mid and near layers slide at different speeds under the slide's `motion` (eased in and out), while the gold frame, seal, tag and text stay still. Clouds and birds drift, the river ripples, boats bob, lotus sways, lanterns float and flicker, the sun or moon glows. A layer's plane can be set with `"plane": "far" | "mid" | "near"`.
- `"particles": "petals" | "dust" | "embers"` adds a few light particles to a living slide.
- Sound cues can name a sound instead of a file: `{ "sound": "gong", "at": 0.4, "gain_db": -6, "shake": true }`. The sounds are synthesized in code, nothing is downloaded:

| `sound` | Character | Notes |
|---------|-----------|-------|
| `gong` | deep bronze gong, about 4 s ring | `shake` allowed |
| `drum` | big drum hit with a faint bronze ring | `shake` allowed |
| `bell` | temple bell, about 3 s | |
| `whoosh` | soft swish | optional `duration` |
| `wind` | gentle wind bed | `duration` required |
| `water` | lapping water bed | `duration` required |

`render --sfx-volume 0.5` plays every sound effect (file cues, synthesized sounds and the automatic whoosh) at half amplitude, about −6 dB, on top of each cue's `gain_db`. Range 0 to 2, default 1; 0 mutes the effects.

- Moving transitions (`slideleft`, `slideright`, `slideup`, `wipeleft`, `wiperight`, `circleopen`) get an automatic soft whoosh; `"auto_sfx": false` turns it off for that slide.
- Tuning lives in the theme's optional `living` and `sfx` blocks (travel per plane, shake size, loop length, reverb, whoosh level).
- `examples/hai_ba_trung/script.json` uses all of this. `--preview` still writes the still PNGs; the moving planes are built only for the video, in the temp directory (`--keep-temp` keeps them).

### Characters and scenes that move (v2.3, M10)

With `"schema_version": "2.3"` (spec Appendix A.5), a living slide comes alive without new fields: furnace flames flicker, temple incense smoke sways, banners and the elephant's flag wave, and every character breathes and sways slightly while held flags wave. Boat crew move with their boat.

Characters can also act at a given time:

```json
"actions": [
  { "who": "leader_1", "do": "rally", "at": 0.6 },
  { "who": "dan", "do": "kneel", "at": 1.2 }
]
```

- Give a character an `id` (`[a-z0-9_]`); template characters already have one (`group`: `leader_1`, `leader_2`, `general_alt_1`, `general_alt_2`, `general_1`, `general_2`; `landscape` crew: `crew_1` to `crew_4`).
- Actions: `rally` (raise the free arm; a flag-bearer raises the flag), `bow`, `kneel`, `sit`, `stand_up`, `raise_flag`, `look`. `duration` overrides the default length.
- A character can start `"pose": "kneeling"` or `"seated"`, stay still with `"idle": false`, or stand on a boat with `"on": <boat layer index>`.
- `validate` checks ids, action names, overlaps, the slide end (auto timing when no voice is given, so leave room) and FR-48 while moving.
- Tuning lives in the theme `living` block (`flame_px`, `smoke_sway_px`, `cloth_wave`, `idle_loop_seconds`, `breath_scale`, `idle_sway_deg`, `idle_head_deg`, `flag_wave_hz`).
- `examples/hai_ba_trung` and `examples/trong_dong` use 2.3.

### Artwork files: new objects without code (v2.3, M11)

New scene objects are JSON files in `themes/son_mai/artwork/`, drawn in the lacquer style by one layer: `{"type": "artwork", "name": "torch", "x": 540, "y": 1100, "scale": 1.5}`. A file lists parts (SVG path strings, ellipses, rectangles) with palette colours, gradients, gold leaf or eggshell, gold outlines, clipping, and optional motion (`flicker`, `wave`, `sway`, `rise`, `pulse`) that plays on living slides.

```bash
python -m history_shorts artwork check
python -m history_shorts artwork preview --name torch --out output/torch.png
```

How to draw one: `docs/artwork-guide.md`. Shipped: `tablet_altar` (the tablet layer as a file) and `torch`.

### Scene objects without people

Extra layer types from `docs/visual_backlog.md`, usable in any `{"layers": [...]}` scene:

- `drum`: `{"type": "drum", "x": 540, "y": 720, "r": 400, "birds": 8}`: a bronze-drum face (original drawing) with a star, ring bands and flying birds.
- `gong`: `{"type": "gong", "x": 540, "y": 730, "r": 160}`: a gong hanging in a carved wooden frame, with its mallet; the frame spans about 1.9 r either side and 2.6 r above the face.
- `temple`: `{"type": "temple", "x": 540, "y": 1100, "scale": 1.5, "incense": true}`: a temple gate (original design) standing on the ground line `y`, about 430 x 270 units.
- `map`: `{"type": "map", "x": 110, "y": 330, "w": 860, "h": 780, "dots": [[0.34, 0.36]], "scatter": 65, "arrow": false}`: a stylised delta map panel (not traced from a real map). `dots` are big red marks in map units (0–1), `scatter` adds that many small dots on land, `arrow` adds a red arrow from the north.
- `scroll`: `{"type": "scroll", "x": 520, "y": 760, "scale": 2.1}`: a half-unrolled scroll with abstract ink columns (not readable text), a red seal and a brush; about 420 x 300 units.
- `elephant`: `{"type": "elephant", "x": 520, "y": 1100, "scale": 2.1, "facing": 1, "flag": true}`: a war elephant with a saddle cloth and a flag, no rider; feet on `y`, about 300 x 300 units with the flag.
- `stilt_house`: `{"type": "stilt_house", "x": 560, "y": 1095, "scale": 1.45, "bamboo": true}`: a nhà sàn on stilts with a thatched saddle roof and a ladder; the bamboo clump stands to its left.
- `banners`: `{"type": "banners", "y": 1080, "rows": 4}`: rows of hills planted with flags and spears, the back row smallest; rows are 70 px apart, so the back row sits at `y - 70 * (rows - 1)`.
- `regalia`: `{"type": "regalia", "x": 540, "y": 1095, "scale": 2.2, "screen": true}`: a crown and a square seal on a cushion and low table, with an optional folding screen behind (about 320 x 310 units).
- `fallen_flags`: `{"type": "fallen_flags", "x": 560, "y": 1095, "scale": 2.2}`: an abandoned camp (empty tent, spears lying at rest, a torn flag, a cold fire); no people and no violence.
- `sail_boat`: `{"type": "sail_boat", "x": 540, "y": 1060, "scale": 1.5, "facing": 1}`: a sailing boat with two ribbed red sails, no crew; `y` is the waterline, the mast reaches 330 units above it.
- `lone_path`: `{"type": "lone_path", "y": 1145, "depth": 340, "mist": true}`: a path that winds and narrows from `y` up to `y - depth`, with soft mist bands over the far end.
- `lanterns`: `{"type": "lanterns", "items": [{"x": 520, "y": 1095, "scale": 2.1}]}`: floating lotus lanterns, each with a flame, a soft glow and a reflection; list far (small) ones first.
- `tablet`: `{"type": "tablet", "x": 540, "y": 1095, "scale": 1.75}`: a blank memorial tablet (never any text) on an altar with an incense bowl and two candles; about 280 x 350 units.
- `horse`: `{"type": "horse", "x": 690, "y": 1095, "scale": 1.75, "facing": -1}`: a bronze horse statue (gold leaf) on a stone plinth, no rider; used with `drum` for "Trống đồng → Ngựa đồng" in `examples/hai_ba_trung`.
- `citadel`: `{"type": "citadel", "x": 540, "y": 860, "scale": 1.3}`: three concentric earthen ramparts with a moat, gate and hall (an original design, not a site plan); the moat spans 340 x 130 units around the centre.
- `bamboo_village`: `{"type": "bamboo_village", "x": 540, "y": 1095, "scale": 1.7}`: a village behind its bamboo hedge, with three thatched houses, a banyan and a gate; about 540 x 260 units.
- `furnace`: `{"type": "furnace", "x": 540, "y": 1095, "scale": 1.4}`: a clay-brick casting furnace with fire in its mouth and flames over its top, a warm halo around it; about 300 x 400 units. Pair it with `"particles": "embers"`.
- `plinth`: `{"type": "plinth", "x": 540, "y": 1095, "scale": 1.6}`: an empty stone plinth (four faint hoof marks) under a shaft of light with drifting dust; the beam starts 540 units above the floor and fades out upwards.

### Sources workflow

Every example lists `sources` and marks each factual slide with `"claim": true` and a `source` index. `validate` warns about a missing `sources` list and about a claim without a `source`; `render` prints a numbered `Sources:` block, ready to paste into a caption (a typed source reads `[2] (journal) ...`), and stores the same list in the report. Folk-record claims are worded as such ("theo thần tích", "theo truyền thuyết"). Never invent a fact, date, name or quote: where a citation is still needed, write a placeholder such as `[CẦN NGUỒN] ...` in `sources` and the owner supplies the document.

`gallery` renders a 1080x5880 contact sheet. The top block is every role x facing x prop (4 props across, 8 role x facing rows down, each cell labelled `role · facing · prop`) so the characters can be reviewed at a glance. Below it, eight rows of 270x360 cells show each scene layer type with the reference template's parameters (sun, moon, clouds, mountains, peaks gradient, peaks eggshell, hills left, river, ground, boat, birds, lotus, drum, gong, temple, map, scroll, elephant, stilt house, banners, regalia, fallen flags, sail boat, lone path, lanterns, tablet, horse, citadel, bamboo village, furnace, plinth); each is the layer drawn at full canvas scale, with a fixed 3:4 crop scaled into its cell (`gallery.LAYER_SPECS`). `--out` defaults to `output/gallery.png` relative to the current directory; parent directories are created and the PNG is written atomically. Figures use their role's default crest.

## Tests and snapshots

```bash
pytest -q                        # everything; E2E tests marked `ffmpeg` skip without FFmpeg
pytest --update-snapshots        # write the snapshot baselines for the installed library versions
pytest -m ffmpeg -q              # only the end-to-end tests that run FFmpeg
pytest --cov=history_shorts --cov-report=term-missing   # coverage (see Coverage)
```

Snapshot tests hash the first slide's PNG of both examples (`tests/test_compose_snapshot.py`). Baselines live in `tests/snapshots/baselines.json`, keyed by `pycairo=...;numpy=...;scipy=...;Pillow=...;cairo_c=...;freetype=...` (spec R-02; the bundled Cairo and FreeType C library versions are part of the key): a pixel is only reproducible for one set of library versions. On any other set the snapshot tests skip with "run pytest --update-snapshots". Use that flag only for an intentional visual change (or a deliberate version bump), say so in the change, and review the new PNGs by eye before committing `baselines.json`.

`tests/test_visual.py` also compares the first slide of each example with the approved references in `docs/reference/approved/`: the mean colour of each layout region (header, visual, title, subtitle, chrome) is converted to CIE Lab (D65) and the ΔE76 must stay at or below 8 (AC-03, AC-04). This is a coarse automated gate; owner sign-off on the preview PNGs is still required.

## Coverage

`pytest-cov` is a dev dependency (owner-approved 2026-11-08). It is not part of the default `pytest -q` run, which stays fast:

```bash
pytest --cov=history_shorts --cov-report=term-missing
```

Line coverage on 2026-11-08 (816 tests; NFR-08 requires at least 85 % for the first six rows):

| Group | Statements | Missed | Line coverage |
|---|---|---|---|
| config (`config`, `validation`, `scene_config`, `script_config`) | 769 | 9 | 98.8 % |
| text | 138 | 0 | 100 % |
| layout | 16 | 0 | 100 % |
| textures | 102 | 0 | 100 % |
| characters/* | 501 | 1 | 99.8 % |
| scene/* | 531 | 0 | 100 % |
| whole package | 3523 | 36 | 99 % |

The only module below 95 % is `__main__.py` (0 %, a five-line entry point that the tests reach through `cli.main`).

## Performance

NFR-01 and NFR-03, measured on 2026-11-08 with `/usr/bin/time -l` on an Apple M1 Pro (`sysctl -n machdep.cpu.brand_string`), 8 cores (8 physical), 16 GB RAM, macOS, FFmpeg 8.1, default `--jobs` (7). The 10-slide script repeats five `me_linh` and five `nu_tuong` slides (landscape and group scenes, two text-only slides, two `zoom_in` slides, 40 s of video); the single slide is the first `me_linh` slide.

| Measurement | Target | Result | Peak RSS |
|---|---|---|---|
| `render --preview`, 1 slide | 6 s | 1.7 s | 0.51 GB |
| `render` full video, 1 slide | 6 s | 4.3 s | 0.51 GB |
| `render --preview`, 10 slides | 60 s | 9.2 s | 0.77 GB |
| `render` full video, 10 slides | 120 s | 25.8 s | 0.75 GB |
| Peak RSS (NFR-03), 10 slides repeated from the examples (`render`, full video) | 1.5 GB | 0.54 GB | |
| Peak RSS (NFR-03), 10 slides with unique hand-written eggshell scenes (`render`, full video) | 1.5 GB | 0.55 GB | |

The unique-scene script has 7 layer-scene slides (8 eggshell peaks and 2 hills each, positions and heights varied per slide so no eggshell mask repeats) and 3 `landscape` template slides with distinct seeds; it is the worst case for the eggshell cache. Before the final fix wave the cache stored full-frame textures without a bound and that script peaked at 2.09 GB (NFR-03 not met); the cache now stores bounding-box crops only and keeps at most 32 entries (`compose.EGGSHELL_CACHE_MAX_ENTRIES`), and the output is byte-identical. The time rows were measured before that change and are unchanged by it (same work, byte-identical output); the repeated-slide Peak RSS was 0.76 GB before and is 0.54 GB now.

Living slides (M9), measured 2026-11-13 on the same machine with `examples/hai_ba_trung` (8 slides, 5 living, 30 s), M8 = commit 0d0411d with the same script at 2.1:

| Measurement | M8 | M9 | Peak RSS M8 / M9 |
|---|---|---|---|
| `render`, `--jobs 1` | 228 s | 206 s | |
| `render`, default `--jobs` | 123 s | 162 s | 1.31 GB / 1.78 GB |

AC-31 (≤ 3x) is met. NFR-03 (1.5 GB) is **not** met when a script has living slides: one living clip's FFmpeg graph peaks near 1.9 GB (a dozen full-frame planes at 2x), so a render with living slides encodes at most 2 clips at once (`video.LIVING_MAX_JOBS`). Scripts without living slides are unchanged.

Character and scene animation (M10), measured 2026-11-20 on the same machine with `examples/hai_ba_trung` (10 slides, 6 living, 37.7 s, `--jobs 2`), the same script at 2.2 against 2.3:

| Measurement | 2.2 (M9) | 2.3 (M10) | Peak RSS 2.2 / 2.3 |
|---|---|---|---|
| `render`, `--jobs 2` | 212 s | 260 s | 1.63 GB / 1.94 GB |

AC-38 (≤ 1.5x) is met at 1.23x. Characters are drawn frame by frame on demand, so memory does not grow with the clip length; the NFR-03 note above still applies to living renders.

All targets are met with wide margins. The targets name a 4-core laptop; this machine has 8 cores, and the parallel clip encode accounts for part of the 10-slide video time.

## Acceptance

Automated evidence for each acceptance criterion in the spec (section 13). AC-03 and AC-04 also have owner sign-off (2026-11-08) on the preview PNGs.

| AC | Evidence | Status |
|---|---|---|
| AC-01 | `tests/test_e2e.py::test_render_nu_tuong` | met |
| AC-02 | same test: ffprobe 1080x1920, 30 fps, h264, yuv420p, duration = sum of slides within 0.1 s | met |
| AC-03 | `tests/test_visual.py::test_first_slide_matches_reference_regions` (ΔE76 <= 8 per region); owner sign-off 2026-11-08 | met |
| AC-04 | same test for `me_linh`; owner sign-off 2026-11-08 | met |
| AC-05 | `tests/test_scene_terrain.py::test_no_crossing_peak_outlines`, `test_eggshell_peaks_contained`, `tests/test_compose.py::test_fill_mask_never_leaks` | met |
| AC-06 | `tests/test_formations.py` overlap tests (`test_reference_group_has_no_overlaps`, `test_head_overlap_reported`, `test_check_all_*`), `tests/test_visual.py::test_examples_have_no_overlap_or_other_errors` | met |
| AC-07 | `tests/test_figure.py::test_hand_centre_on_shaft`, `test_oar_grip_segment_drawn_in_front`, `tests/test_gallery.py` (every role x facing x prop) | met |
| AC-08 | `tests/test_text.py::test_liberation_has_every_vietnamese_glyph`, `tests/test_cli_validate.py::test_missing_theme_font_glyphs_are_listed` | met |
| AC-09 | `tests/test_chrome.py::test_palette_gold_drives_all_gold` | met |
| AC-10 | `tests/test_render_preview.py::test_preview_writes_pngs_and_never_spawns_ffmpeg` | met |
| AC-11 | `tests/test_cli_validate.py::test_validate_three_errors_exit_3`, `test_validate_missing_sources_only_warns`, `tests/test_config_script.py::test_three_errors_all_reported` | met |
| AC-12 | `tests/test_compose_snapshot.py::test_full_slides_byte_identical`, `tests/test_render_preview.py::test_two_renders_byte_identical` | met |
| AC-13 | `tests/test_e2e.py::test_music_matches_length_and_fades` | met |
| AC-14 | `tests/test_cli_render.py::test_without_ffmpeg_exit_4`, `tests/test_e2e.py::test_without_ffmpeg_on_path_exit_4` | met |
| AC-15 | the quality gates below and `tests/test_guards.py` (no network imports, no `shell=True`, only `cli.py` prints, no crackle) | met |
| AC-16 | `tests/test_audio.py::test_export_writes_one_txt_per_narrated_slide`, `test_export_sha_matches_file_bytes`, `test_export_second_run_is_byte_identical` | met (unit) |
| AC-17 | `tests/test_audio.py::test_timing_uses_required_length_and_frame_grid`, `test_explicit_duration_shorter_than_voice_is_an_error`; end to end on a 4-slide narrated script: video 11.366 s = sum of slides; `tests/test_ducking.py::test_mix_keeps_the_audio_for_the_whole_video` (audio as long as the video) | met (unit + manual end to end) |
| AC-18 | `tests/test_audio.py::test_stale_narration_names_every_stale_slide` | met (unit) |
| AC-19 | `tests/test_voice_mux.py::test_v2_mux_command_untouched_without_voices`, `test_no_voice_needs_the_old_mux_command` | met (unit) |
| AC-20 | `tests/test_ducking.py::test_voice_ducks_music_by_several_dB` (music drops about 3.7 dB under the voice, measured on FFmpeg output); integrated loudness −13.9 LUFS for target −14 (within ±1 LU) on the scratch render | met (ducking automated; loudness checked by hand) |
| AC-21 | `tests/test_guards.py::test_no_speech_imports`, `test_no_network_imports` | met |

Quality gates (all must pass): `ruff check . && ruff format --check . && mypy --strict history_shorts && pytest -q`, plus `pytest -m ffmpeg -q` for the end-to-end tests alone.

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
- Zoom (FR-84): `zoom_in` pre-scales the slide 4x before `zoompan`, because zoompan floors its crop origin to whole source pixels and 2x visibly judders (about 15 Hz); 4x is smooth.
- Formations (FR-47): `centre_pair` takes exactly 1, 2, 4 or 6 characters. An odd extra character (3 or 5) would stand in the centre in front of another character's head and always fail the FR-48 check, so it is a count error that points to `line` or `v_shape`.
- Video (FR-80..92): the video length is the sum of the slide durations, each already a whole number of frames, so the mux uses `-t` of that sum rounded to 3 decimals. FFmpeg is located before any slide is rendered (AC-14). The report's `ffmpeg` version is `major.minor`, or `dev` for builds without a release number.
- Variety (FR-49): a character `seed` draws bun, sash and hem-dot-spacing factors in [0.9, 1.1] (`variation_for`); without a seed all three are 1.0 and the figure is unchanged. Boxes keep the unvaried extents (the bun grows at most 0.3 unit), and varied hem dots outside 92 % of the hem half-width are dropped.
- Eggshell cache (FR-66): one cache per render run, keyed by mask crc32, cell, gap, seed, layer and mask shape.
- Coverage (NFR-08): `pytest-cov` is an owner-approved dev dependency (2026-11-08, spec C-03); coverage runs as a separate command and is not part of `pytest -q`.
- Planned for v2.1, not implemented: extra motions and extra poses (Appendix A.2 onward).
- Narration audio (v2.1, M7): history-shorts and the owner's separate sound project exchange files only. `export-narration` writes `<id>.txt` and a manifest with `text_sha256`; the sound project returns `audio_manifest.json` and voice files; `render --audio` fits slide timing to the voice, ducks music and normalises loudness. No TTS inside history-shorts (spec Appendix A.1, C-01, C-02).
- Voice pairing (2026-11-13): `audio-manifest` builds `audio_manifest.json` from `<id>.wav`/`<id>.flac` files, and a voice older than its `.txt` counts as stale (export keeps the mtime of unchanged files). The one-command pipeline is `tools/make_video.py`, outside the package, because history-shorts itself never starts the sound project (spec A.1.1, A.1.8).
- Draft voice (2026-11-13): while VoiceStudio is unavailable, `tools/say_voice.py` uses the offline macOS `say` voice Linh as a `--voice-cmd`, at 200 wpm so every `hai_ba_trung` slide stays under 14 s. Like the sound project, it lives in `tools/` and history-shorts never calls it (C-01, spec A.1.1).
- Narration timing: a voiced slide is `ceil_to_frame(lead_in + voice + tail)` long; an explicit `duration` wins only when it is at least that long (spec A.1.6).
- Narration ducking uses FFmpeg `sidechaincompress` with the theme's `audio.duck` values; loudness is one `loudnorm` pass to `audio.loudness_lufs` / `audio.true_peak_db` (spec A.1.7).
- Motions and cues (v2.1, M8, owner-approved 2026-11-12): transitions overlap the previous clip (clip k is encoded longer and joined with `xfade` at slide k+1's start), so slide starts, voice offsets and the total stay the same; the join re-encodes only when a transition is used. `tone` is a compose step after the frame (FR-21), so text, seal and tag keep their colours. `text_in` slides also write `NN_bg.png` and `NN_text.png`; their text no longer zooms with the scene. Sound effects are owner-supplied files mixed after ducking; a `music_cut` mutes music with 50 ms ramps. Pan motions hold the view at 110 %. A 2.0 script keeps the v2.0 motion list and error text (spec Appendix A.2).
- Living slides and sound (v2.2, M9, owner-approved 2026-11-13): sound effects may be synthesized in code (numpy/scipy, seeded per cue); downloading sound stays banned. A living slide is split into planes recovered exactly from the still pipeline (grain and tone are linear, so the first frame equals the preview). Ambient motion is applied to each layer's rendered pixels (bob, roll, sway, ripple, glow), not by redrawing, so drawers are unchanged; banners and character flags therefore do not wave yet. Planes of one depth share one `zoompan` on `yuva444p` (RGBA zoompan was about 10x slower, 4:2:0 smeared red and gold edges) at 2x prescale (half-pixel steps, slightly softer fine detail). The layer depth override is `plane`, because `lone_path` already has a `depth` field. Default planes: sky, clouds, birds, mountains, peaks far; hills, river, ground strip, buildings, boats, animals mid; figures and foreground objects near.
- Artwork files (v2.3, M11, owner-approved 2026-11-21): new scene objects are project JSON files (approach A), not SVG, because Claude authors them and textures and motion must be first-class; path strings use SVG `d` syntax, parsed in the project (no new dependency). Gradients may fade to transparent and be radial; all artwork motion is scaled by `living.artwork_motion`; textured parts never move (their texture would shimmer). The layer is part of 2.3, which was still unreleased.
- Character and scene animation (v2.3, M10, owner-approved 2026-11-20): moving scene layers are redrawn per loop phase (phase 0 is the still drawing). Characters are drawn through a kit rig (`KitRig`: joint per part, split robe and sleeves) only when a style carries a `Pose`; `--preview` and still slides keep the original paths, so snapshots do not change, and a living first frame matches within ΔE ≤ 2. A held prop translates with the hand without turning and never sinks below the feet. Kneeling squashes the skirt rather than drawing a new silhouette. A raised sleeve shows the kit's existing fist. A characters layer is one lazily drawn sprite; `on` is limited to boat layers. FR-48 runs over sampled poses. Example `me_linh` stays a 2.0 reference script.
- Example `hai_ba_trung` (2026-11-11): scenes use only the approved templates. `context` uses `landscape`; `fall` and `legacy` use `landscape` with `boats: []` (river only); `hook` uses `group` with the two leaders; `peak` and `outro` use the full `group`. `war` and `loss` have no fitting template yet and render chrome and text only. Long titles carry an explicit `\n` so no line ends on a lone word.
- `hai_ba_trung` split (2026-11-13): `loss` and `legacy` were each cut in two at a sentence break (new slides `loss_symbol`, a large drum, and `legacy_story`, the bamboo village) because the VoiceStudio voice read them in 14.6 s and 18.3 s, over the 14 s limit. The narration words are unchanged, only divided; each new slide keeps the source of the slide it came from.
- Example `vuong_trieu_nu` (2026-11-12): the owner's 60 s storyboard adapted to what v2.0/v2.1 can draw. Photos, the Đông Hồ painting, Ban Chiêu and Han figures, maps, counters, split screen and word-by-word text are dropped (C-06; split screen not built). Pans, tones, transitions and text fade-in come from M8. Each shot is one slide without a fixed `duration`, so timing follows the voice (A.1.6) or FR-83 until the voice exists; every slide has its own scene: `group`/`landscape` variants or explicit `layers` (close-up queen, row of generals, empty Han boats, ringed gold disc with birds as a bronze-drum nod, lotus pond), so no slide is text only.
- Example `sach_it_ke` (2026-11-14): the owner's 50 s "sách giáo khoa ít kể" storyboard, 17 slides at schema 2.2. Photos, the Đông Hồ painting, the torn-page effect, the counting number and the five-icon grid are drawn with existing layers instead (scroll, leader, regalia, banners, line of five generals, map). The opening was rewritten with the owner (2026-11-14) into one line ending on "do phụ nữ cầm quyền!", with a 400 ms pause before it and `gain_db` 4 on that voice. Four claims still carry `[CẦN BỔ SUNG NGUỒN]` placeholders. Rendered with music volume 0.1 and `--sfx-volume 0.2`.
