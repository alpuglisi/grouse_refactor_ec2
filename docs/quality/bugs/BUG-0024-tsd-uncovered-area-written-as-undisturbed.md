# BUG-0024: `tsd` writes "undisturbed" for pixels the disturbance record does not cover

## 1. Description
Found by the PA-0017 sweep (BUG-0023). `generate_time_since_disturbance.py`
starts every pixel as "never disturbed" and only overwrites pixels where a
disturbance raster reports a hit. Pixels outside the disturbance stack's
coverage never report a hit, so they are written as `TSD_MAX_YEARS`
("undisturbed for 30 years"), a legitimate value, instead of nodata.

## 2. Where encountered
- `generate_time_since_disturbance.py:302`: `process_region`
  initialises `last`.
- `generate_time_since_disturbance.py:339`: `_emit` converts it to years.

## 3. What it caused to fail
The LANDFIRE annual disturbance stack is CONUS-only. Every region grid
extends into Québec (NH, VT, ME) and ME's also over ocean. There, `tsd`
reads "undisturbed for 30 years" instead of missing. A model sees
fabricated stand history at the Canadian edge of every grid.

**Unconfirmed on real data.** It depends on the stack's footprint versus
the grid, which a check of a real `*_tsd.tif` against `evt` nodata over
Québec would settle. It does not affect the Errol box (entirely in the
US).

## 4. What the defect was
```python
            # -1 = never disturbed within the record.
            last = np.full((nrows, width), -1, dtype=np.int16)
...
                hit = arr > 0
                if v.nodata is not None:
                    hit &= arr != v.nodata
                last[hit] = d
...
    years_since = np.where(last >= 0, year - last, TSD_MAX_YEARS)
    dst.write(tsd_encode(years_since), 1, window=win)
```
"No hit" is treated the same whether the record says undisturbed or the
record has no data there. `hit` also excludes only each vintage's
*declared* nodata tag, which differs by vintage (`32767`, or `-32768` for
Dist22), so a `32767` fill under a `-32768` tag counted as a disturbance
(CR-0008 round 8, B3). Every such pixel is outside coverage, so after
the fix below it changes no output.

## 5. Root cause analysis (Five Whys)
1. *Why do uncovered pixels read undisturbed?* "No hit" defaults to
   undisturbed.
2. *Why is "no data" counted as "no hit"?* Out-of-coverage reads are
   nodata, and nodata is only *excluded from hits*, never propagated to
   the output.
3. *Why not propagated?* The generator assumed its source covers the
   whole grid.
4. *Why that assumption?* Grid extent (LANDFIRE rectangles) and source
   coverage (CONUS) were never compared.
5. *Why no check?* No rule tied generator source coverage to the output
   grid (see BUG-0023).

**Root cause:** same mechanism as BUG-0023, generation over a grid larger
than the source's coverage with uncovered pixels given a legitimate
default.

## 6. Corrective action
Confirmed on real data: outside the disturbance record's coverage every
`tsd` file read the "undisturbed 30 years" constant (ME 96,300,932 px
per file; NH 5,663,604; VT 2,104,152).
- **Data — CR-0010:** those pixels set to `-9999` in all 30 `tsd` files,
  coverage = intersection over vintages of `value ∉ NODATA_SENTINELS`
  (pinned digest). Evidence: `docs/quality/evidence/CR-0010-gates.txt`.
- **Generator — CR-0008:** `generate_time_since_disturbance.py` tracks
  per-pixel coverage (intersection over vintages ≤ the output year) and
  writes `-9999` outside it; `hit` excludes every sentinel. Verified:
  regenerated ME 2016, NH 2025, VT 2025 are pixel-identical to CR-0010's
  repair (`docs/quality/evidence/CR-0008-gates.txt`).

Status: **FIXED** (CR-0010 data, CR-0008 generator).

## 7. Recurrence review
Same mechanism as BUG-0023, found by its sweep (PA-0017). Not a recurrence
of an earlier fixed bug.

## 8. Preventive action
Covered by **PA-0017** (BUG-0023). No new rule.
