# CR-0036: 3DEP lidar forest-structure generator (code, acceptance and NH pilot)

**Status: DRAFT v2, 2026-10-05.** Revised after review round 1, in which both reviewers returned REVISE. Verdicts and dispositions are in `CR-0036-review-log.md`. This document states only current intent.

## Scope
Add a generator that turns USGS 3DEP airborne-lidar point clouds into 30 m understory and canopy-structure layers on each region's template grid. Each point is binned directly into a template cell, with no warp and no Earth Engine. This CR delivers the generator, its pinned source table, its acceptance checks and an NH pilot of three windows. Pilot outputs are written outside `data/`.

The full ME/NH/VT build, the registry entries and the keep/remove evaluation are CR-0037.

## Why now
- **The gap.** Grouse select dense understory and stems in the 0.5–5 m layer, and no current layer measures it. The lidar research (`evidence/CR-0036/ROUTE.md` §3) found that no ready-made product supplies understory return density for these states.
- **Why the earlier attempt failed.** The earlier 3DEP attempt was reverted because Earth Engine exports were too slow (`CHANGELOG.md`, "LiDAR/3DEP terrain features — added then removed"). This design does not use Earth Engine.
- **Request.** The owner asked for this on 2026-10-05.

## Sources (evidence: `evidence/CR-0036/ROUTE.md`, `BANDWIDTH.md`, `WESM.csv`)
- **USGS 3DEP Entwine Point Tiles (EPT).** These are at `s3://usgs-lidar-public/<name>/ept.json`, in us-west-2. The bucket is public. Points are in EPSG:3857, with Z in metres.
- **3DEP LAZ tiles on rockyweb.** These cover projects not in EPT, and each project's `.vpc` tile index lists its tiles. They are stored in **native CRSs**, for example UTM 19N (EPSG:6348) and VT State Plane (EPSG:6589), and some sources are in **US survey feet**.
- **USGS WESM** gives each work unit's collection dates, `horiz_crs`, `vert_crs` and footprint polygon.
- **Pinned source table: `lidar_sources.csv`.** It has one row per work unit covering ME, NH or VT, with these columns:
  - WESM work unit;
  - read location (EPT name or rockyweb path);
  - `reader` (`ept` | `las`);
  - horizontal CRS (EPSG);
  - XY unit factor to metres;
  - Z unit factor to metres;
  - collection start and end dates;
  - leaf-risk flag (set if the collection window overlaps 15 May – 15 October);
  - the pinned PROJ pipeline string from the source CRS to the template CRS.

  The table is produced by the committed script `build_lidar_sources.py` from a pinned WESM snapshot (sha256 recorded) and the source headers. It is committed and reviewed under PA-0048. The generator refuses any source whose header CRS or units differ from its row.

## The change

### 1. `generate_lidar_structure.py` (new)

1. **Cell assignment.** Each template cell is assigned to the newest work unit in `lidar_sources.csv` whose WESM footprint contains the cell centre. Newest means the latest `collect_end`. A cell with no covering work unit is NODATA and counted. Assignment is per cell, never per block. The assignment is written to the metadata raster (§3).
2. **Blocks.** The template is processed in blocks of `LIDAR_BLOCK_CELLS` = 64 × 64 cells (1.92 km). At QL1 density that is about 80 M points.
   - For each block, every work unit assigned to any of its cells is read over the block's footprint plus a pad of `LIDAR_PAD_M` = 60 m.
   - EPT is read with `readers.ept` (`requests` = 8, no `resolution`).
   - LAZ tiles are processed tile-major: each tile is downloaded once to local scratch, all blocks that touch it are completed, and the tile is then deleted.
