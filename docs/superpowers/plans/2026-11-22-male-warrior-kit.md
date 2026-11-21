# M12 Male Warrior Kit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reusable `warrior_male` costume kit with variant parts and four role presets (`viet_general`, `viet_soldier`, `northern_general`, `northern_soldier`), drawn like the approved M12a prototype, rigged for every M10 action.

**Architecture:** A new kit module pair (`characters/kits/warrior_male.py` still parts, `warrior_male_rig.py` joints) registered beside `ancient_female`; parts dispatch on `CharacterStyle.variant`. Script schema 2.4 adds props and per-character variant/colour overrides; roles stay data.

**Tech Stack:** Python ≥ 3.10, pycairo, numpy; pytest, ruff, mypy --strict.

**Spec:** `docs/superpowers/specs/2026-11-22-male-warrior-kit-design.md` (owner-approved). Approved look: `docs/reference/approved/warrior_male_roles.png`, `warrior_male_faces.png`; numbers from `docs/reference/prototype/warrior_male_proto.py` (copy numbers, not structure; never import from docs/).

## Global Constraints

- No new dependencies, no network, no `shell=True`, no crackle, darkest stroke `palette.black`, colours only palette keys.
- New optional palette keys with fallbacks: `steel` (126,128,122) → `gold_dk`, `steel_dk` (74,78,78) → `black`, `indigo` (46,58,92) → `jade`, `indigo_dk` (28,34,58) → `robe_crew_dk`; values go in `themes/son_mai/theme.json`.
- New script fields need `schema_version` `"2.4"`; 2.3 and older scripts render exactly as before (snapshots unchanged).
- `ancient_female` look unchanged; its rest pose and stills keep their snapshots.
- Male face = prototype `male_face`/`male_features` (approved), shared by all male roles; no beard, pupils, ears or shading.
- Weapons at rest; sword sheathed at the near hip; shield on the far forearm.
- Same joint names as `ancient_female_rig` (`skirt`, `torso`, `head`, `near_arm`, `far_arm`, `near_fore`, `far_fore`, `hand`, `prop`).
- Tests with `PYTHONPATH=<worktree> <repo>/.venv/bin/pytest`; gates `ruff check . && ruff format --check . && mypy --strict history_shorts && pytest -q`; commit per task, never push.

## Review Focus

1. **A 2.3 script using a male role or new prop** — clear `requires schema_version "2.4"` error, never a crash. Test in Task 1.
2. **`ancient_female` given `shield`/`sword_sheathed`, or a warrior given `oar`** — `validate` error at `<character>.prop` (existing `kit_problem`). Test in Task 3.
3. **A theme without the new palette keys** — loads, male roles draw with fallbacks. Test in Task 1.
4. **Mirrored (`facing -1`) shield bearer doing `rally`** — the near (free) arm rises, the shield stays on the far arm. Test in Task 5.
5. **Gallery sheet with the four new roles** — every new cell has art and its label; sheet height grows, nothing overlaps. Test in Task 3.

---

### Task 1: Contract 2.4 and palette

**Files:** Modify `history_shorts/scene_config.py` (`PROP_NAMES`/`Prop` + `sword_sheathed`, `shield`; `CharacterSpec` + `helmet: str | None`, `body: str | None`, `armour: str | None`, `banner: str | None`; `V24_CHARACTER_KEYS`), `history_shorts/script_config.py` (`WARRIOR_SCHEMA_VERSION = "2.4"`, level 4 gating of the new character keys, of the new props and of the new role names), `history_shorts/config.py` (`PALETTE_FALLBACKS` += the four keys), `themes/son_mai/theme.json`; Test `tests/test_v24_contract.py`.

- [ ] Step 1: failing tests — 2.4 script with `{"role": "viet_general", "helmet": "cap", "armour": "steel", "banner": "indigo", "prop": "shield"}` loads with those values; each new key/prop/role in a 2.3 script errors `requires schema_version "2.4"` at its path (Review Focus 1); `helmet` must be one of `topknot_wrap, viet_helmet, northern_helmet, cap`, `body` one of `tunic, lamellar, lamellar_cape`; `armour`/`banner` unknown palette key → error (palette check); theme without the four keys loads and fills them from fallbacks (Review Focus 3); supported versions list ends with "2.4" (update the pinned message test).
- [ ] Step 2: run — FAIL. Step 3: implement. Step 4: run — PASS + gates. Step 5: commit `feat(script): schema 2.4 warrior fields and palette keys`.

### Task 2: Style fields and variants plumbing

