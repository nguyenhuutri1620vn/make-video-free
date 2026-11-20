# Character and scene animation inside a slide — design

Date: 2026-11-20. Owner: Tri Nguyen. Milestone: M10 (builds on M9 living slides, schema `"2.2"`).
Base: branch `claude/character-scene-animation-plan-07ddde`, fast-forwarded to
`claude/trong-dong-video-script-43a090` (e9072dc = `feat/m7-narration` + the `furnace` layer);
`develop` does not have M7–M10.

## Intent

The owner finds the videos boring when people stand like statues. M9 made the painting deep and
moved a few objects by shifting their rendered pixels, but characters never move and fire, smoke
and flags are frozen. The owner's examples:

- Hai Bà Trưng on a boat: the water moves gently (and the people move with the boat).
- Casting a bronze drum: the furnace fire flickers.
- People make small arm/body movements when the slide needs it, e.g. raising an arm to rally
  (*hô hào*).
- Later: a person sits down or stands up.

## Goals

1. **Scene redraw motion.** Things that move in life move: furnace flames, temple incense smoke,
   flag cloth (banners layer, elephant flag, character flags). Done by redrawing the layer at a loop
   phase, not by warping pixels.
2. **Carriers.** A character standing on a boat (or other carrier) bobs and rolls with it.
3. **Character rig.** The `ancient_female` kit gets joints (head, torso, both shoulders and
   elbows, a crouch amount) so a character can be drawn in any pose; the rest pose looks exactly
   like today.
4. **Idle life.** On a living slide every character breathes and shifts slightly (seamless loop),
   so nobody is a statue.
5. **Timed actions.** A script can make a character perform a named action at a time:
   `rally`, `bow`, `kneel`, `sit`, `stand_up`, `raise_flag`, `look`. Actions are pose keyframes
   stored as data; adding one never edits drawing code.

## Non-goals

- Walking/running across the slide, crowds animating in sync choreography, horses or elephants
  walking.
- Facial animation: no lip-sync, no blinking, no expressions (faces stay as FR-43).
- Rigging a second costume kit (only `ancient_female` exists); the kit API is made ready for it.
- Changing `--preview` or the still pipeline.

## Anti-goals (failure even if it works)

- Cheap-animation feel: linear motion, robotic snaps between poses, jitter, visible loop seams,
  limbs that bend unnaturally, gaps/cracks at shoulders or elbows, a hand that leaves its spear.
- Weapons aimed or swung at anyone, combat, gore (CLAUDE.md). Spears stay upright at rest in every
  action; `rally` raises the free hand (or the flag), never the spear tip toward someone.
- Any change to the approved still look: proportions, colours, faces.
- Hard-rule breaks: no AI, no network, no new dependencies, no crackle/black streaks, no
  hardcoded style values (amplitudes, durations, angles are theme values or named constants).

## Constraints

- pycairo/numpy/scipy/Pillow/FFmpeg only. Deterministic: same script → identical frames.
- **Rest pose identity:** drawing a character with the rest pose must produce byte-identical
  pixels to today's `draw_figure`, so existing snapshots (AC-25/AC-30) do not change.
- AC-07 holds in every frame: the hand centre stays within 0.5 unit of the shaft.
- FR-48 overlap checks hold for the union bounding box of a character over all its frames.
- New fields need `schema_version` `"2.3"`; 2.2 and older scripts render exactly as before.
- Only `living: true` slides animate; on a still slide the new fields produce a validation
  warning and the character is drawn at the pose at t = 0.
- Owner's mix rules still apply (fade/dissolve transitions, no zoom/pan crop of the gold frame).

## Approaches considered

| | Approach | Trade-off | Decision |
|---|---|---|---|
| A | Rig the costume kit: parts are drawn under joint transforms from a `Pose`; poses and actions are data; characters are redrawn per frame as sprite planes | Smooth, natural, extensible to sit/stand; most work (splitting arm/robe paths into jointed pieces while keeping the rest pose identical) | **Chosen by the owner (2026-11-20)** |
| B | Cut the rendered figure into pieces (arm, torso) and rotate pixels, like M9's `transform_frame` | Fast to build; visible cracks at joints, cannot sit/stand | Rejected |
| C | Pre-draw a few poses and crossfade | Simple; jumpy and flickering, the M9 anti-goal | Rejected |

