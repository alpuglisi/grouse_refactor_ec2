# CR-0012: One global block grid, one pooled train/val split, one pooled negative draw

**Status: PROPOSED (v1), 2026-09-30 — awaiting review. All deliverables pending.**
History, verdicts and dispositions: `CR-0012-review-log.md`. Split from
CR-0007 v7 (user decision 2026-09-30); lineage in the review log. This
document states only current intent.

## Scope
Replace the per-region positive thin, block split and negative draw with
single pooled computations on one global block grid. Specify each step as
a deterministic function of its inputs and a seed, so CR-0013 can replay
it exactly. Add standing checks to the training entry points, restrict the
assumed-negative background to the region's state, and guard the stale
copies of the rewritten scripts.

## Why now
BUG-0027. The spatial holdout is computed once per region on a grid
anchored at that region's box (`prepare_training_data.py:85-114`,
`generate_negatives.py:98-107`). Its guarantee holds within a region and
fails across regions. On today's files, 522 of 1,674 pooled validation
positives have a training positive at the identical coordinate. On one
global 3 km grid, 882 blocks hold both a training and a validation record.
Every validation metric in the repository is inflated by this.

BUG-0029 (remainder). `sample_background_points` (`train.py:120-165`)
draws assumed negatives anywhere on the region's raster grid, in any
state. It is dormant at the `--an-background 0.0` default (`:739`).

CR-0007 makes every record belong to one region, which is the
prerequisite for this CR.

## The change

### 1. Constants and helpers (`regions.py`, adding to CR-0007's table)
| name | value |
|---|---|
| `BLOCK_ORIGIN_5070` | `(0.0, 0.0)` |
| `VAL_FRACTION` | 0.2 |
| `SPLIT_SEED` | 42 |
| `WINDOW_PX` | 64 (`train.IMG_SIZE` + 2 × default jitter 0) |

- `block_ids(x_5070, y_5070)` returns `f"{floor((x-x0)/BLOCK_SIZE_M)}_{floor((y-y0)/BLOCK_SIZE_M)}"`.
  It is the only block-id function; `assign_spatial_blocks` and
  `compute_block_ids` lose their `box` argument and call it.
- `order_key(seed, text)` returns
  `int.from_bytes(blake2b(f"{seed}:{text}".encode(), digest_size=8).digest(), "big")`.
  Coordinates are formatted as `f"{lon:.6f},{lat:.6f}"`. This format is
  part of the contract.

### 2. Specification
All distances are Euclidean in EPSG:5070, compared as squared float64
distances. "Keys" are coordinates rounded to 5 dp.

**Positives (`prepare_training_data.py`):**
1. Load `evaluated_sightings_R` for every R in `REGIONS`. Raise unless
   `state == region == R` on every row.
2. Keep habitat rows (`~nonveg_landcover`) unconditionally.
3. Drop rows lacking a full `WINDOW_PX` window in every `FEATURE_SPEC`
   raster at the vintage `dataset.py` reads: `rd.raster_path(feat, year)`
   (`dataset.py:127`), with `year` filled as at `:98-101`. Record the
   count.
4. Thin once over the pooled rows. Visit rows in ascending
   `order_key(SPLIT_SEED, coord)` (ties broken by lon, then lat). Keep a
   row if no kept row is closer than `MIN_SPACING_M`.
5. Compute `block_ids` over the kept rows. Visit blocks in ascending
   `order_key(SPLIT_SEED, block_id)`. Add whole blocks to validation until
   the running record count reaches `round(VAL_FRACTION × N)`, the same
   accumulation rule as `:105-111`.
6. Write the per-region `thinned_/train_/val_positives_R.csv` (with
   `region`, `block_id`, `split`) and **one** global
   `data/pipeline/block_assignments.csv` (`block_id`, `split`, `n`).

