# CR-0015: Draw assumed-negative background points only in-state, only in training blocks, and without treating 0 as nodata

**Status: APPROVED (v2.2), 2026-09-30. Deliverable 1 (interim guard) IMPLEMENTED;** the rest waits for CR-0012 (CR-0007 is implemented).
History, lineage, verdicts and dispositions: `CR-0015-review-log.md`. This
document states only current intent.

## Scope
Change `train.sample_background_points` so the assumed-negative points
used for training lie in the region's own state, in training blocks only,
and are rejected only for true nodata; make `pretrain.py`'s use of the
same function explicit; and close the reader side of PA-0006 with a
mechanical check.

## Order
- Deliverables 1–4 (guard, bug records, L1, PA-0006 re-sweep) can land at
  once.
- Deliverables 5–9 land **after CR-0007** (`regions.in_state`) and
  **after CR-0012** (global block grid, `regions.block_ids`,
  `SPLIT_SEED`, `block_assignments.csv`). CR-0012's approved text
  (`29f388b`) is not reopened; `regions.to_5070` and
  `regions.block_split` (§1) are added by this CR after CR-0012 lands.
- CR-0009's pinned retrain does not pass `--an-background` and is not
  affected.

## One change per CR (CLAUDE.md §1, CR-0011 A5)
The deliverables span pipeline code, a shared helper, acceptance design
and bookkeeping. They are kept together because none lands usefully alone:
- The **interim guard** (deliverable 1) exists only to close the gap until
  §2 lands, and is removed by deliverable 8.
- **`regions.to_5070` and `regions.block_split`** (deliverable 5) are
  required by §2's training-block rule (PA-0001: one copy of the
  transform and of the md5 rule). Their switch-over in
  `generate_negatives.py` is behaviour-preserving and is verified by
  digest, not reviewed as a behaviour change.
- **L1** (deliverable 3) and the **PA-0006 re-sweep** (deliverable 4) are
  the §3.4/§3.5 obligations of BUG-0032's preventive action.

Any defect the re-sweep finds that needs more than a trivial fix gets its
own CR, not this one.

## Why now
`sample_background_points` (`train.py:120-165`) draws uniform row/col
pairs over the region's first-feature raster. Three defects:

1. **Out of state (BUG-0029, assumed-negative part).** The raster covers
   the region's box, which includes neighbouring states and Canada.
   Share of today's accepted points outside the state: ME 36.0 %,
   NH 52.5 %, VT 47.3 % (reviewer A, round 1, 200,000 draws per region).
2. **Into validation blocks (BUG-0042).** The points are labelled 0 and
   added to **training** (`train.py:290-306`). Nothing keeps them out of
   validation blocks. Of in-state draws, 19.3 % (ME), 19.6 % (NH) and
   20.5 % (VT) fall in validation blocks (same measurement). No CR-0013
   gate can see this, because the points are drawn in memory and never
   written to a file.
3. **0 treated as nodata (BUG-0032).** `bad = set(NODATA_SENTINELS) |
   {nodata, 0}` (in `sample_background_points`) rejects a pixel whose first feature reads `0`.
   With discovered features the first is `evt`, where 0 does not occur
   (0.0000 % in all three regions). But `features` is taken as passed
   when `--features` is given (`:897`), so the `# spec order:
   categorical first` comment at `:135` is false then. A first feature
   where 0 is a reading (e.g. `tcc`, 0 % canopy) makes the defect live.

The path is live. `pretrain.py:179` calls the function for every SSL
tile. `--an-background 1.0` is used by the untracked sweep recipes
(`sweep/launch.sh`, `sweep/runner.sh`, `sweep/launch2.sh`,
`sweep/launch3.sh`) and by Run B/Run C in the untracked
`grouse_model_results_summary.md`.

## The change

### 1. Two helpers in `regions.py` (new)

