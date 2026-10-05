# Lidar forest structure for ME/NH/VT at 30 m: route assessment

2026-10-05. Research only. No repository file was changed.
Working files are in this directory: `wesm_summary.txt`, `newest_points.txt`, `resources.geojson`, `wesm_nne.gpkg` and `nodes/`.

**Bottom line.** No ready-made product supplies understory (0.5–5 m) return density for these states. The only route that delivers every target metric is to process 3DEP point clouds directly. Done well, that takes about **2–5 days of wall-clock time on one 8–16-core EC2 host**. It streams roughly **12 TB**, stores **under 0.5 TB**, and needs no Earth Engine.

Coverage differs by state:
- **NH:** 97% of the state is in Entwine Point Tiles (EPT), the fast path.
- **VT:** 2/3 of the 2023 statewide collection is in EPT.
- **ME:** only about half the state is in EPT. The rest must come as LAZ tiles from USGS rockyweb, which is slow.

The current repository already lists this work as the remaining gap. CR-0032 records that GEDI added +0.000 AUC and Meta canopy height added about +0.009. `docs/grouse_model_report.md` (line 178) names partial harvests that hide a dense understory as the case that needs leaf-off lidar. Only the point-cloud route can measure that case.

---

## 1. Routes, ranked by fitness for the target metrics

Throughput figures:
- **Measured:** single-thread LAZ decode ran at 1.6 M points/s, using `lazrs` on EPT nodes in this sandbox.
- **Assumed:** about 0.5–0.8 M points/s per core end to end, after the read, height normalisation (HAG), reprojection and binning. This is an estimate and has **not been verified**. The pilot (§6) measures it.

| # | Route | Metrics supplied | Years in ME/NH/VT | Wall-clock time, 3 states | Disk |
|---|---|---|---|---|---|
| **A** | **3DEP point clouds → per-cell metrics on the template lattice** (EPT on AWS, plus rockyweb LAZ for the gaps) | **All**: 0.5–5 m and 1–3 m return fractions, p95/max height, cover above 5 m, height SD/CV, return counts, acquisition year | 2015–2024. 2023 for 2/3 of VT; 2019 and 2015 in NH; 2017–2024 in ME | 16 cores: ~36–60 h of compute. 8 cores: ~75–115 h. Plus the rockyweb transfer of about 3 TB at an **unverified** rate, overlapped with compute. **Total about 2–5 days.** NH alone: ~5–14 h. | No point storage when streaming. Rockyweb tiles are processed then deleted: 50–100 GB scratch. Output under 5 GB. |
| B | State nDSM/CHM rasters, aggregated exactly. VT has a 2023 35 cm nDSM; NH has a 2 m nDSM composite (to 2020); **ME has none** | Top surface only: max/p95 height, cover above 5 m, height SD, share of top surface in 0.5–5 m. **No understory below the canopy.** | VT 2023; NH 2011–2019 mosaic; ME none | VT ~1–3 h (520 GB COG streamed). NH ~2–8 h through the image service (**unverified**). ME needs route A or C anyway. | VT streamed; NH ~25 GB |
| C | NAIP-CHM 0.6 m (Morford et al. 2026; NAIP imagery mapped to 3DEP-trained heights), aggregated exactly | Top surface only, and it is **not lidar**. Same family as the Meta `mch_*` layers already in use, so likely redundant. | NAIP 2021–2023 | ~0.5–1 day | ~430 GB, scaled from 24.82 TB for CONUS (**unverified** for NNE) |
| D | ORNL DAAC 1854: 30 m canopy height and tree cover for New England | Height and cover only | Lidar 2010–2015 | Under 1 h (two files, 129 MB and 321 MB) | under 1 GB |
| E | Planetary Computer `3dep-lidar-hag` / `-returns` / `-dsm` (2 m COGs) | HAG is an **IDW of all-return HAG** (`output_type: idw`). That is not a canopy height model, and it carries no bins. | 2012–2022 snapshot only | Hours. Hosted in Azure West Europe. | — |
| F | Earth Engine catalog | None found: `USGS/3DEP/1m` and `10m` are DEMs only. NAIP-CHM is in EE as `projects/naip-chm/assets/conus-structure-model`. | — | Ruled out anyway (BUG-0094 / CR-0034) | — |

