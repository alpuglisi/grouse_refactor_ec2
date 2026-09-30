# BUG-0057: `smoke_test_training.py` builds a validation set that breaks the 4-rotation TTA grouping contract

## 1. Description
`GrouseModelHandler.evaluate()` averages validation logits in consecutive
groups of `tta_group` = 4. It assumes every validation point is stored as
its 4 fixed rotations, one after another. `train.py` builds its
validation set that way for both classes. `smoke_test_training.py`
rotates validation positives but not negatives.

With the default `--n-val 10` the set has 50 samples. That is not a
multiple of 4, so every TTA metric is silently skipped, which exposed
BUG-0056. With `--n-val` a multiple of 4 the length divides by 4. TTA then
runs and averages 4 *different* unrotated negatives as if they were one
point. The label assertion cannot catch that, because all 4 share label 0.

## 2. Where encountered
- Found by CR-0012 deliverable 6, test plan item 7
  (`docs/quality/evidence/CR-0012-d6/test_plan.txt`, item 7 and the
  `--n-val 12` diagnostic, `test_plan/smoke_diag_nval12.log`).
- The defect is at `smoke_test_training.py:90-96` (pre-fix numbering), in
  `main()`.
- The contract it breaks: `model_handler.py:1799-1803` (the `evaluate()`
  docstring) and `:1888-1893` (grouping); `train.py:316-324`.
- `git blame`: initial commit `29c194a`. `train.py` at `29c194a` already
  rotated both validation classes (`train.py:141,144` at that commit).

## 3. What it caused to fail
- **Default options (`--n-val 10`):**
  - validation set = 10×4 + 10 = 50 samples; 50 % 4 ≠ 0;
  - `evaluate()` silently omits `tta_auc`, `tta_ap`, `tta_accuracy`,
    `strict_accuracy` and `hedged_pct`;
  - `fit()` then raised `KeyError: 'tuned_tta_accuracy'` (BUG-0056), and
    the smoke test exited 1 at stage 5/7.
- **`--n-val` a multiple of 4 (e.g. 12 → 60 samples):**
  - the smoke test passes;
  - its "TTA AUC", "strict" and "tuned acc" are computed over 12 real
    positive points plus 3 pseudo-points, each the mean of 4 different
    negatives;
  - the printed TTA numbers are wrong, and nothing says so.
- **Not affected:** `train.py`, `calibrate.py` and `bench_pipeline.py`.
  All of them build validation through `train.build_datasets`, which
  rotates both classes. No model, map or pipeline artifact is affected.
  The smoke test's numbers are a functional check and are not reported
  anywhere.

## 4. What the defect was
`smoke_test_training.py:90-96` (before the fix):
```python
        val_ds = ConcatDataset([
            GrousePatchDataset(va_pos.head(args.n_val), rd, cat_f, cont_f,
                               img_size=args.img_size,
                               expand_rotations=True, label=1.0),
            GrousePatchDataset(va_neg.head(args.n_val), rd, cat_f, cont_f,
                               img_size=args.img_size,
                               expand_rotations=False, label=0.0)])
```
The contract it breaks, `model_handler.py:1799-1803` and `:1888-1893`:
```python
        """tta_group: the validation set stores each point as `tta_group`
        consecutive fixed rotations, so averaging predictions in groups of
        that size is exactly test-time augmentation and gives the honest
        per-POINT score (the quantity that matters in deployment). Set 0
        to skip."""
...
        if tta_group and len(logits) % tta_group == 0:
            # Loader must be unshuffled for this grouping to line up with
            # the dataset's point-major ordering - it is (no sampler).
            g = logits.reshape(-1, tta_group).mean(axis=1)
            gy = ys.reshape(-1, tta_group)
            assert (gy == gy[:, :1]).all(), "TTA grouping crossed a label"
```
`train.py:316-324`, which honours the contract:
```python
        # Validation is never augmented: the 4 fixed rotations are kept so
        # val scores stay comparable across runs (and so the evaluator can
        # average them per point as test-time augmentation).
        val_parts.append(GrousePatchDataset(
            val_pos_df, rd, cat_f, cont_f, img_size=img_size,
            expand_rotations=True, label=1.0, cache_dir=cache_dir))
        val_parts.append(GrousePatchDataset(
            val_neg_df, rd, cat_f, cont_f, img_size=img_size,
            expand_rotations=True, label=0.0, cache_dir=cache_dir))
```

## 5. Root cause analysis (differential analysis, then Five Whys)
**Differential analysis:**

| Validation set built by | Positives | Negatives | Length | TTA |
|---|---|---|---|---|
| `train.py` (works) | rotated | rotated | 4·(P+N) | correct per point |
| `smoke_test_training.py` (fails) | rotated | **unrotated** | 4P+N | skipped, or mis-grouped |

