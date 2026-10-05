# CR-0034: Earth Engine downloads requested on each source's own grid

**Status: DRAFT v3, 2026-10-05** — round 2 approved v2 with follow-ups;
v3 applies them and adds §5 (BUG-0095, found in round 2); awaiting a
bounded re-review of §5. Verdicts and dispositions: `CR-0034-review-log.md`. This document states only current intent.

## Scope
`download_tcc_nlcd.py` and `download_treemap.py` request every tile on the
source image's own CRS and pixel lattice, so Earth Engine copies pixels
instead of resampling them; the single resampling step stays the local
nearest warp onto the region's template grid.

## Fixes
BUG-0094 (root cause confirmed: `evidence/CR-0032/source_lattice_NH.txt`)
and, on the same files, BUG-0095 (approximate warp transformer, §5).
The data repair that uses this code is CR-0035.

## Why now
Every Earth Engine layer on disk (`nlcd`, `tcc`, TreeMap `balive`,
`tpa_live`, `qmd`, `carbon_dwn`) is ~half a cell north-west of the template
grid in all three regions, against an Earth-Engine-free reference
(`evidence/CR-0032/layer_registration_sweep.txt`). The sources' pixel
edges sit at odd multiples of 15 m; `region_grid` snaps tiles to multiples
of 30 m in the same orientation, so each output centre lies on a source
pixel corner and nearest-neighbour takes the south-east pixel every time
(1,400 of 1,400 decisive cells). Six of fifteen training channels are
affected; CR-0032's canopy layers also wait on a registered NLCD.

## The change

### 1. Native grid of a source (`download_tcc_nlcd.py`)
- `parse_native_grid(info)`: from an Earth Engine `projection().getInfo()`
  dict, returns `{"crs": <EPSG code if given, else WKT>, "x0", "y0"}` (the
  lattice origin). Refuses (`ValueError`) unless the transform is
  north-up 30 m: `[30, 0, x0, 0, -30, y0]` within 1e-6 m.
- `common_native_grid(infos, what)`: the one grid shared by every source
  image a request touches; refuses an empty list, or images whose CRSs
  differ (compared semantically) or whose origins differ modulo 30 m.
- `year_native_grid(ee, cid, year, bounds_lonlat)`: the subset
  `year_image` mosaics, **filtered to the region's bounds padded by twice
  `region_grid`'s pad** (so every image a tile touches is included); the
  projections of **all** its images (`subset_projections`) go through
  `common_native_grid`. (A collection can hold images for several areas,
  e.g. TCC's study areas; the first image may be one that never touches
  the region.)
- `--collection <id>` pins the collection for one `--features` run (the
  default stays the first readable candidate); every file written is
  tagged `GROUSE_SOURCE="<collection id> <year>"` and
  `GROUSE_GRID=native-lattice`.

### 2. Tiles on that lattice
- `region_grid(bounds_lonlat, *, grid, pad_m=2000)`: `grid` is required.
  Bounds are transformed into `grid["crs"]` and snapped to
  `x0 + 30 k`, `y0 + 30 k` (padded as today).
- `fetch_tile(ee, image, rect, dest, *, crs, retries=4)`: `crs` is
  required; `params["crs"] = crs`, `crs_transform` as today on `rect`,
  `region = ee.Geometry.Rectangle(rect, ee.Projection(crs), False)`.
  Retry clause unchanged (BUG-0066).
- `tiles(...)`: steps in floats from the snapped origin (origins such as
  `3177435.0000000037` are kept, not truncated).
- `build_raster(...)`: gets `grid = year_native_grid(..., bounds_lonlat)`,
  builds tiles with it, merges as today, and **refuses**
  (`check_on_lattice`) unless the merged mosaic's origin lies on the
  source lattice: `r = (c - x0) % 30`, `min(r, 30 - r) <= 1e-6` (and the
  same for `f`). The merged temporary file carries `grid["crs"]`; the
  warp onto the template (`realign_rasters.warp_to_grid`, nearest) and
  every check after it are unchanged.

