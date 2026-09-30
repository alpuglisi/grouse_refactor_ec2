# BUG-0056: `fit()`'s epoch status line indexes `metrics['tuned_tta_accuracy']`, which exists only when TTA ran (third recurrence of BUG-0012)

## 1. Description
At the end of every epoch, `GrouseModelHandler.fit()` prints a status line
that reads `metrics['tuned_tta_accuracy']` by plain indexing. The key is
written a few lines earlier only if `evaluate()` returned TTA logits
(`_tta_logits`). `evaluate()` returns them only when the validation set's
length is a multiple of `tta_group` (4). With any other validation set,
`fit()` raises `KeyError` at the end of epoch 1.

## 2. Where encountered
- Found by CR-0012 deliverable 6, test plan item 7
  (`docs/quality/evidence/CR-0012-d6/test_plan.txt`, item 7;
  `test_plan/smoke.log`). The run was `python smoke_test_training.py`
  with its defaults, cwd = scratch tree B.
- Consumer: `model_handler.py:1339`, in `fit()`.
- Producer: `model_handler.py:1318-1323` (in `fit()`) and
  `model_handler.py:1888-1906` (in `evaluate()`).
- `git blame`: all of these lines come from the initial commit `29c194a`.
  The line already existed as `model_handler.py:722` at `4867db1`, the
  BUG-0014 fix.

## 3. What it caused to fail
- **Observed:** `smoke_test_training.py` with default options exited 1 in
  stage 5/7, at the end of epoch 1:
  ```
    File "/home/ec2-user/grouse2/model_handler.py", line 1339, in fit
      f"tuned acc: {metrics['tuned_tta_accuracy']:.2f}% | "
  KeyError: 'tuned_tta_accuracy'
  ```
  Its validation set is 10×4 positives + 10 negatives = 50 samples, and
  50 % 4 ≠ 0 (why the negatives are unrotated is BUG-0057).
- **Wider impact:** any `fit()` caller whose validation set is not a
  multiple of 4 crashed after its first epoch.
- **Not affected:** `train.py`'s shipped path. `build_datasets` rotates
  both classes, so its validation set is always a multiple of 4.
- **Data:** no model, map or pipeline artifact was affected. The crash
  happens after the epoch-1 checkpoint is written, so a partial
  checkpoint stays on disk (the smoke test writes to its own
  `data/models/smoke_test_model*.pth`).

## 4. What the defect was
Producer, `model_handler.py:1318-1323`. The key is stored through the
loop variable `dst`, and only when `src in metrics`:
```python
            for src, dst in (("_logits", "tuned_accuracy"),
                             ("_tta_logits", "tuned_tta_accuracy")):
                if src in metrics:
                    ykey = "_y" if src == "_logits" else "_tta_y"
                    metrics[dst] = 100.0 * float(
                        ((metrics[src] >= thr) == (metrics[ykey] == 1)).mean())
```
`_tta_logits` exists only under `evaluate()`'s condition,
`model_handler.py:1888`:
```python
        if tta_group and len(logits) % tta_group == 0:
```
Consumer, `model_handler.py:1336-1341`. The two lines around the defect
already use `.get(..., nan)` for keys stored under the same condition:
```python
                      f"TTA AUC: {metrics.get('tta_auc', float('nan')):.4f} | "
                      f"AP: {metrics['ap']:.4f} | "
                      f"rank: {metrics['rank_score']:.4f} | "
                      f"tuned acc: {metrics['tuned_tta_accuracy']:.2f}% | "
                      f"strict: {metrics.get('strict_accuracy', float('nan')):.2f}% "
                      f"(hedged {metrics.get('hedged_pct', float('nan')):.1f}%) | "
```

## 5. Root cause analysis (Five Whys)
1. **Why did `fit()` raise `KeyError`?** Line 1339 indexes
   `metrics['tuned_tta_accuracy']` directly, and for a validation set
   that is not a multiple of 4 the key was never stored.
2. **Why was the key not stored?** `evaluate()` produces its TTA outputs
   (`tta_auc`, `tta_ap`, `tta_accuracy`, `strict_accuracy`,
   `hedged_pct`, `_tta_logits`) only when `len % tta_group == 0`. The
   derived key `tuned_tta_accuracy` inherits that condition through
   `if src in metrics`.
