# Living Scenes and Synthesized Sound Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add synthesized sound effects (named cues + automatic whoosh) and "living" slides (parallax depth planes, ambient sprite loops, particles, hit shake) to history-shorts, without changing any existing render.

**Architecture:** Sounds are pure numpy/scipy functions written to WAV in the render temp dir and mixed by the existing sfx path. A living slide is decomposed into premultiplied RGBA planes (scene planes by depth, ambient sprite sequences, waves, an additive sheen plane, a chrome plane, an optional text plane) whose t = 0 recomposition equals the flat slide; FFmpeg moves each scene plane with its own eased `zoompan` and overlays them.

**Tech Stack:** Python 3.10+, pycairo, numpy, scipy, Pillow, stdlib `wave`, system FFmpeg. pytest/ruff/mypy --strict.

**Spec:** `docs/superpowers/specs/2026-11-13-living-scenes-sfx-design.md` (read it first, including "Settled after builder review"). Also `CLAUDE.md` and `docs/raw_requirement.md` Appendix A.2.

## Global Constraints

- No new dependencies; no network imports; no `shell=True`; FFmpeg commands are `list[str]` (C-01..C-04, NFR-09).
- No hardcoded style values in drawing/animation/synthesis code: numbers live in theme blocks (`living`, `sfx`) or named module constants (C-07).
- Determinism: RNG = `np.random.default_rng([theme.seed, slide_index, key...])`; same input → identical PNGs and WAVs.
- Scripts that use none of the new fields: byte-identical FFmpeg commands and unchanged snapshots (AC-19, AC-25, AC-30). Never run `pytest --update-snapshots` in this plan.
- New fields need `schema_version` `"2.2"`; `"2.0"`/`"2.1"` scripts behave exactly as today.
- Compositing is premultiplied: `rgb + base * (1 - a)`. Strokes never pure `#000`. No crackle.
- Files are written only under the render temp dir and the `--out` area (`slides/`).
- Quality gates after each task: `ruff check . && ruff format --check . && mypy --strict history_shorts && pytest -q`.
- Commit after each task on the current branch (`claude/video-sound-effects-animations-64fc86`, based on `feat/m7-narration`); never push.

## Deviation from the design (recorded here and in the spec, Task 10)

Ambient motion is applied to each animated layer's rendered RGBA (rigid bob/roll/sway, brightness flicker, periodic warp) instead of threading a `phase` through drawers. This leaves every drawer unchanged. Consequence: `banners` and character flags do not wave in M9 (their cloth cannot be separated from hills/bodies without drawer changes); this is listed as a follow-up. Animated set: `clouds` (drift), `birds` (drift + bob), `lanterns` (per-item bob, roll, glow flicker), `boat`/`sail_boat` (bob + roll), `river` (ripple warp), `lotus` (sway), `sun`/`moon` (glow pulse).

## Review Focus

1. A living slide followed by a transition: its clip is longer than the slide (overlap); motion progress, sprite loops and shake must use the extended clip length without freezing or jumping.
2. `"living": true` on a slide with no scene: the stack has only the ground plane; render must succeed (and still idle-drift nothing visible), not crash.
3. A layer whose `depth` override is lower than an earlier layer's: depth is raised, a warning names the layer, and the video stack order equals the preview order.
4. Parallel encoding (`--jobs N`) with several living slides: each slide's assets live in their own directory; no file collisions.
5. A bed sound (`wind`/`water`) whose `at + duration` exceeds the slide, or a `shake` cue on a non-living slide: validation error / warning respectively, never a silent truncation.

Each item has a test in the owning task (marked **RF-n**).

---

### Task 1: Script contract 2.2 (slide fields, sound cues, layer depth)

**Files:**
- Modify: `history_shorts/script_config.py` (versions, `SfxCue`, `Slide`, `_SLIDE_KEYS`, `_SFX_KEYS`, `_parse_sfx_cue`, `_parse_slide`)
- Modify: `history_shorts/scene_config.py` (`LayerScene`, `_parse_layer`, `_parse_layer_scene`)
- Modify: `history_shorts/cli.py:_check_cues` (probe only file cues)
- Modify: `history_shorts/cues.py` (`cue_problems`, `sfx_inputs` skip `path is None`)
- Test: `tests/test_config_script.py`

**Interfaces:**
- Produces (script_config):
  - `LIVING_SCHEMA_VERSION = "2.2"`; `SUPPORTED_SCHEMA_VERSIONS = ("2.0", "2.1", "2.2")`
  - `SOUND_NAMES = ("gong", "drum", "bell", "whoosh", "wind", "water")`, `BED_SOUNDS = ("wind", "water")`, `HIT_SOUNDS = ("gong", "drum")`, `PARTICLE_NAMES = ("none", "petals", "dust", "embers")`, `BED_SECONDS = (0.5, 14.0)`
  - `SfxCue(path: Path | None, at: float, gain_db: float = 0.0, sound: str | None = None, duration: float | None = None, shake: bool = False)` — exactly one of `path`/`sound` set.
  - `Slide` gains `living: bool = False`, `particles: str = "none"`, `auto_sfx: bool = True`.
- Produces (scene_config): `DEPTH_NAMES = ("far", "mid", "near")`; `Depth = Literal["far", "mid", "near"]`; `LayerScene(layers: tuple[Layer, ...], depths: tuple[Depth | None, ...] = ())` (empty or same length as `layers`).

