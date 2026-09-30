# BUG-0023: `road_dist` measured distance to the home state's roads only, across the whole multi-state region grid

## 1. Description
`generate_road_distance.py` loaded TIGER roads for the region's own state
only, but computed and wrote distances for every pixel of the region
grid. That grid is the LANDFIRE request rectangle, which extends well
into neighbouring states. Every pixel across a state line therefore got
the distance to the nearest road *in the home state*, not the nearest
road. Roads just outside the grid edge were also ignored, and pixels
outside all US road data (Canada, ocean) got a computed distance instead
of nodata.

**Reported symptom** (user, 2026-09-29, Errol NH map from `predict.py
--region NH --bounds -71.25 44.70 -70.95 44.90`): "everything on the
maine side of the state border is ranked significantly higher than the
new hampshire side despite being essentially the same habitat."

## 2. Where encountered
- `generate_road_distance.py`, `load_paved_roads` / `county_fips`
  (before commit `bf8d31a` on `main`), and `build_distance_raster` (same
  file).
- Region grid extents: `download_rev.py:19-23`, `BOXES_COORDINATES`. NH
  is `(-72.626, 42.605, -70.600, 45.398)`, reaching −70.60 into Maine.

## 3. What it caused to fail
- **Prediction:** Maine pixels in the NH grid read as up to kilometres
  from any road, even beside Maine roads (Route 26 at Upton, Route 16 at
  Wilsons Mills). Training positives sit 2–5× farther from roads than
  background points (`CHANGELOG.md`, road-hugging investigation), so
  falsely remote land is scored as grouse-like. This is the suspected
  cause of the reported symptom. **Not yet confirmed on real data**; see
  §6 for the pending check.
- **Training:** every training and validation point within a few km of a
  state line got a wrong road distance, in both directions (ME grid
  missing NH roads and vice versa; VT likewise). Every checkpoint trained
  on these rasters, including `bce.pth`, learned from the wrong values.
- **Grid edges and Canada:** roads just outside the grid did not count,
  and Québec pixels held distances to the nearest US road.

## 4. What the defect was
Before `bf8d31a`:
```python
def load_paved_roads(region, mtfcc, target_crs, tiger_year=TIGER_YEAR):
    """Every county's TIGER roads for this state, filtered to the paved
    MTFCC classes and reprojected to the region raster's CRS."""
    ...
    state_fp = STATE_FIPS[region]
    fips = county_fips(state_fp, tiger_year)
    ...
    for cf in fips:
        name = f"tl_{tiger_year}_{state_fp}{cf}_roads.zip"
```
and, over the full grid:
```python
    mask = rasterio.features.rasterize(
        ((geom, 1) for geom in roads.geometry if geom is not None),
        out_shape=(height, width), transform=transform, fill=0,
        default_value=1, all_touched=True, dtype="uint8")
    ...
    dist_m = distance_transform_edt(mask == 0, sampling=(res_y, res_x))
    return road_dist_encode(dist_m), dist_m, transform, crs
```
The source data (one state's roads) covered only part of the output
grid, and nothing marked the rest as nodata.

## 5. Root cause analysis (Five Whys)
1. *Why did Maine pixels get wrong distances?* The roads fed to the
   distance transform were only NH's, and the transform assigns every
   grid pixel a distance to the nearest road it was given.
2. *Why only NH's roads?* The loader was keyed by the region's
   **state** (`STATE_FIPS[region]`), on the implicit assumption that a
   region's grid is that state.
3. *Why was that assumption wrong?* Region grids are LANDFIRE request
   **rectangles** (`download_rev.py:19-23`), which extend into
   neighbouring states and Canada. The grid's extent and the source
   data's extent were defined independently and never compared.
4. *Why didn't anything flag it?* The output has no nodata where the
   source was absent: an invented distance looks exactly like a real one.
   The script's own sanity output (median/p90/p99 distance) cannot reveal
   a spatial coverage gap.
5. *Why wasn't coverage checked at design time?* No rule required a
   derived raster's source data to cover the grid it is written onto. The
   nearest rule, PA-0006, covers readers conflating nodata with a real
   value, not generators inventing values where they have no source.

**Root cause:** a derived raster was computed over a region grid larger
than its source data's coverage (per-state source, rectangular
multi-state grid), and the uncovered area was filled with computed
values instead of being marked nodata. No rule or check tied a
generator's source coverage to its output grid.