Why D, C and B rank below A even though they are faster:
- **D** is native 30 m on its own lattice. Putting it on the template is a nearest/bilinear resample: exactly the BUG-0094/0095 class of error, and impossible to make exact. Its years (2010–2015) fall outside ±2 of almost every vintage (2016–2025). Coverage gaps in northern Maine are likely (**unverified**).
- **C and B** cannot see under the canopy. Route B is not uniform across states, and Maine has nothing.
- **E** has the wrong statistic and stale years.

---

## 2. Recommended route: A, staged NH → VT → ME, behind a CR

### Data sources (all verified to exist)

- **EPT bucket:** `s3://usgs-lidar-public/<name>/ept.json` in us-west-2. Public, no requester-pays. Index: https://github.com/hobuinc/usgs-lidar (`boundaries/resources.geojson`). The live bucket prefixes match that index for ME/NH/VT.
  - Points are stored in EPSG:3857, LAS 1.2 format 1. They include `Classification` with class 2 ground (checked on `NH_Coastal_2_2019`, `VT_Statewide_1_A23` and `CT_River_Lot6`).
  - Size on disk: deep nodes measured 5.5–8.6 bytes/point; use about 7 B/pt.
- **Projects missing from EPT** must be read as LAZ tiles from rockyweb. Each project folder has a `0_file_download_links.txt` and a `.vpc` (STAC virtual point cloud) tile index.
  - Projects: `ME_WesternMtns_1_B24`, `ME_CrownofMaine_B1_2018`, `ME_Eastern_B1/B2_2017`, `VT_Statewide_3_A23`, `NY_NHGaps_2_D24`, plus `ME_Western_2016` for fallback only.
  - Base URL: https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/
  - The `prd-tnm` S3 bucket holds only `browse/`, `metadata/` and the link lists. The LAZ files themselves are on rockyweb.
  - Rockyweb measured **~170 KB/s per stream from this sandbox**. Speed from EC2 is **unverified**; use many parallel streams.
  - The `ME_WesternMtns` tiles are LAS 1.4 format 6, not COPC, at about 5 B/pt.
- **Footprints, dates and quality level:** USGS WESM, https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/WESM.gpkg (3.7 GB; read remotely with a bounding-box filter through `/vsicurl`) and `WESM.csv`.

### Point volume, newest acquisition wins (`newest_points.txt`)

| State | Total points | Not in EPT |
|---|---|---|
| ME | 761 G | 332 G |
| NH | 205 G | 13 G |
| VT | 687 G | 210 G |
| **Total** | **≈1.65 T points ≈ 11.6 TB** | |

VT can be cut by about 210 G points if the `VT_Statewide_3_A23` third uses the older EPT projects (2014–2017) instead of rockyweb. That trades year match for speed.

### Tools

- PDAL 2.6 or later with python-pdal, from conda-forge.
- Pipeline: `readers.ept` (with `bounds` in EPSG:3857 and `requests` 16–32), or `readers.las` for rockyweb tiles.
  - Then `filters.range` with `"Classification[0:6],Classification[8:17]"`. Ranges on the same dimension are ORed, so this drops noise classes 7 and 18, class 20, and withheld points (stored as 128 and above).
  - Then `filters.hag_nn`, or `filters.hag_delaunay` on steep terrain.
  - Then numpy aggregation in Python (§5).
- Do **not** use `writers.gdal` for the final output. It has no bin-fraction statistic, and its origin convention is not documented (`origin_x/origin_y` is described as "lower-left"). It would reintroduce a half-pixel risk.
- Docs: https://pdal.io/stages/readers.ept.html, https://pdal.io/stages/filters.hag_delaunay.html, https://pdal.io/stages/writers.gdal.html

### Execution

1. Split each region's template into blocks of 256×256 cells (7.68 km).
2. Assign each block to its newest covering project, using WESM footprints.
3. Run one process per block across all cores. Each block reads its 3857 bounding box plus a 60 m pad, so HAG triangulation has ground beyond the edges. Each cell gets its value only from points that fall inside it, so block seams are exact.
4. Cells cut by a project boundary are taken from the next project, or flagged.
5. Cache finished blocks by key so an interrupted run resumes, following the `generate_canopy_structure.py` pattern.

### Do not

- Do not thin with `readers.ept` `resolution`. EPT levels are 3D-voxel-thinned, which under-samples dense canopy relative to understory and biases every return-fraction metric.
- Do not cache the raw points.

