# M10 Character and Scene Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inside a living slide, fire, smoke and flags move by redrawing, and characters breathe, sway and perform timed actions (rally, bow, kneel, sit, stand_up, raise_flag, look) through a jointed costume kit.

**Architecture:** Scene layers gain optional phase-aware drawers that M9's `SpritePlane.render(p)` calls instead of warping pixels. The `ancient_female` kit reads an optional `Pose` from `CharacterStyle`: `pose is None` draws today's exact paths (still slides, `--preview`); a `Pose` draws jointed parts under Cairo joint transforms. Characters on 2.3 living slides become their own sprite planes; action timelines are data interpolated per frame.

**Tech Stack:** Python ≥ 3.10, pycairo, numpy, scipy, Pillow, system FFmpeg; pytest, ruff, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-11-20-character-scene-animation-design.md` (owner-approved 2026-11-20), together with `CLAUDE.md` and `docs/raw_requirement.md` Appendix A.4 (M9).

## Global Constraints

- No AI, no network imports, no new dependencies, no `shell=True`, no crackle/black streaks, darkest stroke `palette.black` (CLAUDE.md hard rules 1–8).
- No hardcoded style values: amplitudes, angles, durations are named constants or `theme.living` values.
- Determinism: RNG = `rng_for(theme.seed, slide_index, key)`; new keys: character motion `CHAR_KEY = 700 + layer_index * 16 + character_index` (layer_index < 16 crew/items guaranteed by `MAX_CREW` and an items cap check).
- Every new feature switches on only when `script.schema_version == "2.3"` (`ANIMATED_SCHEMA_VERSION`). A 2.2 script produces identical planes, FFmpeg commands and snapshots (extends AC-30).
- `pose is None` → byte-identical to today's `draw_figure`; all existing snapshots stay unchanged (AC-32). Never run `--update-snapshots` in this milestone.
- Phase 0 of every redraw equals the still drawer pixel-for-pixel; every redraw is periodic (`draw(p=1) == draw(p=0)`) (AC-35).
- Living first frame vs `--preview`: mean ΔE ≤ 2 per layout region (settled call 1).
- Hand centre within 0.5 unit of the shaft in every pose; a held spear within ±10° of vertical (AC-33). Weapons never point at anyone; faces unchanged (FR-43).
- Demos reuse existing slides only; never invent historical text.
- Quality gates after each task: `ruff check . && ruff format --check . && mypy --strict history_shorts && pytest -q`.
- Commit on this branch after each task; never push.

## Review Focus

1. **Mirrored characters (`facing: -1`) performing actions** — the "near" arm must stay the prop arm after `scale(-1, 1)`; rally must raise the free arm on the correct side. Test in Task 7.
2. **Held/kneeling pose through the transition overlap** — the clip is `slide duration + transition.duration`; a `kneel` at the end must hold, not snap back, during the overlap. Test in Task 14.
3. **Characters near the gold frame or text while moving** — raised arms/flags and parallax travel can push a box into the title/seal; FR-48 must use the union box over the clip. Test in Task 12.
4. **Sprite sequences longer than 999 frames** — current `%03d` pattern breaks silently for long slides at 30 fps. Test in Task 1.
5. **2.2 scripts with `living: true` (e.g. `trong_dong`)** — must not change at all. Test in Task 1 and Task 12.

---

## Milestone M10a — scene redraw (owner reviews a rendered clip at the end)

### Task 1: Phase-redraw infrastructure and schema 2.3

**Files:**
- Modify: `history_shorts/script_config.py` (add `ANIMATED_SCHEMA_VERSION = "2.3"` to `SUPPORTED_SCHEMA_VERSIONS`)
- Modify: `history_shorts/scene/registry.py` (phase drawer type + `phase_entry`)
- Modify: `history_shorts/scene/__init__.py` (export `PHASE_DRAWERS: Mapping[type, PhaseDrawer]`, empty for now)
- Modify: `history_shorts/living/planes.py` (`_groups`, `_Animator.planes`, `build_stack(..., redraw: bool = False)`)
- Modify: `history_shorts/living/assets.py` (`_write_plane` frame names `%04d`; `render_living` passes `redraw`), `history_shorts/ffmpeg.py:_living_inputs` (`%04d` pattern)
- Test: `tests/test_living_redraw.py` (new), `tests/test_living_assets.py`

**Interfaces:**
- Produces: `PhaseDrawer = Callable[[FloatImage, Layer, DrawContext, int, float], FloatImage]` (last arg = phase in [0, 1)); `phase_entry(layer_type, fn) -> tuple[type, PhaseDrawer]`; `PHASE_DRAWERS`; `build_stack(ctx, layers, depths, *, animated=True, redraw=False)`; `render_living` passes `redraw = script.schema_version == ANIMATED_SCHEMA_VERSION`; `check_phase_drawer(layer, drawer) -> None` test helper in `tests/helpers/phase.py` asserting phase-0 identity and periodicity.

- [ ] **Step 1: Write failing tests**

```python
def test_schema_23_accepted(): parse a minimal living script with schema_version "2.3" → no errors
def test_redraw_layer_becomes_sprite_only_on_23(fake_phase_drawer):
    # register a fake PhaseDrawer for TempleLayer via monkeypatch
    stack22 = build_stack(ctx, layers, depths, redraw=False)
    stack23 = build_stack(ctx, layers, depths, redraw=True)
    assert not any(isinstance(p, SpritePlane) and k in p.layer_indices for p in stack22.scene)
    assert any(isinstance(p, SpritePlane) and p.layer_indices == (k,) for p in stack23.scene)
