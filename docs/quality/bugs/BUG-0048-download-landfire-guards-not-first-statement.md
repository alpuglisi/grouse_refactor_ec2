# BUG-0048: `legacy/download_landfire*.py` guarded only under `__main__`, pointing at another stale copy (PA-0026 sweep)

## 1. Description
The three original LANDFIRE downloaders in `legacy/` write
`data/landfire/*.tif`, the raster directory `download_rev.py` owns. They
were neutralised (BUG-0002/0003) by a `raise SystemExit(1)` inside
`if __name__ == "__main__":`. That is not the file's first statement, so
importing the module and calling `download_landfire_data()` still runs the
old code. The message also tells the user to run `download.py`, which is
itself a stale copy (now guarded by CR-0007, BUG-0031).

## 2. Where encountered
PA-0026 §3.5 output-path sweep (BUG-0031 §8), 2026-09-30:
`legacy/download_landfire.py:196-206`, `legacy/download_landfire_2.py:193-203`,
`legacy/download_landfire_3.py:204-214`; `out_dir = "data/landfire"` at
`:68`, `:64`, `:64` respectively.

## 3. What it caused to fail
Nothing observed. Running the file as a script stops. The hazard is an
import-and-call (as the repository's own `inv_*` scripts do with other
modules), which would write rasters from a retired endpoint and placeholder
AOIs (BUG-0002/0003) over the live ones. The message sends a user to a
stale copy.

## 4. What the defect was
`legacy/download_landfire.py:196-206`, verbatim:
```python
if __name__ == "__main__":
    print(
        "DEPRECATED: this script calls a retired LandFire API endpoint "
        "(BUG-0002) and uses placeholder AOI coordinates that don't "
        "overlap the project's ME/NH/VT sighting data (BUG-0003). Use "
        "download.py instead, which has both fixes. See "
        "docs/quality/bugs/BUG-0002-landfire-retired-endpoint.md and "
        "BUG-0003-landfire-placeholder-aoi.md."
    )
    raise SystemExit(1)
    download_landfire_data()
```
(`_2` and `_3` are identical in this block.)

## 5. Root cause analysis
Same root cause as BUG-0031 (differential analysis: these copies *were*
given a runtime stop, unlike BUG-0031's five, but at the script-entry layer
rather than the module layer). The stop was placed where the old entry call
was, and its replacement pointer was not updated when `download.py` was
itself superseded by `download_rev.py`.

**Root cause:** the guard was attached to one way of running the file (its
`__main__` block) instead of to the module, and it names a replacement by
hand, so it went stale when the replacement did.

## 6. Corrective action
**CR-0007 v9.2 (§3, "v9.2 (BUG-0048)" paragraph):** line 1 of
`legacy/download_landfire.py`, `legacy/download_landfire_2.py` and
`legacy/download_landfire_3.py` is now
```python
raise SystemExit("legacy/download_landfire.py is a stale copy of download_rev.py (BUG-0031, BUG-0048); use download_rev.py")  # CR-0007 section 3, PA-0026
```
(with each file's own name). The replacement named is `download_rev.py`, the
live LANDFIRE downloader that owns `data/landfire/`, not `legacy/download.py`
(itself a guarded stale copy). The module-level guard covers import-and-call
as well as script runs, which addresses the root cause (a guard attached to
one entry path). Verified by `check_partition.py` P7: the three files are in
`P7_GUARDED` (`check_partition.py:68-71`); P7 checks by AST that the guard
is the first statement and that running each file exits non-zero naming
BUG-0031. PASS in `docs/quality/evidence/CR-0007-gates-v9.2.txt`.

Status: **FIXED** (CR-0007 v9.2).

## 7. Recurrence review
- **BUG-0031 / PA-0026**: the same mechanism; found by that rule's sweep.
- **BUG-0002, BUG-0003 / PA-0002**: these are the same files. Their earlier
  remediation is the partial guard quoted above. PA-0002's failure analysis
  is in BUG-0031 §7 (a mark or a partial stop counted as "deprecated").

## 8. Preventive action
Covered by **PA-0026** ("starts with `raise SystemExit` naming the
replacement"). No new rule.