#### `regions.to_5070(lon, lat)`
Returns `(x, y)` in EPSG:5070 from `Transformer.from_crs("EPSG:4326",
"EPSG:5070", always_xy=True)`, i.e. exactly today's
`generate_negatives.to_albers` (`:93-95`), the transform that produces
`x_5070`/`y_5070` in CR-0012's pool. After CR-0012 lands,
`generate_negatives.to_albers` delegates to it (kept as a thin wrapper so
its callers are unchanged). The CRS literals move with it; the wider
analysis-CRS constant stays CR-0007's deferred item (d).

#### `regions.block_split(block_ids, assignments)`
Returns a `"train"`/`"val"` array, one entry per block id:
- If the block id is in `assignments.block_id`, the block's `split` from
  the file.
- Otherwise, `"val"` iff
  `int(hashlib.md5(f"{SPLIT_SEED}:{block_id}".encode()).hexdigest(), 16) % 10_000 < vf * 10_000`,
  where `vf = (assignments.split == "val").mean()`. That is today's
  `generate_negatives.split_for_unassigned` (`:110-115`) with the seed
  fixed to `regions.SPLIT_SEED` and `vf` as CR-0012 §2 defines it.

`assignments` is the DataFrame read from `block_assignments.csv` through
`PATH_TEMPLATES` through whichever accessor CR-0012 §4 implements
(today `RegionData.block_assignments`, `grouse_data.py:444`; PA-0003).
The function does no file I/O.

`generate_negatives.py`'s pool step 10 calls `block_split`, and
`split_for_unassigned` is deleted (PA-0001). Both switch-overs (this and
`to_albers` → `to_5070`) are covered by the B1 byte-identical gate. `acceptance_split.py` keeps
its own re-typed rule, because CR-0013 requires the replay to be
independent (PA-0021(e)).

### 2. `train.sample_background_points`
New signature:
`sample_background_points(rd, features, n, seed=0, *, region, train_blocks_only, assignments=None, in_state=None)`

- **`region` and `train_blocks_only` are required keywords** with no
  default. A caller cannot get today's behaviour by omission.
- **`assignments`** is required when `train_blocks_only` is true
  (otherwise `ValueError`), and must be `None` when it is false.
- **`in_state`** defaults to `regions.in_state` (CR-0007). It is a
  callable `(lon, lat, region) -> bool array`, injectable so the synthetic
  tests (U1, U2) need no county file.
- **Validity.** Reject a draw only when the first feature's pixel is in
  `NODATA_SENTINELS`, equals the file's declared nodata, or is not
  finite. `0` is no longer rejected (BUG-0032).
- **In-state.** Keep a draw only if `in_state(lon, lat, region)`.
- **Training blocks** (when `train_blocks_only`):
  - Transform the draw's `lon`/`lat` to EPSG:5070 with
    `regions.to_5070` (§1). Never use the raster's native x/y: the
    rasters are in per-region Albers, not EPSG:5070.
  - Get the block id with `regions.block_ids(x, y)`.
  - Keep the draw only if `regions.block_split(ids, assignments) ==
    "train"`.

  The AN path imports only `regions` for this (no `generate_negatives`,
  scipy, sklearn or matplotlib).
- **Budget.** Unchanged: `m = max(64, 2 * shortfall)` draws per round, up
  to 40 rounds. With acceptance rate p ≥ 0.38, each round leaves at most
  `(1 − 2p) ≤ 0.24` of the shortfall. So n = 10,000 needs about 7 rounds
  while `2 · shortfall > 64`, and the 64-draw floor then finishes in a
  few more. The `SystemExit` on shortfall stays; its message adds the
  observed acceptance rate and the region.
- **Determinism.** Unchanged: `numpy.random.default_rng(seed)`, one draw
  sequence per call.
- **Docs.** Update the docstring. Replace the `:135` comment with
  "validity is judged on `features[0]` as passed". Update the
  `--an-background` help (`:739-750`) to say "in-state, training blocks
  only".

### 3. Call sites
- **`train.build_datasets`** (`:296`) passes `region=region,
  train_blocks_only=True, assignments=<CR-0012's block_assignments
  accessor>` (§1).