**Candidate pool (`generate_negatives.py`, pooled pass):**
1. Load `gbif_negatives_R` for every R. Raise unless `state == R`.
2. Apply the `MAX_COORD_UNCERTAINTY_M` filter (today inert: 0 of 265,212
   rows carry a value).
3. Deduplicate on the key, keeping the first row in file order. Raise if
   a key is filed under two states (today 0). 265,212 → 35,678.
4. Drop every record `verify_partition` returns, and record the
   coordinates. Today that is 6: 5 inside no polygon, 1 filed NH inside
   ME. None is relabelled: `state` is the acquisition query key, and an
   audited exception list would grow silently.
5. Thin once over the pooled candidates, as in positives step 4.
6. Drop candidates within `BUFFER_M` of any row of any region's
   `evaluated_sightings` (all rows, vegetated or not, pooled). Record the
   count removed.
7. Extract the envelope features on the grid of the record's own region,
   with `rd.raster_path(feat, year)` as `:198-205` does. Drop rows with
   nodata (`:207`).
8. Drop windowless rows, as in positives step 3.
9. Compute `evt_phys`, `envelope_id` (binners fitted on the region's
   `evaluated` habitat rows, `:220-222`), `is_nonveg`, `weight` and
   `weight_basis` (`build_weight`, unchanged).
10. Assign `block_id`. Assign `split`: the block's split if the block is
    in `block_assignments.csv`. Otherwise use `split_for_unassigned`
    (md5, unchanged) with `val_fraction` equal to the share of
    positive-occupied blocks in validation. That share is global now; it
    is 0.197 on today's files.
11. Persist the pool as `data/negatives/candidate_pool.csv`. Columns:
    `longitude, latitude, x_5070, y_5070, state, region, year,
    common_name`, the envelope features, `evt_phys, envelope_id,
    is_nonveg, weight, weight_basis, block_id, split`.

**Draw (per region R and split s):** `n = round(n_pos(R, s) × NEG_RATIO)`;
`n_nv = min(round(n × NONVEG_MAX_FRAC), |NonVeg pool|)`;
`n_hab = n − n_nv`.
- If the habitat pool is smaller than `n_hab`, **raise**. This replaces
  the beyond-cap top-up at `:278-286`.
- Within each sub-pool, select the `n_*` rows with the largest
  `log(u) / weight`, where
  `u = (order_key(SPLIT_SEED, "neg:" + coord) + 0.5) / 2**64`.
  This is weighted sampling without replacement (Efraimidis–Spirakis),
  the same distribution `rng.choice(..., replace=False, p=w)` targets. It
  is order-invariant, and it removes `weighted_take`'s `.loc`
  duplicate-label hazard (`:267-274`) because no index labels are used.
- Every pooled `pd.concat` uses `ignore_index=True`.

**Writes.** Both scripts build every output in memory, raise before any
write, then write each file to a temp path and `os.replace` it. The
per-region negative files keep their columns (`:304-309`).

**Split manifest.** `data/pipeline/split_manifest.json`. Contents:
- every §1 constant and the CR-0007 constants used;
- the hash spec;
- the sha256 of every input and every output file;
- the count at every numbered step, per region;
- the dropped coordinates from pool step 4;
- the git commit;
- the pandas, numpy, scipy, pyproj and PROJ versions, and the PROJ
  operation string for 4326→5070.

### 3. CLI and ownership
- `prepare_training_data.py` loses `--min-spacing-m`, `--block-size-m`,
  `--val-fraction`, `--seed` and `--habitat-only` (the last is
  `store_true, default=True`, so it can never be switched off).
  `MIN_SPACING_M_DEFAULT`, `BLOCK_SIZE_M_DEFAULT` and the unused `rng`
  (`:102`) are deleted. `generate_negatives.py` loses `--seed`.
- `--regions` on either script is a diagnostic dry run that refuses to
  write. A subset run would produce a global table covering only that
  subset.
- `prepare_training_data.py` owns the block grid and the validation draw.
  `generate_negatives.py` reads `block_assignments.csv` and never draws.
