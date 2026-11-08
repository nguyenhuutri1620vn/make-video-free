# history-shorts — Raw Requirements

| Field        | Value                                                                 |
|--------------|-----------------------------------------------------------------------|
| Document     | Raw Requirements Specification                                        |
| Project      | history-shorts                                                        |
| Version      | 2.0.1 (amended)                                                       |
| Status       | Approved for implementation                                           |
| Owner        | Tri Nguyen                                                            |
| Last updated | 2026-11-07 (owner decisions recorded; see §6.2, §6.3, §8, §16, App. A) |
| Implementer  | Claude Code (working rules in `CLAUDE.md`)                            |
| Supersedes   | v1.1 (Pillow-only renderer, crackle effect, single static motif)      |

### Change summary from v1.1

| Area              | v1.1                                  | v2.0                                                                 |
|-------------------|---------------------------------------|----------------------------------------------------------------------|
| Vector engine     | Pillow polygons + 2× supersampling    | **Cairo (pycairo)** with cubic Béziers and native anti-aliasing      |
| Textures          | Random dots and crackle polylines     | **numpy/scipy**: gold leaf, Voronoi eggshell inlay, sheen, fine grain |
| Crackle           | Seeded dark polylines                 | **Removed** (read as dirt; owner feedback)                           |
| Characters        | Polygon figures                       | Bézier figures with folk-lacquer faces, hands gripping props         |
| Scenes            | Single motif per slide                | Layered scene graph + two approved templates (`group`, `landscape`)  |
| Primary style     | Bronze                                | **Lacquer (sơn mài)**; bronze kept as legacy                         |
| Typography        | DejaVu Serif                          | Liberation Serif (Bold titles, Italic subtitles)                     |

---

## 1. Overview

### 1.1 Problem

Producing short vertical videos (TikTok / Reels / Shorts) about Vietnamese history by hand is slow and visually inconsistent, and the available automation tools depend on generative AI, which the owner explicitly wants to avoid.

### 1.2 Solution

`history-shorts` is an offline, deterministic command-line pipeline. It reads a **script** (content, JSON) and a **theme** (visual identity, JSON), renders each slide as an illustration in the style of Vietnamese lacquer painting (*tranh sơn mài*), and assembles a 1080×1920 MP4 with FFmpeg.

The target look is fixed by two owner-approved reference images:

| Reference                                          | Template    | What it establishes                                                                                   |
|----------------------------------------------------|-------------|-------------------------------------------------------------------------------------------------------|
| `docs/reference/approved/scene_group.png`          | `group`     | Characters in a `centre_pair` formation before a gold-leaf sun, eggshell clouds and hills, ground band, flags and spears pointing outward. |
| `docs/reference/approved/scene_landscape.png`      | `landscape` | Layered karst peaks, gold-leaf moon, eggshell clouds and mid peaks, river with gold wave strokes, boats with small figures, birds. |

Both share the series chrome: lacquer ground with sheen, gold double frame with corner scrolls, red seal "SỬ VIỆT" top-left, tag pill, centred serif title and italic subtitle, and a gold water-wave band (*sóng nước*) below the safe zone.

The prototype code that produced them lives in `docs/reference/prototype/`. It is the visual source of truth for proportions, palette, and drawing order, but it is not production code.

### 1.3 Goals

| ID   | Goal                                                                                         |
|------|----------------------------------------------------------------------------------------------|
| G-01 | Render a publish-ready vertical video from JSON with a single command.                       |
| G-02 | Match the approved references in palette, composition, line quality, and material feel.     |
| G-03 | Operate fully offline, with no AI, no network calls, and no paid services.                   |
| G-04 | Produce identical output for identical input (determinism).                                  |
| G-05 | Let new videos be made by editing JSON only, using scene templates and reusable characters.  |
| G-06 | Keep the codebase typed, tested, and easy to extend with new elements, roles, and templates. |

### 1.4 Non-goals (v2.0)

- Text-to-speech, voice-over, speech recognition, or automatic captions synced to audio.
- Automatic script writing, content selection, or fact-checking.
- Downloading images, textures, fonts, or music at runtime.
- Uploading or scheduling posts.
- A GUI or web front-end.
- Character animation (walking, gesturing, lip-sync). Characters are static per slide.
- Realistic faces, portraits of identifiable real people, or tracing existing artworks.
- The close-up portrait composition (prototype sample 2 was not approved; see §16).

---

## 2. Hard Constraints

| ID   | Constraint                                                                                                                         |
|------|------------------------------------------------------------------------------------------------------------------------------------|
| C-01 | **No AI.** No LLM, image generation, TTS, ASR, or ML model, local or remote.                                                       |
| C-02 | **No network access at runtime.**                                                                                                  |
| C-03 | **Runtime dependencies are exactly:** Python ≥ 3.10, `pycairo`, `numpy`, `scipy`, `Pillow`, and the system `ffmpeg`/`ffprobe` binaries. Dev: `pytest`, `ruff`, `mypy`. Anything else needs owner approval. |
| C-04 | **No MoviePy, OpenCV, scikit-image, or browser-based renderers.** FFmpeg is called via `subprocess` with argument lists.          |
| C-05 | **Cross-platform:** Windows 10+, macOS 12+, Ubuntu 22.04+.                                                                         |
| C-06 | **Copyright-safe:** all built-in visuals are original procedural drawings. Bundled fonts are OFL-licensed. No bundled third-party art, photos, maps, textures, or music. |
| C-07 | **No hardcoded style values in rendering code.** Colours, fonts, sizes, timings, and texture parameters come from the theme; geometry comes from named constants or the scene file. |
| C-08 | **No crackle or random dark line overlays.** Surface finish is limited to sheen and fine grain (§8.5).                            |

