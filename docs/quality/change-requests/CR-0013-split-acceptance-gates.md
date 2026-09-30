# CR-0013: Acceptance gates for the pooled split and draw, as a committed script

**Status: REVISED (v2.3), 2026-09-30.**
- v2.2 text was signed off by both reviewers.
- v2.3 answers the replay implementer's findings F1–F18
  (`docs/quality/evidence/CR-0013-implementer-findings.md`). It awaits a
  bounded re-review.
- Deliverables 2–5 were done at `8501b51`. Deliverable 5a follows from
  v2.3.

History, verdicts and dispositions are in `CR-0013-review-log.md`. This
CR was split from CR-0007 v7's acceptance layer (commit `bb170ea`). This
document states only current intent.

**Approval preconditions:**
- PA-0021 and BUG-0033 are filed (deliverable 0).
- Deliverables 1–5 are committed on the review branch.

## Scope
Commit a script, its config and its attack suite. Together they decide
whether CR-0012's artifacts are accepted, independently of the code under
test, with no escape mode.

## Why now
CR-0012 cannot land without acceptance gates. It specifies the split and
the draw as deterministic functions of inputs and a seed, which allows
exact acceptance: an independent implementation must reproduce every
artifact row-for-row.

## Files
- `acceptance_split.py`.
- `docs/quality/acceptance_split.json`: the gate config. It holds
  constants, specs and environment, and never changes on calibration.
- `docs/quality/acceptance_split_obs.json`: OBS references, written only
  by `--calibrate`.
- `tests/test_acceptance_split.py`: unit tests and the attack suite.

## Design rules
1. **Independence (PA-0021(e)).**
   - The script never imports `prepare_training_data`,
     `generate_negatives`, `analyze_grouse`, `train`, `dataset`, `models`
     or `regions`.
   - Its only dependencies are numpy, pandas, scipy, pyproj, rasterio and
     geopandas.
   - It resolves raster paths itself from the config's path template and
     vintage rule (§ Normative definitions).
   - E11 parses `regions.py` and the manifest; it does not import them.
2. **Exact gates only.** A statistic becomes a GATE only when some
   constructed pipeline passes every exact gate and fails that statistic
   (PA-0021(c)). No such pipeline is known, so every statistic is an OBS.
3. **No escape mode.** No flag, environment variable or config key
   disables or downgrades a GATE. Pre-CR data fails.
4. **Separate authorship** (user decision).
   - A fresh agent writes `acceptance_split.py`. Its only sources are:
     - this CR;
     - **CR-0012 at `cec1542`** (v2.2.1, text approved 2026-09-30). v2.1
       at `29f388b` was the source for `8501b51`.
     - **CR-0007 at `6619bdd`** (v9, approved), for its §1 table,
       `verify_partition` and its §2 `region` column;
     - the code at `05d788d`.
   - CR-0013 is re-pinned whenever CR-0012 or CR-0007 is revised. The
     replay is written only against approved text.
   - A different fresh agent implements CR-0012.
   - Both agents' transcript ids are recorded in the review log, and
     reviewers check them.

## Normative definitions (pinned at commit `05d788d`)
The replay implements CR-0012 §2. Where §2 says "unchanged" or cites
code, the definition is the function at `05d788d`. The replay
re-implements it; it does not import it.