def test_redraw_sprite_phase0_matches_still(): recompose(stack23) at p=0 equals recompose(stack22) within 1/255
def test_sprite_frames_use_four_digits(tmp_path): write a 1200-frame sprite; files 0000.png..1199.png exist
def test_living_inputs_pattern_four_digits(): "%04d.png" in living_clip_cmd(...)
def test_22_living_commands_unchanged(): existing tests/test_e2e_living command snapshot still equal
```

- [ ] **Step 2: Run** `pytest tests/test_living_redraw.py tests/test_living_assets.py -v` — expect FAIL (missing names).
- [ ] **Step 3: Implement.** In `_groups`, a layer is moving if `type(layer) in ANIMATED or (redraw and type(layer) in PHASE_DRAWERS)`. In `_Animator.planes`, PHASE_DRAWERS wins over SPRITE_KINDS when `redraw`: render `n = self.frames` phases by calling the phase drawer through `matte` and `fin.plane`, crop all phases to the union alpha box + `EDGE_SLACK` with `animate_crop`-style edge extension, return one `SpritePlane` whose `render(p)` indexes the precomputed crops (`round(p * n) % n`). Rename sprite frames to `%04d`.
- [ ] **Step 4: Run** the tests — expect PASS; run full gates.
- [ ] **Step 5: Commit** `feat(living): phase-redraw sprites and schema 2.3 gate`

### Task 2: Furnace fire redraw

**Files:** Modify `history_shorts/scene/furnace.py`; Modify `history_shorts/config.py` (`LivingSpec.flame_px: float = 10.0`, `flame_glow: float = 0.08`, ranges `(0, 40)`, `(0, 0.3)` in `_LIVING_NUMBERS`); Test `tests/test_scene_redraw.py` (new).

**Interfaces:** Consumes `phase_entry`, `check_phase_drawer`. Produces `draw_furnace_at(img, layer, ctx, index, phase) -> FloatImage` registered in `PHASE_DRAWERS`.

- [ ] **Step 1: Failing tests** — `check_phase_drawer(furnace_layer, draw_furnace_at)`; `test_furnace_flames_move`: frames at p=0.25 and p=0 differ inside the flame box and are identical outside the flame+halo box; `test_furnace_texture_stable`: pixels below the kiln mouth's top are equal at every phase.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.** Refactor the flame tongue drawing to take `phase`; each tongue's tip x/height offset = `flame_px * Σ_{n=1..3} a_n sin(2π(n·p + φ_tongue_n))` minus its value at p=0 (so p=0 is exact), `a_n` and `φ` from the layer RNG drawn once (same draw order as today, extra draws after the existing ones); halo alpha × `(1 + flame_glow·sin 2πp)`. `draw_furnace` = `draw_furnace_at(..., 0.0)`.
- [ ] **Step 4: Run** — PASS; gates.
- [ ] **Step 5: Commit** `feat(scene): furnace flames flicker on 2.3 living slides`

### Task 3: Temple incense smoke redraw

Same shape as Task 2. **Files:** `history_shorts/scene/temple.py`, `config.py` (`smoke_rise_px: float = 14.0` range `(0, 60)`), `tests/test_scene_redraw.py`. Produces `draw_temple_at`. Smoke curls translate upward by `smoke_rise_px * frac(p + k/curls)` with alpha fading in at the bottom and out at the top so the loop wraps seamlessly; roofs/pillars identical across phases (test pixels outside the smoke box). Commit `feat(scene): temple incense smoke rises`.

### Task 4: Cloth wave for banners and elephant flag

**Files:** Create `history_shorts/scene/cloth.py`; Modify `banners.py`, `elephant.py`, `config.py` (`cloth_wave: float = 0.12` — fraction of flag width, range `(0, 0.4)`); Test `tests/test_cloth.py`, `tests/test_scene_redraw.py`.

**Interfaces:** Produces `wave_point(x: float, y: float, pole_x: float, width: float, phase: float, amp: float, seed_phase: float) -> tuple[float, float]` — displaces a flag outline point; also used by the character flag in Task 10. Produces `draw_banners_at`, `draw_elephant_at`.

- [ ] **Step 1: Failing tests** — `test_wave_zero_at_pole`: `wave_point(pole_x, y, ...) == (pole_x, y)` for all phases; `test_wave_identity_at_phase0`; `test_wave_periodic`; `test_wave_bounded`: |dy| ≤ `amp*width`; `check_phase_drawer` for both layers.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** `wave_point`: `u = |x - pole_x| / width`; `dy = amp * width * u * (sin(2π(p - u) + s) - sin(-2πu + s))`; x unchanged. Flag paths are rebuilt by passing their control points through `wave_point`; spears unchanged.
- [ ] **Step 4: Run** — PASS; gates.
- [ ] **Step 5: Commit** `feat(scene): banners and elephant flags wave`

**M10a checkpoint:** bump a copy of `trong_dong` and an existing temple/banners slide to 2.3 in `tests/data/animated_script.json` (not the examples yet), render, extract first/middle/last frames, show the owner. Wait for feedback before M10b.

---

## Milestone M10b — rig and idle life

### Task 5: Pose type and rest identity

**Files:** Create `history_shorts/characters/pose.py`; Modify `history_shorts/characters/roles.py` (`CharacterStyle.pose: Pose | None = None`); Test `tests/test_pose.py`.

**Interfaces:** Produces
```python
@dataclass(frozen=True, slots=True)
class Pose:
    head_tilt: float = 0.0      # deg, + = chin up
    head_drop: float = 0.0      # units the head moves forward-down when bowing
    torso_lean: float = 0.0     # deg about WAIST, + = forward (toward facing)
    breath: float = 0.0         # -1..1
    near_shoulder: float = 0.0  # deg, + = arm raised forward/up
    near_elbow: float = 0.0     # deg, + = forearm bent up
    far_shoulder: float = 0.0
    far_elbow: float = 0.0
    crouch: float = 0.0         # 0 standing .. 1 kneeling
    lean_back: float = 0.0      # deg, sit only
    flag_wave: float = 0.0      # loop phase of the flag cloth
