# CR-0032 review log

Companion to `CR-0032-meta-canopy-structure-layers.md` (CR-0011 A4):
rounds, verdicts and every concern's disposition.

## Rounds
| round | text | reviewer | verdict | BLOCKING |
|---|---|---|---|---|
| 1 | v1 (`5dd7e70`) | A: correctness of design and data semantics (fresh agent; read-only) | REVISE | 2 (A1, A2; 4 MAJOR, 4 MEDIUM, 3 LOW) |
| 1 | v1 (`5dd7e70`) | B: implementability, composition, test plan, operations (fresh agent; read-only; ran `test_shared_constants`, `test_pa0027_lint`, `test_nodata_zero_lint`: 33 OK) | REVISE | 1 (B1; 4 MAJOR, 4 MEDIUM, 2 LOW) |
| 2 | v2 (`fa8bbc7`), bounded (CR-0011 A2) | A (same agent) | APPROVE WITH FOLLOW-UPS | 0 (1 MAJOR, 1 MEDIUM, 2 LOW) |
| 2 | v2 (`fa8bbc7`), bounded | B (same agent; ran five existing suites, 214 tests: 1 failure = B2-1) | APPROVE WITH FOLLOW-UPS | 0 (2 MAJOR, 2 MEDIUM, 4 LOW) |

| 3 | v4 (`c2329bc`), bounded, after 1b | A (same agent) | APPROVE WITH FOLLOW-UPS | 0 (1 MEDIUM, 2 LOW) |
| 3 | v4 (`c2329bc`), bounded, after 1b | B (same agent) | APPROVE WITH FOLLOW-UPS once B3-1 fixed | 0 (1 MAJOR, 2 MEDIUM, 2 LOW) |

Round 2: both reviewers and the author signed off on v3, conditional on
deliverable 1b (B2-8). **That approval lapsed** when 1b run 1 failed
(`a005e58`; § Deliverable 1b). Round 3: both reviewers and the author sign
off on v4; v5 applies every round-3 follow-up, B3-1 included. Approved
2026-10-05.

Author checks of the reviewers' code claims (against `5dd7e70`):
`download_tcc_nlcd.year_image` ends `.toInt16().unmask(-1)` because EE
exports masked pixels as 0 (line 241); `build_raster` and
`realign_rasters.warp_to_grid` are single-band (`count=1`) and
`warp_to_grid` writes deflate, not LZW; `generate_road_distance.py:311`
excludes only `road_dist` from the year union;
`prepare_training_data.window_mask` iterates the live `FEATURE_SPEC`
(line 174) while `acceptance_split.window_mask` iterates the frozen
`feature_spec_keys` (15 names, `acceptance_split.json:122`), and no test
ties the two. All confirmed.

