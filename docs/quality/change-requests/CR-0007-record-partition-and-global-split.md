# CR-0007: Partition sighting records by state and centralise the shared spatial constants

**Status: PROPOSED (v8), 2026-09-30 — awaiting review. All deliverables pending.**
History, verdicts and dispositions: `CR-0007-review-log.md`. v1–v7 text:
commit `bb170ea` (v7) and `1445ccd` (v3). This document states only
current intent.

**Split (user decision 2026-09-30).** v7 is divided three ways. This CR
keeps the membership key and the shared constants. The global block grid,
the pooled thin and draw and the standing checks move to **CR-0012**. The
acceptance gates for CR-0012 move to **CR-0013**.

## Scope
Make `state` the only region-membership key for sighting records in
`analyze_grouse.py`'s outputs, check it against county polygons, and move
the spatial constants that several scripts define separately into
`regions.py`, with exact acceptance checks only.

## Why now
- **Records belong to several regions.** `analyze_grouse.clip_to_region`
  (`analyze_grouse.py:198`) selects by bounding box, and the boxes overlap.
  The current `evaluated_sightings_{ME,NH,VT}.csv` hold 18,407 rows, of
  which 4,455 (ME 283 / NH 2,696 / VT 1,476) are records of another state.
  Each of those 4,455 location keys also appears in its own state's file.
  This is the membership half of BUG-0027 (duplicated records across
  regions) and the positive half of BUG-0029 (positives selected by box,
  negatives by state).
- CR-0012 pools records across regions. That requires every record to have
  exactly one region first.
- **Constants have drifted.** `TIGER_YEAR` is 2025 in
  `generate_road_distance.py:114` and 2023 in `diagnose_road_bias.py:72`.
  `STATE_FIPS` is defined in both (`:115`, `:71`). The thinning distance,
  block size and exclusion buffer are each defined in the script that uses
  them. CR-0012 fuses and pools the steps that use them, so they must have
  one source first (PA-0001).

## The change

### 1. `regions.py`
Values below are today's values. This CR changes no constant's value.

| name | value | today defined at |
|---|---|---|
| `REGIONS` | `("ME", "NH", "VT")` | implicit in `BOXES` keys and each script's `--regions` default |
| `STATE_FIPS` | `{"ME": "23", "NH": "33", "VT": "50"}` | `generate_road_distance.py:115`, `diagnose_road_bias.py:71` |
| `TIGER_YEAR` | set by CR-0014 (2023); see below | `generate_road_distance.py:114` (2025), `diagnose_road_bias.py:72` (2023) |
| `MIN_SPACING_M` | 30 | `prepare_training_data.py:49` (`MIN_SPACING_M_DEFAULT`), `generate_negatives.py:71` |
| `BLOCK_SIZE_M` | 3000 | `prepare_training_data.py:52` (`BLOCK_SIZE_M_DEFAULT`); imported by `generate_negatives.py:60` |
| `BUFFER_M` | 300 | `generate_negatives.py:70` |
| `COUNTY_POLYGONS` | `data/roads/tl_2023_us_county.zip` | new; pinned on its own, independent of `TIGER_YEAR` |

- **`TIGER_YEAR`.** Its value is decided by CR-0014 (2023). CR-0007 only
  moves it. Whichever of CR-0007 and CR-0014 lands second makes both
  `generate_road_distance.py` and `diagnose_road_bias.py` import
  `regions.TIGER_YEAR` and deletes their local definitions. If CR-0007
  lands first, only `diagnose_road_bias.py` imports it (its value stays
  2023), and `generate_road_distance.py` keeps its local constant until
  CR-0014 replaces it. No generator output changes under this CR.
- `prepare_training_data.MIN_SPACING_M_DEFAULT` and `BLOCK_SIZE_M_DEFAULT`
  become bindings of the `regions` values, not literals. CR-0012 deletes
  them together with the CLI flags that use them.
- `BOXES` gets a docstring: raster request extents, not membership.
- **`verify_partition(lon, lat, state)`** returns the records whose
  county-polygon state differs from `state` or that fall inside no polygon.
  It reads `COUNTY_POLYGONS` with the pyogrio filter
  `where="STATEFP IN ('23','33','50')"`, dissolves by `STATEFP`, and
  reprojects from the file's EPSG:4269 to EPSG:4326 before a `within` join.
  geopandas is imported inside the function, so `regions.py`'s importers do
  not gain the dependency. `in_state(lon, lat, region)` uses the same
  polygons and predicate.
- Re-point the `BOXES` imports that go through `prepare_training_data` to
  `regions`: `predict.py:92`, `download_treemap.py:110`,
  `download_tcc_nlcd.py:74`, `diagnose_road_bias.py:68`,
  `generate_negatives.py:60`.

### 2. `analyze_grouse.py`
**Before:** every stage and every output of `analyze_region` (`:667`) uses
the box-clipped frame from `clip_to_region`.

