# CR-0019 review, reviewer A, round 1 (first review, unrestricted scope)

- **CR reviewed:** `docs/quality/change-requests/CR-0019-common-year-floor.md`
  v2 (PROPOSED), HEAD `a89151f`, with `CR-0019-review-log.md` and
  `docs/quality/evidence/CR-0019/` (preregister.*, check_must_change.py,
  mc_selftest.*, reviewB/).
- **Reviewer:** A (correctness of diagnosis and fix). I did not write the CR.
  I looked at the earlier partial reviewer-A scratch in this directory
  (`analyse.*`, `pipeline_floor_run.py`, `wrong_tree*`) but did not rely on
  it. Every result below comes from my own runs. The working-tree change to
  `reviewA/wrong_trees.txt` was already there when I started. It is not mine.
- **Method:** read-only against the repository and `data/`. I made scratch
  runs under `/tmp/claude-1000/-home-ec2-user-grouse2/491a150a-…/scratchpad/`.
  A file listing (size and mtime) of `data/pipeline` and `data/negatives`
  was the same before and after my runs.

## Verdict: APPROVE WITH FOLLOW-UPS

0 BLOCKING, 0 MAJOR, 2 MEDIUM, 4 LOW.

## Independent re-derivation (what I verified, and how)

1. **Root cause.**
   - `sightings.py:23` and `ebird.py:20` set `START_YEAR = 2016`.
     `get_negatives.py:228-229` sets `--years` default `range(2020, …)`.
     Nothing reconciles the two.
   - `generate_negatives.draw_region_split` draws 1:1 against the positive
     count, so every count check passes.
   - `train.filter_by_year_gap` (`train.py:226-255`) is applied per class
     and per split in `build_datasets` (`train.py:330-341`). It removes only
     the positives' pre-2020 rows. The diagnosis is confirmed.
2. **Raster support: `YEAR_MIN = 2020` is the right floor.**
   `RegionData.raster_years` on disk (ME, NH and VT are identical):
   - evt, evh and sclass: 2022–2024.
   - evc, fdist, ch and cc: 2022–2025.
   - tcc: 2016–2023.
   - All other features: 2016–2025.

   At tolerance 2, LANDFIRE's first year (2022) makes 2020 the first
   accepted year and 2019 the last rejected one. The candidates are 2020–2024
   (265,212 rows, 0 null). The raw sighting files cover 2016–2024. So 2020 is
   both the negatives' acquisition floor and the tol-2 raster floor. The
   upper end is covered up to 2024 at tolerance 2: tcc ends at 2023, a gap
   of 1. Positives' `year` is each location's latest visit
   (`analyze_grouse.py:261-270`, `year == last_year` on 100 % of rows), so
   the floor keeps revisited locations at their latest year. That is
   consistent with the raster lookup.
3. **The pre-registration reproduces.** I ran a copy of `preregister.py`
   with `HERE` redirected to scratch and `ROOT` set to the repository.
   - The control passed.
   - `preregister.txt` is byte-identical.
   - All four `preregister_*.csv` are byte-identical to the committed files,
     so the `PRE_SHA` pins hold.
   - `data/` was untouched.
4. **The real pipeline gives the same result as the replay.** Pre-registration
   and MC self-test use the replay, so this is the independence check.
   - Setup: a scratch tree with the pipeline and negatives CSVs copied and
     everything else symlinked file by file, with no output path a symlink.
     I then ran the **real** `prepare_training_data.run` and
     `generate_negatives.run`.
   - The floor (`year >= 2020`) was injected on the evaluated sightings, for
     the positives script only. It is the same set as step 2 plus the floor,
     because row filters commute. The buffer and the envelope weights still
     read every year.
   - Result: counts `"2"` are 2,909 / 856 / 1,174 and `"6"` are
     2,854 / 827 / 1,128. The draw is exactly §4. No habitat
     `RuntimeError`.
   - `check_must_change.py --old <live> --new <scratch>`:
     **MC: PASS (42/42)**, MC0 included.
   - Conclusion: the change as specified (floor before thinning) gives the
     pre-registered P, B, C and N row for row, and in the pipeline's own
     file order.
