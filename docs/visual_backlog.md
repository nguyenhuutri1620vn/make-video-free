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
| 6 | `elephant` | War elephant in profile with a saddle cloth and a flag, no rider. | `tuong-nu` or `cta` | approved |
| 7 | `stilt_house` | Nhà sàn village by the river, bamboo clump. | `nam-40` | approved |
