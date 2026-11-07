# CLAUDE.md

Working rules for Claude Code in this repository. Read this file and `docs/raw_requirement.md` (v2.0) before any change. Requirement IDs (C-xx, FR-xx, NFR-xx, AC-xx) refer to that document.

## Project in one paragraph

`history-shorts` is an offline Python CLI that turns a `script.json` and a `theme.json` into a 1080×1920 TikTok-style video about Vietnamese history, illustrated in the style of Vietnamese lacquer painting (*tranh sơn mài*). Shapes are drawn with **Cairo** (pycairo), textures are generated with **numpy/scipy**, text is set with **Pillow**, and slides are assembled with **FFmpeg**.

## Visual source of truth

- `docs/reference/approved/scene_group.png` → template `group`
- `docs/reference/approved/scene_landscape.png` → template `landscape`

Open both images before any visual work and compare your preview PNGs against them. The code in `docs/reference/prototype/` produced these images: copy its **numbers** (coordinates, proportions, colours, drawing order, texture parameters) faithfully, but **not its structure** (it uses ctypes Cairo bindings, module globals, no types, no tests). Never import from `docs/`.

`docs/reference/legacy/` is the retired v1 bronze style. Ignore it unless asked.

## Hard rules

1. **No AI**: no LLM, image generation, TTS, ASR, or ML model, local or remote. (C-01)
2. **No network at runtime**: never import `requests`, `httpx`, `urllib.request`, `http.client`, `socket` in `history_shorts/`. (C-02)
3. **Dependencies are fixed**: Python ≥ 3.10, `pycairo`, `numpy`, `scipy`, `Pillow`, system `ffmpeg`/`ffprobe`; dev: `pytest`, `ruff`, `mypy`. Ask before adding anything. Never add MoviePy, OpenCV, scikit-image, cairosvg, or a browser renderer. (C-03, C-04)
4. **No crackle, scratches, or random dark strokes.** Surface finish is sheen + fine grain only. The owner rejected crackle as "unnecessary black streaks". (C-08)
5. **No hardcoded style values** in drawing code: colours from `theme.palette`, fonts and sizes from the theme, geometry from named constants or the scene file. (C-07)
6. **Original artwork only**: no tracing of existing paintings, no realistic faces, no likenesses of real people, no bundled third-party images, textures, or music. (C-06)
7. **No `shell=True`**; FFmpeg commands are `list[str]`. (NFR-09)
8. **Never delete or overwrite files outside the temp dir and the `--out` path.**

## Commands

```bash
# setup
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# run
python -m history_shorts validate --script examples/nu_tuong/script.json
python -m history_shorts render   --script examples/nu_tuong/script.json --preview
python -m history_shorts render   --script examples/me_linh/script.json
python -m history_shorts gallery  --out output/gallery.png

# quality gates — all must pass before a task is done
ruff check . && ruff format --check .
mypy --strict history_shorts
pytest -q
pytest --update-snapshots      # only for intentional visual changes; say so in the report

# inspect a video
ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate -show_entries format=duration -of default=nw=1 output/<file>.mp4
```

## Architecture

```
config.py      JSON → frozen dataclasses (Script, Slide, Theme, Scene, CharacterSpec); all validation here
layout.py      safe zone + regions (header 160–290, visual 290–1150, title 1170–1400, subtitle 1400–1500, chrome 1540+)
canvas.py      thin typed wrapper over pycairo: new surface, path helpers (M/L/C/Z, ellipse, rect),
               fill/stroke, linear/radial gradients, save/restore/translate/scale/clip, to_premul(), mask()
textures.py    lacquer_ground, gold_leaf, eggshell, finish (sheen + grain) — pure numpy/scipy functions
compose.py     float32 RGB buffer; over() premultiplied compositing; fill_mask(); slide assembly in FR-21 order
chrome.py      frame + corner scrolls, waves; seal and tag pill (Pillow)
text.py        wrap by pixel width, auto-shrink, glyph check, title/subtitle drawing (Pillow)
scene/         layer registry + layers (sky, terrain, clouds, boat, lotus) + templates (group, landscape)
characters/    CharacterSpec, ROLES presets, parts, figure (drawing order), formations
ffmpeg.py      discovery, version check, command builders, run with stderr capture
video.py       clips, concat, music, atomic output
report.py      render report + sources block
cli.py         sub-commands, exit codes, summary output (only module that prints)
```