---

## 3. Users and Use Cases

**Primary user:** one content creator publishing a recurring Vietnamese-history series, comfortable editing JSON and running Python.

| ID    | Use case                                                                                         |
|-------|--------------------------------------------------------------------------------------------------|
| UC-01 | Write a `script.json` using the `group` or `landscape` template and render a video in one command. |
| UC-02 | Preview slides as PNG before a full render.                                                      |
| UC-03 | Change characters (role, count, facing) or swap the template without touching code.              |
| UC-04 | Compose a custom scene from layers (sun, peaks, river, boats, characters) when templates are not enough. |
| UC-05 | Add background music that is looped or trimmed to the video length.                              |
| UC-06 | Keep a list of historical sources with each script and print them for the video caption.         |

---

## 4. Glossary

| Term             | Definition                                                                                                 |
|------------------|------------------------------------------------------------------------------------------------------------|
| Script           | JSON describing the video's slides, content, and sources.                                                  |
| Theme            | JSON describing palette, fonts, texture parameters, chrome, and timing.                                    |
| Slide            | One full-screen still: chrome, an illustration (scene), and text.                                          |
| Chrome           | Elements shared by every slide: ground, frame, seal, tag pill, wave band, progress bar, footer.           |
| Scene            | An ordered list of layers drawn in the visual region.                                                      |
| Template         | A named, parameterised scene (`group`, `landscape`) that expands to layers.                               |
| Layer            | One scene element: `sun`, `moon`, `clouds`, `peaks`, `hills`, `river`, `ground`, `characters`, `boat`, `birds`, `lotus`. |
| Character        | A parametric stylised figure defined by a role preset plus overrides.                                     |
| Formation        | A placement rule for characters (`centre_pair`, `line`, `v_shape`).                                       |
| Gold leaf        | Texture of jittered gold squares with thin seams and rare worn spots showing red underlayer.             |
| Eggshell inlay   | Texture (*cẩn vỏ trứng*): Voronoi fragments of ivory with thin dark gaps.                                 |
| Sheen            | Soft warm radial highlight imitating polished lacquer.                                                    |
| Safe zone        | Screen area guaranteed not to be covered by TikTok UI.                                                    |

---

## 5. Functional Requirements

Priority: **M** Must (v2.0) · **S** Should (v2.0 if time allows) · **C** Could (later).

### 5.1 CLI

| ID    | Requirement                                                                                                | Pri |
|-------|------------------------------------------------------------------------------------------------------------|-----|
| FR-01 | `python -m history_shorts render` renders a video with the options in §7.                                   | M   |
| FR-02 | `--preview` writes slide PNGs only and never invokes FFmpeg.                                                | M   |
| FR-03 | `python -m history_shorts validate` checks script, theme, and assets and reports every problem.             | M   |
| FR-04 | `python -m history_shorts gallery` renders a contact sheet of every role × facing × prop, and every layer type. | S |
| FR-05 | `--version` prints the package version.                                                                     | M   |

### 5.2 Loading and validation

| ID    | Requirement                                                                                                                         | Pri |
|-------|-------------------------------------------------------------------------------------------------------------------------------------|-----|
| FR-10 | Load UTF-8 JSON and validate against the contracts in §6 into frozen dataclasses.                                                   | M   |
| FR-11 | Collect all errors before exiting; each states file, JSON path, and reason, e.g. `script.json › slides[2].scene.layers[4].x: must be 0–1080`. | M |
| FR-12 | Resolve asset paths relative to the referencing file; they must exist.                                                              | M   |
| FR-13 | Warn (not fail) on: total duration outside 15–90 s; text auto-shrunk; missing `sources`; `"claim": true` without `source`; unknown keys. | M |
| FR-14 | Verify every font covers the full Vietnamese character set (§8.4).                                                                  | M   |

### 5.3 Slide composition

| ID    | Requirement                                                                                                                                  | Pri |
|-------|----------------------------------------------------------------------------------------------------------------------------------------------|-----|
| FR-20 | Each slide is composed in a float32 RGB numpy buffer of 1080×1920 and written as an 8-bit PNG.                                               | M   |
| FR-21 | Fixed layer order: lacquer ground → scene layers (in listed order) → wave band → sheen + grain → frame → seal → tag pill → title → subtitle → progress bar → footer. | M |
| FR-22 | Vector shapes are drawn with Cairo on transparent ARGB32 surfaces and composited into the buffer using premultiplied alpha.                 | M   |
| FR-23 | Textured regions are produced by drawing a Cairo mask and filling it with a numpy texture (§5.6).                                            | M   |
| FR-24 | Text is rendered with Pillow after all graphics, so no texture or effect touches it.                                                         | M   |
| FR-25 | Title and subtitle wrap by measured pixel width, honour explicit `\n`, and auto-shrink in 4 px steps to the theme minimum; still too long → validation error. | M |
| FR-26 | Text, seal, and tag pill stay in the safe zone (§8.2). Character head boxes stay inside the frame (inset 58); the approved `group` composition extends past the safe zone's right edge. Robes, props, and decorative layers may extend beyond the safe zone. | M   |
| FR-27 | Progress bar and footer are optional chrome (`theme.progress_bar`, `theme.footer`); both are off in the approved references.                | M   |

### 5.4 Scenes and templates