**Files:** Modify `history_shorts/characters/roles.py` (`RolePreset` + `armour: str = "gold_dk"`, `banner: str = "vermilion"`, `variant: Mapping[str, str] = {}`; `CharacterStyle` + `armour: RGB`, `banner: RGB`, `variant: Mapping[str, str]`; `resolve_style` applies spec overrides `helmet`/`body` into `variant`, `armour`/`banner` colours), `history_shorts/characters/kits/ancient_female.py` (`_flag` cloth uses `style.banner`; default equals today's vermilion), `history_shorts/characters/kits/ancient_female_rig.py` (`_waved_flag` uses `style.banner`); Test `tests/test_roles.py`.

- [ ] Steps: failing tests (`resolve_style` fills defaults; overrides land in `variant`; ancient_female flag pixels unchanged → existing snapshots pass) → implement → PASS (full snapshot tests) → commit `feat(characters): armour, banner and variant style fields`.

### Task 3: `warrior_male` kit (still) and roles

**Files:** Create `history_shorts/characters/kits/warrior_male.py`; Modify `history_shorts/characters/kits/__init__.py` (register), `history_shorts/characters/roles.py` (four presets), `history_shorts/scene_config.py` (`ROLE_NAMES`), `history_shorts/gallery.py` (sheet height from the role count); Test `tests/test_warrior_kit.py`, `tests/test_gallery.py`.

**Interfaces:** Produces `KIT: Kit` named `"warrior_male"` with `props = {"flag", "spear", "sword_sheathed", "shield", "none"}`, `draw_order = ("cape", "prop_back", "legs", "body", "belt", "sword", "far_sleeve", "shield", "near_sleeve", "prop_front", "hand", "neck", "face", "features", "headwear")`, `head_parts = {"neck", "face", "features", "headwear"}`, `hand_center = (19.0, -58.0)`, `VARIANTS: Mapping[str, Mapping[str, PartFn]]` for slots `headwear` and `body`; constants copied from the prototype (`HAND`, `SHOULDER_NEAR/FAR = (±13, -77)`, `WAIST = (0, -52)`, torso, arm, legs, helmet paths, lamellar 3.2×4.0 plates, 16 rows). Roles (palette keys):

| role | helmet | body | prop | robe, robe_dk | trim | wrap | armour | banner | crest/plume |
|---|---|---|---|---|---|---|---|---|---|
| `viet_general` | viet_helmet | lamellar_cape | flag | vermilion, vermilion_dk | gold | vermilion | gold_dk | vermilion | plume vermilion |
| `viet_soldier` | topknot_wrap | tunic | spear | jade, robe_crew_dk | gold_dk | vermilion | gold_dk | vermilion | — |
| `northern_general` | northern_helmet | lamellar_cape | sword_sheathed | indigo, indigo_dk | gold_dk | indigo | steel | indigo | tassel gold |
| `northern_soldier` | northern_helmet | lamellar | spear | indigo, indigo_dk | steel_dk | indigo | steel | indigo | tassel steel_dk |

(`crest: bool` of the preset turns the plume/tassel on.)

- [ ] Step 1: failing tests — every new role × facing × allowed prop draws non-empty pixels; `kit_problem` rejects `shield` on `leader` and `oar` on `viet_soldier` (Review Focus 2); AC-07 hand on shaft for spear/flag; sword pixels lie right of x=0 and below the belt; shield centre at local (−20, −50); AC-49: drawing only `("face", "features")` for the four roles gives identical masks; rest silhouette within 2 px of the prototype's at h=380 (`warrior_male_roles.png` column 0 rows, measured by bounding box per role); gallery sheet height grows by `4 × len(FACINGS) × CELL_H`, every new cell has art and its label (Review Focus 5).
- [ ] Step 2: run — FAIL. Step 3: implement (copy prototype numbers; variants dispatch on `style.variant[slot]`; face/features are the prototype's male face). Step 4: run — PASS; gates; update gallery snapshot only if the gallery test pins one (say so). Step 5: commit `feat(characters): warrior_male kit and four warrior roles`.

### Task 4: Rig for `warrior_male`

**Files:** Create `history_shorts/characters/kits/warrior_male_rig.py`; Modify `kits/__init__.py` (attach `RIG`); Test `tests/test_warrior_rig.py`.

**Interfaces:** Same `joints(style, pose)` keys as `ancient_female_rig`; `ELBOWS` refit to the male sleeve (measure at y = −60 like M10); body cut at `WAIST_Y = -52` under the belt; legs and boots in the `skirt` segment (they squash with crouch); shield drawn under `far_fore`; `BODY_BOXES` with the shield inside `far_fore`.

- [ ] Step 1: failing tests (parametrised over the four roles × facings × props): rest pose vs still within mean < 1/255, max < 0.25; hand on shaft in `SAMPLE_POSES` of `test_rig.py`; no crack at elbows and waist (AC-34 method); crouch keeps feet and drops the head by `CROUCH_DROP`; shield moves with the far forearm.
- [ ] Steps 2–5: FAIL → implement → PASS + gates → commit `feat(characters): warrior_male rig`.

### Task 5: Actions on every kit

**Files:** Modify `history_shorts/characters/actions.py` (`NEAR_HAND_PROPS: Final = frozenset({"flag", "spear", "oar"})`; `for_prop` swaps to the far arm only when `prop in NEAR_HAND_PROPS`), `history_shorts/characters/kits/ancient_female_rig.py` (`free_arm` uses the same set); Test `tests/test_actions.py`, `tests/test_warrior_rig.py`.

- [ ] Step 1: failing tests — `rally` with `sword_sheathed` and with `shield` raises the near arm; with `spear` the far arm; mirrored shield bearer (`facing -1`) rally keeps the shield on the far arm and raises the near (Review Focus 4); all seven actions run for all four roles over 11 samples without error and with AC-34 continuity (AC-48).
- [ ] Steps 2–5: FAIL → implement → PASS + full suite → commit `feat(characters): actions follow the kit's free arm`.

### Task 6: Docs, checkpoint and owner review

**Files:** Modify `docs/raw_requirement.md` (Appendix A.7 M12: fields, props, roles, palette keys, AC-45…AC-50), `README.md` (roles table, 2.4 fields, Decisions line), `CHANGELOG.md`, `docs/artwork-guide.md` (none), `CLAUDE.md`-referenced constants untouched; Create `tests/data/warrior_script.json` (2.4, two slides with existing neutral text "Thử tướng" / "Thử lính": the four roles, a `rally` and a `bow`).

- [ ] Step 1: `validate` the test script — 0 errors.
- [ ] Step 2: render it to `output/m12_checkpoint.mp4`; extract frames at rest/rally/bow; compare with `warrior_male_roles.png` by eye and list differences.
- [ ] Step 3: full gates; commit `docs: M12 warrior kit spec, README, checkpoint script`.
- [ ] Step 4: show the owner the video and frames; wait for approval.