Data flows one way: `config` → `scene.templates` (expand) → `compose` → PNG → `video`. Drawing modules receive validated dataclasses and a `numpy.random.Generator`; they never read JSON or global state.

## Rendering rules

- **Compositing**: Cairo surfaces are ARGB32 premultiplied BGRA. Convert to RGB float (`[..., [2, 1, 0]] / 255`) and composite with `rgb + base * (1 - a)`. Never composite un-premultiplied values.
- **Masks**: textured regions = draw the shape white on a fresh surface → take alpha → `fill_mask(buffer, texture, mask)`. Textures must not appear outside the mask (FR-36).
- **Clip** with `cairo.clip()` for elements inside a shape (e.g. outlines inside an arch), never by post-cropping arrays.
- **Peaks**: one path per peak, back to front, fill then outline. Never build one combined polyline across overlapping peaks; it produces crossing outlines (FR-35).
- **Gradient bands** that end above the ground must fade to alpha 0, not stop at a hard edge (see the river in the landscape prototype).
- **Text last**: Pillow draws seal text, tag, title, subtitle after `finish()`, so sheen and grain never touch text.
- **Strokes**: darkest stroke colour is `palette.black`; never pure `#000`. Facial and finger lines use `skin_line` with partial alpha.
- **Determinism**: derive every RNG as `np.random.default_rng([theme.seed, slide_index, layer_index])`. No global `random`, no time-based seeds, no unordered set iteration in drawing.
  Exception: eggshell uses `np.random.default_rng([theme.seed, layer_index, mask_crc32])`, independent of slide index, so identical cloud/hill layers look the same on every slide and the cache gets hits.
- **Fonts**: Liberation Serif Bold (title, tag, seal) and Italic (subtitle), from `themes/son_mai/fonts/`. Run the Vietnamese glyph check in `validate`. Reject emoji.

## Characters

- Local frame: feet at (0,0), height 100 units, y up negative. Place with `translate(x, baseline)` then `scale(facing * h/100, h/100)`. Mirroring is only ever done with `scale(-1, 1)`; never mirror coordinates by hand.
- Drawing order (FR-41) matters for correctness: hair back → back prop shaft and head → robe → belt and sash → sleeves → **front prop shaft** → hand → neck → face → features → front hair → bun and hairpin → headwrap → crest. The front shaft makes the hand visibly grip the spear or flag.
- Keep proportions from `docs/reference/prototype/figures.py` as named constants in `characters/parts.py` (e.g. `HEAD_CENTER_Y = -88.5`, `SHOULDER_Y = -79`, `WAIST_Y = -55`, `HEM_HALF_WIDTH = 25`, `PROP_X = 17`).
- Faces stay minimal: ivory oval, faint pink cheeks, thin brows, downcast closed-eye arcs, a tiny nose line, small vermilion lips. Do not add pupils, eyelashes, ears, or shading.
- Do **not** draw loose side-lock strokes beside the face; they read as black streaks (removed after owner feedback).
- Roles are data (`ROLES` dict of presets); adding a role must not require editing `figure.py`.
- Formations compute positions only; they draw back rows first and set `facing` outward for characters left/right of centre.
- After placing characters, compute each character's bounding box (including flag and spear tip) and fail validation on overlap with the seal, tag pill, text regions, or another head (FR-48).

## Textures (copy parameters from the prototype)

- `lacquer_ground`: black → deep → black blend with a clipped `sin` profile (clip before raising to a power to avoid NaN), ±10 % low-frequency noise.
- `gold_leaf(tile, worn)`: per-tile tone jitter, diagonal sine sheen, grain, 1.2 px seams at 82 %, worn spots only near seams, `worn` default 0.05. Higher values look like dirt.
- `eggshell(cell, gap)`: jittered-grid points, `cKDTree.query(k=2)`, gap where `d2 - d1 < gap`; warm ivory fragments, warm dark-brown gaps (not black). Compute only inside the mask's bounding box; cache by (mask hash, params).
- `finish`: additive warm radial sheen ≤ 0.10, multiplicative grain ±2.5 %. Nothing else.

## Coding conventions

