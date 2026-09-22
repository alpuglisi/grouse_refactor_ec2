# BUG-0012: `fit()` can `KeyError` on `metrics['tta_auc']` when TTA grouping doesn't divide evenly

## 1. Description
`GrouseModelHandler.evaluate()` only populates `tta_auc` (and related TTA
metrics) when the validation set size is an exact multiple of `tta_group`.
`fit()` consumes `metrics['tta_auc']` via unconditional plain-dict indexing
every epoch, regardless of whether that condition held.

## 2. Where encountered
`model_handler.py:697` (`improved = metrics['tta_auc'] > best_auc`) and
`:704` (`best_auc = max(best_auc, metrics['tta_auc'])`), vs. the
conditional population at `model_handler.py:834-852` inside `evaluate()`.

## 3. What it caused to fail
Not reachable through the shipped `train.py` CLI path, which always builds
validation sets as exact multiples of the TTA rotation group size (4).
However, any other caller of `GrouseModelHandler.fit()` that passes a
hand-built `val_ds` not guaranteed to be a multiple of `tta_group` will hit
`KeyError: 'tta_auc'` on every epoch where `evaluate()`'s conditional block
didn't run — a hard crash in what should be routine training.

## 4. What the defect was
```python
if tta_group and len(logits) % tta_group == 0:
    ...
    out["tta_auc"] = roc_auc(g, gy)
    ...
# later in fit():
improved = metrics['tta_auc'] > best_auc          # direct index
best_auc = max(best_auc, metrics['tta_auc'])       # direct index, unconditional
```
Notably, the status-line format string elsewhere in the same function uses
`.get()` for the same key, so the unsafe direct-indexing usage is
inconsistent even within a single function/author.

## 5. Root cause analysis (Five Whys)
1. Why can `fit()` crash with `KeyError`? Because it indexes
   `metrics['tta_auc']` directly without checking it exists.
2. Why might it not exist? Because `evaluate()` only adds it to the metrics
   dict when `len(logits) % tta_group == 0` holds for that validation pass.
3. Why does `fit()` assume it always exists? Because in the only path that
   currently calls `fit()` (`train.py`'s CLI), the validation set is always
   constructed to satisfy that condition, so the assumption has never been
   violated in practice.
4. Why wasn't the assumption made explicit or enforced? Because
   `evaluate()`'s conditional population and `fit()`'s unconditional
   consumption were not written with a shared contract — nothing documents
   or asserts that `tta_auc` is guaranteed present when `select_by=='auc'`.
5. Why does the inconsistent `.get()` usage in the same function matter?
   Because it shows the unsafe pattern wasn't a deliberate choice
   everywhere — it's an inconsistency within the same author's code, not a
   uniform assumption.

**Root cause:** `evaluate()`'s TTA metrics block is conditionally executed,
but `fit()` consumes its output unconditionally via direct dict indexing
instead of guarding on the same condition or using a safe accessor
everywhere.

## 6. Corrective action
None implemented yet — documentation-only pass. Recommended: use
`metrics.get('tta_auc')` consistently in `fit()` (matching the existing
status-line usage) with an explicit fallback/guard when `select_by=='auc'`
and the key is absent (e.g. skip the AUC-based improvement check for that
epoch, or raise a clear, actionable error rather than a bare `KeyError`).
Status: **OPEN**.

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
conditional-dict-population/unconditional-consumption mismatches. Result:
**none found**.

## 8. Preventive action
**PA-0010** (see `PREVENTIVE_ACTIONS.md`): a function that conditionally
populates a dict key must have every downstream consumer either guard on
the same condition or use `.get()` with an explicit, intentional default —
never mix unconditional indexing with conditional population of the same
key in the same code path.
