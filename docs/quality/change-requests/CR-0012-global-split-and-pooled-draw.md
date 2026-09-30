# CR-0012: One global block grid, one pooled train/val split, one pooled negative draw

**Status: TEXT APPROVED (v2.2.1, commit `cec1542`), 2026-09-30.** Implementation waits for CR-0013 approval and CR-0009's baselines (deliverable 0).
History, verdicts and dispositions: `CR-0012-review-log.md`. Split from
CR-0007 v7 (`bb170ea`). This document states only current intent.

## Scope
Replace the per-region positive thin, block split and negative draw with
pooled computations on one global block grid. Each is specified as a
deterministic, order-free function of its inputs, so that CR-0013 can
replay it exactly.

## Why now
BUG-0027 is still live. The holdout runs per region, on a grid anchored at
that region's box (`prepare_training_data.py:85-114`,
`generate_negatives.py:98-107`). On today's files:
- 522 of 1,674 pooled validation positives have a training positive at
  the identical coordinate.
- On one global 3 km grid, 882 blocks hold both training and validation
  records, counting positives and negatives (541 counting positives
  only).

Every validation metric is inflated by this. CR-0007 gives every record a
single region, which is the prerequisite for pooling.

## The change

### 1. Constants and helpers (`regions.py`, added to CR-0007's table)
| name | value |
|---|---|
| `BLOCK_ORIGIN_5070` | `(0.0, 0.0)` |
| `VAL_FRACTION` | 0.2 |
| `SPLIT_SEED` | 42 (the only seed source; no CLI seed) |
| `WINDOW_PX` | 64 (`train.IMG_SIZE` + 2 × default jitter 0) |

- `block_ids(x, y)` returns
  `f"{floor((x-x0)/BLOCK_SIZE_M)}_{floor((y-y0)/BLOCK_SIZE_M)}"`. It is the
  only block-id function. `assign_spatial_blocks` and `compute_block_ids`
  lose `box`.
- `order_key(text)` is
  `int.from_bytes(blake2b(f"{SPLIT_SEED}:{text}".encode(), digest_size=8).digest(), "big")`.
  Coordinates are formatted `f"{lon:.6f},{lat:.6f}"`.
- `window_in_bounds(src, x, y)`:
  - `(row, col) = rowcol(src.transform, x, y)`, rounding down, as
    `dataset.py`'s `src.index` does;
  - `h = WINDOW_PX // 2`;
  - true iff `[row−h, row−h+WINDOW_PX) × [col−h, col−h+WINDOW_PX)` lies
    inside `[0, height) × [0, width)`.

  Nodata inside the window is **not** considered: `dataset.py` reads it as
  missing. So CR-0014's new Canada nodata drops no record.
- Deleted from `prepare_training_data.py`: `REGIONS_DEFAULT` (`:42`),
  `MIN_SPACING_M_DEFAULT`, `BLOCK_SIZE_M_DEFAULT`, `VAL_FRACTION_DEFAULT`
  (`:53`), `RANDOM_SEED_DEFAULT` (`:54`) and the unused `rng` (`:102`).

### 2. Specification
Conventions:
- Distances are Euclidean in EPSG:5070, compared as squared float64.
- "Keys" are coordinates rounded to 5 dp.
- Every sort is stable (`kind="mergesort"`).
- Every pooled `pd.concat` uses `ignore_index=True`.
- **Rounding.** Every `round(...)` below is Python's built-in `round()`
  on the float64 product, which rounds half to even, as the current code
  does. It applies to `round(VAL_FRACTION × N)`, `round(n_pos × NEG_RATIO)`
  and `round(n × NONVEG_MAX_FRAC)`.
- **Parsing.** CSVs are read with `float_precision="round_trip"`.
- **Writing.** CSVs are written with pandas' default float repr.
- **Output row order.** Every output is canonically sorted, stably, by:
  - `longitude`, then `latitude`, for the positive, negative and pool
    files; the pool is sorted by `region` first;
  - `block_id`, for `block_assignments.csv`.

  Train/val files keep that order. Digests are taken on those bytes.
