# history-shorts v2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the offline `history-shorts` CLI that turns `script.json` + `theme.json` into a 1080×1920 lacquer-style (*sơn mài*) MP4 matching the two approved reference images.

**Architecture:** One-way pipeline `config` → `scene.templates` (expand) → `compose` (Cairo shapes + numpy textures into a float32 RGB buffer, Pillow text last) → PNG → `video` (FFmpeg clips, concat, audio mux). Drawing modules receive frozen dataclasses and a `numpy.random.Generator`; only `cli.py` prints.

**Tech Stack:** Python ≥ 3.10, pycairo, numpy, scipy, Pillow, system ffmpeg/ffprobe ≥ 4.4; dev: pytest, ruff, mypy.

**Spec:** `docs/raw_requirement.md` (v2.0, amended in Task 0) and `CLAUDE.md`. Visual source of truth: `docs/reference/approved/*.png`; numbers come from `docs/reference/prototype/*.py` (copy numbers, never structure, never import from `docs/`).

## Global Constraints

- Runtime deps exactly: `pycairo`, `numpy`, `scipy`, `Pillow` + system `ffmpeg`/`ffprobe` (≥ 4.4). Dev: `pytest`, `ruff`, `mypy`. Anything else needs owner approval (C-03). Never MoviePy, OpenCV, scikit-image, cairosvg, browser renderers (C-04).
- No AI of any kind (C-01). No network modules in `history_shorts/`: `requests`, `httpx`, `urllib.request`, `http.client`, `socket` (C-02).
- No `shell=True`; FFmpeg commands are `list[str]` (NFR-09).
- No crackle, scratches, random dark strokes; finish = sheen ≤ 0.10 + grain ±2.5 % only (C-08).
- No colour literals in drawing code: colours from `theme.palette`, fonts/sizes from theme, geometry from named constants or the scene file (C-07). Darkest stroke colour is `palette.black`; never `#000`.
- Every RNG via `compose.rng_for(seed, slide_index, layer_index)` = `np.random.default_rng([seed, slide_index, layer_index])`; eggshell uses `compose.eggshell_rng` (Task 0 decision). No global `random`, no time seeds.
- Canvas 1080×1920; safe zone left 80, right 150, top 160, bottom 420; text centred on x = 505.
- Compositing: Cairo ARGB32 premultiplied BGRA → `[..., [2, 1, 0]] / 255`; `rgb + base * (1 - a)`.
- Exit codes: 0 ok, 1 internal, 2 usage, 3 validation, 4 FFmpeg missing/old, 5 FFmpeg failed, 130 interrupted.
- Python 3.10+ syntax, full type hints, `mypy --strict history_shorts` clean, `ruff check .` and `ruff format --check .` clean; `@dataclass(frozen=True, slots=True)` for config/specs; `pathlib.Path` everywhere; `logging` for diagnostics; only `cli.py` prints.
- Identifiers/logs/errors/docs in English; on-screen text Vietnamese.
- Never delete or overwrite files outside the temp dir and the `--out` path (plus `<out_dir>/slides/NN.png`, FR-90).
- **Gate** (run at the end of every task, all must pass): `ruff check . && ruff format --check . && mypy --strict history_shorts && pytest -q`.
- Branch per milestone from `develop`: `feature/m0-spec`, `feature/m1-foundation`, …; PR into `develop` at milestone end. M2, M3, M4 end with preview PNGs shown to the owner and **wait for sign-off** before the next milestone.

## Review Focus

1. **Paths with spaces, Vietnamese letters, and apostrophes** (`~/Video/Sử Việt/bà 'Trưng'/script.json`, also on Windows): render and FFmpeg concat must work. Concat list escaping is tested in Task 21; an E2E render from such a directory is in Task 22.
2. **Vietnamese typed in decomposed form (NFD, common when copying from macOS apps):** it must validate, pass the glyph check, and render the same as NFC. NFC normalisation is tested in Task 3.
3. **JSON saved with a UTF-8 BOM** (Windows Notepad): it must load. Tested in Task 2 for the theme and Task 3 for the script.
4. **A single unbreakable word wider than the text column even at the minimum size:** this must be a validation error naming the slide, the field and a suggestion, not a crash or an infinite loop. Tested in Task 5.
5. **Ctrl-C during the FFmpeg stage:** the temp dir is removed, no partial file is left at `--out`, and the exit code is 130. Tested in Task 22.

---

## File Structure

```
pyproject.toml               package metadata, version ranges (3.10-compatible), ruff/mypy/pytest config
constraints.txt              exact pins used for dev + snapshot baselines (Python 3.11+)
CHANGELOG.md                 one entry per milestone
history_shorts/
  __init__.py                __version__ = "2.0.0"
  __main__.py                calls cli.main()
  cli.py                     argparse sub-commands, exit-code mapping, console summary (only printer)
  errors.py                  Issue, Issues collector, exception classes with exit_code
  primitives.py              RGB, Point, Box, FloatImage, FloatMask type aliases and Box helpers
  config.py                  JSON → frozen dataclasses for Theme, Script, Slide, scenes, layers, CharacterSpec; slide_duration()
  checks.py                  cross-file checks: palette refs, glyphs, text fit, overlaps (used by validate + render)
  layout.py                  safe zone, regions, text anchors (named constants)
  canvas.py                  typed pycairo wrapper
  textures.py                noise, lacquer_ground, gold_leaf, eggshell, finish
  compose.py                 over, fill_mask, rng_for, eggshell_rng, render_slide (FR-21 order)
  chrome.py                  frame, waves, seal, tag pill, progress bar, footer
  text.py                    charset, glyph check, wrap, fit, plan_text, draw_text
  render.py                  render_slides(): orchestrates per-slide compose → PNG files
  output.py                  slugify, default_out_path, slides_dir
  gallery.py                 contact sheet (FR-04)
  scene/__init__.py          LAYER_DRAWERS registry, draw_layers()
  scene/sky.py               sun/moon, birds
  scene/clouds.py
  scene/terrain.py           mountains, peaks, hills, river, ground
  scene/boat.py
  scene/lotus.py
  scene/people.py            characters layer drawer
  scene/templates.py         group, landscape → ExpandedScene
  characters/__init__.py     ROLES presets, CharacterStyle, resolve_style()
  characters/parts.py        named proportion constants + part path functions
  characters/figure.py       DRAW_ORDER, draw_figure(), figure_boxes()
  characters/formations.py   centre_pair, line, v_shape → PlacedCharacter list
  ffmpeg.py                  discovery, version, command builders, run()
  video.py                   durations, temp dir, clips, concat, mux, atomic output
  report.py                  render report JSON + sources block
themes/son_mai/theme.json, themes/son_mai/fonts/{LiberationSerif-Bold.ttf, LiberationSerif-Italic.ttf, LICENSE}
examples/nu_tuong/script.json, examples/me_linh/script.json   (already drafted; owner reviews content)
tests/                       one test module per source module; tests/helpers/visual.py; tests/snapshots/baselines.json
```

---

## M0 — Spec amendments

### Task 0: Record the owner's decisions in the spec, CLAUDE.md, and README

**Files:**
- Modify: `docs/raw_requirement.md` (§6.2, §6.3, FR-44, FR-65/66, §8.2, §8.4, AC-07, §16, new Appendix A)
- Modify: `CLAUDE.md` (Determinism bullet, Commands)
- Modify: `README.md` (add "Decisions" and "Setup" sections)
- Create: `CHANGELOG.md`

**Interfaces:** Produces the contract later tasks implement. No code.

- [ ] **Step 1: Create branch.** `git checkout -b feature/m0-spec` and commit the pending files (`CLAUDE.md`, `docs/`, `examples/`, `.gitignore`) as `chore: add spec, references, prototype, example drafts`.
- [ ] **Step 2: §6.2 palette.** The 13 keys stay required. Add 14 optional keys. Each key falls back to a required key when absent:

| Optional key | son_mai value | Fallback | Used by |
|---|---|---|---|
| `robe_general_dk` | [70,14,10] | `vermilion_dk` | role `general` robe shadow |
| `robe_general_alt_dk` | [56,28,16] | `brown` | role `general_alt` |
| `robe_crew_dk` | [30,50,42] | `jade` | role `boat_crew` |
| `egg_tone` | [226,212,184] | `egg` | eggshell fragments |
| `egg_gap` | [58,30,20] | `brown` | eggshell gaps |
| `sheen` | [255,210,160] | `gold_lt` | finish sheen |
| `shadow` | [10,4,2] | `black` | title drop shadow |
| `deep_warm` | [70,20,12] | `deep` | landscape ground mid |
| `mountain_base` | [60,14,10] | `deep` | far mountains gradient end |
| `peak_base` | [44,11,8] | `deep` | gradient peaks bottom |
| `river_top` | [40,12,8] | `deep` | river band top |
| `hull_dk` | [40,20,12] | `black` | boat hull bottom |
| `leaf_dk` | [24,40,34] | `jade` | lotus leaf |
| `petal_tip` | [240,170,150] | `pink` | lotus petal tip |

- [ ] **Step 3: §6.2 textures.** `sheen` becomes `{x, y, r, strength}`, with default `{330, 760, 620, 0.10}` taken from prototype `lac.finish`.
- [ ] **Step 4: §6.3 layers.** Add optional texture overrides to these layers:
  - `sun`/`moon`: `tile`, `worn`.
  - `clouds`, `hills`, and `peaks` with `fill: eggshell`: `cell`, `gap`.
  - `characters`: `baseline` (default 1100).
  - Boat `crew` items keep the Character contract. Their `x`, `baseline` and `height` are canvas px; when omitted, they are computed from boat slots (Task 18).
- [ ] **Step 5: FR-44 / AC-07.** The oar must also pass through the hand. Its shaft becomes the line through the hand centre (17.3, −60.5) and the blade top (25, 0), drawn from y −78 to y 6. Draw a front shaft segment like the spear and the flag.
- [ ] **Step 6: Text and layout rules (§8.2, §8.4).**
  - **Title placement:** a one-line title has its top at y 1215. A two-line title has its tops at 1190 and 1190 + step, where step = round(size × 102 / 92).
  - **Subtitle placement:** top = last title line top + 128. Additional subtitle lines step by round(size × 56 / 46).
  - **Subtitle colour:** continue the title alternation. Two title lines (egg, gold_lt) give an `egg` subtitle; one line gives `gold_lt`.
  - **Safe zone (FR-26):** the check applies to text, seal, tag, and character head boxes. Robes and props may extend past it.
  - **Progress bar (off by default):** y 1540, height 4, x 80–930. Track `gold_dk` at alpha 0.4; fill `gold` for (i+1)/n.
  - **Footer (off by default):** `tag` font, `gold_dk`, centred at x 540, top y 1830.