REST: Final = Pose()
def blend(a: Pose, b: Pose, w: float) -> Pose            # per-field lerp
def add(a: Pose, b: Pose) -> Pose                        # per-field sum, crouch clipped to [0,1]
```
- [ ] **Step 1: Failing tests** — `blend(a,b,0)==a`, `blend(a,b,1)==b`, `add(REST,p)==p`, crouch clip; `test_style_pose_none_is_default`.
- [ ] **Step 2–4:** run FAIL → implement → PASS + gates.
- [ ] **Step 5: Commit** `feat(characters): Pose type`

### Task 6: Jointed parts in the ancient_female kit

**Files:** Modify `history_shorts/characters/kits/ancient_female.py` (and split into `history_shorts/characters/kits/ancient_female_rig.py` for the jointed variants, to keep files focused); Test `tests/test_rig.py`.

**Interfaces:** Consumes `Pose`. Each part in `KIT.parts` keeps signature `(cv, style, palette)`; when `style.pose is None` it runs today's code unchanged; otherwise it delegates to its rig variant. Produces named pivots `NEAR_SHOULDER = (12.0, -78.0)`, `FAR_SHOULDER = (-12.0, -78.0)`, `HOLD_ELBOW = (19.5, -60.0)`, `HANG_ELBOW = (20.5, -58.0)` (mirror x for far), `NECK = (0.0, CHIN_Y)`, `WAIST = (0.0, WAIST_Y)`; and `joint(cv, pivot, deg)` context helper (`save/translate/rotate/translate back`, restore on exit).

- [ ] **Step 1: Failing tests**
```python
@pytest.mark.parametrize("role,facing,prop,crest", ROLE_MATRIX)   # same matrix as AC-07 tests
def test_rest_pose_close_to_legacy(role, facing, prop, crest):
    legacy = render_figure(style(pose=None)); rigged = render_figure(style(pose=REST))
    assert mean_abs_diff(legacy, rigged) < 1/255 and max_abs_diff(legacy, rigged) < 0.25
