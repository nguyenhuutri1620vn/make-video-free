# Male warrior kit (Đại Việt and northern armies) — design

Date: 2026-11-22. Owner: Tri Nguyen. Milestone: M12. Base: `develop` after M11 and the
Cổ Loa artwork merge.

## Intent

Every character today is the `ancient_female` kit (Hai Bà Trưng era). The owner wants a
**reusable set of male characters** for many future videos: a Vietnamese general in the
manner of Ngô Quyền (938) and, in general, the soldiers of the northern invading armies
(Southern Han, Song, Yuan…), plus ordinary soldiers on both sides. It must work with the
M10 rig and actions (bow, rally, kneel…) and fit the approved lacquer style.

## Goals

1. One new costume kit, `warrior_male`, whose parts come in **variants** chosen by data:
   headwear (`topknot_wrap` khăn chít, `viet_helmet` mũ trụ Đại Việt, `northern_helmet`
   mũ trụ phương Bắc, `cap` soldier's cap), body (`tunic` áo vải, `lamellar` giáp vảy,
   `lamellar_cape` giáp vảy + áo choàng), props (existing `spear`, `flag`, `none`, plus
   `sword_sheathed` gươm trong vỏ, `shield`).
2. Roles as data (no figure code per role): `viet_general` (Ngô Quyền-style leader:
   Đại Việt helmet, lamellar with cape, flag or sheathed sword), `viet_soldier`
   (cap or wrap, tunic, spear), `northern_general` (northern helmet, lamellar with cape,
   sheathed sword), `northern_soldier` (northern helmet, lamellar, spear or shield).
3. Same local frame and **same joint names** as `ancient_female_rig` (torso, head,
   near/far arm and forearm, hand, prop, skirt), so all M10 poses, idle motion and actions
   work unchanged; FR-48 boxes via `KitRig.body_boxes`.
4. Sides are told apart by **helmet silhouette, armour cut, colours and banners**, never by
   faces or body features.
5. Gallery: the character sheet gains the four new roles × facing × props; preview PNGs
   for owner approval before the kit is final.

## Non-goals

- Riding horses or elephants, archery poses, combat actions.
- Faces with expressions, beards or portrait likeness; named individuals beyond role presets.
- Other eras' kits (Lý–Trần court, Nguyễn, modern) — later, by adding variants/kits.
- Changing `ancient_female` or any approved composition.

## Anti-goals

- Caricature or ethnic stereotyping of either side (faces identical across sides).
- Violence: weapons always at rest; no wounds, no fighting poses.
- Realistic armour rendering that breaks the flat lacquer look; black outlines; crackle.
- A "Ngô Quyền" that claims to be a portrait (C-06): it is a stylised general.

## Constraints

- No new dependencies; Cairo drawing like the existing kit; mypy strict; FR-41-style draw
  order documented in the kit; geometry as named constants.
- Colours only from the palette. Proposed **new optional palette keys** (with fallbacks, so
  older themes still load): `steel` (cool grey for northern armour), `steel_dk`,
  `indigo` (northern robes), `indigo_dk`. Owner approval of these keys is part of approving
  this design (CLAUDE.md: palette changes need owner approval).
- Rest pose of every role drawn with `pose=None` (still) and with the rig must match within
  the M10 tolerance (mean < 1/255, max < 0.25).
- AC-07 holds for every role/prop: the hand stays on the shaft; a sheathed sword hangs at
  the hip (no grip); a shield is carried on the far arm.

## Approaches considered

| | Approach | Trade-off | Decision |
|---|---|---|---|
| A | Two kits (`dai_viet_male`, `northern_army`) | Most distinct silhouettes; roughly double the code; a new era means another kit | Rejected |
| B | One male kit with variant parts; roles pick variants | Most roles per line of code, reuses the rig; sides share body shape and differ in helmet/armour/colour/banner | **Chosen by the owner (2026-11-22)** |
| C | Characters as artwork JSON files | No code, but no rig or actions | Rejected |

## Design

### 1. Kit structure (`characters/kits/warrior_male.py`, `warrior_male_rig.py`)

- Proportions (100 units tall, feet at 0): head centre ≈ −88, shoulders ≈ −78 and wider
  than the female kit (half-width ≈ 15), waist ≈ −52, hem or armour skirt to ≈ −14 with
  trousers and boots below (no long robe). Exact numbers come from the approved prototype.
- `CharacterStyle` gains `variant: Mapping[str, str]` (part slot → variant name); role
  presets set it; a spec may override single slots (`"helmet": "cap"`).
- Draw order (FR-41 analogue): back hair/cape → prop back → legs and boots → body (tunic or
  armour) → belt → sleeves/arms → front prop shaft → hand → neck → face → features →
  headwear → crest/plume. Face and features reuse the female kit's minimal face (same
  shapes), so faces are identical across sides.
- Variant registry: `VARIANTS: Mapping[slot, Mapping[name, PartFn]]` inside the kit; the
  kit's part for a slot dispatches on `style.variant[slot]`. Adding a variant is a function
  plus a registry line; `figure.py` never changes.
