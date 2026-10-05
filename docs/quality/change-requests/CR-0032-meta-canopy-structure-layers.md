# CR-0032: Meta 1 m canopy-structure layers as model features

**Status: APPROVAL LAPSED, 2026-10-05** — deliverable 1b failed its bar
(`docs/quality/evidence/CR-0032/1b_combo_run1.txt`: the four columns at
30 m radius +0.0033 AUC, bar +0.006). Revision pending the pre-stated
r30 + r100 measurement (review log § 1b). Verdicts and dispositions:
`CR-0032-review-log.md`. This document states only current intent.

## Scope
Add four static 30 m raster features, aggregated from the Meta/WRI 1 m
global canopy-height map, to every region's raster stack, so the CNN can
use fine-scale canopy structure (gaps, sapling and pole patches) that the
30 m LANDFIRE/TreeMap layers blur.

## Fixes
No defect. A feature addition, justified by measurement (below).

## Why now
Read-only diagnostics on the current split (CR-0021 data), gradient-
boosted trees on the CNN's own inputs plus candidate columns, validation
AUC:
- today's 15 rasters: 0.770 (`diagnose_gbm_baseline.py`; CNN 0.762);
- + LCMS/Hansen harvest history: +0.001 (`diagnose_disturbance_features.py`);
- + GEDI L2B lidar profile: +0.000 (`diagnose_lidar_features.py`);
- + all 12 Meta columns (mean, sd, four height shares; 30 m and 100 m
  radius): +0.009 to +0.012 AUC, +0.013 to +0.017 AP
  (`diagnose_lidar_features.py`, 3 seeds; `diagnose_structure_combo.py`,
  5 seeds). The share of canopy 5-12 m tall ranked 4th of 92 by
  permutation importance.

The four columns this CR builds (30 m mean and the < 1, 1-5, 5-12 m
shares) are measured on their own by `diagnose_structure_combo.py` row
"+ CR-0032 four (r30)" (deliverable 1b). Approval requires that row's
mean gain to be at least +0.006 AUC; otherwise the layer set is revised.

## The change

### 3.1 Source and Earth Engine image
Asset `MCH_ASSET = "projects/sat-io/open-datasets/facebook/meta-canopy-height"`
(ImageCollection of 1 m canopy-height tiles in metres; Meta/WRI, imagery
mostly 2018-2020; MAE 2.8 m). Per region, in `mch_image(ee, bounds)`:
1. `coll = ImageCollection(MCH_ASSET).filterBounds(region)`; refuse if
   empty.
2. `proj = coll.first().projection()`;
   `h = coll.mosaic().setDefaultProjection(proj)` (metres; masked where
   the source has no data).
3. Bands `h`, `h < 1`, `1 <= h < 5`, `5 <= h < 12` (masked where `h` is),
   aggregated by `reduceResolution(ee.Reducer.mean(), maxPixels=MCH_MAX_PIXELS)`
   (`MCH_MAX_PIXELS` = 4096): the mean height and the three shares of the
   **valid** 1 m pixels in each output cell.
4. Band `valid = ee.Image(1).updateMask(h.mask()).unmask(0)
   .setDefaultProjection(proj)` (a constant image has no native
   projection of its own), same reducer: the valid fraction of each
   cell, never masked.
5. `.toFloat().unmask(-1)`: any masked output cell is the marker -1
   (Earth Engine would otherwise export it as 0).

The five float bands (`h, f01, f15, f512, valid`) are downloaded raw; all
encoding is local (§3.3).

