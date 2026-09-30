# BUG-0025: TreeMap `unmask(0)` also fills pixels outside TreeMap's coverage with "non-forest"

## 1. Description
Found by the PA-0017 sweep (BUG-0023). `download_treemap.py` unmasks every
TreeMap band to 0 before download, deliberately, because 0 is the correct
value for in-coverage non-forest. The same call also turns pixels outside
TreeMap's CONUS footprint into 0. The file is written with
`nodata=None`, so "outside coverage" becomes "non-forest: zero basal
area, zero stems."

## 2. Where encountered
- `download_treemap.py:293` (`build_raster`) and `:319`, the output
  profile.

## 3. What it caused to fail
Québec (every grid) and ocean (ME) read as non-forest in `balive`,
`tpa_live`, `qmd` and `carbon_dwn`, a legitimate reading, instead of
missing.

Confirmed on real data (see §6). It does not affect the Errol box.

## 4. What the defect was
```python
    single_band = image.select([band]).unmask(0).toFloat()
...
                           transform=transform, nodata=None,
```
and, in `generate_treemap_features.py`, `_clean` turned any sentinel that
did reach it into the same fabricated value (CR-0008 round 8, B3):
```python
    a[~np.isfinite(a)] = 0.0
    a[a >= NODATA_FLOOR] = 0.0
    a[a < 0] = 0.0
```

## 5. Root cause analysis (Five Whys)
1. *Why do out-of-coverage pixels read non-forest?* `unmask(0)` fills
   every masked pixel.
2. *Why every masked pixel?* One mask carries two meanings in Earth
   Engine: in-coverage non-forest, and outside the product.
3. *Why weren't they separated?* The design considered only the
   in-coverage meaning (see the module docstring, "NON-FOREST: unmask(0)
   AT DOWNLOAD TIME").
4. *Why was that enough?* The grid was assumed to lie inside the source
   coverage.
5. *Why no check?* No rule tied source coverage to the output grid (see
   BUG-0023).

**Root cause:** same mechanism as BUG-0023.

## 6. Corrective action
Confirmed on real data: `data/treemap_raw` carries `nodata=None` and no
sentinel at all, and every TreeMap feature read `0` outside the US
(ME 96,215,819 px per file; NH 5,659,263; VT 2,100,649), plus
11,700 / 4,464 / 2,137 px of `> 0` resampling bleed past the border.
Because the raw bands cannot distinguish "outside CONUS" from
"non-forest", coverage comes from an external reference: the region's
NLCD valid footprint.
- **Data — CR-0010:** outside-NLCD pixels set to `-9999` in all 120
  TreeMap files; in-coverage zeros (non-forest) kept.
- **Generator — CR-0008:** `generate_treemap_features.py` masks its
  output with the region's NLCD raster, and `_clean` flags bad raw values
  for nodata instead of clamping them to `0`. Verified: VT 2016/2019/2022
  regenerated, all four features pixel-identical to CR-0010's repair.
- `download_treemap.py` is unchanged: its raw output is an intermediate
  the model never reads (CR-0008, Out of scope).

Status: **FIXED** (CR-0010 data, CR-0008 generator).

## 7. Recurrence review
Same mechanism as BUG-0023, found by its sweep. Not a recurrence.

## 8. Preventive action
Covered by **PA-0017**. No new rule.
