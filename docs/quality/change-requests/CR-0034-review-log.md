# CR-0034 review log

Companion to `CR-0034-ee-download-on-source-lattice.md` (CR-0011 A4).

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`bca963d`) | A: correctness (agent; read-only; re-derived BUG-0094 from the evidence and code) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 1 MEDIUM, 3 LOW) |
| 1 | v1 (`bca963d`) | B: implementability, composition, tests (agent; read-only; ran test_cr0034/0035, both lints, test_cr0018_candidates) | REVISE | 1 (B34-1; 1 MAJOR, 2 MEDIUM, 1 LOW) |

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