| ID    | Requirement                                                                                                                         | Pri |
|-------|-------------------------------------------------------------------------------------------------------------------------------------|-----|
| FR-30 | A slide's `scene` is either `{ "template": name, ...params }` or `{ "layers": [...] }` (§6.3).                                      | M   |
| FR-31 | Template `group` reproduces `scene_group.png`: gold-leaf sun (centre 540,650, r 300) with double ring, two eggshell clouds high left/right, far vermilion mountains with gold ridge, eggshell hills at both edges, ground band at y≈1092, characters in `centre_pair` on baseline 1100. | M |
| FR-32 | Template `landscape` reproduces `scene_landscape.png`: gold-leaf moon (770,450, r 125), birds, back karst peaks drawn individually tallest-first with gold outlines, three eggshell clouds, three eggshell mid peaks, river band (y≈940) with alternating gold wave strokes fading out at the bottom, and up to two boats with crew. | M |
| FR-33 | Template parameters: `characters` (list, for `group`); `boats` (list, for `landscape`); `sun`/`moon` on/off; `seed`. Unspecified parameters take the reference values. | M |
| FR-34 | Custom scenes list layers explicitly; every layer type in §6.3 is available.                                                       | M   |
| FR-35 | Peaks are drawn one per path, back to front, each filled before its outline, so outlines never cross.                              | M   |
| FR-36 | Mask-based layers never leak outside their shape (no texture bands outside a peak, hill, or cloud).                                 | M   |
| FR-37 | Additional templates: `procession` (characters in `line`), `council` (seated figures).                                              | C   |

### 5.5 Characters

| ID    | Requirement                                                                                                                         | Pri |
|-------|-------------------------------------------------------------------------------------------------------------------------------------|-----|
| FR-40 | A character is drawn in a local frame: feet at (0,0), height 100 units, y up negative; placed via Cairo translate/scale; `facing: -1` mirrors with `scale(-1, 1)`. | M |
| FR-41 | Drawing order: long hair (back) → prop shaft and head (back) → robe → belt and sash → sleeves → prop shaft (front, through the hand) → hand → neck → face → features → front hair → bun and hairpin → headwrap → crest. | M |
| FR-42 | Robe: crossed-collar (*giao lĩnh*) silhouette with flared hem, vertical gradient, back-fold shadow, ivory under-collar, lapel trim line, hem band with dots, thin gold outline. | M |
| FR-43 | Face: ivory oval, faint pink cheeks, thin brows, downcast closed-eye arcs, tiny nose line, small vermilion lips. No other detail.     | M   |
| FR-44 | Hands: fist shape with three finger lines and a thumb line, gripping the prop shaft, which passes in front of the sleeve. This holds for `flag`, `spear`, and `oar`. The oar shaft is the line through the hand centre (17.3, −60.5) and the blade top (25, 0), drawn from y −78 to y 6, with a front shaft segment drawn like the spear and flag. | M |
| FR-45 | Roles (presets): `leader` (vermilion robe, gold trim, gold headwrap, fan crest, flag); `general` (dark vermilion, dark-gold trim, red headwrap, spear); `general_alt` (brown robe, red trim, spear); `boat_crew` (jade robe, oar). Any field can be overridden. | M |
| FR-46 | Props: `flag` (swallow-tail banner with gold border, inner lines, roundel, finial), `spear` (leaf blade and red tassel), `oar`, `none`. | M |
| FR-47 | Formations: `centre_pair` (two front leaders 565 px, middle pair 475 px, outer pair 420 px at x ≈ 432/648, 285/795, 150/930), `line`, `v_shape`. Back rows drawn first. Outer characters face outward so props never cross the centre. | M |
| FR-48 | No character or prop overlaps the seal, the tag pill, a text box, or another character's head.                                     | M   |
| FR-49 | Character variety: per-character `seed` that varies hair bun size, sash length, and hem dot spacing within ±10 %.                  | S   |
| FR-50 | Poses `kneeling`, `seated`, `riding_elephant`; props `sword`, `drum`.                                                               | C   |
| FR-51 | Character parts may be authored as SVG in Inkscape and loaded instead of procedural parts (requires an SVG renderer approved under C-03). | C |

### 5.6 Lacquer textures and finish

| ID    | Requirement                                                                                                                          | Pri |
|-------|--------------------------------------------------------------------------------------------------------------------------------------|-----|
| FR-60 | **Lacquer ground:** vertical blend black → deep red → black with `sin` profile, modulated ±10 % by low-frequency Gaussian noise.     | M   |
| FR-61 | **Gold leaf:** square tiles (`tile` px) with tone jitter −9 %…+7 %, diagonal sine sheen ±10 %, grain ±4 %, 1.2 px seams at 82 % brightness, worn spots only near seams, coverage ≤ `worn` (default 0.05), blended 65 % toward the underlayer colour. | M |
| FR-62 | **Eggshell inlay:** jittered-grid seed points with cell size `cell` px; nearest/second-nearest distance via `scipy.spatial.cKDTree`; gap where `d2 − d1 < gap` (default 1.0 px) coloured warm dark brown; fragment tones jittered −16 %…+2 % around warm ivory. Computed only inside the mask's bounding box. | M |
| FR-63 | **Sheen:** additive warm radial highlight `(1 − d/r)²` with strength ≤ 0.10. The theme's `textures.sheen` `{x, y, r, strength}` is the default; a template may override it (`group`: 360, 700, 640, 0.10; `landscape`: 700, 520, 520, 0.08). | M |
| FR-64 | **Grain:** multiplicative fine Gaussian noise ±2.5 %.                                                                                | M   |
| FR-65 | Every texture takes a `numpy.random.Generator` seeded from theme seed + slide index + layer index; no global RNG. Exception: the eggshell RNG is `default_rng([seed, layer_index, mask_crc32])`, independent of slide index, so identical cloud and hill layers look the same on every slide. | M |
| FR-66 | Eggshell regions are cached by (mask hash, parameters) during a render run. Because the eggshell RNG does not depend on the slide index (FR-65), identical masks hit the cache across slides. | S |