- `:153`'s bare `except Exception` no longer swallows `MissingDataError`.
  It re-raises. Any other exception is logged with its type and traceback
  (PA-0011).

### 4. `grouse_data.py`
Add `PATH_TEMPLATES` entries for `block_assignments.csv`,
`candidate_pool.csv`, `split_manifest.json` and CR-0013's
`acceptance_record.json`. Remove the per-region `block_assignments`
entry (`:122`). Move the accessor from `RegionData` (`:440-441`) to
`GrouseData`.

### 5. Standing checks (`train.py`, `calibrate.py`, `bench_pipeline.py`)
`build_datasets` (`train.py:238-317`) calls
`acceptance_split.standing_checks()` once, before the region loop
(`:253`), so it raises before any `GrousePatchDataset` is built. The loop
body and the return contract are unchanged. The callers are
`train.py:980`, `calibrate.py:355` and `bench_pipeline.py:95`.
`standing_checks`:
- reads the CSVs itself, so it never touches `RegionData`'s cached frames;
- checks every region in CR-0013's config, whatever `regions` the caller
  passed;
- runs the coordinate-only exact gates CR-0013 lists;
- refuses unless `acceptance_record.json` exists and its digests match the
  files being read;
- uses `raise`, not `assert`.

It also refuses a run whose `img_size + 2·jitter` exceeds the manifest's
`WINDOW_PX`.

`smoke_test_training.py`, `diagnose_training.py` and `diagnose_wetland.py`
build datasets without `build_datasets`. They are not gated, and are
listed here so that is visible.

### 6. `sample_background_points` (`train.py:120-165`)
Keep only points where `regions.in_state(..., region)` is true. The
existing budget (40 batches of 2 × remaining) absorbs the ~50 % rejection
rate. geopandas is imported only on this path, which is reached only when
`--an-background > 0`. The 0/nodata conflation at `:143` is filed as
BUG-0032 and not fixed here.

### 7. Duplicate scripts (PA-0002; BUG-0031 is filed by CR-0007)
Runtime `SystemExit` guards on four scripts:
- `clean.py` and `legacy/gen_negs.py`: executable copies of the two
  rewritten scripts that write the same paths. `legacy/gen_negs.py` would
  read the global block table while computing box-anchored ids.
- `legacy/download.py` and `legacy/download_more.py`: diverged copies
  writing `download_rev.py`'s raster paths.

The recorded evidence scripts that import the removed names are run from
a worktree at commit `ec1470a`, not ported.

## Acceptance
Run `acceptance_split.py` (CR-0013) on the rebuilt artifacts. Every GATE
passes, and it writes `acceptance_record.json`. The gates, their
definitions and their config are CR-0013's and are not restated here.

## Impact
- **Every checkpoint and metric stops being comparable.** Train and val
  files, negative weights and splits all change. `train.py`,
  `calibrate.py` and `bench_pipeline.py` refuse pre-CR data, so CR-0009's
  pre-CR baselines must already be captured (deliverable 0).
- **Expected on today's inputs** (the rebuild reads CR-0007's regenerated
  files, so these are expectations, not predictions):
  - 6,232 positives (ME 3,660 / NH 1,079 / VT 1,493) in 3,861 blocks;
  - 759 validation blocks holding 1,246 records.
  - NH roughly halves against today's 2,244-row NH file.
- **Readers:** `get_negatives.py:128` (row count of `thinned_positives`),
  `organize_project.py:73` (per-region `block_assignments` glob),
  `tune.py`, and the evidence scripts.
- **Docs:** `ARCHITECTURE.md:59`, `grouse_data.py:20`, the module
  docstrings at `prepare_training_data.py:15-33` and
  `generate_negatives.py:19-24`, and `PROJECT_TREE.md`.
- **Not affected:** rasters, model architecture, `predict.py`.

