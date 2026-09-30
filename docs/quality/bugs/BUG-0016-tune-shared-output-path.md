# BUG-0016: `tune.py` and `tune_bins.py` silently overwrite each other's output

## 1. Description
`tune.py` and `tune_bins.py` are diverged duplicate scripts (both
docstring-titled `tune_envelope_bins.py`) that sweep different variable
sets — `tune.py` has a `"slope"` variant `tune_bins.py` lacks;
`tune_bins.py` has `"ch"`, `"cc"`, `"fdist"` variants `tune.py` lacks — but
both write their results to the exact same output file with no
disambiguation.

## 2. Where encountered
`tune.py:225` and `tune_bins.py:236`: both
`out_csv = f"data/pipeline/bin_tuning_{region}.csv"`.

## 3. What it caused to fail
Whichever script is run last silently overwrites the other's results at
`bin_tuning_{region}.csv`, with nothing in the output file indicating
which variable set (and thus which subset of `RASTER_FEATURES` —
`ch`/`cc`/`fdist` are real pipeline features per `grouse_data.py`) produced
it. A user running `tune.py` (e.g. out of habit, or because it sorts first
alphabetically) gets a sweep silently missing 3 of the 7 real habitat
variables, and if run after `tune_bins.py`, clobbers the more complete
result with no error or warning.

## 4. What the defect was
`tune.py`'s `VARIANTS` includes a `"slope"` key using `_slope_fixed`
(absent from `tune_bins.py`); `tune_bins.py`'s `VARIANTS` includes `"ch"`,
`"cc"`, `"fdist"` keys (absent from `tune.py`). `tune_bins.py`'s comment
("slope/aspect removed from the sweep: dropped from the feature set")
indicates a later decision than `tune.py`'s comment ("aspect removed...")
— `tune.py` still sweeps slope despite its own comment only mentioning
aspect as removed, an internal inconsistency that, combined with
`tune_bins.py`'s added ch/cc/fdist variants, indicates `tune_bins.py` is
the later, more complete script. Neither file marks the other as
superseded, and both target the identical output path.

## 5. Root cause analysis (Five Whys)
1. Why do the two scripts silently clobber each other's output? Because
   both write to the same hardcoded path with no variant-set marker.
2. Why do they sweep different variable sets in the first place? Because
   `tune_bins.py` was forked from (or evolved past) `tune.py` to add
   ch/cc/fdist and drop the since-abandoned slope variant, without the two
   being reconciled into one script or one clearly superseding the other.
3. Why does the shared output path matter more here than in the
   BUG-0002/0003/0004 cases? Because there, the stale copy either failed
   outright (loud) or downloaded wrong-geography data (silent but into its
   own distinct output). Here, the failure mode is two *live, runnable*
   scripts sharing one *mutable* output artifact — a distinct hazard: not
   "the stale copy still has the old bug" but "either copy can destroy the
   other's most recent output with no record of which ran last."
4. Why wasn't this caught in the original review pass? Because the
   original pass's download/negatives-focused agents didn't cover
   `tune.py`/`tune_bins.py` in enough depth to diff them against each
   other — a follow-up review pass assigned to these files specifically
   found it.

**Root cause:** two independently-runnable scripts sweep different,
non-overlapping variable sets but share a single mutable output path with
no marker for which produced it — neither file is a strict superset of
the other's *content*, unlike the BUG-0002/0003/0004 cases, so the fix
can't simply be "backport the missing bit," it has to address the shared-
path hazard itself.

## 6. Corrective action
Fixed directly (trivial: a warning print only, no behavior change to the
actual sweep logic — no CR required): `tune.py` now prints a warning at
the start of `main()` naming the shared-output-path hazard and recommending
`tune_bins.py`. This does not change `tune.py`'s sweep behavior or delete
the `slope` variant (that would risk silently dropping intentionally-kept
scope without a domain-owner decision) — it makes the hazard visible
before the destructive overwrite happens, which is the concrete failure
this bug describes. Verified: file parses.

**Status: OPEN for full resolution** — the underlying design question
(should `tune.py`'s `slope` variant be merged into `tune_bins.py`, should
one file be deleted, should output paths be disambiguated by variant set —
which would be a schema change to `PATH_TEMPLATES["bin_tuning"]`,
requiring a CR) needs a domain-owner call, not an engineering guess. The
warning banner is a stopgap that prevents the silent-clobber failure mode
from being *unannounced*, not a structural fix.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **related to BUG-0002/
0003/0004/0015** (the general "duplicate script drift" mechanism, PA-0002)
but a **distinct failure mode** — those bugs are "the stale copy still has
the old defect"; this one is "two live copies share a mutable output
artifact with no ownership marker," which PA-0002's wording ("delete or
mark deprecated") doesn't fully cover, since neither file is simply
"superseded" here — each has content the other lacks.

**Prior-preventive-action failure analysis:** PA-0002 is **too narrow**
for this specific sub-case: it assumes one copy is deprecated in favor of
a superseding other, but here the two copies have diverged in complementary
(not strictly nested) ways, so "delete or deprecate" doesn't apply cleanly
without a content-reconciliation decision this session can't make alone.

## 8. Preventive action
**PA-0014** (new, see `PREVENTIVE_ACTIONS.md`) — extends PA-0002 for the
case where duplicate scripts have diverged in non-overlapping (not
strictly superseding) ways: such scripts must never share a single mutable
output path without a visible marker (in the filename, or a written
manifest/header row) recording which script/variant-set produced it. Where
they currently do, add a loud warning until a domain-owner reconciles the
scripts or disambiguates the output paths (a schema change, needing a CR).