- [ ] **Step 1: Write failing tests** in `tests/test_config_script.py` (use the file's existing script-building helpers):
  - `test_v22_accepts_living_fields`: 2.2 slide with `living: true, particles: "petals", auto_sfx: false` → `slide.living is True`, `slide.particles == "petals"`, `slide.auto_sfx is False`.
  - `test_v21_rejects_living_fields`: same keys under 2.1 → one error each whose message contains `requires schema_version "2.2"`.
  - `test_sound_cue_parsed`: `{"sound": "gong", "at": 0.4, "gain_db": -6, "shake": true}` → `SfxCue(path=None, at=0.4, gain_db=-6.0, sound="gong", duration=None, shake=True)`.
  - `test_cue_needs_exactly_one_source`: both `file` and `sound` → error "give either 'file' or 'sound'"; neither → same error.
  - `test_unknown_sound_lists_allowed`: `sound: "trumpet"` → error containing `gong, drum, bell, whoosh, wind, water`.
  - `test_bed_needs_duration` / `test_hit_rejects_duration`: `wind` without `duration` → error; `gong` with `duration` → error; `wind` with `duration: 20` → range error (0.5–14).
  - `test_shake_only_on_hits`: `bell` with `shake: true` → error.
  - `test_sound_cue_requires_v22`: `sound` key in 2.1 → error `requires schema_version "2.2"`.
  - `test_layer_depth_override`: 2.2 layers scene with `{"type": "clouds", ..., "depth": "near"}` → `scene.depths == ("near",)`; a layer without `depth` → `None`; `depth` in a 2.1 script → error; `depth: "deep"` → error listing `far, mid, near`.
  - `test_v21_script_unchanged`: existing 2.1 example parses to the same `Slide` values as before (compare against defaults: `living False`, `auto_sfx True`, `particles "none"`).
- [ ] **Step 2:** Run `pytest tests/test_config_script.py -q` → new tests FAIL.
- [ ] **Step 3: Implement.** Gate new keys with a version level: replace the `narrated: bool` threading by a helper `_at_least(version: str, wanted: str) -> bool` (tuple compare of `major.minor`) where needed; keep 2.1 error messages unchanged. `depth` is read in `_parse_layer` before the class keys check (add `"depth"` to the allowed key set, return it alongside the layer) and the 2.2 gate is checked in `_parse_slide` (scene parser does not know the version: return depths and let `_parse_slide` error at `scene.layers[i].depth`). In `cli._check_cues` build `has_audio` only if any cue has a `path`; `cue_problems` skips the audio probe for `path is None` and adds the bed rule: `at + duration > slide seconds` → error at `slides[i].sfx[j].duration` (**RF-5**).
- [ ] **Step 4:** Add test `test_bed_past_slide_end_is_error` (RF-5) in `tests/test_config_script.py` calling `cues.cue_problems` with durations `[3.0]` and a `wind` cue `at 2.0, duration 2.0` → one error naming `.duration`. Run the file → PASS. Run full gates.
- [ ] **Step 5: Commit** `feat(script): schema 2.2 with living, particles, sound cues and layer depth`

### Task 2: Theme blocks `living` and `sfx`

**Files:**
- Modify: `history_shorts/config.py` (dataclasses, `_THEME_KEYS`, parsers, `Theme`)
- Modify: `themes/son_mai/theme.json` only if a test fixture requires explicit values (defaults should suffice — prefer not to touch it)
- Test: `tests/test_config_theme.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True, slots=True)
  class LivingSpec:
      travel_px: Mapping[str, float]      # {"far": 30, "mid": 60, "near": 90}
      zoom_factor: Mapping[str, float]    # {"far": 0.35, "mid": 0.7, "near": 1.0}
      idle_drift: float = 0.15            # fraction of travel for motion "none"
      prescale: int = 2
      loop_seconds: float = 2.0
      shake_px: float = 6.0
      shake_seconds: float = 0.4
      cloud_drift_px_s: float = 6.0
      bird_drift_px_s: float = 18.0
      bob_px: float = 5.0
      roll_deg: float = 1.2
      sway_deg: float = 1.0
      ripple_px: float = 2.0
      flicker: float = 0.06
      glow_pulse: float = 0.03
      particle_count: int = 14
      particle_colors: Mapping[str, str]  # {"petals": "pink", "dust": "gold", "embers": "vermilion"} — palette keys; verify they exist in son_mai palette, otherwise pick the closest existing keys and note it
  @dataclass(frozen=True, slots=True)
  class SfxSpec:
      sample_rate: int = 48000
      auto_whoosh_db: float = -14.0
      reverb_wet: float = 0.25
      reverb_seconds: float = 2.2
      jitter: float = 0.03
  ```
  `Theme.living: LivingSpec = field(default_factory=...)`, `Theme.sfx: SfxSpec = field(default_factory=SfxSpec)`. Mappings wrapped in `MappingProxyType` like `DEFAULT_TONES`.
- [ ] **Step 1: Failing tests:** `test_living_defaults` (theme without block → values above), `test_living_override` (`"living": {"travel_px": {"near": 80}}` → near 80, far/mid default), `test_living_rejects_unknown_depth_key`, `test_living_particle_color_must_be_palette_key`, `test_sfx_defaults_and_ranges` (`sample_rate` must be 44100 or 48000; `auto_whoosh_db` −40…0; `reverb_wet` 0…1).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** parsers following `_parse_text_in` / tones style (`ctx.section`, `ctx.num` with ranges). Ranges: travel 0–200 px, zoom_factor 0–1.5, prescale 1–4, loop_seconds 0.5–8, shake_px 0–30, others ≥ 0.
- [ ] **Step 4:** Run tests + gates → PASS (snapshots unchanged: theme defaults are not used by existing steps).
- [ ] **Step 5: Commit** `feat(theme): living and sfx blocks`

### Task 3: Sound synthesis library

**Files:**
- Create: `history_shorts/sfx.py`
- Test: `tests/test_sfx.py`

**Interfaces:**
- Consumes: `SfxSpec` (Task 2), `SOUND_NAMES` (Task 1).
- Produces:
  - `NOMINAL_SECONDS: Final[Mapping[str, float]] = {"gong": 4.0, "drum": 1.5, "bell": 3.0, "whoosh": 0.9}`
  - `synth(name: str, rng: np.random.Generator, spec: SfxSpec, *, duration: float | None = None, pan: tuple[float, float] = (0.0, 0.0)) -> NDArray[np.float32]` — shape `(n, 2)`, `n = round(seconds * spec.sample_rate)` where seconds = `duration` for beds and whoosh-with-duration, else nominal + reverb tail; `pan` = (start, end) in −1…1 linearly interpolated over the sound.
  - `write_wav(samples: NDArray[np.float32], path: Path, sample_rate: int) -> None` — 16-bit PCM stereo via `wave`, clipped to ±1.
  - `PEAK_DBFS: Final = -1.0`
- [ ] **Step 1: Failing tests** (AC-26), all with `rng = np.random.default_rng([7, 0, 0])`, default `SfxSpec()`:
  - `test_deterministic[name]` for all six names: two calls with fresh equal RNGs → `np.array_equal`.
  - `test_finite_and_peak[name]`: `np.isfinite(x).all()`; `20*log10(abs(x).max()) <= -1.0 + 1e-3`; `> -3.0` (not near-silent).
  - `test_jitter_varies`: `synth("gong", rng_a)` vs `rng_b = default_rng([7, 0, 1])` → not equal, but spectral centroids within 10 %.
  - `test_centroid_ranges`: spectral centroid (helper `centroid_hz(x, sr)` in the test) — gong 150–900 Hz, drum 60–400 Hz, bell 600–3000 Hz, whoosh 500–4000 Hz, wind 150–1500 Hz, water 300–3000 Hz. (Builder: if a recipe lands just outside after careful listening, adjust the recipe, not the range, unless the range is clearly wrong; note any range change in the report.)
  - `test_decay`: gong RMS of last 0.5 s < RMS of first 0.5 s − 20 dB; drum energy after 1.0 s < 5 % of total.
  - `test_bed_length_and_fades`: `synth("wind", rng, spec, duration=3.0)` has `3.0*48000` frames; first and last 10 ms RMS < −40 dBFS (fade in/out, seamless start/end).
  - `test_pan_moves`: whoosh with `pan=(1.0, -1.0)`: right-channel energy dominates the first third, left dominates the last third.
  - `test_write_wav_roundtrip(tmp_path)`: read back with `wave` → 2 channels, 16-bit, rate 48000, frame count equal.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** One private function per sound (`_gong`, `_drum`, …) returning mono or stereo float, then shared `_reverb(x, rng, spec)` (fftconvolve with exponentially decaying noise IR of `spec.reverb_seconds`, independent IR per channel, mix `spec.reverb_wet`), `_pan`, `_normalise(x, PEAK_DBFS)`. Recipe guidance is in the spec §1; all recipe numbers are module constants grouped per sound (e.g. `GONG_PARTIALS: Final = ((1.0, 1.0), (1.47, 0.6), ...)`). Jitter: multiply pitches by `1 + rng.uniform(-spec.jitter, spec.jitter)` once per call. No per-sample Python loops (use numpy vector ops / `scipy.signal.lfilter`, `butter`, `sosfilt`).
- [ ] **Step 4:** Run tests + gates → PASS. Also listen: write each sound to `tmp_path`-like scratch and play with `ffplay -nodisp -autoexit` (manual; note impressions in the report).
- [ ] **Step 5: Commit** `feat(sfx): synthesized gong, drum, bell, whoosh, wind, water`

### Task 4: Cue planning, auto whoosh and mixing synthesized cues

**Files:**
- Modify: `history_shorts/cues.py` (add `SynthJob`, `synth_jobs`, `shake_times`, `MOVING_TRANSITIONS`)
- Modify: `history_shorts/video.py` (`RenderOptions.synth`, `_materialize_synth`, `_run_steps`)
- Modify: `history_shorts/cli.py:_encode_video` (pass `synth=cues.synth_jobs(...)`; warn for shake on non-living slides)
- Modify: `history_shorts/report.py` (list synthesized cues: slide id, name, at, gain, auto flag)
- Test: `tests/test_cues.py` (create), `tests/test_video.py`, `tests/test_e2e.py`

**Interfaces:**
- Consumes: `synth`, `write_wav`, `NOMINAL_SECONDS` (Task 3); `SfxCue`, `Slide.auto_sfx` (Task 1); `Theme.sfx`, `Theme.transition.duration`.
- Produces:
  - `MOVING_TRANSITIONS: Final = ("slideleft", "slideright", "slideup", "wipeleft", "wiperight", "circleopen")`
  - `AUTO_CUE_INDEX: Final = 99` (RNG key of the auto whoosh)
  - `@dataclass(frozen=True, slots=True) class SynthJob: name: str; slide_index: int; cue_index: int; delay_ms: int; gain_db: float; duration: float | None; pan: tuple[float, float]; auto: bool` — defined in `history_shorts/sfx.py` (not `cues.py`) so `video.py` can use it without importing `cues` (which imports `video.overlaps`).
  - `synth_jobs(script: Script, durations: list[float], theme: Theme) -> tuple[SynthJob, ...]`
  - `shake_times(slide: Slide) -> tuple[float, ...]` — `at` of cues with `shake=True`, sorted.
  - `RenderOptions.synth: tuple[SynthJob, ...] = ()`
  - `video._materialize_synth(jobs: tuple[SynthJob, ...], theme: Theme, work: Path) -> tuple[ffmpeg.VoiceInput, ...]` — writes `work/sfx_{slide:02d}_{cue:02d}.wav`, RNG `default_rng([theme.seed, job.slide_index, job.cue_index])`.
- Auto whoosh rule (spec §1 + A.2.3): for slide k > 0 with `transition in MOVING_TRANSITIONS`, `auto_sfx` true and script version 2.2: `overlap = cues-side copy of video.overlaps(...)[k-1]` (reuse `video.overlaps`), duration = `overlap + 0.4`, start = slide k start − 0.2 s (clamped ≥ 0), gain `theme.sfx.auto_whoosh_db`, pan by direction: `slideleft`/`wipeleft` (1, −1); `slideright`/`wiperight` (−1, 1); `slideup`/`circleopen` (0, 0).
- [ ] **Step 1: Failing tests** in `tests/test_cues.py`:
  - `test_auto_whoosh_on_moving_transition`: 2.2 script, slides 3 s each, slide 1 `transition: "slideleft"` → one auto job, `name "whoosh"`, `delay_ms == 2800`, `pan == (1.0, -1.0)`, `gain_db == -14.0`.
  - `test_no_auto_whoosh_for_fade_or_cut_or_opt_out_or_v21`: `fade` → none; `slideleft` with `auto_sfx: false` → none; same script as 2.1 (no auto) → none.
  - `test_named_cue_job`: `{"sound": "bell", "at": 1.0, "gain_db": -3}` on slide 2 (start 6 s) → `delay_ms 7000`, `cue_index 0`, `auto False`.
  - `test_file_cues_stay_in_sfx_inputs`: mixed file + sound cues → `sfx_inputs` has only the file cue; `synth_jobs` only the sound cue.
  - `test_shake_times`: cues gong(shake) at 2.0, drum(shake) at 0.5, bell at 1.0 → `(0.5, 2.0)`.
  - In `tests/test_video.py`: `test_materialize_synth_writes_wavs(tmp_path)` → files exist, `VoiceInput.delay_ms` and `gain_db` copied, deterministic bytes across two runs.
  - In `tests/test_ffmpeg_commands.py`: `test_no_synth_command_unchanged` — a 2.1 script with transitions produces the same mix command as before (AC-30): compare with the existing expected-command fixture/helper used for AC-25.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** `_run_steps` calls `_materialize_synth` before building `MixPlan(opts.voices, opts.sfx + synth_inputs, opts.cuts)`. In `cli`, a `shake` cue on a non-living slide → `WARN slides[i].sfx[j].shake has no effect without "living": true` (**RF-5**, test `test_shake_without_living_warns` in `tests/test_cli_validate.py`).
- [ ] **Step 4: E2E (AC-27)** in `tests/test_e2e.py`, `@pytest.mark.ffmpeg`: render a 2-slide 2.2 script (no scene, 3 s each, slide 1 `transition: "slideleft"`, slide 0 cue `gong at 1.0`) and assert, with the existing RMS helper used for AC-24, that RMS in [1.0, 1.2] s > RMS in [0.8, 1.0] s and RMS in [2.8, 3.2] s > RMS in [2.2, 2.6] s. Run tests + gates → PASS.
- [ ] **Step 5: Commit** `feat(audio): mix synthesized cues and automatic transition whoosh`

### Task 5: Depth assignment and plane decomposition

**Files:**
- Create: `history_shorts/living/__init__.py`, `history_shorts/living/depth.py`, `history_shorts/living/planes.py`
- Modify: `history_shorts/compose.py` (expose step helpers needed by planes: a function returning the grain field and the sheen field separately; keep `finish()` output bit-identical)
- Modify: `history_shorts/textures.py` (`finish` refactored into `sheen_field(...)` and `grain_field(...)`; `finish` = `clip((img + sheen) * grain)` — must stay bit-identical, snapshots prove it)
- Test: `tests/test_living_planes.py`

**Interfaces:**
- Consumes: `LayerScene.depths`, `Depth` (Task 1); `LivingSpec` (Task 2); `draw_layers`, `DrawContext`, `SlideContext`, `chrome.*`, `tone_grade`.
- Produces:
  - `living.depth.DEFAULT_DEPTH: Final[Mapping[type, Depth]]` — far: `SunLayer, CloudsLayer, MountainsLayer, PeaksLayer`; mid: `HillsLayer, RiverLayer, CitadelLayer, TempleLayer, BambooVillageLayer, StiltHouseLayer, MapLayer, BoatLayer, SailBoatLayer, ElephantLayer, HorseLayer, LonePathLayer, BannersLayer, BirdsLayer`; near: everything else. A test asserts every class in `LAYER_TYPES` has an entry.
  - `effective_depths(layers: Sequence[Layer], overrides: Sequence[Depth | None]) -> tuple[tuple[Depth, ...], tuple[int, ...]]` — second item: indices whose depth was raised (RF-3).
  - `FloatRGBA = NDArray[np.float32]` shape `(h, w, 4)`, premultiplied.
  - `@dataclass(frozen=True) class ScenePlane: depth: Depth; rgba: FloatRGBA; layer_indices: tuple[int, ...]; opaque: bool` (first plane = ground + leading far layers, opaque).
  - `@dataclass(frozen=True) class TopPlanes: waves: FloatRGBA; sheen: FloatImage; chrome: FloatRGBA; text: FloatRGBA | None`
  - `@dataclass(frozen=True) class LivingStack: scene: tuple[ScenePlane, ...]; top: TopPlanes`
  - `matte(draw: Callable[[FloatImage], FloatImage], h: int, w: int) -> FloatRGBA` — runs `draw` on zeros and on ones; `alpha = 1 - (white - black).mean(-1)`, `rgb = black`.
  - `build_stack(ctx: SlideContext, layers: Sequence[Layer], depths: Sequence[Depth]) -> LivingStack` — consecutive layers of equal depth merge into one plane; layer indices passed to drawers stay `k + GROUND_LAYER + 1` as in `draw_layers`.
  - `recompose(stack: LivingStack) -> FloatImage` — t = 0 composite: scene planes over each other → waves over → `+ sheen` → chrome over → text over; then clip.
- Math (why it is exact; implement exactly this): flat = `Pillow(T(frame + (1-a_f)·(G·(waves + (1-a_w)·scene) + sheen)))` with grain `G` (multiply) and tone `T` (linear) ⇒ apply `G` then `T` to each scene plane's premultiplied rgb and to the waves plane; apply `T` to the sheen field; chrome = `T(frame)` matted together with the Pillow steps (seal, tag, title, subtitle unless `text_in`, progress bar, footer) by running those steps on a black and on a white 8-bit base; text plane likewise when `text_in == "fade"`.
- [ ] **Step 1: Failing tests:**
  - `test_default_depth_covers_all_layer_types`.
  - `test_effective_depths_monotone` (RF-3): `[clouds(None), boat(None), mountains("far")]` → `("far", "mid", "mid")`, raised `(2,)`.
  - `test_matte_recovers_alpha`: draw a 50 %-alpha red Cairo rect via `over` → alpha 0.5 ± 1/255 inside, 0 outside.
  - `test_recompose_matches_flat[example]` for every slide of `examples/hai_ba_trung` and `examples/nu_tuong` with tone forced to each of `none`, `warm`: `abs(recompose(stack)*255 - np.asarray(render_slide(ctx))).mean() <= 0.5` and max ≤ 6 (8-bit text rounding).
  - `test_finish_bit_identical`: `finish` before/after refactor — covered by existing snapshot tests passing unchanged; add an explicit test comparing `finish(...)` against `clip((img + sheen_field) * grain_field)` on a random image.
  - `test_no_scene_living_slide` (RF-2): slide without scene → one opaque plane, recompose matches flat.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement** `depth.py`, `planes.py`, the textures split. Grain field must be the same array `finish` uses (same RNG key `FINISH_LAYER`). In `cli` validation, for each living slide with a layers scene, emit `WARN slides[i].scene.layers[k].depth raised from <a> to <b> to keep the drawing order` for every raised index (RF-3); test `test_depth_raise_warns` in `tests/test_cli_validate.py`. A living slide with a template scene uses the expanded layers and the default table.
- [ ] **Step 4:** Run tests + full gates (snapshots must pass untouched) → PASS.
- [ ] **Step 5: Commit** `feat(living): depth table and exact plane decomposition`

### Task 6: Ambient animators and particles

**Files:**
- Create: `history_shorts/living/animate.py`, `history_shorts/living/particles.py`
- Modify: `history_shorts/living/planes.py` (`build_stack` pulls animated layers out into their own planes, keeping order)
- Test: `tests/test_living_animate.py`

**Interfaces:**
- Consumes: Task 5 types; `LivingSpec`; `matte`.
- Produces:
  - `@dataclass(frozen=True) class SpritePlane: depth: Depth; frames: tuple[FloatRGBA, ...]; origin: tuple[int, int]` (crop origin in canvas px).
  - `@dataclass(frozen=True) class DriftPlane: depth: Depth; rgba: FloatRGBA; velocity: tuple[float, float]` (px/s, canvas px).
  - `ScenePlaneLike = ScenePlane | SpritePlane | DriftPlane`; `LivingStack.scene: tuple[ScenePlaneLike, ...]`.
  - `ANIMATED: Final[Mapping[type, str]]` = `{CloudsLayer: "drift", BirdsLayer: "glide", LanternsLayer: "float_items", BoatLayer: "bob", SailBoatLayer: "bob", RiverLayer: "ripple", LotusLayer: "sway", SunLayer: "pulse"}`.
  - `animate(kind: str, rgba: FloatRGBA, spec: LivingSpec, frames: int, rng: np.random.Generator, *, anchor: tuple[float, float]) -> SpritePlane | DriftPlane` (anchor = pivot for roll/sway: bottom-centre of the layer's alpha bbox).
  - `float_items(layer: LanternsLayer, render_one: Callable[[LanternsLayer], FloatRGBA], spec, frames, rng) -> tuple[SpritePlane, ...]` — one sprite per item (layer copy with a single item), phase offset per item from `rng`.
  - `particle_frames(kind: str, spec: LivingSpec, palette: Palette, rng: np.random.Generator, frames: int, region: Box) -> SpritePlane` — region = layout visual region (290–1150); alpha ramps to 0 within 40 px of the region edges.
- Motion functions (all periodic in phase `p = i / frames`, so frame `frames` ≡ frame 0): bob `y = bob_px·sin(2πp+φ)`; roll `θ = roll_deg·sin(2πp+φ+π/2)`; sway `θ = sway_deg·sin(2πp)` about the anchor; ripple: horizontal displacement `ripple_px·sin(2π(y/λ − p))` with λ = 24 px, applied with `scipy.ndimage.map_coordinates(order=1)`; pulse: rgb·alpha scaled by `1 + glow_pulse·sin(2πp)`; flicker (lanterns): brightness `1 + flicker·smooth_noise(p)` where smooth noise = sum of 3 sines with integer frequencies 1–3 and random phases (periodic). Glide: DriftPlane (velocity `bird_drift_px_s`, direction from rng sign) — wing beat is out of scope. Drift: DriftPlane with velocity `(±cloud_drift_px_s, 0)`.
- Frame count = `round(spec.loop_seconds * fps)`; sprite crop = alpha bbox padded by `ceil(bob_px + 4)` px.
- [ ] **Step 1: Failing tests** (AC-29):
  - `test_loop_seamless[kind]` for bob/sway/ripple/pulse/float_items/particles: `animate` frame 0 vs a recomputed frame at index `frames` (expose `frame_at(kind, rgba, spec, p, ...)` and assert `frame_at(..., 1.0)` equals frame 0 within 1e-5).
  - `test_static_pixels_unchanged_ripple`: pixels with alpha 0 within 2·ripple_px of nothing stay 0; total alpha mass preserved within 1 %.
  - `test_bob_amplitude`: alpha centroid y over frames spans `2·bob_px ± 0.5`.
  - `test_particles_stay_in_region`: every frame's alpha is 0 outside `region`.
  - `test_build_stack_order_with_animated`: layers `[mountains, clouds, hills, boat, lotus]` → planes `[opaque(ground+mountains), Drift(clouds), Static(hills), Sprite(boat), Sprite(lotus)]`; `recompose` (with sprites at frame 0, drift at offset 0) still matches flat within Task 5 tolerances.
  - `test_determinism`: two builds → identical arrays.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement.** Each animated layer is matted alone (`matte(lambda base: drawer(base, layer, dctx, index))`), then grain and tone are applied (as in Task 5) before animating, so grain moves with the object.
- [ ] **Step 4:** Run tests + gates → PASS.
- [ ] **Step 5: Commit** `feat(living): ambient sprite loops, drift planes and particles`

### Task 7: Writing living assets

**Files:**
- Create: `history_shorts/living/assets.py`
- Modify: `history_shorts/render.py:render_slides` (new kw-only `living_assets: bool = True`, `durations: Sequence[float] | None = None`)
- Modify: `history_shorts/cli.py` (`_render_pngs` passes `living_assets=not args.preview` and the durations)
- Modify: `history_shorts/output.py` (`living_dir(png: Path) -> Path` = `<stem>_living/`)
- Test: `tests/test_living_assets.py`, `tests/test_render_preview.py`

**Interfaces:**
- Consumes: Tasks 5–6.
- Produces:
  - `@dataclass(frozen=True) class PlaneFile: kind: Literal["static", "sprite", "drift"]; depth: Depth; path: Path; frames: int; origin: tuple[int, int]; velocity: tuple[float, float]; pad: tuple[int, int]; size: tuple[int, int]` — `path` is a PNG (static/drift) or a `%03d.png` pattern (sprite); `pad` = (px, py) edge padding; `size` = padded image size.
  - `@dataclass(frozen=True) class LivingClip: planes: tuple[PlaneFile, ...]; waves: Path; sheen: Path; chrome: Path; text: Path | None; shakes: tuple[float, ...]`
  - `write_living(stack: LivingStack, directory: Path, spec: LivingSpec, duration: float, shakes: tuple[float, ...]) -> LivingClip`
  - `living_pad(depth: Depth, spec: LivingSpec, drift: float, duration: float) -> tuple[int, int]` — `px = ceil(travel_px[depth] + shake_px + |drift|·duration + 2)`, `py = ceil(px · 1920 / 1080)` (aspect-proportional so a single zoom maps the window).
  - Static/drift planes are padded with `np.pad(mode="edge")` on premultiplied RGBA; sprites are written unpadded at their crop and composited onto a transparent padded canvas in FFmpeg (Task 8), so they get `pad` of their depth and `origin + pad`.
  - Sheen is written as 8-bit RGB PNG scaled ×4 (`round(sheen·255·4)`, clipped) with the factor as constant `SHEEN_PNG_GAIN = 4` (it is ≤ 0.10, so ×4 keeps precision); FFmpeg divides it back.
  - `render_slides` returns the same list as before; living clips are collected via a new function `render_living(script, theme, out, durations) -> tuple[LivingClip | None, ...]` called by `cli` after `render_slides` (keeps `render_slides` signature stable; drop the `living_assets` kw if unused).
- [ ] **Step 1: Failing tests:**
  - `test_write_living_files(tmp_path)`: one living slide of `hai_ba_trung` → every `PlaneFile.path` exists (sprites: `frames` files), padded sizes equal `(1080 + 2px, 1920 + 2py)`.
  - `test_pad_covers_travel`: `living_pad("near", spec, 0, 5)` ≥ `travel_px["near"] + shake_px`.
  - `test_assets_per_slide_dirs` (RF-4): two living slides → disjoint directories `01_living/`, `02_living/`.
  - `test_preview_writes_no_living_assets(tmp_path)` in `tests/test_render_preview.py`: `render --preview` on a living script → no `*_living` dir; slide PNGs identical to the same script without `living`.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run + gates → PASS.
- [ ] **Step 5: Commit** `feat(living): write plane and sprite assets per slide`

### Task 8: FFmpeg living clip

**Files:**
- Create: `history_shorts/living/motion.py` (pure expression builders)
- Modify: `history_shorts/ffmpeg.py` (`living_clip_cmd`)
- Modify: `history_shorts/video.py` (`RenderOptions.living: tuple[LivingClip | None, ...] = ()`; `_clip_cmds` picks `living_clip_cmd` when set)
- Modify: `history_shorts/cli.py` (pass `living=` from Task 7)
- Test: `tests/test_living_motion.py`, `tests/test_ffmpeg_commands.py`

**Interfaces:**
- Consumes: `PlaneFile`, `LivingClip` (Task 7); `LivingSpec`; existing `_fade_filter`, `TextLayer`, `X264_PRESET`.
- Produces:
  - `eased(frames: int) -> str` → `"(1-cos(PI*on/{frames}))/2"`.
  - `camera(motion: str, depth: Depth, spec: LivingSpec) -> tuple[float, float, float]` — (dx_px, dy_px, dzoom) reached at progress 1: pan_left `(-travel, 0, 0)`, pan_right `(+travel, 0, 0)`, pan_up `(0, -travel, 0)`, pan_down `(0, +travel, 0)`, zoom_in `(0, 0, 0.06·zoom_factor)`, zoom_out `(0, 0, −0.06·zoom_factor)` (starts at `1+0.06·f`), none `(idle_drift·travel, 0, 0)`; travel = `travel_px[depth]`.
  - `shake_expr(times: tuple[float, ...], spec: LivingSpec, fps: int, axis: Literal["x", "y"]) -> str` — sum over times of `between(on/fps, t0, t0+3·τ) * A·exp(-(on/fps-t0)/τ)·sin(2π·f·(on/fps-t0)+φ)`, A = `shake_px`, τ = `shake_seconds/3`, f = 9 Hz (x) / 7 Hz (y), φ = 0 (x) / π/2 (y); `"0"` when no times.
  - `plane_graph(index: int, plane: PlaneFile, motion: str, duration: float, fps: int, spec: LivingSpec, shakes: tuple[float, ...], label: str) -> str` — for sprites: `color=c=black@0:s={W}x{H}:r={fps},format=rgba[c];[c][index:v]overlay={ox}:{oy}:shortest=1`; then `scale={W*k}:{H*k}` (k = `spec.prescale`), `zoompan=z='{Z}':x='{X}':y='{Y}':d=1:s=1080x1920:fps={fps}` with `Z = (1+2px/1080)·(1+dzoom·P)` (zoom_out: `(1+2px/1080)·(1+|dzoom|·(1−P))`), `X = iw/2-iw/zoom/2 + (dx·P + drift_x·on/fps + shake_x)·iw/(zoom·1080)`, `Y` likewise with 1920; drift uses `plane.velocity`.
  - `living_clip_cmd(info: FfmpegInfo, clip: LivingClip, out: Path, duration: float, fps: int, crf: int, fades: str, motion: str, spec: LivingSpec, threads: int | None, text: TextLayer | None) -> list[str]` — inputs in order: planes (static/drift: `-loop 1 -framerate fps -t dur -i png`; sprite: `-stream_loop -1 -framerate fps -i pattern`, limited by `-t dur`), waves, sheen, chrome, text. Graph: planes overlaid in order (`overlay=0:0:format=auto`), then waves (`overlay`), then sheen added (`[s]format=rgb24,lutrgb=r=val/4:g=val/4:b=val/4[sh]` + `blend=all_mode=addition`, using `SHEEN_PNG_GAIN`), then chrome overlay, then text overlay with the existing `fade=t=in:...:alpha=1` when `text` is given, then `fades`, `format=yuv420p`. Same encoder args as `clip_cmd`.
- [ ] **Step 1: Failing tests:**
  - `test_camera_table` for all motions × depths (exact tuples from `LivingSpec()` defaults).
  - `test_eased_endpoints`: evaluate the expression in Python (replace `on`, `PI`, `cos`) at `on=0` → 0, `on=frames` → 1, `on=frames/2` → 0.5.
  - `test_shake_expr_zero_without_times` and `test_shake_expr_decays`: Python-evaluated value at `t0+3τ` ≈ 0, peak |value| ≤ `shake_px`.
  - `test_living_cmd_structure`: one input per plane + 3 (+1 with text); graph contains one `zoompan` per scene plane, `blend=all_mode=addition`, ends with `format=yuv420p[v]`; no `shell`, all items `str`.
  - `test_living_clip_uses_extended_duration` (RF-1): `_clip_cmds` for a living slide followed by a `slideleft` slide → the living command's `frames` in `eased()` equals `round((dur+overlap)·fps)`.
  - `test_non_living_commands_unchanged` (AC-30): existing 2.1 examples → `_clip_cmds` output equals the commands produced before this task (use the existing AC-25 fixture/comparison).
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** Run + gates → PASS.
- [ ] **Step 5: Commit** `feat(living): parallax clip command with eased motion and hit shake`

### Task 9: End-to-end checks for living slides

**Files:**
- Test: `tests/test_e2e_living.py` (create; `@pytest.mark.ffmpeg`)
- Create: `tests/data/living_script.json` (2.2, 2 slides: slide 0 `living: true, motion: "pan_right"`, scene layers `[mountains, clouds, hills, river, boat, lotus]`, cue `gong at 0.5 shake true`; slide 1 `living: true, motion: "none", particles: "petals", text_in: "fade", transition: "slideleft"`, scene `template: "landscape"`; durations 4 s and 3 s)

- [ ] **Step 1: Write tests** (AC-28 + first-frame match), extracting frames with FFmpeg to PNG under `tmp_path`:
  - `test_living_render_duration`: ffprobe duration = 7.0 ± 0.1 s.
  - `test_first_frame_matches_preview`: frame 0 vs `render --preview` PNG of slide 0: mean ΔE (use `tests/helpers` ΔE function used for AC-03) ≤ 2 per layout region.
  - `test_top_region_stable`: frame band y 1540–1920 (chrome region) at t = 0.2 vs t = 3.5: mean abs diff ≤ 3/255 (excluding the progress bar row if it animates — it does not).
  - `test_near_moves_more_than_far`: phase-correlate (numpy FFT) a crop of the near area (y 1000–1140) and the far area (y 300–420) between t = 0.1 and t = 3.8 → |shift_near| > |shift_far| > 0.
  - `test_no_holes`: every frame sampled at 0.5 s steps: no pixel inside x 40–1040, y 300–1500 equals pure black (all channels ≤ 2/255) unless the same pixel is ≤ 2/255 in the preview.
  - `test_shake_visible_then_settles`: mean abs diff between consecutive frames around t = 0.5–0.7 > that around t = 1.5–1.7.
- [ ] **Step 2:** Run `pytest tests/test_e2e_living.py -q` → PASS (fix the implementation in the owning module if not; do not loosen thresholds without noting why in the report).
- [ ] **Step 3: Commit** `test(living): end-to-end parallax, stability and first-frame checks`

### Task 10: Example, docs and measurement

**Files:**
- Modify: `examples/hai_ba_trung/script.json` (→ `"2.2"`, `living: true` on scene slides, named sounds, one `particles`)
- Modify: `docs/raw_requirement.md` (A.2.1 `sfx` row: sounds may be synthesized; new section A.4 "Living slides and synthesized sound (M9)" with fields, theme blocks, AC-26..AC-31)
- Modify: `docs/superpowers/specs/2026-11-13-living-scenes-sfx-design.md` (add the deviation paragraph from this plan)
- Modify: `README.md` (user guide: sound names table, living/particles/depth fields, theme `living`/`sfx` blocks; "Decisions": synthesized sfx 2026-11-13, warp-based ambient motion, banners/flags not waving yet; changelog)
- Modify: `docs/visual_backlog.md` (follow-up item: waving banners and character flags)

- [ ] **Step 1:** Edit the example. Sounds: `gong` (shake) on the title slide at 0.3 s; `drum` (shake) on the uprising slide; `bell` on a temple/tablet slide if present; `wind`/`water` beds (−18 dB) where the scene shows open land/river; `particles: "petals"` on one calm slide. Do not change any on-screen text or historical content.
- [ ] **Step 2:** `python -m history_shorts validate --script examples/hai_ba_trung/script.json` → exit 0, warnings reviewed (depth raises listed).
- [ ] **Step 3:** Measure AC-31: render `hai_ba_trung` on the M8 commit (`git stash`-free: use `git worktree add <scratch> 0d0411d` in the scratchpad) and on this branch, both `--jobs 1`; record `elapsed` from the summary. Target ≤ 3×; if over, profile (`--verbose` per-slide times) and reduce (`prescale`, sprite crop, loop_seconds) before continuing.
- [ ] **Step 4:** Render the final example to `output/hai_ba_trung.mp4`, extract frames at 0.0/1.5/3.0 s of two living slides, open them next to `docs/reference/approved/*.png` and the preview PNGs; list visible differences in the report. Probe the video with the ffprobe command in CLAUDE.md.
- [ ] **Step 5:** Docs edits above. Run all gates.
- [ ] **Step 6: Commit** `docs: M9 living slides and synthesized sound; hai_ba_trung uses them`

Final report to the owner: what changed, AC-26..AC-31 status, test results, measured render time, visual notes, and ask the owner to watch `output/hai_ba_trung.mp4` and judge "natural".
