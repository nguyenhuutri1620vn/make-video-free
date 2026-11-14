# Living scenes and synthesized sound effects — design

Date: 2026-11-13. Owner: Tri Nguyen. Milestone: M9 (builds on M8, spec Appendix A.2, branch `feat/m7-narration`).

## Intent

The owner has background music but no sound effects, and finds the videos too static: every slide is
one flat painting that is zoomed or panned. The goal is a video that feels **as natural as possible**:
the painting has depth and small things in it move on their own, and key moments have sound
(gong, drum, bell, a soft whoosh between scenes).

## Goals

1. **Synthesized sound effects.** A small library of named sounds generated in code (numpy/scipy),
   usable as `sfx` cues by name. No downloaded or bundled audio.
2. **Automatic whoosh** on moving transitions, so existing M8 scripts gain sound without edits.
3. **Parallax camera.** A slide's scene is rendered as depth layers that move at different speeds
   under the existing camera motions; the gold frame, seal, tag and text stay fixed like a window.
4. **Ambient motion.** Selected scene elements move on their own in short seamless loops
   (clouds drift, water shimmers, banners wave, lanterns sway and glow, birds glide, boats bob) plus
   optional light particles (falling lotus petals, drifting dust/embers).
5. **Natural feel everywhere.** Eased starts and stops, small amplitudes, smooth (not per-frame
   random) variation, slight per-hit variation in sounds, optional gentle camera shake on a hit.

## Non-goals

- Pop-up name cards and split screen (still planned separately, A.2).
- Moving characters' bodies or faces (only their flags may wave).
- Light sweep / glint across gold, lip-sync, music generation.
- Changing the approved still look: a `--preview` PNG of any slide stays identical.

## Anti-goals (failure even if it "works")

- Anything that reads as cheap animation: linear constant-speed motion, jitter, visible loop seams,
  strobing, layers sliding so far that gaps or hard edges show.
- Sounds that are harsh, clipped, obviously "beepy", or louder than the narration.
- Textures that shimmer between frames (eggshell/grain must be stable over time).
- Breaking a hard rule in CLAUDE.md: no AI, no network, no new dependencies, no crackle or black
  streaks, no hardcoded style values (amplitudes, speeds and sound parameters live in the theme
  or as named constants).

## Constraints

- Dependencies stay `pycairo`, `numpy`, `scipy`, `Pillow`, system FFmpeg; WAV writing uses the
  stdlib `wave` module.
- Determinism: every RNG derives from `[theme.seed, slide_index, layer_or_cue_index, ...]`; the
  same script renders identical frames and identical audio.
- AC-19/AC-25 still hold: a script that uses none of the new fields produces byte-identical FFmpeg
  commands and identical snapshots.
- Spec change: A.2.1 currently says "history-shorts never downloads or generates sound". The owner
  approved on 2026-11-13 that sound effects are **synthesized in code**; downloading stays banned.
  Update the spec, README "Decisions" and changelog in the same change.

## Approaches considered

| | Approach | Trade-off | Decision |
|---|---|---|---|
| A | Render each slide as a few depth PNGs plus small looping sprite sequences for moving elements; FFmpeg moves and overlays them | Real depth and ambient life at moderate render cost; more complex filter graphs | **Chosen** (owner delegated the how: "make it as natural as possible") |
| B | Redraw every frame in Python with a time parameter | Most flexible, but ~1 s per textured frame → 20+ min per 40 s video, and textures risk shimmering | Rejected |
| C | FFmpeg filters only on the flat PNG (easing, shake) | Cheapest, but still reads as one flat picture moving | Its easing/shake parts are folded into A |

## Design

### 1. Sound effects (`history_shorts/sfx.py`, new)

Pure functions `synth(name, rng, *, sample_rate, duration=None) -> np.ndarray` (float32 stereo,
peak −1 dBFS) and a writer to 48 kHz 16-bit WAV in the render temp dir.