| function (at `05d788d`) | used by |
|---|---|
| `analyze_grouse.fit_scheme_binners`, `_apply_binner`, `build_envelope_id` | E10, R3 |
| `analyze_grouse.is_evt_phys_nonveg`, `load_evt_crosswalk` (newest `LF*_EVT.csv`) | E10, R3 |
| `analyze_grouse.sample_raster` (bounds test, nodata and `NODATA_SENTINELS` → NaN) | R3 |
| `generate_negatives.build_weight` (including its four basis strings), `split_for_unassigned` | E10, R3 |
| `grouse_data.RegionData.raster_path(feat, year)` (nearest valid year) | E8, R3 |
| `dataset.py:98-102` year fill | E8 |
| **CR-0007 v9 at `6619bdd`, §1:** `REGIONS`, `STATE_FIPS`, `COUNTY_POLYGONS_YEAR` (2023, read through `PATH_TEMPLATES["tiger_county"]`, i.e. `data/roads/tl_2023_us_county.zip`). `verify_partition`: pyogrio `STATEFP IN (<STATE_FIPS values>)`, dissolve by `STATEFP`, EPSG:4269 → 4326, `within`. It returns records in no polygon, or whose polygon's state ≠ `state`. | E1, E11, E12, R3 |
| **CR-0007 v9 §2:** `evaluated_sightings_R` carries `region == state == R` | E1, R1 |

**Coordinates.** Every distance, thin, buffer and block id is computed
from EPSG:5070 coordinates **recomputed from lon/lat** with the pinned
transform. The `x_5070`/`y_5070` columns are recorded values, checked by
full-row equality. On today's files they differ from a fresh transform by
at most 1.4e-9 m (F9). CR-0012's text does not yet say this (tracker).

**Premises and ties.** Each is a normative reading, recorded as F16:
- **Block-order ties.** A key collision between two blocks is broken by
  the `block_id` string.
- **`gbif_id` premise.** If `gbif_id` is null or not unique, the replay
  raises, so R3 and its dependants FAIL.
- **Crosswalk.** If the newest `LF*_EVT.csv` is not the pinned path, or
  its sha256 differs, the replay raises.
- **Year fill for E8.** The max is taken per checked file and region.
  This is moot while no year is NaN, which pool step 7 guarantees.

The config carries the values these need:
- `FEATURE_SPEC` keys, all 15 at `models.py:517`: evt, evh, evc,
  sclass, fdist, ch, cc, tcc, nlcd, road_dist, tsd, balive, tpa_live,
  qmd, carbon_dwn.
- The envelope-feature list is
  `sorted({c for c, _ in ENVELOPE_SCHEME if c not in ("evt_phys", "evt_group")} | {"sclass", "evt"})`
  (`generate_negatives.py:198-199`), which gives `evh, evt, sclass`.
- `ENVELOPE_SCHEME`, `NON_VEG_SCLASS_CODES` and the `EVT_PHYS` non-veg
  prefixes.
- The crosswalk path (`data/landfire/attribute_tables/LF2025_EVT.csv`)
  and its sha256.
- The raster path template.

**`split_for_unassigned`:**
`val ⇔ int(md5(f"{SPLIT_SEED}:{block_id}").hexdigest(), 16) % 10000 < vf × 10000`,
where `vf` = (positive-occupied blocks in val) / (positive-occupied
blocks), in float64.

**Window predicate (E8, CR-0012 window drop): in-bounds.**
- For a record and a raster: `(row, col) = rowcol(transform, x, y)` with
  floor, as `dataset.py`'s `src.index` computes it.
- `n = WINDOW_PX`, `h = n // 2`.
- The window `[row−h, row−h+n) × [col−h, col−h+n)` must lie inside
  `[0, height) × [0, width)`.
- Nodata inside the window is **not** considered. `dataset.py` reads
  nodata as missing, and a nodata predicate would drop records next to
  CR-0014's new Canada nodata, which CR-0014 says leaves records
  unaffected.

**Dedup (CR-0012 pool step 3): order-free.** Per key, keep the row with
the smallest `gbif_id`. `gbif_id` is non-null and unique over all
265,212 rows, while 6,492 keys carry more than one `year`, so
"first in file order" would not be reproducible. CR-0012 v2 adopts this
(§2 pool step 3).

**Shared-definition blind spot.** If a normative function is itself
wrong, the pipeline and the replay reproduce the same error. See stated
limit 2.