### 5.7 Chrome

| ID    | Requirement                                                                                                     | Pri |
|-------|-----------------------------------------------------------------------------------------------------------------|-----|
| FR-70 | Frame: gold outer rectangle (inset 40, width 5) and dark-gold inner rectangle (inset 58, width 1.5), with corner scroll ornaments. | M |
| FR-71 | Seal: 118 px vermilion square with gold border and inner ivory hairline, two lines of text (default "SỬ", "VIỆT"), at (92,160). | M |
| FR-72 | Tag pill: vermilion rounded pill with gold border and light-gold bold text, centred at x 590, y 180.            | M   |
| FR-73 | Wave band: four rows of triple concentric half-arcs, alternating gold / dark gold, starting at y 1600.          | M   |

### 5.8 Video assembly and audio

| ID    | Requirement                                                                                                                                 | Pri |
|-------|---------------------------------------------------------------------------------------------------------------------------------------------|-----|
| FR-80 | Each slide becomes an H.264 clip with fade-in/out from the theme.                                                                          | M   |
| FR-81 | Clips are joined with the concat demuxer.                                                                                                   | M   |
| FR-82 | Output: MP4, `libx264`, `yuv420p`, 30 fps, CRF 20, `+faststart`; atomic write (temp file then rename).                                      | M   |
| FR-83 | Auto-duration when `duration` is absent: `clamp(chars × 0.08 s, 2.5 s, 6.0 s)`.                                                             | M   |
| FR-84 | Optional slow zoom per slide (`"motion": "zoom_in"`, 100 % → 106 %) via FFmpeg `zoompan` on a 2× pre-scaled PNG.                           | S   |
| FR-85 | `--music`: loop or trim to video length, fade in 0.5 s, fade out 1.5 s, volume `--music-volume` (default 0.6), AAC 192 kbps 48 kHz stereo.  | M   |
| FR-86 | Without music, add a silent AAC track.                                                                                                      | S   |
| FR-87 | `--jobs N` encodes clips in parallel (default CPU − 1).                                                                                     | S   |

### 5.9 Output and reporting

| ID    | Requirement                                                                                                    | Pri |
|-------|----------------------------------------------------------------------------------------------------------------|-----|
| FR-90 | Slide PNGs always go to `<out_dir>/slides/`; intermediates go to a temp dir removed unless `--keep-temp`.       | M   |
| FR-91 | A render report JSON next to the video: input hashes, durations, warnings, tool versions, timings, and the script's `sources`. | M |
| FR-92 | Console summary: slide count, total duration, output path, elapsed time, and a "Sources" block ready to paste into a caption. | M |

---

## 6. Data Contracts

All coordinates are canvas pixels on 1080×1920 unless stated otherwise.

### 6.1 `script.json`

| Field            | Type            | Req | Default | Notes                                   |
|------------------|-----------------|-----|---------|-----------------------------------------|
| `schema_version` | string          | yes | —       | `"2.0"`.                                |
| `title`          | string          | yes | —       | Used for default output name and report.|
| `sources`        | array of string | no  | `[]`    | Citations or URLs.                      |
| `slides`         | array of Slide  | yes | —       | 1–30 items.                             |

**Slide**

| Field      | Type    | Req | Default | Notes                                                    |
|------------|---------|-----|---------|----------------------------------------------------------|
| `tag`      | string  | no  | `""`    | ≤ 28 chars, uppercase recommended.                       |
| `title`    | string  | yes | —       | ≤ 60 chars, `\n` allowed.                                |
| `subtitle` | string  | no  | `""`    | ≤ 120 chars, `\n` allowed.                               |
| `duration` | number  | no  | auto    | 0.5–15 s.                                                |
| `scene`    | Scene   | no  | none    | §6.3. Without a scene, the slide is chrome + text only. |
| `motion`   | enum    | no  | `none`  | `none` \| `zoom_in` (FR-84).                             |
| `claim`    | boolean | no  | `false` | Marks a factual statement.                               |
| `source`   | integer | no  | —       | Index into `sources`.                                    |

### 6.2 `theme.json`

| Field            | Type      | Req | Notes                                                                                                   |
|------------------|-----------|-----|---------------------------------------------------------------------------------------------------------|
| `schema_version` | string    | yes | `"2.0"`.                                                                                                |
| `name`           | string    | yes |                                                                                                         |
| `seed`           | integer   | yes | Base seed for all textures.                                                                             |
| `palette`        | map → RGB | yes | Required keys: `black`, `deep`, `vermilion`, `vermilion_dk`, `gold`, `gold_lt`, `gold_dk`, `egg`, `brown`, `brown_lt`, `skin_line`, `pink`, `jade`. Values `[r,g,b]` 0–255. Optional keys: see the table below; each falls back to a required key when absent. |
| `fonts`          | object    | yes | `title` (bold serif), `subtitle` (italic serif), `tag` (bold serif). Paths relative to theme file.     |
| `type_scale`     | object    | yes | `tag`, `title`, `title_min`, `subtitle`, `subtitle_min` (px).                                          |
| `textures`       | object    | no  | `gold_leaf {tile, worn}`, `eggshell {cell, gap}`, `sheen {x, y, r, strength}`, `grain {strength}`. Sheen default `{x: 330, y: 760, r: 620, strength: 0.10}` (from prototype `lac.finish`). |
| `chrome`         | object    | no  | `frame`, `seal {lines, x, y, size}`, `tag {cx, y}`, `waves {y, rows}`, `progress_bar`, `footer`.        |
| `transition`     | object    | no  | `fade_in`, `fade_out` (s).                                                                             |
| `video`          | object    | no  | `fps` (30), `crf` (20).                                                                                |

