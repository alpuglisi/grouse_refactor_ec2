# BUG-0092: `StratifiedBatchSampler` is always built with `seed=0`, so batch composition and order are identical across `--seed` values and across ensemble members

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: FIXED in code (`2c05388`, 2026-09-30, trivial fix, no CR); validation pending on the data host; owner: lead.**

## 1. Description
`fit()` constructs `StratifiedBatchSampler(train_labels, batch_size,
pos_frac=batch_pos_frac)` with no seed, so the sampler's
`np.random.default_rng(0)` is the same stream in every run.
`train.py --seed` seeds torch and numpy's global state, which control
weight initialisation and the D4/jitter augmentation, but not this
generator. Two runs with different seeds, and the N members of
`--ensemble`, therefore see the same sequence of index batches; the
ensemble's documented diversity comes from pooling/regularisation and
init only.

## 2. Where encountered
- `dataset.py:504` (`seed=0` default), `:525` (`default_rng(seed)`).
- `model_handler.py:795-798` (constructed without a seed).
- `train.py:973-975`, `:1139-1141` (seeds that do not reach it).

## 3. What it caused to fail
Reproducibility claims of `--seed` ("two configurations can be compared
without run-to-run noise", `train.py:920-923`) hold, but seed-varied
repeats under-estimate run-to-run variance from batch order, and
ensemble members share it. No correctness effect on any single run.

## 4. What the defect was
`dataset.py:504`, `:525`:
```python
    def __init__(self, labels, batch_size, pos_frac=None, seed=0):
...
        self.rng = np.random.default_rng(seed)
```
`model_handler.py:795-798`:
```python
        if train_labels is not None:
            from dataset import StratifiedBatchSampler
            sampler = StratifiedBatchSampler(train_labels, batch_size,
                                             pos_frac=batch_pos_frac)
```

## 5. Root cause analysis (Five Whys)
1. *Why identical batches?* The sampler's seed is a constructor default.
2. *Why never overridden?* `fit()` has no seed parameter; `train.py`
   seeds the global RNGs and assumed that covered the training path.
3. *Why no rule?* No rule requires every RNG on the training path to
   derive from the run seed.

**Root cause:** an RNG constructed on the training path with a
constant default seed that the run's `--seed` is never wired to.

## 6. Corrective action
**None yet.** Trivial fix: add `seed` to `fit()` (default from
`torch.initial_seed() % 2**32` or an explicit argument), pass
`seed + member index` from `train.py`, and record it in the run args.
**Implemented 2026-09-30, commit `2c05388` (trivial fix under CLAUDE.md §1: one function, no public signature, file format or schema change).** `fit()` seeds `StratifiedBatchSampler` from `torch.initial_seed() % 2**32`, i.e. `train.py --seed` (+ member index for ensembles); `--seed 0` reproduces the previous batch order exactly. Validation here: `python -m py_compile` only, since this environment has no numpy, torch, rasterio or data tree. To verify: on a torch install: `StratifiedBatchSampler(labels, 32, seed=0)` and `seed=1` yield different first batches, `seed=0` yields the pre-fix sequence; two `train.py --seed 0` runs log identical epoch-1 batch compositions.
Status: **FIXED (code); validation pending on the data host.** Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "seed",
"rng", "deterministic".

**Matches:** CR-0012 `SPLIT_SEED` (pipeline determinism, hash-based),
CR-0015 (`sample_background_points` seeded per region). No prior BUG.

**Prior-preventive-action failure analysis.** No rule. Category: no
rule.

## 8. Preventive action
**PA-0047**: every RNG constructed on the training path (numpy
`Generator`, `random`, `torch.Generator`, sampler seeds) takes its seed
from the run's `--seed` plus a documented offset; no
`default_rng(0)`/`seed=0` default is reachable from `train.py`; a test
asserts `fit()` threads the seed to the sampler.

**Sweep (§3.5), `default_rng(`/`seed=0` in `dataset.py`,
`model_handler.py`, `train.py`, `pretrain.py`, `calibrate.py`:**
`StratifiedBatchSampler` (this); `train.sample_background_points`
(seeded `seed + region_i`, correct); `pretrain.py` (`seed + i`,
correct); `calibrate.py:229`, `:365` (calibration folds and the smoke
subsample use fixed seeds by design; recorded). No other instance.

## Cross-references
CR-0012 (`SPLIT_SEED`), CR-0015; PA-0047.