- Python 3.10+, full type hints, `mypy --strict` clean. `@dataclass(frozen=True, slots=True)` for config and specs.
- `pathlib.Path` everywhere; asset paths resolve relative to the referencing file.
- `logging` for diagnostics; only `cli.py` prints. Exceptions from `errors.py`, mapped to exit codes in `cli.py`.
- Functions ≤ ~50 lines where practical; separate geometry (pure) from drawing (Cairo calls) from I/O.
- Identifiers, logs, errors, docs: English. On-screen text: Vietnamese.

## Testing

- Unit tests for every validation rule and helper; texture tests assert determinism and mask containment.
- Parametrise character tests over role × facing × prop × crest (AC-07); assert the hand centre lies within 0.5 unit of the shaft.
- Overlap tests for formations and both templates (AC-05, AC-06).
- Snapshot tests: SHA-256 of first-slide PNGs for both examples, baselines keyed by pycairo/numpy/scipy/Pillow versions.
- Visual check helper: mean colour per layout region vs the approved references, ΔE ≤ 8 (AC-03, AC-04). Owner sign-off is still required.
- Guard tests: no network imports, no `shell=True`, no crackle/scratch function in `textures.py`.
- E2E tests run FFmpeg; mark `@pytest.mark.ffmpeg` and skip when unavailable. All test output under `tmp_path`.

## Workflow

1. State which FR/AC IDs the task covers before coding.
2. Follow milestones M1 → M6 (spec §14). Do not start the next milestone until the current one meets its exit criteria.
3. Small, focused changes; run ruff, mypy, pytest after each logical step.
4. For anything visual: render `--preview`, open the PNGs, compare side by side with the approved references, and list any visible differences in the report. End M2, M3, and M4 by showing preview PNGs to the owner.
5. If the spec is ambiguous, pick the simplest option that satisfies the acceptance criteria and matches the references, then log it under "Decisions" in `README.md`. Ask only if a choice would break a hard rule, change a data contract (§6), or change the approved look.
6. A change to a data contract or CLI flag updates the spec, README, examples, and tests in the same change.

## Definition of done

- [ ] Covered FR/AC IDs implemented and listed.
- [ ] `ruff check .`, `ruff format --check .`, `mypy --strict history_shorts`, `pytest -q` all pass.
- [ ] New behaviour has tests; snapshot updates are intentional and explained.
- [ ] Visual work compared against the approved references, differences reported.
- [ ] README and examples reflect user-visible changes.
- [ ] No hard rule violated.

End every task with a short report: what changed, requirement IDs, test results, visual comparison notes, and open issues.

## Historical content

- Example scripts include `sources`; factual slides use `"claim": true` and a `source` index.
- Do not invent historical facts, dates, names, or quotes. If content is needed, leave a clearly marked placeholder and tell the owner.
- Word folk-record claims as such ("theo thần tích", "theo truyền thuyết"). Do not present stylised costume as historically exact.

## Do not

- Do not add dependencies, crackle effects, or pure-black strokes.
- Do not download textures or music; ask the owner to supply them. Fonts may be downloaded at setup time (see Environment notes).
- Do not change the approved composition, palette, or proportions without owner approval.
- Do not draw realistic faces, nudity, gore, or combat violence; weapons are held at rest.
- Do not weaken tests or delete snapshots to make a build pass.
- Do not commit `output/`, `.venv/`, or caches.

## Environment notes

- The owner's work machine may restrict installs. If pycairo, scipy, or FFmpeg cannot be installed, stop and report the blocker with options (conda-forge packages, `pip install --user`, a portable FFmpeg build) instead of working around restrictions.
- On Windows, pycairo wheels are on PyPI; on macOS/Linux it may need the system Cairo library (`brew install cairo`, `apt install libcairo2-dev`). Document what worked in the README.
- Liberation Serif fonts are expected in `themes/son_mai/fonts/` with their licence; `validate` must name the exact missing file if absent.
- If the fonts are missing, download them yourself during setup (never at runtime, C-02), only from trusted sources: the official release at `github.com/liberationfonts/liberation-fonts/releases`, the Homebrew cask `font-liberation`, or the OS package (`apt install fonts-liberation`). Copy only the `.ttf` files and the OFL `LICENSE` into `themes/son_mai/fonts/`, record the source URL and SHA-256 in the README, and never execute anything from the download.
