# CR-0034 review log

Companion to `CR-0034-ee-download-on-source-lattice.md` (CR-0011 A4).

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`bca963d`) | A: correctness (agent; read-only; re-derived BUG-0094 from the evidence and code) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 1 MEDIUM, 3 LOW) |
| 1 | v1 (`bca963d`) | B: implementability, composition, tests (agent; read-only; ran test_cr0034/0035, both lints, test_cr0018_candidates) | REVISE | 1 (B34-1; 1 MAJOR, 2 MEDIUM, 1 LOW) |
| 2 | v2 (`fb3a824`), bounded | A | APPROVE WITH FOLLOW-UPS | 0 (1 LOW) |
| 2 | v2 (`fb3a824`), bounded | B (ran the standing suites; PA-0035 sweep) | APPROVE WITH FOLLOW-UPS | 0 (1 LOW) |

| 3 | v3 (`8281e48`), bounded | A (reproduced BUG-0095: 0.943 default vs 1.000 at 1e-6, 20,000 cells) | APPROVE WITH FOLLOW-UPS | 0 (1 MEDIUM, 1 LOW) |
| 3 | v3 (`8281e48`), bounded | B (measured the exact warp's cost: ~16x on the warp step) | APPROVE WITH FOLLOW-UPS | 0 (2 LOW) |

Round 3: both reviewers and the author sign off on v3; approved. v4
applies the follow-ups and the code lands with it.

Round 2: both reviewers and the author sign off on v2. v3 applies the two
LOW follow-ups and adds §5 (BUG-0095, raised in CR-0035's round 2), which
is new text and goes to a bounded round-3 re-review before implementation.

## Round 1: concerns and dispositions (v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| B34-1 = A34-1 | BLOCKING | grid read from the first image of the year subset, no `filterBounds`, no check across images; TCC's evidence origin (-51285, 1319505) suggests a non-CONUS image; the lattice check only compares the mosaic with the grid we chose | accepted: `year_native_grid(..., bounds_lonlat)` filters by the region and passes every intersecting image's projection through `common_native_grid` (same CRS semantically, same origin mod 30, else refuse); `vintage_native_grid` likewise; tests G8, G9; mutants "no filterBounds" and "first image only" fail | §1, §3; G8, G9 |
| B34-2 = A34-2 | MAJOR / MEDIUM | every fake grid is EPSG:5070, so a hard-coded `"EPSG:5070"` on the merged or raw file passes | accepted: the fake serves only the source's own CRS; G4 and G7 also run with a custom Albers WKT source; G7 asserts the raw file's CRS; mutants labelling either file EPSG:5070 fail | Test plan; G4, G7 |
| B34-3 | MEDIUM | callers missed: `diagnose_grid_registration.py`, `tests/test_cr0018_candidates.py` (BUG-0066 retry tests) | accepted: both listed; the retry test only gains `crs=` and `Projection` (assertions unchanged) and lands with the code so the standing suite never goes red (verified: 44/44 with the trial) | §4 |
| B34-4 | MEDIUM | `vintage_native_grid` forms, `main` passing `grid=`, TreeMap refusal untested | accepted in part: `vintage_native_grid` (collection and Image) and TreeMap off-lattice refusal tested (G9, G7). `main` wiring: `grid` is a required keyword of `build_raster` (omission raises `TypeError`), a wrong image's grid is refused by `common_native_grid`, and CR-0035's per-file gate measures every file written; a `main` dry-path test is not added | G7, G9 |
| B34-5 | LOW | `tiles()` truncates float origins with `int()` | accepted: float stepping | §2 |
| A34-3 | LOW | "native lattice = exact copy" assumed | accepted: CR-0035 pilot fetches `pixelCoordinates` on the native lattice (`diagnose_fetch_tile_offset.py --native`), centres within 0.01 m | §4; CR-0035 step 1 |
| A34-4 | LOW | NLCD WKT is WGS84-based; PROJ step to NAD83 | accepted: CR-0035 pilot records the PROJ pipeline; CR-0035's per-file gate catches any residual | CR-0035 step 1 |
| A34-5 | LOW | `%` wrap: 29.9999999 refused | accepted: `min(r, 30 - r)`; G6 float-noise test; mutant fails | §2; G6 |

## Author's trial implementation (v2, not committed)
`tests/test_cr0034.py` v2 (24 tests) and the updated
`test_cr0018_candidates` (20) pass (44/44). Mutants, each must fail: 0-origin
snap; hard-coded request `crs`; no lattice check; TreeMap's own
`region_grid`; merged file labelled EPSG:5070; raw TreeMap labelled
EPSG:5070; no `filterBounds`; first image only; wrap-around lattice test.
All nine fail.

## Round 2: concerns and dispositions (v3)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A34-2-1 | LOW | images filtered by unpadded bounds while tiles cover bounds + 2 km | accepted: `filterBounds` on the bounds padded by 4 km (`padded_lonlat`), in both downloaders; G9 asserts the padded rectangle | §1; G9 |
| B34-2-1 | LOW | Impact says all outputs on the template CRS; raw TreeMap files are now native | accepted: Impact split into template-grid files vs raw TreeMap files | Impact |
| (B35-2-4 → BUG-0095) | MEDIUM in CR-0035 | approximate warp transformer | new §5: `WARP_TOLERANCE_PX = 1e-6` at both repair-path warps; author measured 0.932 (default) vs 1.000 (1e-6) on a 60 km rotated grid; G10, G11; mutant (default tolerance) fails both | §5; BUG-0095 |

Trial implementation (v3, not committed): `test_cr0034` (26) and
`test_cr0018_candidates` (20) pass, 46/46; the ten mutants listed in the
CR fail.

## Round 3: concerns and dispositions (v4)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A34-3-1 | MEDIUM | BUG-0095 sweep calls `generate_time_since_disturbance` harmless; it warps the CONUS grid onto the rotated template (`tsd` is a training channel) | accepted: confirmed instance **BUG-0096**; `tolerance=WARP_TOLERANCE_PX` in this CR's code, G11 pins it; `tsd` regenerated in CR-0035 step 2.5; coverage-repair, predict-map and diagnostic warps tracked | §5; BUG-0095 §8; BUG-0096 |
| A34-3-2 | LOW | "real layers are smoother" understates categorical layers | accepted: BUG-0095 §3 reworded | BUG-0095 |
| B34-3-1 | LOW | runtime cost of the exact transformer unstated | accepted: §5 states ~11-16x on the warp step, ~1-2 min per region-sized layer; CR-0035 records times | §5 |
| B34-3-2 | LOW | G11 accepts only the bare-name spelling | accepted: bare name or module attribute | G11 |
| B35-3-1 (CR-0035) | MEDIUM | TreeMap raw write not atomic | accepted here (the code is CR-0034's): stage `.tmp` + `os.replace` | §3 |

Implementation: the trial code ported unchanged plus the v4 items; full
suite 519 tests OK (6 skipped, real data); PA-0035 sweep 0 hits.
