# CR-0034: Earth Engine downloads requested on each source's own grid

**Status: DRAFT, 2026-10-05** — awaiting independent review.
Verdicts and dispositions: `CR-0034-review-log.md` (created at the first
review). This document states only current intent.

## Scope
`download_tcc_nlcd.py` and `download_treemap.py` request every tile on the
source image's own CRS and pixel lattice, so Earth Engine copies pixels
instead of resampling them; the single resampling step stays the local
nearest warp onto the region's template grid.

## Fixes
BUG-0094 (root cause confirmed: `evidence/CR-0032/source_lattice_NH.txt`).
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
  lattice origin). Refuses (`ValueError`, message names the projection)
  unless the transform is north-up 30 m: `[30, 0, x0, 0, -30, y0]` within
  1e-6 m.
- `year_native_grid(ee, cid, year)`: the grid of the first image of that
  year's subset (the same subset `year_image` mosaics; a mosaic has no
  native projection of its own).

### 2. Tiles on that lattice
- `region_grid(bounds_lonlat, *, grid, pad_m=2000)`: `grid` is required.
  Bounds are transformed into `grid["crs"]` and snapped to
  `x0 + 30 k`, `y0 + 30 k` (padded as today).
- `fetch_tile(ee, image, rect, dest, *, crs, retries=4)`: `crs` is
  required; `params["crs"] = crs`, `crs_transform` as today on `rect`,
  `region = ee.Geometry.Rectangle(rect, ee.Projection(crs), False)`.
  Retry clause unchanged (BUG-0066).
- `build_raster(...)`: gets `grid = year_native_grid(...)`, builds tiles
  with it, merges as today, and **refuses** unless the merged mosaic's
  origin lies on the source lattice (`(c - x0) % 30` and `(f - y0) % 30`
  within 1e-6 m). The merged temporary file carries `grid["crs"]`; the
  warp onto the template (`realign_rasters.warp_to_grid`, nearest) and
  every check after it are unchanged.

### 3. TreeMap (`download_treemap.py`)
- Its private copies of `region_grid`, `tiles` and `fetch_tile` are
  removed; it imports them from `download_tcc_nlcd` (the duplicate is how
  the defect landed twice; PA-0001 family).
- `vintage_native_grid(ee, vintage)`: the native grid of the vintage's
  first image (collection) or the image itself; `main` passes it to
  `build_raster(..., grid=...)`, which uses the same lattice check.
- `generate_treemap_features.py` is unchanged (it already warps nearest
  onto the template from whatever CRS the raw file carries).

### 4. Diagnostics
`diagnose_fetch_tile_offset.py` and `diagnose_source_lattice.py` keep
reproducing the BUG-0094 route by passing an explicit 0-origin EPSG:5070
grid (`BUG0094_ZERO_GRID`), named as such.

## Impact
- **No data changes in this CR.** Files on disk change only when CR-0035
  re-runs the downloads.
- **Callers:** `region_grid` and `fetch_tile` gain required keywords;
  every caller in the repository is updated (the two downloaders, the two
  diagnostics). `generate_canopy_structure.py` uses `year_image`,
  `mask_to_valid`, `PRODUCTS`, `template_raster`, `_fetch_all` only:
  unchanged.
- **Output files:** same names, CRS (template), dtype, nodata and tags as
  today; only the content moves ~half a cell.
- **Tile sizes:** unchanged defaults (`--tile-m` 96000 / 48000); the
  source lattice has the same pixel size.

## One change per CR (CR-0011 A5)
Code only (two downloaders and their diagnostics). Data repair,
re-acceptance and the evaluation retrain are CR-0035.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A source's native CRS is a custom WKT Earth Engine will not accept back as `crs` | The CR-0032 pilot already used a WKT `crs` successfully; CR-0035's pilot re-downloads one tile per product before the full run |
| Native transform not north-up 30 m (e.g. a future product version) | `parse_native_grid` refuses; tested |
| Two sources of one product on different lattices (a mosaic across tiles) | `build_raster` refuses a mosaic off the first image's lattice; tested |
| The fix moves content but the effect on the model is unknown | CR-0035 measures it |

## Test plan
**Synthetic, `tests/test_cr0034.py` (pre-approval, CR-0011 A3):** a fake
Earth Engine serves a synthetic categorical source on an EPSG:5070
lattice with a 15 m origin offset and resamples requests by
nearest-neighbour with ties broken to the south-east (BUG-0094's measured
behaviour).
- G1 `parse_native_grid`: accepts north-up 30 m; returns crs/origin;
  refuses rotation, 10 m pixels, a missing transform.
- G2 `region_grid`: snaps to the given lattice (origin mod 30 = 15), covers
  the bounds, requires `grid`.
- G3 `fetch_tile`: passes `crs`, `crs_transform` and the region in that
  projection; requires `crs`.
- G4 end to end: `build_raster` for `nlcd` onto a rotated local-Albers
  template equals the source warped straight onto the template (>= 99 %
  of valid cells).
- G5 control: the same pipeline with the BUG-0094 0-origin grid falls
  below 60 % (the simulation detects the defect).
- G6 `build_raster` refuses a merged mosaic off the source lattice.
- G7 TreeMap: `download_treemap` uses `download_tcc_nlcd`'s `region_grid`,
  `tiles` and `fetch_tile` (identity), and its `build_raster` end to end
  passes G4's criterion.
- Existing suites pass (both lints, `test_shared_constants`, all others).

**On the EC2 host:** CR-0035 (re-download pilot and full run, then
`diagnose_layer_registration.py` must show every layer at (0, 0)).

## Deliverables
- [ ] 1. This CR and `tests/test_cr0034.py`; two independent reviews;
      approval.
- [ ] 2. Code (§1-§4); all suites pass.
- [ ] 3. BUG-0094 corrective action §6 updated; PA-0049 filed with CR-0035
      close-out (its sweep is done: `layer_registration_sweep.txt`).

## Out of scope
- Re-downloading anything (CR-0035).
- The deprecated TreeMap assets (`USFS/GTAC/TreeMap/v20xx` superseded by
  `projects/gtac-data-publish/assets/TreeMap/Product_Version/2023-1`):
  tracked follow-up.
- Consolidating `download_treemap._fetch_all`/`ee_init` with
  `download_tcc_nlcd` (not part of the defect).
