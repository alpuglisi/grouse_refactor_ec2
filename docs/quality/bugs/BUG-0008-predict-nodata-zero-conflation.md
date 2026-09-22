# BUG-0008: `predict.py` conflates sentinel nodata with legitimate zero-valued data

## 1. Description
`predict.py` collapses sentinel nodata values to `0` during raster reads,
then uses `0` itself as the nodata signal for masking. This both (a) masks
out legitimate cells whose real data value is `0`, and (b) fails to mask
true nodata when the raster's declared `nodata` attribute is itself `0`.

## 2. Where encountered
`predict.py:255` (masking check), fed by `predict.py:203-205` (`read_strip`
sentinel-to-zero collapse).

## 3. What it caused to fail
- Cells whose reference feature legitimately equals class `0` (a common
  "no forest"/background encoding in categorical rasters) are silently
  treated as nodata and dropped from the prediction map — valid land area
  goes missing with no error.
- When a raster's own `nodata` attribute is literally `0`, the guard
  `ref_nodata != 0` is `False`, so masking is skipped for that raster
  entirely: true nodata cells (already collapsed to `0` by the sentinel
  pass) get predicted on and shown as real probabilities. This directly
  contradicts the module's own docstring claim that "Nodata is handled
  honestly... masked out... instead of being predicted-on-garbage and
  hidden" (`predict.py:20-22`).

## 4. What the defect was
```python
if ref_band[cy, cx] == 0 and ref_nodata != 0:
```
fed by:
```python
for s in NODATA_SENTINELS: cat[cat == s] = 0; cont[cont == s] = 0.0
```

## 5. Root cause analysis (Five Whys)
1. Why can valid data or true nodata be handled wrong? Because a single
   value (`0`) is used to represent two different things: "this cell is
   nodata" and "this cell's real value happens to be zero."
2. Why does the masking guard invert for `ref_nodata == 0`? Because the
   guard `ref_nodata != 0` was written assuming `nodata` is never actually
   `0`, treating `0` as an implicit "no nodata declared" sentinel rather
   than checking a real boolean/mask.
3. Why was `0` chosen as the universal sentinel? Because it's a convenient
   default for numeric arrays and most of the project's rasters likely
   don't declare `nodata=0`, so the bug wasn't visible in typical runs.
4. Why wasn't a dedicated mask array (or NaN for continuous layers) used
   instead? Because it requires carrying an extra boolean array alongside
   each raster's data array through the read/tile/predict pipeline, which
   the current code avoids for simplicity.
5. Why does that simplicity choice matter? Because it silently breaks the
   exact safety guarantee (honest nodata masking) the module's own
   docstring promises, in both directions (mask-too-much and mask-too-
   little), for real, plausible raster configurations.

**Root cause:** overloading a single numeric value (`0`) to mean both
"sentinel nodata" and "legitimate zero" removes the information needed to
tell them apart, and the fallback guard (`nodata != 0`) silently fails
exactly when a raster's own nodata value is `0`.

## 6. Corrective action
None implemented yet — documentation-only pass. Recommended: carry an
explicit boolean nodata mask per raster (computed from the raster's own
`nodata` attribute at read time, before collapsing sentinels), and check
that mask directly instead of re-deriving nodata from a post-hoc `== 0`
comparison. Status: **OPEN**.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
nodata/mask handling. Result: **none found**.

## 8. Preventive action
**PA-0006** (see `PREVENTIVE_ACTIONS.md`): raster nodata/mask handling must
use a dedicated mask array (or NaN for continuous layers) to distinguish
"sentinel nodata" from a legitimate value of `0`, never overload `0` for
both, and must not gate masking behavior on a comparison (`nodata != 0`)
that is defeated whenever the dataset's true nodata value is itself `0`.