**Optional palette keys.** The 13 required keys stay required. The following 14 keys are optional; when absent, each falls back to the required key shown.

| Optional key          | `son_mai` value | Fallback       | Used by                          |
|-----------------------|-----------------|----------------|----------------------------------|
| `robe_general_dk`     | [70, 14, 10]    | `vermilion_dk` | role `general` robe shadow       |
| `robe_general_alt_dk` | [56, 28, 16]    | `brown`        | role `general_alt` robe shadow   |
| `robe_crew_dk`        | [30, 50, 42]    | `jade`         | role `boat_crew` robe shadow     |
| `egg_tone`            | [226, 212, 184] | `egg`          | eggshell fragments               |
| `egg_gap`             | [58, 30, 20]    | `brown`        | eggshell gaps                    |
| `sheen`               | [255, 210, 160] | `gold_lt`      | finish sheen                     |
| `shadow`              | [10, 4, 2]      | `black`        | title drop shadow                |
| `deep_warm`           | [70, 20, 12]    | `deep`         | landscape ground mid             |
| `mountain_base`       | [60, 14, 10]    | `deep`         | far mountains gradient end       |
| `peak_base`           | [44, 11, 8]     | `deep`         | gradient peaks bottom            |
| `river_top`           | [40, 12, 8]     | `deep`         | river band top                   |
| `hull_dk`             | [40, 20, 12]    | `black`        | boat hull bottom                 |
| `leaf_dk`             | [24, 40, 34]    | `jade`         | lotus leaf                       |
| `petal_tip`           | [240, 170, 150] | `pink`         | lotus petal tip                  |

**Default theme `themes/son_mai/theme.json`** (values from the approved prototype):

```json
{
  "schema_version": "2.0",
  "name": "Sơn mài — Sử Việt",
  "seed": 40,
  "palette": {
    "black": [16, 9, 7], "deep": [48, 14, 9],
    "vermilion": [176, 36, 24], "vermilion_dk": [112, 22, 14],
    "gold": [212, 166, 76], "gold_lt": [242, 210, 130], "gold_dk": [138, 96, 40],
    "egg": [236, 225, 200], "brown": [92, 50, 28], "brown_lt": [128, 74, 40],
    "skin_line": [96, 52, 32], "pink": [224, 140, 120], "jade": [52, 84, 70],
    "robe_general_dk": [70, 14, 10], "robe_general_alt_dk": [56, 28, 16], "robe_crew_dk": [30, 50, 42],
    "egg_tone": [226, 212, 184], "egg_gap": [58, 30, 20], "sheen": [255, 210, 160],
    "shadow": [10, 4, 2], "deep_warm": [70, 20, 12], "mountain_base": [60, 14, 10],
    "peak_base": [44, 11, 8], "river_top": [40, 12, 8], "hull_dk": [40, 20, 12],
    "leaf_dk": [24, 40, 34], "petal_tip": [240, 170, 150]
  },
  "fonts": {
    "title": "fonts/LiberationSerif-Bold.ttf",
    "subtitle": "fonts/LiberationSerif-Italic.ttf",
    "tag": "fonts/LiberationSerif-Bold.ttf"
  },
  "type_scale": { "tag": 34, "title": 92, "title_min": 64, "subtitle": 46, "subtitle_min": 34 },
  "textures": {
    "gold_leaf": { "tile": 34, "worn": 0.05 },
    "eggshell": { "cell": 16, "gap": 1.0 },
    "sheen": { "x": 330, "y": 760, "r": 620, "strength": 0.10 },
    "grain": { "strength": 0.025 }
  },
  "chrome": {
    "frame": { "enabled": true },
    "seal": { "lines": ["SỬ", "VIỆT"], "x": 92, "y": 160, "size": 118 },
    "tag": { "cx": 590, "y": 180 },
    "waves": { "y": 1600, "rows": 4 },
    "progress_bar": { "enabled": false },
    "footer": { "enabled": false, "text": "" }
  },
  "transition": { "fade_in": 0.3, "fade_out": 0.3 },
  "video": { "fps": 30, "crf": 20 }
}
```

### 6.3 Scene

**Template form**

```json
{ "template": "group", "characters": [ { "role": "leader" }, { "role": "leader" },
  { "role": "general_alt" }, { "role": "general_alt" }, { "role": "general" }, { "role": "general" } ] }
```

```json
{ "template": "landscape",
  "boats": [
    { "x": 290, "y": 1056, "scale": 1.5,  "crew": [ { "role": "leader", "facing": 1 }, { "role": "boat_crew", "facing": -1 } ] },
    { "x": 780, "y": 1104, "scale": 1.25, "crew": [ { "role": "general" }, { "role": "boat_crew" } ] }
  ] }
```

**Layer form** — `{ "layers": [ ... ] }`, drawn in order. Layer types:

| `type`       | Fields                                                                                  | Texture        |
|--------------|-----------------------------------------------------------------------------------------|----------------|
| `sun`/`moon` | `x`, `y`, `r`, `rings` (0–2); optional `tile`, `worn`                                   | gold leaf      |
| `clouds`     | `items: [{x, y, scale, flip}]`, `outline` (`gold` \| `gold_dk`); optional `cell`, `gap`   | eggshell       |
| `mountains`  | `y`, `amp` — rolling far range, gradient fill, gold ridge                              | flat gradient  |
| `peaks`      | `y`, `items: [{x, height, width}]`, `fill` (`gradient` \| `eggshell`); with `fill: eggshell`, optional `cell`, `gap` | per `fill` |
| `hills`      | `side` (`left` \| `right`), `base`, `top`; optional `cell`, `gap`                       | eggshell       |
| `river`      | `y`, `height`                                                                           | flat + strokes |
| `ground`     | `y`, `height`                                                                           | flat + strokes |
| `characters` | `formation` or explicit `items: [{role, x, baseline, height, facing, ...overrides}]`; `baseline` (default 1100) | — |
| `boat`       | `x`, `y`, `scale`, `crew: [Character]`                                                  | —              |
| `birds`      | `items: [{x, y, scale}]`                                                                | —              |
| `lotus`      | `x`, `y`, `scale`                                                                       | —              |

