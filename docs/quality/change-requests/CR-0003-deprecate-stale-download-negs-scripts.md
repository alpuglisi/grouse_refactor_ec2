# CR-0003: Deprecate stale superseded scripts (BUG-0002, BUG-0003, BUG-0004)

## Scope
Add a loud, fail-fast deprecation banner to `download_landfire.py`,
`download_landfire_2.py`, `download_landfire_3.py`, and `gen_negs.py`,
pointing to their fixed successors (`download.py`, `generate_negatives.py`)
and exiting immediately instead of running with a known defect.

## Why now
BUG-0002/BUG-0003 found `download_landfire.py`/`_2`/`_3` still call a
retired API endpoint and still use placeholder Montana/N. California AOI
coordinates, both already fixed in `download.py`. BUG-0004 found
`gen_negs.py` lacks a non-vegetated sampling cap already fixed in
`generate_negatives.py`. All four are stale, independently-runnable
duplicate scripts left in the repository with no marker distinguishing
them from their maintained successor — someone running the wrong one by
name gets silent failure or silently degraded output.

## The change and why it's a deprecation banner, not a line-level backport
Initial plan was to backport the specific fixes (endpoint URL, AOI
coordinates, sampling cap) directly into the stale files. On inspection,
`download_landfire.py`/`_2`/`_3` use an entirely different API paradigm
than `download.py` — the old ArcGIS GPServer `submitJob`/`esriJobSucceeded`
polling contract (job IDs, `results.Output_File`, `messages[].type`) vs.
`download.py`'s newer `lfps.usgs.gov/api/job` REST contract. Swapping just
the URL constant would submit requests in the old request/response shape
to a new endpoint that doesn't speak that protocol — not a fix, a
different, unverified bug. This environment has no network access to the
live USGS LFPS API to validate a full rewrite of the request/response
handling against, so attempting one blind is a real risk of shipping an
unverified new defect while claiming to have fixed an old one.

**Chosen fix instead:** make these 3 files impossible to silently run
broken — a banner at the top of `main`/`__main__` that prints why the
script is deprecated and exits immediately, rather than looping through
every region/year/feature combination failing (BUG-0002) or succeeding
against the wrong geography (BUG-0003). This directly resolves both bugs'
"silent failure" impact without introducing new, unverifiable logic.

`gen_negs.py` is different: its sampling cap fix (`NONVEG_MAX_FRAC`) is a
same-paradigm, mechanically portable change — both files already share the
same `is_nonveg`/`weight`/`block_id`/`split` column structure over the same
candidate-pool dataframe, so `generate_negatives.py`'s ~35-line two-pool
sampling block (a `habitat_pool`/`nonveg_pool` split, a `weighted_take`
helper, and a shortfall top-up) can be ported as-is, not just a one-line
constant swap — see CR-0003-B below for why it's backported directly
rather than only deprecated.

### CR-0003-A: `download_landfire.py`, `_2.py`, `_3.py` — deprecation banner
Add, immediately inside `if __name__ == "__main__":` (before calling
`download_landfire_data()`):
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
    print("\nAll tasks completed!")