- [ ] **Step 7: FR-65/66 and CLAUDE.md Determinism.** Eggshell RNG = `default_rng([seed, layer_index, mask_crc32])`, independent of slide index. Identical cloud/hill layers then look the same on every slide, and the cache in Task 25 gets hits. All other RNGs keep `[seed, slide_index, layer_index]`.
- [ ] **Step 8: §16 dependency note.** `pyproject.toml` declares ranges valid on Python 3.10 (`numpy>=1.26`, `scipy>=1.11`, `Pillow>=10.1`, `pycairo>=1.25`). `constraints.txt` pins the dev versions (pycairo 1.29.2, numpy 2.4.6, scipy 1.17.1, Pillow 13.0.0). Those pins need Python ≥ 3.11, so snapshot baselines exist only for pinned sets.
- [ ] **Step 9: Appendix A — v2.1 storyboard (planned, not in v2.0).** Record:
  - **Narration:** the owner runs VoiceStudio separately. history-shorts exports narration `.txt` per segment, using `[pause Nms]` markers and no custom emotion tags. It mixes the owner's voice files, ducks music under voice, and fits slide duration to voice length. C-01 and C-02 stay unchanged.
  - **Motions:** pan, pop-up name cards, colour-tone shift, split screen.
  - **Poses:** kneeling and riding an elephant.
- [ ] **Step 10: README.** Add a "Setup (macOS)" section. Record that Homebrew `freetype` 2.15.0 bottles link `/usr/lib/libhvf.dylib`, which is missing on macOS 15.0.1, and the fix: `brew reinstall --build-from-source freetype`. Add a "Decisions" section listing Steps 2–8 in one line each.
- [ ] **Step 11: Commit** `docs: amend spec v2.0 with owner decisions (palette extras, oar grip, text anchors, eggshell rng)`. Open a PR into `develop`.

---

## M1 — Foundation (exit: AC-08, AC-11)

### Task 1: Package scaffold, fonts, guard tests, `--version`

**Files:**
- Create: `pyproject.toml`, `constraints.txt`, `history_shorts/__init__.py`, `history_shorts/__main__.py`, `history_shorts/cli.py`, `history_shorts/errors.py`, `history_shorts/primitives.py`
- Create: `themes/son_mai/fonts/` (`LiberationSerif-Bold.ttf`, `LiberationSerif-Italic.ttf`, `LICENSE`)
- Test: `tests/test_cli_basic.py`, `tests/test_guards.py`, `tests/conftest.py`

**Interfaces:**
- Produces:
  - `history_shorts.__version__: str = "2.0.0"`.
  - `cli.main(argv: list[str] | None = None) -> int`.
  - `errors.Issue(file: str, path: str, message: str, severity: Literal["error","warning"])` with `.format() -> str`, which returns `f"{file} › {path}: {message}"`.
  - `errors.Issues` with `.error(file, path, msg)`, `.warning(...)`, `.errors`, `.warnings`, `.raise_if_errors()`.
  - Exceptions with `exit_code`: `HistoryShortsError` (1), `ValidationFailed(issues)` (3), `FfmpegMissing` (4), `FfmpegTooOld` (4), `FfmpegFailed(command, stderr_tail)` (5).
  - `primitives`: `RGB = tuple[int, int, int]`, `Point = tuple[float, float]`, `FloatImage = npt.NDArray[np.float32]`, `FloatMask = npt.NDArray[np.float32]`. `Box(x0, y0, x1, y1)` (frozen) with `.intersects(other) -> bool`, `.inside(other) -> bool`, `.width`, `.height`, `.union(other) -> Box`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cli_basic.py
def test_version_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "history-shorts 2.0.0"

def test_no_subcommand_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2

# tests/test_guards.py  (AST scan of every history_shorts/**/*.py)
FORBIDDEN = {"requests", "httpx", "urllib.request", "http.client", "socket"}
def test_no_network_imports(): ...          # no Import/ImportFrom of FORBIDDEN (or their parents' submodules)
def test_no_shell_true(): ...               # no Call with keyword shell=Constant(True)
def test_only_cli_prints(): ...             # no Name('print') calls outside cli.py
def test_box_intersects_and_inside():
    a, b = Box(0, 0, 10, 10), Box(9, 9, 20, 20)
    assert a.intersects(b) and not a.inside(b) and Box(1, 1, 2, 2).inside(a)
    assert not Box(0, 0, 10, 10).intersects(Box(10, 0, 20, 10))   # touching edges do not intersect
```

- [ ] **Step 2: Run** `pytest tests/test_cli_basic.py tests/test_guards.py -v`. Expected: FAIL (`ModuleNotFoundError: history_shorts`).
- [ ] **Step 3: Implement the scaffold.**
  - `pyproject.toml`: setuptools backend; `requires-python = ">=3.10"`; the ranges from Task 0 Step 8; `[project.optional-dependencies] dev = ["pytest", "ruff", "mypy"]`; `[project.scripts] history-shorts = "history_shorts.cli:main"`.
  - Ruff: `target-version = "py310"`, `line-length = 100`.
  - Mypy: `strict = true`, plus an override `module = ["scipy.*"]` with `ignore_missing_imports = true`.
  - Pytest markers: `ffmpeg`, `slow`.
  - `cli.main` uses argparse with sub-commands `render`, `validate`, `gallery` (stubs that return 1 for now) and `--version` (`action="version"`).
- [ ] **Step 4: Fonts.** Download `liberation-fonts-ttf-2.1.5.tar.gz` from `https://github.com/liberationfonts/liberation-fonts/releases` into the scratchpad. Copy only `LiberationSerif-Bold.ttf`, `LiberationSerif-Italic.ttf` and `LICENSE` into `themes/son_mai/fonts/`. Record the URL and the SHA-256 of each file in the README. Execute nothing from the archive.
- [ ] **Step 5: Run** `pip install -e ".[dev]" -c constraints.txt`, then the Gate. Expected: all PASS.
- [ ] **Step 6: Commit** `feat(m1): package scaffold, guards, --version, Liberation Serif fonts` on `feature/m1-foundation`.

### Task 2: Theme loading and validation

**Files:**
- Modify: `history_shorts/config.py` (create)
- Create: `themes/son_mai/theme.json` (spec §6.2 values plus the 14 optional palette keys from Task 0 and `sheen {x:330, y:760, r:620, strength:0.10}`)
- Test: `tests/test_config_theme.py`

**Interfaces:**
- Produces:
  - `Palette`: frozen, `__getitem__(key: str) -> RGB`, `.rgb01(key) -> tuple[float, float, float]`, `.keys()`. Fallbacks are applied at load.
  - `GoldLeafSpec(tile: int, worn: float)`, `EggshellSpec(cell: int, gap: float)`, `SheenSpec(x: float, y: float, r: float, strength: float)`.
  - `Textures(gold_leaf, eggshell, sheen, grain: float)`.
  - `Fonts(title: Path, subtitle: Path, tag: Path)`, `TypeScale(tag, title, title_min, subtitle, subtitle_min: int)`.
  - `SealSpec(lines: tuple[str, ...], x, y, size)`, `TagSpec(cx, y)`, `WavesSpec(y, rows)`, `FooterSpec(enabled: bool, text: str)`.
  - `Chrome(frame: bool, seal, tag, waves, progress_bar: bool, footer)`.
  - `Transition(fade_in, fade_out: float)`, `VideoSpec(fps: int, crf: int)`.
  - `Theme(schema_version, name, seed, palette, fonts, type_scale, textures, chrome, transition, video, path: Path)`.
  - `load_theme(path: Path) -> tuple[Theme, list[Issue]]`. It returns the warnings and raises `ValidationFailed` carrying all errors.
  - Constants `REQUIRED_PALETTE_KEYS` (13) and `PALETTE_FALLBACKS: dict[str, str]` (14).

- [ ] **Step 1: Write failing tests**

```python
DEFAULT = Path("themes/son_mai/theme.json")

def test_default_theme_values():
    theme, warnings = load_theme(DEFAULT)
    assert warnings == []
    assert theme.seed == 40 and theme.palette["gold"] == (212, 166, 76)
    assert theme.palette["egg_tone"] == (226, 212, 184)
    assert theme.type_scale.title == 92 and theme.type_scale.subtitle_min == 34
    assert theme.textures.gold_leaf == GoldLeafSpec(tile=34, worn=0.05)
    assert theme.textures.sheen == SheenSpec(330, 760, 620, 0.10)
    assert theme.chrome.seal.lines == ("SỬ", "VIỆT")
    assert theme.fonts.title.is_absolute() and theme.fonts.title.exists()

def test_optional_palette_key_falls_back(tmp_theme):       # fixture: copy of default theme dir with edits
    theme, _ = load_theme(tmp_theme(drop_palette=["egg_tone"]))
    assert theme.palette["egg_tone"] == theme.palette["egg"]

def test_all_errors_reported_with_paths(tmp_theme):
    with pytest.raises(ValidationFailed) as exc:
        load_theme(tmp_theme(drop_palette=["gold"], palette={"black": [300, 0, 0]}, fonts={"title": "fonts/Missing.ttf"}))
    msgs = [i.format() for i in exc.value.issues]
    assert "theme.json › palette.gold: required key missing" in msgs
    assert "theme.json › palette.black: each value must be an integer 0–255" in msgs
    assert any(m.startswith("theme.json › fonts.title: file not found: /") for m in msgs)  # absolute resolved path

def test_unknown_key_warns(tmp_theme):
    _, warnings = load_theme(tmp_theme(extra={"colour": 1}))
    assert [w.format() for w in warnings] == ["theme.json › colour: unknown key (ignored)"]

def test_utf8_bom_loads(tmp_theme):
    load_theme(tmp_theme(bom=True))

def test_invalid_json_reports_line_and_column(tmp_path):
    p = tmp_path / "theme.json"; p.write_text('{\n  "name": ,\n}', encoding="utf-8")
    with pytest.raises(ValidationFailed) as exc:
        load_theme(p)
    assert exc.value.issues[0].format() == "theme.json › (json): invalid JSON at line 2, column 11: Expecting value"
```

