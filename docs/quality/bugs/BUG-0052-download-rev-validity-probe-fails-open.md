# BUG-0052: `download_rev.py` treats a raster it cannot open as one that passed the empty-raster check (PA-0027 sweep)

## 1. Description
`_raster_valid_fraction` wraps the whole raster read in `except Exception`
and returns `None` on any error. Both callers read `None` as "check
passed":
- **After a download.** An extracted `.tif` that rasterio cannot open is
  installed as the live raster by `_place_result`, and the task reports
  `"ok"`.
- **With `--refetch-empty`.** An existing file that cannot be opened is
  kept, and is never re-fetched.

The docstring says an unopenable file is "already handled by the zip/tif
checks above". The only check above is the zip CRC (`testzip`). It proves
the bytes match the archive, not that they are a readable GeoTIFF.

## 2. Where encountered
PA-0027 §3.5 sweep (BUG-0049 §8), 2026-09-30:
- `download_rev.py:113-126`, the probe;
- callers at `:293-294` and `:396-397`.

The open-issue tracker already had this as an untested hypothesis:
"`download_rev.py`'s valid-pixel check may pass a raster that … fails to
open". The code reading below confirms the open-failure half. The
no-nodata half (`return 1.0`) is a separate design choice and stays a
tracked hypothesis.

## 3. What it caused to fail
- **Observed:** nothing. No known download hit it.
- **Possible outcome:** an unreadable file replaces a readable raster
  (the old file goes to `REPLACED_DIR`) and the run reports success.
  Downstream, `grouse_data.RegionData.raster_path` rejects the unreadable
  file (`grouse_data.py:327`, which fails closed). It then silently falls
  back to the nearest valid year, so training and prediction read
  another vintage without saying so.
- **Masking:** a programming error or `MemoryError` inside the probe also
  counts as "passed".

## 4. What the defect was
`download_rev.py:113-126`:
```python
def _raster_valid_fraction(path):
    """Fraction of non-nodata pixels in a raster's first band. Returns
    None (skip the check) if the file can't be opened as a raster at all
    - that's a different failure mode, already handled by the zip/tif
    checks above."""
    try:
        with rasterio.open(path) as src:
            data = src.read(1)
            if src.nodata is None:
                return 1.0   # no nodata value defined - can't judge, allow it
            n_valid = int((data != src.nodata).sum())
            return n_valid / data.size if data.size else 0.0
    except Exception:
        return None
```
The callers, at `:293-294` and `:396-397`:
```python
                    pct_valid = _raster_valid_fraction(tmp_tif)
                    if pct_valid is not None and pct_valid < MIN_VALID_PIXEL_FRAC:
```
```python
                    frac = _raster_valid_fraction(out)
                    if frac is None or frac >= MIN_VALID_PIXEL_FRAC:
                        continue
```

## 5. Root cause analysis (Five Whys)
1. **Why is an unopenable raster installed?** The probe's error branch
   returns `None`, and the caller treats `None` as a pass.
2. **Why is `None` a pass?** The author assumed an earlier check had
   already rejected unreadable files.
3. **Why was that wrong?** The earlier check is a zip CRC, which covers
   integrity of the archive, not readability as a raster.
4. **Why was it never caught?** No rule required a swallowed exception to
   resolve to the fail-closed outcome. PA-0011 covered only retry loops,
   and only asked for logging.

**Root cause:** a broad handler resolved to the success branch of a
validity check (BUG-0049's mechanism), resting on an unverified
assumption about an upstream check.

## 6. Corrective action
**None yet.** Open for the lead to decide.

The fix is confined to one function: return `0.0` (invalid) on a
rasterio open or read error, narrowed to `rasterio.errors.RasterioIOError`
and `OSError`, and re-raise anything else. The callers are unchanged,
because 0.0 is below `MIN_VALID_PIXEL_FRAC`:
- an unreadable download is rejected;
- an unreadable existing file is re-fetched.

That meets `CLAUDE.md`'s trivial-fix test: one function, no signature
change, no behaviour change beyond the defect. So a BUG is required but
no CR. This pass is documentation only, so the fix is left to the owner.
Owner: the next change to `download_rev.py` (tracker).

Status: **OPEN**.

## 7. Recurrence review
- **BUG-0049** was filed in the same pass: same mechanism, found by
  PA-0027's sweep.
- **BUG-0013 / PA-0011:** same family (broad handler). PA-0011's failure
  analysis is in BUG-0049 §7.
- **BUG-0015:** the same probe was back-ported to `download_more.py`. That
  was a different mechanism, a missing back-port.

## 8. Preventive action
Covered by **PA-0027** (a swallowed exception must resolve to the
fail-closed outcome). No new rule.
