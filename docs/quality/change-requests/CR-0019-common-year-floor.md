# CR-0019: One year floor for both classes, applied at selection; the train-time year-gap filter refuses instead of dropping

**Status: PROPOSED (v1), 2026-09-30.** Verdicts and dispositions:
`CR-0019-review-log.md`. This document states only current intent.

## Scope
Select positives only from `YEAR_MIN = 2020`, the first year both label
classes were acquired, at CR-0012 positives step 2 (before thinning), so
the split files carry one year floor for both classes and the 1:1 draw is
made against the positives that actually train. Make
`train.filter_by_year_gap` refuse, instead of silently dropping, any
split-file record. Extend CR-0013's acceptance to match (new exact gate
E14), then regenerate the split files.

## Fixes
- **BUG-0034**, root cause (disjoint per-class temporal support) and
  consequences (a) (broken 1:1 balance and calibration prevalence) and
  (e) (designs built around the drop). Consequence (b) is fixed only in
  part: see § Residual.
- The BUG-0034 items in the tracker: the build-time assert (§8 of the
  BUG) and the thin-order interaction (CR-0012 A9).

## Why now
BUG-0034 is the only live instance behind PA-0020. Every CR since has
worked around it, and the next retrain (§4) should be on data without it.

**Measured on today's accepted artifacts** (the CR-0017 live files; their
digests equal `data/pipeline/acceptance_record.json`, sha256
`9d5ad0a9…`). Every number in this CR comes from
`docs/quality/evidence/CR-0019/preregister.txt`, produced by
`preregister.py` in the same directory. BUG-0034's own figures (1,973 of
8,365) are from the pre-CR-0012 data and are superseded by these.

| | positives (P) | negatives (N) |
|---|---|---|
| rows | 6,232 | 6,232 |
| year range | 2016–2024 | 2020–2024 |
| year < 2020 | 1,437 (23.06 %): ME 814, NH 256, VT 367 | 0 |
| dropped by `filter_by_year_gap`, tolerance 2 (default) | 1,437 | 0 |