```
(The unreachable original call is left in place, not deleted, so a future
reader who removes the banner sees exactly what ran before — an explicit,
visible choice rather than a silent deletion.)

### CR-0003-B: `gen_negs.py` — backport the non-vegetated sampling cap
Port `generate_negatives.py`'s `NONVEG_MAX_FRAC = 0.30` cap and the
pool-split sampling logic it enables into `gen_negs.py`, replacing the
uncapped `p = pool['weight'] / pool['weight'].sum()` weighted sampling.
This is a same-paradigm, line-for-line portable change (both files already
share the same pool/weight dataframe structure) — see BUG-0004 for the
exact before/after. Also add a short header comment noting `gen_negs.py`
is superseded by `generate_negatives.py` and recommending the latter for
new runs, without a hard `SystemExit` (unlike CR-0003-A, this script is
now correct after the backport, not merely guarded — no reason to block
running it).

## Impact on other parts of the system
- None of these 4 files is imported by any other module (confirmed via
  grep — `download.py` calling its own `download_landfire_data()` function
  is a same-file self-reference, not an import of `download_landfire.py`).
  Only someone invoking these scripts directly (`python download_landfire.py`,
  `python gen_negs.py`) is affected.
- `download_landfire.py`/`_2`/`_3`: after this change, running them exits
  immediately with an explanatory message instead of attempting downloads
  — a deliberate, visible behavior change (was: silently broken; now:
  loudly refuses to run).
- `gen_negs.py`: after this change, its sampled negative sets will differ
  from previous runs (fewer non-vegetated candidates, more habitat
  candidates) — the intended fix, matching `generate_negatives.py`'s
  already-accepted behavior.

## Risk assessment
**Risk level: low.** CR-0003-A only adds an early exit to otherwise-broken
scripts nobody should be running successfully today anyway. CR-0003-B
ports an already-proven, same-paradigm fix from a sibling file with
identical data structures. **Accepted risk:** neither can be validated
against live APIs/data in this environment (see Test plan).

## Test plan
- CR-0003-A: `python download_landfire.py` (and `_2`, `_3`) should print
  the deprecation message and exit with code 1, verified by running each
  and checking the exit code and stdout, without needing network access
  (the exit happens before any request is made).
- CR-0003-B: `python -c "import ast; ast.parse(open('gen_negs.py').read())"`
  to confirm it still parses; a diff-level comparison against
  `generate_negatives.py`'s equivalent block to confirm the ported logic
  matches exactly (same `NONVEG_MAX_FRAC`, same pool-split structure).
  Cannot validate against live GBIF data or a real candidate pool in this
  environment (no `data/` tree present) — flagged as an accepted test gap.

## Deliverables
- [x] Add deprecation banner + `SystemExit(1)` to `download_landfire.py`.
- [x] Add deprecation banner + `SystemExit(1)` to `download_landfire_2.py`.
- [x] Add deprecation banner + `SystemExit(1)` to `download_landfire_3.py`.
- [x] Backport `NONVEG_MAX_FRAC` cap + pool-split sampling into `gen_negs.py`.
- [x] Add a superseded-by comment header to `gen_negs.py`.
- [x] Update `BUG-0002`, `BUG-0003`, `BUG-0004` corrective-action sections
      and `BUG_LOG.md` statuses.

## Out of scope
- A full rewrite of `download_landfire.py`/`_2`/`_3` to speak the new
  `lfps.usgs.gov/api/job` protocol (would need live-API validation this
  environment can't provide; if the project wants these 3 files fully
  working rather than deprecated, that's a separate, larger CR with a real
  test plan against the live USGS endpoint).
- Deleting the 4 files outright (kept, so history/behavior stays
  inspectable, and so a future CR upgrading them has something to diff
  against).
- `audit.py`/`analyze_grouse.py`'s duplicate-file structural risk (noted
  in BUG-0001, not touched here).

## § Review

**Reviewer (independent agent, re-derived from current source): APPROVE.**
Confirmed via grep that `download_landfire.py`/`_2`/`_3` all use the old
ArcGIS GPServer contract (`SUBMIT_URL`, `esriJobSucceeded`, `Output_File`)
vs. `download.py`'s `lfps.usgs.gov/api/job`, supporting the
deprecation-over-blind-rewrite decision; confirmed the `__main__` blocks
match exactly where the banner is inserted; confirmed none of the 4 files
is imported elsewhere. For CR-0003-B, confirmed `gen_negs.py`'s current
uncapped sampling and `generate_negatives.py`'s `NONVEG_MAX_FRAC`
pool-split share the same column structure, so the port is mechanically
sound.

One non-blocking wording note: this CR's "Why now" section originally
described CR-0003-B's port as "same pool/weight/sampling API, just adding
a cap," which undersold that the actual ported block is a ~35-line
two-pool rewrite (`habitat_pool`/`nonveg_pool` split plus a `weighted_take`
helper and shortfall top-up), not a one-line cap addition.

**Disposition: accepted, corrected below.** The "Why now" wording is
tightened to describe the port's actual size without changing the risk
level (still low — mechanically sound, same data structures, no new
external dependency).

**Author sign-off:** approved for implementation as revised.
