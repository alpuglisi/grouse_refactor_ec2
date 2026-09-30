# CR-0007: Partition records by state and run the train/val block holdout once over the pooled data

**Status: REVISED (v2) after review — awaiting re-review
(`CLAUDE.md` §1.2).** Nothing committed. All deliverables pending.

### Revision note (v1 → v2)
Two reviewers returned on v1: APPROVE WITH CHANGES (1 blocking) and
REJECT (1 blocking). A third review was still running when this revision
was written and its findings are not yet incorporated.

1. **Assertion (d) was a tautology and is replaced** (blocking). Given
   (a), each class's per-region `state` histogram is `{R: 1.0}` by
   construction, so (d)'s gap was identically **0.000 pp for any
   negative draw whatsoever**. A reviewer built a conformant pipeline
   that drew negatives only from the southern half of each state — every
   gate green while the positive/negative spatial support collapsed,
   reproducing BUG-0029 at ~15× its pre-CR magnitude. v1 had deleted the
   check that catches this (the per-region occupied-block support test)
   and kept only the one that cannot.
2. **Pooled `concat` index discipline is now specified** (blocking).
   `weighted_take` uses `subpool.loc[idx]`; pooling the three candidate
   frames without `ignore_index=True` makes labels repeat and `.loc`
   returns every match — overshooting the negative quota with duplicated
   records, i.e. reintroducing double-weighting on the negative side by
   way of the fix for it. Demonstrated: a 3-element pick returned 6 rows.
3. `verify_partition()` now has an implementing call site for the
   **negative** class; v1 placed it only in `analyze_grouse`, which never
   sees negatives, while both known exceptions are negatives.
4. **The NH box question is resolved cheaply instead of deferred**: 721
   of 69,219 NH candidates lack a full window, and v1 replaced the
   selection step, so drawing one was sampling luck and I5 would have
   failed with no remedy.
5. Preservation rules R5–R7 added; R1's remedy made structural.
6. Per-region validation fraction, a parameter manifest, and a
   recorded-vs-recomputed `block_id` check added to the acceptance set.
7. Several of v1's own numbers corrected — see "Corrections to v1".

### Corrections to v1
- **I5's "NH 4 / 6"**: `--jitter` defaults to **0** (`train.py:462`), so
  `read_size == img_size == 64` and the real count is **4**. The 6
  requires jitter 8, which no run uses. v1 also failed to say which
  record set "today" refers to: it is the **pre-partition** NH file
  (2,244 rows); the post-partition set (1,116) is **0**, which is a
  point in the partition's favour that v1 stated too loosely to land.
- **`analyze_grouse.py:439`** — the `MIN_VALID_FRAC` check is at
  **`:444`**; `:439` is the loop head.
- **§5's "measured effect: none"** for pooled negative thinning is
  true for the 30 m constraint (0 cross-state candidate pairs under
  30 m) but overstated: pooling still changes the *retained* set,
  because the greedy thinner shuffles once over 35,792 records instead
  of three times over ~12,000.

**Supersedes part of CR-0006**, which bundled this with raster coverage
fixes and a retrain. CR-0006 reached revision 3 and was rejected by both
of its fresh reviewers; five reviews produced 100+ concerns. The
partition design in it survived every attack; the raster half and the
acceptance layer did not. This CR carries the surviving half alone.
CR-0008 carries the raster work; CR-0009 carries the retrain. IDs follow
`CLAUDE.md`'s flat counter — CR-0006 stays on the register, marked
superseded, and is not renumbered.

## Scope
Fix BUG-0027 (cross-region train/val leakage) and BUG-0029 (mismatched
positive/negative spatial support) by making region membership a **state
partition** and running the spatial block holdout **once over the pooled
records**, with dataset-build assertions that make both classes
detectable.

## Why now
Both defects are confirmed on real data and independently reproduced by
four reviewers:

- **522 of 1,674 pooled validation positives (31.2 %) are also pooled
  training positives at the identical coordinate.** Within a region the
  block holdout works (0.0 % of val positives have a train positive
  within 30 m); pooled it is 31.7 %.
- **A further 1,131 positive coordinates are duplicated inside a single
  split** — straight double sample-weighting. (CR-0006 cited only the
  522, understating the duplicate problem threefold.)
- 1,128 of the NH region's 2,244 positives lie outside New Hampshire,
  against **0** of its negatives by the `state` column (1 by polygon).

Every validation number in this repository is therefore unusable,
including the `0.811` best-rank figure used to choose between
checkpoints.

**Not why now:** the Errol map symptom the investigation started from is
**already fixed** by `bf8d31a` — `P(ME pixel > NH pixel)` 0.8513 → 0.5400
on the reported map's checkpoint, with the NH side unmoved. This CR does
not fix that symptom; CR-0009 exists partly to prove it is still fixed
after a rebuild.

## The change

### Root causes
- **BUG-0027:** a spatial computation that must be global (the block
  holdout) is run on per-region subsets selected by overlapping labels,
  so its guarantee holds within a region but not across the pool.
- **BUG-0029:** the two label classes are drawn from differently-shaped
  regions — positives by bounding box, negatives by state — so their
  spatial supports do not coincide, and nothing compares them.

Both have one cure: partition records by **state**, so positives adopt
the definition negatives already use.

