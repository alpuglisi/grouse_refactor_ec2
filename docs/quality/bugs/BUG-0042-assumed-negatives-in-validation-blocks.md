# BUG-0042: Assumed-negative background points are drawn inside validation blocks and added to training

## 1. Description
With `--an-background > 0`, `train.build_datasets` asks
`sample_background_points` for random raster locations and adds them to
the **training** set with label 0. Nothing kept them out of the spatial
**validation** blocks that CR-0012 reserves. About a fifth of the
in-state draws landed in validation blocks. The model was therefore
trained on locations inside the areas that measure it, with a label
asserted there.

This is a different code path from BUG-0027. BUG-0027 was about the
split *files*. This bug is about rows generated *in memory* at training
time, which never pass through a file, so no CR-0013 gate can see them.

## 2. Where encountered
- `train.py:290-306` at `00c0b6f`, in `build_datasets`. The sampler is
  `train.py:121-165`.
- Found in the CR-0012 round-1 review (reviewer A, A1, MAJOR) and
  carried into CR-0015 (review log, lineage). It is a review finding,
  never observed in a run. The interim guard (CR-0015 deliverable 1)
  has blocked the path since 2026-09-30.

## 3. What it caused to fail
Share of in-state draws falling in validation blocks: ME 19.3 %,
NH 19.6 %, VT 20.5 % (CR-0015 review log, reviewer A round 1, 200,000
draws per region).

Every model trained with `--an-background > 0` therefore had
label-0 training rows inside its validation blocks, so its validation
metrics are not a spatial holdout. That covers the sweep recipes
`sweep/launch*.sh` and `sweep/runner.sh`, and Runs B and C in
`grouse_model_results_summary.md`. The size of the optimism is not
measured.

CR-0009's pinned retrain does not use the path.

## 4. What the defect was
`train.py:299-306` at `00c0b6f`:
```python
        if background_per_pos > 0:
            n_bg = int(round(background_per_pos * len(pos_df)))
            if n_bg > 0:
                ...
                bg_df = sample_background_points(rd, features, n_bg,
                                                 seed=seed + region_i)
                bg_tr = GrousePatchDataset(
                    bg_df, rd, cat_f, cont_f, img_size=img_size,
                    expand_rotations=True, label=0.0, ...)
                train_parts.append(bg_tr)
```
The sampler (`train.py:147-156` at `00c0b6f`) drew uniform `row`/`col`
over the whole raster:
```python
            rows = rng.integers(0, src.height, m)
            cols = rng.integers(0, src.width, m)
```
It took no block assignment and never consulted
`block_assignments.csv`.

## 5. Root cause analysis (Five Whys)
1. *Why were validation-block locations in training?* The sampler draws
   uniformly over the raster, and nothing filters by block.
2. *Why was there no filter?* The function predates the spatial block
   split. It was written to draw "background", with the split treated
   as a property of the record files.
3. *Why did CR-0012's holdout not constrain it?* CR-0012 made the split
   files disjoint by block, and CR-0013 gates those files. The sampler
   produces rows in memory at training time, after every file gate has
   run.
4. *Why was it missed when the holdout was designed?* The PA-0018
   sweep (CR-0014) and CR-0012's design listed spatial computations and
   file producers, selected by how their source is chosen. They did not
   list every *consumer* of the holdout: every code path that creates a
   training row.
5. *Why does that matter generally?* A holdout is a property of **every**
   training row, not of the files. Any row producer that bypasses the
   files bypasses the holdout.

**Root cause:** the spatial holdout was enforced only on the split
files. A run-time producer of training rows was neither constrained by
the holdout nor covered by any gate.

## 6. Corrective action
CR-0015 §2–§3, deliverable 6 (commit `2c23d7d`).
- `sample_background_points` now takes the required keyword
  `train_blocks_only`. When it is true, each draw's lon/lat goes through
  `regions.to_5070` → `regions.block_ids` →
  `regions.block_split(ids, assignments)`, and only `"train"` is kept.
  That is the same rule `generate_negatives.py` uses for positive-free
  blocks (CR-0015 §1, deliverable 5; byte-identical per B1).
- `build_datasets` passes `train_blocks_only=True,
  assignments=data.block_assignments`.
- `pretrain.py` passes `False`. Its SSL tiles carry no label, so they
  leak none.

Tests (see `docs/quality/evidence/CR-0015-background.txt` for the
real-data run):
- **U2** (synthetic, non-5070 CRS, five block kinds): no point in listed
  or unassigned validation blocks, and at least one point in each
  training kind. U2 fails on the constructed unassigned-as-train,
  `VAL_FRACTION`, native-x/y and pre-CR samplers.