### 3. TreeMap (`download_treemap.py`)
- Its private copies of `region_grid`, `tiles` and `fetch_tile` are
  removed; it imports them from `download_tcc_nlcd` (the duplicate is how
  the defect landed twice; PA-0001 family).
- `vintage_native_grid(ee, vintage, bounds_lonlat)`: for a collection,
  every image intersecting the region through `common_native_grid`; for a
  single Image, its own grid. `main` computes it per (vintage, region) and
  passes `grid=` (a required keyword) and `source="<asset> <band>"` to
  `build_raster`, which uses the same lattice check and writes the raw
  file in `grid["crs"]` with the two tags.
- `generate_treemap_features.py` is unchanged (it already warps nearest
  onto the template from whatever CRS the raw file carries).

### 4. Callers
- `diagnose_fetch_tile_offset.py`, `diagnose_source_lattice.py` and
  `diagnose_grid_registration.py` keep reproducing the BUG-0094 route by
  passing an explicit 0-origin EPSG:5070 grid (`BUG0094_ZERO_GRID`),
  named as such. `diagnose_fetch_tile_offset.py` also gains `--native`:
  `ee.Image.pixelCoordinates` fetched on a source's native lattice
  (`year_native_grid`), reporting each centre's offset (CR-0035 pilot).
- `tests/test_cr0018_candidates.py` (BUG-0066 retry tests): passes
  `crs="EPSG:5070"` and gives its fake `ee` a `Projection`; its retry
  assertions are unchanged. Lands with this CR's code (deliverable 2), so
  the standing suite never goes red.

## Impact
- **No data changes in this CR.** Files on disk change only when CR-0035
  re-runs the downloads.
- **Callers:** `region_grid` and `fetch_tile` gain required keywords;
  every caller in the repository is updated (the two downloaders, three
  diagnostics, `test_cr0018_candidates`). `generate_canopy_structure.py` uses `year_image`,
  `mask_to_valid`, `PRODUCTS`, `template_raster`, `_fetch_all` only:
  unchanged.
- **Template-grid files** (`data/landfire/*_{nlcd,tcc,...}.tif`): same
  names, CRS (template), dtype and nodata as today, two new tags
  (`GROUSE_GRID`, `GROUSE_SOURCE`); the content moves ~half a cell
  (BUG-0094) and up to one cell where the approximate warp had swapped a
  pixel (BUG-0095).
- **Raw TreeMap files** (`data/treemap_raw/`): written in the source's
  native CRS and lattice (EPSG:5070 or the 2016 vintage's NAD83 Albers
  WKT), with the two tags; `generate_treemap_features` warps them as
  before.
- **Tile sizes:** unchanged defaults (`--tile-m` 96000 / 48000); the
  source lattice has the same pixel size.