### 3.2 Grid and tiles
The output grid is the region's **template grid** (latest `evt` clip,
`download_tcc_nlcd.template_raster`). Each tile is a window of that grid,
`tile_px` x `tile_px` (default 256, a multiple of 16; `--tile-px`),
fetched by `fetch_window(ee, image, crs_wkt, transform, width, height,
dest, retries=4)`: one `getDownloadURL` with the template's WKT as `crs`,
the window's affine as `crs_transform` and the window rectangle as
`region`, retrying the same transient types as
`download_tcc_nlcd.fetch_tile` (BUG-0066 clause), into `dest + ".part"`,
then `os.replace`. A fetched or cached tile is used only if its CRS equals
the template's and its transform equals the requested window's to 1e-3
px; otherwise the run is refused (fetched) or the tile re-fetched
(cached). No warp, no mosaic: a tile's cells are the template's cells. Windows where the template is
entirely nodata are not fetched (written as `NODATA`). The asset filter
uses the template footprint in lon/lat (`template_bounds_lonlat`,
`transform_bounds(..., densify_pts=21)`).

### 3.3 Encoding (local, `encode_tile`)
Per cell, from the five floats:
- **`NODATA`** (-9999) where `valid < MCH_MIN_VALID_FRAC` (0.5), or any
  band is -1 (PA-0017: a value only where the source covers the cell);
- **`NODATA`, counted** where `h > MCH_HEIGHT_MAX_M` (60 m): a source
  artefact, not clipped (PA-0034). The region is refused if these exceed
  `MCH_MAX_OVER_FRAC` = 0.001 of the valid cells;
- otherwise `mch_height_encode(h)` and `mch_share_encode(f)`. Each refuses
  NaN/inf (PA-0006 encoder clause), rounds to stored units, then refuses
  a stored value outside 0-600 dm / 0-1000 per mille (so float32 means a
  hair outside [0, 1] are kept, real out-of-range values refused; no
  clipping, PA-0034). 0 is a valid reading (PA-0028).

| feature | value | stored | `FEATURE_SPEC` scale |
|---|---|---|---|
| `mch_mean` | mean canopy height of valid pixels | decimetres 0-600 | 300.0 |
| `mch_f01` | share of valid pixels < 1 m | per mille 0-1000 | 1000.0 |
| `mch_f15` | share 1 <= h < 5 m | per mille | 1000.0 |
| `mch_f512` | share 5 <= h < 12 m | per mille | 1000.0 |

Constants `MCH_BIN_EDGES_M` = (1, 5, 12), `MCH_MIN_VALID_FRAC`,
`MCH_HEIGHT_MAX_M` and the two encoders live in `models.py`.

### 3.4 Generator `generate_canopy_structure.py` (new)
`build_region(ee, image, rd, tile_px=256, workers=8, dry_run=False,
tile_dir=None, pilot_lonlat=None)`:
- **Years**: `vintage_years(rd)` = union of the region's feature
  vintages excluding `STATIC_FEATURES` (`road_dist` and the four
  `mch_*`), so a stale static file cannot perpetuate its year.
- **Tiles**: fetched concurrently (`download_tcc_nlcd._fetch_all`) into a
  persistent cache (`--tile-dir`, default `~/.cache/grouse_mch/{REGION}`,
  outside `data/`) under a subdirectory keyed by a hash of (template WKT,
  transform, shape, `tile_px`, `MCH_ASSET`, `RECIPE_VERSION`); a cached
  tile passing the §3.2 identity check is reused, so a failed run
  resumes and a changed template or recipe re-fetches.
- **Write**: each tile is encoded and written into its window of four
  staged `.tmp` files (template profile, int16, nodata -9999, deflate,
  block = `tile_px`; tags `GROUSE_COVERAGE=ee-mask`,
  `GROUSE_SOURCE=MCH_ASSET`). After the last tile: refuse (staged files
  deleted, existing files untouched) if valid cells < 1 % of template-
  valid cells or the > 60 m share exceeds its limit; check
  `grid_mismatch(staged, template) is None`; then copy to every vintage
  year and `os.replace` (identical bytes per year).
