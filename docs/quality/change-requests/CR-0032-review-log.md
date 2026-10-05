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

Quorum (CLAUDE.md §1.4): both reviewers and the author sign off after
round 2; v3 applies every round-2 follow-up (none left open except as
noted). Approval is conditional on deliverable 1b (B2-8).

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
