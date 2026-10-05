# CR-0032: Meta 1 m canopy-structure layers as model features

**Status: DRAFT, 2026-10-05** — awaiting independent review.
Verdicts and dispositions: `CR-0032-review-log.md` (created at the first
review). This document states only current intent.

## Scope
Add four static 30 m raster features, aggregated from the Meta/WRI 1 m
global canopy-height map, to every region's raster stack, so the CNN can
use fine-scale canopy structure (gaps, sapling and pole patches) that the
30 m LANDFIRE/TreeMap layers blur.

## Fixes
No defect. A feature addition, justified by measurement (below).

## Why now
Read-only diagnostics on the current split (CR-0021 data, record
`fc376877…`), gradient-boosted trees on the CNN's own inputs plus
candidate features, validation AUC:
- today's 15 rasters: 0.770 (`diagnose_gbm_baseline.py`; CNN 0.762);
- + LCMS/Hansen harvest history: +0.001 (`diagnose_disturbance_features.py`);
- + GEDI L2B lidar profile (incl. 0-5 m understory density): +0.000
  (`diagnose_lidar_features.py`);
- **+ Meta 1 m canopy height: +0.009 to +0.012 AUC, +0.013 to +0.017 AP**
  (`diagnose_lidar_features.py`, 3 seeds; `diagnose_structure_combo.py`,
  5 seeds); the only addition that cleared the pre-stated +0.01 bar.
  Meta + LCMS = Meta alone.
The strongest single new column was the share of canopy 5-12 m tall
(4th of 92 by permutation importance, after sclass, evt, road_dist);
the share under 1 m and the 1-5 m share follow.

## The change

### 1. Source
`projects/sat-io/open-datasets/facebook/meta-canopy-height` (Earth Engine,
community catalog; ImageCollection of 1 m canopy-height tiles in metres;
Meta/WRI, imagery 2009-2020, mostly 2018-2020; MAE 2.8 m). The asset id
is a module constant; the generator refuses if the collection is empty
over a region. A single static vintage.

### 2. Layers (4, continuous, int16, nodata `NODATA` = -9999)
Per 30 m cell, from the 1 m pixels inside it:

| feature | value | stored | `FEATURE_SPEC` scale |
|---|---|---|---|
| `mch_mean` | mean canopy height | decimetres (0-600) | 300.0 |
| `mch_f01` | share of 1 m pixels with height < 1 m | per mille (0-1000) | 1000.0 |
| `mch_f15` | share with 1 <= h < 5 m | per mille | 1000.0 |
| `mch_f512` | share with 5 <= h < 12 m | per mille | 1000.0 |

The share >= 12 m is 1000 minus the three and is not stored. Bin edges
(1, 5, 12 m) are constants `MCH_BIN_EDGES_M` in `models.py`, next to the
encoders `mch_height_encode` / `mch_share_encode`, which refuse NaN/inf
and out-of-range input (PA-0006 encoder clause, PA-0034). A cell is
**nodata** unless at least `MCH_MIN_VALID_FRAC` = 0.5 of its 1 m pixels
are valid (PA-0017: a value only where the source covers the cell); 0 is
a valid reading (PA-0028).

### 3. Generator `generate_canopy_structure.py` (new)
- Earth Engine: mosaic the collection; per 1 m pixel build the height
  band (dm) and three 0/1 indicator bands and a validity band; aggregate
  each with `reduceResolution(ee.Reducer.mean(), maxPixels=1024)` onto
  the EPSG:5070 30 m lattice (origin 0, as `download_tcc_nlcd.region_grid`
  snaps); mask cells with valid fraction < 0.5; encode as in §2.
- Export, mosaic and grid handling reuse `download_tcc_nlcd`
  (`ee_init`, `region_grid`, `tiles`, `fetch_tile` with its narrow retry
  clause, `_fetch_all`, `template_raster`) and
  `realign_rasters.warp_to_grid` (nearest) onto the region's template
  grid; `grouse_data.grid_mismatch` must be None or the file is not
  written. Default tile 6,000 m (200 x 200 output px, 36 M source px per
  tile; `--tile-m`).
- Output `data/landfire/{REGION}_{YEAR}_{feature}.tif` for every YEAR in
  the union of the region's existing feature vintages (identical copies
  of one static layer, exactly as `generate_road_distance.py` does), tag
  `GROUSE_COVERAGE=ee-mask`; atomic replace (`.tmp` + `os.replace`).
  Refuses when < 1 % of a region's cells are valid.
