# Artwork guide (M11)

How to draw a new scene object as a JSON file instead of Python. Read this before writing
any file in `themes/son_mai/artwork/`. The format is specified in
`docs/superpowers/specs/2026-11-21-artwork-files-design.md` and spec Appendix A.6.

## Workflow

1. Write `themes/son_mai/artwork/<name>.json` (`name`: `[a-z0-9_]`, 1–40 characters).
2. `python -m history_shorts artwork check --name <name>` until it prints `<name>: ok`.
3. `python -m history_shorts artwork preview --name <name> --out output/<name>.png`, open
   the PNG, compare with `docs/reference/approved/*.png`, fix, repeat.
4. Use it in a 2.3 script: `{"type": "artwork", "name": "<name>", "x": 540, "y": 1100, "scale": 1.5}`
   (`flip: -1` mirrors it).
5. `python -m history_shorts gallery` also writes `gallery_artwork.png` with the whole library.

## Units and origin

- One unit is one pixel at `scale` 1. The origin (0, 0) is where the object stands on the
  ground; y goes **up negative**, like every other layer (`d: "M -10 0 L -10 -120 …"`).
- Sizes that sit well with the rest of the library:

| Thing | Size in units |
|---|---|
| a person (the character kit) | 100 tall |
| altar / tablet (`tablet_altar`) | 280 wide, 340 tall |
| torch (`torch`) | 16 wide, 240 tall |
| boat hull | 400 wide |
| a building gate | 300–500 wide |

Scripts then scale with `scale` (1.0–2.0 typical) so one file serves near and far.

## Parts and order

- Parts draw in list order: back to front, each fill then outline. Put glows and halos
  first, the body next, details and outlines on top, flames last.
- One geometry per part: `d` (SVG path: `M L H V C S Q T A Z`, absolute or relative),
  `ellipse` `[cx, cy, rx, ry]` or `rect` `[x, y, w, h, r?]`.
- `clip`: the part is drawn only inside an earlier part's shape (bands on a vase, lines on a
  plaque). Never post-crop by hand.
- No text, no faces, no likeness of a real painting or photo: compose shapes yourself (C-06).

## Colour and surface (lacquer look)

- Only palette keys from `themes/son_mai/theme.json` (`vermilion`, `vermilion_dk`, `gold`,
  `gold_lt`, `gold_dk`, `egg`, `egg_tone`, `brown`, `brown_lt`, `black`, …).
- Bodies: two-key vertical gradient light-to-dark (`["vermilion", "vermilion_dk"]`), like the
  approved references. Wood: `["brown_lt", "brown"]`.
- Outlines: `gold` 1.0–1.6 for main shapes, `gold_dk` 0.8–1.2 for inner lines. Never use
  `black` as an outline colour and never pure black anywhere.
- Gold leaf (`{"texture": "gold_leaf", "tile": 20}`) for discs, plaques, crowns, sacred metal.
  Eggshell (`{"texture": "eggshell", "cell": 12}`) for clouds, hills, stone, pale panels.
  Sizes are in units. Textured parts never move.
- Glows: radial `stops` fading to alpha 0 (`[["gold_lt", 0.3, 0], ["gold_lt", 0, 1]]`). Any
  band that ends above the ground fades to 0, never a hard stop.
- No crackle, scratches or random dark strokes.

## Motion (2.3 living slides only)

| Kind | Fields | Use for |
|---|---|---|
| `flicker` | `amp` (units) | flames: the top moves, the base stays |
| `wave` | `amp` (fraction of width, ≤ 0.5), `pole` (x) | cloth, flags: fixed at the pole |
| `sway` | `deg`, `pivot` [x, y] | lanterns, branches, hanging things |
| `rise` | `amp` (units) | smoke curls: a wave travelling up |
| `pulse` | `amp` (≤ 0.5) | halos and glows brightening and dimming |

Keep it calm: flame `amp` 2–8, smoke 3–8, cloth 0.05–0.15, sway 2–6°, pulse 0.1–0.3. The
theme knob `living.artwork_motion` scales everything. Example flame:

```json
{"id": "flame", "d": "M -13 -170 C -19 -196 -6 -216 0 -242 C 6 -216 19 -196 13 -170 Z",
 "fill": {"color": "vermilion"}, "motion": {"kind": "flicker", "amp": 6}}
```

## Checklist before using a new file

- [ ] `artwork check` is clean.
- [ ] The preview at 4 phases looks calm, nothing detaches, no seams.
- [ ] Colours and outlines match the approved references; no black outlines.
- [ ] Original composition; no text, faces or traced artwork.
- [ ] `title` (Vietnamese) and `description` say what it is.
