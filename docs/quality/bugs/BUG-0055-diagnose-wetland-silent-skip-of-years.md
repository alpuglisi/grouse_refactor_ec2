# BUG-0055: `diagnose_wetland.center_codes` silently leaves a year's records uncoded when its raster lookup raises (PA-0027 sweep)

## 1. Description
`center_codes` looks up the NLCD centre-pixel code for every record, one
year at a time. If `rd.raster_path(feature, year)` raises any exception,
the year is skipped with no message. Its records keep the fill code `-1`
and are counted in the diagnostic's composition tables as a class of
their own.

## 2. Where encountered
PA-0027 §3.5 sweep (BUG-0049 §8), 2026-09-30:
- `diagnose_wetland.py:65-70`;
- callers at `:158`, `:160` and `:208`.

## 3. What it caused to fail
- **Observed:** nothing checked. This is a diagnostic script; it writes no
  pipeline or model artifact.
- **Possible outcome:** wetland and water composition shares are computed
  over fewer records than they claim, with the missing ones pooled under
  code `-1`, and no warning.
- **Downstream use:** the untracked `WETLAND_LEAN_FINDINGS.md` cites this
  diagnostic's figures. Whether any year was skipped when they were
  produced is not known.

## 4. What the defect was
`diagnose_wetland.py:62-70`:
```python
    codes = np.full(len(df), -1, dtype=int)
    if "year" not in df.columns:
        return codes
    for year in sorted(df["year"].dropna().astype(int).unique()):
        mask = (df["year"].astype(int) == year).values
        try:
            path = rd.raster_path(feature, int(year))
        except Exception:
            continue
```

## 5. Root cause analysis (Five Whys)
1. **Why can records go uncoded silently?** The handler continues and
   prints nothing.
2. **Why continue?** The author expected an occasional missing raster
   (`MissingDataError`).
3. **Why does it hide other errors too?** The handler is broad, and the
   fill value `-1` looks like data to the tables built from it.

**Root cause:** a broad, silent handler resolved to the "continue"
branch, and the skipped records keep a fill value that downstream
counting treats as a class (BUG-0049's mechanism).

## 6. Corrective action
Commit `4683e3c` (trivial fix, no CR; confirmed confined: the function
body plus one name, `MissingDataError`, added to the existing
`from grouse_data import (...)` line; no signature, CLI or output
change).

`diagnose_wetland.center_codes` now catches only `MissingDataError` from
`rd.raster_path`. It prints `[warn] [<region>] <feature> <year>: no raster
(...) - N record(s) left uncoded (-1)` and continues. Any other error
propagates. Skipped records still carry `-1`, but the skip is now
visible with its record count.

Test: `tests/test_pa0027_fixes.py::Bug0055CenterCodes`: on a synthetic
GeoTIFF, a year with `MissingDataError` leaves its 2 records at `-1` and
prints the count, and the other year is coded; a `RuntimeError`
propagates. Both tests fail on the pre-fix code.

Not re-checked: whether the figures cited in `WETLAND_LEAN_FINDINGS.md`
were produced with a skipped year (§3). That needs a re-run on real data
and is outside this fix.

Status: **FIXED** (`4683e3c`).

## 7. Recurrence review
- **BUG-0049** (same pass): same mechanism.
- **BUG-0013 / PA-0011:** see BUG-0049 §7.

## 8. Preventive action
Covered by **PA-0027**. No new rule.