## Config (`acceptance_split.json`)
- **Constants.** These must equal CR-0012's manifest list one-for-one:
  - `REGIONS`, `MIN_SPACING_M`, `BLOCK_SIZE_M`, `BLOCK_ORIGIN_5070`,
    `BUFFER_M`, `VAL_FRACTION`, `SPLIT_SEED`, `WINDOW_PX`;
  - `NEG_RATIO`, `NONVEG_MAX_FRAC`, `W_FLOOR`, `W_CAP`, `NEUTRAL_WEIGHT`,
    `NONVEG_WEIGHT`, `MAX_COORD_UNCERTAINTY_M`;
  - key precision 5 dp.
- **Specs.** The hash spec: blake2b with an 8-byte digest; input strings
  `"{seed}:{lon:.6f},{lat:.6f}"`, `"{seed}:{block_id}"` and
  `"{seed}:neg:{lon:.6f},{lat:.6f}"`; `u = (key+0.5)/2**64`. The
  `split_for_unassigned` spec, window predicate, dedup rule and the
  lists above.
- **Paths.** The county file path and sha256.
- **Environment.** Versions of pandas, numpy, scipy, pyproj, PROJ,
  rasterio, GDAL, geopandas, shapely and pyogrio, plus the 4326→5070
  operation string.
- **`columns`.** The ordered column list for every output: P, N, C and
  B. These are normative for CR-0012 (v2.2 cites them). The positives
  list is the `evaluated_sightings` columns at `05d788d`, then `region`,
  `block_id`, `split`. `region` is selected by name from S, where
  CR-0007 §2 places it after `spatial_zone`. CR-0007 is unchanged.
- **`manifest_schema`.** The manifest's keys, count meanings (rows of a
  region remaining after each numbered step) and dropped-list format
  (`[lon, lat]`, sorted). Normative; CR-0012 v2.2 cites it.
- **`obs`.** OBS settings: `OBS_Z`, null sizes, seeds and cell sizes.
- **Rounding and parsing.**
  - Every `round` is Python's `round()` on the float64 product (half to
    even).
  - CSVs are read with `float_precision="round_trip"`.
  - Canonical row order is as in CR-0012 §2.

A config edit is a reviewed change. `acceptance_record.json` stores the
config's sha256, and CR-0009 cites it. A coordinated edit of the config
and `regions.py` passes E11; that is stated limit 4.

## Artifacts
Every path is under `--data-root` (default: the repository), for R in
`REGIONS`:

| set | files |
|---|---|
| **P** positives | `data/pipeline/thinned_positives_R.csv`; its parts `train_positives_R.csv`, `val_positives_R.csv` |
| **N** selected negatives | `data/negatives/negatives_R.csv`; its parts `train_negatives_R.csv`, `val_negatives_R.csv` |
| **B** blocks | `data/pipeline/block_assignments.csv` |
| **C** pool | `data/negatives/candidate_pool.csv` |
| **M** manifest | `data/pipeline/split_manifest.json` |
| **S** sightings (input) | `data/pipeline/evaluated_sightings_R.csv` |
| **I** other inputs | `envelope_metrics_R.csv`, `gbif_negatives_R.csv`, the crosswalk, and every raster the replay or E8 reads (`road_dist` extents included) |

"Digested artifacts" means the 18 CSVs in P and N, plus B and C.

## Gates (GATE, exact)
Combined files (`thinned_positives_R`, `negatives_R`) are pooled over
`REGIONS`. Parts are never pooled with their combined file. In the full
run, block ids and distances use coordinates recomputed from lon/lat,
never read from a column.