- [ ] **Step 2: Run** `pytest tests/test_config_theme.py -v`. Expected: FAIL (import error).
- [ ] **Step 3: Implement `load_theme`.**
  - Read with `encoding="utf-8-sig"`.
  - Use a small path-tracking validator (`_Ctx(file, issues)` with a `.at(key)` / `.idx(i)` path builder) so that every `Issue.path` reads `slides[2].scene.layers[4].x`.
  - Resolve font paths against `theme.json`'s parent.
  - Optional sections take the §6.2 defaults.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m1): theme loading and validation`.

### Task 3: Script, scene, layer, and character parsing

**Files:**
- Modify: `history_shorts/config.py`
- Test: `tests/test_config_script.py`, `tests/data/three_errors.json`

**Interfaces:**
- Consumes: `_Ctx` and `Issue` from Task 2.
- Produces (all frozen, slots):
  - **Character:** `CharacterSpec(role: str, facing: int | None, robe/robe_dk/trim/wrap: str | None, prop: Literal["flag","spear","oar","none"] | None, crest: bool | None, x/baseline/height: float | None, seed: int | None)`.
  - **Item records:** `CloudItem(x, y, scale, flip: int)`, `PeakItem(x, height, width)`, `BirdItem(x, y, scale)`.
  - **Layers:**
    - `SunLayer(kind: Literal["sun","moon"], x, y, r, rings: int, tile: int | None, worn: float | None)`
    - `CloudsLayer(items, outline: Literal["gold","gold_dk"], cell: int | None, gap: float | None)`
    - `MountainsLayer(y, amp)`
    - `PeaksLayer(y, items, fill: Literal["gradient","eggshell"], cell, gap)`
    - `HillsLayer(side: Literal["left","right"], base, top, cell, gap)`
    - `RiverLayer(y, height=290)`
    - `GroundLayer(y, height=52)`
    - `CharactersLayer(formation: Literal["centre_pair","line","v_shape"] | None, baseline=1100, items)`
    - `BoatLayer(x, y, scale, crew)`
    - `BirdsLayer(items)`
    - `LotusLayer(x, y, scale)`
    - `Layer = Union[...]` of all of the above.
  - **Scenes:** `LayerScene(layers: tuple[Layer, ...])`; `TemplateScene(template: Literal["group","landscape"], characters: tuple[CharacterSpec, ...] | None, boats: tuple[BoatLayer, ...] | None, sun: bool = True, moon: bool = True, seed: int | None = None)`.
  - **Slide and script:** `Slide(tag, title, subtitle, duration: float | None, scene: LayerScene | TemplateScene | None, motion: Literal["none","zoom_in"], claim: bool, source: int | None)`; `Script(schema_version, title, sources: tuple[str, ...], slides: tuple[Slide, ...], path: Path)`.
  - **Functions:** `load_script(path: Path) -> tuple[Script, list[Issue]]`; `slide_duration(slide: Slide, fps: int) -> float`.
  - **Constants:** `ROLE_NAMES = ("leader","general","general_alt","boat_crew")`; `LAYER_TYPES` maps type name → class.

- [ ] **Step 1: Write failing tests**

```python
def test_examples_load():
    s, _ = load_script(Path("examples/nu_tuong/script.json")); assert len(s.slides) == 5
    m, _ = load_script(Path("examples/me_linh/script.json")); assert len(m.slides) == 6
    assert isinstance(s.slides[0].scene, TemplateScene) and s.slides[0].scene.template == "group"

def test_three_errors_all_reported():                       # AC-11
    with pytest.raises(ValidationFailed) as exc:
        load_script(Path("tests/data/three_errors.json"))
    assert sorted(i.format() for i in exc.value.issues) == [
        "three_errors.json › slides[0].title: required",
        "three_errors.json › slides[1].duration: must be 0.5–15",
        "three_errors.json › slides[2].scene.layers[0].x: must be 0–1080",
    ]

def test_missing_sources_and_unsourced_claim_only_warn(tmp_script):
    _, w = load_script(tmp_script(sources=None, slides=[{"title": "A", "claim": True}]))
    assert {i.path for i in w} == {"sources", "slides[0].source"}

@pytest.mark.parametrize("field,value,msg", [
    ("tag", "X" * 29, "must be at most 28 characters"),
    ("title", "X" * 61, "must be at most 60 characters"),
    ("subtitle", "X" * 121, "must be at most 120 characters"),
    ("title", "Hai Bà 🔥", "emoji are not supported (U+1F525)"),
    ("source", 5, "index out of range (sources has 1 item)"),
])
def test_slide_field_errors(tmp_script, field, value, msg): ...

def test_nfd_text_normalised_to_nfc(tmp_script):           # Review Focus 2
    nfd = unicodedata.normalize("NFD", "Trưng Trắc")
    s, _ = load_script(tmp_script(slides=[{"title": nfd}]))
    assert s.slides[0].title == "Trưng Trắc"

def test_slide_count_bounds(tmp_script): ...                # 0 and 31 slides → "slides: must contain 1–30 slides"
def test_unknown_layer_type_lists_allowed(tmp_script): ...  # message ends with "allowed: sun, moon, clouds, mountains, peaks, hills, river, ground, characters, boat, birds, lotus"
def test_unknown_role(tmp_script): ...                      # "slides[0].scene.characters[0].role: must be one of leader, general, general_alt, boat_crew"
def test_total_duration_warning(tmp_script): ...            # 2 short slides → warning "total duration 5.0 s is outside 15–90 s"
def test_utf8_bom_script_loads(tmp_script): ...             # Review Focus 3

@pytest.mark.parametrize("title,subtitle,expected", [("Ab", "", 2.5), ("X" * 40, "Y" * 40, 6.0), ("X" * 30, "Y" * 10, 3.2)])
def test_auto_duration(title, subtitle, expected):          # FR-83, \n not counted, rounded to 1/fps
    assert slide_duration(make_slide(title, subtitle), fps=30) == pytest.approx(expected)
```

- [ ] **Step 2: Run** `pytest tests/test_config_script.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement the parsers.** NFC-normalise every text field before checks. Emoji detection by code point: U+1F000–U+1FAFF, U+2600–U+27BF, U+FE0F, U+200D. Coordinate ranges: x 0–1080 and y 0–1920 for layer coordinates; positive for `r`, `scale`, `height`, `width`; `rings` 0–2; `facing` ∈ {−1, 1}. `slide_duration` uses the explicit duration or `clamp(len(title+subtitle without "\n") × 0.08, 2.5, 6.0)`, then rounds to the nearest 1/fps.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m1): script/scene/layer/character parsing with path-tracked errors`.

### Task 4: Layout constants

**Files:**
- Create: `history_shorts/layout.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Produces:
  - `CANVAS_W = 1080`, `CANVAS_H = 1920`, `SAFE_ZONE = Box(80, 160, 930, 1500)`, `TEXT_CENTER_X = 505`, `TEXT_MAX_WIDTH = 850`.
  - `REGIONS: dict[str, Box]` with `header` (0,160,1080,290), `visual` (0,290,1080,1150), `title` (0,1170,1080,1400), `subtitle` (0,1400,1080,1500), `chrome` (0,1540,1080,1920).
  - Text anchors: `TITLE_TOP_ONE_LINE = 1215`, `TITLE_TOP_TWO_LINES = 1190`, `TITLE_STEP_RATIO = 102 / 92`, `SUBTITLE_GAP = 128`, `SUBTITLE_STEP_RATIO = 56 / 46`.

- [ ] **Step 1: Write failing test.** It asserts the exact values above, and that `REGIONS["title"].y1 == REGIONS["subtitle"].y0`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the constants.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m1): layout regions and text anchors`.

### Task 5: Text — charset, glyph check, wrap, fit, plan, draw

**Files:**
- Create: `history_shorts/text.py`
- Test: `tests/test_text.py`

**Interfaces:**
- Consumes: `Theme`, `Slide`, the layout constants, `Box`.
- Produces:
  - `VIETNAMESE_CHARSET: str` (146 characters: the 12 bases `aăâeêioôơuưy` × {no tone + 5 tones} + `đ`, in both cases, all NFC).
  - `missing_glyphs(font_path: Path, chars: str = VIETNAMESE_CHARSET) -> list[str]`.
  - `wrap(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]`.
  - `TextLine(text, x, y, size, color_key: str, font_key: Literal["title","subtitle"])`.
  - `TextPlan(lines: tuple[TextLine, ...], shrunk: bool, title_box: Box, subtitle_box: Box | None)`.
  - `plan_text(slide: Slide, theme: Theme) -> TextPlan`, which raises `TextFitError(field, suggestion)`.
  - `draw_text(img: Image.Image, plan: TextPlan, theme: Theme) -> None`.

- [ ] **Step 1: Write failing tests**

```python
BOLD = Path("themes/son_mai/fonts/LiberationSerif-Bold.ttf")

def test_charset_contents():
    assert len(VIETNAMESE_CHARSET) == 146
    for ch in "ĂÂĐÊÔƠƯăâđêôơưộẶỹỴ":
        assert ch in VIETNAMESE_CHARSET

def test_liberation_has_every_vietnamese_glyph():          # AC-08
    assert missing_glyphs(BOLD) == []
    assert missing_glyphs(BOLD.with_name("LiberationSerif-Italic.ttf")) == []

def test_missing_glyph_detected_against_notdef():
    assert missing_glyphs(BOLD, chars="a\U0010FFFD") == ["\U0010FFFD"]

def test_explicit_newline_respected_and_width_wrap(theme):
    font = ImageFont.truetype(str(BOLD), 92)
    assert wrap("Những nữ tướng\nbên Hai Bà Trưng", font, 850) == ["Những nữ tướng", "bên Hai Bà Trưng"]
    assert all(font.getlength(line) <= 850 for line in wrap("Hai Bà Trưng " * 4, font, 850))

def test_reference_layout_two_line_title(theme):           # matches scene1.py
    plan = plan_text(make_slide("Những nữ tướng\nbên Hai Bà Trưng", "Khi phụ nữ cầm quân giữ nước"), theme)
    t = [l for l in plan.lines if l.font_key == "title"]; s = [l for l in plan.lines if l.font_key == "subtitle"]
    assert [l.y for l in t] == [1190, 1292] and [l.color_key for l in t] == ["egg", "gold_lt"]
    assert s[0].y == 1420 and s[0].color_key == "egg" and not plan.shrunk

def test_reference_layout_one_line_title(theme):           # scene3.py anchors
    plan = plan_text(make_slide("Mê Linh, năm 40", "Nơi cuộc khởi nghĩa bắt đầu"), theme)
    assert [l.y for l in plan.lines] == [1215, 1343] and plan.lines[1].color_key == "gold_lt"

def test_long_title_shrinks_in_4px_steps(theme):
    plan = plan_text(make_slide("Khởi nghĩa Hai Bà Trưng\nđánh đuổi quân Đông Hán", ""), theme)
    sizes = {l.size for l in plan.lines}
    assert plan.shrunk and len(sizes) == 1 and (92 - sizes.pop()) % 4 == 0

def test_unbreakable_word_is_fit_error(theme):            # Review Focus 4
    with pytest.raises(TextFitError) as exc:
        plan_text(make_slide("Trưnggggggggggggggggggggggggggg", ""), theme)
    assert exc.value.field == "title" and "shorten" in exc.value.suggestion

def test_draw_text_only_touches_text_regions(theme):
    img = Image.new("RGB", (1080, 1920)); draw_text(img, plan_text(make_slide("Mê Linh", "x"), theme), theme)
    a = np.asarray(img); assert a[:1150].max() == 0 and a[1600:].max() == 0