## Design

### 1. Rig (`characters/pose.py`, kit changes)

- `Pose` (frozen dataclass, all floats, rest = all zero): `head_tilt` (deg), `head_turn_y` (unit
  head drop for bowing), `torso_lean` (deg about the waist), `breath` (fraction, 0…1 small),
  `near_shoulder`, `near_elbow`, `far_shoulder`, `far_elbow` (deg), `crouch` (0 = standing,
  1 = fully kneeling/seated), `flag_wave` (loop phase for flag cloth).
- Joint pivots are named constants in the kit (shoulders at `(±12, SHOULDER_Y + 1)`, elbows on the
  existing sleeve path near y ≈ −58 for the holding arm and −55 for hanging arms, waist at
  `WAIST_Y`, neck at `CHIN_Y`). Exact pivot points are the builder's, fitted to the current paths.
- Kit part signature gains a `pose: Pose` argument (default `REST`). Each part applies
  `save / translate(pivot) / rotate / translate(-pivot)` for its joint chain; mirroring stays
  `scale(-1, 1)` in `figure.py`.
- **Arms:** each sleeve path is split at its elbow into an upper sleeve and a forearm sleeve
  (+ hand). At rest the two pieces are the current path's geometry exactly; an overlap patch
  (a small filled ellipse of the sleeve colour at the elbow, drawn under the forearm) hides any
  crack when bent. The hand and the front prop shaft are children of the near forearm, so the grip
  holds in every pose (AC-07 per frame).
- **Prop rule:** while a spear is held, the near arm's angles are clamped so the shaft stays within
  ±10° of vertical (weapon at rest). A flag may be raised (`raise_flag`).
- **Crouch (kneel/sit):** the robe from waist to hem is redrawn as a shorter, wider skirt: torso
  and head translate down by `crouch × CROUCH_DROP` (≈ 22 units), hem half-width grows by
  `crouch × CROUCH_SPREAD`, and at `crouch = 1` a folded-knee robe silhouette is used (the
  FR-50 `kneeling` pose shape). The kit provides the robe outline as a function of `crouch` that
  equals today's path at 0. Feet stay at (0, 0).
- **Breath:** torso scale `1 + breath × BREATH_SCALE` (≈ 0.6 %) about the waist, shoulders lift
  ≤ 0.3 unit; head follows.
- `figure_boxes` takes a pose; `pose_extent(style, poses)` gives the union box for validation.

### 2. Actions and idle (data, `characters/actions.py`)

- `ACTIONS: dict[str, Action]`; an `Action` is a tuple of keyframes `(t_fraction, Pose)` plus
  `hold: bool` (stay in the last pose, e.g. `kneel`, `sit`) — pure data like `ROLES`.
- Interpolation between keyframes uses ease-in-out (cosine) per joint, with a small overshoot-free
  follow-through: head and sleeves lag the torso by `FOLLOW_LAG` (≈ 0.08 s). No linear tweens.
