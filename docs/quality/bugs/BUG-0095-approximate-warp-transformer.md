# BUG-0095: local nearest-neighbour warps use GDAL's approximate transformer, so on a large rotated grid ~7 % of cells take a neighbouring source pixel

**Status:** OPEN — fix in CR-0034 (v3) for the repair path (`warp_to_grid`,
`generate_treemap_features`); other call sites in §8. Found 2026-10-05 in
CR-0035 round-2 review (reviewer B, B35-2-4) and reproduced by the author.

## 1. Description
`rasterio`'s `WarpedVRT` (and `reproject`) default to GDAL's approximate
transformer, error up to `tolerance` = 0.125 source pixels (3.75 m at 30
m). With nearest-neighbour onto a grid rotated against the source, a cell
centre within that distance of a source pixel edge can take the
neighbouring pixel.

## 2. Where encountered
`realign_rasters.py:86` (`warp_to_grid`, used by `download_tcc_nlcd.build_raster`
and `realign_rasters`), `generate_treemap_features.py:307`.

## 3. What it caused to fail
Measured (author, 2026-10-05; synthetic random field, EPSG:5070 source
with BUG-0094's 15 m lattice offset, 60 km local-Albers template like the
LFPS grids): cells equal to the source pixel containing the cell centre -
default 0.932, `tolerance` 0.01: 0.995, 1e-6: 1.000; `reproject(tolerance=0)`:
1.000. On a 3 km grid the loss was 0.25 %. Real layers are spatially
smoother, so fewer cells change value, but the displacement exists in every
warped layer (`nlcd`, `tcc`, the TreeMap layers). It would also have
failed CR-0035's per-file gate on correctly re-downloaded data.

## 4. What the defect was
```python
        with WarpedVRT(src, crs=ref.crs, transform=ref.transform,
                       width=ref.width, height=ref.height,
                       resampling=Resampling.nearest,
                       src_nodata=nodata, nodata=nodata) as vrt, \
```
```python
            vrts[attr] = WarpedVRT(s, crs=ref_crs, transform=ref_transform,
                                   width=width, height=height,
                                   resampling=Resampling.nearest)
```
No `tolerance`: the 0.125 px approximation applies.

## 5. Root cause analysis (Five Whys)
1. Why do some cells take a neighbour? The transformer's coordinates are
   off by up to 0.125 px, and nearest-neighbour turns any error that
   crosses a pixel edge into a whole-pixel swap.
2. Why is the transformer approximate? GDAL's default (speed); rasterio
   passes it through unless `tolerance` is given.
3. Why was the default accepted? The warp was judged by its declared grid
   (`grid_mismatch`), which is exact; where content lands was not
   measured.
4. Why not measured? No check compared warped content with the source
   pixel containing each cell centre (the same gap as BUG-0094 §5.4).

**Root cause:** a resampling step's accuracy was taken from library
defaults and its output grid, never from a measurement of where content
lands.

## 6. Corrective action
CR-0034 v3 §5: `realign_rasters.WARP_TOLERANCE_PX = 1e-6`, passed by
`warp_to_grid` and `generate_treemap_features` (`tolerance=0` together with
an explicit transform fails in rasterio 1.5's `WarpedVRT`). Tests G10
(60 km rotated grid, 100 % of sampled cells take the containing pixel; the
default fails at ~0.95) and G11 (both call sites pass the constant).
Data repaired by CR-0035's re-download.

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` / `PREVENTIVE_ACTIONS.md`: same mechanism family as
**BUG-0094** (found the same day; resampled content misplaced while the
declared grid is right) and **BUG-0009 / PA-0007** (half-pixel
conventions). Prior-preventive-action failure analysis: PA-0007 is too
narrow (Affine construction only); BUG-0094's preventive action PA-0049
was not yet filed (same root cause, §5.4). Not a separate root cause: it
is handled by PA-0049, whose clause (b) (content registration measured
against an independent reference) would have caught it, extended with
clause (c) below.

## 8. Preventive action
PA-0049 (filed at CR-0035 close-out) gains (c): every local resampling
call passes an explicit, exact transformer tolerance; library defaults are
not accepted for nearest-neighbour onto a rotated grid.
Sweep (2026-10-05, `git grep` for `WarpedVRT(`, `reproject(`,
`warp_to_grid(` in tracked `*.py` minus `inv_*`/`res_*`/`docs/`/`legacy/`):
- `realign_rasters.py:86`, `generate_treemap_features.py:307` - fixed by
  CR-0034 v3.
- `generate_time_since_disturbance.py:297`, `repair_coverage_rasters.py:130`,
  `check_raster_repair.py:121`, `predict.py:174`, `predict.py:724`,
  `find_tsd_contrast_points.py:117` - to assess: each is harmless where
  source and template share CRS and lattice (the transform is then
  affine and exact). Tracked as one item with owner; each confirmed
  instance gets its own BUG.

## Cross-references
BUG-0094; CR-0034 (fix), CR-0035 (data repair); PA-0049.