```

- [ ] **Step 2: Run** `pytest tests/test_text.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - **Glyph check:** a character is missing when its rendered mask equals the mask of U+10FFFD (`.notdef`).
  - **Fitting:** try sizes from `type_scale.title` down to `title_min` in steps of 4. The title fits when it wraps to ≤ 2 lines within `TEXT_MAX_WIDTH`. The subtitle fits when it wraps to ≤ 2 lines and its bottom is ≤ `REGIONS["subtitle"].y1`.
  - **Shadow:** the title gets a 3 px offset shadow in palette `shadow`.
  - **Placement:** all lines are centred on `TEXT_CENTER_X`.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m1): text wrapping, fitting, glyph check, drawing`.

### Task 6: Canvas wrapper

**Files:**
- Create: `history_shorts/canvas.py`
- Test: `tests/test_canvas.py`

**Interfaces:**
- Produces: `Canvas(w: int = 1080, h: int = 1920)`. It sets line cap and join to round, like the prototype.
  - Chainable path methods returning `Self`: `M`, `L`, `C`, `Z`, `new_path()`, `ellipse(cx, cy, rx, ry)`, `rect(x, y, w, h)`.
  - Sources: `color(rgb: RGB, alpha: float = 1.0)`, `vgrad(y0, y1, stops: Sequence[tuple[float, RGB, float]])`, `rgrad(cx, cy, r, stops)`.
  - Painting: `fill(keep: bool = False)`, `stroke(width: float, keep: bool = False)`, `clip()`.
  - Transforms: `save()`, `restore()`, `translate`, `scale`, `rotate`.
  - Output: `to_premul() -> tuple[FloatImage, FloatMask]` (premultiplied RGB 0..1 via BGRA→RGB) and `mask() -> FloatMask`.

- [ ] **Step 1: Write failing tests**

```python
def test_premultiplied_bgra_to_rgb():
    cv = Canvas(8, 8); cv.color((212, 166, 76)).rect(0, 0, 8, 8).fill()
    rgb, a = cv.to_premul()
    assert np.allclose(rgb[4, 4], np.array([212, 166, 76]) / 255, atol=1 / 255) and a[4, 4] == 1

def test_half_alpha_is_premultiplied():
    cv = Canvas(8, 8); cv.color((212, 166, 76), 0.5).rect(0, 0, 8, 8).fill()
    rgb, a = cv.to_premul()
    assert np.allclose(rgb[4, 4], np.array([212, 166, 76]) / 255 * 0.5, atol=2 / 255) and a[4, 4] == pytest.approx(0.5, abs=0.01)

def test_mask_of_ellipse():
    cv = Canvas(100, 100); cv.color((255, 255, 255)).ellipse(50, 50, 30, 30).fill()
    m = cv.mask(); assert m[50, 50] == 1 and m[2, 2] == 0 and m.dtype == np.float32

def test_vgrad_endpoints():
    cv = Canvas(4, 100); cv.vgrad(0, 100, [(0, (255, 0, 0), 1), (1, (0, 0, 255), 1)]).rect(0, 0, 4, 100).fill()
    rgb, _ = cv.to_premul(); assert rgb[0, 0, 0] > 0.95 and rgb[99, 0, 2] > 0.95
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** on `cairo.ImageSurface(FORMAT_ARGB32)`. Read pixels with `np.ndarray(shape=(h, stride // 4, 4), dtype=np.uint8, buffer=surface.get_data())[:, :w]`, then `.astype(np.float32) / 255` and `[..., [2, 1, 0]]`.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m1): typed pycairo canvas wrapper`.

### Task 7: `validate` command and cross-file checks

**Files:**
- Create: `history_shorts/checks.py`
- Modify: `history_shorts/cli.py`
- Test: `tests/test_cli_validate.py`

**Interfaces:**
- Consumes: `load_theme`, `load_script`, `missing_glyphs`, `plan_text`.
- Produces: `checks.check_all(script: Script, theme: Theme) -> list[Issue]`, which covers:
  - glyphs for each theme font (`theme.json › fonts.title: missing glyphs: ơ, ư`);
  - text fit per slide (`script.json › slides[3].title: does not fit at 64 px; shorten to about N characters`);
  - shrink warnings;
  - palette references in character overrides.

  Overlap checks are appended in Task 14. Also produces the `cli validate` exit code 3 on errors, and the exit-1 runtime import check `_require_runtime()` with an install hint per OS.

- [ ] **Step 1: Write failing tests**

```python
def test_validate_examples_exit_0(capsys):
    assert main(["validate", "--script", "examples/me_linh/script.json"]) == 0
    assert "0 errors" in capsys.readouterr().out

def test_validate_three_errors_exit_3(capsys):            # AC-11
    assert main(["validate", "--script", "tests/data/three_errors.json"]) == 3
    out = capsys.readouterr().out
    assert out.count("three_errors.json ›") == 3 and "3 errors" in out

def test_missing_font_exit_3_names_path(tmp_theme, capsys):
    assert main(["validate", "--script", "examples/me_linh/script.json", "--theme", str(tmp_theme(fonts={"title": "fonts/X.ttf"}))]) == 3
    assert "fonts/X.ttf" in capsys.readouterr().out

def test_missing_pycairo_exit_1_with_hint(monkeypatch, capsys):
    monkeypatch.setattr("history_shorts.cli._import_module", raise_for("cairo"))
    assert main(["validate", "--script", "examples/me_linh/script.json"]) == 1
    assert "brew install cairo" in capsys.readouterr().out or sys.platform != "darwin"
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** The CLI maps `HistoryShortsError.exit_code`. It prints issues as `ERROR <formatted>` / `WARN <formatted>`, then `N errors, M warnings`. Install hints: macOS `brew install cairo pkg-config && pip install pycairo`, Ubuntu `sudo apt install libcairo2-dev && pip install pycairo`, Windows `pip install pycairo`.
- [ ] **Step 4: Run** the Gate. Expected: PASS. M1 exit criteria AC-08 and AC-11 are met.
- [ ] **Step 5: Commit** `feat(m1): validate command with cross-file checks`. Add a CHANGELOG `M1` entry and open a PR.

---

## M2 — Textures & chrome (exit: AC-09, AC-12 partial; owner sees previews)

### Task 8: Textures

**Files:**
- Create: `history_shorts/textures.py`
- Test: `tests/test_textures.py`

**Interfaces:**
- Consumes: `Palette`, `SheenSpec`, `FloatImage`, `FloatMask`.
- Produces:
  - `noise(h: int, w: int, sigma: float, rng: Generator) -> FloatMask`: zero mean, normalised so max |v| = 1.
  - `lacquer_ground(rng, palette, top: str = "black", mid: str = "deep", bottom: str = "black") -> FloatImage`.
  - `gold_leaf(rng, palette, tile: int, worn: float, under: str = "vermilion_dk") -> FloatImage`.
  - `eggshell(rng, mask: FloatMask, palette, cell: int, gap: float) -> FloatImage`: zero outside the mask bbox.
  - `finish(img: FloatImage, rng, palette, sheen: SheenSpec, grain: float) -> FloatImage`.
- Parameter values to copy exactly from `docs/reference/prototype/lac.py` lines 184–255:
  - **Ground:** `sin` profile `** 1.5` after `clip`; 30 % blend toward the bottom colour; noise at quarter resolution with σ 18 and ±10 %.
  - **Gold leaf:** tone uniform −0.09…+0.07 per tile; sheen `1 + 0.10·sin((x+y)/260)`; grain 0.04 at σ 0.8; seams `< 1.2` px at ×0.82; worn = `noise(H/2, W/2, 6) > 1 − worn·2.2` within `binary_dilation(seam, 3)`, blended `×0.35 + under×0.65`.
  - **Eggshell:** grid step `cell` plus jitter uniform(0, cell); `cKDTree.query(k=2)`; gap where `d2 − d1 < gap`; shade uniform −0.16…+0.02 around palette `egg_tone`; gaps in `egg_gap`.
  - **Finish:** `(clip(1 − d/r, 0, 1))² · strength · palette.sheen`, then `× (1 + grain · noise(σ 0.7))`.

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("fn", ["ground", "gold", "egg", "finish"])
def test_deterministic(fn, palette, cloud_mask): ...       # same default_rng([40, 0, 1]) twice → np.array_equal

def test_lacquer_ground_profile(palette):
    g = lacquer_ground(np.random.default_rng(1), palette)
    assert g.shape == (1920, 1080, 3) and g.dtype == np.float32 and not np.isnan(g).any()
    black, deep = np.array(palette.rgb01("black")), np.array(palette.rgb01("deep"))
    assert np.abs(g[0].mean(0) - black).max() < 0.03
    assert np.linalg.norm(g[960].mean(0) - deep) < np.linalg.norm(g[960].mean(0) - black)

def test_gold_leaf_seams_and_tone(palette):
    t = gold_leaf(np.random.default_rng(1), palette, tile=34, worn=0.05)
    gold = np.array(palette.rgb01("gold"))
    assert np.abs(t.mean((0, 1)) / gold - 1).max() < 0.12
    seam_rows = t[::34].mean(); body = t[17::34].mean()
    assert 0.75 < seam_rows / body < 0.90

def test_eggshell_contained_and_gap_ratio(palette, cloud_mask):   # FR-36
    e = eggshell(np.random.default_rng(1), cloud_mask, palette, cell=16, gap=1.0)
    ys, xs = np.nonzero(cloud_mask > 0.01)
    outside = np.ones(cloud_mask.shape, bool); outside[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = False
    assert e[outside].max() == 0
    gap = np.all(np.isclose(e, palette.rgb01("egg_gap"), atol=1e-6), axis=-1) & (cloud_mask > 0.99)
    assert 0.04 < gap.sum() / (cloud_mask > 0.99).sum() < 0.25

def test_finish_bounds(palette):
    base = np.full((1920, 1080, 3), 0.5, np.float32)
    out = finish(base, np.random.default_rng(1), palette, SheenSpec(330, 760, 620, 0.10), grain=0.025)
    far = out[1900, 1070] / 0.5
    assert np.all((far > 0.97) & (far < 1.03)) and out.max() <= 0.5 * 1.03 + 0.10 + 1e-6

def test_textures_module_has_no_crackle_or_global_rng():    # C-08, FR-65 guard
    src = Path("history_shorts/textures.py").read_text(encoding="utf-8")
    assert not re.search(r"crackle|scratch|crack", src, re.I)
    assert not re.search(r"np\.random\.(?!Generator\b|default_rng\b)", src) and "import random" not in src
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the five functions, using the prototype parameters listed above.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m2): lacquer, gold-leaf, eggshell textures and finish`.

### Task 9: Compose core and slide assembly

**Files:**
- Create: `history_shorts/compose.py`
- Test: `tests/test_compose.py`

**Interfaces:**
- Consumes: `Canvas`, the textures, `plan_text`/`draw_text`, `Theme`, `Slide`.
- Produces:
  - `over(base: FloatImage, cv: Canvas) -> FloatImage`.
  - `fill_mask(base, tex, mask) -> FloatImage`.
  - `rng_for(seed: int, slide_index: int, layer_index: int) -> Generator`.
  - `eggshell_rng(seed: int, layer_index: int, mask: FloatMask) -> Generator`: uses `zlib.crc32` of `(mask > 0.5).tobytes()`.
  - Layer-index constants: `GROUND_LAYER = 0` (scene layer k uses `k + 1`), `FINISH_LAYER = 999`.
  - `SLIDE_STEPS = ("ground", "scene", "waves", "finish", "frame", "seal", "tag", "title", "subtitle", "progress_bar", "footer")`.
  - `SceneStyle(ground: tuple[str, str, str], sheen: SheenSpec, seed: int)`.
  - `SlideContext(script, theme, slide_index, style: SceneStyle, draw_scene: Callable[[FloatImage, DrawContext], FloatImage] | None, debug_safe_zone: bool)`.
  - `DrawContext(theme, palette, seed, slide_index)` with `.rng(layer_index)`.
  - `render_slide(ctx: SlideContext) -> Image.Image`.

- [ ] **Step 1: Write failing tests**

```python
def test_over_uses_premultiplied_alpha():
    base = np.full((4, 4, 3), 0.5, np.float32); cv = Canvas(4, 4); cv.color((255, 0, 0), 0.5).rect(0, 0, 4, 4).fill()
    assert np.allclose(over(base, cv)[0, 0], [0.75, 0.25, 0.25], atol=2 / 255)