- After the filter, validation prevalence is 968 / 2,214 = 0.4372. That
  is exactly `val_prevalence` in `data/calibration/calibration.json`
  (the CR-0009 model's Platt fit), against a documented 0.5.
- The dropped set is exactly `{year < 2020}`: every feature has a raster
  within ±2 years of 2020 and later (LANDFIRE from 2022), none of 2019
  and earlier.

## The change

### 1. Root cause
The two classes are acquired from the same GBIF dataset
(`4fa7b334-…`; all 43,024 raw sighting rows carry it, and it is
`get_negatives.EOD_DATASET_KEY`) with different year floors:
`sightings.py:23` / `ebird.py:20` (`START_YEAR = 2016`) and
`get_negatives.py:228-229` (`range(2020, …)`). No step reconciles the
two. The negatives are drawn 1:1 against the positive count
(`generate_negatives.draw_region_split`), so every count check passes,
and `filter_by_year_gap` (`train.py:226-255`) then removes only the
positives' pre-2020 years at training time (BUG-0034 §5).

The fix moves year selection to where the classes are selected, with one
constant for both, and turns the train-time filter into a check.

### 2. Pipeline (normative; amends CR-0012 §2)
**Constant.** `regions.py` gains `YEAR_MIN = 2020`, with a comment: the
first year both classes were acquired, and the first year with every
`FEATURE_SPEC` raster within `train.py`'s default `--max-year-gap` of 2.
It is the only literal (PA-0025). `get_negatives.py`'s `--years` default
becomes `range(YEAR_MIN, today + 1)` (same value; single-sourced;
nothing is fetched).

**Positives step 2, as amended.** Raise `ValueError` if any row of the
region's evaluated sightings has a null `year`. Keep the rows with
`~nonveg_landcover` **and** `year >= YEAR_MIN`. The manifest count `"2"`
is the rows after both conditions; the manifest schema is unchanged.

- *Placement.* Step 2 is before step 4 (thinning), so a pre-2020 point
  can no longer win the thin order and suppress a post-2020 neighbour.
  This is the CR-0012 A9 interaction: re-thinning adds 14 positives that
  today's thin drops.
- *Selection, not acquisition.* `evaluated_sightings_R` is unchanged,
  and so are its two other consumers: pool step 6(a) (the 300 m buffer
  still uses every sighting, 2016 included: a 2018 grouse location is
  still not evidence of absence) and the envelope metrics and binners
  (pool step 9). `sightings.py`/`ebird.py` keep `START_YEAR = 2016` for
  those two uses.

**Pool step 1, as amended.** After loading each region's candidates,
raise `ValueError` if any row has a null `year` or `year < YEAR_MIN`. This
is a guard, not a filter: all 265,212 raw candidates are 2020–2024 today,
so no row and no count changes. A later re-fetch with older years then
fails loudly and forces a reviewed `YEAR_MIN` change, instead of silently
widening one class.

**Draw.** Unchanged: per region and split, `n = round(n_pos × NEG_RATIO)`
against the new positives.

**`train.filter_by_year_gap`.** Same verdict per year as today. If any
row would be excluded, raise `SystemExit` naming the region, the class
and split (`what`), the row count, the years, the tolerance, and the
remedy (`--max-year-gap -1` or a larger value, or a reviewed `YEAR_MIN`
change). Otherwise return the frame unchanged (same return expression as
today). Records with a null year are still kept (unchanged; E14 means
the split files have none). The signature and the name stay (the name is
cited in CRs and evidence scripts); the docstring, the `build_datasets`
comment and the `--max-year-gap` help say that the flag now checks and
that `YEAR_MIN` selects.

Why refuse and not drop: after this change a tolerance of 1 would drop
928 of 4,809 positives and 1,861 of 4,809 negatives, recreating an
asymmetric per-class effect at training time (PA-0020(iv)). Refusal is an
exact predicate (PA-0021: exact preferred), and it keeps what trains
equal to what CR-0013 accepted (PA-0029).

**Code.**

| file | change |
|---|---|
| `regions.py` | `YEAR_MIN = 2020` and its comment |
| `prepare_training_data.py` | step 2 as above; module docstring step 2; `measured_constants()` gains `YEAR_MIN` |
| `generate_negatives.py` | pool step 1 guard; module docstring step 1 |
| `get_negatives.py` | `--years` default from `regions.YEAR_MIN` |
| `train.py` | `filter_by_year_gap` refuses; docstring, `build_datasets` comment, `--max-year-gap` help |
| `tests/test_cr0019.py` (new) | § Test plan |
| `tests/test_shared_constants.py` | pin `YEAR_MIN` |

### 3. Acceptance (amends CR-0013; normative for the replay author)
**Config (`docs/quality/acceptance_split.json`).**
- `constants.YEAR_MIN`: 2020. E11(c) then requires it in both manifest
  sections' constants.
- `regions_py.names.YEAR_MIN`: E11(e) then requires the `regions.py`
  literal to equal it.
- The `GATE_SECTION_SHA256` pins in `tests/test_acceptance_split.py` are
  updated; that update is part of this CR's review.

**Replay.** Positives step 2 and pool step 1 exactly as §2 (the replay
raises `ReplayError` where the pipeline raises). R1–R4 then check the
change row for row, and R1/R3's count checks read the new `"2"` count.

**New gate E14 (exact).**

| id | set, pooling | predicate |
|---|---|---|
| E14 | P combined, N combined; C (full run) | every row's `year` is non-null, integral and `≥ YEAR_MIN` (config) |

- E14 joins the standing subset on P and N (pandas only; `standing_checks`
  runs before every `build_datasets`). C is covered by the record digests,
  as for E3(C).
- E14 is where PA-0020(ii)'s build-time support comparison lives for the
  time axis: both classes' supports lie in `[YEAR_MIN, ∞)`, and the
  train-time refusal (§2) makes that support the one that trains.
- E9 is unchanged: its per-(region, split) count predicate still holds.

**Attack rows** (CR-0013 § Attacks; `tests/test_acceptance_split.py`,
synthetic fixture). Each names the fixture rows it needs; the test
asserts they exist, so no attack passes vacuously (PA-0021(a)).

| attack | fixture rows required | must fail |
|---|---|---|
| No floor (step 2 unchanged) | ≥ 1 habitat positive with `year < YEAR_MIN` that survives the window and the thin | E14, R1, R2 |
| Floor after thinning | a pair closer than `MIN_SPACING_M`: the `year < YEAR_MIN` member first in thin order, the other `≥ YEAR_MIN` | R1 (E14 passes) |
| Floor off by one (`year > YEAR_MIN`) | ≥ 1 habitat positive with `year == YEAR_MIN` that survives the thin | R1, R2 |
| Floor applied to the sightings (source-level cut, so the buffer shrinks) | ≥ 1 candidate within `BUFFER_M` of a `year < YEAR_MIN` sighting only, that survives steps 7–10 and is drawn | R3, R4 |
| Floor on the train split only | ≥ 1 `year < YEAR_MIN` positive in a validation block | E14, R1, R2 |

A unit test also checks that the replay raises on a candidate with
`year < YEAR_MIN` and on one with a null year.

**Must-change gate MC (PA-0021(b); one-off, for this regeneration).**
`docs/quality/evidence/CR-0019/check_must_change.py --old <pre-CR tree>
--new <post-CR tree>`, committed before approval (CR-0011 A3); its
checks are in its docstring. It reads the pre-registered outputs
(`preregister_P.csv`, `_B.csv`, `_C_split.csv`, `_N.csv`):

| check | what it pins | a no-op fails? | a deletion fails? |
|---|---|---|---|
| MC0 | old tree = the CR-0017 live record copy (else the pre-registration is stale) | – | – |
| MC1 | P: exact rows (key, split, block_id, year); kept rows byte-identical except the pre-registered split changes | yes | yes |
| MC2 | B: equal to the pre-registered table | yes | yes |
| MC3 | C: same rows and order; only the pre-registered `split` changes | yes | – |
| MC4 | N: exact rows (key, split, `is_nonveg`); equal to C on shared columns; label 0; order; count = P per (region, split) | yes | yes |
| MC5 | train/val files are the combined file's lines by split | – | – |

**Pre-registration validity.** `preregister.py` runs CR-0013's replay
(`acceptance_split.Replay`, written by a separate agent from the CR-0013
text), not the pipeline, subclassed only at positives step 2. Its
**control** first requires the unmodified replay to reproduce today's P,
B, C and N (keys, split, `block_id`), and aborts otherwise; it passed.
`mc_selftest.py` emits the predicted tree to a scratch directory: MC
PASSes on it (39/39) and FAILs with the live tree as NEW (a no-op), in
`mc_selftest.txt`. A reviewer's wrong-tree runs are deliverable 1.

### 4. What the change does to the data (pre-registered)
| region, split | P today | P after | P today after the tol-2 filter | N after |
|---|---|---|---|---|
| ME train | 2,922 | 2,291 | 2,278 | 2,291 |
| ME val | 738 | 563 | 568 | 563 |
| NH train | 840 | 634 | 630 | 634 |
| NH val | 239 | 193 | 193 | 193 |
| VT train | 1,224 | 922 | 919 | 922 |
| VT val | 269 | 206 | 207 | 206 |
| **total** | 6,232 | 4,809 | 4,795 | 4,809 |

- **P:** 4,795 kept, 1,437 removed (exactly the pre-2020 rows), 14 added.
- **B:** 3,861 → 3,205 positive-occupied blocks: 656 vanish (they held
  only pre-2020 positives), none appear, 7 flip val → train, none flip
  train → val. 8 kept positives move val → train; none move train → val.
- **C:** same 22,099 rows; 501 change split (207 train → val, 294 val →
  train), all in blocks that lost their positives and now take the md5
  rule.
- **N:** 4,808 kept, 1,424 removed, 1 added. 48 of the new validation
  negatives were training negatives before.
- **Balance:** prevalence 0.5000 in both splits with no filter;
  `filter_by_year_gap` at tolerance 2 drops 0 of either class.

### 5. Residual (not fixed here)
Within 2020–2024 the two classes' year **distributions** still differ
(N front-loaded on 2020: 1,861 of 4,809; P peaks in 2022). Year alone
predicts the label at AUC 0.6615 after the change (0.6578 today after the
filter). This is BUG-0034 consequence (b)'s remainder.

Year-matching the draw (per region, split and year) would remove it by
construction, but today's pool cannot supply it: 6 of 30 cells are short
of habitat candidates (215 in all; ME train 2024 −70, VT train 2024 −77;
`preregister.txt` § REJECTED OPTION 1b). Supplying it needs more
2023–2024 negative candidates, i.e. a GBIF re-fetch (network,
outward-facing, a user decision) or a design decision on coarser
matching. It is a separate defect (distribution, not support) and is
proposed as its own BUG, owned by a future CR (review log § Proposed
bookkeeping).

### 6. Retrain decision: no retrain under this CR
- `grouse_cr0009.pth` is not retrained here. A **follow-up CR** (id
  allocated by the lead; CR-0009's shape) retrains, refits calibration
  and records a new validation baseline on the post-CR-0019 split.
- CR-0009's baseline (AUC 0.7783, AP 0.6851 at prevalence 0.4372) stops
  being comparable: prevalence moves to 0.5 (AP moves with it by
  construction), and the validation set changes (§4). `CHANGELOG.md` says
  so.
- **Until that retrain, `calibrate.py` must not be run on
  `grouse_cr0009.pth`.** 48 of the new 962 validation negatives were its
  training negatives, and nothing refuses a checkpoint fitted under
  another split (BUG-0060, open). The existing `calibration.json` and
  maps stay as they are; `predict.py` reads no split file. `CHANGELOG.md`
  and the tracker carry the warning.

## Alternatives considered
| option | verdict |
|---|---|
| **(1) One floor, at selection, for both classes; filter refuses** | **Chosen.** No network, no new data. Removes the disjoint support and the train-time asymmetry; training positives +14 vs today's post-filter set. |
| (1b) As (1), plus a year-matched draw | Rejected for now: infeasible from today's pool (§5). Its own CR after a supply decision. |
| (1c) Floor derived at run time from raster availability and `--max-year-gap` | Rejected: couples the data pipeline to a training flag; the split files would change with a CLI value. `YEAR_MIN` is one reviewed constant, and the refusal catches a mismatch. |
| (2) Re-fetch negatives from 2016 | Rejected: a GBIF re-fetch (network, outward-facing, credentials); recovers **0** training positives (no raster within ±2 of 2016–2019 for LANDFIRE, and LF2020 non-topo products are retired, `download_rev.py:51-58`); and `get_negatives.py`'s `yr_cap = sp_cap / len(years)` would spread the pool into years the filter discards. |
| (3) Make `filter_by_year_gap` balance-restoring (subsample negatives at training time) | Rejected: a run-time producer of training rows that no file gate sees (PA-0029); calibration and training would read a set CR-0013 never accepted; the vintage support stays disjoint in every unfiltered consumer. |
| (4) Relax `--max-year-gap` | Rejected: gives 2016 sightings a 2022 landscape, the thing the filter exists to prevent. |

## Impact
- **Data (deliverable 6):** every P, N, B and C file, both manifest
  sections and `acceptance_record.json` are rewritten; the OBS reference
  file is recalibrated (`--calibrate`). `evaluated_sightings_*`, the
  envelope metrics, the raw candidates and every raster are unchanged.
  The pre-CR files are backed up first.
- **Acceptance:** `acceptance_split.py`, its config and its tests change.
  The config sha256 changes, so `standing_checks` refuses all training
  until the new full run writes a record.
  - **Refusal window.** Deliverables 2–3 are committed on an unmerged
    CR-0019 branch and merged only at deliverable 6 step 1, immediately
    before the live run. The window is from that merge to the new record
    (minutes). Before the merge, `train.py`/`calibrate.py` on the working
    branch are unaffected; merging the `train.py` change alone would
    refuse every run on today's files, which is why it merges with the
    data.
  - `prepare_training_data.py` itself removes the negatives manifest
    section and the record (its step 6), so the refusal also covers the
    run's intermediate state.
- **Models:** §6.
- **Other consumers:** `analyze_grouse.py`, the envelope metrics and the
  buffer keep every sighting year (§2). `tune_bins.py` and the
  `diagnose_*` scripts that read the split files see floored positives.
  `bench_pipeline.py` calls `build_datasets` with the default tolerance
  (no-op after the change). `smoke_test_training.py` does not call it.
- **CR texts:** pointer lines in CR-0012 §2 (positives step 2, pool
  step 1) and CR-0013 (E-table, standing subset, § Attacks): "amended by
  CR-0019". `ARCHITECTURE.md` (the `filter_by_year_gap` sentence) and
  `CHANGELOG.md` are updated.
- **Coordination:** BUG-0068 and the BUG-0069 site at
  `acceptance_split.py:2620` are pending fixes in the same file ("after
  CR-0017 merges"). Whichever lands second rebases and re-pins the PA-0027
  lint digests (`tests/test_pa0027_lint.py`).

## One change per CR (CR-0011 A5)
The deliverables span pipeline code, acceptance design, data
regeneration and bookkeeping. They cannot land separately:
- The pipeline change without the replay change fails R1–R4, so no
  record is written and `standing_checks` refuses all training.
- The replay change without the pipeline change fails E11, E14 and R1–R4
  on today's files (deliverable 2 shows it).
- The `train.py` refusal without the regeneration refuses every run on
  today's files (1,437 positives); the regeneration without the refusal
  leaves a tolerance of 1 or 0 free to recreate the asymmetry (§2).
- The regeneration is how they land together; bookkeeping closes the BUG.

The retrain is split out (§6), as CR-0009 was from CR-0012. The
year-matched draw is split out (§5): it needs a decision this CR cannot
make.

## Risk: MEDIUM
Every training file is regenerated and the validation set changes.

| risk | mitigation |
|---|---|
| The pipeline and the replay disagree | Exact R1–R4 replay; MC pins every output row against an independent pre-registration; either fails loudly, nothing is accepted silently |
| Floor in the wrong place (after thinning, at the source, off by one, one split only) | Attack rows (§3); MC1/MC2 exact |
| Habitat pool undersupplied after the change (`RuntimeError`) | Targets only fall (every (region, split) target is lower than today's); the pool is unchanged except 501 split labels. Checked in the scratch run (deliverable 4) |
| A regenerated split used with the old model (leakage in calibration or evaluation) | §6 warning in `CHANGELOG.md` and the tracker; retrain follow-up CR; BUG-0060 (open) owns the mechanical refusal |
| A live run that fails part-way | Deliverable 6's order and restore rule |
| The refusal breaks a workflow that passed `--max-year-gap 0` or `1` | It refuses with the remedy in the message. No caller in the tree passes those values; the untracked `sweep/launch*.sh` pass `-1` (disabled), which after the change trains on the same rows as the default, because the split files hold no year below `YEAR_MIN` |
| Loss of 1,423 negatives (22.8 %) relative to today's files | Accepted: 1:1 is the documented design, and those negatives balanced positives that never trained. Batch composition was already restored by `StratifiedBatchSampler`; calibration is what changes |

## Test plan
**Validatable here:**
- **`tests/test_cr0019.py`** (synthetic):
  - positives step 2 drops `year < YEAR_MIN`, keeps `year == YEAR_MIN`,
    raises on a null year;
  - the floor precedes thinning: a pre-floor point first in thin order
    does not suppress its post-floor neighbour;
  - pool step 1 raises on a candidate with a null year or
    `year < YEAR_MIN`;
  - pool step 6(a) still drops a candidate within `BUFFER_M` of a
    pre-floor sighting only;
  - `filter_by_year_gap` raises when any row would be excluded (message
    names region, what, count, years); returns the frame unchanged
    otherwise; `-1` disables.
- **Acceptance tests (deliverable 2):** E14 unit tests; the five attack
  rows and the replay-raises test; the config pins; the existing suite.
- **Today's real files, read-only (deliverable 2):** E14 FAILs (P, 1,437
  rows: ME 814, NH 256, VT 367); E11 FAILs (no `YEAR_MIN` in the
  manifest constants); R1–R4 FAIL; every other gate passes.
- **Scratch-tree real-data run (deliverable 4):** CSVs copied, rasters and
  county zip symlinked, no output path a symlink; run
  `prepare_training_data.py` then `generate_negatives.py` then
  `acceptance_split.py`: 20/20 GATEs; MC PASS with `--old` the live tree;
  a second run byte-identical; on the scratch tree, `build_datasets`
  (via `bench_pipeline.py` or a direct call) drops 0 rows at tolerance 2
  and refuses at tolerance 1.
- **Suites unchanged otherwise:** `tests/test_cr0012.py`,
  `tests/test_cr0017.py`, `tests/test_shared_constants.py`,
  `tests/test_pa0027_lint.py`, `tests/test_nodata_zero_lint.py`,
  `tests/test_acceptance_split.py`.
- **PA-0021(a):** a reviewer builds wrong trees (no-op, deletion, floor
  after thinning, floor at the source, off-by-one) and correct trees, and
  records MC's verdicts (deliverable 1). For E14 and the attack rows, the
  code reviewer re-runs the attack suite and checks each required fixture
  row exists.

**Not validatable here:**
- The model-quality effect (no retrain, §6).
- Whether the residual within-epoch year imbalance (§5) is learned by a
  retrained model: it needs the retrain and a seed-varied null (BUG-0039's
  lesson).
- Whether 2016–2019 locations visited only then are different habitat:
  they are excluded, not measured.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (CR-0011 A3), reviewed with this CR:
      `docs/quality/evidence/CR-0019/preregister.py`, `preregister.txt`,
      the four `preregister_*.csv`, `check_must_change.py`,
      `mc_selftest.py`, `mc_selftest.txt`; plus a reviewer's PA-0021(a)
      wrong-tree runs of MC, recorded in the evidence directory.
- [ ] 2. Acceptance changes (§3) on an unmerged CR-0019 branch, by a fresh
      agent that does not also write deliverable 3 (CR-0013 rule 4):
      `acceptance_split.py`, the config, the tests; suite passes; the
      read-only run on today's files gives exactly the expected FAILs
      (evidence `acceptance_prefix.txt`).
- [ ] 3. Pipeline and `train.py` changes (§2) and `tests/test_cr0019.py`
      on the same branch; the suites in § Test plan pass.
- [ ] 4. Scratch-tree real-data run (§ Test plan); evidence under
      `docs/quality/evidence/CR-0019/scratch/`.
- [ ] 5. Preconditions, recorded before any write under `data/`: no other
      CR is mid-way through a data write; the live artifacts equal the
      CR-0017 record (MC0). Back up the 20 digested artifacts, the
      manifest, the record and the OBS file to
      `/home/ec2-user/grouse_backup/CR-0019/` (mirroring `data/…`),
      sha256 verified; MC0 passes with `--old` = the backup.
- [ ] 6. Live run, in order: (1) merge the CR-0019 branch;
      (2) `prepare_training_data.py`; (3) `generate_negatives.py`;
      (4) MC, old = backup, new = live: PASS; (5) `acceptance_split.py`:
      20/20 GATEs, record written; (6) `acceptance_split.py --calibrate`.
      On any FAIL in (2)–(6): restore every backed-up file (sha256
      verified), record the failure, commit no data evidence, revert the
      merge, stop. On success commit the evidence, the record copy and the
      OBS file.
- [ ] 7. Pointer lines in CR-0012 §2 and CR-0013 (§ Impact);
      `ARCHITECTURE.md`; `CHANGELOG.md` entry: the data change, the new
      prevalence, CR-0009's baseline no longer comparable, and "do not run
      `calibrate.py` on `grouse_cr0009.pth` against this split" (§6).
- [ ] 8. Bookkeeping (review log § Proposed bookkeeping): BUG-0034
      corrective action and status; `BUG_LOG.md` row; the residual BUG
      (§5) filed; PA-0020 Swept? cell (BUG-0034 live instance fixed, the
      source-axis item it owns resolved, sweep by mechanism for any other
      per-class year selection, incl. `train.sample_background_points`'
      fixed vintage); tracker: the retrain follow-up CR, the §6 warning,
      the residual, MEDIUM/LOW review items.
- [ ] 9. Close-out: every item above ticked; status IMPLEMENTED.

## Out of scope
- **The retrain, calibration and new baseline** (§6): a follow-up CR.
- **The year-matched draw and any negatives re-fetch** (§5): the residual
  BUG's own CR, after a user decision on network acquisition.
- **Changing positive acquisition** (`sightings.py`/`ebird.py`
  `START_YEAR`): 2016 is kept for the buffer and the envelope metrics
  (§2).
- **Checkpoint split provenance** (BUG-0060): its own CR.
- **`train.sample_background_points`' single vintage** (every
  assumed-negative point takes the latest `features[0]` year): examined by
  deliverable 8's sweep and filed there if it is an instance; not changed
  here.
- **`predict.py`'s latest-vintage rule** (PA-0020 Swept?: separate
  mechanism).
