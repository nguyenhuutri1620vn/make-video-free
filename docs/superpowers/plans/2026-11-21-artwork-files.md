# M11 Artwork Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New scene objects are JSON artwork files in `themes/son_mai/artwork/`, drawn by one `artwork` layer in the lacquer style, with declared motion, validation, preview and an authoring guide — no Python per object.

**Architecture:** A new `history_shorts/artwork/` package parses path strings and artwork files into frozen dataclasses (validated with the project's `Ctx`), and moves parts per loop phase. `scene/artwork.py` draws a parsed artwork with Cairo, using masks for gold leaf and eggshell. The layer joins the M10 phase-redraw machinery when a file declares motion. The CLI gains `artwork check` and `artwork preview`, and the gallery gains an artwork sheet.

**Tech Stack:** Python ≥ 3.10, pycairo, numpy, scipy, Pillow, stdlib `json`/`difflib`; pytest, ruff, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-11-21-artwork-files-design.md` (owner-approved 2026-11-21), with `CLAUDE.md` and `docs/raw_requirement.md` Appendix A.5 (M10).

## Global Constraints

- No new dependencies, no network, no `shell=True`, no crackle/scratch, no pure `#000` (CLAUDE.md hard rules).
- Colours only as palette keys inside artwork files; code holds no style values except named constants.
- `artwork` layers need `schema_version` `"2.3"`; a 2.2 script with one is a validation error.
- Artwork names match `[a-z0-9_]{1,40}`; files live only in `<theme dir>/artwork/<name>.json` (no paths in scripts).
- Limits: ≤ 300 parts, ≤ 20 000 path numbers per file, coordinates within ±2000 units, stroke width 0.2–20, alpha 0–1, gradient 2–6 stops with ascending offsets 0–1.
- Motion kinds `flicker` (`amp` units), `wave` (`amp` fraction, `pole` x), `sway` (`deg`, `pivot` [x, y]), `rise` (`amp` units), `pulse` (`amp` 0–0.5); each value × theme `living.artwork_motion` (default 1.0, range 0–3); phase 0 = still drawing; periodic.
- Textured parts (gold_leaf, eggshell), and parts clipped to one, may not move; a part clipped to a moving part may not be textured. Texture `tile`/`cell`/`gap` are artwork units.
- Determinism: textures use `ctx.rng(index)` / eggshell mask-crc RNG; motion phases from `ctx.rng(index + ARTWORK_MOTION_KEY)` where `ARTWORK_MOTION_KEY = 900`.
- Existing Python layers, snapshots and 2.2/2.3 renders without `artwork` stay unchanged.
- Tests run with `PYTHONPATH=<worktree> <repo>/.venv/bin/pytest`; gates: `ruff check . && ruff format --check . && mypy --strict history_shorts && pytest -q`. Commit per task; never push.

## Review Focus

1. **A file edited between `validate` and a render in the same process (preview loops)** — the cache must reload on mtime change, never draw a stale or half-written file. Test in Task 2.
2. **Name with path tricks** (`"../theme"`, `"Torch"`, `"torch.json"`) — rejected by the name pattern before any file access. Test in Task 3.
3. **`flip: -1` with motion and gradients** — mirrored artwork must move and shade like the unmirrored one (mirror only via `scale(-1, 1)`). Test in Task 4.
4. **Missing `artwork/` directory or empty library** — `artwork check` reports "no artwork" cleanly (exit 0 with a note), `validate` names the missing file. Test in Task 5.
5. **Very small or very large `scale`** (0.1, 5) — textures keep their unit size and strokes stay ≥ 0.2 px-ish visible; no crash on tiny masks. Test in Task 3.

---

### Task 1: Path-string parser

**Files:** Create `history_shorts/artwork/__init__.py`, `history_shorts/artwork/path.py`; Test `tests/test_artwork_path.py`.

**Interfaces:**
- Produces: `Op = tuple[str, tuple[float, ...]]` with kinds only `"M"` (x, y), `"L"` (x, y), `"C"` (x1, y1, x2, y2, x, y), `"Z"` (); `parse_path(d: str) -> tuple[Op, ...]` (absolute, H/V→L, S/Q/T→C, A→C); `class PathError(ValueError)` with `.position: int`; `path_bounds(ops) -> tuple[float, float, float, float]`; `trace(cv: Canvas, ops) -> None`; `count_numbers(d: str) -> int`.

- [ ] **Step 1: Failing tests** — one per command absolute and relative (`m l h v c s q t a z`): e.g. `parse_path("M 0 0 h 10 v 5 H 0 Z") == (("M",(0,0)),("L",(10,0)),("L",(10,5)),("L",(0,5)),("Z",()))`; implicit repeated pairs after `M` become `L`; `S` reflects the previous control point; `Q` converts to the exact cubic (control = P0 + 2/3(Q−P0)); `A` quarter circle `M 10 0 A 10 10 0 0 1 0 10` ends at (0,10) with every point on the circle within 0.05 (sample 9 Bézier points); exponents `1e1`, `-.5`, `3-4`; errors: `parse_path("M 0 0 X 1")` raises `PathError` with `position == 6`, missing numbers, path not starting with M; `path_bounds` of a curve includes control hull.
- [ ] **Step 2: Run** `pytest tests/test_artwork_path.py -v` — FAIL (module missing).
- [ ] **Step 3: Implement** with a regex tokenizer (`[MmLlHhVvCcSsQqTtAaZz]|[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?`) tracking token positions; arcs via the SVG endpoint-to-centre conversion split into ≤ 90° segments.
- [ ] **Step 4: Run** — PASS; gates.
- [ ] **Step 5: Commit** `feat(artwork): SVG path-string parser`

### Task 2: Artwork model, loader and library

**Files:** Create `history_shorts/artwork/model.py`, `history_shorts/artwork/load.py`; Modify `history_shorts/config.py` (`LivingSpec.artwork_motion: float = 1.0`, range (0, 3)); Test `tests/test_artwork_load.py`, data `tests/data/artwork/*.json` (small valid and invalid files).

**Interfaces:**
- Produces (all `@dataclass(frozen=True, slots=True)`):
  - `Solid(color: str, alpha: float = 1.0)`; `Gradient(stops: tuple[tuple[str, float, float], ...], direction: Literal["v","h"] | None, radial: tuple[float, float, float] | None)` — two-key `gradient` becomes stops `((k0,1,0),(k1,1,1))`; `Texture(kind: Literal["gold_leaf","eggshell"], tile: float | None, worn: float | None, cell: float | None, gap: float | None)`; `Fill = Solid | Gradient | Texture`
  - `Stroke(color: str, width: float, alpha: float = 1.0)`; `Motion(kind: Literal["flicker","wave","sway","rise","pulse"], amp: float = 0.0, deg: float = 0.0, pole: float = 0.0, pivot: tuple[float, float] = (0.0, 0.0))`
  - `Part(id: str, ops: tuple[Op, ...], fill: Fill | None, stroke: Stroke | None, alpha: float, clip: str | None, motion: Motion | None)` — `ellipse`/`rect` are converted to ops at load (rect `r` → rounded corners).
  - `Artwork(name: str, title: str, plane: Depth, parts: tuple[Part, ...])`, property `moves: bool`.
- `load_artwork(path: Path, palette: Palette) -> tuple[Artwork, list[Issue]]` raising `ValidationFailed` on errors (same style as `load_script`); issue file is `artwork/<name>.json`.
- `class ArtworkLibrary` with `__init__(directory: Path)`, `names() -> list[str]`, `path(name) -> Path`, `get(name: str, palette: Palette) -> Artwork` (cache keyed by `(path, st_mtime_ns, st_size)`); `library_for(theme: Theme) -> ArtworkLibrary` (`theme.path.parent / "artwork"`, one instance per directory).

- [ ] **Step 1: Failing tests** — valid file round-trip (parts, ops, fills, motion); each rule gives its message and JSON path: unknown palette key (lists none, says `unknown palette key 'xx'`), two geometries in one part, none, bad `d` (`parts[2].d: bad command 'X' at 6`), duplicate part id, `clip` to a later or unknown part, gradient stops not ascending / < 2 / > 6, alpha out of range, stroke width out of range, > 300 parts, > 20 000 numbers, coordinate beyond ±2000, unknown motion kind, `wave` without `pole`, `sway` without `pivot`, textured part with motion, part clipped to textured part with motion, textured part clipped to a moving part, `plane` not far/mid/near, `"artwork": "2"` unsupported; Review Focus 1: write file, `get` it, rewrite with a changed colour, `get` returns the new colour.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** with `read_json_object` + `Ctx` readers; geometry ops through Task 1; coordinate check over all op numbers.
- [ ] **Step 4: Run** — PASS; gates.
- [ ] **Step 5: Commit** `feat(artwork): file model, loader and library`

### Task 3: The `artwork` layer (still drawing)

**Files:** Modify `history_shorts/scene_config.py` (`ArtworkLayer(name: str, x: float, y: float, scale: float = 1.0, flip: int = 1)`, parser, `LAYER_TYPES["artwork"]`), `history_shorts/script_config.py` (gate `artwork` layer type below 2.3 inside `_check_version_keys`), `history_shorts/living/depth.py` (`DEFAULT_DEPTH[ArtworkLayer] = "mid"`; `scene_layers` passes the file's `plane` as the override when the layer has none); Create `history_shorts/scene/artwork.py` (registered in `scene/__init__.py`); Test `tests/test_artwork_layer.py`.

**Interfaces:**
- Consumes: `library_for`, `Artwork`, `Part`, `trace`.
- Produces: `draw_artwork(img, layer: ArtworkLayer, ctx: DrawContext, index: int) -> FloatImage`; `draw_parts(img, art: Artwork, layer: ArtworkLayer, ctx, index, parts: Sequence[Part]) -> FloatImage` (used by Task 4 with moved parts).

- [ ] **Step 1: Failing tests** (test library via a fixture copying `tests/data/artwork/` into a tmp theme dir):
```python
test_name_pattern_rejects_paths: "../theme", "Torch", "torch.json" → error at layers[0].name (Review Focus 2)
test_artwork_needs_23: same layer in a 2.2 script → 'requires schema_version "2.3"'
test_solid_square_pixels: a 100x100 unit solid gold_lt square at scale 1 colours exactly the expected box
test_gradient_alpha_fade: vertical stops gold_lt alpha 1 → 0: top row opaque, bottom row ≈ 0
test_radial_glow: centre alpha ≈ stop 0 alpha, edge ≈ 0
test_texture_inside_mask: gold_leaf part: no changed pixel outside its mask (AC-41); two renders identical
test_eggshell_deterministic: eggshell part renders identically twice; cache hit on the second
test_clip_to_part: a part clipped to a circle draws nothing outside it
test_flip_mirrors: flip -1 equals the horizontal mirror about x within anti-aliasing (Review Focus 3, still)
test_tiny_and_huge_scale: scale 0.1 and 5 render without error; texture tile in artwork units (Review Focus 5)
test_default_plane_from_file: file plane "near" → scene_layers gives near; layer plane override wins
```
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement**: `translate(x, y)`, `scale(flip*scale, scale)`; per part in order: clip (save → trace clip part → clip) → fill (Solid: colour; Gradient: bounds of the part for linear, `rgrad` for radial; Texture: draw the part white on a fresh canvas under the same transform → mask → `fill_mask` with `gold_leaf(rng, palette, tile_px, worn)` or `eggshell(ctx.eggshell_rng(index, mask), mask, palette, cell_px, gap)`, px = units × scale) → stroke → restore. Part alpha multiplies fill and stroke alpha.
- [ ] **Step 4: Run** — PASS; gates; snapshots unchanged.
- [ ] **Step 5: Commit** `feat(scene): artwork layer draws library files`

### Task 4: Artwork motion

**Files:** Create `history_shorts/artwork/motion.py`; Modify `history_shorts/scene/artwork.py` (`draw_artwork_at`), `history_shorts/scene/__init__.py` (`PHASE_DRAWERS[ArtworkLayer]`; `redraws(layer, theme: Theme | None = None)` true for an artwork whose file `moves`), `history_shorts/living/planes.py` (pass `ctx.theme` to `redraws`); Test `tests/test_artwork_motion.py`.

**Interfaces:**
- Produces: `move_part(part: Part, phase: float, rng_phases: np.ndarray, scale: float) -> Part` (returns a part with moved ops and, for `pulse`, scaled alpha); `motion_phases(ctx: DrawContext, index: int, count: int) -> np.ndarray` (shape `(count, 2, 3)` radians from `ctx.rng(index + ARTWORK_MOTION_KEY)`); `draw_artwork_at(img, layer, ctx, index, phase) -> FloatImage`.

- [ ] **Step 1: Failing tests** — for each kind on a test file: phase 0 equals `draw_artwork` exactly; phase 1 within 1/255 of phase 0; at phase 0.25 pixels change only inside the moving part's motion box; `flicker` keeps the part's lowest points fixed (weight 0 at the bottom, 1 at the top of the part bounds); `wave` keeps points at `pole` fixed (uses `history_shorts.cloth.wave_point`); `sway` keeps `pivot` fixed; `rise` moves points by a wave travelling up; `pulse` changes only alpha; `living.artwork_motion = 0` freezes all motion; `flip -1` moving artwork equals the mirror of the unflipped one at the same phase (Review Focus 3); a 2.3 living slide with a moving artwork gets a redraw sprite, a still artwork does not; 2.2 unchanged.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** offsets as `amp·Σ wₙ(sin(2πnp+φₙ) − sin φₙ)/Σw` (`w = (1, 0.5, 0.25)`), exactly zero at p = 0; values × `artwork_motion`.
- [ ] **Step 4: Run** — PASS; gates.
- [ ] **Step 5: Commit** `feat(artwork): declared motion redrawn on living slides`

### Task 5: Validation, CLI and gallery

**Files:** Modify `history_shorts/checks.py` (`_check_artwork`: every `ArtworkLayer` name exists in the library — else error listing up to 3 close names via `difflib.get_close_matches` — and loads cleanly, its issues reported with the artwork file name), `history_shorts/cli.py` (`artwork check [--name N] [--theme]`, `artwork preview --name N --out PNG [--phases 4] [--theme]`), `history_shorts/gallery.py` (`artwork_sheet(theme) -> Image.Image`; `gallery` also writes `<out stem>_artwork.png` when the library is not empty); Test `tests/test_artwork_cli.py` (`@pytest.mark.ffmpeg` not needed).

- [ ] **Step 1: Failing tests** — `validate` of a script naming `"torhc"` errors `unknown artwork 'torhc'; did you mean: torch`; a broken library file used by a script reports `artwork/bad.json › parts[0].fill.color: ...` and exit 2; `artwork check` exit 0 on the shipped library, 2 on a tmp library with a bad file, and prints "no artwork in <dir>" with exit 0 when the directory is missing or empty (Review Focus 4); `artwork preview` writes a PNG of width `phases × PREVIEW_CELL_W` (named constant, 540) showing the object on the lacquer ground; `gallery` writes the artwork sheet next to the main sheet.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** — preview cells: the slide's lacquer ground cropped to the object's bounds + margin, object drawn at scale fitting the cell, phases 0, 1/n, …; labels with Pillow in the gallery label font.
- [ ] **Step 4: Run** — PASS; gates.
- [ ] **Step 5: Commit** `feat(cli): artwork check, artwork preview and gallery sheet`

### Task 6: First library items, guide and docs

**Files:** Create `themes/son_mai/artwork/tablet_altar.json`, `themes/son_mai/artwork/torch.json`, `docs/artwork-guide.md`; Modify `docs/raw_requirement.md` (Appendix A.6 M11: format, layer, motion, commands, AC-39…AC-44; FR-51 note: artwork files replace SVG authoring for scene objects), `README.md` (user guide section + Decisions line for the three settled calls), `CHANGELOG.md`; Test `tests/test_artwork_library.py`.

- [ ] **Step 1: Failing tests** — `test_library_checks_clean`: every shipped file loads with no issues; `test_tablet_altar_matches_python_tablet` (AC-40): render `TabletLayer(540, 1150, 1.6)` and `ArtworkLayer("tablet_altar", 540, 1150, 1.6)` over the same lacquer ground; mean ΔE ≤ 3 over `REGIONS["visual"]` (use `helpers.visual.region_delta_e`); `test_torch_moves`: torch has motion and its phase-0.25 drawing differs only above the pole top.
- [ ] **Step 2: Run** — FAIL (files missing).
- [ ] **Step 3: Author** `tablet_altar.json` from the coordinates and palette keys in `scene/tablet.py` (altar, panel, pedestal, body, cloud crown, blank plaque, bowl, incense sticks, ember, smoke curves as strokes, candles, flames, radial glows); `torch.json` original: bamboo pole (gradient brown_lt→brown, gold_dk outline, three node rings), bound head (vermilion_dk wraps), flame (vermilion outer, gold inner, gold_lt core, each `flicker`), radial halo (`pulse`). Write `docs/artwork-guide.md` (units/origin, size table: person 100, altar 280 wide, building 300–500; layer order; palette usage; gradient vs gold leaf vs eggshell; outlines gold/gold_dk; motion recipes with example snippets; checklist: `artwork check`, `artwork preview`, compare with approved references, original artwork only, no text in objects).
- [ ] **Step 4: Run** — PASS; full suite; gates.
- [ ] **Step 5:** `artwork preview` both items and the Python tablet side by side; show the owner. Commit `content: first artwork files, authoring guide, spec A.6`.