3. **PDAL reads only.** No PDAL filter or HAG stage is used. Points are kept if they are not withheld (`Withheld` == 0 where that dimension exists, else bit 3 of `ClassFlags` clear) and their `Classification` ∉ {6, 7, 13, 14, 15, 16, 17, 18}. A source lacking `ReturnNumber` is refused.
4. **Coordinates.** Each source has a pinned pipeline in the table, built with `pyproj.Transformer.from_pipeline`. That pipeline transforms each point's XY from its source CRS to the template CRS, and Z is multiplied by the table's Z factor. Distances and heights from then on are in template metres.
5. **Height above ground (numpy/scipy, pinned).** Ground points are those with class 2.
   - For each other point, ground height is the inverse-distance-squared mean over the `LIDAR_HAG_K` = 6 nearest ground points within `LIDAR_HAG_MAXDIST_M` = 30 m in XY, found with `scipy.spatial.cKDTree`.
   - HAG = Z − ground height. A point with no ground within the distance gets no HAG and is counted.
   - Because `LIDAR_HAG_MAXDIST_M` ≤ `LIDAR_PAD_M`, every ground point that can influence an in-block point is in the padded read. **Block seams are therefore exact.**
   - Points with HAG < −2 m or > `LIDAR_HAG_MAX_M` = 80 m are dropped as noise and counted.
6. **Binning.** With template transform `T`, a point at template coordinates (x, y) goes to cell `col = floor(u)`, `row = floor(v)`, where `(u, v) = ~T · (x, y)`. That is, cells are half-open on the template's pixel edges. A point counts only toward its own cell, and only if that cell is assigned to the point's work unit. There is no intermediate raster, and no `reproject`, `WarpedVRT`, `writers.gdal` or thinning filter (§5 lint).
7. **Features per cell.** Encoding is int16, nodata −9999. "Returns" means kept points with a valid HAG. `n(a,b)` is the count with a ≤ HAG < b.

   | Feature | Definition | Encoding |
   |---|---|---|
   | `lid_u05_2` | n(0.5,2) / n(−2,2) | per mille |
   | `lid_u1_3` | n(1,3) / n(−2,3) | per mille |
   | `lid_u3_5` | n(3,5) / n(−2,5) | per mille |
   | `lid_u5_10` | n(5,10) / n(−2,10) | per mille |
   | `lid_p95` | 95th percentile (`numpy.percentile`, method `linear`) of HAG over returns with HAG ≥ 0.5; 0 if fewer than 5 such returns | decimetres |
   | `lid_wcov5` | first returns with HAG > 5 / all first returns. Leaf-off, this measures woody and conifer cover, not canopy closure. | per mille |
   | `lid_sd` | population SD (ddof 0) of HAG over returns with HAG ≥ 0.5; 0 if fewer than 5 such returns | decimetres |

   - The `lid_u*` fractions are occlusion-adjusted: the share of the returns that reached that height layer.
   - A ratio feature is NODATA where its denominator is below `LIDAR_MIN_DENOM` = 20.
   - Every feature is NODATA where the cell has fewer than `LIDAR_MIN_RETURNS` = 50 returns.
   - Encoders refuse out-of-range values. They raise, following the `mch_*` precedent and PA-0034, and never clip.
8. **Resume.** Each finished block is cached under a key that hashes all of:
   - the template grid (CRS, transform, shape);
   - the `lidar_sources.csv` sha256;
   - the recipe constants;
   - the work units read.

   A change in any of these invalidates the cache.
9. **Assembly.** Staged `.tmp` files are written with windowed writes, `grid_mismatch(out, template) is None` is asserted, and the files are moved into place with `os.replace`.

### 2. Year policy: a static layer with two masks
Most acquisitions are far from the 2016–2025 vintages:
- VT: 2023.
- NH: 2015–2019, plus 2024 gaps.
- ME: 2016–2024.

The layers are therefore static (the `road_dist`/`mch_*` precedent): one acquisition, written for every vintage Y of the region. Two masks apply.

**Mask A, disturbance between flight and vintage.**
- `A` is the cell's acquisition year: the year of the median `GpsTime` of its returns, so a multi-year project is resolved per cell.
- Let `M = max(Y, A)`. The disturbance year is `D = M − round(tsd_decode(tsd_M))`.
- The cell is NODATA in vintage Y when `min(Y, A) ≤ D ≤ max(Y, A)`.
- A cell at the undisturbed cap (`TSD_MAX_YEARS`) is never masked.
- A cell where `tsd_M` is nodata is masked.