- The split-for-unassigned rule in pool step 10 is the current
  `split_for_unassigned` (`generate_negatives.py:110-115`), with the seed
  fixed to `SPLIT_SEED` and `vf` =
  `(block_assignments.split == "val").mean()` over positive-occupied
  blocks.

**Positives (`prepare_training_data.py`):**
1. Load `evaluated_sightings_R` for every R in `REGIONS`. Raise unless
   `state == region == R` on every row.
2. Keep the habitat rows (`~nonveg_landcover`).
3. Drop rows that fail `window_in_bounds` in any `FEATURE_SPEC` raster at
   `rd.raster_path(feat, year)`, with `year` filled as at
   `dataset.py:98-102`, the column max taken over the region's
   habitat rows from step 2 (no NaN years exist today).
4. Thin the pooled rows. Visit rows by ascending `order_key(coord)`, ties
   broken by lon then lat. Keep a row iff its squared distance to every
   already-kept row is ≥ `MIN_SPACING_M²` (a row exactly
   `MIN_SPACING_M` away is kept, as today and as CR-0013 E2 requires).
5. Assign `block_ids`. Visit blocks by ascending `order_key(block_id)`.
   Add whole blocks to validation until the running record count reaches
   `round(VAL_FRACTION × N)` (the `:105-111` rule).
6. Write, per R, `thinned_/train_/val_positives_R.csv`, adding
   `block_id` and `split`. `region` already exists in the `evaluated_sightings_R` rows (CR-0007 §2).
   The columns are exactly CR-0013's config `columns.positives`, in that
   order, selected from the `evaluated_sightings_R` rows by name; so `region` follows `envelope_id`.
   The train and val files are exactly the combined file's `split` rows.
   Write one `block_assignments.csv` with columns
   `columns.block_assignments`.

**Candidate pool (`generate_negatives.py`):**
1. Load `gbif_negatives_R` for every R. Raise unless `state == R`.
2. Apply the `MAX_COORD_UNCERTAINTY_M` filter.
3. Deduplicate on the key, keeping the row with the **smallest `gbif_id`**.
   `gbif_id` is non-null and unique over all 265,212 rows. File order is
   not used because 6,492 keys carry more than one `year`. Raise if a key
   is filed under two states (today: 0). 265,212 → 35,678.
4. Drop every record `verify_partition` returns, and record the
   coordinates. Today that is 6: 5 inside no polygon, and 1 filed NH but
   inside ME. They are dropped, not relabelled, because `state` is the
   acquisition key.
5. Thin, as in positives step 4.
6. Drop candidates whose squared distance to any row of any
   `evaluated_sightings_R` is `≤ BUFFER_M²`. Record the count.
7. Extract the envelope features on the region's grid with
   `rd.raster_path(feat, year)` (`:198-205`). Drop rows with nodata
   (`:207`).
8. Drop rows failing `window_in_bounds`, as in positives step 3.
9. Compute `evt_phys`, `envelope_id` (binners fitted on the region's
   `evaluated` habitat rows, `:220-222`), `is_nonveg`, `weight` and
   `weight_basis` (`build_weight`, unchanged).
10. Assign `block_id`. `split` is the block's split if the block is in
    `block_assignments.csv`. Otherwise it is `val` iff
    `int(md5(f"{SPLIT_SEED}:{block_id}").hexdigest(), 16) % 10000 < vf × 10000`,
    where `vf` is the share of positive-occupied blocks in validation
    (0.197 today).
11. Write `data/negatives/candidate_pool.csv` with these columns:
    `longitude, latitude, x_5070, y_5070, state, region, year,
    common_name, gbif_id`, the envelope features,
    `evt_phys, envelope_id, is_nonveg, weight, weight_basis, block_id,
    split`.

