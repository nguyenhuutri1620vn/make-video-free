# Visual backlog: scenes without people

The owner asked (2026-11-12) for more varied pictures with fewer human figures, and for
Claude to propose and approve the next items on its own. Each item is a new scene layer
drawn with Cairo in the lacquer style (original artwork, C-06), colours from the palette
(C-07), no crackle (C-08), no new dependencies (C-03). Approved templates are not changed.

Work one item at a time: layer code + config parsing + tests, a `--preview` check against
the approved references, use it in `examples/vuong_trieu_nu/script.json`, quality gates,
commit on the current branch (never push). Mark the item done with the commit hash.
When the list runs out, append new proposals in the same format, auto-approved.

| # | Layer | Look | Replaces in `vuong_trieu_nu` | Status |
|---|-------|------|------------------------------|--------|
| 1 | `drum` | Bronze-drum face: 12-ray star in the centre, concentric gold-leaf bands with zigzag and circle-tangent motifs, a ring of flying Lạc birds. | `mau-he` (ringed disc + birds), `vua-nu` background | done (b457a8b) |
| 2 | `gong` | Hanging gong on a carved wooden frame with a mallet, gold leaf boss, eggshell frame posts. | `cong-ba` ("lệnh ông không bằng cồng bà") | done (880d1e6) |
| 3 | `temple` | Temple gate (tam quan): three curved roofs with upturned eaves, vermilion pillars, steps, two incense burners with soft smoke curls. | `den-tho`, `chua-quen` | done (1fc54e5) |
| 4 | `map` | Stylised, original map of the Red River delta: gold coastline, river lines, red dots (list of x, y), optional arrow from the north. Not traced from any real map. | `me-linh`, `65-thanh` (many dots), `ma-vien` (arrow) | done (2307b8b) |
| 5 | `scroll` | Half-unrolled paper scroll with plain ink lines (no readable text) and a brush. | `nu-gioi` | done (b4d9296) |
| 6 | `elephant` | War elephant in profile with a saddle cloth and a flag, no rider. | `tuong-nu` and `cta` | done (f30c5db) |
| 7 | `stilt_house` | Nhà sàn village by the river, bamboo clump. | `nam-40` | done (ca9cfba) |
| 8 | `banners` | A hillside planted with many war flags and spears at rest, rows shrinking into the distance (no people). | `con-nhieu` ("+ còn rất nhiều") | done (25291cf) |
| 9 | `regalia` | A royal crown and a square seal on a cushion before a folding screen, lacquer red and gold. | `trung-vuong`, `ba-nam` | done (36a1de4) |
| 10 | `fallen_flags` | An empty camp: fallen spears, a torn flag on the ground, a cold campfire. | `bo-di` ("Họ bỏ đi…") | done (6511370) |
| 11 | `sail_boat` | A large sailing junk with a ribbed sail on sea waves, no crew. | `le-chan` and `tap-2` (Lê Chân, the sea) | done (4d57b97) |
| 12 | `lone_path` | A narrow path winding into misty mountains, two small footprints marks, no figures. | `khong-tin` | done (660f70d) |
| 13 | `lanterns` | Floating lotus-shaped lanterns with small flames drifting on the river, a few reflections. | `song-hat` (remembrance on the Hát river) | done (5755bde) |
| 14 | `tablet` | A blank memorial tablet (no text) on an altar with an incense bowl and two candles. | `thanh-thien` (a figure known mostly from temple records) | done (5a77168) |
| 15 | `horse` | A bronze horse statue on a stone plinth, gold-leaf surface, no rider; for "Trống đồng → Ngựa đồng" next to the drum. | `hai_ba_trung` slide `loss` (text only today) | done (8ef1b78) |
| 16 | reuse | No new layer: give `hai_ba_trung` slide `war` the map with the northern arrow, and swap its repeated scenes for the new layers. | `hai_ba_trung` | done (2b3ec0c) |
| 17 | `citadel` | A spiral earthen citadel seen from above-front: three concentric ramparts with a moat and a gate, gold ridge lines (spec Appendix B "thành quách"). | library item for era packs; gallery | done (c3c549b) |
| 18 | `bamboo_village` | A bamboo hedge ring around a few thatched roofs and a banyan tree at the village gate (spec Appendix B "làng tre"). | library item for era packs; gallery | approved (auto, 2026-11-13) |