- Props: `sword_sheathed` (scabbard at the near hip, drawn with the body; no hand grip;
  the near hand hangs) and `shield` (round shield on the far forearm, drawn after the far
  sleeve). `spear` and `flag` reuse the female kit's shaft geometry at the male hand
  centre.

### 2. Rig

- Same joint names and transform functions as `ancient_female_rig`; pivots refit to the
  male proportions (constants). Armour skirt behaves like the robe skirt (cut at the belt,
  squashes for `kneel`/`sit`); legs fold under the skirt when crouching.
- `KitRig.body_boxes` split by joint as in M10.

### 3. Roles and palette

| Role | Helmet | Body | Default prop | Colours (palette keys) |
|---|---|---|---|---|
| `viet_general` | `viet_helmet` with plume | `lamellar_cape` | `flag` | vermilion cape, gold lamellar trim |
| `viet_soldier` | `topknot_wrap` | `tunic` | `spear` | brown / jade tunic, vermilion wrap |
| `northern_general` | `northern_helmet` with crest | `lamellar_cape` | `sword_sheathed` | indigo cape, steel lamellar |
| `northern_soldier` | `northern_helmet` | `lamellar` | `spear` | steel lamellar, indigo sleeves |

Banners: the existing flag prop takes a `banner` colour key so each side carries its own
colours (no writing on flags).

### 4. Delivery order (each step ends with owner review)

1. **M12a — prototype:** reference PNGs (4 roles × front, both facings, at rest and in a
   `rally`/`bow` pose) drawn with a throwaway script → owner approves the look, the palette
   keys and the proportions. Approved images go to `docs/reference/approved/`.
2. **M12b — kit (still):** parts, variants, roles, gallery, tests (rest-pose identity,
   AC-07, FR-48 boxes, no overlap of shield/sword with text boxes).
3. **M12c — rig:** joints, crouch, actions; checkpoint video with an existing-text test
   slide (no invented history).

## Acceptance (M12)

| ID | Criterion |
|---|---|
| AC-45 | Owner-approved reference PNGs exist for the four roles. |
| AC-46 | Every role × facing × prop draws; still and rest-pose rig match (M10 tolerance). |
| AC-47 | Hand on shaft for spear/flag in every pose; sword at hip; shield on far forearm. |
| AC-48 | All seven actions run on all four roles; no cracks at elbows/waist (AC-34 method). |
| AC-49 | Faces of all roles are pixel-identical in the head box at rest (no side-specific features). |
| AC-50 | Older themes without the new palette keys still load (fallbacks). |

## Settled after builder review (designer's calls, owner may override)

1. **Script contract, schema `"2.4"`.** 2.3 is on `develop` (released), so new fields need
   2.4 (gated like 2.2/2.3). `Prop` gains `sword_sheathed` and `shield`. `CharacterSpec`
   gains flat optional keys `helmet` (headwear variant), `body` (body variant), `armour`
   (palette key) and `banner` (palette key). README, spec appendix A.7, examples and tests
   change in the same step.
2. **Props per kit.** Validation already checks a prop against the role's kit
   (`checks.kit_problem` with `Kit.props`). `ancient_female` keeps flag/spear/oar/none;
   `warrior_male` takes flag/spear/none/sword_sheathed/shield (no oar). AC-46 covers each
   role × facing × the props its kit allows.
3. **Faces (AC-49).** The male kit reuses the female face and feature functions at the same
   head centre (−88.5), so the test draws only the `face` and `features` parts of every role
   and compares them: identical pixels. Headwear differs and is not compared.
4. **Actions with new props.** The gesturing arm is a kit rule: a prop held in the near hand
   (spear, flag, oar) gestures with the far arm; `none` and `sword_sheathed` gesture with
   the near arm; with a `shield` (on the far forearm) the near arm gestures and the shield
   moves with `far_fore` (its box joins `body_boxes["far_fore"]`). `raise_flag` without a
   flag stays a validation error (existing rule). `actions.for_prop` asks the kit instead of
   testing `prop != "none"`.
5. **Colours.** For the male kit the existing style fields mean: `robe`/`robe_dk` = tunic or
   cape and its shade, `trim` = armour edges and belt, `wrap` = headwrap or plume. New
   `RolePreset`/`CharacterStyle` fields `armour` (lamellar plates; default `gold_dk`) and
   `banner` (flag cloth; default `vermilion`) are added for both kits; for `ancient_female`
   `banner` defaults to today's flag colour so nothing changes.
6. **Palette keys.** `steel`, `steel_dk`, `indigo`, `indigo_dk` are proposed; the M12a
   prototype shows them and their approval comes with the reference images. Theme changes
   and the AC-50 fallbacks are done after that review, in M12b.

## Left to the builder

- Exact path geometry, plume/crest shapes, lamellar pattern density (style from prototype).
- Fallback keys for the new palette colours.
- How `variant` overrides are parsed (keep the CharacterSpec style).
