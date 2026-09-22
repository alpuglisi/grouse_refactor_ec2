# BUG-0002: `download_landfire.py`/`_2`/`_3` still call the retired LandFire GPServer endpoint

## 1. Description
`download_landfire.py`, `download_landfire_2.py`, and `download_landfire_3.py`
all submit jobs to the old ArcGIS GPServer `submitJob` URL, which
`download.py` (the successor script) documents as retired in 2025 and
already replaced there.

## 2. Where encountered
- `download_landfire.py:50`
- `download_landfire_2.py:46`
- `download_landfire_3.py:46`
- Contrast: `download.py:35` (`BASE_URL = "https://lfps.usgs.gov/api/job"`)

## 3. What it caused to fail
Running any of the three older scripts today fails every job submission
against a dead endpoint — the script produces zero output, looping through
every region/year/feature combination and printing submit errors for each.

## 4. What the defect was
`download_landfire.py:50` (and identically `_2`, `_3`):
```python
SUBMIT_URL = "https://lfps.usgs.gov/arcgis/rest/services/LandfireProductService/GPServer/LandfireProductService/submitJob"
```
`download.py:35` carries the corrected replacement, with its own comment
documenting the fix:
```python
# --- NEW API base (the old ArcGIS GPServer/submitJob path was retired in 2025) ---
BASE_URL = "https://lfps.usgs.gov/api/job"
```

## 5. Root cause analysis (Five Whys)
1. Why do 3 files call a dead endpoint? Because they still hold the
   pre-2025 URL that `download.py` replaced.
2. Why weren't they updated when `download.py` was fixed? Because the fix
   was applied only to the file being actively edited at the time.
3. Why wasn't the fix propagated to the other files? Because they are
   superseded copies (`_2`, `_3` version-numbered iterations) left in the
   repository with no deprecation marker or removal.
4. Why weren't the superseded copies removed once `download.py` existed?
   Because there is no process step that requires deleting/deprecating a
   prior script version when its successor lands.
5. Why is there no such process step? Because change control for this
   repository (prior to this QMS policy) had no requirement to consider the
   "impact on other parts of the system" — sibling copies of a script were
   not treated as something a fix needs to reach.

**Root cause:** superseded script versions (`_2`, `_3`, and the original)
are left in the repository as runnable files after a fix lands in a newer
version, with nothing to prevent someone from running the stale, still-
broken copy.

## 6. Corrective action
None implemented yet — documentation-only pass. Recommended fix (for a
future CR): either delete `download_landfire.py`/`_2`/`_3` if `download.py`
fully supersedes them, or if any are still needed for a distinct purpose,
port the endpoint fix into each and add a header comment marking them
superseded/deprecated in favor of `download.py`. Status: **OPEN**.

## 7. Recurrence review
Searched `BUG_LOG.md`: BUG-0001 is the only prior entry, and its mechanism
(independently-edited duplicated *constants*) differs from this one
(entirely *stale superseded script files* not receiving a fix at all).
Result: **none found** — this is the first instance of the "stale
superseded copy never gets the fix" mechanism. (BUG-0003 and BUG-0004 below
are further instances of this same mechanism, found in the same review
round — see their own recurrence sections, which reference this bug.)

## 8. Preventive action
**PA-0002** (see `PREVENTIVE_ACTIONS.md`): when a script is copied/
versioned to apply a fix or add a feature, the superseded original must be
deleted or explicitly marked deprecated in the same change — never left as
a runnable copy carrying the old defect.
