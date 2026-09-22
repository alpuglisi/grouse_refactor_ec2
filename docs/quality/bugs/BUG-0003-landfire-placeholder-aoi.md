# BUG-0003: `download_landfire.py`/`_2`/`_3` still use placeholder Montana/N. California AOI coordinates

## 1. Description
The same three superseded LandFire download scripts also still contain the
original placeholder area-of-interest boxes (around Montana and Northern
California), which `download.py`'s own comments record as a previously
identified and fixed defect — replaced there with the real Maine/New
Hampshire/Vermont extents.

## 2. Where encountered
- `download_landfire.py:13-29`
- `download_landfire_2.py:11-27`
- `download_landfire_3.py:11-27`
- Contrast: `download.py:13-23`

## 3. What it caused to fail
Running any of the three older scripts downloads valid-looking rasters for
regions that have zero overlap with the project's actual sighting data
(Maine/New Hampshire/Vermont). This is silent data corruption in the sense
that it does not error — it produces plausible output that is geographically
useless for the analysis, and would only be caught by someone noticing the
coordinates don't match the project area.

## 4. What the defect was
`download_landfire.py:13-29` (and identically `_2`, `_3`) defines
`BOXES_COORDINATES` as a list of boxes centered near -114.1/47.1 (Montana),
-107.7/46.5, and -123.7/41.7 (Northern California) — none overlapping
ME/NH/VT.

`download.py:15-17` documents the fix explicitly:
```python
# Rebuilt from the actual sighting-data extent (was previously pointed at
# Montana/N. California test coordinates that never overlapped the ME/NH/VT
# sighting CSVs).
```
and replaces the placeholder list with a state-keyed dict:
`BOXES_COORDINATES = {"ME": ..., "NH": ..., "VT": ...}`.

## 5. Root cause analysis (Five Whys)
1. Why do 3 files still use Montana/N. California test coordinates? Because
   they were never updated after the placeholder-AOI bug was found and
   fixed in `download.py`.
2. Why wasn't the fix propagated? Same mechanism as BUG-0002: these are
   superseded copies that don't receive fixes applied to their successor.
3. Why does that matter for two separate bugs (endpoint + AOI) in the same
   files? Because both defects were fixed in the same rewrite (`download.py`
   replacing the older `download_landfire*.py` scripts) and neither fix
   was backported — one root cause produces multiple stale defects in the
   same abandoned files.
4. (See BUG-0002 §5 steps 3-5 for the rest of the causal chain — same root
   cause.)

**Root cause:** identical to BUG-0002 — superseded script versions are left
in the repository as runnable files after their successor fixes a defect,
with nothing preventing someone from running the stale, still-broken copy.
This bug and BUG-0002 are two independent defects that happen to share one
root cause and were fixed together in the same rewrite.

## 6. Corrective action
None implemented yet — documentation-only pass. Same remediation path as
BUG-0002 (delete or deprecate-and-backport). Status: **OPEN**.

## 7. Recurrence review
Searched `BUG_LOG.md`: **matches BUG-0002** — same root cause (stale
superseded script never receiving a backported fix), same files, found in
the same review pass. This is not treated as a "prior preventive action
that failed to prevent a recurrence" in the strict sense (no preventive
action existed yet when both were found — they were discovered together),
but per §4.3 of `CLAUDE.md` the preventive action for this bug does not
duplicate PA-0002 — it is covered by the same rule. No new preventive
action is added here; this bug is logged under the **same** PA-0002 as
BUG-0002.

## 8. Preventive action
Covered by **PA-0002** (see BUG-0002 and `PREVENTIVE_ACTIONS.md`) — no new
rule needed; this is a second, independent defect instance of the same
mechanism PA-0002 targets.
