# BUG-0094: every Earth Engine download (nlcd, tcc, TreeMap x4) is shifted ~half a cell north-west: tiles requested on a lattice offset exactly half a pixel from the source grid, so nearest-neighbour breaks a four-way tie the same way for every pixel

**Status:** OPEN — root cause confirmed; corrective action CR-0034 (code)
and CR-0035 (data repair, re-acceptance, evaluation). Found 2026-10-05 by
the CR-0032 pilot grid check.

## 1. Description
`nlcd`, `tcc` and the TreeMap layers (`balive`, `tpa_live`, `qmd`,
`carbon_dwn`) on disk are displaced about 15 m west and 15 m north
(~21 m) against the template grid, in all three regions. LANDFIRE-derived
layers are aligned. Six of the fifteen training channels have carried the
shift in every model trained so far.

## 2. Where encountered
- `download_tcc_nlcd.py:301-316` (`region_grid`, 0-origin 30 m snap),
  `:323-330` (`fetch_tile` params), `:410-470` (`build_raster`).
- `download_treemap.py:224-260` (copies of `region_grid`, `fetch_tile`),
  `:306-340` (`build_raster`).
- Found by `generate_canopy_structure.grid_check` (CR-0032 pilot,
  `evidence/CR-0032/pilot_NH_run1-3.txt`).

## 3. What it caused to fail
- Measured against an Earth-Engine-free reference (`road_dist`, TIGER
  vectors rasterised on the template grid), every EE layer peaks at
  offset (1, 0) or (1, 1), i.e. content north-west of its true place, in
  ME, NH and VT (tcc in ME/NH; weak signal in VT); LANDFIRE layers peak
  at (0, 0) (`evidence/CR-0032/layer_registration_sweep.txt`,
  `grid_registration_NH.txt`).
- NLCD fetched straight onto the template grid peaks at (0, 0) and scores
  0.532 vs 0.459 for the on-disk copy at the true position.
- Model inputs: the six channels describe the cell ~21 m south-east of
  the record's cell. Effect on accuracy unmeasured (CR-0035 evaluates).

## 4. What the defect was
```python
def region_grid(bounds_lonlat, pad_m=2000):
    ...
    x0 = math.floor((min(xs) - pad_m) / PIXEL_M) * PIXEL_M
    y0 = math.floor((min(ys) - pad_m) / PIXEL_M) * PIXEL_M
```
```python
    params = {
        "crs": "EPSG:5070",
        "crs_transform": [PIXEL_M, 0, rect[0], 0, -PIXEL_M, rect[3]],
        "region": ee.Geometry.Rectangle(list(rect), "EPSG:5070", False),
        "format": "GEO_TIFF",
    }
```
The requested lattice has edges at multiples of 30 m; the sources' edges
are at odd multiples of 15 m (`evidence/CR-0032/source_lattice_NH.txt`:
NLCD, TCC, TreeMap 2016/2020/2022 all "origin mod 30: 15, 15").

## 5. Root cause analysis (Five Whys, with differential checks)
1. Why are the EE layers ~one cell off? Their values come from the
   source pixel south-east of each output centre: in 1,400 of 1,400
   decisive cells Earth Engine took the SE neighbour
   (`source_lattice_NH.txt`).
2. Why always one neighbour? Each output centre lies exactly on a corner
   of four source pixels (parallel grids, offset 15 m in x and y), so
   nearest-neighbour has a four-way tie, which Earth Engine resolves
   deterministically.
3. Why is the requested grid offset? `region_grid` snaps to multiples of
   30 m, written to make tiles "share pixel edges" with each other; the
   source's own lattice was never read.
4. Why was the shift not caught? Our own geometry is exact (fetch_tile,
   rio_merge and warp_to_grid within 0.1 m: `fetch_tile_offset_NH.txt`);
   `grid_mismatch` checks only the declared grid, and no check compared
   a layer's *content* with an independent reference.
5. Why no content check? PA-0007 (BUG-0009) addressed half-pixel
   conventions only where an Affine is built from centres; registration
   of resampled data was assumed from the transform.

Differential: same image fetched on the source's own lattice copies
pixels exactly (no tie); fetched onto the rotated template grid it
registers at (0, 0) against roads. The 0-origin parallel lattice is the
only route that shifts.

**Root cause:** rasters were resampled (nearest) onto a grid parallel to
the source and offset by exactly half a pixel, which turns every
resampling decision into a tie broken in one fixed direction; and no
check measured registration of content against an independent reference.

## 6. Corrective action
Pending: CR-0034 (request every EE source on its own native CRS and
lattice, so Earth Engine copies pixels and the only resampling is the
local nearest warp onto the rotated template; registration check against
`road_dist` as an acceptance gate); CR-0035 (re-download nlcd, tcc,
TreeMap for all regions and vintages; regenerate split manifests and
re-accept; evaluation retrain).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for grid, registration,
half-pixel and realignment defects. Match by mechanism family:
**BUG-0009 / PA-0007** (prediction export offset by half a pixel: centre
coordinate used as the Affine corner). Not the same code, same family:
raster content misregistered by a half-pixel convention.

**Prior-preventive-action failure analysis.** PA-0007 is **too narrow**
(it binds only to building an Affine from centre coordinates, and its
sweep found one `Affine(` construction) and **not verifiable** (it states
a convention but requires no measurement of where content lands). A
resampling route with a correct transform but tie-biased content is
outside both its wording and its sweep. Other grid rules (the
`grid_mismatch` check, realign_rasters) check declared grids only.

## 8. Preventive action
PA-0049 (extends PA-0007), to be filed at close-out with CR-0034:
(a) a raster resampled onto a grid parallel to its source is requested
on the source's own lattice (read from the source, never assumed); a
half-pixel-offset parallel grid is forbidden; (b) every raster layer a
model reads is checked for **content registration** against an
independent reference produced without the same tool chain
(`diagnose_layer_registration.py` against `road_dist`) when created or
re-downloaded, and the result recorded. Sweep: done
(`layer_registration_sweep.txt`: only the EE downloads affected).

## Cross-references
CR-0032 (discovery); CR-0034, CR-0035 (fix); BUG-0009, PA-0007; PA-0049.