| id | set, pooling | predicate |
|---|---|---|
| E0 | P, N, B, C, M | Each file exists and has exactly the column set CR-0012 §2 names (as an ordered list in the config). Values, and therefore types, are constrained by R1–R4's full-row equality; no separate dtype check. A missing file is a named FAIL. |
| E1 | P, N (combined and parts), C | On every row, `state == region ==` the file's region. In C, `region ∈ REGIONS` and `state == region`. The regions present equal `REGIONS`. |
| E1p | P, N per R | `train_*_R` equals the `split == "train"` rows of the combined file, row for row, in the same order and values. The same holds for `val_*_R`. Together they cover the combined file. |
| E2 | P combined, pooled | 0 pairs closer than `MIN_SPACING_M` |
| E3 | N combined, pooled; C | 0 duplicate keys; 0 pairs closer than `MIN_SPACING_M` |
| E4 | P and N combined, pooled | Per class: 0 keys in both train and val. Across classes: 0 shared keys. |
| E5 | P ∪ N combined, pooled | 0 recomputed blocks hold both a train and a val record |
| E6 | P, N combined; C; B | recorded `block_id` equals the recomputed id; B's split equals the split of the positives in each block |
| E7 | N combined; C, vs S pooled | squared distance to nearest sighting `> BUFFER_M²` for every row |
| E8 | P, N combined; C | window predicate holds for every `FEATURE_SPEC` raster at `raster_path(feat, year)`, with `year` filled as `dataset.py:98-102` does |
| E9 | N per (R, split) | count `= round(n_pos × NEG_RATIO)`, where `n_pos` is counted from P; NonVeg `≤ round(n × NONVEG_MAX_FRAC)`; habitat pool in C `≥` habitat target |
| E10 | C, N | `evt_phys`, `envelope_id`, `is_nonveg`, `weight` and `weight_basis` equal the recomputed values (weight to relative 1e-12) |
| E11 | M | (a) Every S ∪ I file is listed in M's inputs, with a sha256 equal to the file on disk. A listed input outside S ∪ I passes only if it is a digested artifact that matches disk. <br>(b) "Every raster read" includes the fallback candidates that `raster_path`'s validation opens. <br>(c) M's constants, specs, `REGIONS` and environment equal the config, and so does the running environment. <br>(d) M's output digests equal the digested artifacts. <br>(e) `regions.py`, parsed with `ast`, holds literal values equal to the config for the eight CR-0012 names plus `STATE_FIPS` and `COUNTY_POLYGONS_YEAR`. |
| E12 | C, N; M | `verify_partition`, reimplemented, finds 0. M's dropped list equals the recomputation on the deduplicated raw candidates. |

**Replay gates.** From S, I and the config, the script produces P, B, C and
N, the same files CR-0012 writes. Equality is **full-row**: every
column, row sets matched on key, floats to relative 1e-12, everything
else exact. The manifest's per-step counts must also match.

Each R-gate also requires the shipped rows to be in CR-0012's canonical
order (config `row_order`).

| id | replayed | also checks |
|---|---|---|
| R1 | P, combined and parts | windowless-drop count |
| R2 | B | |
| R3 | C | every per-step count |
| R4 | N, combined and parts | |

**Record.** On a pass, the script writes
`data/pipeline/acceptance_record.json`. It holds:
- the sha256 of the 20 digested artifacts;
- the config and OBS-file sha256;
- the input digests from E11;
- `(path, size, mtime_ns)` for every raster in I;
- the commit and the OBS report.

The record's own sha256 goes into the committed evidence file
`docs/quality/evidence/CR-0012-acceptance.txt`.

**Standing subset.** `standing_checks(img_size, jitter, augment, *,
data_root=None, config=None)` is called by CR-0012 §5.
- The two keyword-only arguments are test hooks. Their defaults are the
  repository and the default config, and they cannot disable a check.
- It imports only numpy, pandas and scipy, at call time.
- Without pyproj it takes `x_5070`/`y_5070` from the files. The standing
  digests bind those columns to the accepted bytes, and R1/R4 checked them
  against lon/lat at acceptance.
- It collects every failure, then raises one `AcceptanceError` (a
  `RuntimeError`).
- It refuses a missing record, and a record made under a different config
  sha256.