Using `tsd_M` covers both directions: vintages after the flight, and vintages before it. Disturbances after 2024 are invisible, because the LANDFIRE disturbance record ends in 2024.

**Mask B, regrowth in young stands.** The cell is NODATA in vintage Y when both:
- `|Y − A| > YEAR_MATCH_TOLERANCE`, and
- `tsd_A` records a disturbance within `LIDAR_REGEN_YEARS` = 20 years before A.

Young regenerating stands change too fast for a stale measurement.

Both masks remove grouse-relevant cells where the lidar is old. CR-0037 must report its evaluation within `|Y − A| ≤ 2` as well as overall.

### 3. Metadata raster (not a model feature)
- Path: `{R}_lidar_meta.tif`.
- Bands, all int32:
  1. acquisition year `A`;
  2. median acquisition day of year;
  3. return count;
  4. ground-return count;
  5. no-HAG point count;
  6. work-unit index.
- A `GROUSE_LIDAR_SOURCES` tag holds the source table's sha256 and the index-to-work-unit mapping.

In this CR the raster is written only for pilot windows, outside `data/`. Its `PATH_TEMPLATES` entry is CR-0037.

### 4. Encoders
`lidar_share_encode` and `lidar_height_encode` live in the generator for this CR. CR-0037 moves them, the features, `FEATURE_SPEC`, `RASTER_FEATURES` and `STATIC_FEATURES` into the shared registries, together with the `test_cr0032.py:163` update.

### 5. Acceptance checks (committed with this draft, CR-0011 A3)
The gate script `check_lidar_structure.py` owns every threshold as a constant. Each GATE has a **negative control** that must fail (PA-0021(a)). `--self-test` runs the controls on synthetic data, and the pilot gate passes only if every real check passes and every control fails.

| Check | Type | Real input | Negative control (must fail) |
|---|---|---|---|
| C1 grid | GATE | `grid_mismatch(out, template) is None` | transform offset by half a cell |
| C2 registration | GATE | Road sweep (the `diagnose_layer_registration` method) reading the pilot file, ≥ `MIN_WINDOWS` = 8 windows of 128 cells, for `lid_wcov5` and `lid_p95`. The peak must be at (0, 0). | layer shifted 1 cell |
| C3 height scale | GATE | Median of `lid_p95` ÷ LANDFIRE `ch` over forest cells (NLCD 41–43) where both are valid, within [`RATIO_LO`, `RATIO_HI`] = [0.5, 2.0]. Run per work unit. | `lid_p95` × 3.2808 (feet error) |
| C4 understory contrast | GATE | Median `lid_u1_3` in regenerating forest (`tsd` 3–15 years) minus median in mature forest (undisturbed cap and `cc` ≥ 60%) ≥ `MIN_REGEN_CONTRAST` = 50 per mille | `lid_u1_3` permuted across cells |
| C5 coverage | GATE | Per work unit: valid share of assigned forest cells ≥ 0.99 | one work unit's points dropped |
| C6 seam | GATE (EC2) | Window W2 assembled from 64-cell blocks equals the same area computed as one 128-cell block, bit for bit | `LIDAR_HAG_MAXDIST_M` set above `LIDAR_PAD_M` |
| C7 project offset | OBS | Per-work-unit medians of every feature on matched forest cells either side of a project boundary in W2 | — |
| C8 throughput | OBS | Points/s per core, bytes read, rockyweb MB/s at 8 and 32 streams, a `usgs-lidar` requester-pays listing | — |

`tests/test_cr0036.py` covers:
- the gate script's controls on synthetic rasters;
- the generator's pure functions, with brute-force oracles for:
  - binning, including points exactly on edges;
  - each metric, including empty and below-threshold denominators;
  - HAG, including a slope, no ground within range, and a water case;
  - seam exactness;
  - both masks, for Y < A, Y = A and Y > A, the cap, and tsd nodata;
  - CRS and units, with a feet source and a UTM source;
  - encoder refusals;
