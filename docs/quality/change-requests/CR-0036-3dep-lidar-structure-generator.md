# CR-0036: 3DEP lidar forest-structure generator (code, acceptance and NH pilot)

**Status: DRAFT v1, 2026-10-05.** Not yet reviewed or approved. Verdicts and dispositions will be recorded in `CR-0036-review-log.md`. This document states only current intent.

## Scope
Add a generator that turns USGS 3DEP airborne-lidar point clouds into 30 m understory and canopy-structure layers on each region's template grid. Each point is binned directly into a template cell, so there is no warp and no Earth Engine step. This CR delivers the generator, its acceptance checks and a one-window NH pilot written outside `data/`. The full ME/NH/VT build and the keep/remove evaluation follow as CR-0037.

## Why now
- **The structural gap.** Grouse select dense 0.5–5 m understory and stem density. No current layer measures it: LANDFIRE `ch`/`cc`/`evh` and TreeMap carry it coarsely, Meta `mch_*` (CR-0032) is imagery-derived, and GEDI added +0.000 AUC (`diagnose_lidar_features.py`). The research report (`evidence/CR-0036/ROUTE.md` §3) found that no ready-made product supplies understory return density for these states.
- **Why the earlier attempt failed.** The earlier 3DEP attempt was reverted because Earth Engine exports were too slow (`CHANGELOG.md`, "LiDAR/3DEP terrain features — added then removed"). This design does not use Earth Engine.
- **Owner request:** 2026-10-05.

## Sources (evidence: `evidence/CR-0036/ROUTE.md`, `evidence/CR-0036/BANDWIDTH.md`)
- **USGS 3DEP Entwine Point Tiles (EPT)** at `s3://usgs-lidar-public/<project>/ept.json`, in AWS us-west-2. The bucket is public. Points are stored in EPSG:3857, and class 2 is ground.
- **3DEP projects not in EPT** are read as LAZ tiles from USGS rockyweb, located through each project's `.vpc` tile index. The projects are `ME_WesternMtns_1_B24`, `ME_CrownofMaine_B1_2018`, `ME_Eastern_B1/B2_2017`, `VT_Statewide_3_A23` and `NY_NHGaps_2_D24`. Rockyweb throughput from EC2 is **unverified**; the pilot measures it.
- **USGS WESM** (`WESM.gpkg`/`WESM.csv`) supplies project footprints, collection dates and quality level.
- **Which project fills each cell:** the newest acquisition covering the cell. Volume is about 1.65–2.0 T points (about 11–13 TB streamed); nothing is cached.

## The change

### 1. `generate_lidar_structure.py` (new)
1. **Blocks.** Each region's template (its latest EVT clip, the same template as `generate_canopy_structure.py`) is split into blocks of 256 × 256 cells. Each block is assigned its newest covering project from WESM. A cell on a project boundary is assigned to exactly one project, the newest that covers the cell centre. The project assignment is written to the metadata raster (§3).
2. **Reading.** A block is read from the 3857 bounding box of its template footprint, padded by 90 m.
   - EPT projects use PDAL `readers.ept` with `requests` = 16. Rockyweb projects use `readers.las` on the intersecting tiles.
   - `resolution` thinning is never used, because it biases the return-fraction metrics (`ROUTE.md` §2).
   - A block whose point count exceeds `LIDAR_MAX_BLOCK_POINTS` is split into four sub-blocks, recursively, to bound memory.
3. **Filtering and height.**
   - `filters.range` with `Classification[0:6],Classification[8:17]` drops noise (7, 18), class 20 and withheld points.
   - Height above ground comes from `filters.hag_nn`. Both the filter and the HAG method are pinned as module constants.
4. **Binning onto the template.** Each point's (X, Y) is transformed from EPSG:3857 to the template CRS with one pinned `pyproj.Transformer(always_xy=True)`, an exact per-point transform.
   - The cell is `col = floor(u)`, `row = floor(v)` with `(u, v) = ~T · (x, y)`, where `T` is the template transform. Cells are half-open on the template's own pixel edges.
   - Points of the 90 m pad that fall outside the block are dropped after HAG, so the HAG triangulation sees ground beyond the block edge while each cell's value comes only from its own points. Block seams are therefore exact.
   - There is no intermediate raster and no `reproject`, `WarpedVRT` or `writers.gdal` call (§5 lint).
   - The output uses exactly `T`, so `grid_mismatch(out, template)` is `None` by construction.
   - The PROJ pipeline description is recorded in the tags (`GROUSE_PROJ`).