- `--standing` uses the config's `standing` defaults (64, 0, False).
- Checks: E0 (P and N only), E1, E1p, E3 (N), E4, E5 and E6 on the 18
  CSVs for every config region.
- Digests: the 18 CSVs' sha256 must equal the record's.
- Raster fingerprint: each raster in I must match the record's
  `(path, size, mtime_ns)`.
- Window size: `img_size + 2·pad ≤ WINDOW_PX`, where `pad = jitter` if
  `augment` else 0.

| gate | full run | `standing_checks` |
|---|---|---|
| E0 (P, N), E1, E1p, E3 (N), E4–E6 | GATE | GATE |
| E0 (B, C, M), E2, E3 (C), E7–E12, R1–R4 | GATE | covered by the record digests |
| O1–O10 | OBS | — |

## CLI and report
`acceptance_split.py` takes these options:
- `--data-root DIR`. The root must hold `data/pipeline/`,
  `data/negatives/`, `data/landfire/` and `data/roads/`. A backup without
  that layout (e.g. `/home/ec2-user/grouse_backup/CR-0007/`, which holds
  `pipeline/` and `negatives/`) is run through a scratch root:
  - each CSV is symlinked file by file, so no record can be written into
    the backup;
  - `data/landfire` and `data/roads` are linked to the live tree.
