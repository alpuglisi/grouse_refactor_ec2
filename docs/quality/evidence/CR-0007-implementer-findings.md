# CR-0007 implementer findings (deliverables 2–6, 2026-09-30)

Where the approved v9 spec could not be implemented as written, or left a
choice open. Spec changes are **not** made here; each item names what an
amendment would have to decide.

## F1 — BLOCKING for P6: tracked evidence scripts enter the P6 scan after approval

**What.** `python check_partition.py` (acceptance run, `CR-0007-gates.txt`)
fails P6 with three problems, all outside the §1 re-point table:

```
docs/quality/evidence/CR-0007-r7/build.py:14: region-code sequence literal
docs/quality/evidence/CR-0007-r7/feats.py:9: region-code sequence literal
docs/quality/evidence/CR-0007-r7/lib.py:4: region-code sequence literal
```

**Why.** The P6 scan set is "`git ls-files '*.py'` minus basenames
`inv_*`/`res_*` and `tests/`" (CR §Acceptance, "P6 scan";
`check_partition.p6_scanned_files`). The nine
`docs/quality/evidence/CR-0007-r7/*.py` scripts (round-7 reviewer A's
attack scripts) became git-tracked in `f5e5ee4` (CR-0013 deliverables 0, 1,
2a), **after** v9 was approved at `f8fafbc`/`6619bdd`. At approval they
were untracked, so the round-9 count (24 lines) and both reviewers' "P6 is
passable" verdicts were correct then.

**Why the implementer did not fix it.** Every remedy is a spec or gate-code
change:
- re-point the scripts to `regions` — edits frozen evidence (they record
  what reviewer A ran), and they are not in the §1 table;
- add them to `P6_EXEMPT` — `tests/test_shared_constants.py` pins the
  exemption set (`EXPECTED_EXEMPT`, "growth of this set is a review item");
- exclude `docs/` (or `docs/quality/evidence/`) from the scan set — changes
  the §Acceptance "P6 scan" definition.

The third seems the most natural (evidence is a record, not live code;
compare `inv_*`/`res_*`), but that is for the amendment's reviewers.

**Consequence.**
- P6 FAILS in the acceptance run; P1–P5, P7, P8 pass.
- The `@unittest.expectedFailure` marker on
  `tests/test_shared_constants.RepositoryTree.test_repository_tree` was
  **left in place**. Deliverable 2 says to remove it, but without it the
  suite fails for this reason alone. It still does its job: once the
  amendment lands, the test passes and the marker is reported as an
  "unexpected success", which forces its removal. The last line of the P6
  problem list is the only thing it currently catches.
- Deliverable 2 is otherwise complete: the §1 table's files have no
  remaining violations (`p6_problems` lists only the three lines above).

## F2 — minor count error in the spec (no action)

§Acceptance P6 "today" and the v9 disposition A1/B1 say "24 literal lines
in 21 files". At `f8fafbc` the scanner finds 24 lines in **20** files
(recomputed from `scan_repository` minus the three r7 files). The line
count, which is what P6 pins, is right.

## F3 — choices the spec left open (implemented; stated for review)

1. **In-state batch size.** §2 says box points are "drawn in batches from
   one generator". Implemented as box-sized batches of `n_samples` (lons
   then lats per batch, as the old single draw did), keeping in-state
   points in draw order until `n_samples` exist
   (`analyze_grouse.in_state_background_points`; `MAX_BG_BATCHES = 20`).
   Batches used: 2 per region (in-state shares 0.477–0.540).
2. **`verify_partition` return type.** "Returns the records" is implemented
   as a DataFrame (`longitude`, `latitude`, `state`, `polygon_state`,
   index = input position); `in_state` returns a boolean array.
3. **Non-veg report.** §2 moves the `nonveg_flagged_{region}.csv` write to
   after the restriction. The flag computation and its printed data-quality
   report moved with it, so the printed counts describe the file written
   (own-state rows). The per-row flag is unchanged. The written file now
   also carries `spatial_density`, `spatial_zone` and `region`, because it
   is written after the KDE stage.

## F4 — files of other CRs touched because the §1 table names them

`generate_negatives.py` and `prepare_training_data.py` (both later rewritten
by CR-0012) and `repair_coverage_rasters.py` (CR-0010) were edited: the §1
table names them. Only imports and constant bindings changed. No value
changed and no CLI default changed.

## F5 — PA-0026 sweep finding outside §3's scope (BUG-0048, not remediated)

The output-path sweep for BUG-0031's new PA (PA-0026) found
`legacy/download_landfire.py`, `_2.py`, `_3.py`. They write
`data/landfire/*.tif`, the directory `download_rev.py` owns. Their guard is
a `raise SystemExit(1)` inside `if __name__ == "__main__":` (not the first
statement), and it tells the user to run `download.py`, itself a stale
copy. `CLAUDE.md` §3.5 says to remediate sweep findings, but CR-0007 v9 §3
names exactly three files, so adding three more guards is a scope change.
Filed as **BUG-0048, OPEN**, owner CR-0007's author (natural to carry in
the same amendment as F1). `tune.py` (the other hit) is the already-open
BUG-0016; no new BUG.

## F6 — BUG-0029 closure wording: approved spec vs a later tracker item

CR-0007 v9 deliverable 6 says: BUG-0027 and BUG-0029 corrective action
"membership: CR-0007; split and draw: CR-0012"; fixed when CR-0012 lands,
closed after CR-0009. A later tracker item
(`docs/quality/CR-0007-0008-OPEN-ISSUES.md:139`, from CR-0015 round-1 B8)
asks whoever executes CR-0007 d6 to write BUG-0029 as "membership: CR-0007;
split and draw: CR-0012; assumed negatives: CR-0015", FIXED when CR-0015
deliverable 7b passes. CR-0015's status line still reads PROPOSED (v2.2)
(round-3 reviewer sign-offs were committed in `d6dfe09`/`e9092f8` while this
work was in progress; no author/user approval is recorded), so its closure
rule is not yet approved. **BUG-0029 was written with the approved v9 wording**
(`docs/quality/bugs/BUG-0029-…md` §6, `BUG_LOG.md` row). The tracker item is
left open for its owner (CR-0007's author). If CR-0015 is approved, the
BUG-0029 §6 status line and its `BUG_LOG.md` row need a one-line edit.

## Deliverable 7 — not done (by instruction)

The road-file re-points (`generate_road_distance.py:116,122,173`,
`check_road_dist.py:472`) and the removal of their two P6 exemptions wait
for CR-0016, which changes `check_road_dist.py` (implemented in `363b543`
while this work was in progress), and then for CR-0014's closure. `diagnose_road_bias.py` (not a CR-0014 file) was
re-pointed under deliverable 2 as the table says.