def test_pose_none_byte_identical_to_main(): existing figure snapshot hashes unchanged
def test_no_crack_at_elbow(pose in SAMPLE_POSES): alpha of sleeve mask has no hole inside its convex hull near the elbow (AC-34)
def test_spear_clamped(): rigged spear shaft angle within ±10° for near_shoulder in (-60..160)
def test_hand_on_shaft_all_poses(): kit.hand_center transformed by the pose stays ≤ 0.5 from shaft (AC-33)
```
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement.** Split each sleeve path at the elbow into upper (shoulder→elbow) and forearm (elbow→cuff) closed paths whose union at rest equals today's outline; draw an elbow patch ellipse (sleeve colour, radius ≈ sleeve half-width at the cut) under the forearm. Chain: torso lean (about WAIST, only parts above the belt) → shoulder → elbow → hand → `prop_front` shaft. Spear: compute the shaft angle from the arm chain and counter-rotate the prop about the hand centre so the shaft stays vertical; clamp `near_shoulder`/`near_elbow` so the hand stays where the vertical shaft can pass through it. Head parts (neck…crest) under `torso_lean` then `head_tilt` about NECK, plus `head_drop` translate. Breath: `scale(1 + breath*breath_scale)` about WAIST for torso parts and lift shoulders/head by `breath*0.3` units.
- [ ] **Step 4: Run** — PASS; gates (snapshots unchanged).
- [ ] **Step 5: Commit** `feat(characters): jointed arms, torso and head for posed drawing`

### Task 7: Free-hand arm and facing

**Files:** `ancient_female_rig.py`; Test `tests/test_rig.py`.

- [ ] **Step 1: Failing tests** — `free_arm(style) -> Literal["near", "far"]` returns `"far"` when the style holds a prop, else `"near"`. `test_free_arm_raise(facing in (1, -1), prop in ("spear", "none"))`: setting the free arm's shoulder to 120 puts that arm's highest canvas point above the head top, and the prop arm's hand stays on the shaft; `test_raised_arm_shows_fist`: when shoulder > 60°, the `_fist` pixels appear at the cuff (settled call 4), absent at rest.
- [ ] **Step 2–4:** FAIL → implement (fist drawn at the forearm cuff only when the arm is raised past `FIST_SHOW_DEG = 60`) → PASS + gates.
- [ ] **Step 5: Commit** `feat(characters): raised free arm with fist`

### Task 8: Crouch robe (kneel / sit)

**Files:** `ancient_female_rig.py`; Test `tests/test_rig.py`.

**Interfaces:** Produces constants `CROUCH_DROP = 22.0`, `CROUCH_SPREAD = 9.0`; `robe_outline(crouch: float) -> list[PathOp]` equal to today's robe path at 0.

- [ ] **Step 1: Failing tests** — `test_robe_outline_rest_equal`; `test_crouch_head_drops`: head box top moves down by `CROUCH_DROP ± 0.5` at crouch 1; `test_feet_stay`: lowest robe y = `BODY_BOTTOM` for all crouch; `test_crouch_continuous`: head y monotonic in crouch over 21 samples; `test_kneel_no_crack` (AC-34 style).
- [ ] **Step 2–4:** FAIL → implement (upper body translated down by `crouch*CROUCH_DROP`; skirt outline interpolated from standing to a folded-knee silhouette, hem half-width `HEM_HALF_WIDTH + crouch*CROUCH_SPREAD`; `lean_back` rotates the upper body about the hip) → PASS + gates.
- [ ] **Step 5: Commit** `feat(characters): kneeling and seated crouch`

### Task 9: Character flag wave

**Files:** `ancient_female_rig.py` (`_flag` rig variant uses `cloth.wave_point` with `pose.flag_wave`); Test `tests/test_rig.py`. Test: flag pixels change between `flag_wave=0` and `0.25`, pole and hand unchanged, periodic. Commit `feat(characters): character flags wave` (closes M9 backlog #20 — mark it in `docs/visual_backlog.md`).

### Task 10: Idle motion generator

**Files:** Create `history_shorts/characters/idle.py`; Modify `config.py` (`LivingSpec`: `idle_loop_seconds: float = 4.0` range `(1, 12)`, `breath_scale: float = 0.006` `(0, 0.03)`, `idle_sway_deg: float = 0.6` `(0, 3)`, `idle_head_deg: float = 1.0` `(0, 4)`, `flag_wave_hz: float = 0.5` `(0, 2)`); Test `tests/test_idle.py`.

**Interfaces:** Produces `idle_pose(rng: Generator, t: float, period: float, spec: LivingSpec) -> Pose` — breath = `sin(2πt/period)`, torso sway and head tilt = smooth sums of 2 sines with whole cycles per `period` and RNG phases; `flag_wave = frac(t * cycles/period)` with cycles = round(`flag_wave_hz*period`).

- [ ] **Step 1: Failing tests** — `test_idle_periodic`: `idle_pose(rng, 0) == idle_pose(rng, period)` (fresh rng with same seed); `test_idle_bounded`: |torso_lean| ≤ `idle_sway_deg`, |head_tilt| ≤ `idle_head_deg`; `test_idle_out_of_step`: two different RNG seeds give different `torso_lean` at t = period/4; `test_idle_smooth`: max change between 1/24 s samples ≤ 0.1°.
- [ ] **Step 2–4:** FAIL → implement → PASS + gates. Add theme keys to `themes/son_mai/theme.json` only if the theme file lists every living key today (follow existing pattern).
- [ ] **Step 5: Commit** `feat(characters): idle breathing and sway`

### Task 11: Character sprites on living slides (incl. boat crew)

**Files:** Create `history_shorts/living/characters.py`; Modify `history_shorts/living/planes.py`, `history_shorts/scene/people.py` (`draw_figures(..., poses: Sequence[Pose | None] | None = None)`), `history_shorts/scene/boat.py` (`draw_boat_at(img, layer, ctx, index, phase)` registered in `PHASE_DRAWERS`, crew posed by `idle_pose`, hull drawn after crew as today); Test `tests/test_living_characters.py`.

**Interfaces:** Consumes `idle_pose`, `PhaseDrawer`. Produces `character_planes(ctx, k, layer, depth, fin, timeline_for) -> list[SpritePlane]` where `timeline_for(char_index) -> Callable[[float], Pose]` (t in seconds → pose; idle-only today, actions in Task 14); characters whose union boxes overlap are rendered in one sprite in draw order.

- [ ] **Step 1: Failing tests** — `test_characters_layer_animated_only_23`; `test_character_sprite_loop_seamless` (AC-35); `test_first_frame_close_to_preview`: mean ΔE ≤ 2 per region vs `--preview` render; `test_boat_crew_feet_on_deck`: crew baseline within 1 px of the boat deck line in every frame (AC-36 via shared bob transform); `test_overlapping_characters_one_sprite`.
- [ ] **Step 2–4:** FAIL → implement → PASS + gates. Idle sprite frames = `round(idle_loop_seconds * fps)`.
- [ ] **Step 5: Commit** `feat(living): characters and boat crew breathe on 2.3 slides`

### Task 12: Union-box validation (FR-48 over time)

**Files:** Modify `history_shorts/validation.py` (and `characters/figure.py:figure_boxes` gains `pose: Pose | None = None` parameter only — no drawing change); Test `tests/test_validation.py`.

**Interfaces:** Produces `pose_union_boxes(style, placement, poses: Iterable[Pose]) -> FigureBoxes`; validation of a 2.3 living slide samples the character's timeline at `VALIDATION_SAMPLES = 25` times plus parallax extremes.

- [ ] **Step 1: Failing tests** — `test_raised_flag_hits_title_fails`: a 2.3 slide whose `raise_flag` lifts a box into the title region → error naming the character id; same slide at 2.2 without actions → passes; `test_union_box_contains_all_samples`.
- [ ] **Step 2–4:** FAIL → implement → PASS + gates.
- [ ] **Step 5: Commit** `feat(validation): FR-48 checks over the character's motion`