**Draw (per R and split s):**
- `n = round(n_pos(R, s) × NEG_RATIO)`.
- `n_nv = min(round(n × NONVEG_MAX_FRAC), |NonVeg pool|)`.
- `n_hab = n − n_nv`.
- A habitat pool smaller than `n_hab` **raises**. This replaces the
  top-up at `:278-286`.
- In each sub-pool, select the `n_*` rows with the largest
  `log(u)/weight`, where `u = (order_key("neg:" + coord) + 0.5) / 2**64`.
  Ties are broken by ascending `order_key("neg:" + coord)`. This is
  Efraimidis–Spirakis sampling without
  replacement. It uses no index labels, which removes `weighted_take`'s
  `.loc` hazard (`:267-274`).
- Write `negatives_R.csv` with exactly CR-0013's config
  `columns.negatives`: the `:304-309` columns, then `region`. Its train
  and val files are exactly its `split` rows. The pool file uses
  `columns.pool`.

**Split manifest (`data/pipeline/split_manifest.json`).** It has two
sections, one written by each script:
- **`positives`**: written by `prepare_training_data.py`, which also
  deletes any `negatives` section and any `acceptance_record.json`.
- **`negatives`**: added by `generate_negatives.py`, which first raises
  unless the `positives` section's output digests match the files on
  disk.

The manifest's keys, the meaning of its counts (rows of a region
remaining after each numbered step), the `draw` object and the format of
the dropped list are defined by CR-0013's config `manifest_schema`
(`docs/quality/acceptance_split.json`), which is normative. Every path
key in `inputs` and `outputs` is **repo-relative**, formed exactly as the
config's `paths` and `raster.template` form it (e.g.
`data/pipeline/thinned_positives_ME.csv`). Each section records the values
the script **actually used**, measured at run time — never a copy of the
config — so that E11's comparison with the config detects drift:
- every constant in CR-0013's config list, one for one, as read from
  `regions.py` and the script;
- the hash spec;
- the sha256 of every input read (including each raster) and every output
  written;
- the count at every numbered step, per region;
- the dropped coordinates (pool step 4);
- the git commit, and `dirty: true` if `git status --porcelain` lists any
  tracked `.py` file;
- the environment the run used, in the shape of the config's
  `environment` object (library versions from the imported modules, and
  the 4326→5070 operation string produced per `environment.op_rule`).

**Writes.** Each script builds all its outputs in memory, raises before
writing anything, then writes each file to a temp file in the same
directory and `os.replace`s it.

### 3. CLI, errors, ownership
- `prepare_training_data.py` loses every flag: `--regions`,
  `--min-spacing-m`, `--block-size-m`, `--val-fraction`, `--seed` and
  `--habitat-only`.
- `generate_negatives.py` loses `--regions` and `--seed`.
- Both scripts always run over `REGIONS`.
- `prepare_training_data.py` owns the grid and the validation draw.
  `generate_negatives.py` only reads them.
- `generate_negatives.py:153`: the pooled pass has no skip path.
  `MissingDataError` propagates. Any other exception is logged with its
  type and traceback, then re-raised (PA-0011).

### 4. `grouse_data.py`
- Add `PATH_TEMPLATES` entries for `block_assignments.csv`,
  `candidate_pool.csv`, `split_manifest.json` and
  `acceptance_record.json`.
- Remove the per-region `block_assignments` entry (`:122`).
- Move the accessor (`:440-441`) to `GrouseData`.

### 5. Standing checks
`build_datasets` (`train.py:238-317`) calls
`acceptance_split.standing_checks(img_size, jitter, augment)` once, before the
region loop (`:253`). Nothing else in the loop or the return contract
changes. This covers the callers `train.py:980`, `calibrate.py:355` and
`bench_pipeline.py:95`. What `standing_checks` checks is defined by
CR-0013. The window check uses the effective pad, which is `jitter` if
`augment` else 0 (`dataset.py:75`): it refuses
`img_size + 2 × pad > WINDOW_PX`.

`smoke_test_training.py`, `diagnose_training.py` and `diagnose_wetland.py`
bypass `build_datasets`, so they are not gated.