- Initial set (angles are tuning targets, final values the builder's, judged against the anti-goals):
  - `rally`: free arm rises to ~120° with a closed fist at the cuff, head tilts up, slight forward lean; returns.
    With a flag, the flag arm rises instead (`raise_flag` behaviour). Duration default 1.6 s.
  - `bow`: torso lean ~25°, head down, returns. 1.4 s.
  - `kneel` / `sit`: crouch 0 → 1 (`kneel` keeps the torso upright; `sit` adds a slight lean back),
    hold. 1.2 s. `stand_up`: crouch 1 → 0. 1.2 s.
  - `raise_flag`: flag arm lifts the flag ~30 units, holds 0.6 s, lowers. 1.6 s.
  - `look`: head turns toward `facing` by tilt only (no profile redraw), returns. 1.0 s.
- **Idle loop** (on by default on living slides): breath sine at ~0.25 Hz rounded to a whole
  number of cycles per clip, plus a smooth tiny sway of torso (≤ 0.6°) and head (≤ 1°) from the
  character's RNG (`[theme.seed, slide_index, layer_index, character_index]`) so neighbours are out
  of step. Flag cloth waves continuously (see §3). Idle adds on top of the current action pose.
- A character that starts the slide kneeling uses `"pose": "kneeling"` (initial pose, a named
  pose in `POSES`), so `stand_up` can follow.

### 3. Scene redraw motion

- Registry entries gain an optional `draw_at(ctx, layer, phase)`. Phase 0 must equal the still
  drawer's output pixel-for-pixel; the function is periodic in phase. Textures keep their RNG so
  only the moving shape changes (no texture shimmer, M9 AC-29).
- M9's `planes.py` gets motion kind `"redraw"`: the sprite's `render(p)` calls `draw_at` cropped
  to the layer's bounding box plus margin (reuse `SpritePlane`).
- Initial set: `furnace` (flame tongues sway and change height from smooth periodic noise; halo
  glow pulses), `temple` (incense smoke curls rise and drift), `banners` (cloth wave), `elephant`
  (flag cloth), `lanterns` (flame tip flicker on top of the existing `float`). Character flags wave
  through `Pose.flag_wave` (closes M9 backlog #20).
- Cloth wave: the flag's free edge and middle are displaced by a travelling sine whose amplitude is
  zero at the pole, so the cloth stays attached.
- Amplitudes/speeds under theme `living.redraw` (e.g. `flame_px`, `smoke_rise_px_s`,
  `cloth_wave_units`).

### 4. Carriers

- A character may name a carrier layer: `"on": <layer index>` (people layer characters) — the
  character inherits that layer's ambient motion transform (bob + roll about the carrier's anchor).
- (Superseded, see "Settled" 3.) The `landscape` template's `boat_crew` characters were to be attached automatically, so
  existing living slides with boats stop showing crew drifting relative to the hull.
- The carrier transform is applied when drawing the character (Cairo transform), not by warping
  pixels.

### 5. Script contract (schema `"2.3"`)

On a slide (living only):

```json
"living": true,
"actions": [
  { "who": "trung_trac", "do": "rally", "at": 1.2 },
  { "who": "trung_nhi",  "do": "raise_flag", "at": 1.6, "duration": 2.0 },
  { "who": "elder",      "do": "stand_up", "at": 0.5 }
]
```

- `CharacterSpec` gains optional `id` (unique per slide, `[a-z0-9_]+`), `pose` (initial named
  pose, default `standing`), `on` (carrier layer index), `idle` (bool, default true on living
  slides).
- Template characters get stable ids (`group`: `left_1`, `centre`, …; `landscape`: `crew_1`,
  `crew_2`), listed in the README, so scripts can target them without spelling the template out.
- Action fields: `who` (character id), `do` (name in `ACTIONS`), `at` (s, ≥ 0), optional
  `duration` (s, overrides the default). Validation: unknown id/action → error listing allowed
  values; overlapping actions on one character → error; action ending after the slide end → error;
  `stand_up` without a prior crouched pose/action → error; any action on a still slide → warning.
- Timing is in slide seconds, like `sfx` cues, so the owner can match a gesture to the narration.

### 6. Rendering and assembly

- On a living slide, characters are removed from their scene plane and rendered as their own
  `SpritePlane`s (depth of their layer). A character with only idle motion renders one seamless
  loop (`living.loop_seconds` multiple). A character with actions renders a non-looping frame
  sequence for the clip length at the video frame rate.
- Frame sequences are cropped to the union box of the character over the clip. Characters on one
  layer whose union boxes overlap are rendered together into one sprite so draw order is kept.
- `ffmpeg.py`'s living clip builder accepts non-looping sprite sequences (no `-stream_loop`).
- `--preview` is unchanged (rest/initial pose at t = 0). `--preview-frames` (if M9 added it, else
  add it here) writes first/middle/last frames so poses can be checked as PNGs.

### 7. Examples and docs

- No new historical content: demos reuse existing slides only (CLAUDE.md "do not invent").
  Boat crew: an existing `landscape`/boat slide in `me_linh` or `vuong_trieu_nu`. Rally/bow: an
  existing slide that already shows the named women. Furnace: the existing `trong_dong` slide.
  If no existing slide fits an action, leave a marked placeholder and tell the owner.
- Spec: Appendix A.5 (M10) with fields, theme block, acceptance; FR-50 `kneeling`/`seated` poses
  marked delivered via `pose`. README user guide + Decisions; changelog.

## Acceptance (proposed M10 criteria)

| ID | Criterion |
|---|---|
| AC-32 | Rest pose and phase-0 redraw are pixel-identical to today's drawers; all existing snapshots unchanged. |
| AC-33 | For every role × facing × prop × each action at 11 sample times, the hand centre is within 0.5 unit of the shaft, and a held spear stays within ±10° of vertical. |
| AC-34 | Joint continuity: at every sampled pose, no transparent pixel appears inside the union of upper and lower sleeve masks at the elbow (no cracks). |
| AC-35 | Idle and redraw loops are seamless (frame N = frame 0) and non-moving pixels are identical across phases. |
| AC-36 | A carried character's feet stay within 1 px of the carrier's deck line in every frame. |
| AC-37 | Validation: each rule in §5 has a test; FR-48 checks use union boxes over the clip. |
| AC-38 | Render time of the updated examples is reported against M9; target ≤ 1.5× M9 per living slide. |

Owner sign-off: render the updated examples and show them; the owner judges "natural" and
"not boring".

## Delivery order (each step ends with owner review of a rendered clip)

1. **M10a — scene redraw + carriers:** `draw_at` for furnace, temple smoke, banners/elephant
   flags; crew on boats. Smallest, visible win; no rig.
2. **M10b — rig + idle:** `Pose`, jointed arms, crouch robe, breath/sway, character flag wave,
   per-character sprites.
3. **M10c — actions:** `ACTIONS` data, script contract 2.3, validation, examples.

## Settled after builder review (designer's calls, owner may override)

1. **Rest pose vs animated drawing.** `--preview` and still slides keep today's exact drawers
   (snapshots unchanged, AC-32 applies to them). Animated characters on living slides always use
   the jointed drawing, in every frame including frame 0, so there is no pop; the living first
   frame must match the preview within ΔE ≤ 2 mean per layout region (the M9 tolerance), not
   byte-identical. AC-32 is read this way.
2. **Gating.** Idle motion, redraw motion and carriers switch on only for `schema_version`
   `"2.3"`. Existing 2.2 living videos (including `trong_dong` today) render exactly as before;
   the demo examples are bumped to 2.3.
3. **Boat crew.** `scene/boat.py` draws crew and hull on one canvas (hull over the crew's feet)
   and already bobs as one sprite, so crew never drift. To animate crew, the boat layer gets a
   `draw_at` that redraws its crew with their idle pose inside the same sprite (draw order kept).
   The `on` carrier field is only for characters from a `characters`/people layer placed over a
   `boat`/`sail_boat`/`elephant` layer; §4's "template crew attach automatically" is replaced
   by this.
4. **Rally hand.** No new hand artwork: a raised arm shows the sleeve with the existing closed fist
   (`_fist`) at the cuff, used only during actions. The owner judges it at the M10c review.

## Left to the builder

- Exact pivot points, angle values, durations, amplitudes (as constants/theme values) tuned against
  the anti-goals; exact crouch robe silhouette (original artwork, FR-50 spirit).
- How `pose` threads into kit parts (argument vs context) as long as `figure.py` stays role-agnostic.
- Sprite crop/merge strategy, caching of identical frames (e.g. a held pose), temp-dir layout.
- Default ids for `group` template slots.