### 1. `regions.py` — membership key and shared constants
- **Partition key: the existing `state` column.** Verified: `state`
  equals the dissolved TIGER-2023 county polygon for **43,024 of 43,024**
  raw sightings, 0 outside all polygons, and one reviewer measured **max
  distance-to-own-polygon 0.0 m**. For positives this is evidential —
  `analyze_grouse.load_all_sightings:167` takes it from the filename,
  and those files are written by `sightings.py:132` grouping a GBIF
  export by `stateProvince`, so it is GBIF's per-record value.
  **For negatives it is definitional**, not evidential:
  `get_negatives.py:268` passes `stateProvince` as a query parameter and
  `generate_negatives.py:302` carries it into the column. Recorded as a
  known limit, not presented as verification.
- **`verify_partition()`** — new, mandatory in `analyze_grouse.py`,
  polygon-based, source pinned to `data/roads/tl_2023_us_county.zip`
  dissolved by `STATEFP`. The generalized `cb_*_20m` boundaries are
  forbidden (they generate false disagreements). Predicate: `within`.
  **It must be given a disposition rule before it can pass** — see
  "Known exceptions" below.
- **Constants centralised here** (PA-0001), each currently duplicated or
  drifted:
  - `STATE_FIPS` — `generate_road_distance.py:115` and
    `diagnose_road_bias.py:71`.
  - `MIN_SPACING_M = 30` — `prepare_training_data.py:49` and
    `generate_negatives.py:71`; §3 fuses the two thinning steps, so they
    must not be able to drift.
  - `BLOCK_SIZE_M = 3000` — currently `prepare_training_data.py:52`,
    imported by `generate_negatives.py:60`.
  - **`BLOCK_ORIGIN_5070 = (0.0, 0.0)`** — new, and the most important.
    `assign_spatial_blocks:95` and `compute_block_ids:104` must agree on
    it *exactly*; if they drift, a positive and a negative at the same
    spot get different block ids and BUG-0027 is recreated. CR-0006
    specified a "global origin" without naming it as a shared constant,
    and a reviewer demonstrated a drifted-origin pipeline that passed
    every one of its acceptance checks.
- `BOXES` is documented as **raster request extents only**. Its NH entry
  does not cover the NH polygon (polygon reaches −70.5751, box −70.600;
  0.0299 % of the state outside, 0.0665 % including a 32 px margin).
  Membership no longer depends on it, but §7 and CR-0008 still sample
  over it, so widening NH to ≈ −70.563 is **raised as an open question**
  — the cost is re-downloading every NH raster, since `BOXES` is the
  download AOI (`download_rev.py:22`).

### 2. `analyze_grouse.py` — partition and consistent availability
- `clip_to_region` (`:198-203`) selects on `state == region`, writes an
  explicit `region` column, and calls `verify_partition()`. An unknown
  `state` value is an **error**, not a silent zero-row drop.
- `background_envelope_sample` (`:411`), `background_nonveg_rate`
  (`:324`) and the KDE fit set are clipped to the partition. Measured
  in-state share of the availability sample *after* the `dropna` and
  non-veg drop those functions apply: **ME 95.9 %, NH 53.2 %, VT
  55.2 %** — so the `Selection_Ratio` bias is severe for NH and VT and
  near-nil for ME. Because this drops ~47 % of the NH/VT sample, the
  draw must **rejection-sample back up to `n_samples`**, and
  `:439`'s `n_valid >= n_samples * MIN_VALID_FRAC` check must be
  re-expressed against the clipped `n` or it silently tightens ~2×.
  Without that, judgeable envelopes fall (measured NH 50→48, VT 48→46 at
  `MIN_AVAIL_BG = 15`), pushing envelopes to `NEUTRAL_WEIGHT`.
- geopandas becomes a **declared dependency of the analysis path**.

### 3. `prepare_training_data.py` — one global grid, one draw
- `assign_spatial_blocks` (`:85-114`) loses its `box` argument and
  anchors on `BLOCK_ORIGIN_5070`.
- `main()`: load every region → concatenate → **thin once over the
  pooled records** → assign blocks and draw validation once → write each
  region's files plus **one global `block_assignments.csv`**.
- `--regions` subset runs become diagnostic-only and refuse to write,
  because a subset run would emit a global block table containing only
  that subset's blocks.
- Dead code removed: `--habitat-only` is `action='store_true',
  default=True` and can never be switched off (the habitat filter at
  `:149-150` becomes unconditional); the `rng` at `:102` is unused
  because the draw uses `block_counts.sample(random_state=seed)`.
- **Expected pooled positive count ≈ 6,230**, reproduced independently
  by three reviewers. A result near **6,508** indicates the habitat flag
  was taken from a foreign region's grid rather than the record's own —
  that is a diagnostic, not an acceptable alternative.

### 4. Duplicate scripts (PA-0002)
`clean.py`, `legacy/gen_negs.py` and `legacy/audit.py` are **executably
identical** to their live counterparts — AST-normalised diff with
docstrings stripped gives **0 / 0 / 2** differing lines, the 2 being a
literal moved to a shared import. All three get runtime `SystemExit`
guards.

The hazard is specific: `legacy/gen_negs.py` writes the *same*
`data/negatives/*.csv` paths, reads `block_assignments` and computes
region-local block ids. After this CR it would read the global file
while emitting local ids — the id ranges do not overlap at all, so 100 %
of candidates fall through to hash splitting, silently reintroducing
BUG-0027's leakage with no error.

**Also in scope, found during CR-0006's review:** `legacy/download.py`
and `legacy/download_more.py` are un-guarded, runnable, **diverged**
copies writing the same `data/landfire/{region}_{year}_{feature}.tif`
paths as `download_rev.py:82`. BUG-0015's remediation backported a fix
instead of deprecating the copy, so PA-0002 was violated by the change
recorded as satisfying it. Both get guards; PA-0002's and PA-0014's
Swept? rows are corrected.