### 6. Duplicate scripts (PA-0002; BUG-0031 is filed by CR-0007)
`clean.py` and `legacy/gen_negs.py` get a `SystemExit` as their first
statement, before any import. They are executable copies of the two
rewritten scripts and write the same paths. The evidence scripts that
import the removed names are run from a worktree at `05d788d`.

## Acceptance
Run `acceptance_split.py` (CR-0013). Every GATE passes, and
`acceptance_record.json` is written. The gates and config are CR-0013's.

## Impact
- **Every checkpoint and metric stops being comparable.** Pre-CR data is
  refused by the standing checks, so CR-0009's pre-CR baselines must come
  first (deliverable 0).
- **Schemas:**
  - positive files gain `region`;
  - negative files gain `region`;
  - `block_assignments` becomes one global file;
  - new files: `candidate_pool.csv`, `split_manifest.json`.
- **Expected on today's inputs** (not a prediction; the rebuild reads
  CR-0007's files):
  - 6,232 positives (ME 3,660 / NH 1,079 / VT 1,493) under this
    specification, against 6,230 from the legacy thinner;
  - 3,861 blocks, of which 759 are validation blocks holding 1,246
    records.
  - CR-0009's figures should be updated to match.
- **Readers of changed files:**
  - `get_negatives.py:128` (row count of `thinned_positives_R`);
  - `organize_project.py:73` (per-region `block_assignments` glob);
  - `diagnose_training.py:49-50`, `diagnose_wetland.py:157-159`,
    `smoke_test_training.py:74` (read the split files; the added column
    is harmless);
  - `tune.py`;
  - `diagnose_road_bias.py:132` and `diagnose_water_bias.py:123`.
- **Docs:** `ARCHITECTURE.md:59`, `grouse_data.py:20`, the module
  docstrings at `prepare_training_data.py:15-33` and
  `generate_negatives.py:19-28`, and `PROJECT_TREE.md`.
- **Not affected:** rasters, models, `predict.py`, and
  `sample_background_points` (moved to CR-0015).

## Risk: MEDIUM-HIGH
| risk | mitigation |
|---|---|
| Validation metrics fall | This is the correct outcome, never a rollback trigger |
| Replay and pipeline share a misreading | CR-0013 separate authorship and attack suite |
| A gate raises mid-write | All outputs built in memory; raises come first; atomic replace |
| Partial run: positives rebuilt, negatives stale | The `negatives` section and the record are deleted by `prepare_training_data.py`. `generate_negatives.py` checks the positive digests. The standing checks refuse until acceptance. |
| Library upgrade changes hash order or PROJ output | Versions pinned in the manifest; CR-0013 E11 fails |
| Habitat shortfall after CR-0007's reweighting | The draw raises; the counts are in the manifest |
| Pre-CR baselines lost | Deliverable 0, with a fallback |

**Rollback.** Restore only this CR's outputs from CR-0007's backup —
`thinned_positives_*`, `train_positives_*`, `val_positives_*`,
`block_assignments_*`, `negatives_*`, `train_negatives_*`,
`val_negatives_*` — never CR-0007's own outputs (`evaluated_*`,
`envelope_metrics_*`, `nonveg_flagged_*`), which would revert the
partition. Delete `block_assignments.csv`, `candidate_pool.csv`,
`split_manifest.json` and `acceptance_record.json`. Revert the code
commit.

## Test plan
**Validatable here:**
- The full rebuild and acceptance.
- A second run gives byte-identical outputs.
- **Order test.** Run from a scratch working directory whose `data/`
  holds copies of the input CSVs with rows randomly permuted (rasters
  symlinked). Outputs must be byte-identical. This exercises the
  order-free dedup, the hash order and the stable sorts.
- Both guards fire.
- The standing checks refuse the backed-up pre-CR files and `--jitter 8` with augmentation.
- A partial run (positives only) is refused.
- `smoke_test_training.py` runs.
- Import smoke of every module named in §3–§6.