- `--config`
- `--emit-reference DIR` (writes the replay's own artifacts)
- `--calibrate`
- `--standing`

Every gate is evaluated and reported, even after one fails. A gate whose
input is missing reports `FAIL (missing <path>)`. The exit code is 0 only
if every GATE passes; the record is written only then. The report lists
each gate once, and marks each O-row as OBS.

## Attacks (PA-0021(a))
Each row is a mutation in `tests/test_acceptance_split.py`, applied to
`--emit-reference` output, which must pass unmutated. So the suite runs
before CR-0012 exists. "R7-A" means round-7 reviewer A's scripts,
committed by deliverable 1.

| attack | recorded in | must fail |
|---|---|---|
| Box-clipped membership | `inv_reviewB_confirm.py` | E1, E4, E5 |
| Train rows copied into `val_positives_ME.csv` | CR-0013 round-1 A | E1p |
| Val-positive `year` set to NaN, or a positive `weight` set to 0.2 (this adds a column, so it also fails E0) | CR-0013 round-1 A | R1 |
| Column dropped or added | CR-0013 round-1 B | E0 |
| Per-region thin, then pool | `inv_reviewB_pipeline.py` | E2, R1 |
| Thin at 60 m | `inv_reviewF_i12.py` | R1, E11 |
| Order-dependent thinner or draw | `res_determ_orders.py`, `inv_reviewF_i14.py` | R1, R2 |
| Dropped shuffle | `inv_reviewF_attack1.py` | R2 |
| Eastern-half or dense-first val draw | `inv_reviewF_attack_i14.py`, `res_thresh_pos.py` | R2 |
| Neighbour-preferring stratified draw | `inv_reviewH_i14c.py` | R2 |
| Two origins; ids read from the column | `inv_reviewD_attack.py`, `inv_reviewD_attack2.py` | E5, E6 |
| Southern-half/southern-sixth draw | `inv_reviewD_cr7b.py`, `inv_reviewF_attack4b.py` | R4 |
| NH-only skew (Break 1) | `inv_formalA_break1.py` | R4 |
| Sorted-id positive-free split (Break 2) | `inv_formalA_attackC.py`, `inv_formalA_attackC2.py` | R3 |
| 10A inter-region skew | `inv_formalC_attack1.py`, `inv_formalC_attack2.py` | R4 |
| 10B feature-extremum split | `inv_formalC_attack3.py` | R3 |
| 10A″ northern candidates dropped **by pipeline code** | `inv_formalC_attack4.py`, `inv_formalC_attack5.py` | R3 (the input-borne variant is stated limit 1) |
| 10C NonVeg top-up | `inv_formalC_attack6.py` | E9, R4 |
| Pool strips at 3–20 % | `res_supply_1.py` … `res_supply_8.py` | R3 |
| Weight collapse; NonVeg or species monoculture | `res_comp_attacks.py` | E10, R4 |
| Pool weight suppression; `build_weight` changed | v7 stated limits 4–5 (`bb170ea`) | E10 |
| No 300 m buffer | R7-A `attacks.py` A1; `inv_reviewF_attack_buffer.py` | E7, R3 |
| With replacement; ×20 near grouse, as replicated rows | R7-A `attacks.py` A2, A3p | E3, R4 |
| Weight ×20 near grouse, no replication | R7-A `attacks.py` A3p (variant) | R4; E10 if the weights are written |
| Val candidates near val positives thinned | R7-A `valattack.py` | R3 |
| Duplicate negatives, 5–10 % | R7-A `comp.py`, `inv_reviewH_negdup.py` | E3, R4 |
| Partition exception kept (NH-filed record in ME); dropped list edited | CR-0013 round-1 B | E12 |
| Input edited after the manifest | CR-0013 round-1 A | E11 |
| `--regions` subset | v7 § `--regions` hole | E1, E11 |
| Windowless record kept | `inv_reviewH_i5.py` | E8 |
| **Standing checks:** val file edited after acceptance; pre-CR file swapped in; raster touched; `--jitter 8` with augmentation | CR-0013 round-1 B | `standing_checks` raises |

## Observations (OBS: reported, never blocking)
Terms used below:
- **RF** = 1,920 m (`WINDOW_PX` × 30 m).
- **TV** = total variation distance between two histograms.
- **KS** = two-sample Kolmogorov–Smirnov statistic.
- **SMD** = standardised mean difference.
- `d` = distance from a positive to the nearest negative of the same
  region.

Null populations:
- **N-split:** 400 replays of R2 with the block-order seed varied, on
  the realised thinned positives.
- **N-draw:** 400 replays of R4 with the draw seed varied. The realised
  split and pool are fixed.
- **N-perm:** 1,000 in-run permutations of the val labels over blocks.

Operational choices are fixed in the config's `obs` section and recorded
as F15:
- null seeds are `null_seed_base + i`;
- "records per val block" is the mean;
- a block's val indicator means "holds any val record";
- the weight-proportional pool is the pool's `weight_basis` histogram
  weighted by `weight`;
- the worst cell is taken over (R, split);
- `d` uses the combined files;
- "previous accepted run" means the previous record's `obs` values.

A z-score is reported only for rows that have a null. Rows marked
"none" report the value and its change from the previous accepted run.

| id | statistic | class / subset / pooling | null |
|---|---|---|---|
| O1 | median distance from each val positive to the nearest train positive | positives / all / pooled | N-split |
| O2 | records per val block; \|val share of blocks − val share of records\| | positives / all / pooled | N-split |
| O3 | Moran's I of the val indicator, kNN k = 4, 8, row-standardised, over block centres | positives / occupied blocks / pooled | N-perm |
| O4 | as O3, over blocks holding any selected record; and over blocks holding any pool record | both / all / pooled | N-perm |
| O5 | `Exc` = mean of `max(0, d − RF)` in km; `S` = share with `d > RF`; `Sws_val`, `Excws_val` = the same for val positives vs val negatives only | both / as named / per region | N-draw |
| O6 | NonVeg share, val − train; `weight_basis` TV, train vs val; `weight_basis` TV, selected vs weight-proportional pool; mean habitat weight, selected ÷ pool; `evt_phys` TV within NonVeg, selected vs pool; `common_name` TV, selected vs pool | selected vs pool / as named / per region | N-draw |
| O7 | habitat pool ÷ habitat target, worst cell; pool ÷ target; SUP-O = positives farther than 10 × m from the pool, where m is the median over 10 km cells (≥ 5 positives) of the median distance to the pool; SUP-R = max ÷ median of those cell medians | pool / per cell / per region | none |
| O8 | max KS val vs train over the continuous features (positives); the same for selected negatives, whole and habitat-only; max SMD | positives; selected / as named / pooled and per region | N-split; N-draw |
| O9 | year histogram per class (shows BUG-0034) | both / all / per region | none |
| O10 | val fraction per class | both / all / per region | none |

- **Calibration.** `--calibrate` runs only after every GATE passes, using
  the script's own replay. It writes `acceptance_split_obs.json` with a
  footing digest over S and I; `acceptance_split.json` is left
  unchanged. A footing change marks the references stale.
- **`road_dist`.** O8 reads its values and E8 its extents. Both are taken
  after CR-0014 lands; if CR-0014 lands later, the full run and O8's
  calibration are repeated.

## Stated limits
1. **Inputs are taken as given**: S, I and the rasters. Examples are
   input-borne nodata (10A″ via rasters) and upstream selection. They are
   gated by CR-0007 (P1–P7), CR-0008, CR-0010 and CR-0014, and bound here
   by digest (E11) so they cannot change unnoticed.
2. **A shared misreading passes.** This covers both a shared misreading
   of CR-0012 §2 and a defect in a normative function at `05d788d`
   (§ Normative definitions). Mitigations: separate authorship (rule 4)
   and the attack suite. OBS flags are the residual signal.
3. **Design adequacy** is not testable by any gate: block size, val
   fraction, cap, weighting, and support quality. O1–O10 report it, and
   CR-0009 measures its consequence.
4. **The config is the pre-registration.** A coordinated edit of the
   config, `regions.py` and the pipeline passes. Config changes are
   reviewed, and the record carries the config's sha256.
5. **Year-gap filter.** `filter_by_year_gap` removes records after
   acceptance. E2–E5 are preserved under removal. Support changes are
   visible in O9, and BUG-0034 owns them.
6. **Record authenticity.** The record is a file under `data/`. Its
   committed evidence copy is the reference, and `standing_checks`
   re-runs the coordinate gates regardless.
7. **An environment change fails E11.** It requires a rebuild.

## Impact
- New files: see § Files. `acceptance_record.json` is written on a pass.
- Every training entry point depends on the standing subset (CR-0012 §5).
- **No escape.** CR-0009's pre-CR baselines come before CR-0012 (CR-0012
  deliverable 0).
