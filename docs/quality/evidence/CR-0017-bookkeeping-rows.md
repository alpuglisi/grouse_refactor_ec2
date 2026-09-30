# CR-0017 proposed bookkeeping rows (pipeline side; not yet filed)

Written by the deliverable 3/4 implementer. The implementer does not edit
`BUG_LOG.md` or `PREVENTIVE_ACTIONS.md`; the lead files these at
deliverable 8, after the live run (deliverable 6) succeeds. The rows
follow the proposal in `CR-0017-review-log.md` § Proposed bookkeeping
rows; the lead allocated BUG-NEW-a as **BUG-0064**.

## Implementation facts the rows cite
- Pipeline change: commit `7424166` on branch
  `worktree-agent-aa9cd9861e95c4aaf` (base: CR-0015 head `3add80b`).
  - `regions.py`: `_county_polygons()` (the one county reader, shared by
    `_state_polygons()` and D), `_domain_5070()`, `domain_edge_m(x, y, *,
    domain=None)`.
  - `generate_negatives.py`: `domain_edge_drop_mask(lon, lat)`; pool
    step 6 drops `in_buffer | at_edge`; the log prints (a), (b only) and
    the overlap.
- Scratch-tree run (deliverable 4, pipeline part):
  `docs/quality/evidence/CR-0017/scratch/`. Step 6: (a) 9,720,
  (b only) 89, both 20. Final pool 22,187 -> 22,099 (88 removed; one of
  the 89 step-6 (b)-only rows would have been dropped later by step 7/8).
  MC (old = live, new = scratch): PASS, all of MC0-MC5. Second run
  byte-identical.

## BUG_LOG.md, BUG-0050 row update
"... remediation: CR-0017 (pool step 6 also drops candidates within
`BUFFER_M` of the sightings' acquisition-domain edge, ME∪NH∪VT;
`regions.domain_edge_m`, `generate_negatives.domain_edge_drop_mask`,
commit `7424166`); status FIXED" — FIXED only once deliverable 6 (live
regeneration, MC PASS, 19/19 GATEs) is done.

## BUG_LOG.md, new row BUG-0064
- date: 2026-09-30;
- symptom: the negatives' 300 m buffer is blind at the NY and MA state
  lines, affecting 49 pool candidates and 11 selected negatives
  (`docs/quality/evidence/CR-0017/preregister.txt`);
- root cause: the buffer source ends at the acquisition-domain edge
  (ME∪NH∪VT), and BUG-0050's evidence took the national border as that
  edge (PA-0020(v) not applied);
- remediation: CR-0017 (same change as BUG-0050, commit `7424166`);
- status: FIXED at CR-0017 deliverable 6 (pending).

The BUG-0064 investigation, the recurrence review against BUG-0050 /
PA-0023 and the proposed PA (extends PA-0023) are as drafted in
`CR-0017-review-log.md` § Proposed bookkeeping rows; nothing in the
implementation changes them.

## PA-0023 Swept? cell addendum
- BUG-0050 FIXED (CR-0017);
- NY and MA instance: BUG-0064, FIXED (CR-0017);
- KDE: BUG-0051 (Canada, NY and MA edges), owned by its own CR.

## No new defect found during implementation
- `tests/test_cr0012.py`'s synthetic tree has only a placeholder county
  zip (its `verify_partition` is patched). Step 6 (b) now reads the county
  file for D, so the module patches `regions._domain_5070` with a far-away
  box (`setUpModule`). This is a fixture change, not a defect: the
  generator fails closed on the missing file (pyogrio `DataSourceError`)
  rather than skipping (b).
