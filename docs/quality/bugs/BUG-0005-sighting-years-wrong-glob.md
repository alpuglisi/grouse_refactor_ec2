# BUG-0005: `grouse_data.py` `sighting_years()` globs the wrong directory

## 1. Description
`RegionData.sighting_years()` globs for sighting CSVs directly under the
base config directory, while the sibling method `sightings(year)` on the
same class resolves the actual, namespaced `data/sightings/` path via the
shared `PATH_TEMPLATES` dict. After `organize_project.py` moves raw files
into `data/sightings/` (standard project layout), `sighting_years()` always
returns an empty list even though the files it should find are present.

## 2. Where encountered
`grouse_data.py:331-332` (`sighting_years()`), contrasted with
`grouse_data.py:323-325` (`sightings(year)`).

## 3. What it caused to fail
Any caller using the idiom `for yr in rd.sighting_years(): rd.sightings(yr)`
silently processes zero years — no exception, just an empty loop — because
`sighting_years()`'s glob pattern never matches anything once files live
under `data/sightings/`.

## 4. What the defect was
```python
for p in glob.glob(self.config.resolve(
        f"{self.region.lower()}_sightings_*.csv")):
```
This resolves relative to the config's base directory with no
`data/sightings/` prefix, whereas `sightings(year)` uses
`PATH_TEMPLATES["sightings"] = "data/sightings/{state_lower}_sightings_{year}.csv"`
for the equivalent lookup.

## 5. Root cause analysis (Five Whys)
1. Why does `sighting_years()` return nothing? Because its glob pattern
   doesn't include the `data/sightings/` prefix that the files actually
   live under.
2. Why doesn't it include that prefix? Because it hardcodes its own path
   fragment instead of deriving it from `PATH_TEMPLATES["sightings"]`.
3. Why does it hardcode instead of reuse? Because `sighting_years()` was
   likely written before (or independently of) the `data/sightings/`
   namespacing convention was introduced for `sightings(year)`.
4. Why wasn't `sighting_years()` updated when that convention was
   introduced elsewhere in the same class? Because nothing ties the two
   methods' path logic together — they're two independently-written string
   patterns describing what should be the same location.

**Root cause:** `sighting_years()`'s glob pattern is a hardcoded path
fragment independent of the single source of truth (`PATH_TEMPLATES`) that
the class's own `sightings(year)` method correctly uses, so the two drifted
out of sync when the directory layout changed.

## 6. Corrective action
Trivial fix (confined to `sighting_years()`, no signature/schema change —
no CR required per `CLAUDE.md`'s triviality bar): `sighting_years()` now
derives its glob pattern from `PATH_TEMPLATES["sightings"]` via
`.format(state_lower=..., year="*")`, the same template `sightings(year)`
already uses, instead of a separately hardcoded path fragment. See
`grouse_data.py`'s `sighting_years()`. Status: **CLOSED**.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug involves
path-template drift specifically (BUG-0001 is a spatial-bbox constant,
BUG-0002/0003/0004 are stale-superseded-file fix propagation). This is a
different mechanism — a single-file internal inconsistency between two
methods, not a cross-file duplication. Result: **none found**.

## 8. Preventive action
**PA-0003** (see `PREVENTIVE_ACTIONS.md`): any path/glob pattern that
should describe the same location as an existing `PATH_TEMPLATES` entry
must be derived from that same template, never re-hardcoded as an
independent string.
