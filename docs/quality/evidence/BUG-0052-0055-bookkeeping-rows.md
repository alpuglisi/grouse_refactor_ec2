# BUG-0052..BUG-0055 BUG_LOG replacement rows (for the lead to apply)

Replace each whole line in `docs/quality/bugs/BUG_LOG.md` that starts
with `| BUG-00NN |` by the replacement line given here. Only the
Remediation and Status cells change; the other cells are copied
verbatim from the current line. No cell in these rows contains a
literal `|`, so no `\|` escapes are needed.

## BUG-0055

Current line:

```
| BUG-0055 | 2026-09-30 | `diagnose_wetland.center_codes` skips a year silently on any raster-lookup error; its records keep fill code `-1`, counted as a class (PA-0027 sweep) | Broad silent handler resolves to "continue" (BUG-0049 mechanism) | None yet — catch `MissingDataError` only, print the skip (one function; no CR); owner: next change to `diagnose_wetland.py` | OPEN (low; diagnostic) |
```

Replacement line:

```
| BUG-0055 | 2026-09-30 | `diagnose_wetland.center_codes` skips a year silently on any raster-lookup error; its records keep fill code `-1`, counted as a class (PA-0027 sweep) | Broad silent handler resolves to "continue" (BUG-0049 mechanism) | `4683e3c` (no CR): catch `MissingDataError` only, print year and uncoded record count, others propagate; `tests/test_pa0027_fixes.py::Bug0055CenterCodes` | FIXED |
```

## BUG-0054

Current line:

```
| BUG-0054 | 2026-09-30 | `download_tcc_nlcd.sighting_years` silently drops a class whose file fails to load, narrowing the vintages downloaded (PA-0027 sweep) | Broad silent handler resolves to "continue" (BUG-0049 mechanism) | None yet — catch `MissingDataError` only, print the skip (one function; no CR); owner: next change to `download_tcc_nlcd.py` | OPEN (low) |
```

Replacement line:

```
| BUG-0054 | 2026-09-30 | `download_tcc_nlcd.sighting_years` silently drops a class whose file fails to load, narrowing the vintages downloaded (PA-0027 sweep) | Broad silent handler resolves to "continue" (BUG-0049 mechanism) | `4683e3c` (no CR): catch `MissingDataError` only, print the skipped class, others propagate; `tests/test_pa0027_fixes.py::Bug0054SightingYears` | FIXED |
```

## BUG-0053

Current line:

```
| BUG-0053 | 2026-09-30 | `analyze_grouse.load_evt_crosswalk` maps an unreadable EVT table to `None` ("no table"); callers degrade `evt_phys` to `Unmapped` and exit 0 (PA-0027 sweep) | Broad handler resolves an error to a designed non-error branch (BUG-0049 mechanism) | None yet — let the read error propagate (one function; no CR); owner: next change to `analyze_grouse.py` | OPEN |
```

Replacement line:

```
| BUG-0053 | 2026-09-30 | `analyze_grouse.load_evt_crosswalk` maps an unreadable EVT table to `None` ("no table"); callers degrade `evt_phys` to `Unmapped` and exit 0 (PA-0027 sweep) | Broad handler resolves an error to a designed non-error branch (BUG-0049 mechanism) | `4683e3c` (no CR): lead decision, crosswalk is required: missing, unreadable or malformed table raises, never returns `None`; `tests/test_pa0027_fixes.py::Bug0053EvtCrosswalk`; dead caller `None` branches tracked (LOW) | FIXED |
```

## BUG-0052

Current line:

```
| BUG-0052 | 2026-09-30 | `download_rev._raster_valid_fraction` returns `None` on any error and both callers read `None` as "passed": an unopenable download is installed as `ok`, an unopenable existing file is never re-fetched (PA-0027 sweep) | Broad handler resolves to the success branch of a validity check, on an unverified "checked above" assumption (BUG-0049 mechanism) | None yet — return invalid (0.0) on rasterio/OS errors, re-raise others (one function; no CR); owner: next change to `download_rev.py` | OPEN |
```

Replacement line:

```
| BUG-0052 | 2026-09-30 | `download_rev._raster_valid_fraction` returns `None` on any error and both callers read `None` as "passed": an unopenable download is installed as `ok`, an unopenable existing file is never re-fetched (PA-0027 sweep) | Broad handler resolves to the success branch of a validity check, on an unverified "checked above" assumption (BUG-0049 mechanism) | `4683e3c` (no CR): `RasterioIOError`/`OSError` -> logged, `0.0` (invalid: rejected / re-fetched), others propagate; `tests/test_pa0027_fixes.py::Bug0052RasterValidFraction` | FIXED |
```