- **Dry run / pilot**: fetches one window (the one holding most of the
  region's positives, template centre if none; `--pilot-lonlat`
  overrides) into a temporary directory, prints the native CRS and
  nominal scale, the per-band counts of -1, low-validity, > 60 m and
  encoded cells, the fraction of `valid` strictly inside (0, 1) (0 means
  the band was not aggregated), value ranges, and the measured fetch time;
  runs `grid_check(ee, nlcd_image, rd, "nlcd", window)` - the region's
  latest NLCD year fetched through `fetch_window` over the pilot window,
  compared with the on-disk `nlcd` file, refused below `MIN_GRID_AGREE`
  (0.99) of cells equal (catches an EE misreading of the template WKT,
  which the gate shares); writes the
  encoded window as one 4-band int16 file (bands in `MCH_FEATURES` order)
  to `--pilot-out` (default `/tmp/mch_pilot_{REGION}.tif`) and nothing
  under `data/`. Refuses if `ceil(30 / g + 1)^2 > MCH_MAX_PIXELS`, with
  `g` the native pixel's ground size (nominal scale x cos(latitude) for a
  Mercator source).
- **`--copy-only`**: writes missing vintage years from the existing
  latest `mch_*` files, no Earth Engine.
- Returns `{"years", "written", "valid_frac", "n_tiles", "skipped",
  "over_max"}`. CLI: `--regions`, `--project`, `--tile-px`, `--workers`,
  `--tile-dir`, `--dry-run`, `--pilot-lonlat`, `--pilot-out`,
  `--copy-only`. `__main__`
  block last (PA-0035).

### 3.5 Acceptance gate `check_canopy_structure.py` (committed with v2)
Read-only. Per region, two seeded samples from the generated
latest-vintage files - valid cells, and any cells inside the template's
valid area (so over-masking shows) - are recomputed in Earth Engine with `reduceRegions`
over each cell's exact polygon (template CRS) at the source's native
scale, plus a sample of the four bands' interior-share fraction. The
script's constants and `compare()` decide pass/fail; the CR does not
restate them. The pilot runs it on the pilot tile; the full run runs it
on every region.

### 3.6 Registration
`grouse_data.RASTER_FEATURES` gains the four names; `models.FEATURE_SPEC`
gains four continuous entries (§3.3). `train.discover_features` picks them
up when present in every region; `predict.py` and `calibrate.py` read a
checkpoint's own feature list.

## Impact
- **Training:** the next `train.py` run without `--features` uses 19
  rasters (stem input channels +4). `--features` excludes them.
- **Existing checkpoints and calibrations:** unchanged (checkpoint
  feature list wins).
- **Split pipeline and acceptance:** after CR-0033, the split window mask
  and the acceptance replay read the same pinned 15-name list, so
  registering `mch_*` changes neither; split files are not regenerated.
- **Diagnostics:** after registration, the `diagnose_*` scripts' "today's
  features" baseline includes `mch_*` (they use `discover_features`).
- **Year bias (CR-0021):** identical bytes for every vintage; no year
  information.
- **Disk:** 4 int16 deflate files per region per vintage year; tile cache
  under `~/.cache/grouse_mch` (deletable after the run).
- **Patch cache:** keyed on the feature list; new caches are built.

## One change per CR (CR-0011 A5)
One feature family: generator, encoders, registration, and its gate and
tests. The split-pipeline coupling found in review is CR-0033.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| Masked cells exported as readings | `unmask(-1)` + unmasked validity band + local `NODATA`; T3 and the pilot counts |
| Aggregation not performed (projection) | `setDefaultProjection`; `check_canopy_structure.py` interior-share and cell recomputation |
| EE limits / long runs | 256 px tiles, resumable cache, all-nodata windows skipped, pilot runtime estimate recorded before the full run |
| Source encodes water as height 0, not masked | Accepted: water reads as "open" (f01 near 1000), which `evt`/`nlcd` already identify; the pilot reports it |
| Community-hosted asset changes | Asset id constant; empty collection refused; written files tagged |
| Imagery 2018-2020 vs records 2020-2024 | Accepted: a static snapshot like `road_dist` |
| The CNN does not reproduce the trees' gain | § Evaluation decides; removal is a follow-up CR |