- the lint.

Tests of the generator's functions skip until deliverable 2 lands. Deliverable 2 removes the skip, so they cannot pass vacuously after it.

### 6. NH pilot (after approval; outputs under `/tmp/lidar_pilot/`)
- **W1.** 20 × 20 km centred on Pawtuckaway State Park (−71.17, 43.08). It is mostly `NH_Coastal_1_2019` (EPT, QL1, leaf-off) and yields about 25 registration windows. It provides C1–C5.
- **W2.** 128 × 128 cells (3.84 km). It is chosen by `--pilot-seam` from the source table as the NH block whose assigned cells are split most evenly between an EPT work unit and a rockyweb one. It provides C3, C5, C6 and C7 across both readers and CRSs.
- **W3.** 128 × 128 cells for steep terrain, centred on the first covered candidate: Crawford Notch (−71.40, 44.20), Franconia Notch (−71.68, 44.15) or Pinkham Notch (−71.25, 44.26). The candidate list is pinned in the script. It provides C3–C5.
- **Expected cost.** About 12 G points, 1–3 h on 16 cores in us-east-2, about $2 in cross-region transfer. The pilot sets the CR-0037 compute plan.

## Impact
- **New dependency.** PDAL ≥ 2.6 and python-pdal (conda-forge, pinned in `envs/lidar.yml`), used only by the generator for reading. HAG and metrics need only numpy and scipy, which are already present.
- **No change** to `data/`, the split, `models.py`, the registries or any model.
- **Numbering.** `HYBRID_REPORT.md` §5 provisionally numbered its CRs from CR-0036. Those are not yet drafted and will take the next free numbers. Lidar is not in that plan's v1; CR-0037 decides lidar's role.
- **CR-0038 source-year gate.** Lidar's source year is the per-cell `A` in the metadata raster.

## Risk
**Medium.** Mitigations:

| Risk | Mitigation |
|---|---|
| CRS and unit errors | Pinned per-source pipelines, header check, C3 per work unit, C5 per work unit, W2 spans both readers |
| Registration | Edge binning plus C1 and C2, each with a control |
| Leaf state, density and year offsets between projects | Per-cell `A` and day-of-year in metadata, C7, leaf-risk flag; CR-0037 must evaluate within project |
| Steep-terrain HAG | IDW of k = 6 within 30 m; W3 |
| Memory | 64-cell blocks |
| Snow on early-spring flights | Tracked to CR-0037 QA |

## Test plan
- **Here:** `tests/test_cr0036.py` (controls, oracles, lint), `check_lidar_structure.py --self-test`, all existing suites.
- **On EC2 (owner):** the pilot, then `check_lidar_structure.py --pilot /tmp/lidar_pilot`. Outputs are committed to `evidence/CR-0036/`.
- **Cannot be validated here:** real point clouds, S3 and rockyweb throughput, real leaf state per flight.

## Deliverables
- [ ] 1. This CR, the review log, `check_lidar_structure.py`, `tests/test_cr0036.py`; reviews; approval.
- [ ] 2. `build_lidar_sources.py`, `lidar_sources.csv` (pinned WESM sha256), `generate_lidar_structure.py`, `envs/lidar.yml`; skip guards removed; all suites pass.
- [ ] 3. NH pilot on EC2; the C1–C6 gates and every control pass as specified; evidence committed (including `wesm_summary.txt` and `newest_points.txt`).
- [ ] 4. Bookkeeping: `ARCHITECTURE.md`, `CHANGELOG.md`, tracker rows (CR-0037 must evaluate within work unit and within `|Y − A| ≤ 2`); CR-0037 drafted with the measured throughput.

## Out of scope
- **CR-0037:** the full build; registry, `PATH_TEMPLATES` and `models.py` entries; 100 m neighbourhood layers; per-project normalisation; snow QA; the keep/remove evaluation.
- **Other data and corrections:** 3DEP terrain (DEM) features; state nDSM, NAIP-CHM and ORNL products; LCMS 2025 disturbance (tracked).