## Risk: MEDIUM-HIGH
| risk | mitigation |
|---|---|
| Validation metrics fall | That is the correct outcome. It is never a rollback trigger. |
| The acceptance replay and the pipeline share a misreading of §2 | CR-0013's attack suite runs every recorded attack against the implemented gates |
| A gate raises halfway through a write | Every output is built in memory, all raises come first, and each file is replaced atomically |
| A library upgrade changes the hash order or PROJ output | Versions and the PROJ operation are in the manifest. CR-0013 fails on a mismatch rather than accepting a different split. |
| The habitat pool falls short after CR-0007's reweighting | The draw raises; the shortfall is visible in the manifest counts |
| Pre-CR baselines lost | Deliverable 0 is a precondition |
| Stale per-region block tables stay resolvable | Template removed; files deleted after the backup is verified |

## Test plan
**Validatable here:**
- The full rebuild; `acceptance_split.py` passes.
- A second run of both scripts produces byte-identical outputs.
- Running with `REGIONS` reordered produces identical outputs.
- `--regions ME` refuses to write.
- The five guards fire.
- The standing checks refuse the backed-up pre-CR files.
- The standing checks refuse `--jitter 8`.
- `smoke_test_training.py` runs.
- Import smoke of every module named in §3–§7.

**Not validatable here:**
- Model quality (CR-0009).
- `--an-background > 0` in a real run (no recorded run uses it).
- Hash-order stability across a future pandas, numpy or PROJ release.
  The manifest detects it; nothing prevents it.

## Deliverables (in execution order)
- [ ] 0. **Precondition:** CR-0009 deliverable 2 (pre-CR baselines) is
      done. The standing checks make pre-CR data unreadable afterwards.
- [ ] 1. **Precondition:** CR-0007 has landed, and `check_partition.py`
      passes on the current `data/pipeline/`. CR-0007's backup exists and
      its manifest verifies.
- [ ] 2. **Precondition:** CR-0013 is approved, with `acceptance_split.py`
      and its config committed.
- [ ] 3. `regions.py` §1; `prepare_training_data.py` and
      `generate_negatives.py` per §2–§3.
- [ ] 4. `grouse_data.py` §4. Update the readers and docs listed in Impact.
- [ ] 5. Standing checks (§5), `sample_background_points` (§6), guards (§7).
- [ ] 6. Run `prepare_training_data.py`, then `generate_negatives.py`.
      Run `acceptance_split.py`; every GATE passes. Run the test plan.
- [ ] 7. Delete `data/pipeline/block_assignments_{ME,NH,VT}.csv`.
- [ ] 8. Bookkeeping:
      - File BUG-0032 (`sample_background_points` 0/nodata, open, fix
        deferred).
      - New BUG (next free id) for `generate_negatives.py:153` swallowing
        `MissingDataError` (PA-0011 recurrence review).
      - BUG-0027 and BUG-0029 status: fixed, closing under CR-0009.
      - PA-0018's Swept? cell: the pooled-holdout enforcement is CR-0013's
        standing checks.

## Landing order
CR-0010, CR-0008 (landed) → CR-0007 → CR-0013 approved → CR-0009
baselines → **CR-0012** → CR-0009 retrain. CR-0014 (`road_dist`) should
land before deliverable 6; if it lands after, the acceptance run is
repeated (CR-0013 E8 reads `road_dist` extents, O8 its values).

## Out of scope
- Acceptance gate definitions → CR-0013.
- Membership and constants → CR-0007.
- BUG-0034 (positive/negative year floors). Its fix changes the positive
  set; CR-0013's replay gates need no re-derivation for it.
- The 0/nodata conflation in `sample_background_points` (BUG-0032).
- Block size, validation fraction and NonVeg cap as design choices.
  Stratified validation draws (not adopted; see the review log).
- `scripts_backup/`: untracked copies that use pre-reorganisation paths
  (e.g. `landfire_data/`), so they cannot write current `data/` paths.