- Code under test is not touched.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Replay false-fails a correct pipeline | Order-free rules; a shuffled-row test (below); the reference output must pass unmutated |
| Float or PROJ differences at thresholds | Squared float64 comparisons; environment pinned (E11) |
| Standing checks slow training start | CSVs, hashes and stat calls only; no rasters |
| OBS mistaken for a gate | Every report line carries OBS; flags summarised |

## Test plan
**Validatable here:**
- E-row unit tests.
- The attack suite.
- **Shuffle test:** the replay run with every input CSV's rows randomly
  permuted and `REGIONS` reordered must produce byte-identical outputs.
  This is possible only with the order-free dedup.
- Deliverable 5.
- `--calibrate` on reference output.
- Runtime and memory of the full run and of `standing_checks`, recorded.

**Not validatable here:**
- Real CR-0012 artifacts (CR-0012 deliverable 6).
- O8 before CR-0014.
- Whether OBS flags predict model harm (CR-0009).

## Deliverables (in execution order)
**Before approval (reviewed in round 2):**
- [ ] 0. File BUG-0033 and PA-0021, bookkeeping only, by this CR's author.
      No BUG-0033 text exists yet, so draft it from CR-0007 v7's BUG-0033
      deliverable (`bb170ea`) and the review log's break history.
      - Include the §2.4 statement (E-1).
      - The calibration-from-extrema cause gets its own BUG, with the next
        free id at filing (BUG-0036 and BUG-0037 are taken).
      - PA-0021 text: the draft in `res_qms_PA-0019-0020-0021-draft-rows.md`,
        plus clause (a) "recorded so it can be re-run" (E-PAa) and clause
        (f) (class, subset, null). This is the one text the tracker's
        "Reconcile PA-0021" item asks for.
      - Lineage: extends PA-0016.
      - Swept?: "no — not yet run; owner: CR-0013", as PA-0022 requires
        (a BUG or CR, not a tracker item). The scope is the acceptance tables of
        CR-0007..0013 plus live-code thresholds.
      - Filing PA-0021 before PA-0019/0020 is recorded under the tracker's
        PA-numbering item.