| Name | Character | How (guidance; exact parameters are the builder's, as theme/constant values) |
|---|---|---|
| `gong` | deep bronze gong, slow bloom, ~4 s ring | sum of inharmonic partials with slightly detuned pairs (beating), pitch glide down a few cents, soft mallet attack, exponential decay per partial (high partials faster), reverb |
| `drum` | bronze-drum / big skin drum hit, ~1.5 s | low sine "thump" with fast pitch drop, filtered noise skin transient, short body resonance, reverb |
| `bell` | temple bell, ~3 s | few strong inharmonic partials (bell ratios), bright strike, long decay, reverb |
| `whoosh` | soft air swish matching a transition | band-passed noise whose centre frequency sweeps and amplitude swells then fades; stereo pan follows the transition direction |
| `wind` | gentle wind bed, length = `duration` | low-passed noise with slow smooth amplitude and cutoff modulation; seamless fades |
| `water` | soft lapping water bed, length = `duration` | filtered noise with slow random swells plus sparse small droplet blips |

- **Reverb:** convolution (`scipy.signal.fftconvolve`) with a synthesized exponentially decaying noise
  impulse response, decorrelated per channel for stereo width; wet/dry from the theme.
- **Variation:** each cue gets its own RNG (`[seed, slide_index, cue_index]`) for ±small pitch,
  level and timbre jitter, so two gongs never sound identical but renders are reproducible.
- Output must contain no NaN/inf and no samples above −1 dBFS before `gain_db`.

**Script contract (A.2.1 `sfx`, extended):** a cue has exactly one of `file` or `sound`.

```json
"sfx": [
  { "sound": "gong", "at": 0.4, "gain_db": -6, "shake": true },
  { "sound": "wind", "at": 0.0, "duration": 5.0, "gain_db": -18 }
]
```

- `sound`: one of the names above (unknown name → validation error listing allowed names).
- `duration`: required for `wind`/`water` (0.5 s … slide end − `at`), rejected for others.
- `shake`: optional, default false, valid only with `gong`/`drum`; see §4.
- Synthesized cues go through the existing mix path (after ducking, through `loudnorm`), exactly
  like file cues.

**Auto whoosh:** a slide whose `transition` is one of the moving ones (`slideleft`, `slideright`,
`slideup`, `wipeleft`, `wiperight`, `circleopen`) gets a `whoosh` cue centred on the transition,
at theme level `sfx.auto_whoosh_db` (default −14 dB), panned with the direction. `fade`,
`fadeblack`, `dissolve` and `cut` get none. A slide can turn it off with `"auto_sfx": false`.
The auto cue counts toward the 4-cue limit only for reporting, not validation.

### 2. Depth layers (parallax)

- New optional slide field `"living": true` (default false). Only living slides use §2–§4; others
  render exactly as today.
- Every scene layer type gets a default depth in a table in `scene/` (data, not code branches):
  `far` (sun/moon, sky clouds, mountains, peaks), `mid` (hills, river, citadel, temple, villages,
  map, boats, elephants, horses), `near` (characters, banners, lotus, drum, gong, lanterns,
  fallen flags, foreground ground strips). A layer may override with `"depth": "far"|"mid"|"near"`.
  Template scenes (`group`, `landscape`) expand to layers first, then use the same table.
- A living slide renders: `back.png` (lacquer ground + far layers, opaque), `mid.png` and
  `near.png` (RGBA, only their layers), and `top.png` (RGBA: waves, frame, seal, tag, title,
  subtitle, progress bar, footer). Grain (`finish`) is applied per depth layer inside its alpha
  so it moves with the painting; the warm radial sheen is applied once in `top.png` as a fixed
  light so it does not slide.
- Depth layers are drawn on a canvas larger than 1080×1920 by the travel margin of their depth,
  so moving never exposes an edge. Layers keep their original coordinates (the extra margin
  extends the ground/sky outward; nothing is re-laid out).
- **Camera motions on a living slide** reuse the existing `motion` values; each depth moves by its
  own factor of the camera travel (theme `living.depth_factor`, e.g. far 0.35, mid 0.7, near 1.0)
  with eased progress `P = (1 − cos(π·t)) / 2`. `motion: none` on a living slide still drifts very
  slightly (theme `living.idle_drift`) so the scene breathes.
- The frame/top layer never moves, so the window effect is: the painting moves inside the gold frame.
- **Composition check:** with the travel applied at t = 0 and t = 1, the existing overlap checks
  (FR-48: characters vs seal, tag, text) must still pass; validation fails otherwise.

### 3. Ambient motion (sprites and particles)

- Animatable layer types get an optional phase-aware drawer: same function, plus a `phase` in
  `[0, 1)` on the draw context. Phase changes only the moving part (cloth wave offset, water ripple
  offset, lantern swing angle and glow level, boat bob height, bird wing angle and position).
  Everything else, including textures and their RNG, is identical across phases.
- For each animated layer the renderer draws `N` phases (theme `living.loop_frames`, e.g. 48 at
  24 fps = a 2 s loop), cropped to the layer's bounding box plus margin, as an RGBA image sequence.
  Motion functions must be periodic in phase so frame N equals frame 0 (seamless loop).
- Initial animated set: `clouds` (horizontal drift, done as a slow overlay offset, no sprite),
  `river`/water parts (ripple), `banners` and character flags (wave), `lanterns` (sway + soft glow
  flicker from smooth noise), `boat`/`sail_boat` (bob and slight roll), `birds` (glide path across
  the slide plus wing beat). Others stay still.
- Particles: optional slide field `"particles": "petals"|"dust"|"embers"` drawn as a fourth RGBA
  layer sequence: a few (theme-limited count) small shapes in palette colours falling or rising on
  smooth swaying paths, generated from the slide RNG, kept out of text regions.
- Amplitudes, speeds and counts are theme values under `living`, chosen small enough to read as
  calm (e.g. flag wave ≤ a few units in the character frame, bob ≤ 6 px).

### 4. Camera shake on a hit

A cue with `"shake": true` adds a short damped shake to the depth layers (not the top layer):
amplitude theme `living.shake_px` (e.g. 6 px), decaying over ~0.4 s, smooth (sum of two low-frequency
sines with exponential envelope), starting at the cue's `at`. Only on living slides; a warning otherwise.

### 5. Assembly

- `ffmpeg.py` gains a builder for a living clip: inputs `back`, `mid`, `near`, sprite sequences
  (`-stream_loop -1` image sequences), particles and `top`; a `filter_complex` that crops/offsets
  each depth with its eased expression plus shake, overlays sprites at their crop origin within
  their depth layer, then overlays `top`, then the existing tone/fade/text_in handling.
- Clips still go through the existing `xfade`/concat join and audio mix unchanged.
- `--preview` stays a still PNG per slide (identical to today, i.e. the t = 0 frame without
  parallax offset). A new `--preview-frames` option (writes the first, middle and last frame of each
  living slide) is left to the builder's judgement.

### 6. Examples and docs

- Update `examples/hai_ba_trung` (already uses M8 effects) to use `living`, synthesized `sfx`
  (gong on the title, drum on a battle-free "uprising" moment, bell on a temple slide,
  wind/water beds where the scene shows them) and `particles` on one slide.
- Spec: new section A.4 (M9) with fields, theme block, timing rules and acceptance criteria; A.2.1
  `sfx` line updated. README: user guide for sounds and living slides, "Decisions" entries.

## Acceptance (proposed M9 criteria)

| ID | Criterion |
|---|---|
| AC-26 | Each synthesized sound renders deterministically (same seed → identical samples), has no NaN/inf, peaks ≤ −1 dBFS, and its spectral centroid / decay length fall in the documented range for its name. |
| AC-27 | A synthesized cue is audible at its offset (AC-24 method); auto whoosh appears on moving transitions only and disappears with `auto_sfx: false`. |
| AC-28 | A living slide's video: the frame/top region is pixel-stable across frames (after encoding tolerance), near layer moves more than far layer between first and last frame, and no frame shows canvas edge (border rows/columns match lacquer ground statistics). |
| AC-29 | Every sprite loop is seamless: phase-0 frame equals phase-N frame; non-moving pixels of an animated layer are identical across phases. |
| AC-30 | Scripts without `living`, `particles`, `sound`, `shake`, `auto_sfx` produce identical FFmpeg commands and snapshots (extends AC-25). |
| AC-31 | Render time of the updated `hai_ba_trung` example is measured and reported against the M8 baseline; target ≤ 3×. |

Owner sign-off: render the updated example and show it; the owner judges "natural".

## Settled after builder review (designer's calls, owner may override)

1. **Base branch:** this worktree branch was fast-forwarded to `feat/m7-narration` (0d0411d), which
   holds M8 and backlog #1–19; `develop` does not have M8 yet. M9 starts from there.
2. **Layer order vs depth:** list order always wins. Effective depth is
   `max(default_or_override, depth of the previous layer)` down the list (far < mid < near), so
   the living stack always matches the still preview's draw order. No validation error, no
   reordering of example scenes needed; the report lists layers whose depth was raised.
3. **Preview vs first frame:** `--preview` keeps today's flattened pipeline unchanged (AC-30). The
   living first frame must match the preview within ΔE ≤ 2 mean per layout region (encoding
   tolerance), not pixel-identical. Sheen goes into a separate fixed RGB layer composited with
   additive blend (`blend=all_mode=addition`), not alpha "over", so it matches the flat finish.
4. **Edges:** every depth layer is padded by its travel margin with edge replication
   (`np.pad(..., mode="edge")` on the RGBA array) — no drawer changes. Travel per depth is capped
   (far ≤ 30 px, mid ≤ 60 px, near ≤ 90 px at 1080 wide, theme values) so replicated strips stay
   short and mostly sit under the gold frame. AC-28 checks no frame shows a transparent hole.
5. **Zoom per depth:** `zoom_in`/`zoom_out` scale each depth around the shared centre by
   `1 + (zoom − 1) × depth_factor`. Use 2× prescale on depth layers (not 4×) and none on sprites
   and the top layer; measure against AC-31 and raise only if steps are visible.
6. **Schema:** the new fields (`living`, `particles`, `depth`, cue `sound`/`duration`/`shake`,
   `auto_sfx`) require `schema_version` `"2.2"`; `"2.1"` scripts keep working unchanged.
   `auto whoosh` therefore applies only to 2.2 scripts, so existing 2.1 renders do not change.
   The `hai_ba_trung` example moves to 2.2.
7. **`text_in` with `living`:** allowed. The fixed top is split into a chrome layer and a text
   layer, and the text layer reuses the existing fade-in.

## Changes made while building (2026-11-13)

- Ambient motion is applied to each animated layer's rendered pixels (bob, roll, sway, ripple warp, glow), not through a phase-aware drawer, so no drawer changed. Consequence: `banners` and character flags do not wave yet (backlog #20).
- The layer override key is `plane`, not `depth`: `lone_path` already has a numeric `depth`.
- The slide tone is applied once in FFmpeg (`colorchannelmixer`, the tone's 3x3 matrix) after the sheen and the gold frame, not per plane. Toning each plane clipped bright colours (a warm sun) that a partly transparent plane above still shows; found on `legacy_story` after the 2026-11-14 merge. Planes and the sheen are now untoned, and the frame is its own plane.
- Living planes are written to the render temp directory, not `slides/`.
- `zoompan` runs on `yuva444p` with planes of one depth grouped, for speed; spectral-centroid checks use the power spectrum.

## Left to the builder

- Exact synthesis recipes and parameter values (as long as they live in theme/constants and meet AC-26).
- Exact depth assignment of each layer type and theme default numbers.
- Sprite crop strategy, loop length, image format for sequences (PNG), temp-dir layout, caching.
- How phase is threaded into drawers (DrawContext field vs argument), keeping `figure.py` unchanged
  except for the flag drawer reading phase.
- Whether to add `--preview-frames`.