**Character**

| Field      | Type   | Req | Default         | Notes                                                      |
|------------|--------|-----|-----------------|------------------------------------------------------------|
| `role`     | enum   | yes | —               | `leader` \| `general` \| `general_alt` \| `boat_crew`.     |
| `facing`   | int    | no  | auto (outward)  | `1` prop on the right, `-1` prop on the left.              |
| `robe`, `robe_dk`, `trim`, `wrap` | palette key | no | preset | Overrides.                                   |
| `prop`     | enum   | no  | preset          | `flag` \| `spear` \| `oar` \| `none`.                      |
| `crest`    | bool   | no  | preset          | Fan crest on the bun.                                      |
| `x`, `baseline`, `height` | number | no | formation | Explicit placement.                                   |

Optional texture overrides (`tile`, `worn`, `cell`, `gap`) take the same units as the corresponding `textures` entries in the theme and override them for that layer only. Boat `crew` items follow the Character contract above; their `x`, `baseline`, and `height` are canvas pixels, and when omitted they are computed from the boat's slots.

---

## 7. CLI

```
python -m history_shorts render   --script PATH [--theme PATH] [--out PATH]
                                  [--music PATH] [--music-volume FLOAT]
                                  [--preview] [--keep-temp] [--jobs N]
                                  [--debug-safe-zone] [--verbose]
python -m history_shorts validate --script PATH [--theme PATH]
python -m history_shorts gallery  [--theme PATH] [--out PATH]
python -m history_shorts --version
```

Default theme: `themes/son_mai/theme.json`. Default output: `output/<slug(title)>.mp4`.

| Exit | Meaning                                  |
|------|------------------------------------------|
| 0    | Success (warnings may be printed).       |
| 1    | Internal error.                          |
| 2    | Invalid CLI usage.                       |
| 3    | Validation failed.                       |
| 4    | FFmpeg missing or < 4.4.                 |
| 5    | FFmpeg failed.                           |
| 130  | Interrupted; temp files cleaned.         |

---

## 8. Rendering Specification

### 8.1 Canvas

1080×1920, sRGB. Internal buffer float32 0–1. Cairo surfaces ARGB32 premultiplied, converted with BGRA → RGB channel reorder.

### 8.2 Safe zone and regions

| Edge   | Reserved |   | Region   | Band (y px) | Content                          |
|--------|----------|---|----------|-------------|----------------------------------|
| Top    | 160      |   | Header   | 160 – 290   | Seal, tag pill                   |
| Bottom | 420      |   | Visual   | 290 – 1150  | Scene                            |
| Left   | 80       |   | Title    | 1170 – 1400 | Title (1–2 lines)                |
| Right  | 150      |   | Subtitle | 1400 – 1500 | Subtitle                         |
|        |          |   | Chrome   | 1540 – 1920 | Wave band (outside safe zone)    |