### 5. `generate_negatives.py`
- `compute_block_ids` (`:98-107`) loses `box`, uses `BLOCK_ORIGIN_5070`.
- Reads the single global `block_assignments.csv`. **The per-region
  `block_assignments_{region}.csv` files are deleted and the per-region
  `PATH_TEMPLATES` entry removed** — leaving both namespaces resolvable
  is what makes the drifted-id failure reachable.
- 300 m buffer queries **pooled** grouse locations.
- Thinning pooled. **Measured effect today: none** — pooled negatives
  have 0 pairs under 30 m, because the per-state GBIF queries already
  partition the candidate coordinates. It is done for PA-0018
  conformance, not because it fixes a measured defect, and this CR says
  so rather than implying otherwise.
- `process_region` (`:133-324`) must be **split into a pooled pass and a
  per-region pass**: hygiene, thinning and the buffer become pooled,
  while envelope extraction (`:198-205`), metrics (`:227`) and the 1:1
  targets (`:250-251`) stay per-region. Pooled candidates are assigned a
  region by the **same `state` key** §1 defines. Verified: all three
  candidate files carry a `state` column holding only the 2-letter code.
- **Every pooled `pd.concat` uses `ignore_index=True`** — including the
  existing ones at `:289` and `:301`. `weighted_take` (`:267-274`) does
  `subpool.loc[idx]`; with repeated index labels `.loc` returns every
  match, overshooting the quota with duplicated records. Demonstrated:
  pooling two 4-row frames without `ignore_index`, a 3-element
  `rng.choice` returned **6 rows**. (Converting `weighted_take` to
  positional selection is an acceptable equivalent.)
- **`verify_partition()` runs on the pooled candidate frame here**, with
  the § Known-exceptions rule applied. §1 places the positive-side call
  in `analyze_grouse.clip_to_region`, which never sees negatives — and
  both known exceptions are negatives.
- **Candidates without a full `img_size + 2·jitter` window in every
  feature raster they would be read from are dropped before sampling**,
  and the count recorded (measured today: NH **721** of 69,219, ME 2,
  VT 0). This makes I5 unfailable by construction and resolves the NH
  box question (§1) without re-downloading any raster.
- Which pass owns the block-id/split step (`:241-247`) must be named.
  Note the semantics change: `val_fraction = (blocks['split']=='val').mean()`
  (`:243`) becomes a **global** block-level rate. Measured: per-region
  today ME 0.205 / NH 0.214 / VT 0.213; global **0.190**. That shifts the
  hash-split val rate ~2 pp for every candidate in a block holding no
  positives (~65 % of them).
- `binners = fit_scheme_binners(...)` (`:220-222`) is fitted on that
  region's `evaluated`, which §2 makes state-only — so the quantile edges
  move and every candidate's `envelope_id`, hence its weight, changes.
- Preserve: the boolean `mask` in the extraction loop (`:200-205`) mixes
  positional and label indexing and is correct only while `mask` stays
  boolean; and the "candidate file absent → return" path (`:141-143`).
- `:153`'s bare `except Exception` re-raises `MissingDataError` (it is
  the only thing that block currently swallows; the residual `except`
  logs exception type and traceback per PA-0011). This is what turns a
  half-finished rebuild into "Skipping" over stale negatives.
- `:60` imports `BOXES`/`BLOCK_SIZE_M_DEFAULT`/`thin_by_min_distance`
  from `prepare_training_data`; re-point the constants at `regions`.

### 6. `train.py` — standing assertions
All run **pooled**, and **before `filter_by_year_gap`**, which drops
22–24 % of positives and **0 %** of negatives and would otherwise
guarantee divergence on correct data. `build_datasets` (`:253-315`) is
today a single per-region loop calling that filter at the top of each
iteration, so this requires splitting it into a **load pass** and a
**construct pass** (see "Preservation rules" below). The failing path
must raise **before any `GrousePatchDataset` is constructed**.

- **(a) Partition:** every positive and every negative in region R has
  `state == R`. Exact, no threshold, no geopandas.
- **(b) Disjointness:** no coordinate rounded to 5 dp appears in both
  pooled splits, evaluated per class. *(Restored — CR-0006 v3 deleted
  this while rewriting §6, leaving BUG-0027 with no standing
  enforcement at all.)*
- **(c) Block disjointness:** no block holds both a train and a val
  record, either class — **computed by recomputing block ids from
  `longitude`/`latitude` against `BLOCK_ORIGIN_5070` and
  `BLOCK_SIZE_M`, never from the recorded `block_id` column.** The
  column form is a tautology: `split` is derived as a pure function of
  the recorded id, so grouping by it returns 0 for any pipeline,
  correct or not.
- **(d) Spatial support:** per region, the fraction of 30 km blocks
  occupied by positives that hold **no** negative, on a grid anchored on
  `BLOCK_ORIGIN_5070`, computed from lon/lat over the pooled
  pre-`filter_by_year_gap` frame. **Threshold ≤ 0.15.**

  v1 used a per-region comparison of the two classes' `state`
  histograms at ≤0.5 pp. That is **identically zero given (a)** — a
  re-test of (a), not a support check — and a reviewer passed it while
  drawing every negative from the southern half of each state.

  Calibrated across 5 seeds against a fair draw and that skewed draw,
  rather than from one realisation:

  ```
               ME       NH       VT
  fair  max  0.0252   0.0513   0.0250
  skew  min  0.6975   0.5897   0.4000
  pre-CR     0.0484   0.3220   0.2500
  ```

  **This gate fails NH and VT on today's data and does NOT fail ME**
  (0.0484 sits below the fair-draw ceiling of 0.0513, so no threshold
  can both pass a legitimate draw and fail it). That is acceptable only
  because **(a) catches ME's actual defect exactly** — 137 out-of-state
  positives against 0 out-of-state negatives. (a) sees out-of-state
  imbalance and is blind to within-state skew; (d) is the reverse.
  Neither alone is sufficient and the CR does not claim otherwise.
  **Re-measure both endpoints on the rebuilt negatives before freezing
  0.15.**