**M10b checkpoint:** render the test script (landscape boat slide from `me_linh` + a group slide, bumped to 2.3 in `tests/data/animated_script.json`), show the owner first/middle/last frames and the clip. Wait for feedback before M10c.

---

## Milestone M10c — timed actions

### Task 13: Actions and named poses as data

**Files:** Create `history_shorts/characters/actions.py`; Test `tests/test_actions.py`.

**Interfaces:** Produces
```python
@dataclass(frozen=True, slots=True)
class Action:
    keys: tuple[tuple[float, Pose], ...]   # (fraction 0..1, pose delta), first and last fraction 0 and 1
    duration: float                        # default seconds
    hold: bool                             # keep the last pose after the action
    needs_crouch: bool = False             # stand_up
ACTIONS: Mapping[str, Action]   # rally 1.6, bow 1.4, kneel 1.2 hold, sit 1.2 hold, stand_up 1.2, raise_flag 1.6, look 1.0
POSES: Mapping[str, Pose]       # "standing": REST, "kneeling": Pose(crouch=1), "seated": Pose(crouch=1, lean_back=-6)
def ease(x: float) -> float     # (1 - cos πx) / 2
def action_pose(action: Action, u: float, follow_lag_frac: float) -> Pose
```
Pose deltas (tuning targets): rally free arm `shoulder 120, elbow 20`, `head_tilt 8`, `torso_lean 4`, peak 0.35–0.7; bow `torso_lean 25, head_drop 3, head_tilt -10`, peak 0.4–0.6; raise_flag `near_shoulder 35` (flag props only); look `head_tilt 6`. `rally` with a flag prop raises the flag arm instead. `follow_lag_frac = FOLLOW_LAG / duration`, `FOLLOW_LAG = 0.08` s, applied to head and arm fields.