- CLI: `--regions`, `--project`, `--tile-m`, `--workers`, `--dry-run`
  (one tile, prints the four bands' value ranges, writes nothing).

### 4. Registration
`grouse_data.RASTER_FEATURES` gains the four names; `models.FEATURE_SPEC`
gains four continuous entries (§2). Nothing else: `train.discover_features`
picks them up when present in every region; the CNN's stem channels are
derived; `predict.py` and `calibrate.py` read a checkpoint's own feature
list, so existing checkpoints are unaffected.

## Impact
- **Training:** the next `train.py` run without `--features` uses 19
  rasters instead of 15 (stem input channels grow by 4). A run can
  exclude them with `--features`.
- **Existing checkpoints and calibrations:** unchanged in behaviour
  (checkpoint feature list wins in `predict.py`/`calibrate.py`).
- **Split files, acceptance (`acceptance_split.py`), standing checks:**
  untouched; the acceptance record's `rasters` list names only rasters
  the pipeline reads, which these are not.
- **Year bias (CR-0021):** a static layer is identical for every vintage,
  so it carries no year information.
- **Disk:** 4 int16 LZW files per region per vintage year.
- **Patch cache:** keyed on the feature list, so new caches are built.

## One change per CR (CR-0011 A5)
One feature family (generator + registration + tests). The retrain that
measures it is deliverable 5's evaluation, not a separate code change.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Community-hosted asset changes or disappears | Asset id is a constant; generator refuses on an empty collection; written files are tagged and stay usable |
| Earth Engine compute limits at 1 m | Small tiles (6 km), `--dry-run` pilot on one tile, `_fetch_all` retries transient errors only |
| Grid misregistration | Warp onto the template + `grid_mismatch` refusal (same path as tcc/nlcd) |
| Nodata read as a reading | Valid-fraction mask, sentinel -9999, encoders refuse NaN; test pins it |
| Imagery 2018-2020 vs records 2020-2024 | Accepted: a static structure snapshot, like `road_dist`; residual stands changed since 2020 |
| The CNN does not reproduce the trees' gain | Deliverable 5 decides: below +0.003 TTA AUC the names are removed from `RASTER_FEATURES` again (files may stay on disk) |

## Test plan
**Synthetic (this repository), `tests/test_cr0032.py`, written before
approval (CR-0011 A3):**
- T1 encoders: round-trip, refusal of NaN/inf/out-of-range (height < 0 or
  > 60 m; share outside [0, 1]).
- T2 registration pins: the four names in `RASTER_FEATURES` and
  `FEATURE_SPEC` with the §2 kinds and scales; `MCH_BIN_EDGES_M` =
  (1, 5, 12).
- T3 local build: with `fetch_tile` monkeypatched to write synthetic
  EPSG:5070 tiles (known values, a nodata block), the generator writes
  four files per vintage year on a synthetic template grid: values
  preserved, nodata where expected, `grid_mismatch` None, the copies
  byte-identical across years, nothing written on `--dry-run`, refusal
  when < 1 % valid.
- T4 years: the vintage list is the union of the region's other
  features' years (the road_dist rule).
- Existing suites still pass (`test_shared_constants`, both lints,
  `test_cr0031`, `test_acceptance_split`, ...).

**On the EC2 host:**
- `--dry-run` on one NH tile: value ranges plausible (mean 0-35 m,
  shares in [0, 1], some nodata only over water/outside coverage).
- Full run for ME, NH, VT; then a point cross-check: the generated
  layers sampled at the training points agree with the
  `diagnose_lidar_features.py` 30 m-radius samples (Spearman >= 0.8 for
  `mch_f512` vs `meta_f5_12_r30`).
- Evaluation: retrain the current best recipe (warm restarts, wd 3e-3)
  with the new features, calibrate, compare with
  `grouse_cr0031_wd3e3_wr.pth` (TTA AUC 0.762, AP 0.726, out-of-sample
  Brier 0.196).

## Deliverables
- [ ] 1. This CR and `tests/test_cr0032.py` (pre-approval); two
      independent reviews; approval.
- [ ] 2. Code: `generate_canopy_structure.py`, `models.py` (constants,
      encoders, `FEATURE_SPEC`), `grouse_data.RASTER_FEATURES`; all
      suites pass.
- [ ] 3. EC2: dry-run pilot, then the full generation (user runs it;
      writes under `data/landfire/`).
- [ ] 4. Point cross-check against the diagnostic samples.
- [ ] 5. Evaluation retrain + calibration; keep or remove decision
      recorded (§ Risk).
- [ ] 6. Bookkeeping: `ARCHITECTURE.md` (pipeline step 2), `CHANGELOG.md`,
      tracker follow-ups; close-out.

## Out of scope
- Airborne lidar (USGS 3DEP): GEDI added nothing, so not justified now.
- LCMS/Hansen disturbance layers: redundant with Meta in the trees.
- Neighbourhood (100 m) versions of the layers: the CNN's 64 x 64 window
  covers that itself.
- Dropping or replacing existing features (`tsd`, `road_dist`).
- Retraining policy beyond the one evaluation run (CR-0020).