**After:**
- `load_all_sightings` (`:156`) raises if any record's `state` (taken from
  the file name, `:177`) is not in `REGIONS`, and raises if
  `verify_partition` returns any record. Today it returns 0 of 43,024.
- `analyze_region` keeps the box clip for feature extraction and the KDE
  stage (`:787-795`). The KDE source is therefore every record inside the
  region's box, including neighbouring-state records near the border, as
  PA-0018 requires for a spatial computation.
- Immediately after the KDE stage, `valid` is restricted to
  `state == region` and gains a `region` column. Every later stage and
  every file write uses the restricted frame: envelope binning and
  metrics, `evaluated_sightings_{region}.csv` and
  `envelope_metrics_{region}.csv` (`:1016-1017`), and the maps. The
  `nonveg_flagged_{region}.csv` write (`:776`) moves after the restriction.
- **Consistent availability.** `background_envelope_sample` (`:411`) and
  `background_nonveg_rate` (`:324`) still draw uniformly over the box. They
  keep only points where `regions.in_state(..., region)` is true, drawing
  further batches from the same generator until `n_samples` in-state
  points exist. They raise after 20 batches. The in-state share of each box
  is ME 0.526 / NH 0.477 / VT 0.540 (20,000 uniform points, seed 1). The
  `MIN_VALID_FRAC` check (`:444`) is unchanged, because its denominator is
  now in-state points.
- `background_envelope_sample` writes the points it used to
  `data/pipeline/availability_sample_{region}.csv`, for P5.
- geopandas becomes a dependency of `analyze_grouse.py`.

Known limit: `verify_partition` cannot detect a record in coastal water
that lies inside a county polygon. Such records have no LANDFIRE value and
are removed by the extraction `dropna`, not by the partition.

**Provenance of `state`.** Positives: GBIF `stateProvince`, grouped into
per-state files by `sightings.py:132`. Negatives: the `stateProvince`
query parameter at `get_negatives.py:268`. Both are GBIF's value, and the
polygon check is the evidence for both.

### 3. `legacy/audit.py` (PA-0002)
An executable copy of `analyze_grouse.py` that writes the same
`data/pipeline/evaluated_sightings_*` and `envelope_metrics_*` paths
(`legacy/audit.py:1021-1022`). This CR makes the two diverge, so it gets a
runtime `SystemExit` guard. The other four copies are CR-0012's.

## Acceptance
All checks are exact predicates, in one committed script,
`check_partition.py`. It does not import `analyze_grouse.py`. It reads the
raw sighting files, the county polygons and the outputs.

| id | check | today (pre-CR files) | required |
|---|---|---|---|
| P1 | every row of `evaluated_sightings_R` and `nonveg_flagged_R` has `state == R` and `region == R` | 4,455 foreign rows; no `region` column | 0 violations |
| P2 | 5 dp location keys of the three `evaluated_sightings` files are pairwise disjoint | 4,455 shared keys | 0 |
| P3 | for each R, keys(`evaluated_R`) ⊆ K_R, the unique keys of raw state-R sightings; every key in K_R missing from `evaluated_R` has nodata in at least one `REQUIRED_FEATURES` raster at the vintage the vintage rule picks for its most recent year (the check re-implements that rule and the most-recent-year choice) | K = 7,924 / 2,303 / 3,725; 0 keys missing | holds for every key |
| P4 | `verify_partition` over all raw sightings | 0 of 43,024 | 0 |
| P5 | `availability_sample_R.csv` has exactly `BACKGROUND_N` rows, all inside R's polygon (recomputed) | file absent | holds |
| P6 | `tests/test_shared_constants.py`: `regions` holds the §1 values, and no live module outside `regions.py` assigns a literal to those names or to their `_DEFAULT` aliases. Exempt: the guarded copies, and `generate_road_distance.TIGER_YEAR` until CR-0014 lands | fails (8 literal definitions outside `regions.py`) | passes |
| P7 | import smoke: every module that imports `regions` or a re-pointed name (§1, §2, plus `generate_road_distance.py`, `download_rev.py`, `clean.py`) | — | all import |

P1 fails on today's files and P3 fails on any silently dropped record, so
neither a no-op nor a deletion passes (PA-0021(b)).

**Observations (reported, never blocking):**
- O1: symmetric difference between post-CR `evaluated_R` keys and pre-CR
  `evaluated_R` ∩ state-R keys. It is expected to be 0 if the LANDFIRE
  rasters have not changed since the pre-CR files were written.
- O2: habitat rows per region. Today, own-state habitat rows are 3,740 /
  1,119 / 1,552 (6,411 pooled).
- O3: judgeable envelopes (`Avail_N ≥ MIN_AVAIL_BG`) per region, before
  and after.

## Impact
- **Rewritten by the run:** `data/pipeline/evaluated_sightings_*`,
  `envelope_metrics_*` and `nonveg_flagged_*`. `availability_sample_*` is
  new. Selection ratios change, because usage and availability are both
  state-only, so negative weights change at CR-0012's rebuild.