Three callers execute these: `train.py:980`, `calibrate.py:351`,
`bench_pipeline.py:95`. **All four hard-fail on any pre-CR dataset** —
(a) on 137 + 1,128 + 717 out-of-state positives, (b) on 522, (c) on 882,
(d) on NH 0.322 / VT 0.250 — so the three entry points become unrunnable
against the current data, which this CR's own test plan requires and
CR-0009 needs for a baseline. A **single explicit pre-CR mode covering
all four**, with a loud banner, and its use recorded in any artifact the
run produces, so an escaped run cannot be mistaken for a clean one.
(Cost is not the constraint: the polygon path measures 1.2 s.)

### 7. `train.py` — `sample_background_points`
`:120-165` draws assumed-negatives from raster row/col pairs across the
region's **box**, in any state — BUG-0029's mechanism in the file this
CR edits. Dormant at the `--an-background 0.0` default (`:739`).
Brought under the partition; the `attempts < 40` /
`m = max(64, 2*(n-len(lons)))` oversample budget (`:145-149`) must be
raised to absorb a ~47 % rejection rate, or the `SystemExit` at `:161`
becomes reachable. `:141`'s `bad = set(NODATA_SENTINELS) | {nodata, 0}`
conflates 0 with nodata — a live PA-0006/BUG-0017 instance in this
function. **Deferred, not fixed here**, and allocated **BUG-0032**: it is
dormant at the `--an-background 0.0` default, and fixing a nodata
conflation inside a CR about record membership would mix two mechanisms.
An either/or is not a deliverable, so the decision is recorded.

### Preservation rules for the `build_datasets` split
Not optional detail — the failure mode is silent.

- **R1 (structural, not asserted).** Derive the label array *from* the
  parts list after the loop — `train_labels =
  np.concatenate([p.labels for p in train_parts])` — and the failure mode
  ceases to exist. `labels` is a cheap property (`dataset.py:446-453`,
  no raster I/O). Keep `assert len(train_labels) == len(train_ds)` as a
  belt, and forbid reordering `train_parts` after the labels are derived.
  Why it matters: `StratifiedBatchSampler` (`dataset.py:504-510`) uses
  the label array to compute index sets and **never compares
  `len(labels)` with `len(train_ds)`**; labels are `np.repeat(base, 4)`
  under `expand_rotations` (`dataset.py:453`), so a load pass that
  builds labels from dataframes yields a 1× array and **three quarters
  of the training set is silently never sampled**. A hand-maintained
  invariant plus a boundary spot-check is not enough — the spot-check is
  evadable (for parts `[A(1,len 4), B(0,len 4)]` the array
  `[1,0,1,1,0,1,0,0]` matches at both boundaries and is wrong inside).
- **R2.** The construct pass stays per-region, and soft labels are
  computed from the already-filtered frame. `_score_teacher_probs`
  (`train.py:200`) reads patches from *that region's* rasters, so a
  pooled frame cannot be scored. Length is validated
  (`dataset.py:90-96`); **order is not**, so a same-length permutation
  silently misattaches distillation targets.
- **R3.** Background sampling keeps `enumerate(regions)` position and
  the **filtered** count — `n_bg` uses the filtered frame and
  `seed = seed + region_i` (`:291-297`).
- **R4.** The return contract stays `(ConcatDataset, ConcatDataset,
  np.ndarray)`; new parameters keyword-with-default.
- **R5.** The load/assertion pass must **not mutate the frames it
  reads**. `RegionData._load_csv` (`grouse_data.py:237-241`) returns the
  **cached DataFrame object itself**, not a copy — `training_frame`
  defensively `.copy()`s at `:449` for exactly this reason. The
  assertions need derived columns, including a **recomputed `block_id`**
  for (c), and the positives CSVs already carry `block_id` and `split`.
  Assigning onto a frame from `rd.positives(...)` silently overwrites the
  recorded column in memory for every later reader in the process — the
  assertion built to detect id drift would create it. Work on
  `pd.concat([...], ignore_index=True)` copies.
- **R6.** `filter_by_year_gap` stays **per region**: it resolves
  `rd.raster_years(f)` (`train.py:179`) and `raster_path`'s
  empty-vintage fallback is per region. The year sets happen to be
  identical across all three regions for all 15 features today, so
  pooling it is harmless now and would break silently on the first
  single-region re-fetch.
- **R7.** Preserve the train/val asymmetry. Train datasets get `**aug`
  (`cache_dir`, `jitter`, `augment`) plus `soft_labels`; validation gets
  `cache_dir=` only (`train.py:278-315`, "Validation is never augmented"
  at `:307-309`). Collapsing both into one shared constructor is how a
  randomised validation set ships, and nothing downstream would raise.

## Known exceptions that must be dispositioned before the gate can pass
`verify_partition()` is mandatory and fail-hard, and **two negative
records are documented to fail it**: `(-70.92538, 43.3258)` filed NH
with an ME polygon, and `(-67.10082, 44.501766)` filed ME and inside no
polygon at all. The candidate pool holds 6 such records of 35,792.
Positives: **0 of 43,024**.

