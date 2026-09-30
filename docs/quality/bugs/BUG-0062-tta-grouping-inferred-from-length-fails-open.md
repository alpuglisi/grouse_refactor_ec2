# BUG-0062: TTA grouping is inferred from the validation length and fails open (`evaluate`, `calibrate.collect_val_logits`) (PA-0030 sweep)

## 1. Description
Two functions average validation logits in consecutive groups of
`tta_group` (4), on the assumption that each point is stored as its 4
rotations: `GrouseModelHandler.evaluate()` and
`calibrate.collect_val_logits()`. Neither checks that assumption. Both
infer it from `len(logits) % tta_group == 0`.
- **Length not divisible:** `evaluate()` silently omits every TTA metric
  (`tta_auc`, `tta_ap`, `tta_accuracy`, `strict_accuracy`, `hedged_pct`,
  and so `tuned_tta_accuracy`). `collect_val_logits()` silently returns
  per-rotation logits, which calibration then fits and reports as if they
  were per-point.
- **Length divisible but the layout is wrong** (an unrotated class,
  BUG-0057): both silently average different points together. The only
  check, a label assertion, cannot see it when the mixed points share a
  label.

## 2. Where encountered
- PA-0030 sweep (BUG-0056 §8), 2026-09-30, step 4: every consumer that
  groups by `tta_group`.
- `model_handler.py:1888-1893` (`evaluate()`).
- `calibrate.py:154-159` (`collect_val_logits()`). Its caller prints
  "points x 4 rotations" unconditionally at `calibrate.py:359-360`.
- `git blame`: initial commit `29c194a` for both.

## 3. What it caused to fail
- **Observed:** BUG-0056's crash, which the silent skip in `evaluate()`
  set up, and BUG-0057's silently mis-grouped smoke-test metrics with
  `--n-val 12`.
- **No production artifact is affected today.** `train.py`,
  `calibrate.py` and `bench_pipeline.py` all build validation through
  `train.build_datasets`, which rotates both classes (verified by the
  BUG-0057 §8 sweep). The defect is latent for them.
- **What happens on a future non-conforming builder:**
  - checkpoint selection by `auc`/`rank`/`strict` quietly falls back to
    non-TTA metrics or to `-inf` (`model_handler.py:630-637`);
  - calibration is fit on rotations, not points, and still reports
    "points";
  - in the divisible case the TTA numbers are wrong, and no error or
    warning is given.

## 4. What the defect was
`model_handler.py:1888-1893`:
```python
        if tta_group and len(logits) % tta_group == 0:
            # Loader must be unshuffled for this grouping to line up with
            # the dataset's point-major ordering - it is (no sampler).
            g = logits.reshape(-1, tta_group).mean(axis=1)
            gy = ys.reshape(-1, tta_group)
            assert (gy == gy[:, :1]).all(), "TTA grouping crossed a label"
```
(no `else`: the TTA keys are simply absent)

`calibrate.py:154-159`:
```python
    if tta_group and len(logits) % tta_group == 0:
        g = logits.reshape(-1, tta_group).mean(axis=1)
        gy = labels.reshape(-1, tta_group)
        assert (gy == gy[:, :1]).all(), "TTA grouping crossed a label"
        return g, gy[:, 0]
    return logits, labels
```

## 5. Root cause analysis (fault tree)
**Top event:** TTA metrics or calibration inputs are wrong or missing,
and no error is raised.
- **OR gate 1: length not divisible**
  - AND: a builder skipped rotation for some class (BUG-0057), **and** the
    consumer takes a silent fallback (the missing `else`, or
    `return logits, labels`).
- **OR gate 2: length divisible, layout wrong**
  - AND: a builder skipped rotation for a class whose count is a
    multiple of 4 (or shuffled the loader), **and** the consumer checks
    only the length and the labels, never the dataset's layout.

Both branches share one basic event: **the consumer infers an input
contract from a weak proxy (the length) and, when the proxy fails,
resolves to a degraded result instead of an error.** Each dataset part
carries `GrousePatchDataset.expand_rotations`, which is the true
contract, but no consumer reads it.

**Root cause:** the grouping contract is not checked at the point where
it is used. It is inferred from the length, and a violation fails open.

## 6. Corrective action
**Not fixed in this pass.** Making the grouping fail closed changes
`evaluate()`'s behaviour for its callers: a non-conforming validation set
would raise where it now degrades. Under `CLAUDE.md` §1 that is not a
trivial fix, so it needs a CR.

**Proposed CR outline** (for the lead):
- **Scope:** `evaluate()` and `calibrate.collect_val_logits()` check the
  TTA grouping contract from the dataset, and raise on violation when
  `tta_group > 0`.
- **Change:**
  1. Add one helper, e.g. `dataset.tta_layout_ok(ds, group) -> (bool,
     reason)`. It walks `ConcatDataset.datasets` recursively and requires
     every leaf to be a `GrousePatchDataset` with
     `expand_rotations=True`. With `group == 4`, a leaf of another type is
     treated as a violation, because its layout is unknown.
  2. In `evaluate()`: if the loader has a sampler other than
     `SequentialSampler`, or the dataset fails the helper, raise
     `ValueError` naming the offending part. Keep the length check as a
     defensive assertion.
  3. In `collect_val_logits()`: the same check, and remove the
     `return logits, labels` fallback. The "points x 4 rotations" message
     becomes true by construction.
  4. `tta_group=0` stays the explicit opt-out. There the TTA keys are
     legitimately absent, and consumers keep `.get` (BUG-0012/0014/0056).
- **Impact:**
  - `train.py`, `calibrate.py`, `bench_pipeline.py` and the fixed
    `smoke_test_training.py` conform, so there is no change for them.
  - Any other caller with an unrotated or custom validation set now
    raises. It must pass `tta_group=0` to opt out.
  - `fit()` passes the default `tta_group=4` and does not expose the
    parameter. Whether `fit()` should forward a `tta_group` argument is a
    signature change and a separate decision.
- **Risk:** low to medium. The failure mode moves from silent to loud.
  Mitigation: the sweep in BUG-0057 §8 lists every builder.
- **Test plan:**
  - unit tests with small fake `GrousePatchDataset`-like parts covering
    conforming, non-divisible, divisible-but-unrotated and shuffled
    cases;
  - a smoke test re-run on a scratch tree;
  - a `calibrate.py` smoke run (`--max-points`) on a scratch tree.
- **Out of scope:** `fit()` signature; the train-set rotation choice in
  `smoke_test_training.py`.

Status: **OPEN** (needs a CR; tracker; owner: lead).

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`, for "TTA",
"grouping", "rotation", "fail closed", "silent" and "skip".
- **BUG-0049 / PA-0027 (broad handler resolves to success).** Same
  fail-open shape, but an `if` instead of an `except`, so PA-0027 does
  not apply as written. That gap is too narrow a layer, and PA-0030's
  fail-closed clause extends the principle to conditions.
- **BUG-0052 (validity probe fails open).** Same shape, exception-based.
- **BUG-0012/0014/0056 (consumers of the keys this skip omits).** Their
  fixes made consumers tolerate the silent skip, and none addressed the
  skip itself. See the prior-PA failure analysis in BUG-0056 §7.

## 8. Preventive action
**PA-0030** (from BUG-0056), no new PA. Its fail-closed clause covers
this bug: when a key or result is absent because an input broke the
producer's contract, the producer raises, and it checks the contract from
the input's own metadata, not from a proxy such as the length.