5. **The train-time filter on the regenerated scratch tree** (real
   `train.filter_by_year_gap`, `discover_features` features):

   | tolerance | P dropped | N dropped |
   |---|---|---|
   | 2 | 0 | 0 |
   | 3 | 0 | 0 |
   | −1 | 0 | 0 |
   | 1 | 928 | 1,861 |

   This matches §2 and §4. The tol-1 asymmetry is real, so the refusal is
   justified (PA-0020(iv)).
6. **Callers of the refusal.**
   - `build_datasets` is called only by `train.py:1050`, `calibrate.py:356`
     (default tolerance 2, features from the checkpoint; a feature subset
     only loosens the check) and `bench_pipeline.py:96` (default).
   - No tracked caller passes 0 or 1.
   - `sweep/launch2.sh` and `sweep/launch3.sh` pass `-1`.
   - The CR-0009 history used `--max-year-gap 3`. That value is larger, so it
     is not refused.
   - `pretrain.py`, `smoke_test_training.py`, `tune_bins.py` and
     `diagnose_*` do not call the filter.
   - `tests/test_cr0012.py:381` mocks `standing_checks` before the filter.

   No legitimate caller breaks at tolerance ≥ 2 or −1 once the data is
   regenerated.
7. **E14 can fail on today's data and pass after.**
   - Today: P has 1,437 rows below 2020, so (a) FAILs. P's years are
     {2016..2024} against N's {2020..2024}, so (b) FAILs.
   - After: both sets are {2020..2024}, and (a) and (b) PASS (my real-pipeline
     tree).
   - Both are exact predicates.
8. **Numbers checked against my runs.** All of these match:
   - the 1,437 dropped positives, split ME 814, NH 256, VT 367;
   - 968/2,214 = 0.4372, which equals `calibration.json` `val_prevalence`
     0.4372177;
   - kept 4,795, removed 1,437, added 14;
   - B 3,861 → 3,205;
   - C: 501 split changes (207 / 294);
   - N: 4,808 kept, 1,424 removed, 1 added;
   - 48 new validation negatives were training negatives;
   - year AUC 0.6615;
   - 1b shortfall of 215 in 6 cells.
9. **Live-run ordering.**
   - The config sha changes at the merge, so `standing_checks` refuses from
     the merge until the new record exists.
   - `prepare_training_data.run` deletes the record before writing.
   - The outputs are exactly the 20 digested artifacts plus the manifest
     (10 + 10). `acceptance_split` writes the record and the OBS file. The
     backup list in deliverable 5 is therefore complete.
   - Restoring the files and reverting brings back the old config sha and the
     old record. Rollback is sound (see A5 for a git detail).
10. **A5 (one change per CR).** The inseparability argument holds: without
    the replay change, R1–R4 fail; without the pipeline change, E11, E14 and
    R fail. The `train.py` refusal is honestly described as separable-after
    and bundled. Compliant.

## Findings

### A1 — MEDIUM — `YEAR_MIN` filters the positives but only guards the negatives, so the refusal's "reviewed `YEAR_MIN` change" remedy fails the pipeline
- **Where:** CR §2, "Pool step 1, as amended" (a guard that raises on a
  non-null `year < YEAR_MIN`) and "`train.filter_by_year_gap`" (the remedy
  text). Scope: "one year floor for both classes, applied at selection".
- **Failure scenario.** After CR-0019, a user wants a stricter landscape
  match and runs `train.py --max-year-gap 1`.
  1. The refusal fires (928 P and 1,861 N) and suggests "a reviewed
     `YEAR_MIN` change".
  2. The natural value is `YEAR_MIN = 2021`: at tolerance 1, 2021 is the
     first year within 1 of LANDFIRE 2022, and tcc (to 2023) still covers
     2024.
  3. That value filters the positives at step 2, but pool step 1 then
     **raises** on the 99,744 raw 2020 candidates (of 265,212).
  4. So the remedy the message names cannot be carried out without either a
     code change to step 1 or a GBIF re-fetch. For the negatives, the "one
     floor at selection" is really an acquisition assumption plus a crash.
