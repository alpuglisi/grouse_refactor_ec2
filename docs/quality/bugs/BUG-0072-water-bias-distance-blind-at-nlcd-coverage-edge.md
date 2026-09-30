# BUG-0072: `diagnose_water_bias.py` distance-to-water reads past the NLCD coverage edge (Canadian border) as "no water" (PA-0023 instance)

> Found by the PA-0023 / PA-0032 sweep in CR-0017 deliverable 8
> (BUG-0064 §8), 2026-09-30, at `6342f2a`.

## 1. Description
`diagnose_water_bias.py` measures, per region, how far positives and
negatives lie from open water and from water-or-wetland, using a
Euclidean distance transform of the region's latest NLCD raster. NLCD
covers the United States only; over Canada the raster holds nodata
(`-9999`). The transform treats nodata pixels as "not water", so for a
record near the Canadian border whose nearest NLCD-covered water is
farther away than the border, the distance is measured as if Canada had
no water. The value is an over-read of unknown size, with nothing
marking it.

## 2. Where encountered
- `diagnose_water_bias.py:72-82` (`build_distance_raster`), called at
  `:125-127` from `process_region`, at `6342f2a`.
- Found by the mechanism sweep recorded in BUG-0064 §8 (search for
  `distance_transform` over the tracked `*.py`). BUG-0037's PA-0023 sweep
  (BUG-0037 §8) did not list this file.

## 3. What it caused to fail
Diagnostic output only: the per-class "median / mean / % within 300 m /
1 km" lines and the VERDICT of `diagnose_water_bias.py`. The script
writes no file that any pipeline, training or acceptance step reads.

Measured by `docs/quality/evidence/CR-0017/sweep/water_dist_edge_probe.py`
(output `water_dist_edge_probe.txt`, read-only, at `6342f2a`): records
whose distance to the nearest nodata pixel is smaller than their
measured distance to open water, so the true distance may be smaller:

| region | positives | negatives | where |
|---|---|---|---|
| ME | 28 of 3,660 | 8 of 3,660 | lat 45.2–47.5, the Québec / New Brunswick line |
| NH | 2 of 1,079 | 1 of 1,079 | lat 45.07–45.27 |
| VT | 3 of 1,493 | 2 of 1,493 | lat ≈ 45.00 |

The grid edge adds no further records (the "grid edge or nodata" and
"nodata" counts are equal). About 0.6 % of records are affected, in both
classes; the direction of any effect on the class comparison is not
known.

## 4. What the defect was
`diagnose_water_bias.py:72-82`:
```python
def build_distance_raster(nlcd_path, target_codes):
    """Euclidean distance (meters) from every pixel to the nearest pixel
    whose NLCD code is in target_codes. Returns (dist_array, transform,
    crs) so callers can sample it at arbitrary points."""
    with rasterio.open(nlcd_path) as src:
        nlcd = src.read(1)
        transform, crs, nodata = src.transform, src.crs, src.nodata
    mask = np.isin(nlcd, target_codes)
    res_x, res_y = abs(transform.a), abs(transform.e)
    dist = distance_transform_edt(~mask, sampling=(res_y, res_x))
    return dist, transform, crs
```
`nodata` is read and never used: nodata pixels enter `~mask` as
"not water", and no pixel whose neighbourhood reaches nodata before
water is marked.

## 5. Root cause analysis (Five Whys)
1. **Why can the distance be too large near Canada?** The transform
   searches across nodata pixels as if they were land without water.
2. **Why is there nodata there?** NLCD's coverage ends at the US border;
   the region grid extends into Canada.
3. **Why was it not handled?** The script predates PA-0023 and was
   written like the pre-CR-0014 `road_dist` generator: nodata is not
   distinguished from "not the target".
4. **Why did PA-0023's sweep not find it?** BUG-0037's sweep listed the
   neighbourhood computations the author knew about (road_dist, the
   buffer, thinning, blocks, the KDE, `diagnose_road_bias.py`); it did
   not search the code for the primitives, so a diagnostic distance
   transform was not enumerated.

**Root cause:** a neighbourhood computation whose source (NLCD) ends at a
data-coverage border inside the neighbourhood, with the source's nodata
treated as a valid "absent" value; the PA-0023 sweep that should have
found it enumerated computations from memory instead of by a search.

## 6. Corrective action
**None yet.** The fix is PA-0023's nodata option: in
`build_distance_raster`, compute the distance to the nearest nodata or
off-grid pixel and write NaN wherever it is smaller than the distance to
the target; `summarize` must then drop NaN and print how many records
were excluded. That touches two functions and changes the diagnostic's
printed figures, so it is not inside the "one function" trivial-fix
definition; it goes with the next change to `diagnose_water_bias.py`
(tracker, `docs/quality/CR-0007-0008-OPEN-ISSUES.md`, with BUG-0070's
LOW VERDICT item). Priority LOW: diagnostic only, about 0.6 % of records.

Status: **OPEN** (low; diagnostic only).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "border",
"distance transform", "nodata", "neighbourhood", "coverage".

**Matches:**
- **BUG-0037 / PA-0023:** same mechanism (a distance transform whose
  source ends at the Canadian border), same shape as the pre-CR-0014
  `road_dist` generator.
- **BUG-0050, BUG-0051, BUG-0064:** same rule, other computations.
- **PA-0017 / BUG-0058, BUG-0059:** nodata read as a real value; related
  but about values, not neighbourhoods.

**Prior-preventive-action failure analysis:**
- **PA-0023** — the rule covers this case. Its sweep (BUG-0037 §8) was
  **incomplete**: it enumerated computations by recollection, not by a
  recorded search, and missed this file. Category: not followed as
  written (§3.5 asks for a sweep by mechanism), with nothing making the
  enumeration checkable.
- **PA-0022** — requires owners for undetermined items; it cannot help
  with an item never listed.

## 8. Preventive action
**Folded into PA-0032** (filed with BUG-0064, extends PA-0023) as its
sweep-method clause: a PA-0023 / PA-0032 sweep enumerates candidate
computations by a recorded code search for the neighbourhood primitives
(the search terms and file set are written into the Swept? cell or the
bug doc), never from memory. Not a separate PA: same parent rule, same
review-only enforcement. The BUG-0064 §8 sweep is the first one run that
way.