**Not validatable here:**
- Model quality (CR-0009).
- Hash and PROJ stability across future releases. The manifest detects
  a change; nothing prevents it.

## Deliverables (in execution order)
- [x] 0. **Precondition: CR-0009 deliverable 2 done.**
      - CR-0009 v4 must be committed.
      - Capture item 3's in-box point set and every other pre-CR
        measurement that CR-0009 lists. Write them to
        `docs/quality/evidence/CR-0009/`, with a `SHA256SUMS` file.
        Commit both.
      - Verify by re-reading the files against `SHA256SUMS`.
      - Fallback if this is missed: in a git worktree at `05d788d`,
        restore `data/pipeline/` and `data/negatives/` from CR-0007's
        backup, symlink the rasters, and take the measurements there.
- [x] 1. **Precondition:** CR-0007 has landed and `check_partition.py`
      passes. CR-0007's backup manifest verifies.
- [x] 2. **Precondition:** CR-0013 is approved, with its script, config and
      tests committed.
- [x] 3. `regions.py` §1; `prepare_training_data.py` and
      `generate_negatives.py` §2–§3.
- [x] 4. `grouse_data.py` §4. Update the readers and docs in Impact.
- [x] 5. Standing-check call (§5) and guards (§6).
- [x] 6. Run `prepare_training_data.py`, then `generate_negatives.py`,
      then `acceptance_split.py`; every GATE passes. Run the test plan.
      Real run `1bc2df6` (18/18 GATEs); test plan 7/7 PASS (`docs/quality/evidence/CR-0012-d6/test_plan.txt`; item 7 after BUG-0056/0057 fix `40dbecf`).
      CR-0014 should have landed first; if it lands after, repeat this
      step.
- [ ] 7. Delete `data/pipeline/block_assignments_{ME,NH,VT}.csv`.
- [x] 8. Bookkeeping (done 2026-09-30; details in `CR-0012-review-log.md`
      § Deliverable 8):
      - BUG-0049 for `generate_negatives.py:153`, with a PA-0011
        recurrence review. It is a recurrence, so PA-0027 supersedes
        PA-0011. PA-0027's sweep filed BUG-0052..0055.
      - BUG-0027: fixed, closing after CR-0009.
      - BUG-0029: the positive-side part is fixed. The assumed-negative
        part waits for CR-0015.
      - PA-0018's Swept? cell: pooled-holdout enforcement is provided by
        CR-0013.
      - PA-0023's Swept? cell, checked against the code: pool step 6
        pools every region's sightings, but they are US-only, so the
        Canadian-sightings question is **not** closed. It is re-owned by
        BUG-0050 (buffer) and BUG-0051 (KDE), and needs a new CR.
      - BUG-0031 is FIXED (5 of 5), and the tracker items are updated.

## Landing order
CR-0007 → CR-0013 approved → CR-0009 baselines → **CR-0012** → CR-0009
retrain. CR-0014 lands before deliverable 6, or deliverable 6 is repeated.
CR-0015 (assumed negatives) is independent.

## Out of scope
- **`sample_background_points`**, the BUG-0029 remainder and BUG-0032.
  This is moved to CR-0015, not yet written (tracker). The function is
  live: `pretrain.py:63,179` calls it unconditionally, and
  `sweep/launch.sh` uses `--an-background 1.0`.
  CR-0015 must also restrict the points to **training blocks**. Today
  about 20 % of them fall in validation blocks (CR-0012 round-1 A1).
- **Guards on `legacy/download.py` and `legacy/download_more.py`.** These
  are unrelated to the split (tracker; BUG-0031 sweep).
- Acceptance gates (CR-0013). Membership and constants (CR-0007).
  BUG-0034.
- Block size, validation fraction and NonVeg cap as design choices.
  Stratified draws.
- `scripts_backup/`. It uses pre-reorganisation paths (e.g.
  `landfire_data/`), so it cannot write to `data/`.