- **Not read by training.** `train.py`, `calibrate.py` and
  `bench_pipeline.py` read only the train/val positive and negative CSVs,
  which this CR does not write. CR-0009's baselines are unaffected.
- **Other readers of the rewritten files:** `prepare_training_data.py`,
  `generate_negatives.py` (CR-0012 rewrites both), `tune.py:215`,
  `tune_bins.py:213`, `check_exotic.py:109`, `dupe_check.py:90`,
  `legacy/audit.py` (guarded), `clean.py` (CR-0012 guards it).
- **Not affected:** rasters, `road_dist`, model code, the negative files,
  splits.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Old `generate_negatives.py` runs between this CR's run and CR-0012. Its per-region buffer would then see only own-state sightings. | Measured cost: 3 candidates are within 300 m of a foreign-state sighting only. CR-0012's rebuild is the next data run; the backup (deliverable 1) restores the pre-CR state. |
| Rejection sampling fails to fill `n_samples` | Bounded at 20 batches, then raise; the in-state share is at least 0.477 |
| `TIGER_YEAR` moves a generator's output | Reconciliation rule in §1; `generate_road_distance.py`'s value changes only under CR-0014 |
| A silently dropped record | P3 |
| Polygon check across a datum | Explicit `to_crs` in `verify_partition` |

## Test plan
**Validatable here:** P1–P7 on the real run. `check_partition.py` run
against the backed-up pre-CR files must fail P1 and P2. A unit test with
one record deleted from a synthetic `evaluated` file must fail P3. The
test for P6 must fail on today's tree.

**Not validatable here:** whether the model improves (CR-0009). Behaviour
without geopandas or the county file (the error path is specified, not
exercised).

## Deliverables (in execution order)
- [ ] 1. Back up `data/pipeline/` and `data/negatives/` (24 MB + 27 MB) to
      `/home/ec2-user/grouse_backup/CR-0007/`, with a sha256 manifest.
      CR-0012 relies on this backup.
- [ ] 2. `check_partition.py` and `tests/test_shared_constants.py`,
      committed before approval (§1.1). P1/P2 are demonstrated failing on
      today's files.
- [ ] 3. `regions.py` §1, including `verify_partition`, `in_state`, and the
      `TIGER_YEAR` rule. Re-point the imports.
- [ ] 4. `analyze_grouse.py` §2.
- [ ] 5. `legacy/audit.py` guard (§3).
- [ ] 6. Run `analyze_grouse.py`. Run `check_partition.py`; P1–P7 pass.
      Record O1–O3. Do **not** run `prepare_training_data.py` or
      `generate_negatives.py`; CR-0012 does.
- [ ] 7. Bookkeeping:
      - New BUG (next free id): shared constants defined outside
        `regions.py`, including the `TIGER_YEAR` drift. Recurrence review
        against BUG-0001/PA-0001, with a prior-PA failure analysis
        (PA-0001 had no mechanical enforcement). PA: extend PA-0001 with
        P6 as its standing check.
      - BUG-0031: PA-0014's sweep omitted the `legacy/audit.py` /
        `analyze_grouse.py` pair, and PA-0002's sweeps left five runnable
        copies. Include the §4.2 failure analysis for PA-0002. Correct the
        Swept? cells of PA-0002 and PA-0014.
      - Promote `DRAFT_BUG-0034` first, with its status corrected to
        "open; fix owned by a future CR" (not "fixed in CR-0007").
      - Promote `DRAFT_BUG-0029` into `docs/quality/bugs/` with a
        `BUG_LOG.md` row, its §8 rewritten to cite PA-0020. File PA-0020
        from `res_qms_PA-0019-0020-0021-draft-rows.md`, with BUG-0034 as
        its live instance and no `coord_uncertainty_m` example.
      - Record the KDE-source decision in PA-0018's Swept? cell.
      - BUG-0027 and BUG-0029: corrective action "membership: CR-0007;
        split and draw: CR-0012". Status changes to fixed when CR-0012
        lands, and to closed after CR-0009.

## Landing order
- Independent of CR-0010 and CR-0008. `analyze_grouse.py` reads only the
  LANDFIRE vegetation channels.
- Before CR-0012, which requires P1–P7 passing on the files it reads.
- Either order with CR-0014 (the `TIGER_YEAR` rule in §1).
- Before or after CR-0009's baseline capture (see Impact).

## Out of scope
- Global block grid, pooled thin and draw, candidate pool, standing
  checks in `train.py`, `sample_background_points`, the other four
  duplicate scripts → CR-0012.
- Acceptance of the split and the draw → CR-0013.
- `TIGER_YEAR`'s value and `road_dist` regeneration → CR-0014.
- BUG-0026 (`diagnose_road_bias.py` uses home-state roads only): this CR
  re-points its constants and does not fix it.
- BUG-0034's fix; BUG-0028; the retrain (CR-0009).