3. **Why did BUG-0012 and BUG-0014 not fix this line?** Their
   investigations and fixes were organised around one key, `tta_auc`.
   BUG-0014's PA-0013 says to grep "for every other occurrence of that
   exact key access pattern", and the key was `tta_auc`.
   `tuned_tta_accuracy` is a different key with the same condition. It
   sat three lines from the BUG-0012 status-line fix and was not looked
   at.
4. **Why did PA-0013's "repo-wide sweep of the general mechanism" (commit
   `bea206c`) not find it, when the line was already present
   (`model_handler.py:722` at the time)?**
   - The sweep worked from keys, not from the producer. It looked for
     other keys "conditionally populated", but this key is stored as
     `metrics[dst]` through a loop variable, so a text search for
     `metrics['<literal>'] =` under an `if` does not see it.
   - No list was made of every key `evaluate()`/`fit()` can omit.
   - The sweep's method and its candidate list were not recorded (the
     Swept? cell says only "found nothing"), so nobody could check it.
5. **Why could that happen after two occurrences?**
   - PA-0010/PA-0013 place the obligation on consumers, one key at a
     time. Nothing requires the producer's full set of optional keys to
     be listed.
   - Nothing requires the absent-key path to be exercised. No test or
     recorded run fed `fit()` a validation set of non-multiple length,
     although BUG-0012 §3 named exactly that case ("any other caller of
     `GrouseModelHandler.fit()` that passes a hand-built `val_ds`"). The
     repository's own `smoke_test_training.py` was such a caller the
     whole time.

**Root cause:** `evaluate()`'s output key set depends on a runtime
condition. The standing rules checked consumers one key at a time,
starting from the key named in the bug, with an unrecorded text search.
So a sibling key stored through a loop variable, with the same condition,
was never enumerated. The absent-key path was never executed, so nothing
caught it.

## 6. Corrective action
Trivial fix (one expression in `fit()`, no signature, schema or CLI
change, so no CR). Commit `40dbecf` on branch
`worktree-agent-adef8b998228501c0`:
```python
                      f"tuned acc: {metrics.get('tuned_tta_accuracy', float('nan')):.2f}% | "
```
This matches the neighbouring `tta_auc`/`strict_accuracy`/`hedged_pct`
reads. `nan` prints as "not computed", which is what happened.

**PA-0013 full-file check:** `grep -n "tuned_tta_accuracy"
model_handler.py` now shows the producer (`:1319`), the fixed status line
(`:1339`) and the TensorBoard tag table (`:1378`), which is guarded by
`if key in metrics` (`:1388`). No plain index is left. The mechanism
sweep (§8) covers every other key.

**Verification** (`docs/quality/evidence/CR-0012-d6/smoke_rerun.txt`):
- **Absent-key path.** The pre-fix `smoke_test_training.py` (validation
  set of 50 samples, TTA skipped) was run against the fixed
  `model_handler.py`, on scratch tree B. Result: all 7 stages passed; the
  status line prints `tuned acc: nan%`. Before the fix this run raised
  `KeyError`.
- **Present-key path.** The fixed smoke test with defaults (validation set
  of 80 samples) passed all 7 stages, with finite `tuned acc`.
- **Unit tests.** `python -m unittest discover -s tests -t .`: 223
  tests, OK.

The fix covers this consumer. The producer-side cause (TTA metrics
silently omitted when the validation set breaks the grouping contract) is
BUG-0062, which is open and needs a CR. PA-0030 addresses the mechanism.

Status: **FIXED** (`40dbecf`; no CR, trivial).

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`, for `KeyError`,
`.get(`, "conditionally popul", `tta`, `metrics[` and "dict key".

**Match: BUG-0012 (PA-0010) and BUG-0014 (PA-0013).**
- The mechanism is the same: `evaluate()` populates a key under
  `len % tta_group == 0`, and `fit()` consumes it unconditionally.
- The function and the producer condition are the same. Only the key
  differs.
- This is the **third** occurrence.

No other rows match. BUG-0049/PA-0027 (a broad handler resolving to
success) is a related shape, a silent degrade. It works on exceptions,
not on key sets. §8 uses it for the fail-closed decision.

**Why PA-0010 did not prevent it:**
- **Not followed at fix time.** This was already recorded in BUG-0014 §7,
  and it recurred again.
- **Not verifiable.** The rule's wording ("every downstream consumer")
  covers this line, but it gives no way to find every consumer of every
  optional key.

**Why PA-0013 did not prevent it:**
- **Too narrow.** The rule is scoped to "that exact key access pattern",
  meaning the key named in the bug. This bug is a different key with the
  same condition.
- **Wrong layer.** It works from consumers of one key, not from the
  producer's full optional-key set.
- **Not enforced or verifiable.** Its Swept? cell ("repo-wide sweep of
  the general mechanism ... found nothing") records neither a method nor
  a candidate list. The line it missed was in the same function as the
  two bugs it had just fixed. A text search for literal-key stores cannot
  see `metrics[dst]`.
- **No execution.** Neither rule asks that the absent-key path be run.
  One smoke run with a non-multiple-of-4 validation set would have shown
  the crash in September.

## 8. Preventive action
**PA-0030 supersedes PA-0010 and PA-0013** (`PREVENTIVE_ACTIONS.md`). It
changes the prior rules in these ways:
- **Producer-driven enumeration.** Every key a producer can omit is
  listed, including keys stored through variables, differing return
  literals, `.update()` and `**`. Then every consumer of each key is
  checked. The method does not start from the key named in the bug.
- **Consumers that assume a fixed key set** (a CSV header, a
  `DictWriter`, a column list) are in scope.
- **Absence that means a contract violation fails closed.** If a key is
  missing because an input broke the producer's contract (here, a
  validation set that does not follow the 4-rotation layout), the
  producer raises instead of omitting the key. This is PA-0027's
  fail-closed principle applied to conditions rather than exceptions.
  `.get(key, default)` stays correct only for keys that are legitimately
  optional (for example `tta_group=0`, an explicit opt-out).
- **Verifiable sweep.** A fix closes only after
  `docs/quality/evidence/BUG-0056/sweep_condkeys.py` (and
  `sweep_returns.py`) has been run, with its output and triage recorded.
- **Absent path executed.** A test or a recorded run must exercise the
  producer's absent-key path through every consumer.

The PA-0010 and PA-0013 rows stay, marked "Superseded by PA-0030".

**Fail-closed decision.**
- **Decided:** `evaluate()` (and `calibrate.collect_val_logits`) should
  raise when `tta_group > 0` and the validation set does not satisfy the
  grouping contract. They should check the contract from the dataset
  (every leaf `GrousePatchDataset` has `expand_rotations=True`), not
  infer it from the length.
- **Reason:** a length check cannot detect BUG-0057's silent
  mis-grouping. Omitting the metrics turns a contract violation into a
  silently degraded run.
- **Not implemented here:** it changes `evaluate()`'s behaviour for
  callers, so it is not a trivial fix. It is filed as BUG-0062, with a
  CR outline in the tracker.

**Mechanical enforcement:**
- **In place now:** the sweep scripts, committed and re-runnable
  (`docs/quality/evidence/BUG-0056/`).
- **Not done:** turning `sweep_condkeys.py` into a lint test with an
  allow-list, in the style of `tests/test_nodata_zero_lint.py`. The
  heuristic's name-based matching needs an allow-list of about 60 keys
  (`sweep_triage.md`), and that test needs its own CR (tracker).

**Sweep (§3.5), 2026-09-30, by mechanism:**
- Scope: git-tracked `*.py` minus `inv_*`, `res_*`, `docs/` (67 files).
- Full record: `docs/quality/evidence/BUG-0056/sweep_triage.md`.
- Findings:
  - this bug;
  - BUG-0057 (a builder that breaks the grouping contract; fixed);
  - BUG-0061 (`_log_metrics` fixes the CSV header from the first row ever
    written; open);
  - BUG-0062 (TTA grouping inferred from length, failing open, in
    `model_handler.evaluate` and `calibrate.collect_val_logits`; open,
    needs a CR).
- Every other flagged row was classified as not the mechanism.