- **Why not BLOCKING:** it fails loudly and produces no wrong data. At
  `YEAR_MIN = 2020` it changes nothing today.
- **Suggested fix (either):**
  - (a) Make pool step 1 a symmetric **filter**: keep non-null
    `year >= YEAR_MIN`, and let null years fall through to step 7 as today.
    Today's counts and MC stay the same, because no candidate is below 2020.
    The Scope sentence then becomes literally true, and `YEAR_MIN` becomes a
    working selection knob for both classes. The acquisition-quota concern
    (`yr_cap`) stays with `get_negatives.py`'s default, which is already
    single-sourced from `YEAR_MIN`.
  - (b) Keep the guard, but correct the refusal message, the `regions.py`
    comment and §2: raising `YEAR_MIN` also requires changing negatives
    step 1 under a CR. Lowering it requires a re-fetch.

  Either way, add a `tests/test_cr0019.py` case for the chosen behaviour at
  a `YEAR_MIN` above the minimum candidate year.

### A2 — MEDIUM — §5 misattributes the residual and understates the no-network options; part of it is a per-class year-selection rule
- **Where:** CR §5; review log § Proposed bookkeeping (BUG-NEW-a
  "Cause: … `get_negatives.py` pass-1 order and positives' latest-visit
  year"). The claim "Supplying it needs more 2023–2024 negative candidates,
  i.e. a GBIF re-fetch … or a design decision on coarser matching".
- **Measured** (on the pre-registered P and N, read-only):
  - The positives' representative year is the **latest** visit
    (`analyze_grouse.py:261-270`); 37.1 % of P are multi-visit.
  - The negatives' representative year is the record with the **smallest
    gbif_id** (`generate_negatives.dedup_min_gbif_id`): 98.9 % of selected N
    carry their key's earliest year, and 11.4 % have a later year available.
  - Year→label AUC is 0.6615 as specified. It is 0.5584 if P uses
    `max(first_year, 2020)`, and 0.6125 if N uses its key's latest year.
  - A large part of the residual therefore comes from two different
    per-class representative-year rules. That is a time-axis selection
    asymmetry (PA-0020(i)/(ii)), not only acquisition supply. It can be
    addressed without network access.
- **Failure scenario.** The residual BUG is filed with only "pass-1 order /
  re-fetch / year-matched draw" as its remedy space. The follow-up CR then
  asks the user for a GBIF re-fetch decision when a no-network, reviewable
  alternative exists: harmonise the representative-year rule, e.g. latest
  year for both classes. It also leaves a PA-0020 instance unnamed.
- **Suggested fix.**
  - §5: state the representative-year rules as a measured contributor, with
    the figures above or re-measured by the author, and drop "needs a re-fetch"
    as the only route.
  - BUG-NEW-a: list both rules as candidate causes (PA-0016: hypotheses,
    each to be tested).
  - Deliverable 8: add both rules explicitly to the PA-0020 sweep items.

  No change to CR-0019's implementation is needed. The residual stays out of
  scope, correctly: it is a distribution problem, not support.

### A3 — LOW — the `tests/test_cr0012.py` fixture edit is a no-op as written
- **Where:** CR §3 "Existing fixtures": "`tests/test_cr0012.py`: candidate
  years `:593` move to ≥ `YEAR_MIN`".
- The candidate years there are already `rng.choice([2023, 2024, 2025])`
  (`tests/test_cr0012.py:593`). The sighting years (`:254`, `:551`) are
  2020–2025 as well.
- **Scenario:** the implementer searches for something to change and alters
  the fixture needlessly, or wrongly concludes that the floor is tested
  there.
- **Fix:** say that `test_cr0012.py` needs no year edit. Only the null-year
  rows (`:594`) and `:835-836` are relevant, and they stay. The "floor
  before thinning" and the step-2 tests then live only in
  `tests/test_cr0019.py`.

### A4 — LOW — E14(b) exact pooled set equality on the small synthetic acceptance fixture
- **Where:** CR §3 E14(b) and the "Existing fixtures" edit
  (`tests/test_acceptance_split.py:227,291,319`: years `rng.integers(2019,
  2024)`, to move to ≥ `YEAR_MIN`).
- **Scenario.** On the real data every year has hundreds of rows per class.
  On the fixture, after thinning, windowing and a 1:1 draw, a year present in
  P can be absent from N by chance. The **correct** fixture tree then FAILs
  E14(b). The seed is fixed, so the failure is deterministic, not flaky. It
  pushes the deliverable-2 author to tune seeds, or to weaken the check.
- **Fix:** deliverable 2 builds fixture years deterministically, so that the
  correct tree's P and N year sets are equal by construction. Add a test that
  asserts this for the correct tree, alongside the attack-row existence
  asserts.

### A5 — LOW — the rollback "revert the merge" leaves a revert-of-merge on `main`
- **Where:** deliverable 6, "revert the merge".
- **Scenario.** The first live attempt fails at step 5 and the merge is
  reverted. A later retry that merges the (fixed) CR-0019 branch again
  silently omits every commit already reachable from the reverted merge.
  git needs a revert-of-the-revert. The result is a pipeline without the
  floor, or a replay without E14, that MC and R1 would then flag. That is
  wasted work, not bad data.
- **Fix:** run steps 2–6 with the CR-0019 branch checked out in the live
  working tree, and fast-forward or merge `main` only after step 6 passes.
  On failure, restore the files and check out `main`. The refusal window is
  unchanged. Alternatively, state the revert-of-revert step explicitly.

### A6 — LOW (tracked follow-up; owner BUG-0060) — §6 checkpoint warning is prose only
- **Where:** CR §6.
- **Scenario:** `calibrate.py --model grouse_cr0009.pth` after the
  regeneration. 48 of the 962 new validation negatives are that model's
  training negatives (I reproduced the count), and nothing refuses the run.
- The CR states this, and BUG-0060 owns the mechanical refusal. I record it
  so the tracker entry names this CR's split as a concrete instance. No
  change to CR-0019 is required.

## Not findings (checked, no issue)
- **Floor placement.** It is before thinning. The real-pipeline run shows the
  14 added positives, and MC catches an after-thin tree (reviewer B's trees;
  the earlier reviewer-A scratch agrees). The buffer and the envelope weights
  still use every sighting year; `gn.read_csv` is a separate binding and is
  unaffected by the positives-step change.
- **Pool guard.** No-op today (0 null years, 0 below 2020 in 265,212 raw rows).
- **E11 and the manifest.** `measured_constants()` is shared by both sections,
  so `YEAR_MIN` appears in both. E11(e) parses the `regions.py` literal via
  AST.
- **Refusal vs standing checks.** `standing_checks` runs before the filter
  and, with E14(a), already refuses any pre-`YEAR_MIN` split row. After the
  change, the refusal can only fire for tolerance < 2 or if raster vintages
  change. Both are the intended loud failures.
- **Residual scope.** Correctly out of scope as a distribution defect with
  its own BUG, subject to A2's wording.
- **A5 (one change per CR).** Compliant; see item 10 above.
- **MC design.** Self-test 42/42. My real-pipeline tree is 42/42.
  Reviewer B's 23 wrong trees all fail or are documented as covered by R1/R4.
  Satisfies PA-0021(a)/(b).

## Evidence (scratch, not committed)
- Pre-registration re-run: `…/scratchpad/prereg/` (txt and 4 CSVs,
  byte-identical to the committed files).
- Real-pipeline floored tree: `…/scratchpad/tree/`. Log in
  `…/scratchpad/run_floor.log`, MC output in `…/scratchpad/mc_real.txt`
  (`MC: PASS (42/42 checks pass)`).
- A2 measurements: inline Python on `preregister_P.csv`, `preregister_N.csv`,
  `evaluated_sightings_*.csv` and `gbif_negatives_*.csv` (read-only).