The only difference is `expand_rotations` on the validation negatives.

**Five Whys:**
1. **Why were the TTA metrics skipped or wrong?** The validation
   negatives are one sample per point, not four, so `evaluate()`'s
   groups of 4 do not match points.
2. **Why are they unrotated?** The smoke test's validation block copies
   its training block, where negatives are deliberately unrotated
   ("unweighted - original behavior"). Rotation was treated as a
   class-balance choice. It is also a structural requirement of the
   validation set.
3. **Why did the smoke test not surface the violation directly?**
   `evaluate()` infers the layout from the length alone. It silently
   skips TTA when the length does not divide, and silently mis-groups
   when it does. No error is raised in either case.
4. **Why is the contract only inferred?** It is written down only in
   prose: the `evaluate()` docstring and a `train.py` comment. The
   dataset does record `expand_rotations`, but `evaluate()` never checks
   it.

**Root cause:** the TTA grouping contract is enforced nowhere. It lives
in a docstring and a comment, and `evaluate()` infers it from the length
and fails open. So a validation builder that differs from `train.py`,
here by copying the training block's rotation choice, produced a
non-conforming set with no error.

## 6. Corrective action
Trivial fix (one argument in `main()`, no CLI flag or schema change, so
no CR). Commit `40dbecf` on branch `worktree-agent-adef8b998228501c0`:
- The validation negatives now use `expand_rotations=True`.
- A comment cites BUG-0057 and the contract.
- The validation set is now 4·(n_val + n_val). With the defaults that is
  80 samples, laid out point-major within each class, so groups match
  points.
- The training-set construction is unchanged. It is not subject to the
  TTA contract.

**Verification** (`docs/quality/evidence/CR-0012-d6/smoke_rerun.txt`):
- `python smoke_test_training.py` with its defaults, on scratch tree B,
  printed `val=80 samples`.
- All 7 stages passed, with finite TTA AUC, tuned accuracy and strict
  accuracy on every epoch.
- Unit tests: 223, OK.

This fixes the one non-conforming builder. The root cause, a contract
that is inferred and fails open, is not fixed by this change. It is
BUG-0062, which is open and needs a CR (PA-0030's fail-closed clause).

Status: **FIXED** (`40dbecf`; no CR, trivial). The root-cause
remediation is tracked as BUG-0062.

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`, for "rotation",
`expand_rotations`, "TTA", "grouping", "contract" and "smoke".

**Results:**
- No earlier bug about a builder breaking the grouping contract.
- BUG-0012 and BUG-0014 are the consumer side of the same silent skip.
  BUG-0012 §3 named "a hand-built `val_ds` not guaranteed to be a
  multiple of `tta_group`" as the trigger. This smoke test was such a
  builder then and was not checked. That failure is analysed in
  BUG-0056 §7, and PA-0030 addresses it.
- BUG-0049/PA-0027: the same fail-open shape (a violation resolved to a
  degraded "success" branch), but on exceptions. PA-0027 does not cover
  a condition-based silent skip.

**Prior-preventive-action failure analysis:**
- **PA-0010 and PA-0013:** both are consumer-side rules. They made
  consumers tolerate the missing key. Neither asks why the key is
  missing, or whether its absence signals an input contract violation.
  So both would have accepted a fix that hides this bug (`.get` →
  `nan`). This is a wrong-layer failure.
- **PA-0027:** too narrow for this bug. It covers `except` handlers, and
  here the silent degrade is an `if`.

## 8. Preventive action
**PA-0030** (shared with BUG-0056; supersedes PA-0010 and PA-0013). Its
fail-closed clause applies here: a producer whose output depends on an
input contract (here, validation data stored point-major in groups of
`tta_group`) checks that contract from the input's own metadata and
raises on violation. It does not omit outputs or infer the layout from
the length. Implementing that in `evaluate()` and
`calibrate.collect_val_logits` is BUG-0062 (needs a CR).

**Sweep (§3.5):** every validation-set builder (`expand_rotations=` call
sites in git-tracked `*.py`, minus `inv_*`/`res_*`/`docs/`):
- **Conform:** `train.py:288-324`, used by `calibrate.py` and
  `bench_pipeline.py`. `diagnose_wetland.py:202` also conforms; its own
  `reshape(-1, 4)` raises on a non-multiple, so it fails closed.
- **Not validation sets:** `diagnose_training.py:89-92,144-147`
  (unrotated). They are never passed to `evaluate()` or grouped. The
  script scores samples individually.
- **Non-conforming:** this bug only.

Full record: `docs/quality/evidence/BUG-0056/sweep_triage.md`.