## Round 1, reviewer A: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A1 | BLOCKING | masked cells exported as 0 (no unmask to a marker) → water and gaps read as real readings | accepted: every band is exported as float with `unmask(-1)`; the validity band is built unmasked; cells are set to `NODATA` locally where valid < 0.5 or any band is -1; T3 feeds -1 and low-validity cells and asserts `NODATA` | v2 §3.1, §3.3; T3 |
| A2 | BLOCKING | `mosaic()` has a WGS84 1° default projection, so `reduceResolution` does not aggregate the 1 m pixels | accepted: `setDefaultProjection(first tile's projection)` before `reduceResolution`; the pilot refuses when the shares look like samples (fraction strictly inside (0, 1000) below `MIN_INTERIOR_SHARE_FRAC`, in `check_canopy_structure.py`) and compares cells against `reduceRegions` at native scale | v2 §3.1; §3.5; `check_canopy_structure.py` |
| A3 | MAJOR | `maxPixels=1024` too low for an EPSG:3857 ~1.19 m source | accepted: `MCH_MAX_PIXELS = 4096`; the pilot prints the native CRS and nominal scale and refuses if `ceil(30/scale + 1)^2 > MCH_MAX_PIXELS` | v2 §3.1, §3.5 |
| A4 | MAJOR | (a) validity band derived from `h` is always 1; (b) numpy encoders are not on the write path | accepted: (a) validity = `ee.Image(1).updateMask(h.mask()).unmask(0)`; (b) raw floats are downloaded and encoded locally by `models.mch_*_encode` in `encode_tile`, which T3 drives with raw values | v2 §3.1, §3.3; T3 |
| A5 | MAJOR (author treats as blocking implementation) | `prepare_training_data.window_mask` reads every `FEATURE_SPEC` raster; registering `mch_*` breaks split regeneration and acceptance | accepted, split out (CR-0011 A5): latent defect BUG-0093, fixed by prerequisite **CR-0033** (window mask pinned to the acceptance feature list, with a test tying the two). CR-0032 deliverable 2 waits for CR-0033 | CR-0033; v2 Impact, Deliverables |
| A6 | MEDIUM | two resampling steps (mean on 5070, nearest warp) shift the footprint up to ~21 m | accepted: export directly on the region's template grid (template WKT + window `crs_transform`); no warp; `grid_mismatch` is None by construction and still checked | v2 §3.2 |
| A7 | MEDIUM | the measured gain used 12 Meta columns; the CR builds 4 | accepted: `diagnose_structure_combo.py` now also fits "+ CR-0032 four (r30)" and "+ four + sd" from the existing caches; result is a pre-approval gate (deliverable 1b, user runs it on EC2). If the four alone give < +0.006 AUC (mean of 5 seeds) the CR is revised before approval | v2 Why now, Deliverable 1b |
| A8 | MEDIUM | keep/remove on one retrain vs one checkpoint; Spearman cross-check with mismatched geometry and no failure action | accepted: 3 seeds per arm, same recipe and seeds, baseline arm retrained with `--features` (the 15); criteria pre-stated (§ Evaluation); the Spearman check is replaced by the matched-geometry `check_canopy_structure.py` gate whose failure blocks registration use | v2 § Evaluation, §3.5 |
| A9 | MEDIUM | ~12,300 synchronous tiles at 6 km; late failures lose hours | accepted: persistent per-tile cache with resume (`--tile-dir`), tiles over all-nodata template windows skipped, runtime estimate from the pilot recorded before the full run | v2 §3.2, §3.4 |
| A10 | LOW | new vintage of another feature needs a full EE rerun | accepted: `--copy-only` writes missing years from the existing latest `mch_*` file without EE | v2 §3.4 |
| A11 | LOW | diagnostics' "today's features" includes `mch_*` after registration | accepted as a note: the diagnostic scripts' baselines are documented as the discovered list; `diagnose_structure_combo.py` is not re-run after registration (Out of scope) | v2 Impact |
| A12 | LOW | 4-corner bounds understate curved edges | accepted: `transform_bounds(..., densify_pts=21)` | v2 §3.2 |
| A13 | LOW | a single > 60 m artefact aborts a region | accepted: cells > 60 m become `NODATA` and are counted; the region is refused only if they exceed `MCH_MAX_OVER_FRAC` = 0.001 of valid cells; T3 covers both | v2 §3.3; T3 |

## Round 1, reviewer B: concerns and dispositions (as of v2)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| B1 | BLOCKING | masked pixels exported as 0 (= A1) | accepted: see A1; the pilot reports per-band counts of -1, low-validity and `NODATA` cells | v2 §3.1, §3.3, §3.5 |
| B2 | MAJOR | `mosaic()` projection (= A2) and `maxPixels` (= A3) | accepted: see A2, A3 | – |
| B3 | MAJOR | encoders off the data path; > 60 m policy | accepted: see A4(b), A13 | – |
| B4 | MAJOR | runtime, no resume, `_fetch_all` cancels on first failure | accepted: see A9. Batch `Export.image` to Cloud Storage is out of scope (needs a bucket); revisit if the pilot estimate exceeds 24 h for all regions | v2 §3.4; Out of scope |
| B5 | MEDIUM | 5070 mosaic memory (~2.5-10 GB for ME) | accepted: no mosaic; each tile is encoded and written into its window of the four output files (windowed writes, block = tile) | v2 §3.2 |
| B6 | MEDIUM | dry-run tile unspecified | accepted: the pilot window is the one holding the most of the region's positives (template centre if none); `--pilot-lonlat` overrides | v2 §3.4 |
| B7 | MEDIUM | year union must exclude the family's own (and `road_dist`) years | accepted: `vintage_years` excludes `STATIC_FEATURES` = `road_dist` + `MCH_FEATURES`; T4 fixture has a stale `NH_2019_mch_mean.tif` | v2 §3.4; T4 |
| B8 | MEDIUM | cross-check threshold in prose, no committed script | accepted: `check_canopy_structure.py` committed with v2; it owns its constants; the CR cites it only | §3.5 |
| B9 | MAJOR | +0.003 bar inside seed noise; removal breaks T2 | accepted: see A8; removal is a follow-up CR that reverts the registration and T2 | v2 § Evaluation |
| B10 | LOW | (a) tests untracked; (b) `from`-import defeats the patch; (c) bounds source unstated; (d) non-nearest resampling uncaught | (a) committed `84ed374`; (b) tests now patch `generate_canopy_structure.fetch_window`, the generator's own module global; (c) §3.2 states the template footprint; (d) moot: no resampling (A6); T3 asserts exact per-window values | v2 §3.2; T3 |
| B11 | LOW | deliverables missing review log/tracker, EC2 record owners, PA-0035, LZW wording | accepted: deliverables list them; files are deflate (stated) | v2 Deliverables, Impact |