- **`pretrain.py:179`** passes `region=region, train_blocks_only=False`.
  - SSL tiles carry no labels, so tiles in validation blocks leak no
    label.
  - Keeping tiles in-state matches the records the model is trained and
    validated on.
  - This **changes the SSL tile set**: in-state only, and 0-valued pixels
    become eligible. An existing `grouse_ssl_backbone.pth` stays loadable
    but cannot be reproduced from the new code. This is recorded in
    `CHANGELOG.md`.
  - Update the `--tiles` help (`pretrain.py:120-122`) to say "in-state".
  - **New dependency.** `pretrain.py` now always needs geopandas,
    pyogrio and the county file (`PATH_TEMPLATES["tiger_county"]` at
    `COUNTY_POLYGONS_YEAR`, CR-0007). Today it needs none of them.
    Reconciliation with CR-0012 B-21 ("geopandas only when
    `--an-background > 0`"): B-21 is about `train.py`, and it still
    holds there — the default training path never calls the function,
    and every import stays inside it. `pretrain.py` has no path that
    avoids the sampler, so for it the dependency is unconditional and
    accepted. A missing package or file fails at start, before any GPU
    work. Both packages are installed here (geopandas 1.1.4,
    pyogrio 0.13.0).

### 4. Interim guard (removed by deliverable 8)
Placed in `train.main()` immediately after `args = parser.parse_args()`
(`:882`), before seeding, `GrouseData()` or any GPU work. It is **not**
placed in `sample_background_points`, so `pretrain.py` is not blocked:
```
if args.an_background > 0:
    raise SystemExit("--an-background > 0 is disabled until CR-0015 lands "
                     "(assumed negatives drawn out of state and in "
                     "validation blocks; BUG-0029, BUG-0042).")
```
**Recipes it breaks:**
- `sweep/launch.sh` and `sweep/runner.sh`: `--an-background 1.0` in
  `BASE`.
- Run B and Run C (`grouse_model_results_summary.md`).
- Any `sweep/launch2.sh` or `sweep/launch3.sh` run that does not override
  the flag.

**Recipes it does not break:** runs that override with a later
`--an-background 0` (argparse keeps the last value), e.g. `r16`–`r20` in
`launch2.sh`/`launch3.sh`, and CR-0009's retrain. All these scripts are
untracked, so this CR does not edit them.

## Acceptance
| id | type | check | required |
|---|---|---|---|
| U1 | GATE | Synthetic raster split into two "states" by a line, `in_state` injected: every returned point is in-state, and `in_state` was called with the given `region` | all |
| U2 | GATE | Synthetic raster in a non-5070 Albers CRS, with assignments whose native-x/y block ids differ from the 5070 ids. The fixture has five block kinds: **(i)** in the file as `val`, md5 would say `train`; **(ii)** in the file as `train`, md5 would say `val`; **(iii)** unassigned, md5 `val`; **(iv)** unassigned, md5 `train`; **(v)** unassigned, hashed in `[vf, VAL_FRACTION)` (md5 `train` under `vf`, `val` under `VAL_FRACTION`), with the fixture's `vf` chosen so such a block exists. With `train_blocks_only`: 0 points in (i) or (iii); ≥ 1 point in each of (ii), (iv) and (v). Fixture sizes are chosen so that (ii), (iv) and (v) each expect ≥ 50 points | 0 / ≥1 / ≥1 / ≥1 |
| U3 | GATE | A pixel reading `0` is eligible; each sentinel, the declared nodata and NaN are not | pass |
| U4 | GATE | Exactly `n` points, and identical points for the same seed | pass |
| U5 | GATE | Shortfall raises `SystemExit` naming the acceptance rate | pass |
| U6 | GATE | Calling without `region` or `train_blocks_only` raises `TypeError`; `train_blocks_only=True` without `assignments` raises `ValueError` | pass |
| U7 | GATE | Guard (deliverable 1): `train.main` with `--an-background 1` exits naming CR-0015 before `GrouseData` is constructed; with `--an-background 1 --an-background 0` it passes the guard. Deleted with the guard | pass |
| B1 | GATE | `to_5070`/`block_split` refactor (deliverable 5): after `generate_negatives.py` is switched (`to_albers` delegates to `to_5070`; pool step 10 calls `block_split`), a re-run gives `candidate_pool.csv` and every `negatives_*` file byte-identical to the digests in the manifest of the latest CR-0012 deliverable 6 run, and `acceptance_split.py` passes unchanged | identical / pass |
| L1 | GATE | Lint rule below, over the file set below: 0 matches outside the allowlist | 0 |
| V1 | GATE | Real data, n = 5,000 per region, AN path, seed 0. An **independent** re-check finds 0 out-of-state points and 0 validation-block points. The re-check uses its own polygon test on the county file (not `regions.in_state`), its own 4326→5070 transformer and floor formula (not `regions.block_ids`), and a re-typed md5 rule (not `block_split`) | 0 / 0 |
| V2 | OBS | Acceptance rate per region, split into in-state × validity × train-block | report |
| V3 | GATE (calibrated) | Real data. **Statistic:** per region, \|share of accepted points in unassigned-train blocks − reference area share\|. **Class:** unassigned-train blocks. **Subset:** valid, in-state, train-block area. **Null population:** the fair sampler over 100 seeds. **Reference:** an independent pixel-centre enumeration of the first-feature raster, at a fixed stride giving ≥ 100,000 in-state centres per region, classified with V1's re-check. **Threshold:** set by the calibration in deliverable 7a | ≤ calibrated bound |

**V1 cannot pass by skipping.** The tests use `unittest` (pytest is not
installed). Before CR-0012 lands, V1 and V3 call `self.skipTest` with a
message when `block_assignments.csv` is absent. At deliverable 7 they run
with `GROUSE_REQUIRE_REAL_DATA=1`; with that variable set, a missing input
is `self.fail`, not a skip. The evidence file records the
`python -m unittest -v` output, whose summary line must show no
`skipped=`.

**PA-0021 conformance.**
- **(a)** V1 and V3 are also run on constructed wrong samplers, built by
  the round-2 reviewer, not the author:
  - today's sampler (V1 must fail both counts);
  - an over-excluding sampler that treats every unassigned block as
    excluded (V3 must fail: its share is 0);
  - an under-excluding sampler that treats every unassigned block as
    train (V1 must fail on the (iii)-kind points);
  - an under-excluding sampler using a fraction **below** `vf` (0.18) in
    the md5 rule: V1 must fail, on points in unassigned blocks hashed in
    `[0.18, vf)` (about 85 of 5,000 per reviewer A's estimate).

  A sampler using `VAL_FRACTION` (0.2) instead of `vf` **over**-excludes
  (blocks hashed in `[vf, 0.2)`, about 0.3 % of the area), so neither V1
  nor V3 can see it. **U2 kind (v)** catches it: that sampler puts 0
  points there. Which check catches which wrong sampler:

  | wrong sampler | caught by |
  |---|---|
  | today's (no in-state, no block rule) | V1 (both counts), U1, U2 |
  | unassigned treated as excluded | V3, U2 (iv) |
  | unassigned treated as train | V1, U2 (iii) |
  | md5 fraction 0.18 (< `vf`) | V1 |
  | `VAL_FRACTION` instead of `vf` | U2 (v) |
  | native x/y instead of 5070 | U2 |
- **(b)** U4's exact `n` is the cardinality gate, so both a no-op and a
  deletion fail.
- **(c)** V3 is the only non-exact row. The reviewer A1 suggestion of
  ±3 pp is not pinned. Deliverable 7a computes the fair distribution
  (100 seeds × 3 regions) and the broken samplers' values. The bound
  is the fair p99. If it does not separate every broken sampler, V3 is
  demoted to OBS and the demotion is recorded.

### L1 rule (committed as `tests/test_nodata_zero_lint.py`)
**File set:** `git ls-files '*.py'`, minus top-level `inv_*` and `res_*`
and `docs/**` (the evidence scripts). The set grows with the code, so the
test pins no count; it checks that the mechanism's home files are in scope
and no excluded file is.

**Rule.** Parse each file with `ast`. A node is *nodata-bearing* if its
subtree contains a `Name` or `Attribute` whose identifier matches
`(?i)nodata|sentinel`. A *zero* is an `int`/`float` `Constant` equal to 0
(not `bool`). Report a node when any of the following holds:
- **(a)** A `Set`/`List`/`Tuple` display contains a zero and a
  nodata-bearing element; or a `BinOp` with `|` or `+` has one operand
  that is such a display containing a zero and the other operand
  nodata-bearing. Example: `set(NODATA_SENTINELS) | {nodata, 0}`,
  `list(NODATA_SENTINELS) + [0]`.
- **(b)** A flattened chain of `&` (or of `|`) `BinOp`s has an operand
  (after stripping `~`/`not`) that is a single-op `Compare` with zero,
  where the op excludes 0 under `&` (`!=`, `>`, `<`) or includes 0 under
  `|` (`==`, `<=`, `>=`). The rule matches whatever the other operands
  are, so `m & (x != 0)` matches.
- **(b′)** The same test as (b) for a `BoolOp` `and`/`or`, but only when
  another operand is nodata-bearing. Scalar `and`/`or` over counts
  (e.g. `n == 0 and …`) would otherwise flood the rule.
- **(c)** A `Compare` between a nodata-bearing operand and a zero
  (`src.nodata != 0`, PA-0006's original trigger).
- **(d)** A `BoolOp` `or` with a nodata-bearing operand and a zero
  operand (`nodata or 0`).

**One match per statement.** A matched node nested inside another matched
node is not reported (the `|` and its `{nodata, 0}` are one match).

**Allowlist.** In the test file, keyed by `(path, ast.unparse(node))` of
the outermost matched node, never by line. Each entry cites the deliverable-4 sweep result that
justifies it. Entries are reviewed as part of this CR.

**Positive controls.** The test also asserts that the rule matches each
of these snippets, including reviewer A's patterns:
- `m & (x != 0)`
- `(arr > 0) & ~sentinel`
- `nodata or 0`
- `set(NODATA_SENTINELS) | {nodata, 0}`
- `src.nodata != 0`
- `~np.isin(v, NODATA_SENTINELS) & (v != 0.0)`
- `(v == 0) | (v == nodata)`
- `list(NODATA_SENTINELS) + [0]`

It asserts that the rule does not match `(a < 0) | ~np.isfinite(a)`,
`n == 0 and declared == nodata` or `vals[vals == src.nodata] = np.nan`.

**Until deliverable 4.** The allowlist is empty and the test pins the
match set to exactly the 4 statements below (`EXPECTED_UNCLASSIFIED`),
so any new match fails it. Deliverable 4 moves each to the allowlist
(with its justification) or removes it with a fix; after deliverable 6
the pinned set is empty.

**Expected result on today's tree** (`python -m unittest
tests.test_nodata_zero_lint -v`, 2026-09-30, commit `05d4ce5`: 6 tests OK, 63 files):
4 statements, cited by text (line numbers move).
1. `train.py`: `set(NODATA_SENTINELS) | {nodata, 0}` — BUG-0032, fixed
   by §2; no allowlist entry.
2. `find_tsd_contrast_points.py`:
   `~np.isin(nlcd_arr, NODATA_SENTINELS) & (nlcd_arr != 0)` — known
   sibling; classified by deliverable 4.
3. `generate_time_since_disturbance.py`: `(arr > 0) & ~sentinel` —
   classified by deliverable 4. Author's reading: 0 is the VAT
   "Background" class. It stays in `cov` (the preceding
   `cov &= ~sentinel`), and `hit` is a disturbance predicate, not a
   validity mask.
4. `check_road_dist.py`: `(state != 0) & ~home` — classified by
   deliverable 4. Author's reading: 0 is "no state" in a rasterised state
   id.

After deliverable 6, the expected result is 0 matches outside the
allowlist.

**Limit.** L1 sees only literal-0 comparisons and displays. Two kinds of
conflation are out of its reach: a 0 reached through a variable, and a
0 introduced by a `fill_value=0` read or by `nan_to_num`. Deliverable 4's
manual read covers them.

## Impact
- **AN-background training** (`--an-background > 0`): points move
  in-state and out of validation blocks. Every model trained on the AN
  path before this CR learned from out-of-state and validation-block
  assumed negatives. Recorded in `CHANGELOG.md` (deliverable 6).
- **SSL pretraining:** tiles move in-state; new dependency (§3).
- **`generate_negatives.py`:** `to_albers` delegates to `regions.to_5070`;
  pool step 10 calls `regions.block_split`; outputs are byte-identical
  (B1).
- **`regions.py`:** gains `to_5070` and `block_split`. `check_partition.P6_NAMES` needs
  no change (no new constant).
- **Not affected:** the default training path (`--an-background 0`),
  CR-0009's pinned retrain, `acceptance_split.py`, and every file CR-0013
  gates (B1 proves the pool and negatives are unchanged).

## Risk: LOW
| risk | mitigation |
|---|---|
| Too few accepted points → `SystemExit` | Budget analysis (§2); V2 reports the rate; the message names it |
| Block rule or transform drifts from CR-0012's | One copy of each (§1); B1 digest check; V1 re-types the rule independently |
| Wrong CRS for block ids | U2's fixture is in a non-5070 CRS; V1 recomputes from lon/lat |
| AN path used before §2 lands | Interim guard (§4) |
| L1 false positives slow later work | Allowlist keyed by statement text; each entry reviewed |

## Test plan
**Validatable here:**
- U1–U7 and L1 (synthetic; no county file needed).
- B1, V1–V3 after CR-0012 lands.
- Constructed-sampler runs for PA-0021(a).

**Not validatable here:** the model-quality effect of the change. That
needs an AN-path retrain, which is out of scope; CR-0009's retrain does
not use the AN path.

## Deliverables (in execution order)
- [x] 1. Interim guard (§4) and U7; can land before CR-0007/CR-0012.
- [ ] 2. **Bug records.**
  - [ ] **BUG-0032** (0 treated as nodata, `train.py`
        `set(NODATA_SENTINELS) | {nodata, 0}`), with all §2
        sections. §4 recurrence review:
        - Prior instances: BUG-0008 (`predict.py`); BUG-0017
          (`dataset.py`, **still OPEN, unconfirmed**); BUG-0036
          (encoders, the PA-0006 scope extension).
        - Prior-PA failure analysis: category **too narrow and not
          enforced-verifiable**. Each PA-0006 sweep was scoped by file or
          layer — BUG-0008's by the inference path, BUG-0017's by
          `dataset.py`'s patch path, BUG-0036's by write-side encoders —
          not by the mechanism (a validity mask that admits a literal 0
          next to the nodata set, in any file). No lint enforced it.
        - Preventive action: **"extends PA-0006"**, at the next free PA
          id at filing. It requires validity masks to reject only
          declared nodata, `NODATA_SENTINELS` and non-finite values
          unless an L1 allowlist entry justifies more. L1 is its
          mechanical enforcement (§3.4).
        - Update PA-0006's Swept? cell from deliverable 4.
        - `BUG_LOG.md` row.
  - [ ] **BUG-0042** (assumed-negative points drawn into validation
        blocks, `train.py:290-306`). This is a new BUG, not an amendment
        of BUG-0027: it is a different code path (in memory, not the
        split files), and BUG-0027's corrective action (CR-0012) does not
        reach it. §4 recurrence review against PA-0018 and BUG-0027:
        - PA-0018 says a pooled holdout's guarantee must hold across the
          pooled data.
        - Its CR-0014 sweep examined per-region spatial computations that
          select a source by label. It did not list producers of training
          rows that bypass the split files.
        - CR-0013's gates see only files.
        - Category: **too narrow** (scoped by how the source is selected,
          not by every consumer of the holdout) and **not enforced**.
        - Preventive action "extends PA-0018": every producer of training
          rows, including rows generated in memory at training time, is
          constrained by the holdout and covered by a gate.
        - Sweep: every run-time producer of training rows
          (`build_datasets`, `pretrain.py`, `calibrate.py`, `tune.py`,
          `smoke_test_training.py`, `diagnose_*`). Each finding gets its
          own BUG.
        - `BUG_LOG.md` row.
- [ ] 3. Commit `tests/test_nodata_zero_lint.py` (L1 and its controls)
      before approval (CLAUDE.md §1, CR-0011 A3). Written 2026-09-30
      (committed `da1484f`, count check fixed `05d4ce5`); passes and reports exactly the 4 pinned statements
      until deliverables 4 and 6 are done.
- [ ] 4. **PA-0006 re-sweep, scoped by mechanism.**
  - **Scope:** every tracked, non-evidence file that reads
    `NODATA_SENTINELS` or a raster's declared nodata. That includes
    `analyze_grouse.py`, `check_raster_repair.py`, `check_road_dist.py`,
    `dataset.py`, `find_tsd_contrast_points.py`,
    `generate_road_distance.py`, `generate_time_since_disturbance.py`,
    `predict.py` and `legacy/audit.py`, plus `train.py`.
  - **Method:**
    - classify each L1 match;
    - manually read each validity or nodata mask for the out-of-reach
      forms (a 0 through a variable, a `fill_value=0` read,
      `nan_to_num`, an integer cast of NaN).
  - **Outcome:** each finding gets its own BUG (next free id,
    cross-referencing this sweep) or a written not-a-defect
    justification, which becomes its allowlist entry.
    The `find_tsd_contrast_points.py` statement is the known sibling. BUG-0017 is
    re-examined in this pass; it is closed or its OPEN status re-owned,
    per PA-0022.
  - **Result:** goes in the Swept? cells of PA-0006 and the new PA.
- [ ] 5. After CR-0007 and CR-0012 land: `regions.to_5070` and
      `regions.block_split` (§1), and `generate_negatives.py`'s switch
      (`to_albers` delegates; pool step 10 calls `block_split`). Re-run `generate_negatives.py`
      and `acceptance_split.py`; B1 passes.
- [ ] 6. §2 and §3; U1–U6 pass; L1 reports 0 matches outside the
      allowlist. `CHANGELOG.md` entry in the same commit: the AN-path
      and SSL changes, and that earlier AN-path models used out-of-state
      and validation-block negatives.
- [ ] 7. Real data, with `GROUSE_REQUIRE_REAL_DATA=1`:
  - [ ] 7a. V3 calibration (100 seeds × 3 regions, plus the
        constructed samplers); record the bound or the demotion to OBS.
  - [ ] 7b. V1–V3, plus the constructed-sampler runs for V1. Save the
        output to `docs/quality/evidence/CR-0015-background.txt`.
- [ ] 8. Remove the interim guard and U7.
- [ ] 9. Close-out:
  - BUG-0032: FIXED.
  - BUG-0042: FIXED.
  - **BUG-0029 closure rule:** corrective action "membership: CR-0007;
    split and draw: CR-0012; assumed negatives: CR-0015". The bug is
    FIXED when this deliverable 7b passes (CR-0012 having landed), and
    CLOSED when, in addition, CR-0009 closes.
  - Swept? cells for PA-0006, PA-0018 and the two new PAs.

## Out of scope
- **Buffering assumed negatives away from known presences.** This is a
  modelling choice; the docstring's rationale stands.
- **`window_in_bounds` for assumed-negative points.** Today an edge point
  is read with boundless nodata fill, and it stays so. CR-0012's
  predicate exists to keep file-based records identical between the
  pipeline and `dataset.py`; assumed-negative points are not
  file-based records.
- **An explicit uniformity gate.** Rejection sampling of uniform draws is
  uniform over the accepted set (verified by reviewer A); V3 covers the
  failure that matters.
- **The analysis-CRS constant** (`"EPSG:5070"` literals elsewhere,
  e.g. `analyze_grouse.py:679`). This is CR-0007's deferred item (d).
- Retraining with the AN path.
- Editing the untracked sweep scripts.
- BUG-0034.
- Fixes for re-sweep findings that need a CR of their own.