---

## 3. Metrics each route can actually supply

All metrics are per 30 m cell. Encodings follow `mch_*`: int16, per mille or decimetres, nodata −9999.

| Metric | A (points) | B (nDSM) | C (NAIP-CHM) | D (ORNL) |
|---|---|---|---|---|
| f(0.5 ≤ HAG < 5 m), all returns | yes | top surface only | top surface only | no |
| f(1 ≤ HAG < 3 m), all returns | yes | top surface only | top surface only | no |
| Occlusion-adjusted understory: n(bin) / n(HAG < bin top) | yes | no | no | no |
| p95 / max height | yes | yes | yes, compressed about 10% at the tall end | height only |
| Cover above 5 m: first returns > 5 m / all first returns | yes | yes (pixel share) | yes (pixel share) | tree cover (different definition) |
| Height SD/CV (returns > 0.5 m), CHM rugosity | yes | yes | yes | no |
| Return and ground-return counts (QA), acquisition year, project ID | yes | year only | NAIP date | no |

Neighbourhood versions at 100 m (CR-0032 found the 100 m radius carried most of the gain) are computed afterwards from the 30 m layers, on the template.

---

## 4. Acquisition-year and leaf-condition caveats

The full table is in `wesm_summary.txt`, built from WESM collection dates. Rows marked "LEAF-ON RISK" are only flagged because their collection window spans June–September. **Per-flight leaf state was not verified.**

| State | Share of state by newest acquisition | Leaf condition |
|---|---|---|
| **VT** | 99% from `VT_Statewide_1/2/3_A23` (23 Mar – 13 May 2023, QL1) | Leaf-off |
| **NH** | 54% `NH_CT_River_North_L6` (Oct 2015 – Apr 2016, QL2); 24% `NH_Coastal_1/2_2019` (Nov 2019 – Apr 2020); 15% `NH_Umbagog_2016` (Apr 2016 – May 2018); 6% `NY_NHGaps_2_D24` | `NY_NHGaps_2_D24` was flown 21 May – 16 Jun 2024: **possible leaf-on** |
| **ME** | 16% `WesternMtns_B24` (Oct–Nov 2024); 10% `MidCentral_B23` (2023, QL1); 7% `SouthCentral_B22`; 8% `MidCoast_2021`; 7% `SouthCoastal_2020`; 20% `CrownofMaine_2018`; 25% `Eastern_2017`; 5% `Umbagog` 2016/17; 1.4% uncovered | See below |

Maine leaf-condition risks:
- `Eastern_2017` was flown 30 Apr – 4 Dec 2017: possibly partly leaf-on.
- `CrownofMaine_2018` was flown 12 May – 3 Jun 2018 (B1) and 13 May 2018 – 8 Jun 2019 (B2). Late May/June is near leaf-out in northern Maine.
- `SouthCoastal_2020` ran to 10 Jun.
- `MidCoast_2` ran from May 2021 to May 2022.

What this means for the model:
- **Year matching (`YEAR_MATCH_TOLERANCE = 2`, vintages 2016–2025).**
  - VT 2023 is within ±2 of 2021–2025.
  - NH 2015/16 is within ±2 only of 2016–2018.
  - ME 2017/18 is within ±2 only of 2016–2020.
  - Treating lidar as per-vintage would drop most records. The only workable policy is the CR-0032 / `road_dist` precedent: one static layer copied to every vintage, plus a `lidar_year` band. Disturbance after acquisition then needs handling, for example by masking cells where `tsd` shows a disturbance after `lidar_year`. **This is a policy decision for the CR.**
- **Leaf-off versus leaf-on.**
  - Leaf-off returns measure deciduous stems and branches and conifer foliage. That suits stem density, but **cover above 5 m in deciduous stands reads low**.
  - Mixed leaf states across projects add a project-level offset. Carry `project_id`, check per-project distributions in the pilot and in the full QA, and consider per-project normalisation.
  - Density also varies (QL1 ~22–33 points/m², QL2 ~6–8, legacy projects ~1). Fractions are density-robust; counts and max are not, so prefer p95 over max.

---

## 5. Placing results on the template grid without resampling

The template is each region's latest EVT clip, in an LFPS local Albers. It is rotated relative to UTM and EPSG:3857 (ARCHITECTURE.md:167; BUG-0095).