5. **Metrics per cell.** All are computed with `np.bincount` and an `np.lexsort` by (cell, HAG). "Returns" means all returns after filtering; HAG is in metres.

   | Feature | Definition | Encoding (int16, nodata −9999) |
   |---|---|---|
   | `lid_f05_5` | share of returns with 0.5 ≤ HAG < 5 | per mille |
   | `lid_f1_3` | share of returns with 1 ≤ HAG < 3 | per mille |
   | `lid_u1_3` | occlusion-adjusted understory: n(1 ≤ HAG < 3) / n(HAG < 3) | per mille |
   | `lid_p95` | 95th percentile of HAG over returns with HAG ≥ 0.5 (0 if none) | decimetres, clipped to [0, 600] |
   | `lid_cov5` | first returns with HAG > 5 / all first returns | per mille |
   | `lid_sd` | standard deviation of HAG over returns with HAG ≥ 0.5 (0 if fewer than 2) | decimetres |

   The 100 m neighbourhood versions are out of scope (CR-0037).
6. **Nodata.** A cell is NODATA in every feature when either:
   - it has fewer than `LIDAR_MIN_RETURNS` returns (default 50), or
   - it has no ground return within the block.

   Cells outside any 3DEP footprint are also NODATA, and the share is reported as `GROUSE_COVERAGE`.
7. **Resume.** Each finished block is written to a per-block cache file under a key of (region, block, project, recipe). An interrupted or spot-terminated run redoes only the missing blocks.
8. **Assembly.** Blocks are assembled into staged `.tmp` files with windowed writes. A region is refused, with existing files left untouched, if fewer than 1% of template-valid cells are valid or if `grid_mismatch` is not `None`. Outputs are written with `os.replace`.

### 2. Year policy: static layer, stale-cell mask
- **Why static.** Lidar acquisition years are VT 2023, NH 2015–2019 (plus 2024 gaps) and ME 2016–2024. Most fall outside ±2 years (`YEAR_MATCH_TOLERANCE`) of the 2020–2025 vintages. A per-vintage policy would therefore drop most records.
- **The policy.** Following the `road_dist` and `mch_*` precedent (`STATIC_FEATURES` in `generate_canopy_structure.py`), the layers are written for every vintage year Y of the region's other features.
- **Stale-cell mask.** The copies differ in one way: in vintage Y, a cell is NODATA when the `tsd` raster for Y records a disturbance after the cell's acquisition year. The disturbance year is `Y − tsd_decode(tsd_Y)`. A cell at the undisturbed cap (`TSD_MAX_YEARS`) is never masked.
- **Residual risk.** Disturbances after 2024 are invisible, because the LANDFIRE disturbance record ends in 2024 (evidence `CR-0035/step2_redownload_and_inventory.txt`).

### 3. Metadata raster (not a model feature)
`data/landfire/{R}_lidar_meta.tif`, int16, with these bands:
1. acquisition year;
2. return count, capped at 32767;
3. ground-return count;
4. project index, keyed by a `GROUSE_LIDAR_PROJECTS` tag that lists the WESM project ids.

It is used by the stale mask, by QA and by CR-0037's per-project checks. It is not in `RASTER_FEATURES`.

### 4. `models.py`
- Add the six features to `FEATURE_SPEC` (continuous; scales 1000 for the shares, 600 for `lid_p95`, 200 for `lid_sd`), to `RASTER_FEATURES` and to the static-feature list.
- Add encoders `lidar_share_encode` and `lidar_height_encode`, which raise on non-finite input, following `mch_*_encode`.
- No training input changes until rasters exist on disk: `train.py` discovers features from disk, and `SPLIT_WINDOW_FEATURES` is pinned (CR-0033).

### 5. Acceptance checks (written before approval, CR-0011 A3)
**`tests/test_cr0036.py`** uses synthetic point arrays and a synthetic rotated template, with no network. It covers:
1. **Binning.** Points on cell edges go to the higher cell (half-open), and a rotated-template case is included. Every point's cell is checked against brute-force polygon containment.
2. **Metric correctness.** Each metric is checked against a brute-force per-cell computation. This includes `lid_u1_3` with an empty denominator and `lid_p95` against `np.percentile` (method pinned).
3. **Seam exactness.** A block computed whole equals the same block computed as four sub-blocks, bit for bit.
4. **Nodata.** The thresholds apply (returns < 50, no ground), and coverage is reported.
5. **Stale mask.** A synthetic `tsd` stack in which the disturbance year is before, equal to and after the acquisition year, plus the undisturbed cap.
6. **Encoders.** Encoders raise on NaN or inf, and their output stays within the int16 range.
7. **Lint.** `generate_lidar_structure.py` contains no `reproject(`, `WarpedVRT`, `writers.gdal`, `"resolution"` or `calculate_default_transform`.
8. **Resume.** The cache key changes when the recipe constants change.