def test_fill_mask_never_leaks():
    base = np.random.default_rng(0).random((10, 10, 3), dtype=np.float32); tex = np.ones_like(base)
    mask = np.zeros((10, 10), np.float32); mask[2:5, 2:5] = 1
    out = fill_mask(base, tex, mask); assert np.array_equal(out[mask == 0], base[mask == 0])

def test_rng_for_is_deterministic_and_distinct():
    assert rng_for(40, 0, 1).random() == rng_for(40, 0, 1).random() != rng_for(40, 0, 2).random()

def test_eggshell_rng_ignores_slide_index_but_tracks_mask(): ...

def test_chrome_and_text_slide(theme, script_one_slide):
    img = render_slide(SlideContext(script_one_slide, theme, 0, default_style(theme), None, False))
    assert img.size == (1080, 1920) and img.mode == "RGB"

def test_steps_order_is_fr21():
    assert SLIDE_STEPS == ("ground", "scene", "waves", "finish", "frame", "seal", "tag", "title", "subtitle", "progress_bar", "footer")
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement `render_slide`.** Iterate `SLIDE_STEPS` and dispatch each step to its own function. The chrome steps call into `chrome.py` (Task 10). Until Task 10 lands, they may be temporary no-ops that the Task 10 tests replace. `default_style(theme)` returns `SceneStyle(("black", "deep", "black"), theme.textures.sheen, theme.seed)`. The image is converted with `Image.fromarray((clip(img, 0, 1) * 255).astype(np.uint8), "RGB")` before the Pillow steps. With `--debug-safe-zone`, `SAFE_ZONE` and the region outlines are drawn last, in palette `pink`.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m2): compositing core and FR-21 slide assembly`.

### Task 10: Chrome

**Files:**
- Create: `history_shorts/chrome.py`
- Modify: `history_shorts/compose.py` (wire the steps)
- Test: `tests/test_chrome.py`

**Interfaces:**
- Consumes: `Canvas`, `Theme`, `Image`.
- Produces:
  - `draw_frame(cv, palette)`: copy `lac.frame`. Gold rect inset 40, width 5. `gold_dk` inset 58, width 1.5. Corner scrolls at the 4 inner corners: `M(0,70) C(0,20 20,0 70,0)` width 2.5; `M(18,54) C(18,30 30,18 54,18)` width 1.5; dot r 6 at (30,30).
  - `draw_waves(cv, palette, spec: WavesSpec)`: rows spaced 46, step 104, odd rows offset by step/2, radii (46, 32, 18), alpha 0.9 − k·0.15, width 2.0, rows alternating `gold` / `gold_dk`.
  - `draw_seal(img, theme)`: rounded radius 10, border 3 `gold`, fill `vermilion`; inner inset 8, radius 6, 1 px `egg`; title font 36, lines at y + 14 + i·46.
  - `tag_box(text, theme) -> Box`: width = text width + 52, height = size + 26, centred at `tag.cx`, top at `tag.y`.
  - `draw_tag(img, text, theme)`: radius 30, border 2 `gold`, fill `vermilion`, text `gold_lt` at y + 10.
  - `seal_box(theme) -> Box`.
  - `draw_progress_bar(img, theme, index, count)` and `draw_footer(img, theme)`, both using the Task 0 Step 6 geometry.

- [ ] **Step 1: Write failing tests**

```python
def test_frame_lines(theme, chrome_slide):                  # chrome_slide: rendered PNG array for a text-only slide
    gold = np.array(theme.palette["gold"])
    assert np.abs(chrome_slide[960, 42].astype(int) - gold).max() < 30

def test_waves_only_in_chrome_band(theme, chrome_slide_no_text): ...   # gold-ish pixels exist in y 1550–1740, none in 1450–1549

def test_tag_box_reference_geometry(theme):
    box = tag_box("NĂM 40 SAU CÔNG NGUYÊN", theme)
    assert box.y0 == 180 and box.height == 60 and (box.x0 + box.x1) / 2 == pytest.approx(590)

def test_seal_box(theme): assert seal_box(theme) == Box(92, 160, 210, 278)

def test_palette_gold_drives_all_gold(theme_with_gold_green):           # AC-09
    a = render_array(theme); b = render_array(theme_with_gold_green)
    assert not np.array_equal(a[960, 42], b[960, 42]) and b[960, 42][1] > b[960, 42][0]

def test_progress_bar_off_by_default_on_when_enabled(theme, theme_progress): ...
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** and wire the functions into `render_slide`'s steps.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m2): frame, waves, seal, tag pill, progress bar, footer`.

### Task 11: `render --preview` for chrome + text slides

**Files:**
- Create: `history_shorts/render.py`, `history_shorts/output.py`
- Modify: `history_shorts/cli.py`
- Test: `tests/test_render_preview.py`

**Interfaces:**
- Consumes: `render_slide`, `load_*`, `check_all`.
- Produces:
  - `output.slugify(title: str) -> str`: NFD, strip combining marks, `đ→d`, lowercase, non-alnum runs → `-`.
  - `output.default_out_path(script) -> Path`, which is `output/<slug>.mp4`.
  - `output.slides_dir(out: Path) -> Path`, which is `out.parent / "slides"`.
  - `render.render_slides(script, theme, out: Path, *, debug_safe_zone: bool, expand: Callable | None) -> list[Path]`. It writes `NN.png` (two-digit, 1-based) and logs a warning for stale `NN.png` files beyond the slide count, without deleting them.
  - `cli render --preview`.

- [ ] **Step 1: Write failing tests**

```python
def test_slugify():
    assert slugify("Nữ tướng thời Hai Bà Trưng") == "nu-tuong-thoi-hai-ba-trung"
    assert slugify("Đền Nghè, Hải Phòng!") == "den-nghe-hai-phong"

def test_preview_writes_pngs_and_never_spawns_ffmpeg(tmp_path, monkeypatch):     # AC-10, FR-02
    monkeypatch.setattr(subprocess, "run", forbid); monkeypatch.setattr(subprocess, "Popen", forbid)
    out = tmp_path / "v.mp4"
    assert main(["render", "--script", "examples/me_linh/script.json", "--preview", "--out", str(out)]) == 0
    assert sorted(p.name for p in (tmp_path / "slides").iterdir()) == [f"{i:02d}.png" for i in range(1, 7)]
    assert not out.exists()

def test_two_renders_byte_identical(tmp_path):              # AC-12 (partial: chrome + text)
    a = render_once(tmp_path / "a"); b = render_once(tmp_path / "b")
    assert all(x.read_bytes() == y.read_bytes() for x, y in zip(a, b))
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Scenes are ignored until M4: `expand=None` renders chrome and text only.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Owner checkpoint.**
  1. Render both examples with `--preview`.
  2. Compare `slides/01.png` side by side with the approved references (chrome, frame, waves, seal, tag, text position and colours).
  3. Report the differences.
  4. Send the PNGs to the owner and **wait for sign-off**.
- [ ] **Step 6: Commit** `feat(m2): render --preview for chrome and text`. Add a CHANGELOG `M2` entry and open a PR.

---

## M3 — Characters (exit: AC-06, AC-07; owner sees gallery)

### Task 12: Roles and style resolution

**Files:**
- Create: `history_shorts/characters/__init__.py`
- Modify: `history_shorts/checks.py` (palette refs in overrides)
- Test: `tests/test_roles.py`

**Interfaces:**
- Consumes: `CharacterSpec`, `Palette`.
- Produces:
  - `RolePreset(robe: str, robe_dk: str, trim: str, wrap: str, crest: bool, prop: str)`. All colours are palette keys.
  - `ROLES: Mapping[str, RolePreset]`.
  - `CharacterStyle(robe: RGB, robe_dk: RGB, trim: RGB, wrap: RGB, trim_is_gold: bool, crest: bool, prop: str)`.
  - `resolve_style(spec: CharacterSpec, palette: Palette, roles: Mapping[str, RolePreset] = ROLES) -> CharacterStyle`.

- [ ] **Step 1: Write failing tests**

```python
def test_role_presets_match_prototype():
    assert ROLES["leader"] == RolePreset("vermilion", "vermilion_dk", "gold", "gold", True, "flag")
    assert ROLES["general"] == RolePreset("vermilion_dk", "robe_general_dk", "gold_dk", "vermilion", False, "spear")
    assert ROLES["general_alt"] == RolePreset("brown", "robe_general_alt_dk", "vermilion", "vermilion", False, "spear")
    assert ROLES["boat_crew"] == RolePreset("jade", "robe_crew_dk", "gold_dk", "vermilion", False, "oar")

def test_overrides_apply(palette):
    s = resolve_style(CharacterSpec(role="general", robe="jade", prop="flag", crest=True), palette)
    assert s.robe == palette["jade"] and s.prop == "flag" and s.crest

def test_new_role_is_data_only(palette):
    roles = {**ROLES, "scholar": RolePreset("egg", "brown", "gold_dk", "jade", False, "none")}
    assert resolve_style(CharacterSpec(role="scholar"), palette, roles).prop == "none"

def test_unknown_palette_override_is_validation_error(): ...   # checks: "slides[0].scene.characters[0].robe: unknown palette key 'teal'"
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m3): role presets and style resolution`.

### Task 13: Figure parts and drawing order

**Files:**
- Create: `history_shorts/characters/parts.py`, `history_shorts/characters/figure.py`
- Test: `tests/test_figure.py`

**Interfaces:**
- Consumes: `Canvas`, `CharacterStyle`, `Palette`.
- Produces:
  - In `parts.py`, named constants copied from `figures.py`: `HEAD_CENTER_Y = -88.5`, `SHOULDER_Y = -79`, `WAIST_Y = -55`, `HEM_HALF_WIDTH = 25`, `PROP_X = 17`, `HAND_CENTER = (17.3, -60.5)`, `SPEAR_TOP = -134`, `FLAG_TOP = -136`, `OAR_SHAFT = ((15.07, -78.0), (25.76, 6.0))`, `OAR_BLADE_TOP = (25.0, 0.0)`.
  - One function per part: `hair_back`, `prop_back`, `robe`, `belt`, `sleeves`, `prop_front`, `hand`, `neck`, `face`, `features`, `hair_front`, `bun`, `headwrap`, `crest`. Each has the signature `(cv: Canvas, style: CharacterStyle, palette: Palette) -> None`. Path coordinates are copied from `figures.py`.
  - `shaft_segment(prop: str) -> tuple[Point, Point] | None`.
  - `Placement(x: float, baseline: float, height: float, facing: int)`.
  - In `figure.py`: `DRAW_ORDER: tuple[str, ...]` and `draw_figure(cv, style, placement, palette) -> None`, which does `translate(x, baseline)` then `scale(facing·h/100, h/100)`.
- Drawing rules:
  - Never draw loose side-lock strokes.
  - The face stays minimal (FR-43).
  - Facial lines use `skin_line` at partial alpha.

- [ ] **Step 1: Write failing tests**

```python
def test_draw_order_is_fr41():
    assert DRAW_ORDER == ("hair_back", "prop_back", "robe", "belt", "sleeves", "prop_front", "hand",
                          "neck", "face", "features", "hair_front", "bun", "headwrap", "crest")