- [ ] 1. Commit the untracked evidence scripts in § Attacks. Copy R7-A's
      scripts into `docs/quality/evidence/CR-0007-r7/`, including the
      data-producing ones (`build.py`, `lib.py`, `feats.py`). Their CSV
      outputs are regenerable and not committed; they are labelled
      provenance-only.
- [x] 2. The config (constants, specs, environment and `obs` settings).
      The OBS file is created only by `--calibrate`.
      E0's ordered column lists are derived and written out here:
      positives = the `evaluated_sightings` columns at the pinned commit
      plus `region`, `block_id`, `split`; negatives = `CSV_KEEP` plus the
      envelope features and the other columns written at the pinned
      commit, plus `region`.
- [ ] 2a. The PA-0021 sweep (this CR owns it, per deliverable 0's Swept?
      cell): the acceptance tables of CR-0007..0013 and live-code
      thresholds; each instance found gets its own BUG (§3.5); update the
      Swept? cell.
- [x] 3. `acceptance_split.py`, by a separate author (rule 4), at `8501b51`.
- [x] 4. `tests/test_acceptance_split.py`: every attack row, the unit
      tests and the shuffle test. 77 pass at `8501b51`.
- [x] 5. Run the script on today's pre-CR files (`--data-root` defaults to
      the repository, read-only, with no record written on failure) and on
      `/home/ec2-user/grouse_backup/CR-0007/` if it exists. Commit the
      report.
      - Expected: **every gate FAILs except E1p**. Every gate must be
        reported.
      - Substantive failures:
        - E0, E1, E4, E5, E6, E11, E12 and R1–R4;
        - **E2**: 1,690 positive pairs under 30 m;
        - **E8**: 4 NH-filed foreign positives outside the window.
      - E3, E7, E9 and E10 fail because C is missing (named FAIL); their
        N parts are clean.
      - Done at `8501b51` (`docs/quality/evidence/CR-0013-first-run.txt`).
- [ ] 5a. v2.3 follow-ups, by the replay author:
      - config: `pins.cr0007` → `6619bdd`; the `regions_py` extra name
        `COUNTY_POLYGONS` → `COUNTY_POLYGONS_YEAR`, with the county path
        from `PATH_TEMPLATES["tiger_county"]`; the environment additions;
      - code: E11(e) names; the canonical-order check in R1–R4, promoted
        from `NOTE` to GATE;
      - tests for both. Re-run deliverable 5.

**After approval:**
- [ ] 6. Inside CR-0012 deliverable 6: the full run passes. Then run
      `--calibrate`, commit the OBS file and the evidence copy of the
      record. After CR-0014, re-calibrate O8.

## Landing order
CR-0007 → CR-0012 **text approved** (its commit recorded here; rule 4) →
CR-0013 deliverables 0–5, then CR-0013 approval → CR-0009 baselines →
CR-0012 implemented (deliverable 6 runs inside it) → CR-0009 retrain.
CR-0014 (implemented) precedes CR-0012's acceptance run.

## Out of scope
- The split and draw (CR-0012) and membership (CR-0007).
- Promoting an OBS to a GATE (needs a new CR, per design rule 2).
- CI (`CLAUDE.md` §3.4).