**`check_lidar_structure.py`** is the pilot and region gate. It owns its thresholds as constants. It checks:
- (a) `grid_mismatch(out, template)` is `None`.
- (b) Content registration (PA-0049(b)). `diagnose_layer_registration`'s road sweep must peak at (0, 0) for `lid_cov5` and `lid_p95`.
- (c) Plausibility. On forest cells (EVT forest classes), the Spearman correlation between `lid_p95` and LANDFIRE `ch` is ≥ `MIN_RHO_CH` = 0.5, and with `mch_mean` if that layer is on disk.
- (d) Under 1% of forest cells fall below the return threshold, within the footprint.
- (e) Points/s, wall-clock time and bytes read are logged. The full-run estimate is derived from them.

### 6. NH pilot (after approval; writes outside `data/`)
- **Window.** A 10 × 10 km window (334 × 334 cells) at Pawtuckaway State Park (−71.17, 43.08). It lies entirely in `NH_Coastal_1_2019`, which is QL1, about 22 points/m² and leaf-off. That is about 2.2 G points, or about 15 GB read.
- **Output.** `--dry-run --pilot-out /tmp/lidar_pilot_NH.tif`.
- **Where to run.** Either the us-east-2 host or a us-west-2 instance. Reading from us-west-2 into us-east-2 costs about $0.30 for the pilot.
- **Pass criteria.** `check_lidar_structure.py --pilot` exits 0.
- **Rockyweb throughput.** The pilot also downloads one rockyweb tile of `ME_WesternMtns_1_B24` and logs its throughput.

## Impact
- **New dependency.** PDAL ≥ 2.6 and python-pdal, from conda-forge. It is imported lazily inside the generator only, so `train.py`, `predict.py` and the test suite do not need it; tests that need PDAL skip without it.
- **No change to `data/`, the split or any model in this CR.** CR-0037 decides whether the layers enter training. A new feature is a geometry change and needs a cold start.
- **CR-0032 interaction.** CR-0032 (`mch_*`) remains as approved. CR-0037 evaluates lidar alone, `mch_*` alone and both together against the CR-0035 "after" baseline.

## Risk
**Medium.** Mitigations:

| Risk | Mitigation |
|---|---|
| Registration | Binning on template pixel edges with an exact per-point transform; the §5 lint; checks (a) and (b) |
| Leaf-on projects (`NY_NHGaps_2_D24`, `ME_CrownofMaine_2018`, `ME_Eastern_2017`, `ME_SouthCoastal_2020`) | The pilot uses a leaf-off project. The project index is carried in metadata. CR-0037 runs per-project distribution QA and decides exclusion or normalisation. |
| Mixed point density (QL1 ≈ 22–33 pts/m², legacy ≈ 1) | Fractions and p95 rather than counts and max. Return-count threshold. |
| Memory: dense tiles reach about 81 M points | Recursive block split (`LIDAR_MAX_BLOCK_POINTS`) |
| Cost and time of the full build | Estimated at about 7 h and $12–50 on a spot c7a.48xlarge in us-west-2 (`BANDWIDTH.md`). Budgeted in CR-0037. |
| Datum | Under 2 m between EPSG:3857/WGS84 and NAD83. The pipeline is pinned and recorded in `GROUSE_PROJ`. |

## Test plan
**Here:** `tests/test_cr0036.py`, the lint and all existing suites. PDAL tests skip if PDAL is unavailable.

**On EC2 (owner):** install the conda environment, run the pilot, then `check_lidar_structure.py --pilot`. Commit the outputs to `evidence/CR-0036/`.

**Cannot be validated here:** real point clouds, S3 and rockyweb throughput, PDAL HAG behaviour on steep terrain, and leaf condition per flight.

## Deliverables
- [ ] 1. This CR, the review log, `tests/test_cr0036.py`, `check_lidar_structure.py`; two independent reviews; approval.
- [ ] 2. `generate_lidar_structure.py`, `models.py` additions; all suites pass.
- [ ] 3. NH pilot on EC2; `check_lidar_structure.py --pilot` exits 0; evidence committed.
- [ ] 4. Bookkeeping: `ARCHITECTURE.md` (pipeline step 2 note), `CHANGELOG.md`, tracker; CR-0037 drafted with the measured throughput.

## Out of scope
- **CR-0037:** the full ME/NH/VT build, the 100 m neighbourhood layers, per-project leaf-condition QA and normalisation, and the keep/remove evaluation.
- **Other data:** 3DEP terrain (DEM) features; state nDSM, NAIP-CHM and ORNL products.
- **Disturbance after 2024:** detecting it, for example with LCMS 2025 (tracked).