## Author's trial implementation for v2 (not committed)
To check that `tests/test_cr0032.py` v2 is satisfiable and discriminating,
the author implemented §3.3-§3.6 (EE parts stubbed) in a throwaway copy
of the tree: all 20 tests pass. Wrong implementations, each must fail:

| mutant | result |
|---|---|
| M1 valid-fraction rule ignored | FAIL (5) |
| M2 > 60 m clipped instead of `NODATA` | FAIL (10) |
| M3 year union excludes only `road_dist` | FAIL (1) |
| M4 all-nodata template windows fetched | FAIL (1) |
| M5 tile cache ignored (no resume) | FAIL (1) |
| M6 > 60 m refusal removed | FAIL (1), after the fixture was changed so only the over-max rule can refuse (first version passed it: all cells over 60 m also tripped the < 1 % rule) |
| M7 masked cells written as 0 | FAIL (6) |

CR-0033 trial: `SPLIT_WINDOW_FEATURES` + loop change makes
`tests/test_cr0033.py` pass (3/3); today's code fails T2 with
`MissingDataError` on the extra feature.

## Round 2: concerns and dispositions (v3)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A2-1 | MAJOR | constant validity band lacks `setDefaultProjection`; would not aggregate | accepted: §3.1 step 4 adds `.setDefaultProjection(proj)`; pilot reports the fraction of `valid` strictly inside (0, 1) | §3.1, §3.4 |
| A2-2 | MEDIUM | tile identity not checked (transform/CRS); cache reused on shape only | accepted with B2-2: identity check on fetched and cached tiles (fetched mismatch refuses, cached re-fetches); cache keyed on grid + asset + recipe; `.part` + `os.replace`. Tests: off-grid tile refused, template change re-fetches. Mutants M8 (no fetched-tile check) and M9+ (no key and no cached check) fail; M9 alone (no key) passes because the cached-tile identity check still re-fetches - defence in depth, behaviour pinned | §3.2, §3.4; T3TileIdentity |
| A2-3 | LOW | float32 shares at 1+ε abort a region | accepted: encoders round to stored units, then range-check the integer (no clipping); T1 adds 1.0004 → 1000 | §3.3; T1 |
| A2-4 | LOW | max-pixels check uses projection units | accepted with B2-7: ground size = nominal scale x cos(lat) | §3.4 |
| B2-1 | MAJOR | branch fails PA-0028 L1 lint on two new statements | accepted: both reviewed as not-a-defect (interior-share bounds over cells already filtered by `valid`; expected encoder output in a test) and added to `test_nodata_zero_lint.ALLOWLIST` with justifications; lint passes | `tests/test_nodata_zero_lint.py` |
| B2-2 | MAJOR | cache not keyed on template/recipe | accepted: see A2-2 | – |
| B2-3 | MEDIUM | generator and gate share any EE misreading of the template WKT | accepted: pilot `grid_check` fetches NLCD over the pilot window via `fetch_window` and requires >= `MIN_GRID_AGREE` = 0.99 equality with the on-disk file; tests: same grid passes, one-cell shift fails | §3.4; T3GridCheck |
| B2-4 | MEDIUM | gate samples only valid cells; over-masking invisible | accepted: second sample of any cells inside the template's valid area (outside the clip the generator writes nothing by design); T5 adds an over-masking case | §3.5; T5 |
| B2-5 | LOW | gate's `MIN_VALID_FRAC` not tied to models | accepted: T2 asserts equality | T2 |
| B2-6 | LOW | sentinel test vacuous | accepted: encodes the boundary values | T1 |
| B2-7 | LOW | = A2-4 | accepted | – |
| B2-8 | LOW | approval depends on an unseen EC2 result | accepted: approval explicitly conditional on 1b; its output is recorded in the evidence directory and this log | Status; Deliverable 1b |

Trial implementation re-run against v3 tests: 25/25 pass; mutants M1-M8
fail (M2 now 14 errors, others as before).

## Deliverable 1b
| run | commit | bar | result | outcome |
|---|---|---|---|---|
| 1 | `fa8bbc7` | "+ CR-0032 four (r30)" >= +0.006 AUC (5 seeds) | +0.0033 (AUC 0.7726 +/- 0.0035 vs 0.7693); all 12 Meta columns +0.0089, all six r30 +0.0040 | **FAILED: approval lapsed** (`evidence/CR-0032/1b_combo_run1.txt`) |
| 2 | `a005e58` | "+ CR-0032 four (r30 + r100)" >= +0.006 AUC (5 seeds), pre-stated in code before the run | +0.0086 (AUC 0.7779 +/- 0.0027), AP +0.0117; r100 only +0.0083 | **PASSED** (`evidence/CR-0032/1b_combo_run2.txt`); v4 restates Why now; bounded re-review (round 3) before implementation |

