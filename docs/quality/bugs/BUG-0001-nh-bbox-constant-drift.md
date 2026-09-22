# BUG-0001: New Hampshire bounding-box constant has drifted between duplicated copies

## 1. Description
The `NH` entry in the `BOXES`/`BOXES_COORDINATES` bounding-box constant is
hardcoded independently in at least 6 files. Two inconsistent values exist:
`-70.614` (in `clean.py`, `download.py`) vs. `-70.600` (in `audit.py`,
`analyze_grouse.py`, `download_more.py`, `download_rev.py`).

## 2. Where encountered
- `clean.py:48`
- `audit.py:21`, `analyze_grouse.py:21` (these two files are byte-for-byte
  identical, md5-confirmed)
- `download.py:23`
- `download_more.py:20`
- `download_rev.py:22`

## 3. What it caused to fail
Silent geographic inconsistency between scripts that are meant to describe
the same NH area of interest:
- `clean.py`'s `assign_spatial_blocks` computes a different grid origin/
  extent for NH than `audit.py`/`analyze_grouse.py` use, for the ~1.5 km
  sliver between -70.614 and -70.600 — silently skewing which records fall
  into which spatial train/val block for sightings in that strip.
- `download.py` vs. `download_more.py`/`download_rev.py` would download NH
  rasters with a slightly different eastern extent depending which script
  is run — sighting points in the disputed strip would be in-bounds for one
  script's raster and out-of-bounds (nodata/index error downstream) for the
  other.
No crash in either case — purely silent data/behavior divergence.

## 4. What the defect was
`clean.py:48`:
```python
"NH": (-72.626, 42.605, -70.614, 45.398),
```
`audit.py:21` / `analyze_grouse.py:21`:
```python
"NH": (-72.626, 42.605, -70.600, 45.398),
```
`clean.py:44`'s own comment already flags the exact risk that materialized:
`# Same boxes as analyze_grouse.py / download.py - kept in sync manually`.
`download.py:23` carries `-70.614`; `download_more.py:20` and
`download_rev.py:22` carry `-70.600`.

## 5. Root cause analysis (Five Whys)
1. Why do two scripts disagree on NH's extent? Because the `NH` tuple is
   hardcoded separately in each file.
2. Why is it hardcoded separately instead of shared? Because there is no
   shared constants module — each script was written (or copied) as a
   self-contained file.
3. Why did the values diverge instead of staying in sync? Because at least
   one file's box was edited later (e.g. a buffer-tuning pass) without a
   mechanism to propagate the edit to the other copies.
4. Why was there no propagation mechanism? Because "kept in sync manually"
   (the codebase's own words) is a human-memory process with no check.
5. Why was a human-memory process considered sufficient? Because the
   duplication was never flagged as a defect until this review — it's easy
   to overlook static tuples as a coupling point between files.

**Root cause:** the `BOXES`/`BOXES_COORDINATES` region-extent constant is
duplicated by copy-paste across independently-maintained files with no
single source of truth, so edits to one copy don't propagate to siblings.

## 6. Corrective action
None implemented yet — this review pass is documentation-only per the task
that produced it. Fixing this requires a CR (see `CLAUDE.md` §1) to
introduce a single shared module (e.g. `regions.py`) exporting `BOXES`,
imported by every script that currently hardcodes it, plus a decision on
which of `-70.614` / `-70.600` is the intended value (needs a domain-owner
call, not an engineering guess — the two values differ by real geography).
Status: **OPEN**.

## 7. Recurrence review
Searched: no prior BUG entries existed before this review pass (`BUG_LOG.md`
was empty). Checked against the other findings from this same review round:
this is the first instance found of the "duplicated constant drifts across
copies" mechanism. Result: **none found** (this is BUG-0001, nothing prior
to check against). Note for future recurrence checks: BUG-0002/0003/0004
below share a *related* but distinct mechanism (stale superseded script
files rather than independently-edited constants) — cross-referenced there.

## 8. Preventive action
**PA-0001** (see `PREVENTIVE_ACTIONS.md`): never duplicate a geographic/
spatial constant (bounding box, CRS, buffer distance) across files —
extract it to one shared, imported module.