1. **Bin points, never warp rasters.** Read the template's `crs` and `transform` T. Transform each point's (X, Y) from EPSG:3857 straight into the template CRS with `pyproj` (an exact per-point transform, not GDAL's approximate warp transformer).
   - Then compute `col = floor((~T * (x, y))[0])` and `row = floor(...[1])`. Cells are half-open intervals on the template's own pixel edges.
   - Aggregate with `np.bincount` per cell, and get p95 from a `np.lexsort` by (cell, HAG).
   - There is no intermediate raster, no Earth Engine and no `reproject` call. The output is written with exactly T, and `grid_mismatch(out, template)` is `None` by construction.
2. **CHM-type metrics** (rugosity, or route B/C rasters) use the same rule. Each fine pixel's **centre** is transformed into the template CRS and assigned to the containing 30 m cell. Each 30 m cell then takes the mean/share over its fine pixels, the same zonal logic as the Meta layers but done locally.
3. **Datum.** EPT is in WGS84 Pseudo-Mercator, while the template is NAD83-based. PROJ may apply a ~1–2 m shift, or none (a ballpark transform). That is under 7% of a cell, but pin the PROJ pipeline (`Transformer.from_crs(..., always_xy=True)`) and record it in the tags.
4. **Content-registration check** (PA-0049 clause b, which BUG-0094 showed is needed). Run the shift-search used in `evidence/CR-0032/layer_registration_sweep.txt` on the new layer against TIGER roads (cover above 5 m drops on roads). The correlation peak must be at (0, 0) to within ±0.25 cell. Cross-check against NH GRANIT nDSM aggregated the same way, as an independent lidar reference.
5. **Tags.** Tag outputs with `GROUSE_SOURCE=<project ids>` and `GROUSE_GRID=template-binned`, with nodata where the return count is below a threshold (for example 50) or where lidar is absent (`GROUSE_COVERAGE`, as for the CR-0008 generators).

---

## 6. Pilot: NH, one hour or less on EC2

**Area.** 10 km × 10 km (334 × 334 template cells) centred on Pawtuckaway State Park, lon −71.17, lat 43.08.
- It lies 100% inside `NH_Coastal_1_2019`: QL1, ~22 points/m², leaf-off (Nov 2019 – Apr 2020). It also overlaps the 2011 legacy collection, which is ignored.
- Volume: about 2.2 G points, about 15 GB from us-west-2.
- If points/s is lower than expected, drop to 5 × 5 km.

**Steps.**

1. **Install (~5 min).** `conda create -n lidar -c conda-forge pdal python-pdal rasterio pyproj numpy`
2. **Script (~60 lines).** The sketch below follows the rules in §5; it is not committed code.
   ```python
   tpl = rasterio.open(rd.path("raster", year=2024, feature="evt")); T = tpl.transform
   x, y = Transformer.from_crs(4326, tpl.crs.to_wkt(), always_xy=True).transform(-71.17, 43.08)
   c, r = ~T * (x, y); c0, r0, W, H = int(c) - 167, int(r) - 167, 334, 334
   corners = [T * (c0 + i, r0 + j) for i in (0, W) for j in (0, H)]
   xs, ys = Transformer.from_crs(tpl.crs.to_wkt(), 3857, always_xy=True).transform(*zip(*corners))
   pad = 90  # ~60 m ground, x1.37 Mercator scale at 43N
   pipe = pdal.Pipeline(json.dumps([
     {"type": "readers.ept", "requests": 32,
      "filename": "https://s3-us-west-2.amazonaws.com/usgs-lidar-public/NH_Coastal_1_2019/ept.json",
      "bounds": f"([{min(xs)-pad},{max(xs)+pad}],[{min(ys)-pad},{max(ys)+pad}])"},
     {"type": "filters.range", "limits": "Classification[0:6],Classification[8:17]"},
     {"type": "filters.hag_nn"}]))
   pipe.execute(); a = pipe.arrays[0]
   X, Y = Transformer.from_crs(3857, tpl.crs.to_wkt(), always_xy=True).transform(a["X"], a["Y"])
   cc, rr = ~T * (X, Y); col = np.floor(cc).astype(int) - c0; row = np.floor(rr).astype(int) - r0
   # keep 0<=col<W, 0<=row<H; idx=row*W+col; bincount -> n, n_ground,
   #   f_05_5, f_1_3, occlusion-adjusted f_1_3, cover>5 (first returns), p95, sd, ...
   # write int16 with transform T * Affine.translation(c0, r0), crs = tpl.crs
   ```
   - For the speed figure, run with 8–16 worker processes on 64 × 64-cell sub-blocks.
3. **Checks and pass criteria.**
   - (a) `grid_mismatch(pilot, template)` is `None`.
   - (b) The road shift-search peaks at (0, 0).
   - (c) p95 against LANDFIRE `ch` and Meta `mch_mean` (Spearman ρ > 0.6, **threshold to be set by the CR's committed script**).
   - (d) Under 1% of forest cells below the return threshold.
   - (e) Wall-clock time and points/s logged. Points/s × cores sets the full-run estimate: about 1.65e12 / (points/s).
   - (f) Quick value test: sample the pilot cells at any training or validation points inside the window.

     Few points are expected inside a 100 km² window. The real gain test is NH-wide, about 5–14 h, through the `diagnose_lidar_features.py` pattern.

**Expected time.** Install 5 min, plus reading 15 GB at 2–10 min, plus compute for 2.2 G points at 4–8 M points/s on 8 cores (5–10 min), plus checks 5 min: **about 20–35 min**.

---

## Process notes (CLAUDE.md)

- The full build is a new generator, eleven or so new `RASTER_FEATURES`, and a year-policy question. It needs a CR, ideally split per CR-0011 A5 into (1) the generator and acceptance checks and (2) the data build and evaluation.
- Pilot scripts and acceptance checks may be committed on a branch before approval (A3). Nothing may be written to `data/` before approval.
- Relevant rules: PA-0049 and BUG-0094/0095 (no Earth Engine reprojection, exact transforms, content-registration check) and PA-0007 (half-pixel conventions).

## Unverified items

- End-to-end points/s per core: decode alone was measured at 1.6 M/s.
- Rockyweb throughput from EC2.
- Cost of S3 transfer from us-west-2 to the host's region; this is an AWS Open Data bucket.
- Leaf state of individual flights in the "LEAF-ON RISK" projects.
- ORNL 1854 coverage gaps in Maine.
- NH GRANIT image-service export speed.
- NAIP-CHM NNE volume.
- Whether NAIP-CHM's EE asset includes structure layers beyond height. The README lists height only.
- A Maine statewide CHM/nDSM: none found on Maine GeoLibrary/MEGIS, which serve DEMs only. This is absence of evidence, **unverified**.

## Sources

**3DEP point clouds and metadata**
- EPT bucket and index: https://s3-us-west-2.amazonaws.com/usgs-lidar-public/ · https://github.com/hobuinc/usgs-lidar
- WESM: https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/WESM.gpkg · https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/metadata/WESM.csv
- Rockyweb LAZ: https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/ME_WesternMtns_B24/ME_WesternMtns_1_B24/

**State products**
- VT: https://registry.opendata.aws/vt-opendata/ ; `https://vtopendata-prd.s3.us-east-2.amazonaws.com/Elevation/STATEWIDE_2023_35cm_NDSM.tif` (EPSG:6589, 0.35 m, LERC float32, 520 GB, public domain with attribution) ; https://vcgi.vermont.gov/data-and-programs/lidar-program
- NH: https://granit24a.sr.unh.edu/image/rest/services/ImageServices/nDSM_NH/ImageServer (2 m, EPSG:26919, first return minus DEM, 8 collections to Jan 2020, "cite NH GRANIT", export capped at 15000×4100 px)
- ME: https://gis.maine.gov/image/rest/services/DEM/Maine_Elevation_DEM_2024/ImageServer (DEM only)

**Other products**
- ORNL 1854: https://doi.org/10.3334/ORNLDAAC/1854 (NASA data policy; Earthdata login; 30 m; lidar 2010–2015)
- NAIP-CHM: https://rangeland.ntsg.umt.edu/data/naip-chm/ · https://pmc.ncbi.nlm.nih.gov/articles/PMC13493895/ (MIT/CC-BY; GCS requester-pays `gs://naip-chm-assets/`)
- Planetary Computer: https://planetarycomputer.microsoft.com/api/stac/v1/collections/3dep-lidar-hag

**PDAL**
- https://pdal.io/stages/readers.ept.html · https://pdal.io/stages/filters.hag_delaunay.html · https://pdal.io/stages/writers.gdal.html
