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
**None yet.** The fix is confined to one function:
- catch only `MissingDataError`;
- print the year and the number of records left uncoded;
- let anything else propagate.

That meets the trivial-fix test, so no CR is needed. Owner: the next
change to `diagnose_wetland.py` (tracker).

Status: **OPEN** (low; diagnostic only).

## 7. Recurrence review
- **BUG-0049** (same pass): same mechanism.
- **BUG-0013 / PA-0011:** see BUG-0049 §7.

## 8. Preventive action
Covered by **PA-0027**. No new rule.
