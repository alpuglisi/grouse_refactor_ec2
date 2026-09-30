# BUG-0035: `nlcd` is correct outside coverage only because its valid range happens to exclude 0

## 1. Description
`download_tcc_nlcd.py` downloads Annual NLCD and USFS TCC through the same
path. Earth Engine exports pixels outside the product footprint as `0`.
For `tcc` that `0` survives as "0 % canopy" (BUG-0030). For `nlcd` it is
rejected — but only because NLCD's class codes start at 11, so the range
mask `valid_range = (11, 95)` happens to exclude `0`. Nothing in the code
states or depends on that on purpose. A product or range change (e.g. a
class-0 code, or widening the range) would silently fabricate a land-cover
class outside coverage.

## 2. Where encountered
- `download_tcc_nlcd.py:218-229` (`year_image`): no `unmask` to an
  out-of-range value before export.
- `download_tcc_nlcd.py:365-367` (`build_raster`): range mask, with
  `valid_range = (11, 95)` for `nlcd` (`:107`).
- Found by the same real-file check as BUG-0030 (CR-0008 v4–v7 research).

## 3. What it caused to fail
Nothing observable today: every `nlcd` raster carries `-9999` outside
coverage (its valid footprint is the reference CR-0010 pins). The defect
is **latent**; `CLAUDE.md` §2 counts it regardless.

## 4. What the defect was
```python
    return sub.select(band).mosaic(), band
...
        out = np.where((arr >= lo) & (arr <= hi), arr,
                       NODATA).astype(np.int16)
```
with `"valid_range": (11, 95)`. Masked pixels arrive as `0`, and
correctness depends on `0 < lo`.

## 5. Root cause analysis (Five Whys)
1. *Why is `nlcd` correct?* `0` is below its valid range.
2. *Why is that an accident?* The range was chosen to describe NLCD's
   class codes, not to reject Earth Engine's mask value.
3. *Why does the mask value reach the range check at all?* The script
   does not unmask to a deliberately out-of-range value before export.
4. *Why not?* Same design gap as BUG-0030: the export was assumed to
   carry only in-coverage values.
5. *Why unnoticed?* The output was correct, and PA-0017's sweep left the
   TCC/NLCD check undetermined with no owner (BUG-0030 §7).

**Root cause:** same as BUG-0030 — the masked Earth Engine source is not
unmasked to an out-of-range value before export.

## 6. Corrective action
CR-0008 §4: `mosaic().toInt16().unmask(-1)` for both products, so `-1`
is rejected by the range mask by design. Plus an in-code post-download
coverage check for `tcc`.

Status: **FIXED** (CR-0008). Tests U3 (`mask_to_valid` rejects both `0`
and `-1` for `nlcd`). A real Earth Engine download could not be run here.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: same mechanism as
BUG-0030 (same script, same Earth Engine mask), BUG-0025 (TreeMap
`unmask(0)`) and PA-0017, which names masked Earth Engine sources.
A recurrence of PA-0017's class, found together with BUG-0030. The
prior-preventive-action failure analysis is BUG-0030 §7: PA-0017's sweep
left this exact check undetermined and unowned.

## 8. Preventive action
Covered by **PA-0022** (from BUG-0030): an undetermined sweep result
must name its owner. No additional rule — the mechanism is PA-0017's,
and PA-0017 already names it.
