# BUG-0071: `generate_treemap_features._source_is_valid` turns any error into "no real content", dropping a vintage

> Filed from CR-0018 lint candidate **C7** (`docs/quality/change-requests/CR-0018-pa0027-lint.md` §4),
> 2026-09-30. Key `('generate_treemap_features.py', '_source_is_valid', 0)`.

## 1. Description
`_source_is_valid(path)` probes a TreeMap source GeoTIFF for real
content. Any exception returned `False`, cached per path by
`functools.lru_cache`. `find_source` then treats the file as absent and
prints that it "has no real content (empty/corrupt/zero valid pixels)",
and `discover_vintages` drops the whole vintage for every region, with a
warning, and the run continues and exits 0 with fewer vintages. A
programming or environment error in the probe (a `TypeError`, a GDAL
driver problem, a `MemoryError`) therefore silently narrowed the feature
set, and the printed cause was wrong.

## 2. Where encountered
- `generate_treemap_features.py:179` (handler) at `666474c`; callers
  `find_source` (`:220-229`) and `discover_vintages` (`:246-253`).
- Found by the CR-0018 lint review, 2026-09-30. The PA-0027 sweep
  (BUG-0049 §8) classed it "probe -> invalid" (fail-closed), judging the
  handler's own return value only.
- Never observed dropping a vintage.

## 3. What it caused to fail
The generated TreeMap features (`generate_treemap_features.py` output,
used as model inputs) would silently be built from fewer TreeMap
vintages, so records are matched to a more distant vintage by
`nearest_vintage`. The run exits 0. The warning blames file content, so
the real cause (the exception) is not visible. For a genuinely corrupt
download the drop is the designed behaviour; the defect is that every
other error took the same path with the same message.

## 4. What the defect was
`generate_treemap_features.py:166-180` at `666474c`:
```python
    try:
        if os.path.getsize(path) == 0:
            return False
        with rasterio.open(path) as src:
            # A decimated probe read, not the real data read - this
            # only needs to answer "is there any signal here at all",
            # and these are CONUS-scale clips.
            arr = src.read(1, out_shape=(1, min(src.height, 1024),
                                         min(src.width, 1024)))
            frac = float((arr > 0).mean()) if arr.size else 0.0
            return frac >= min_valid_frac
    except Exception:
        return False
```
and the caller's message, `find_source`:
```python
        if hits:
            print(f"   [warn] {[os.path.basename(h) for h in hits]} "
                 f"matches TreeMap {vintage} {attr}"
                 f"{f' ({region})' if region else ''} by name, but has "
                 f"no real content (empty/corrupt/zero valid pixels) - "
                 f"treating as not found, not falling back to it.")
```

## 5. Root cause analysis (fault tree)
Top event: a vintage is dropped, run exits 0, printed cause wrong.
AND of:
- **A.** the probe returns `False` for an exception that is not "this
  file is unreadable" (A1: broad `except Exception`; A2: no type
  printed);
- **B.** the caller maps `False` to "absent" and the batch skips the
  unit (designed for bad files: `discover_vintages` excludes an
  incomplete vintage rather than run a subset);
- **C.** the caller's message states one cause ("no real content").

B and C are correct for the expected condition. A is the only faulty
event: `False` ("invalid") is fail-closed for the probe, but its caller
turns it into a unit-of-a-batch skip, so the probe must only return it
for the conditions that skip is designed for.

**Root cause:** a validity probe resolved every exception to "invalid",
and its caller turns "invalid" into a batch skip, so an unexpected error
became a silent, mis-attributed skip.

## 6. Corrective action
Trivial fix (one function, no signature/CLI/schema change), no CR:
```python
    except OSError as e:
        # BUG-0071 (PA-0027): only an unreadable file (vanished, or not
        # a readable GeoTIFF - RasterioIOError is an OSError) is
        # invalid, and the real cause is printed; find_source's warning
        # alone would blame "no real content". Any other error
        # propagates instead of silently dropping the vintage.
        print(f"   [warn] {path}: cannot be read as a raster "
              f"({type(e).__name__}: {e}) - treated as invalid")
        return False
```
`rasterio.errors.RasterioIOError` subclasses `OSError` (checked on the
installed rasterio: MRO `RasterioIOError, RasterioError, OSError, ...`),
so a truncated or non-GeoTIFF file and a vanished path
(`FileNotFoundError` from `getsize`) are still invalid, now with the
cause printed once per path (the result is cached). Everything else
propagates and stops the run. The handler is narrow now, so the lint no
longer flags it; its `EXPECTED_UNCLASSIFIED` entry was removed. The same
pattern is used by the BUG-0052 fix (`download_rev._raster_valid_fraction`).

**Verified:** `tests/test_cr0018_candidates.py::Bug0071SourceIsValid`:
a non-raster file -> `False` with `RasterioIOError` printed; a missing
path -> `False` with `FileNotFoundError`; `rasterio.open` patched to
raise `TypeError` -> propagates. All three fail on `666474c`.

Status: **FIXED** (`0355240`, branch `worktree-agent-a76c8932c8a2f4fc3`).

## 7. Recurrence review (`CLAUDE.md` §4)
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for validity probes,
broad handlers, PA-0027.
- **BUG-0052** (`download_rev` validity probe returned `None`, read as
  "passed") and **BUG-0053** (unreadable EVT table -> "absent" ->
  `Unmapped`): **same mechanism**, a probe's error value read by the
  caller as a designed non-error case. **Recurrence** of BUG-0049 /
  PA-0027.
- **BUG-0068** (this batch): the same caller-side shape.
- Contrast: `grouse_data._is_valid_raster` (allowlisted) returns invalid
  too, but its caller's nearest-year fallback is designed and recorded
  by E11(b).

**Prior-preventive-action failure analysis (PA-0027).** The rule forbids
"returning a value the caller reads as ... a designed non-error case
('absent')". The sweep **misapplied** it by classifying the probe on
its own return value ("invalid" = fail-closed) without following it into
`find_source`/`discover_vintages`. CR-0018 §5 records that caller-side
handling is not detected by the lint (the digest pins only the handler's
own function), so the lint surfaced the handler for review but cannot
close this class mechanically. That decision is owned by the tracker
item "MEDIUM (A-r2, R-A5a): lint limits in CR-0018 §5 ... caller-side
handling ... decide whether to extend PA-0027's text and the lint".

## 8. Preventive action
**No new PA now**; see BUG-0068 §8 (same residual gap; both BUGs added
to the owning tracker item as its concrete instances). Sweep for the
same shape (a probe returning invalid/`None`/`False` on a broad handler
whose caller skips a unit): among the lint's non-conforming handlers at
the fix head, the probes are `acceptance_split.Rasters.is_valid` (->
invalid; its caller replays `grouse_data`'s nearest-year fallback and
raises `ReplayError` when no year is valid), `grouse_data.
RegionData._is_valid_raster` (nearest-year fallback, designed, recorded
by E11(b)) and `download_rev.published_products` (BUG-0065: `None` ->
run the job without the pre-flight). None skips a unit silently. No
other instance.