- [ ] **Step 1: Failing tests** — `test_action_starts_and_ends_at_rest` (non-hold), `test_hold_ends_at_last_key`, `test_ease_no_overshoot` (every field within the min/max of its keys), `test_spear_holder_rally_uses_free_arm`, `test_actions_are_data` (adding a dict entry in a test makes it usable without touching `figure.py`).
- [ ] **Step 2–4:** FAIL → implement → PASS + gates.
- [ ] **Step 5: Commit** `feat(characters): action and pose presets`

### Task 14: Script contract 2.3 and timelines

**Files:** Modify `history_shorts/scene_config.py` (`CharacterSpec`: `id: str | None`, `pose: str = "standing"`, `on: int | None`, `idle: bool = True`), `history_shorts/script_config.py` (`SlideAction(who, do, at, duration)`; `Slide.actions: tuple[SlideAction, ...] = ()`), `history_shorts/scene/templates.py` (default ids: `group` slots `left_1…`, `centre`, `right_1…`; `landscape` crew `crew_1`, `crew_2`), Create `history_shorts/characters/timeline.py`; Test `tests/test_v23_contract.py`, `tests/test_timeline.py`.

**Interfaces:** Produces `timeline(spec: CharacterSpec, actions: Sequence[SlideAction], rng, spec_living) -> Callable[[float], Pose]` = `add(POSES[spec.pose] then action holds, current action_pose, idle_pose if spec.idle)`.