## 6. Corrective action
Commit `bf8d31a` on `main` (`generate_road_distance.py`):
- Roads come from **every TIGER county, in any state**, that intersects
  the grid expanded by `--pad-km` (default 10 km) (`load_counties`,
  `counties_for_grid`).
- The distance transform runs on the padded grid (`padded_grid`) and is
  cropped back, so roads just outside the grid count.
- Pixels outside every US county are written as NODATA (`-9999`) via a
  county-coverage mask; the fraction is printed, with a note that
  distances near the Canadian border remain upper bounds.

**Verified** on a synthetic two-state grid:
- a pixel beside the neighbour state's road reads about 30 m;
- a grid-edge pixel picks up a road 300 m outside the grid (about 330 m;
  the old code gave about 2 km);
- pixels outside all counties are NODATA;
- a non-intersecting county is not loaded.

**Not verified:** against real TIGER downloads, or against the reported
symptom. The pending no-retrain confirmation, on the training box:
1. Keep the old `NH_*_road_dist.tif` files.
2. Run `python generate_road_distance.py --regions NH`.
3. Re-run the same `predict.py` command with the old `bce.pth`.

If the Maine-side jump collapses, this is confirmed as the cause of the
reported symptom. Remaining remediation for the user: regenerate all
regions and retrain from scratch.

**Policy deviation, recorded:** this is a non-trivial change (new CLI
flag, and new NODATA semantics in the output). `CLAUDE.md` §1 requires a
change request and independent review *before* implementation. It was
implemented directly at the user's explicit request, with no CR and no
independent review. A retroactive CR with an independent agent review
is outstanding.

Status: **OPEN**. Fix implemented; the link to the reported symptom is
not yet confirmed; CR/review outstanding; retraining outstanding.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`:
- **BUG-0008 / BUG-0017 / PA-0006:** nodata conflated with a legitimate
  value. Same *family* (a real-looking value where there is no data), but
  at the reading stage. This bug is at the **generation** stage: the
  invented value is written into the raster, so no reader can detect it.
- **BUG-0001 / PA-0001:** duplicated geographic constants. Related
  (region extents), not the same mechanism.
- **BUG-0022:** the process defect in diagnosing this very symptom. That
  session first named this mechanism without verifying it; it is still
  unverified against real data (§6).

No prior instance of this mechanism was found.

**Prior-preventive-action failure analysis (PA-0006):** PA-0006 says
nodata handling "must use a dedicated mask array … to distinguish
sentinel nodata from a legitimate value", which is scoped to consuming
rasters. It could not catch a generator that never produces nodata in
the first place: here there was no sentinel to handle, because the
uncovered area was filled with plausible distances. PA-0017 extends
PA-0006 to generation.

## 8. Preventive action
**PA-0017** (new; extends PA-0006, see `PREVENTIVE_ACTIONS.md`): a
derived raster written onto a region grid must be computed from source
data that covers the whole grid, plus a margin for neighbourhood
operations such as distance transforms or smoothing. Any output pixel the
source does not cover must be written as nodata, never filled with a
default or computed value that is also a legitimate reading. The same
applies to per-state or per-country sources, to masked sources (e.g.
Earth Engine `unmask()`), and to "absent" defaults such as "never
disturbed".

**Sweep (§3.5)**, run across every raster generator, from code only (no
real data):
- **`generate_time_since_disturbance.py`** `_emit`/`process_region`:
  pixels outside the disturbance stack's coverage keep `last = -1` and
  are written as `TSD_MAX_YEARS` ("undisturbed"), not nodata →
  **BUG-0024**.
- **`download_treemap.py`** `build_raster`: `unmask(0)` also fills
  pixels outside TreeMap's CONUS coverage with 0 ("non-forest"), and
  writes the file with `nodata=None` → **BUG-0025**.
- **`diagnose_road_bias.py`**: per-state PRISECROADS, the same
  home-state-only mechanism, in a diagnostic → **BUG-0026**.
- **`download_tcc_nlcd.py`:** out-of-range values → NODATA
  (`valid_range`). How Earth Engine exports *masked* pixels outside
  product coverage was **not determined** from code; needs a check on a
  real file's Canadian area.
- **LANDFIRE (`download_rev.py`):** LFPS delivers its own nodata outside
  coverage; no generator fills it. None found.

**Mechanical enforcement (§3.4): feasible, not yet implemented.** A
coverage-consistency check could, for each region and feature, flag
pixels where the LANDFIRE reference (`evt`) is nodata but the feature is
valid, or vice versa, beyond a small tolerance. That catches this whole
class at generation time. It is a candidate change and needs its own CR.
