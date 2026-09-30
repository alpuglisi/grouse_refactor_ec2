# BUG-0054: `download_tcc_nlcd.sighting_years` silently drops a class whose file fails to load, narrowing the vintages downloaded (PA-0027 sweep)

## 1. Description
`sighting_years` collects the years present in a region's positives and
negatives, to decide which TCC/NLCD vintages to download. It wraps each
file read in `except Exception: continue`, with no message.

If one class fails to load for any reason, the download plan is built
from the other class alone and nothing says so. Reasons include:
- the file is missing;
- a schema error;
- a programming error in `GrouseData`.

## 2. Where encountered
PA-0027 §3.5 sweep (BUG-0049 §8), 2026-09-30:
- `download_tcc_nlcd.py:257-267`;
- caller at `:513-518`.

## 3. What it caused to fail
- **Observed:** nothing.
- **Possible outcome:** fewer product years are downloaded than the
  training records need. `grouse_data.raster_path` then silently uses
  the nearest available vintage for the missing years.
- **When both classes fail:** the caller does print a warning and falls
  back to the latest year only (`:514-517`). The silent case is exactly
  one class failing.

## 4. What the defect was
`download_tcc_nlcd.py:257-267`:
```python
def sighting_years(rd):
    """Every year appearing in this region's positives/negatives."""
    ys = set()
    for getter in (rd.positives, rd.negatives):
        try:
            df = getter("all")
        except Exception:
            continue
        if "year" in df.columns:
            ys |= {int(y) for y in df["year"].dropna().astype(int)}
    return ys
```

## 5. Root cause analysis (Five Whys)
1. **Why can the plan silently miss years?** A failed read of one class
   is skipped with no message.
2. **Why skip at all?** Negatives may legitimately not exist yet when
   rasters are first downloaded. That is the expected
   `MissingDataError` case.
3. **Why does a real error take the same path?** The handler is
   `except Exception`, not `except MissingDataError`, and it prints
   nothing.

**Root cause:** a broad, silent handler resolved every error to the
"continue" branch (BUG-0049's mechanism).

## 6. Corrective action
**None yet.** The fix is confined to one function:
- catch only `MissingDataError`;
- print which class was skipped;
- let anything else propagate.

That meets the trivial-fix test, so no CR is needed; a BUG is required.
Owner: the next change to `download_tcc_nlcd.py` (tracker).

Status: **OPEN** (low).

## 7. Recurrence review
- **BUG-0049** (same pass): same mechanism.
- **BUG-0013 / PA-0011:** see BUG-0049 §7.

## 8. Preventive action
Covered by **PA-0027**. No new rule.