### 5. Exact local warp (BUG-0095)
`realign_rasters.WARP_TOLERANCE_PX = 1e-6`, passed as `tolerance=` by
`warp_to_grid` and by `generate_treemap_features`' `WarpedVRT` (imported).
GDAL's default approximate transformer (0.125 px) sends ~7 % of nearest
picks to a neighbouring pixel on a 60 km rotated grid (BUG-0095 §3);
1e-6 px is exact in practice (`tolerance=0` with an explicit transform
fails in rasterio 1.5's `WarpedVRT`). `warp_to_grid` is also used by
`realign_rasters.py` for other files; exactness only removes error there.
The other warps in the repository are swept in BUG-0095 §8 (tracked).

## One change per CR (CR-0011 A5)
Code only (two downloaders, the shared warp, their diagnostics). §5 is in
this CR because it changes the same files CR-0035 re-creates: landing it
separately would force a second re-download. Data repair,
re-acceptance and the evaluation retrain are CR-0035.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A source's native CRS is a custom WKT Earth Engine will not accept back as `crs` | The CR-0032 pilot already used a WKT `crs` successfully; CR-0035's pilot re-downloads one tile per product before the full run |
| Native transform not north-up 30 m (e.g. a future product version) | `parse_native_grid` refuses; tested |
| A collection's images over the region on different grids, or the grid read from an image elsewhere | `year_native_grid`/`vintage_native_grid` filter by bounds and check every intersecting image (`common_native_grid`); tested with mixed grids |
| A file labelled with the wrong CRS (e.g. a leftover `"EPSG:5070"`) | Tests run end to end with a non-5070 source CRS; tested by mutation |
| Earth Engine applies its own sub-pixel offset on the native lattice, or PROJ's WGS84-NAD83 step moves NLCD | CR-0035 pilot: `pixelCoordinates` on the native lattice within 0.01 m, and the PROJ pipeline recorded; CR-0035's per-file content gate catches any residual |
| The fix moves content but the effect on the model is unknown | CR-0035 measures it |

## Test plan
**Synthetic, `tests/test_cr0034.py` (pre-approval, CR-0011 A3):** a fake
Earth Engine serves a synthetic categorical source on a lattice whose
pixel edges sit at odd multiples of 15 m and answers getDownloadURL by
nearest-neighbour with ties broken to the south-east (BUG-0094's measured
behaviour); it serves only the source's own CRS. End-to-end tests run
with the source in EPSG:5070 and in a custom Albers WKT.
- G1 `parse_native_grid`: accepts north-up 30 m; EPSG or WKT; refuses
  rotation, 10 m, missing transform or CRS.
- G2 `region_grid`: snaps to the given lattice, covers the bounds,
  requires `grid`.
- G3 `fetch_tile`: passes `crs` (EPSG and WKT verbatim), `crs_transform`
  and the region in that projection; requires `crs`.
- G4 end to end (both CRSs): `build_raster` for `nlcd` onto a rotated
  template equals the source warped straight onto it (>= 99 %); tags set.
- G5 control: the BUG-0094 0-origin grid falls below 60 %.
- G6 lattice check: refuses an off-lattice mosaic; accepts float noise
  just below a lattice line.
- G7 TreeMap (both CRSs): shares the fixed functions (identity); raw file
  is an exact copy in the source CRS with the tags; off-lattice refused.
- G8 `common_native_grid`: same lattice accepted; empty, different origin,
  different CRS refused.
- G9 `year_native_grid` filters by the region's bounds and refuses mixed
  grids; `vintage_native_grid` handles collection and Image.
- G10 `warp_to_grid` on a 60 km rotated grid: every sampled cell takes the
  source pixel containing its centre (the default transformer: ~95 %).
- G11 both repair-path `WarpedVRT` calls pass `WARP_TOLERANCE_PX`
  (<= 1e-6).
- Author's trial implementation (not committed): all pass; mutants fail -
  0-origin snap, hard-coded request `crs`, no lattice check, TreeMap's own
  `region_grid`, merged file labelled EPSG:5070, raw TreeMap labelled
  EPSG:5070, no `filterBounds`, first image only, wrap-around lattice
  test, default warp tolerance (G10 and G11 fail).
- Existing suites pass, `test_cr0018_candidates` included (updated with
  the code).

**On the EC2 host:** CR-0035 (re-download pilot and full run, then
`diagnose_layer_registration.py` must show every layer at (0, 0)).

## Deliverables
- [ ] 1. This CR and `tests/test_cr0034.py`; two independent reviews;
      approval.
- [ ] 2. Code (§1-§4) and the `test_cr0018_candidates` update; all
      suites pass.
- [ ] 3. BUG-0094 corrective action §6 updated; PA-0049 filed with CR-0035
      close-out (its sweep is done: `layer_registration_sweep.txt`).

## Out of scope
- Re-downloading anything (CR-0035).
- The deprecated TreeMap assets (`USFS/GTAC/TreeMap/v20xx` superseded by
  `projects/gtac-data-publish/assets/TreeMap/Product_Version/2023-1`):
  tracked follow-up.
- Consolidating `download_treemap._fetch_all`/`ee_init` with
  `download_tcc_nlcd` (not part of the defect).