@pytest.mark.parametrize("prop", ["spear", "flag", "oar"])
def test_hand_centre_on_shaft(prop):                        # AC-07
    (x0, y0), (x1, y1) = shaft_segment(prop); hx, hy = HAND_CENTER
    dist = abs((y1 - y0) * hx - (x1 - x0) * hy + x1 * y0 - y1 * x0) / math.hypot(x1 - x0, y1 - y0)
    assert dist <= 0.5

@pytest.mark.parametrize("role", ["leader", "general", "general_alt", "boat_crew"])
@pytest.mark.parametrize("facing", [-1, 1])
@pytest.mark.parametrize("prop", ["flag", "spear", "oar", "none"])
@pytest.mark.parametrize("crest", [True, False])
def test_every_combination_renders(role, facing, prop, crest, palette):   # AC-07
    cv = Canvas(500, 760); style = resolve_style(CharacterSpec(role=role, prop=prop, crest=crest), palette)
    draw_figure(cv, style, Placement(250, 650, 400, facing), palette)   # flag reaches x 250±200, oar blade y 650+64
    a = cv.mask()
    assert a.sum() > 1000                                    # figure drawn
    assert a[:, :5].max() == 0 and a[:, -5:].max() == 0      # nothing clipped at the cell edges

def test_mirroring_is_exact(palette):
    style = resolve_style(CharacterSpec(role="leader"), palette)
    l, r = Canvas(1080, 1200), Canvas(1080, 1200)
    draw_figure(l, style, Placement(540, 1150, 565, -1), palette); draw_figure(r, style, Placement(540, 1150, 565, 1), palette)
    assert np.allclose(l.mask(), r.mask()[:, ::-1], atol=1 / 255)
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement the parts in the FR-41 order.**
  - **Splitting the prototype:** `figures._sleeves` contains both the front shaft and the hand; split it into `sleeves`, `prop_front` and `hand`. Split `_head` into `neck`, `face`, `features`, `hair_front`, `bun`, `headwrap` and `crest`.
  - **Oar:** `prop_back` draws the full shaft along `OAR_SHAFT` and the blade from `figures.py` lines 38–39 (blade unchanged). `prop_front` draws the oar segment from y −66 to y −55 so the hand grips it.
  - **Hem dots:** colour is `egg` unless trim is gold, in which case it is `vermilion`.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m3): figure parts, FR-41 drawing order, oar grip`.

### Task 14: Bounding boxes, formations, overlap checks

**Files:**
- Create: `history_shorts/characters/formations.py`
- Modify: `history_shorts/characters/figure.py` (`figure_boxes`), `history_shorts/checks.py` (FR-48)
- Test: `tests/test_formations.py`

**Interfaces:**
- Consumes: `Placement`, `CharacterSpec`, `tag_box`, `seal_box`, `TextPlan`.
- Produces:
  - `FigureBoxes(head: Box, body: Box, prop: Box | None)` in canvas px. Head runs from the crest or bun top to the chin. The prop box includes the flag tip or spear tip.
  - `figure_boxes(style, placement) -> FigureBoxes`. Box corners come from transforming each part's local extreme points (no rendering).
  - `PlacedCharacter(spec: CharacterSpec, placement: Placement)`.
  - `place(formation: str, specs: Sequence[CharacterSpec], baseline: float) -> list[PlacedCharacter]`. It returns the characters in draw order (back rows first). `facing` defaults outward: x < 540 → −1, otherwise +1, unless `spec.facing` is set.
  - `checks.check_overlaps(slide_index, placed: list[tuple[PlacedCharacter, CharacterStyle]], text: TextPlan, theme) -> list[Issue]`. A character's head box must not cross the safe zone. No head, body or prop box may intersect the seal box, the tag box, or a text box. No box of one character may intersect another character's head box.
- Formation tables (named constants):
  - **`centre_pair` slots**, in input order front, front, middle, middle, outer, outer: front (432, b+6, 565) and (648, b+6, 565); middle (285, b, 475) and (795, b, 475); outer (150, b−4, 420) and (930, b−4, 420). An odd last character is centred at x 540 in its tier.
  - **`line`:** n ≤ 7, evenly spaced from x 150 to 930, height 475, baseline b.
  - **`v_shape`:** centre (540, b+6, 565); each outward pair steps dx ±135, height ×0.88, baseline −4.

- [ ] **Step 1: Write failing tests**

```python
REF_ROLES = ["leader", "leader", "general_alt", "general_alt", "general", "general"]

def test_centre_pair_reference_positions():
    placed = place("centre_pair", [CharacterSpec(role=r) for r in REF_ROLES], baseline=1100)
    assert [(p.placement.x, p.placement.baseline, p.placement.height, p.placement.facing) for p in placed] == [
        (150, 1096, 420, -1), (930, 1096, 420, 1), (285, 1100, 475, -1),
        (795, 1100, 475, 1), (432, 1106, 565, -1), (648, 1106, 565, 1)]

def test_two_characters_take_front_slots(): ...
def test_line_and_v_shape_face_outward(): ...

def test_reference_group_has_no_overlaps(theme, palette):   # AC-06
    issues = check_overlaps(0, styled(place("centre_pair", REF_SPECS, 1100), palette),
                            plan_text(make_slide("Những nữ tướng\nbên Hai Bà Trưng", "Khi phụ nữ cầm quân giữ nước"), theme), theme)
    assert issues == []

def test_flag_over_seal_reported(theme, palette):
    spec = CharacterSpec(role="leader", x=150, baseline=1000, height=565, facing=-1)
    issues = check_overlaps(0, styled_explicit([spec], palette), empty_text_plan(), theme)
    assert issues and "overlaps seal" in issues[0].message and issues[0].path == "slides[0].scene.characters[0]"

def test_head_overlap_reported(): ...
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement**, then add `check_overlaps` to `check_all`. It runs after expansion in Task 20; for now it is called on `CharactersLayer` scenes only.
- [ ] **Step 4: Run** the Gate. Expected: PASS. M3 exit criteria AC-06 and AC-07 are met.
- [ ] **Step 5: Commit** `feat(m3): figure boxes, formations, FR-48 overlap checks`.

### Task 15: `gallery` command (characters part)

**Files:**
- Create: `history_shorts/gallery.py`
- Modify: `history_shorts/cli.py`
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: `draw_figure`, `resolve_style`, `lacquer_ground`, `draw_text`.
- Produces: `gallery.render_gallery(theme: Theme) -> Image.Image`. It is a grid of 4 roles × 2 facings × 4 props, one figure of 300 px per cell, on lacquer ground, each labelled `role/facing/prop` in the tag font, `gold_lt`. Layer-type rows are appended in Task 20. Also produces `cli gallery [--theme] [--out output/gallery.png]`.

- [ ] **Step 1: Write failing test.** `main(["gallery", "--out", str(tmp_path / "g.png")]) == 0`; the file exists, and its width is 1080.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Owner checkpoint.**
  1. Render the gallery plus a test slide with the reference `centre_pair` on a plain lacquer ground.
  2. Compare with the figures in `scene_group.png`: proportions, faces, hands on shafts, flags pointing outward.
  3. Report the differences, send the PNGs, and **wait for sign-off**.
- [ ] **Step 6: Commit** `feat(m3): gallery command`. Add a CHANGELOG `M3` entry and open a PR.

---

## M4 — Scenes & templates (exit: AC-03, AC-04, AC-05, AC-10; owner sign-off)

### Task 16: Layer registry, sky, clouds

**Files:**
- Create: `history_shorts/scene/__init__.py`, `history_shorts/scene/sky.py`, `history_shorts/scene/clouds.py`
- Test: `tests/test_scene_sky_clouds.py`

**Interfaces:**
- Consumes: `DrawContext`, `Canvas`, `fill_mask`, `over`, `gold_leaf`, `eggshell`, `eggshell_rng`.
- Produces:
  - `LayerDrawer = Callable[[FloatImage, Layer, DrawContext, int], FloatImage]`, where the last argument is the layer index.
  - `LAYER_DRAWERS: dict[type, LayerDrawer]`.
  - `draw_layers(img, layers, ctx) -> FloatImage`.
  - `sky.draw_sun(...)`: mask circle → `gold_leaf(tile = layer.tile or theme default, worn = layer.worn or theme default)`. Ring 1 is `gold_lt` at r, width 3 (sun) or 2.5 (moon). Ring 2 is `gold_dk` at r + 18, width 1.5.
  - `sky.draw_birds(...)`: bird path `M(-12,0) C(-8,-6 -3,-6 0,0) C(3,-6 8,-6 12,0)`, stroke 1.6/s, `gold`.
  - `clouds.cloud_path(cv, item)` and `clouds.draw_clouds(...)`: one mask for all items → eggshell → outline lines with the colour `layer.outline`. Paths and stroke widths come from `elements.cloud_path` and `elements.cloud_lines`.

- [ ] **Step 1: Write failing tests**

```python
def test_sun_texture_contained(ctx):                         # FR-36
    before = flat_base(); after = draw_sun(before.copy(), SunLayer("sun", 540, 650, 300, 2, None, None), ctx, 1)
    yy, xx = np.mgrid[:1920, :1080]; outside = (xx - 540) ** 2 + (yy - 650) ** 2 > (318 + 3) ** 2
    assert np.array_equal(after[outside], before[outside])

def test_clouds_texture_contained(ctx): ...                  # pixels > 4 px outside the cloud mask unchanged
def test_moon_single_ring(ctx): ...                          # no gold_dk ring pixels at r+18
def test_birds_drawn_at_positions(ctx): ...
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m4): layer registry, sun/moon, birds, eggshell clouds`.

### Task 17: Terrain layers

**Files:**
- Create: `history_shorts/scene/terrain.py`
- Test: `tests/test_scene_terrain.py`

**Interfaces:**
- Consumes: as in Task 16.
- Produces the drawers below. All path coefficients are copied from `elements.py`.
  - `draw_mountains`: fill `vgrad(y−100, y+200)` from `vermilion_dk` to `mountain_base`; ridge in `gold`, width 2.5.
  - `draw_peaks`: one path per peak, in list order, fill then outline (FR-35).
    - Gradient fill: top colour `vermilion_dk × (1 − i·0.06)` (constant `PEAK_SHADE_STEP = 0.06`), bottom `peak_base`, outline `gold` 1.8.
    - Eggshell fill: a mask per peak, outline `gold` 2.5.
  - `draw_hills`: `hill_left` / `hill_right` paths, eggshell, outline `gold` 2.5.
  - `draw_river`: `vgrad(y, y+height)` with stops `(0, river_top, 1)`, `(0.65, black, 0.9)`, `(1, black, 0)`, filled as a rect. A `gold` line at y, width 2. Wave strokes:
    - rows at y + 30·k for k in 0..5;
    - x starts at −60 + (k % 2)·45, step 90;
    - `M(x,y) C(x+15,y−8 x+35,y−8 x+50,y)`, width 1.6, alpha 0.75;
    - row colours alternate `gold` / `gold_dk`.
  - `draw_ground`: `elements.ground_band`.