- [ ] **Step 1: Failing tests** (one per rule in design §5):
```python
"unknown character id" → error lists ids; "unknown action" → error lists ACTIONS
overlapping actions on one id → error; at + duration > slide duration → error
stand_up with pose "standing" and no prior kneel/sit → error
actions on a non-living slide → warning; any 2.3 field with schema "2.2" → error 'requires schema_version "2.3"'
duplicate id in a slide → error; id pattern [a-z0-9_]+
test_hold_through_overlap: kneel ending at slide end; timeline(t = duration + transition) == kneeling pose
test_mirrored_rally (facing -1) raises the free arm (Review Focus 1)
```
- [ ] **Step 2–4:** FAIL → implement → PASS + gates. Update `docs/raw_requirement.md` (Appendix A.5, AC-32…AC-38, FR-50 kneeling/seated via `pose`), README (user guide + Decisions entries for the four settled calls), changelog — same commit (CLAUDE.md workflow 6).
- [ ] **Step 5: Commit** `feat(script): schema 2.3 character actions`

### Task 15: Non-looping action sprites and carriers

**Files:** Modify `history_shorts/living/characters.py`, `history_shorts/living/planes.py` (`build_stack(..., clip_seconds: float)`), `history_shorts/living/assets.py`; Test `tests/test_living_characters.py`, `tests/test_e2e_living.py` (`@pytest.mark.ffmpeg`).

**Interfaces:** A character with actions gets `SpritePlane(frames=ceil(clip_seconds*fps))` whose `render(p)` evaluates `timeline(p*clip_seconds)`; identical consecutive frames are written once and hard-linked/copied (builder's choice). `on: k` makes the character inherit layer k's bob/roll transform (Cairo transform with the carrier's `Motion` at the same loop phase) — valid only when layer k is `boat`, `sail_boat` or `elephant`, else a validation error.

- [ ] **Step 1: Failing tests** — `test_action_sprite_frame_count`; `test_action_visible_at_time`: arm box at `at + 0.5*duration` is higher than at `at - 0.1`; `test_carrier_feet_follow` (AC-36); e2e: a 2.3 script with one rally renders, ffprobe duration matches, first frame ΔE ≤ 2 vs preview.
- [ ] **Step 2–4:** FAIL → implement → PASS + gates.
- [ ] **Step 5: Commit** `feat(living): timed character actions and carriers`

### Task 16: Examples, timing report, owner review

**Files:** Modify existing slides only: `examples/trong_dong/script.json` (furnace slide), one existing boat slide in `examples/me_linh` or `examples/vuong_trieu_nu`, one existing slide with the Trưng sisters in `examples/hai_ba_trung/script.json` (bump each touched script to `"2.3"`, add `actions` and character `id`s, no new text); README render-time table.

- [ ] **Step 1:** `python -m history_shorts validate` on the three scripts — no errors.
- [ ] **Step 2:** Render each (full video), record wall time vs the same script at 2.2 (AC-38 target ≤ 1.5× per living slide) and peak RSS; write both into the README.
- [ ] **Step 3:** Extract first/middle/last frames of the animated slides; compare first frames to `--preview` and to `docs/reference/approved/*.png`; list visible differences.
- [ ] **Step 4:** Full gates. Commit `content: animated examples (schema 2.3)`.
- [ ] **Step 5:** Show the owner the clips; owner judges "natural" and "not boring". Record feedback; do not merge or push without the owner.