This CR must choose one and record it: drop them, relabel to the
polygon, or carry an explicit audited exception list. Until then the
gate is self-contradictory — it cannot be satisfied and cannot be
skipped. This is stated as an open decision, not an oversight.

## Impact
- **Every existing checkpoint and every recorded metric stops being
  comparable.** Calibration must be refit (CR-0009).
- **Dataset size and shape change**, measured on the current
  `evaluated_sightings_*.csv`: 8,422 pooled habitat rows → 6,702 unique
  coordinates → **≈6,230** after one pooled 30 m thin. Of those unique
  coordinates, **1,720** appear in more than one region's file and
  **291** appear *only* in a foreign region's file. Rows whose filing
  region differs from their `state`: **2,011**.
  *(CR-0006 stated "1,012 unique habitat positives change region"; that
  figure reproduces under none of these definitions and is withdrawn.)*
- **Per region, positives fall sharply** — this is the number CR-0006
  omitted, and it matters most for the region under complaint:
  ME 3,723 → in-state set, NH **2,244 → 1,116 (−50 %)**, VT 2,261 →
  1,544 by the `state` key on today's thinned files. With 1:1 negatives
  the NH dataset roughly halves.
- **Reassigned records change feature values, not just membership.**
  Each moves to a different local Albers grid; across coordinates
  present in more than one region's file the same ground point already
  disagrees on `evt` for 29.5 %, `evh` 36.3 %, `evc` 41.0 %,
  `nonveg_landcover` 12.2 %. So `envelope_metrics_*`, `bin_tuning_*`,
  `spatial_zone`/`env_zone`, the KDE surfaces and the negative weighting
  all change, and the habitat filter's own output changes — which is why
  no exact post-rebuild count is promised.
- **Consumers**, all verified at `path:line`: `get_negatives.py:128`,
  `organize_project.py:70,73,104,107`, `tune.py:215`,
  `smoke_test_training.py`, `diagnose_training.py`,
  `diagnose_water_bias.py`, `diagnose_wetland.py`,
  `diagnose_road_bias.py:68`, `calibrate.py:351`, `bench_pipeline.py:95`,
  `generate_negatives.py:60`, `legacy/gen_negs.py:67`, and — restored
  after v1 dropped them in the split — `predict.py:91`,
  `download_treemap.py:110`, `download_tcc_nlcd.py:73`, which also
  import `BOXES` from the restructured module. `clean.py:46`,
  `analyze_grouse.py:21`, `prepare_training_data.py:48` import `regions`
  directly. The import-smoke gate covers **sixteen** files, not twelve.
- **Docs**: `ARCHITECTURE.md:59`, `grouse_data.py:20`,
  `PROJECT_TREE.md`, and the module docstrings of
  `prepare_training_data.py:22-28` and `generate_negatives.py:24,36`.
- `RegionData.block_assignments` moves to `GrouseData`.
- **Not affected:** raster contents (CR-0008), model architecture,
  `predict.py`'s reader. Train/predict reader parity was verified
  bit-identical during the investigation.

## Risk level: **MEDIUM-HIGH**
Lower than CR-0006's because no raster is written and no retrain is
performed; the work is reversible by restoring two directories.

| risk | mitigation |
|---|---|
| Validation numbers get worse. **That is the correct outcome** — removing a 31 % leak removes inflation. | Stated in advance. A lower metric is never a rollback trigger. Baselines recorded in CR-0009. |
| The `build_datasets` split silently mis-samples 75 % of training data. | Preservation rules R1–R4, with R1's assertion required in code. |
| Origin/block-size drift between the two scripts recreates BUG-0027. | Both centralised in `regions.py`; assertion (c) computed geometrically, which detects drift (measured: a drifted-origin pipeline scores 723 violating blocks where a correct one scores 0). |
| `verify_partition()` cannot pass. | Must be dispositioned before implementation — see Known exceptions. |
| Stale per-region block tables remain resolvable. | Deleted, and the `PATH_TEMPLATES` entry removed. |
| NH dataset halves, reducing power in the region under complaint. | Stated in Impact; CR-0009 measures the consequence rather than assuming it. |

## Test plan

**Validatable in this environment** (real data present, no retrain
needed). Every acceptance item is stated as a **computation**, not a
number — the recurring defect in CR-0006 was invariants whose inputs
were unspecified.

