# BUG-0030: `tcc` exports Earth Engine's masked pixels as 0 % canopy outside coverage

## 1. Description
`download_tcc_nlcd.py` downloads USFS Tree Canopy Cover from Earth Engine.
Pixels outside the product's footprint (Canada, ocean) are masked in Earth
Engine and arrive in the downloaded GeoTIFF as `0`. The script's range mask
keeps every value in `tcc`'s valid range `0–100`, so those pixels are
written as a legitimate reading — "0 % canopy" — instead of nodata.

## 2. Where encountered
- `download_tcc_nlcd.py:218-229` (`year_image`): the mosaic is fetched
  with no `unmask` to an out-of-range value.
- `download_tcc_nlcd.py:365-367` (`build_raster`): the range mask, with
  `valid_range = (0, 100)` for `tcc` (`:99`).
- Found by CR-0008's real-file check, which closed the item PA-0017's
  sweep left open ("TCC/NLCD masked-pixel export not determined from
  code").

## 3. What it caused to fail
Every existing `tcc` raster (24 files) read `0` over nearly all of the
area outside the US, measured at full resolution:

| region | outside-coverage px reading 0 | share of outside px | outside px reading > 0 |
|---|---|---|---|
| ME | 95,946,265 | 99.7 % | 0 |
| NH | 5,653,164 | 99.9 % | 0 |
| VT | 2,096,352 | 99.8 % | 0 |

The model could not tell these from real 0 % canopy, which is common
inside the US (ME 11.0 %, NH 22.6 %, VT 44.3 % of in-footprint `tcc == 0`).

## 4. What the defect was
```python
def year_image(ee, cid, band_prefs, year):
    ...
    return sub.select(band).mosaic(), band
...
        arr = mosaic[0].astype(np.float64)
        out = np.where((arr >= lo) & (arr <= hi), arr,
                       NODATA).astype(np.int16)
```
with `"valid_range": (0, 100)` for `tcc`. Earth Engine exports masked
pixels as `0`, which is inside `[lo, hi]`.

## 5. Root cause analysis (Five Whys)
1. *Why does `tcc` read 0 outside the US?* Earth Engine's masked pixels
   export as `0`, and the range mask keeps `0`.
2. *Why does the range mask keep it?* `0` is a real `tcc` value, so the
   valid range must start at 0; the range mask cannot tell the two
   meanings apart.
3. *Why weren't they separated before export?* The script never unmasks
   to a value outside the valid range, so the distinction is lost in
   Earth Engine.
4. *Why does `nlcd` from the same script not show it?* `nlcd`'s valid
   range starts at 11, so its exported `0` is rejected — correct only by
   accident (BUG-0035).
5. *Why wasn't this caught when PA-0017 was written?* PA-0017's sweep
   recorded the TCC/NLCD export as "not determined from code (needs a
   real-file check)" and nothing owned that check.

**Root cause:** a masked Earth Engine source is exported with its mask
collapsed into a legitimate value (PA-0017's mechanism), and the sweep
that should have found it recorded an undetermined result with no owner.

## 6. Corrective action
- **Data:** CR-0010 set the outside-coverage pixels of all 24 `tcc` files
  to `-9999`, using the NLCD valid footprint as the coverage reference
  (`tcc` is NLCD Tree Canopy Cover, and its outside-footprint `> 0` count
  is exactly 0). Verified by `check_raster_repair.py` (G0–G7);
  evidence `docs/quality/evidence/CR-0010-gates.txt`.
- **Generator — CR-0008:** `year_image` exports
  `mosaic().toInt16().unmask(-1)`, which the range mask turns into
  `-9999`; every download is written to a temp file and replaces the
  existing one only if no `tcc` value lies outside the region's NLCD
  footprint (tests U3, U5). A real Earth Engine download could not be run
  here; the in-code check covers every future one. (CR-0010's interim
  refuse-to-overwrite guard was removed by CR-0008.)

Status: **FIXED** (CR-0010 data, CR-0008 generator).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`.
- **Same mechanism:** BUG-0025 (TreeMap `unmask(0)` fills outside
  coverage) and BUG-0024 (`tsd` "never disturbed" default outside
  coverage). PA-0017 explicitly names "masked sources (Earth Engine
  `unmask()`)". This is a **recurrence** of PA-0017's class.
- **Prior-preventive-action failure analysis.** PA-0017 was not too
  narrow and not at the wrong layer — it names this exact source type.
  It failed because its sweep was **not followed through**: the Swept?
  cell recorded "not determined from code (needs a real-file check)",
  which PA-0015 accepts as a status, and nothing assigned the check to a
  bug, CR or owner. An undetermined sweep result was indistinguishable
  from a finished one.

## 8. Preventive action
**PA-0022** (extends PA-0015): a Swept? cell may not record an
undetermined result ("not determined", "needs a check", "unconfirmed")
unless it names the BUG or CR that owns resolving it. A sweep with an
unowned undetermined item is an unfinished sweep.

Numbered PA-0022 because PA-0019–0021 are reserved by the pending
bookkeeping batch cited in CR-0007/CR-0008.

**Sweep (§3.5), scoped to the mechanism** — every Swept? cell in
`PREVENTIVE_ACTIONS.md` holding an undetermined result:
- PA-0006: "left unconfirmed pending domain input (BUG-0017)" — owned by
  BUG-0017. Compliant.
- PA-0017: "TCC/NLCD masked-pixel export not determined from code" —
  unowned. Resolved by this bug and BUG-0035; cell updated.
No other instances.

**Mechanical enforcement:** not yet feasible (no CI). A grep for these
phrases in the Swept? column is a candidate lint when CI is added.