- [ ] **Step 1: Write failing tests**

```python
BACK = [PeakItem(470, 380, 120), PeakItem(860, 360, 130), PeakItem(120, 330, 120),
        PeakItem(660, 290, 115), PeakItem(300, 250, 105), PeakItem(1030, 260, 100)]

def test_no_crossing_peak_outlines(ctx, palette):           # AC-05, FR-35
    img = draw_peaks(flat_base(), PeaksLayer(900, tuple(BACK), "gradient", None, None), ctx, 1)
    gold = np.array(palette.rgb01("gold"))
    for i, j in itertools.combinations(range(len(BACK)), 2):            # j drawn after i
        for (x, y) in outline_samples(BACK[i], 900):                     # points on peak i's outline
            if strictly_inside(BACK[j], 900, x, y, margin=3):
                assert np.abs(img[int(y), int(x)] - gold).max() > 0.15

def test_eggshell_peaks_contained(ctx): ...
def test_hills_contained(ctx): ...
def test_river_fades_to_transparent(ctx):
    base = flat_base(); out = draw_river(base.copy(), RiverLayer(940, 290), ctx, 1)
    assert np.allclose(out[1229], base[1229], atol=1 / 255)
def test_ground_gold_line(ctx, palette): ...
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m4): mountains, peaks, hills, river, ground`.

### Task 18: Boat, lotus, characters layer

**Files:**
- Create: `history_shorts/scene/boat.py`, `history_shorts/scene/lotus.py`, `history_shorts/scene/people.py`
- Test: `tests/test_scene_boat_people.py`

**Interfaces:**
- Consumes: `draw_figure`, `resolve_style`, `place`, `figure_boxes`.
- Produces:
  - `boat.CrewSlot(dx: float, dy: float, height: float)` in boat units; `BOAT_CREW_SLOTS = (CrewSlot(6.7, -5.3, 100), CrewSlot(-26.7, -4.0, 80))`.
  - `boat.crew_placements(layer: BoatLayer) -> list[PlacedCharacter]`. Explicit `x`/`baseline`/`height` win; otherwise use `x + dx·s`, `y + dy·s`, `height·s`. Facing defaults to +1.
  - `boat.draw_boat(...)`: crew first, then hull (`hull_dk` at the gradient end), copied from `elements.boat`.
  - `lotus.draw_lotus(...)`: copied from `elements.lotus`, using palette keys `leaf_dk` and `petal_tip`.
  - `people.draw_characters(...)` and `people.placed_characters(layer) -> list[PlacedCharacter]`. The latter is used by checks.

- [ ] **Step 1: Write failing tests:**
  - `test_crew_default_slots`: boat (290, 1056, 1.5) gives crew placements (300.05, 1048.05, 150) and (249.95, 1050.0, 120).
  - `test_hull_drawn_over_crew_feet`.
  - `test_lotus_renders_within_bbox`.
  - `test_characters_layer_uses_formation`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m4): boat with crew, lotus, characters layer`.

### Task 19: Templates

**Files:**
- Create: `history_shorts/scene/templates.py`
- Test: `tests/test_templates.py`

**Interfaces:**
- Consumes: the layer dataclasses, `SceneStyle`, `Theme`.
- Produces:
  - `ExpandedScene(layers: tuple[Layer, ...], style: SceneStyle)`.
  - `expand(scene: TemplateScene | LayerScene, theme: Theme) -> ExpandedScene`. A `LayerScene` gets `default_style(theme)`. A template's `seed` overrides `theme.seed` in the style.
- **`group` template:**
  - Layers, in order:
    1. `SunLayer("sun", 540, 650, 300, rings=2, tile=34, worn=0.05)`
    2. `CloudsLayer((CloudItem(270, 318, 0.8, 1), CloudItem(860, 318, 0.8, -1)), "gold", cell=12, gap=0.9)`
    3. `MountainsLayer(900, 1.0)`
    4. `HillsLayer("left", 1100, 880, 16, 1.0)`
    5. `HillsLayer("right", 1100, 900, 16, 1.0)`
    6. `GroundLayer(1092, 52)`
    7. `CharactersLayer("centre_pair", 1100, characters or REF_SIX)`
  - Style: ground `("black", "deep", "black")`, sheen `(360, 700, 640, 0.10)`.
  - `sun: false` drops layer 1.
- **`landscape` template:**
  - Layers, in order:
    1. `SunLayer("moon", 770, 450, 125, rings=1, tile=26, worn=0.03)`
    2. `BirdsLayer((300,400,1.6), (360,440,1.2), (250,470,1.0), (420,380,0.9))`
    3. `PeaksLayer(900, BACK, "gradient")`
    4. `CloudsLayer(((230,720,1.1,1), (640,650,0.9,-1), (960,760,0.8,1)), "gold_dk", cell=11, gap=1.0)`
    5. `PeaksLayer(945, ((80,200,140), (400,150,150), (990,220,160)), "eggshell", cell=15, gap=1.0)`
    6. `RiverLayer(940, 290)`
    7. The reference boats, crew placed explicitly so they match `scene3.py`: boat 1 `leader` (300, 1048, 150, +1) and `boat_crew` (250, 1050, 120, −1); boat 2 `general` (760, 1098, 125, +1) and `boat_crew` (815, 1100, 110, +1).
  - Style: ground `("black", "deep_warm", "black")`, sheen `(700, 520, 520, 0.08)`.
  - `moon: false` drops the moon. `boats: []` gives no boats. Boats given without crew coordinates use `BOAT_CREW_SLOTS`.

- [ ] **Step 1: Write failing tests**

```python
def test_group_reference_expansion(theme):
    ex = expand(TemplateScene("group", None, None), theme)
    assert [type(l).__name__ for l in ex.layers] == ["SunLayer", "CloudsLayer", "MountainsLayer", "HillsLayer", "HillsLayer", "GroundLayer", "CharactersLayer"]
    assert ex.layers[0] == SunLayer("sun", 540, 650, 300, 2, 34, 0.05)
    assert ex.style.sheen == SheenSpec(360, 700, 640, 0.10) and ex.style.ground == ("black", "deep", "black")

def test_landscape_reference_expansion(theme): ...          # layer types, moon tuple, BACK order, sheen (700,520,520,0.08), ground mid "deep_warm"
def test_template_params(theme): ...                        # sun=False, moon=False, boats=[], characters=2, seed=7 → style.seed == 7
def test_every_layer_type_has_a_drawer():
    assert set(LAYER_DRAWERS) == set(LAYER_TYPES.values())
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Use named constants for all reference geometry.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m4): group and landscape templates`.

### Task 20: Integration, snapshots, visual check, owner sign-off

**Files:**
- Modify: `history_shorts/render.py` (`expand` + `draw_layers` wired), `history_shorts/checks.py` (overlaps on expanded scenes), `history_shorts/gallery.py` (layer-type rows), `tests/conftest.py` (`--update-snapshots`)
- Create: `tests/helpers/visual.py`, `tests/test_visual.py`, `tests/test_compose_snapshot.py`, `tests/snapshots/baselines.json`
- Test: as listed

**Interfaces:**
- Produces:
  - `tests/helpers/visual.region_delta_e(img: np.ndarray, ref: np.ndarray, regions: dict[str, Box]) -> dict[str, float]`: mean colour per region, sRGB → CIE Lab (D65), ΔE76.
  - Snapshot baselines keyed by `f"pycairo={v};numpy={v};scipy={v};Pillow={v}"` → `{example: sha256}`. A missing key makes the test skip with "run pytest --update-snapshots".

- [ ] **Step 1: Write failing tests**

```python
@pytest.mark.parametrize("example,ref", [("nu_tuong", "scene_group.png"), ("me_linh", "scene_landscape.png")])
def test_first_slide_matches_reference_regions(example, ref, tmp_path):   # AC-03/AC-04 automated part
    img = render_first_slide(example, tmp_path)
    deltas = region_delta_e(img, load_ref(ref), REGIONS)
    assert max(deltas.values()) <= 8, deltas

def test_examples_have_no_overlaps(): ...                    # check_all(...) on both examples → no errors (AC-06 on templates)
def test_first_slide_snapshot(example, snapshot_db): ...     # SHA-256 equality or skip
def test_full_slides_byte_identical(tmp_path): ...           # AC-12 complete
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement the wiring.** `render_slides` passes `draw_scene = lambda img, ctx: draw_layers(img, expanded.layers, ctx)` and the style from `expand`. `validate` expands every slide's scene and runs `check_overlaps`. The gallery gets one row per layer type, each drawn at reduced scale on its own cell canvas.
- [ ] **Step 4: Run** `pytest --update-snapshots tests/test_compose_snapshot.py`. This writes the baseline once; say so in the report. Then run the Gate. Expected: PASS.
- [ ] **Step 5: Owner checkpoint.**
  1. Run `render --preview` for both examples.
  2. Open `slides/01.png` next to each approved reference.
  3. List every visible difference: composition, palette, line quality, eggshell density, gold-leaf tone, figure proportions, text.
  4. Include the ΔE table, and send the PNGs plus the gallery.
  5. **Wait for sign-off** (AC-03, AC-04).
- [ ] **Step 6: Commit** `feat(m4): scenes wired into render, visual and snapshot tests`. Add a CHANGELOG `M4` entry and open a PR.

---

## M5 — Video (exit: AC-01, AC-02, AC-13, AC-14)

### Task 21: FFmpeg discovery and command builders

**Files:**
- Create: `history_shorts/ffmpeg.py`
- Test: `tests/test_ffmpeg_commands.py`

**Interfaces:**
- Produces:
  - `parse_version(banner: str) -> tuple[int, int] | None`.
  - `FfmpegInfo(ffmpeg: Path, ffprobe: Path, version: tuple[int, int] | None)`.
  - `find_ffmpeg() -> FfmpegInfo`. It raises `FfmpegMissing` / `FfmpegTooOld` (< 4.4) with an install hint per OS: `brew install ffmpeg`, `sudo apt install ffmpeg`, or `winget install Gyan.FFmpeg`. A dev build (`None`) is accepted with a logged warning.
  - `clip_cmd(info, png: Path, out: Path, duration: float, fps: int, crf: int, fade_in: float, fade_out: float, motion: str = "none") -> list[str]`.
  - `concat_list_text(clips: list[Path]) -> str`.
  - `concat_cmd(info, list_file: Path, out: Path) -> list[str]`.
  - `mux_cmd(info, video: Path, out: Path, total: float, music: Path | None, volume: float) -> list[str]`.
  - `run(cmd: list[str], *, verbose: bool) -> None`. It raises `FfmpegFailed(cmd, last 20 stderr lines)`.

- [ ] **Step 1: Write failing tests**

