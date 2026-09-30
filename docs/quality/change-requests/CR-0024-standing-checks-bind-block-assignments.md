# CR-0024: `standing_checks` binds `block_assignments.csv` and every other file training-time code reads

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented.** Review log: `CR-0024-review-log.md`, to be created by the first reviewer.

## Scope
Add the block table to the standing acceptance subset, run E6 there with the block table included, and derive the standing file list from one shared constant naming the files `train.build_datasets` and its callers read (BUG-0080; PA-0037).

## Why now
BUG-0080: `standing_checks` digests the 18 split CSVs and runs E6 with `include_B=False`; `train.py --an-background` reads `block_assignments.csv` at run time to keep assumed negatives out of validation blocks (CR-0015's fix for BUG-0042). A replaced block table passes the standing check and re-opens the leak with no gate. Latent while the flag is off (BUG-0074 already forbids it), but it is the one training-time consumer the standing subset was meant to protect.

## The change
### 1. Root cause
As BUG-0080 §5: the standing file list is a hand list fixed at CR-0013, not derived from what training-time code reads; CR-0015's gate on the run-time producer was one-time.

### 2. Code (normative)
- `grouse_data.py` (dependency-free leaf, imported by both sides) gains
  `TRAINING_INPUT_KINDS = ("thinned_positives", "train_positives", "val_positives", "negatives", "train_negatives", "val_negatives", "block_assignments")`, with a comment that it is the list `standing_checks` binds and `train.build_datasets` reads (through `RegionData.positives/negatives` and `GrouseData.block_assignments`).
- `acceptance_split.standing_csv_paths(cfg)` returns the per-region paths for the region-keyed kinds plus the single `block_assignments` path (19 files), derived from `TRAINING_INPUT_KINDS`; `digested_paths` is unchanged (20: adds `candidate_pool`).
- `standing_checks` runs `("E6", gate_E6, {"include_C": False, "include_B": True})`.
- `train.build_datasets` reads only kinds in `TRAINING_INPUT_KINDS` (a test asserts it by patching `RegionData.path`/`GrouseData.path` to record the kinds requested during a fixture build).
- `tests/test_acceptance_split.py:2239`: `len(standing_csv_paths) == 19`; a new test asserts `set(standing_csv_paths kinds) == set(TRAINING_INPUT_KINDS)`.

### 3. Acceptance
No new gate: E6 with B and the digest comparison are existing checks now run standing. A harness test: a record made with the current block table, then the block table edited (one block relabelled `"train"`) → `standing_checks` fails naming `block_assignments.csv`.

## Impact
- Training, calibration and benchmarking refuse if the block table changed since acceptance (as they already do for the 18 CSVs).
- Standing check cost: one more small CSV digest and E6's block read.
- CR-0013's standing table gains a row.

## One change per CR (CR-0011 A5)
Acceptance design and a one-constant code change that cannot be separated (the constant is what the acceptance derives its list from). No data change.

## Risk: LOW
| risk | mitigation |
|---|---|
| A live record made before this change lacks the block table digest in `artifacts` | `standing_checks` fails with "missing digest for block_assignments.csv": re-issue the record with a config-only `acceptance_split.py` run (files unchanged); deliverable 3 |
| `train.build_datasets` reads a kind not in the constant in future | The recording test fails |

## Test plan
**Validatable here:** the constant/list equality test (pure Python, once `acceptance_split.py`'s numpy/pandas/scipy imports are available; `grouse_data.py` itself imports pandas and rasterio, so not in this clone).
**Not validatable here:** the harness test and the record re-issue (data host).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): the harness test and the list tests on an unmerged branch.
- [ ] 2. Code (§2).
- [ ] 3. Re-issue the acceptance record (config sha changes; files unchanged) and confirm `standing_checks` passes.
- [ ] 4. Bookkeeping: BUG-0080 → FIXED; `BUG_LOG.md`; PA-0037 Swept? cell; CR-0013 standing table; BUG-0042 §sweep correction ("gated by standing_checks" now true for B).
- [ ] 5. Close-out.

## Out of scope
- `candidate_pool.csv` in the standing subset (not read at training time).
- Lifting the BUG-0074 rule on `--an-background` (its own CR).