- **V1** (real data, independent re-check): 0 validation-block points
  per region.
- **V3:** unassigned-train share against an independent reference.

This addresses the root cause: the generated rows now obey the same
holdout rule as the files, and V1 is the gate that sees them.

Status: **FIXED** at CR-0015 deliverable 7b. It closes at CR-0015
deliverable 9.

## 7. Recurrence review (`CLAUDE.md` §4)
I searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for holdout, split,
leakage, validation block and PA-0018.
- **BUG-0027 / PA-0018** is the closest prior. BUG-0027 was cross-region
  train/val leakage from overlapping boxes and per-region splits.
  PA-0018 says a pooled holdout's guarantee must hold across the pooled
  data.
  - It is the same guarantee (spatial holdout) broken again, by a
    different mechanism: a run-time row producer rather than a per-region
    computation.
  - BUG-0027's corrective action (CR-0012) does not reach it.
  - This is a new BUG, not an amendment of BUG-0027 (CR-0015
    deliverable 2).
- **BUG-0029 / PA-0020:** the same function's out-of-state draws. That
  is a support mismatch, not a holdout breach. Fixed by the same CR.

**Prior-preventive-action failure analysis (PA-0018).** Category: **too
narrow and not enforced**.
- *Too narrow:* PA-0018's CR-0014 sweep examined per-region spatial
  computations that select a source by label. It did not list producers
  of training rows that bypass the split files. Its scope was set by how
  the source is selected, not by every consumer of the holdout.
- *Not enforced:* CR-0013's gates see only files. No gate saw rows
  generated in memory.

## 8. Preventive action
**PA-0029, extends PA-0018.** Every producer of training rows, including
rows generated in memory at training time, is constrained by the
holdout (it draws only from training blocks, or its rows carry no
label). Each one is covered by a gate that reads the rows it actually
produces, not only the files. The row text is in
`docs/quality/evidence/CR-0015-bookkeeping-rows.md`.

**Mechanical enforcement (§3.4):**
- V1 (`tests/test_cr0015_real.py`) re-checks the sampler's real output
  with independent code.
- U2 (`tests/test_cr0015_sampler.py`) runs on every unit-test pass.
- There is no repository-wide lint for "a new row producer". The
  producer sweep below is the manual control, and a CI hook is not
  feasible yet (no CI, `CLAUDE.md`).

**Sweep (§3.5), CR-0015 deliverable 2, 2026-09-30.** It covered every
run-time producer of training or validation rows:
- `train.build_datasets` and all its callers (`train.py`,
  `calibrate.py`, `bench_pipeline.py`);
- `pretrain.py`, `tune.py`, `tune_bins.py`, `smoke_test_training.py`;
- every `diagnose_*.py`;
- `dataset.py`'s row expansion and augmentation, `losses.py`, and the
  inference and descriptive scripts.

**Results:**
- The real rows in `build_datasets` come from the split files through the
  accessors, gated by `acceptance_split.standing_checks`. Not affected.
- Rotation expansion and augmentation only view given rows. Not
  affected.
- `tune*.py` produce no labelled rows (BUG-0016 unchanged).
- `smoke_test_training.py` and `diagnose_training.py` fit only on
  split-file rows and discard the model. Not a bypass. Note: they do not
  call `standing_checks`, and the "covers every caller" comment at
  `train.py:246` omits them.
- `clean.py` and `legacy/gen_negs.py` would re-split, but they are
  guarded by a first-line `SystemExit` (CR-0012 §6).
- **Finding → BUG-0060.** Checkpoints carry no split provenance:
  - `--distill-from` teachers produce soft training targets.
  - `--init-from` accepts supervised checkpoints.
  - `--resume` checks geometry only.
  - `calibrate.py --model` fits Platt on validation rows.

  None of them checks which split the checkpoint was trained on. About
  81 % of today's validation positives were training rows under the
  pre-CR-0012 split.
- **Design questions, not defects** (tracker items for the lead):
  - D1: validation drives model selection, `--dynamic-dropout` and
    calibration; there is no third holdout.
  - D2: `calibrate.cross_fitted_probs` uses random folds, not block
    folds.
  - D3: training-negative weights and the 300 m buffer depend on
    validation positives (`generate_negatives.attach_weights`,
    `Selection_Ratio` over all sightings).
  - D4: there is no buffer between training and validation blocks, and
    the 64 px window is about 1.9 km against 3 km blocks.