## Evaluation (deliverable 5)
Two arms, same recipe (`--sched warm_restarts`, wd 3e-3, the
`grouse_cr0031_wd3e3_wr` command), seeds 0, 1, 2 each: **base** with
`--features` set to the 15 current names, **mch** with the 19. Each run
calibrated. Keep the layers if the mean TTA AUC gain is >= +0.003, the
mean AP gain is >= 0, and the mean out-of-sample Brier is not worse by
more than 0.002. Otherwise a follow-up CR removes them from
`RASTER_FEATURES`/`FEATURE_SPEC` and reverts T2 (files may stay on disk).

## Test plan
**Synthetic, `tests/test_cr0032.py` (pre-approval, CR-0011 A3):**
- T1 encoders: values, int16, round-then-check (1.0004 → 1000), refusal
  of NaN/inf/out-of-range; encoded boundary values are not sentinels.
- T2 registration: the four names in `RASTER_FEATURES` and
  `FEATURE_SPEC` with §3.3 kinds and scales; `MCH_FEATURES` order; the
  generator's and the gate's `MCH_ASSET` and valid-fraction rule are
  equal.
- T3 `encode_tile` and local build, with `fetch_window` monkeypatched to
  write raw 5-band float tiles on the requested window: values encoded;
  -1, low-validity and > 60 m cells → `NODATA`; too many > 60 m cells →
  refusal; all-nodata template window not fetched; `grid_mismatch` None;
  byte-identical copies per year; dry run writes only the pilot file,
  nothing under `data/`; < 1 % valid →
  refusal with existing files untouched; a second run with the tile cache
  fetches nothing; an off-grid fetched tile is refused; a changed
  template re-fetches every tile; `grid_check` passes the same grid and
  fails a one-cell shift.
- T4 years: union excluding `STATIC_FEATURES` (stale `mch` year ignored).
- T5 gate: `check_canopy_structure.compare` passes matching values and
  fails a dm/m scale error, bimodal (sampled) shares, 0-for-nodata, and
  over-masking.
- Existing suites pass.

**On the EC2 host (user runs; results recorded in the CR's evidence
directory `docs/quality/evidence/CR-0032/`):**
1. `--dry-run` pilot on NH: counts, ranges, native scale, fetch time;
   `check_canopy_structure.py --pilot` passes.
2. Full run ME, NH, VT; `check_canopy_structure.py` passes per region.
3. Evaluation (above).

## Deliverables
- [x] 1. This CR, the review log, `tests/test_cr0032.py`,
      `check_canopy_structure.py`; two independent reviews; approval
      (round 2, both APPROVE WITH FOLLOW-UPS; v3 applies them).
- [ ] 1b. `diagnose_structure_combo.py` "+ CR-0032 four (r30)" result on
      EC2 (user runs; output in the evidence directory) meets the Why-now
      bar; approval lapses if it does not (the CR is then revised).
- [ ] 2. After CR-0033 lands: `generate_canopy_structure.py`, `models.py`
      constants/encoders/`FEATURE_SPEC`, `RASTER_FEATURES`; all suites pass.
- [ ] 3. EC2 pilot, runtime estimate, full generation, gate passes (user
      runs; outputs committed to the evidence directory).
- [ ] 4. Evaluation (3 + 3 runs) and the keep/remove decision recorded.
- [ ] 5. Bookkeeping: `ARCHITECTURE.md` (pipeline step 2), `CHANGELOG.md`,
      tracker entries for every MEDIUM/LOW concern; close-out.

## Out of scope
- Airborne lidar (USGS 3DEP); LCMS/Hansen disturbance layers.
- Neighbourhood (100 m) versions and a height-sd layer (unless 1b says
  otherwise).
- Batch `Export.image` to Cloud Storage (revisit if the pilot estimate
  exceeds 24 h for all regions).
- Re-running the `diagnose_*` scripts after registration.
- Dropping or replacing existing features; retraining policy (CR-0020).
