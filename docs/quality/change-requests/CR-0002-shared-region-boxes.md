# CR-0002: Extract the region bounding-box constant to one shared module

## Scope
Fix BUG-0001: replace 6 independently-hardcoded copies of the `BOXES`/
`BOXES_COORDINATES` dict (in `clean.py`, `audit.py`, `analyze_grouse.py`,
`download.py`, `download_more.py`, `download_rev.py`) with imports from one
new shared module, `regions.py`, resolving the current `-70.614`/`-70.600`
NH value conflict to a single value.

## Why now
BUG-0001 found the NH box's `max_lon` has drifted to two different values
across these 6 files with no shared source of truth — silently producing
inconsistent spatial-block assignment (`clean.py`) and inconsistent raster
download extents (`download.py` vs. `download_more.py`/`download_rev.py`).
`clean.py`'s own comment ("kept in sync manually") already documents the
intended invariant this CR restores mechanically.

## The change
1. New file `regions.py`:
   ```python
   """Single source of truth for the project's state bounding boxes.
   (min_lon, min_lat, max_lon, max_lat), ~0.1 deg buffer around each
   state's observed sighting extent. See BUG-0001 for why this exists as
   its own module instead of being duplicated per-script."""
   BOXES = {
       "ME": (-71.158, 42.889, -66.852, 47.555),
       "NH": (-72.626, 42.605, -70.600, 45.398),
       "VT": (-73.510, 42.632, -71.422, 45.112),
   }
   ```
2. In each of the 6 files, replace the locally-defined `BOXES =` /
   `BOXES_COORDINATES =` dict literal with:
   ```python
   from regions import BOXES as BOXES_COORDINATES   # (or `as BOXES`, matching
                                                      # the file's existing name)
   ```
   keeping each file's existing local variable name (`BOXES` in
   `clean.py`/`audit.py`/`analyze_grouse.py`, `BOXES_COORDINATES` in the
   `download*.py` files) so no other line in any of these files needs to
   change.

## NH `max_lon` value decision (-70.600 vs -70.614)
This repository checkout has no `data/` tree (gitignored, not present
locally), so the actual sighting-data extent that these boxes are meant to
buffer around **cannot be verified from this environment**. Choosing
`-70.600` because it's the majority value (4 of 6 files: `audit.py`,
`analyze_grouse.py`, `download_more.py`, `download_rev.py`) vs. `-70.614`
(2 of 6: `clean.py`, `download.py`) is a **weak signal, not a verified
answer** — `clean.py`'s own comment claims it should match `analyze_grouse.py`
*and* `download.py`, and those two don't even agree with each other, so
majority count doesn't prove correctness, only prevalence.
**Accepted risk:** proceeding with `-70.600` as the default in the shared
module (smallest change from majority) but flagging explicitly that the
project owner should confirm this against the real NH sighting-data extent
before relying on it for a production run, and update `regions.py` (one
place) if `-70.614` (or another value) turns out correct.

## Impact on other parts of the system
- `clean.py`, `audit.py`, `analyze_grouse.py`, `download.py`,
  `download_more.py`, `download_rev.py` all now import from `regions.py`
  instead of defining their own copy. Any other constant in those `BOXES`
  dicts (ME, VT) is unchanged in value — only the single source of truth
  changes, not the numbers for ME/VT.
- Anything downstream that reads `BOXES`/`BOXES_COORDINATES` from these
  modules (e.g. `import analyze_grouse` elsewhere) is unaffected: the name
  and shape of the dict at that attribute path is unchanged.
- Once `data/` exists in a real run, block assignments and raster download
  extents for NH will change slightly for points in the -70.614..-70.600
  strip, compared to whichever script a prior run used. This is the
  intended fix (making it consistent) but is a real, visible behavior
  change for anyone re-running the pipeline on NH data after this lands.

## Risk assessment
**Risk level: medium.** Main risk is the unverified NH value decision
above (accepted, with the domain-confirmation flag). Secondary risk: import
path correctness — `regions.py` must be importable from each of the 6
files' working directory (all are flat root-level scripts in the same
directory, so a plain `from regions import BOXES` works without path
manipulation, consistent with how these scripts already import each other,
e.g. `grouse_data.py`'s reference to `analyze_grouse.py`).

## Test plan
- `python -c "import ast; [ast.parse(open(f).read()) for f in ['regions.py','clean.py','audit.py','analyze_grouse.py','download.py','download_more.py','download_rev.py']]"`
  to confirm all 7 files still parse.
- `python -c "from regions import BOXES; print(BOXES)"` to confirm the
  module loads and the dict is well-formed.
- For each of the 6 consuming files, `python -c "import <module>; print(<module>.BOXES or .BOXES_COORDINATES)"`
  to confirm the imported name resolves to the same dict as `regions.BOXES`.
- Cannot validate against real sighting data in this environment (no
  `data/` tree present) — flagged above as the accepted risk.

## Deliverables
- [ ] Create `regions.py` with the single `BOXES` dict (`-70.600` for NH).
- [ ] Update `clean.py` to import `BOXES` from `regions.py`.
- [ ] Update `audit.py` to import `BOXES` from `regions.py`.
- [ ] Update `analyze_grouse.py` to import `BOXES` from `regions.py`.
- [ ] Update `download.py` to import `BOXES_COORDINATES` from `regions.py`.
- [ ] Update `download_more.py` to import `BOXES_COORDINATES` from `regions.py`.
- [ ] Update `download_rev.py` to import `BOXES_COORDINATES` from `regions.py`.
- [ ] Update `BUG-0001-nh-bbox-constant-drift.md` corrective action and
      `BUG_LOG.md` status.
- [ ] Flag the unverified NH value decision to the user as a standing
      follow-up (verify against real sighting data).

## Out of scope
- Verifying the correct NH extent against real sighting data (not possible
  in this environment; flagged to the user).
- Extending `regions.py` to hold other constants beyond `BOXES` (no other
  duplicated constant was identified in this review round; revisit if one
  is found).
- `audit.py`/`analyze_grouse.py` being fully duplicate files beyond this
  one constant (noted in BUG-0001 as a structural risk, not addressed by
  this CR, which only touches the `BOXES` definition).

## Reviewer verdicts
See independent review below (§ Review).
