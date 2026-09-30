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

**Unconfirmed on real data.** It depends on how Earth Engine's `unmask`
treats pixels outside the image footprint, which a check of a real
TreeMap raster over Québec would settle. It does not affect the Errol box.

## 4. What the defect was
```python
    single_band = image.select([band]).unmask(0).toFloat()
...
                           transform=transform, nodata=None,
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
None yet. Proposed: unmask to 0 only inside TreeMap's footprint (e.g.
the CONUS boundary, or the product's `geometry()`), and write nodata
outside. Needs a CR and a re-download.

Status: **OPEN**, unconfirmed on real data.

## 7. Recurrence review
Same mechanism as BUG-0023, found by its sweep. Not a recurrence.

## 8. Preventive action
Covered by **PA-0017**. No new rule.
