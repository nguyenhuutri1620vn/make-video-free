# Artwork files: new scene objects without Python — design

Date: 2026-11-21. Owner: Tri Nguyen. Milestone: M11. Base: branch
`claude/character-scene-animation-plan-07ddde` (M10, schema 2.3, not merged yet).

## Intent

The owner will make videos on many topics, and each topic needs a few objects the library
does not have (the narration must be illustrated exactly: one slide per sentence, draw what
the line names). Today every new object is a Python module of 100–170 lines (coordinates,
palette keys, gradients, textures) plus parsing, registry and tests. The owner wants new
objects without writing code each time.

New objects become **artwork files**: JSON data in a library, drawn by one generic layer in
the lacquer style. **Claude authors the files**; the owner looks at preview PNGs and approves.

## Goals

1. A JSON artwork format that can express what existing scene layers draw: paths, ellipses,
   rectangles, flat palette colours, two-stop gradients, gold leaf and eggshell textures inside
   a shape, gold outlines, clipping a part to another part, transparency.
2. One `artwork` scene layer: `{"type": "artwork", "name": "...", "x", "y", "scale", "flip"}`.
3. Motion declared in the file (flame flicker, cloth wave, sway, smoke sway), redrawn per loop
   phase on 2.3 living slides with the M10 machinery; phase 0 is the still drawing.
4. Validation with exact locations (`artwork/<name>.json › parts[3].d: bad command 'X' at 14`),
   run by `validate` for every artwork a script uses, and by a new `artwork check` command.
5. Preview: `python -m history_shorts artwork preview --name <n> --out <png>` renders the
   object on the lacquer ground at 4 loop phases side by side; `gallery` adds a sheet of the
   whole library.
6. An authoring guide (`docs/artwork-guide.md`) so any later Claude session draws in the same
   units, palette, layering and style.

## Non-goals

- Reading real SVG/XML, Inkscape round-trips (approach B, not chosen).
- Characters or costume kits as artwork files (era packs stay Python kits).
- Porting the existing Python layers to files (they keep working unchanged).
- Any AI in the renderer: files are hand-written data; the renderer only draws them.

## Anti-goals (failure even if it works)

- Objects that do not look like lacquer painting (flat clip-art, black outlines, crackle,
  realistic shading).
- A format so loose that mistakes only show up as a broken picture in the video.
- Breaking a hard rule: new dependencies, network, hardcoded style values in code (colours
  come only from palette keys in the file), pure `#000` strokes, crackle or scratches.
- Copying existing paintings or photos (C-06): artwork is composed, not traced.

## Constraints

- Deps unchanged (pycairo, numpy, scipy, Pillow, stdlib `json`). The path-string parser is
  written in the project.
- Determinism: textures use the layer index RNG as other layers; eggshell keeps its mask-crc
  RNG and cache.
- `artwork` is a 2.3 field (2.3 is unreleased, still on this branch; no new schema version).
  A 2.2 script with an `artwork` layer is a validation error.
- CLAUDE.md drawing rules apply to the renderer: masks for textures, clip with Cairo, fill
  then outline, darkest stroke `palette.black`.

## Approaches considered

| | Approach | Trade-off | Decision |
|---|---|---|---|
| A | Project JSON format, path strings in SVG `d` syntax | Precise validation, textures and motion first-class, same style as script/theme JSON; not viewable in Inkscape (preview PNG instead) | **Chosen by the owner (2026-11-21)** |
| B | SVG subset with custom attributes | Opens in a browser, but browser view is wrong (no textures/motion), XML/style/transform parsing, weaker errors | Rejected |
| — | Python modules per object (today) / YAML | Code per object; YAML needs a new dependency | Rejected |

## Design

### 1. Library and file

- Library: `themes/son_mai/artwork/<name>.json` (`name` = `[a-z0-9_]+`, the file stem). The
  theme gains nothing else; the directory is found next to `theme.json`.
- File shape (local units; origin at the object's ground point, y up negative, like other
  layers):

```json
{
  "artwork": "1",
  "title": "Đuốc",
  "description": "A bamboo torch with a flame; original artwork.",
  "plane": "near",
  "parts": [
    {"id": "pole", "d": "M -4 0 L -3 -120 L 3 -120 L 4 0 Z",
     "fill": {"gradient": ["brown_lt", "brown"], "dir": "v"},
     "stroke": {"color": "gold_dk", "width": 1.2}},
    {"id": "flame", "d": "M -14 -120 C -16 -150 -4 -170 0 -190 C 4 -170 16 -150 14 -120 Z",
     "fill": {"color": "vermilion"},
     "motion": {"kind": "flicker", "amp": 6}},
    {"id": "core", "ellipse": [0, -135, 6, 12], "fill": {"color": "gold_lt"},
     "motion": {"kind": "flicker", "amp": 3}}
  ]
}
```

- Part fields: exactly one geometry (`d` path string; `ellipse` [cx, cy, rx, ry]; `rect`
  [x, y, w, h, r?]); optional `fill`, `stroke`, `alpha` (0–1), `clip` (id of an earlier part:
  this part is drawn clipped to that shape), `motion`. Parts draw in list order, fill then
  stroke.