| # | computed how | today | required |
|---|---|---|---|
| I1 | `cKDTree(pooled positives).query_pairs(regions.MIN_SPACING_M)` on EPSG:5070 coords reprojected from lon/lat | **1690** | 0 |
| I2 | block ids **recomputed** from lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`; count blocks holding both a train and a val record, either class | **882** | 0 |
| I3 | same recomputation; share of val negatives whose block holds any train record | **37.2 %** | 0 % |
| I4 | 5 dp coordinate key, per class, set intersection of pooled train and pooled val | **522 pos / 0 neg** | 0 / 0 |
| I5 | full `img_size + 2·jitter` window (jitter **0** by default, `train.py:462`, so 64 px — name the value the rebuild uses) inside every feature raster the record will be read from, **both classes** | **NH 4** of the pre-partition 2,244; post-partition NH 1,116 → **0**; ME 0, VT 0. Negative candidates: NH **721** of 69,219, ME 2, VT 0 | 0 |
| I6 | pooled positive count: habitat rows whose filing region equals their `state`, deduped on (lon, lat, year), then one pooled `MIN_SPACING_M` thin | 8,365 rows | **6,230 ± 2 %**; near 6,508 = habitat flag taken from a foreign grid |
| I7 | validation fraction, **per class and per region** | — | 20 % ± 1 pp pooled per class; per-region spread recorded, and justified if > ±3 pp |
| I8 | val neg : val pos ratio, pooled and per region | 1.000 | 1.000 ± 0.02 |
| I9 | `verify_partition()` **ran** over positives (`analyze_grouse`) **and** negatives (`generate_negatives`), predicate `within`, source `tl_2023_us_county.zip` dissolved by `STATEFP`; output recorded | positives 0 of 43,024; selected negatives 1 outside + 1 mismatched of 8,365; candidate pool 5 + 1 of 35,792 | 0 after the § Known-exceptions rule |
| I10 | per-region 30 km occupied-block pos-only fraction (assertion (d)) | ME 0.0484, NH 0.3220, VT 0.2500 | ≤ **0.15** per region — see §6(d) for why ME does not fail |
| I11 | recorded `block_id` == block id recomputed from lon/lat against `BLOCK_ORIGIN_5070`/`BLOCK_SIZE_M`, every record, both classes | not checked | 0 mismatches |
| I12 | parameter manifest on `block_assignments.csv` — spacing, block size, origin, seed, val fraction actually used — each equal to its `regions.py` constant | not recorded | recorded and equal |
| I13 | availability sample size == `n_samples` per region per feature after the §2 clip; judgeable-envelope count per region | NH 50, VT 48 (at `MIN_AVAIL_BG = 15`) | unchanged or justified |

I6–I8 exist because I1–I5 are all "violation count == 0" predicates and
therefore monotone under deletion: a reviewer passed every one of them
on a pipeline that had silently dropped **half the dataset**.

I12 exists because `--min-spacing-m` and `--block-size-m` survive as CLI
flags on `prepare_training_data.py` while `generate_negatives.py` takes
the constant — so the two classes can be thinned at different distances
from one command line. Measured: positives thinned at 60 m give 6,144,
**inside I6's ±2 % band**, while I1's predicate is one-sided (harder
thinning satisfies "0 pairs under 30 m" more easily). The undetectable
window is ≈30–65 m. Removing the two flags is the cheaper equivalent.

### I14 — the governing invariant (v3)
> **Re-running `assign_spatial_blocks` from the recorded manifest
> (spacing, block size, origin, seed, val fraction) must reproduce the
> shipped split bit-for-bit**, and the val block set at seed S must
> **differ** from the val block set at seed S′.

Same inversion CR-0008 adopts: stop enumerating bad outcomes, constrain
what may vary. A reviewer deleted one call —
`block_counts.sample(frac=1, random_state=seed)` →
`block_counts.index.tolist()` (`prepare_training_data.py:103`) — in the
function this CR rewrites. Because `value_counts()` is sorted descending,
the validation blocks become **the densest blocks first**, i.e. the KDE
hotspots: val blocks 749 → **236**, records per val block 1.67 → **5.28**,
validation drawn from the top 5.9 % of blocks by occupancy. **Every one
of I1–I13 passed**, with the worst per-region deviation at 2.95 pp —
just inside I7's 3 pp trigger.

It is also **seed-invariant**: identical output for seeds 42, 7 and 1,
which a correct draw never is. Both halves of I14 are free and either one
alone kills it.

**I15 — val-block dispersion:** occupied-val-blocks / occupied-blocks
within 1 pp of the record-level val fraction. Correct draws measure
1.57–1.68 records per val block; the attack measures 5.28.

**I7 becomes a hard gate at ±2 pp per region**, not "recorded and
justified if > ±3 pp". A gate whose failure mode is "write a
justification" is an observation, and the attack above passes precisely
because the item that would have caught it was one. The same applies to
I10 and I13: the table is split into **GATES** (hard fail) and
**OBSERVATIONS** (recorded), and every row says which it is.

**I10's threshold is withdrawn pending re-calibration.** It was set from
a 5-seed maximum. Over 12 seeds a *fair* draw reaches NH **0.0769** and
VT **0.0500** against the ceilings of 0.0513 and 0.0250 I derived — so
the inference "no threshold can both pass a legitimate draw and fail it"
rests on a 5-sample maximum, which is not a bound. Worse, a reviewer
passed I10 by rescaling its own attack from "southern half of each
**state**" to "southern **sixth of each 30 km block**": (d) = 0.084 /
0.103 / 0.125, all under 0.15, while median positive→nearest-negative
distance **tripled** (2.1 → 6.7 km) against a **1.92 km** receptive
field. NH has only 39 positive-occupied 30 km blocks, so the statistic
moves in steps of 1/39 = 0.0256 — a six-state gate. **Replacement:** the
median and p90 of positive→nearest-negative distance, gated against a
fair-draw envelope derived from ≥50 seeds and stated as a quantile, at
or below the receptive-field scale. Re-measure before freezing.

**How every invariant above was calibrated** — and the rule this CR asks
to be made standing policy: *each was measured on at least one
constructed pipeline that is wrong in the way that invariant exists to
catch, not only on the current data and the intended pipeline.* All four
of CR-0006's acceptance failures, and v1's assertion (d), would have
been caught by that rule alone.

Also: assertions (a)–(d) demonstrated **failing** on the current CSVs
and **passing** on rebuilt ones; the three deprecation guards actually
fire; `smoke_test_training.py` runs; import-smoke of all twelve
consumers; `inv_leakage.py` re-run with sections 1–2 reading 0.

**Cannot be validated in this environment, and why:**
- **Whether the model is better.** Requires the retrain (CR-0009), and
  the number will fall by construction.
- **Exact post-rebuild counts.** `analyze_grouse.py` re-samples
  reassigned records from a different grid, so the habitat filter's own
  output changes; 6,230 is an expectation with a band, not a prediction.
- **A fresh-environment run.** geopandas and
  `data/roads/tl_2023_us_county.zip` are present here; behaviour when
  absent is specified but untested.
- **`--an-background` behaviour at non-zero values.** Default is 0.0 and
  no recorded run used it.

## Deliverables
- [ ] **Disposition the two `verify_partition()` exceptions** (Known
      exceptions). Blocks implementation.
- [ ] ~~Decide the NH box question~~ — **resolved in §5**: windowless
      candidates are dropped before sampling, which makes I5 unfailable
      without re-downloading any NH raster. `BOXES` is unchanged.
- [ ] `regions.py`: `state` membership; `verify_partition()`;
      centralise `STATE_FIPS`, `MIN_SPACING_M`, `BLOCK_SIZE_M`,
      `BLOCK_ORIGIN_5070`; `BOXES` documented raster-only.
- [ ] `analyze_grouse.py`: partition, `region` column, rejection-sampled
      availability clip, `:439` threshold re-expressed.
- [ ] `prepare_training_data.py`: global origin, pooled pipeline,
      `--regions` write-guard, dead flag and dead `rng` removed.
- [ ] Runtime guards on `clean.py`, `legacy/gen_negs.py`,
      `legacy/audit.py`, `legacy/download.py`, `legacy/download_more.py`.
- [ ] `generate_negatives.py`: pooled/per-region split, global ids,
      pooled buffer and thinning, `:153` narrowed, constants re-pointed.
- [ ] Move the `block_assignments` accessor to `GrouseData`; remove the
      per-region `PATH_TEMPLATES` entry. **Deleting the per-region
      `block_assignments_*.csv` files happens only after the backup
      below is checksummed** — v2 ordered the deletion before it.
- [ ] `train.py`: `build_datasets` split under R1–R4; assertions
      (a)–(d); escape flag for (d); `sample_background_points`
      partitioned and its oversample budget raised.
- [ ] All twelve consumers and five docs updated.
- [ ] **FIRST:** back up `data/pipeline/`, `data/negatives/` (51 MB),
      **and `old_road_dist/`, `new_road_dist/` and
      `INVESTIGATION_REPORT_errol_map.md`** — all untracked, all inputs
      to CR-0009's acceptance, protected by no CR until now.
- [ ] Run `analyze_grouse.py` → `prepare_training_data.py` →
      `generate_negatives.py`, in that order, recording each one's
      output. *(CR-0006 never ordered these; without the first, the
      partition never materialises.)*
- [ ] Record the full I1–I13 table, before and after.
- [ ] Remove `prepare_training_data.BLOCK_SIZE_M_DEFAULT` (`:52`) once
      `regions.BLOCK_SIZE_M` exists — two names for one constant is the
      mechanism this CR centralises against.
- [ ] Re-run `inv_leakage.py` **including section 3 (pooled
      proximity)**, recorded as numbers; sections 1–2 must read 0.
- [ ] Allocate **BUG-0032** for the deferred
      `sample_background_points` nodata/0 conflation (§7).
- [ ] Promote `DRAFT_BUG-0029` into `docs/quality/bugs/` with a
      `BUG_LOG.md` row; update BUG-0027 and BUG-0029 to confirmed+fixed.
- [ ] BUG-0031: PA-0014's sweep **omission** of the
      `legacy/audit.py`/`analyze_grouse.py` pair, and its recording of
      "content-identical → harmless" as a permanent conclusion for
      copies this CR makes diverge. Include §4.2's prior-PA failure
      analysis for **PA-0002**, whose sweep left five runnable copies.
- [ ] `PREVENTIVE_ACTIONS.md`: PA-0020 scoped to **any per-class
      dataset-defining filter**, not only geographic ones — an uncovered
      sibling exists (`generate_negatives.py:159` drops negatives on
      `coord_uncertainty_m`; positives are never filtered on it).
      Correct PA-0002's and PA-0014's Swept? rows; update PA-0018's to
      record that its enforcement gap is closed by (b)/(c).
- [ ] **Create BUG-0033** — the acceptance-criteria defect class. Five
      documented failures across CR-0006 (3), CR-0007 (2) and CR-0008
      (4 breaks): a count criterion taken from a simulation of the wrong
      pipeline; invariants that were positives-only; invariants read from
      the pipeline's own bookkeeping instead of geometry; thresholds set
      from a single realisation or a 5-sample maximum; and enumerated
      outcomes where a change-set constraint was needed. `CLAUDE.md` §2:
      "a defect found in review counts, even if never observed running."
      No BUG doc exists for it and no CR files one — each assumed
      another would.
- [ ] **Add PA-0021** to `PREVENTIVE_ACTIONS.md`, the rule all three CRs
      quote and none files:
      *(a) every acceptance invariant must be measured on at least one
      constructed pipeline that is wrong in the way that invariant exists
      to catch, not only on the current data and the intended pipeline;
      (b) prefer constraining what MAY change (a whitelist on the change
      set) over enumerating what must not (a blacklist on outcomes);
      (c) any threshold in a hard gate must be calibrated against the
      statistic's sampling distribution, stated as a quantile over ≥50
      draws, never a min/max over a handful; (d) a gate whose failure
      mode is "record a justification" is an observation — label it one.*
      Extends PA-0018's enforcement clause; cross-references PA-0016
      (which governs diagnosing a wrong output, not accepting a fix).
- [ ] Independent review with every concern dispositioned.

## Out of scope
- **Raster coverage** (BUG-0023 ME/VT, BUG-0024, BUG-0025, BUG-0030) →
  **CR-0008**.
- **The retrain, calibration refit, and the end-to-end map check** →
  **CR-0009**.
- **BUG-0026** (`diagnose_road_bias.py:82`, per-state roads in a
  diagnostic). This CR re-points that file and centralises the constant
  whose only live value-use is that defect, but does not fix it.
  Explicitly deferred, with a bug id.
- **BUG-0028** (prediction outputs carry no provenance).
- The 24–41 % inter-region categorical disagreement at identical
  coordinates. Measured, not diagnosed; needs its own investigation.
- `scripts_backup/` — untracked, holds further runnable copies.
- Model architecture, loss, hyperparameters. Adding CI.

## § Review

### Round 1 (v1) — two independent reviews
| reviewer | verdict | blocking |
|---|---|---|
| implementation lane | APPROVE WITH CHANGES | 1 (pooled `concat` index discipline) |
| acceptance lane | REJECT | 1 (assertion (d) a tautology) |

### Round 2 (v2) — two independent reviews
| reviewer | verdict | blocking |
|---|---|---|
| implementation lane | APPROVE WITH CHANGES | 1 (`weighted_take` `.loc` overshoot) |
| fresh, standalone | **REJECT** | 3 (acceptance set broken twice; §1.3/§1.4 unsatisfied; deliverables not executable in order) |

**Dispositions.** Every concern from both rounds is dispositioned below;
none dropped. v2 recorded a seven-line summary and left `§ Review`
reading "Not yet reviewed" — a §1.3/§1.4 violation in its own right,
and the reason this table exists.

| concern | disposition |
|---|---|
| (d) is a tautology given (a) | **Accepted** — replaced by the occupied-block support check; now withdrawn again pending re-calibration (see I10). |
| pooled `concat` index discipline | **Accepted** — `ignore_index=True` mandated in §5, with the 3-pick→6-row demonstration. |
| `verify_partition()` has no negative call site | **Accepted** — added in §5. |
| NH box deferred but not optional | **Accepted** — resolved by dropping windowless candidates before sampling. |
| R1 evadable; R5–R7 missing | **Accepted** — R1 made structural; R5 (cached-frame mutation), R6, R7 added. |
| escape flag scoped to (d) only | **Accepted** — single pre-CR mode covering all four, recorded in any artifact produced. Note a reviewer argues (a)–(c) should stay unconditional; **see open item below.** |
| acceptance set broken (dropped shuffle) | **Accepted** — I14/I15 added. |
| acceptance set broken (rescaled (d) attack) | **Accepted** — I10's threshold withdrawn; replacement specified at receptive-field scale. |
| §1.3/§1.4 unsatisfied | **Accepted** — this table. |
| deliverables not executable in order | **Accepted** — backup moved first. |
| Impact's 6,230 derivation yields 6,508 | **Accepted** — see Corrections. |
| PA-0020's `coord_uncertainty_m` example is inert | **Accepted** — see Corrections. |
| `TIGER_YEAR` owned by no CR | **Accepted** — added to §1's centralisation list. |
| A6/`verify_partition` disposition should block approval, not implementation | **Open** — see below. |

**Open items requiring the reviewer's decision, not the author's:**
1. Whether the pre-CR escape mode may cover (a)–(c) or only (d). One
   reviewer calls a blanket bypass a weakening of the standing
   enforcement this CR restored; another shows the test plan cannot run
   without it. Proposed compromise: blanket mode permitted, but it
   refuses to write any checkpoint, metric or calibration artifact.
2. Whether the two `verify_partition()` exceptions must be dispositioned
   before **approval** rather than before implementation. Note "relabel
   to the polygon" is unavailable for 5 of the 6 candidate-pool records —
   they are inside no polygon at all.

**Author sign-off:** withheld.

## Corrections to v2
- **Impact's chain "8,422 → 6,702 → ≈6,230"** yields **6,508**, which
  this CR elsewhere calls a wrong-grid diagnostic. The correct recipe is
  I6's: keep the row from the record's **own state** file → habitat
  filter = 6,411 → pooled thin = **6,230**. Confirmed by three reviewers
  and by the author reproducing the same error in a verification script.
- **NH's post-partition count is 1,079 (−52 %), not 1,116.** 1,116 is the
  state composition of NH's own file and discards the 137 + 717 NH-state
  records held in the ME and VT files. Per-region: ME **3,659**,
  NH **1,079**, VT **1,492**.
- **PA-0020's cited example is inert.** `coord_uncertainty_m` is null in
  all 265,212 candidate rows and `coordinateUncertaintyInMeters` in all
  43,024 sighting rows, so `generate_negatives.py:159` drops nothing.
  The broadening may still be right in direction, but this evidence for
  it does not exist and is withdrawn.
- `35,792` → **35,678** (the code dedups at 5 dp); I12's undetectable
  window is ≈30–**79** m, not 30–65; `build_datasets` is `:238-317`;
  §7's `bad = ...` is at `:143`; `analyze_grouse`'s `MIN_VALID_FRAC`
  check is at `:444`; the risk table's "723 violating blocks" is
  unreproducible and is withdrawn.
- **The "today" column is measured across mixed pipeline generations** —
  `thinned_positives_*` hold 81 / 70 / 76 coordinates absent from the
  current `evaluated_sightings_*` habitat subset. It must be re-measured
  after one clean `analyze_grouse.py` run.