Author's analysis after run 1, recorded as post-hoc: the gain sits in the
100 m-radius columns. The trees see the new columns only at the point; the
CNN sees a 30 m layer over its 64 x 64 window, and the 100 m mean and
shares are area-weighted means of the 30 m cells, so the CNN can rebuild
them. The like-for-like proxy for four 30 m layers is therefore the four
at r30 **plus** r100. Because this was noticed after a failed result, the
new bar is pre-stated in code before the run (`diagnose_structure_combo.py`
comment, commit below): **"+ CR-0032 four (r30 + r100)" >= +0.006 AUC, mean
of 5 seeds**. If it fails, the layer set is redesigned; if it passes, CR-0032
is revised (Why now restated) and goes to a bounded re-review before any
implementation. The CNN 3 + 3 evaluation remains the decider.

## Round 3: concerns and dispositions (v5)
| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| A3-1 | MEDIUM | the post-run-1 bar guards little: run 1 already showed the r100 gain; run 2 is a re-analysis, not independent | accepted: Why now says the bar was chosen after run 1 and 1b is supporting evidence, not confirmation; § Evaluation criteria declared frozen (any later change is a new CR) | Why now; § Evaluation |
| A3-2 | LOW | "area-weighted means" exact only with validity weights and whole cells | accepted: "approximately (to validity weighting and cell discretisation)" | Why now |
| A3-3 | LOW | the CNN can rebuild the neighbourhood, but may not | accepted, already covered: § Evaluation decides; stored 100 m layers are the named follow-up (Out of scope), the natural next test because r100 only (+0.0083) ≈ r30 + r100 (+0.0086) | this log; Out of scope |
| B3-1 | MAJOR | 1b evidence files untracked (`.gitignore` `*`) | accepted: tracked in the v5 commit; mechanism fixed by `.gitignore` rule 12 (every evidence subdirectory at any depth, text types), since per-CR rules (10, 11) were twice added after the fact | `.gitignore`; evidence |
| B3-2 | MEDIUM | CR overstates the bar's control (= A3-1) | accepted: see A3-1 | Why now |
| B3-3 | MEDIUM | CHANGELOG entry stale (says approved, old bar) and wrong about water ("tall forest") | accepted: entry rewritten (lapse, r30 + r100 bar, v5 approval); water as 0 reads as 0 m (open ground), not tall forest - the author's earlier wording, which also appears in round-1 A1's scenario, was wrong | `CHANGELOG.md` |
| B3-4 | LOW | Rounds/Quorum section did not show the lapse | accepted: rows for round 3 and the lapse stated in the Quorum paragraph | this log |
| B3-5 | LOW | tracker hides that the bar changed | accepted: tracker line says so | tracker |

## Implementation code review (deliverable 2, `d81aff8`)
Reviewer A (same agent; read-only): **APPROVE WITH FOLLOW-UPS**, 0
BLOCKING (1 MAJOR, 6 LOW). Verified from code and EE documentation:
§3.1 expression, `crs_transform` order, tile identity checks and cache
key, PA-0027 retry clause, encoders, staged writes and refusals,
registration order (appended; existing checkpoints keep channel order),
the allowlist entry. Pilot-only items: EE accepts the template WKT; the
returned shape without `dimensions`; CRS equality of returned tiles;
fetch time.

| id | sev | concern (short) | disposition | where |
|---|---|---|---|---|
| C1 | MAJOR | 99 % NLCD equality expects one-step resampling to match the on-disk two-step route; a correct grid would fail (reviewer's simulation: 55-92 %) | accepted: `grid_check` is a registration test - agreement at offsets up to 2 cells, (0, 0) must be best by >= 0.02; tests: exact grid, 15 % resampling noise (passes), 1-cell shift (fails), uniform window (fails, retry elsewhere) | §3.4; `grid_check`; T3GridCheck |
| C2 | LOW | EE's returned CRS may be equivalent but not `==` | open, pilot-confirmable; fails closed (every tile refused). If seen: semantic comparison, recorded in evidence | tracker |
| C3 | LOW | without `dimensions`, a row/column could be added | open, pilot-confirmable; fails closed. Fallback: pass `dimensions` | tracker |
| C4 | LOW | `--copy-only` copies without grid/tag check | accepted: requires `grid_mismatch` None and `GROUSE_SOURCE=MCH_ASSET`; tests T3CopyOnly | §3.4; `copy_only` |
| C5 | LOW | Mercator detected only from an EPSG string | accepted: also from the projection WKT | `native_pixel_check` |
| C6 | LOW | per-year copies not all-or-nothing | accepted: every copy staged before any `os.replace`; leftovers removed | §3.4 |
| C7 | LOW | unaggregated validity band only printed | accepted: pilot refuses when the band is only 0/1 across a coverage edge | §3.4; `_report_pilot` |