```python
I = FfmpegInfo(Path("ffmpeg"), Path("ffprobe"), (8, 1))

@pytest.mark.parametrize("banner,v", [("ffmpeg version 8.1 Copyright", (8, 1)), ("ffmpeg version n4.4.2-0ubuntu", (4, 4)), ("ffmpeg version N-112233-gabc", None)])
def test_parse_version(banner, v): assert parse_version(banner) == v

def test_clip_cmd_exact():
    assert clip_cmd(I, Path("/t/01.png"), Path("/t/clip_01.mp4"), 4.0, 30, 20, 0.3, 0.3) == [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "30", "-t", "4.000",
        "-i", "/t/01.png", "-vf", "fade=t=in:st=0:d=0.300,fade=t=out:st=3.700:d=0.300,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", "-an", "/t/clip_01.mp4"]

def test_concat_list_escapes_quotes_and_uses_posix_paths():    # Review Focus 1
    assert concat_list_text([Path("/tmp/Sử Việt/bà 'Trưng'/clip_01.mp4")]) == "file '/tmp/Sử Việt/bà '\\''Trưng'\\''/clip_01.mp4'\n"

def test_mux_with_music_exact(): ...      # contains "-stream_loop","-1"; filter "[1:a]atrim=0:12.000,asetpts=N/SR/TB,volume=0.60,afade=t=in:st=0:d=0.5,afade=t=out:st=10.500:d=1.5,aresample=48000,aformat=channel_layouts=stereo[a]"; "-c:a","aac","-b:a","192k","-ar","48000","-ac","2","-t","12.000","-movflags","+faststart"
def test_mux_silent_uses_anullsrc(): ...  # "-f","lavfi","-i","anullsrc=r=48000:cl=stereo" (FR-86)
def test_missing_ffmpeg_raises_with_hint(monkeypatch): ...   # shutil.which → None → FfmpegMissing, exit_code 4
def test_run_failure_keeps_last_20_stderr_lines(): ...       # cmd = [sys.executable, "-c", "import sys; [print(i, file=sys.stderr) for i in range(30)]; sys.exit(1)"]
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Call `subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")` with no shell. Format durations with 3 decimals.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m5): ffmpeg discovery and command builders` on `feature/m5-video`.

### Task 22: Video assembly, report, `render` end to end

**Files:**
- Create: `history_shorts/video.py`, `history_shorts/report.py`
- Modify: `history_shorts/cli.py`
- Test: `tests/test_video.py`, `tests/test_report.py`, `tests/test_e2e.py`

**Interfaces:**
- Consumes: `ffmpeg.*`, `render_slides`, `slide_duration`, `check_all`.
- Produces:
  - `RenderOptions(out: Path, music: Path | None, music_volume: float = 0.6, keep_temp: bool, jobs: int, verbose: bool)`.
  - `video.assemble(info, slides: list[Path], durations: list[float], theme, opts) -> Path`. It creates a temp dir with `tempfile.mkdtemp(prefix="history-shorts-")`, writes `<out>.partial.mp4` next to `out`, then `os.replace`. On any exception, including `KeyboardInterrupt`, it removes the partial file and the temp dir (unless `keep_temp`) and re-raises.
  - `report.build_report(...) -> dict[str, object]` and `report.write_report(out: Path, data) -> Path`, which writes `<out stem>.report.json`.
  - `report.sources_block(script) -> str`, formatted as `Sources:\n[1] …\n[2] …`.
  - `cli render` (full) prints this summary: slide count, total duration, output path, elapsed time, sources block. `KeyboardInterrupt` → exit 130.

- [ ] **Step 1: Write failing tests**

```python
def test_interrupt_cleans_temp_and_partial(tmp_path, monkeypatch):        # Review Focus 5, NFR-05
    monkeypatch.setattr("history_shorts.ffmpeg.run", raise_keyboard_interrupt_on_call(2))
    with pytest.raises(KeyboardInterrupt):
        assemble(I, pngs(tmp_path), [3.0, 3.0], theme(), opts(out=tmp_path / "o.mp4"))
    assert not (tmp_path / "o.mp4").exists() and not (tmp_path / "o.mp4.partial.mp4").exists()
    assert not list(Path(tempfile.gettempdir()).glob("history-shorts-*"))  # isolate tempdir with monkeypatched TMPDIR

def test_report_contents(): ...      # keys: script_sha256, theme_sha256, music_sha256, slides[{index,duration,png}], total_duration, warnings, versions{python,pycairo,cairo,numpy,scipy,Pillow,ffmpeg}, timings, sources
def test_sources_block(): ...

@pytest.mark.ffmpeg
def test_render_nu_tuong(tmp_path):                                        # AC-01, AC-02
    out = tmp_path / "Sử Việt 'x'" / "nu tuong.mp4"
    assert main(["render", "--script", "examples/nu_tuong/script.json", "--out", str(out)]) == 0
    p = ffprobe(out)
    assert (p.width, p.height, p.codec, p.pix_fmt, p.fps) == (1080, 1920, "h264", "yuv420p", "30/1")
    assert p.duration == pytest.approx(sum(expected_durations("nu_tuong")), abs=0.1)

@pytest.mark.ffmpeg
def test_music_matches_length_and_fades(tmp_path):                         # AC-13
    music = make_sine(tmp_path / "m.m4a", seconds=7)                       # generated with ffmpeg lavfi sine, no bundled music
    ...  # audio duration == video duration ± 0.1; RMS of last 0.2 s < 0.2 × RMS of the middle second (decode to wav, read with `wave`)

def test_without_ffmpeg_exit_4(monkeypatch, capsys):                       # AC-14
    monkeypatch.setenv("PATH", "")
    assert main(["render", "--script", "examples/me_linh/script.json", "--out", "x.mp4"]) == 4
    assert "install" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Order: validate → render slides → find FFmpeg → clips (serial for now) → concat → mux → report.
  - FFmpeg is located *before* rendering slides, so AC-14 fails fast with exit 4.
  - With `--verbose`, log the full commands at DEBUG.
- [ ] **Step 4: Run** the Gate plus `pytest -m ffmpeg -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m5): video assembly, music, report, end-to-end render`. Add a CHANGELOG `M5` entry and open a PR.

---

## M6 — Polish (exit: all AC)

### Task 23: `--jobs` parallel clip encoding

**Files:**
- Modify: `history_shorts/video.py`, `history_shorts/cli.py`
- Test: `tests/test_video.py`

**Interfaces:** `default_jobs() -> int` returns `max(1, (os.cpu_count() or 2) - 1)`. Encode clips with a `ThreadPoolExecutor(max_workers=jobs)`. The concat order always follows slide order.

- [ ] **Step 1: Write failing tests.**
  - `test_default_jobs`.
  - `test_parallel_preserves_order`: a fake `run` sleeps in reverse order, and the concat list is still in slide order.
  - `test_jobs_1_is_serial`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** On failure, cancel the pending futures and still clean up.
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m6): parallel clip encoding (--jobs)` on `feature/m6-polish`.

### Task 24: `zoom_in` motion

**Files:**
- Modify: `history_shorts/ffmpeg.py`
- Test: `tests/test_ffmpeg_commands.py`

**Interfaces:** `clip_cmd(..., motion="zoom_in")` swaps the `-vf` value for: `scale=2160:3840,zoompan=z='min(1+0.06*on/{frames},1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={fps},fade=…,format=yuv420p`, with `frames = round(duration*fps)`.

- [ ] **Step 1: Write failing tests.**
  - `test_zoom_in_filter_exact`, for 4.0 s at 30 fps.
  - An ffmpeg-marked E2E test: a zoom slide still has the right duration and resolution.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS.
- [ ] **Step 5: Commit** `feat(m6): zoom_in motion via zoompan`.

### Task 25: Eggshell cache and character variety

**Files:**
- Modify: `history_shorts/compose.py` (cache), `history_shorts/characters/figure.py`, `history_shorts/characters/parts.py` (variation)
- Test: `tests/test_compose.py`, `tests/test_figure.py`

**Interfaces:**
- `compose.EggshellCache`: a dict keyed by `(mask_crc32, cell, gap, seed, layer_index)`, alive for one render run and passed in through `DrawContext.cache`.
- `parts.Variation(bun: float, sash: float, dot_spacing: float)` and `variation_for(seed: int | None) -> Variation`. `None` gives `Variation(1, 1, 1)` so the reference stays exact. Otherwise each factor is uniform in [0.9, 1.1] from `default_rng(seed)`.

- [ ] **Step 1: Write failing tests.**
  - `test_cache_hit_returns_identical_array_and_skips_compute`: count the `eggshell` calls via monkeypatch.
  - `test_variation_none_is_identity`.
  - `test_variation_bounds_and_determinism`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the Gate. Expected: PASS. Snapshots must not change, because the reference uses no seed.
- [ ] **Step 5: Commit** `feat(m6): eggshell cache (FR-66) and per-character variety (FR-49)`.

### Task 26: Final QA

**Files:**
- Modify: `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Performance.**
  - Time `render --preview` for a 10-slide script (duplicate `me_linh` slides in `tmp`): target ≤ 60 s.
  - Time one slide: target ≤ 6 s.
  - Time the full 10-slide video: target ≤ 120 s.
  - Measure peak RSS with `/usr/bin/time -l`: target ≤ 1.5 GB (NFR-01, NFR-03).
  - Record the numbers in the README.
- [ ] **Step 2: Coverage (NFR-08).** Measure ≥ 85 % lines on `config`, `text`, `layout`, `textures`, `characters`, `scene`. **This needs `pytest-cov` (or `coverage`), which is not in C-03: ask the owner before adding it.** If refused, report coverage as not measured.
- [ ] **Step 3: Acceptance checklist.** Walk through AC-01…AC-15 and list the test or evidence for each in the final report.
- [ ] **Step 4: README.** Setup per OS (with the freetype note), commands, data contracts summary, Decisions, font provenance, and the "Sources" workflow.
- [ ] **Step 5: Gate**, then commit `docs(m6): final QA, README, changelog`, and open a PR.

---

## v2.1 outline (storyboard format, separate plan after v2.0 ships)

These items are not tasks yet. Each needs a spec revision (data contract) and a separate plan.

- **M7 — Narration I/O:**
  - New `narration` command: `segments[].voice_text` → `narration/NN.txt`, written for natural delivery (short sentences, punctuation pacing, `[pause 500ms]`, no custom emotion tags).
  - `segments[].voice` audio path, mixed by FFmpeg: voice over music with ducking via `sidechaincompress`; slide duration = max(text auto-duration, voice length + 0.3 s).
  - VoiceStudio stays outside the tool (C-01/C-02 unchanged).
- **M8 — Motions:**
  - `pan` (crop window moving across a wider render);
  - pop-up name cards (text layer with scale/alpha keyframes rendered as frame sequence or FFmpeg overlay);
  - colour-tone shift (per-slide grade: desaturate + cool tint from theme);
  - split screen (two scenes side by side with a gold divider).
- **M9 — Poses:** `kneeling`, and `riding_elephant` (an elephant drawn as an original Bézier figure in the lacquer style).
- **Content:** every v2.1 example script keeps `sources`. Folk-record claims are worded "theo thần tích" / "theo truyền thuyết". The storyboard draft's claims (Lê Văn Hưu quote, tax relief, "hàng trăm làng") need citations before use.
