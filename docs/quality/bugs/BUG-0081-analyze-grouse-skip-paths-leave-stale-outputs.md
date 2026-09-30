# BUG-0081: `analyze_grouse.analyze_region` skips a region with `return None`, the run exits 0, and the previous run's `evaluated_sightings_*` / `envelope_metrics_*` stay in place for the downstream scripts to digest

> Found by the 2026-09-30 static code review at `3b3e7d1`. Same outcome
> class as BUG-0049 (fixed in `generate_negatives.py` by CR-0012) and
> BUG-0070, reached without an exception handler.
> **Status: OPEN; owner: lead; fix per function (trivial) or one small
> CR.**

## 1. Description
`analyze_region` has five designed skip paths (no box overlap, no
rasters for a feature, every record dropped at extraction, no record of
the region's own state after the `state == region` restriction, every
record non-vegetated) that `return None` after printing "Skipping". The
region's two output CSVs are written only at the very end of the
function, after the diagnostic map. `__main__` loops over every region
without a `try`, prints "skipped (see log above)" in the summary and
exits 0. A skipped region therefore keeps whatever
`data/pipeline/evaluated_sightings_{R}.csv` and
`envelope_metrics_{R}.csv` the previous run wrote, and
`prepare_training_data.py` / `generate_negatives.py` read and digest
those files as if they were current.

## 2. Where encountered
- Skip paths: `analyze_grouse.py:251-252` (inside `clip_to_region`,
  reached from `:741`), `:758-759`, `:786-787`, `:836-837` (no record of
  the region's own state after the `state == region` restriction),
  `:882-884` (returns `valid, None` before the writes). *Correction
  2026-09-30 (CR-0025 review, A1/B1): the `:836-837` path was missing
  from this list, and `:251` was cited without its call site.*
- Writes: `analyze_grouse.py:1095` (map), `:1099-1100` (the two CSVs).
- Loop: `analyze_grouse.py:1117-1126`.
- Consumers: `prepare_training_data.py:371-373` (reads and digests
  `evaluated_sightings_{R}.csv` into the manifest),
  `generate_negatives.py:409-416` (buffer source), `:247` (envelope
  metrics).

## 3. What it caused to fail
Scenario: sightings are refreshed (new years) and, for one region, the
`sclass` raster is temporarily absent or fails validation. That region's
positives, its contribution to the pooled 300 m buffer and its envelope
metrics come from the previous vintage while the other two regions are
new. `prepare_training_data.py` digests the stale file and acceptance
passes: the gates verify consistency between the files, not their
provenance. The `:882-884` path also returns with `valid` fully computed
and unwritten. Not observed on the live data; the class is confirmed
from the control flow.

## 4. What the defect was
`analyze_grouse.py:756-759`:
```python
    missing = [f for f, yrs in feature_years.items() if not yrs]
    if missing:
        print(f"  [!] No rasters found for {missing} in {region}. Skipping.\n")
        return None
```
`analyze_grouse.py:785-787`:
```python
    if len(valid) == 0:
        print(f"  [!] All {region} records dropped during extraction. Skipping.\n")
        return None
```
`analyze_grouse.py:1094-1100`:
```python
    map_name = f"data/maps/grouse_diagnostic_map_{region}.png"
    fig.savefig(map_name, dpi=300)
    plt.close(fig)
    print(f"Map saved as '{map_name}'")

    valid.to_csv(f"data/pipeline/evaluated_sightings_{region}.csv", index=False)
    env_df.to_csv(f"data/pipeline/envelope_metrics_{region}.csv", index=False)
```
`analyze_grouse.py:1117-1126`:
```python
    results = {}
    for region in REGIONS_TO_RUN:
        results[region] = analyze_region(region, sightings_all, evt_xwalk)
    ...
        if r is None:
            print(f"  {region}: skipped (see log above)")
```

## 5. Root cause analysis (Five Whys)
1. *Why does a downstream script read a stale file?* The skip leaves the
   old file at the path the script reads.
2. *Why is the old file still there?* Outputs are written only at the
   end; a skip writes nothing and removes nothing.
3. *Why does the run exit 0?* The loop stores `None` and reports it as
   a summary line; nothing raises.
4. *Why did the PA-0027 sweep and lint not flag it?* PA-0027 and its
   lint (CR-0018) enumerate exception handlers; these are designed
   `return None`s with no `except`.
5. *Why no rule?* PA-0027 was written for broad handlers; the outcome
   it forbids (a unit of a batch skipped, run exits 0, outputs claim
   completeness) was never stated independently of the handler syntax.

**Root cause:** per-region outputs are written only after every stage
completes, and a designed skip returns into a loop that continues and
exits 0 without removing or marking the unit's previous outputs; the
standing rule is keyed to exception syntax and cannot see it.

## 6. Corrective action
**None yet.** Proposed: on every skip path, raise `MissingDataError`
(propagates, exit non-zero) or delete/rename the region's two outputs
and make `__main__` exit non-zero when any region was skipped; write the
CSVs before the map stage so a plotting error cannot lose them. Each
change is confined to one function, so trivial fixes are possible; the
exit-code change is a small CLI behaviour change and may warrant a CR.
Status: **OPEN**. Owner: lead.

**CR drafted 2026-09-30:** `docs/quality/change-requests/CR-0025-analyze-grouse-no-stale-outputs-on-skip.md` (v3, approved by agent quorum after two review rounds; nothing implemented).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "skip",
"stale", "exit 0", "continue", "region".

**Matches:** BUG-0049 (`generate_negatives.py` skipped a region on any
error; stale files pooled by `train.py`), BUG-0054/BUG-0055/BUG-0070
(silent unit skips in diagnostics and download), PA-0027 (their rule),
BUG-0071 (probe error turned into a vintage skip).

**Prior-preventive-action failure analysis.** PA-0027 covers the same
outcome but binds it to broad exception handlers; the CR-0018 lint walks
`except` clauses. A designed skip without a handler is invisible to
both. Category: too narrow (mechanism keyed to syntax, not outcome).

## 8. Preventive action
**PA-0038** (extends PA-0027): a designed skip of a unit of a batch (a
region, a vintage, a year, a file) in a script that writes files must
(a) leave no stale output for that unit at any path a downstream script
reads (delete, rename, or refuse), (b) make the run exit non-zero or
print a final INCOMPLETE line naming the unit, and (c) never be reached
after a partial write. Enforcement: review; a lint for `return`/
`continue` inside a batch loop of a file-writing script is a CR
candidate.

**Sweep (§3.5), designed unit skips in file-writing scripts:**
`analyze_grouse.py` (five sites, this bug);
`generate_treemap_features.discover_vintages` (BUG-0091);
`download_tcc_nlcd.sighting_years`, `diagnose_wetland`,
`diagnose_training`, `diagnose_water_bias` (fixed under BUG-0054/0055/
0070); `prepare_training_data.py` and `generate_negatives.py` (pooled,
no skip path); `get_negatives.py` (an undersupplied species is printed
and the file stays partial by design, recorded, not filed).

## Cross-references
BUG-0049, BUG-0054, BUG-0055, BUG-0070, BUG-0071, BUG-0091, PA-0027,
PA-0038.