- `fill`: one of `{"color": key}`, `{"gradient": [key, key], "dir": "v"|"h"}` (stops at the
  part's own bounding box; see "Settled" 1 for alpha stops and radial gradients), `{"texture": "gold_leaf", "tile"?, "worn"?}`,
  `{"texture": "eggshell", "cell"?, "gap"?}`; optional `alpha`. Colour values are palette
  keys only.
- `stroke`: `{"color": key, "width": units, "alpha"?}`; width 0.2–20.
- Path syntax: SVG `d` commands `M L H V C S Q T Z` in absolute and relative forms, and `A`
  (arcs, converted to Béziers). Numbers may use exponents.
- Limits: ≤ 1000 parts, ≤ 50 000 path numbers per file, coordinates within ±2000 units.

### 2. Rendering (`scene/artwork.py`, `artwork/` package for parsing)

- Layer `ArtworkLayer(name, x, y, scale, flip)`: `translate(x, y)`, `scale(flip*scale, scale)`
  (mirroring only by scale), draw parts. Textures: draw the part white on a fresh surface →
  mask → `fill_mask` with `gold_leaf`/`eggshell` (CLAUDE.md masks rule), then its stroke.
- The parsed file is cached per run (by path and mtime). Loading happens in validation; a
  render never meets an unvalidated file.
- Default plane from the file's `plane` (else `mid`); a layer `plane` override still wins.

### 3. Motion (2.3 living slides)

- A part with `motion` makes the layer a phase-redraw layer (`redraws()` true for that
  instance). Kinds, all zero at phase 0 and periodic:
  - `flicker` (`amp` units): every path point except those on the part's lowest edge is moved
    by smooth periodic noise (3 harmonics, phases from the layer RNG and part index), stronger
    toward the top — reuses the furnace recipe.
  - `wave` (`amp` fraction, `pole` x): cloth wave from `history_shorts/cloth.py`.
  - `sway` (`deg`, `pivot` [x, y]): the part rotates around the pivot by `deg·sin(2πp + φ)`
    minus its phase-0 value.
  - `rise` (`amp` units): smoke sway travelling up the path (temple recipe).
- Phases share the theme `living.loop_seconds` loop.

### 4. Validation and commands

- `validate` loads every artwork a script names and reports file problems at
  `artwork/<name>.json › <json path>`; unknown name lists the closest names.
- `python -m history_shorts artwork check [--name N]` validates the library (all files when no
  name). Exit codes as `validate`.
- `python -m history_shorts artwork preview --name N --out file.png [--phases 4]`.
- `gallery` gets one more sheet, `artwork`, with every library item.

### 5. Authoring guide and first content

- `docs/artwork-guide.md`: units and origin; size conventions (a person is 100 units; a
  building 300–500); layering back to front; palette keys and when to use gradient vs gold
  leaf vs eggshell; outline colours (`gold`, `gold_dk`, never `black` fills for outlines);
  motion recipes; a checklist (preview at 4 phases, compare with approved references,
  original artwork only).
- First library items: `tablet_altar` (the existing `tablet` layer redrawn as a file — proof
  the format covers a real layer) and `torch` (new, with `flicker`). Others come with topics.

## Acceptance (M11)

| ID | Criterion |
|---|---|
| AC-39 | Path parser: every command, absolute and relative, arcs, exponents; bad input reports the character position. |
| AC-40 | `tablet_altar` renders within mean ΔE ≤ 3 of the Python `tablet` layer at the same place (visual region). |
| AC-41 | Textures stay inside their part's mask; deterministic across runs. |
| AC-42 | Motion: phase 0 equals the still drawing; phase 1 equals phase 0; only moving parts change. |
| AC-43 | Every validation rule has a test with its message and location; a 2.2 script with `artwork` fails. |
| AC-44 | `artwork check`, `artwork preview` and the gallery sheet run in the e2e tests. |

Owner sign-off: preview PNGs of `tablet_altar` and `torch` side by side with the Python tablet.

## Settled after builder review (designer's calls, owner may override)

1. **Gradients with transparency and radial gradients.** `fill` gradients take optional
   `"stops": [[key, alpha, offset], ...]` (2–6 stops, offsets 0–1 ascending) instead of the
   two-key `gradient`, and `"radial": [cx, cy, r]` instead of `dir`. This covers glows (the
   tablet's candle glow, a torch halo) and bands that fade to alpha 0 (CLAUDE.md rule).
   `tablet_altar` must include its glows.
2. **Motion strength.** File values (`amp`, `deg`) are multiplied by one theme knob,
   `living.artwork_motion` (default 1.0, range 0–3), so the owner can calm or strengthen all
   artwork motion in one place. A fifth kind, `pulse` (`amp` 0–0.5), scales the part's alpha
   by `1 + amp·sin(2πp)` (halo glow), zero change at phase 0.
3. **Textured parts do not move.** A part with a `gold_leaf`/`eggshell` fill, or clipped to
   such a part, may not have `motion` (validation error naming the part); likewise a part
   clipped to a moving part may not have a texture. A waving lacquered flag is a later
   feature. Texture `tile`/`cell`/`gap` are in artwork units (scaled with the layer).

## Left to the builder

- Parser structure, arc-to-Bézier details, exact flicker point weighting.
- Cache key details, preview sheet layout.
- Exact validation wording (keep the project's existing message style).