Text is centred on x = 505 (the safe zone's centre), not 540.

**Safe-zone check (FR-26).** The check applies to text, the seal, and the tag pill. Character head boxes stay inside the frame (inset 58, i.e. x 58–1022, y 58–1862); the approved `group` composition extends past the safe zone's right edge. Robes and props may extend past the safe zone.

**Title placement.** A one-line title has its top at y 1215. A two-line title has its line tops at 1190 and 1190 + step, where step = round(size × 102 / 92).

**Subtitle placement.** The first subtitle line's top = last title line top + 128. Additional subtitle lines step by round(size × 56 / 46).

**Progress bar (off by default).** y 1540, height 4, x 80–930. Track in `gold_dk` at alpha 0.4; fill in `gold` for (i + 1) / n of the track.

**Footer (off by default).** `tag` font, `gold_dk`, centred at x 540, top at y 1830.

### 8.3 Line weights (at canvas scale)

Frame 5 / 1.5 px; scene outlines 1.8–2.5 px gold; character outlines 0.5 unit (≈ 2.8 px at 565 px height); facial lines 0.3–0.45 unit. Never use pure black (#000) for strokes; darkest stroke colour is `palette.black`.

### 8.4 Typography

- Title: Liberation Serif Bold, `type_scale.title`, first line `egg`, second line `gold_lt`, 3 px drop shadow in `palette.shadow` (`#0A0402` in `son_mai`).
- Subtitle: Liberation Serif Italic, no shadow. The colour continues the title alternation: two title lines (`egg`, `gold_lt`) give an `egg` subtitle; one title line gives a `gold_lt` subtitle. Placement: §8.2.
- Tag: Liberation Serif Bold in the pill.
- Glyph check string: `ĂÂĐÊÔƠƯăâđêôơư` plus every tone mark on `aeiouy` and their circumflex/horn/breve forms, both cases.
- Emoji are not supported in rendered text; validation rejects them.

### 8.5 Surface finish

Allowed: sheen (FR-63) and grain (FR-64). Forbidden: crackle lines, scratches, random dark strokes, vignette darker than `palette.black` (C-08).

---

## 9. Non-Functional Requirements

| ID     | Category        | Requirement                                                                                     |
|--------|-----------------|-------------------------------------------------------------------------------------------------|
| NFR-01 | Performance     | One slide ≤ 6 s; `--preview` of 10 slides ≤ 60 s; full 10-slide video ≤ 120 s on a 4-core laptop. |
| NFR-02 | Determinism     | Same inputs + same dependency versions → byte-identical PNGs.                                   |
| NFR-03 | Memory          | Peak RSS ≤ 1.5 GB for a 10-slide render.                                                        |
| NFR-04 | Portability     | `pathlib` only; no shell syntax; works with paths containing spaces and Vietnamese characters.  |
| NFR-05 | Reliability     | No partial file at `--out` on failure.                                                          |
| NFR-06 | Usability       | Every error says what, where, and how to fix.                                                   |
| NFR-07 | Maintainability | Full type hints, `mypy --strict` clean, `ruff` clean.                                           |
| NFR-08 | Coverage        | ≥ 85 % lines on `config`, `text`, `layout`, `textures`, `characters`, `scene`.                 |
| NFR-09 | Security        | No `shell=True`; no network modules; input files never executed.                                |

---

## 10. Architecture

### 10.1 Pipeline

```
script.json + theme.json
   │
   ▼
config ──► scene.templates (expand) ──► layout (regions, safe zone)
   │
   ▼  per slide
compose:
  textures.lacquer_ground ─► buffer
  for layer in scene: draw.<layer>  (Cairo shapes / masks) ─► textures.* ─► composite
  chrome.waves ─► textures.finish (sheen, grain) ─► chrome.frame
  text (Pillow): seal, tag, title, subtitle
   │
   ▼
slides/NN.png ──► video (FFmpeg: clip, concat, music) ──► out.mp4 + report.json
```

### 10.2 Repository layout

```
history-shorts/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── docs/
│   ├── raw_requirement.md
│   └── reference/
│       ├── approved/            # scene_group.png, scene_landscape.png (visual source of truth)
│       ├── prototype/           # throwaway prototype code that produced them
│       └── legacy/              # v1 bronze sample
├── history_shorts/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py               # load + validate → dataclasses
│   ├── errors.py
│   ├── layout.py               # safe zone, regions
│   ├── canvas.py               # pycairo wrapper: surfaces, paths, gradients, to_premul, mask
│   ├── compose.py              # buffer, compositing, slide assembly
│   ├── textures.py             # lacquer_ground, gold_leaf, eggshell, finish
│   ├── text.py                 # wrap, shrink, glyph check, Pillow drawing
│   ├── chrome.py               # frame, seal, tag pill, waves
│   ├── scene/
│   │   ├── __init__.py         # layer registry
│   │   ├── templates.py        # group, landscape
│   │   ├── sky.py              # sun, moon, birds
│   │   ├── terrain.py          # mountains, peaks, hills, river, ground
│   │   ├── clouds.py
│   │   ├── boat.py
│   │   └── lotus.py
│   ├── characters/
│   │   ├── __init__.py         # CharacterSpec, ROLES
│   │   ├── figure.py           # drawing order FR-41
│   │   ├── parts.py            # hair, robe, sleeves, belt, head, props
│   │   └── formations.py
│   ├── ffmpeg.py
│   ├── video.py
│   └── report.py
├── themes/
│   └── son_mai/
│       ├── theme.json
│       └── fonts/              # Liberation Serif + LICENSE
├── examples/
│   ├── nu_tuong/script.json    # group template
│   └── me_linh/script.json     # landscape template
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_text.py
    ├── test_layout.py
    ├── test_textures.py
    ├── test_characters.py
    ├── test_scene.py
    ├── test_compose_snapshot.py
    ├── test_ffmpeg_commands.py
    ├── test_no_network_imports.py
    └── test_e2e.py             # @pytest.mark.ffmpeg
```

---

## 11. Error Handling

| Situation                         | Behaviour                                                         | Exit |
|-----------------------------------|-------------------------------------------------------------------|------|
| Invalid JSON                      | File, line, column.                                               | 3    |
| Schema violation                  | All violations with JSON paths.                                   | 3    |
| Missing asset                     | Absolute resolved path.                                           | 3    |
| Font lacks Vietnamese glyphs      | List missing characters.                                          | 3    |
| Text cannot fit                   | Slide, field, suggestion.                                         | 3    |
| Character overlaps protected area | Slide, character index, bounding boxes.                           | 3    |
| pycairo / scipy import fails      | Install hint per OS.                                              | 1    |
| FFmpeg missing / old              | Install hint per OS.                                              | 4    |
| FFmpeg failure                    | Last 20 lines of stderr; full command with `--verbose`.          | 5    |

---

## 12. Testing Strategy

| Level     | Scope                                                                                                                  |
|-----------|------------------------------------------------------------------------------------------------------------------------|
| Unit      | Validation, auto-duration, wrapping, shrink, safe-zone maths, texture statistics (mean tone, gap ratio), mask containment. |
| Character | Parametrised over role × facing × prop × crest: renders without error; bounding box inside expected box; hand centre within 0.5 unit of shaft. |
| Snapshot  | Render both example scripts' first slide; compare SHA-256 against baselines keyed by dependency versions.             |
| Visual    | Perceptual check against `docs/reference/approved/*.png`: mean colour per region within ΔE 8; manual owner sign-off. |
| Command   | Exact FFmpeg argument lists, without running FFmpeg.                                                                   |
| E2E       | Render both examples; `ffprobe` checks resolution, fps, codec, pix_fmt, duration ± 0.1 s.                             |
| Guard     | No network imports; no `shell=True`; no crackle function or dark random strokes in `textures.py`.                     |

---

## 13. Acceptance Criteria

| ID    | Criterion                                                                                                                  | Covers         |
|-------|----------------------------------------------------------------------------------------------------------------------------|----------------|
| AC-01 | `render --script examples/nu_tuong/script.json` exits 0 and produces an MP4.                                               | FR-01, 80–82   |
| AC-02 | `ffprobe`: 1080×1920, 30 fps, h264, yuv420p, duration = Σ slides ± 0.1 s.                                                   | FR-82–83       |
| AC-03 | First slide of `nu_tuong` matches `scene_group.png` in composition, palette, and line quality (owner sign-off; region ΔE ≤ 8). | FR-31, 40–47 |
| AC-04 | First slide of `me_linh` matches `scene_landscape.png` likewise.                                                           | FR-32, 35–36   |
| AC-05 | No crossing peak outlines and no texture outside its mask (automated).                                                     | FR-35–36       |
| AC-06 | No character overlaps seal, tag, text, or another head (automated).                                                        | FR-48          |
| AC-07 | Every role × facing × prop renders; hands sit on shafts, including the `oar` shaft through (17.3, −60.5) and (25, 0) (automated). | FR-40–46       |
| AC-08 | Vietnamese text renders with zero missing glyphs.                                                                          | §8.4           |
| AC-09 | Changing `palette.gold` changes all gold elements with no code change.                                                     | C-07           |
| AC-10 | `--preview` creates PNGs and never spawns FFmpeg.                                                                          | FR-02          |
| AC-11 | `validate` on a script with three errors reports all three, exit 3; missing sources only warns.                           | FR-11, 13      |
| AC-12 | Two renders of the same input give byte-identical PNGs.                                                                    | NFR-02         |
| AC-13 | `--music` yields audio equal to video length with fade-out.                                                                | FR-85          |
| AC-14 | Without FFmpeg on PATH: exit 4 with install guidance.                                                                      | §11            |
| AC-15 | `pytest`, `ruff check`, `mypy --strict history_shorts` pass; guard tests pass.                                             | NFR-07–09, C-08 |

---

## 14. Milestones

| Milestone                  | Deliverables                                                                                   | Exit criteria          |
|----------------------------|------------------------------------------------------------------------------------------------|------------------------|
| M1 — Foundation            | Scaffold, `config`, `errors`, `layout`, `text`, `canvas`, theme `son_mai`, unit tests.        | AC-08, AC-11           |
| M2 — Textures & chrome     | `textures`, `compose`, `chrome`; slide with chrome + text only.                                | AC-09, AC-12 (partial) |
| M3 — Characters            | `characters/*`, formations, `gallery` command.                                                | AC-06, AC-07           |
| M4 — Scenes & templates    | `scene/*`, `group` and `landscape` templates, both example scripts, `--preview`.              | AC-03, AC-04, AC-05, AC-10 |
| M5 — Video                 | `ffmpeg`, `video`, music, report, E2E tests.                                                  | AC-01, AC-02, AC-13, AC-14 |
| M6 — Polish                | `--jobs`, `zoom_in` motion, caching, README, final QA.                                        | All AC                  |

Every milestone ends with green tests and a CHANGELOG entry. Visual milestones (M2–M4) end with preview PNGs shown to the owner.

---

## 15. Assets, Licensing, and Historical Content

- Fonts: Liberation Serif (SIL OFL 1.1), bundled with licence. No other bundled fonts.
- All scene elements and characters are original procedural drawings; reference images inspire, they are not traced.
- Optional future textures must be CC0 (e.g. ambientCG, Poly Haven) or the owner's own photographs, listed in `assets/SOURCES.md`.
- No bundled music.
- Scripts carry `sources`. Statements from folk records or temple legends are worded as such ("theo thần tích", "theo truyền thuyết").
- Costume and props are stylised, not reconstructions; slides must not claim historical exactness for them.

---

## 16. Risks and Open Questions

| ID   | Item                                                                                       | Mitigation / default                                                              |
|------|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| R-01 | Company machine may block installing pycairo, scipy, or FFmpeg.                            | Verify in M1; document conda / portable FFmpeg options in README.                 |
| R-02 | Cairo or numpy version changes alter pixels and break snapshots.                          | `pyproject.toml` declares ranges valid on Python 3.10 (`numpy>=1.26`, `scipy>=1.11`, `Pillow>=10.1`, `pycairo>=1.25`). `constraints.txt` pins the dev versions (pycairo 1.29.2, numpy 2.4.6, scipy 1.17.1, Pillow 13.0.0); those pins need Python ≥ 3.11, so snapshot baselines exist only for pinned sets. |
| R-03 | All characters share one face and silhouette.                                              | FR-49 variation now; SVG-authored parts later (FR-51).                            |
| R-04 | Eggshell computation is slow on large masks.                                               | Bounding-box restriction (FR-62) and caching (FR-66).                             |
| R-05 | Close-up portrait composition (prototype sample 2) was not approved.                      | Out of scope for v2.0; revisit with redesigned face and hands.                    |
| Q-01 | Should the legacy bronze theme be migrated to the v2 engine?                               | Default: no; keep in `docs/reference/legacy/` only.                               |
| Q-02 | Should text appear inside scenes (banners, scrolls)?                                       | Default: no for v2.0.                                                             |

---

## Appendix A — v2.1 storyboard (planned, not in v2.0)

Recorded so later work does not contradict it. Nothing here is implemented in v2.0, and C-01 and C-02 stay unchanged.

**A.1 Narration.** The owner runs VoiceStudio separately; history-shorts runs no TTS (C-01). Planned behaviour:

- Export one narration `.txt` per segment, using `[pause Nms]` markers and no custom emotion tags.
- Mix the owner's voice files into the video.
- Duck the music under the voice.
- Fit each slide's duration to the length of its voice file.

**A.2 Motions.** Pan, pop-up name cards, colour-tone shift, split screen.

**A.3 Poses.** Kneeling and riding an elephant (see FR-50).
