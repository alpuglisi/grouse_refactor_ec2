# BUG-0014: `fit()`'s divergence-guard call still indexed `metrics['tta_auc']` directly (BUG-0012 recurrence, missed sibling)

## 1. Description
`GrouseModelHandler.fit()`'s call into `DivergenceGuard.update()` still
indexed `metrics['tta_auc']` directly, three lines below three other call
sites in the exact same function that were fixed for this identical defect
under BUG-0012. This is a fourth call site that the original BUG-0012 fix
missed.

## 2. Where encountered
`model_handler.py:753-754` (before this fix), in `fit()`, immediately after
the `metrics.get('tta_auc', ...)` fixes from BUG-0012 at lines 720, 733,
740 in the same function.

## 3. What it caused to fail
Identical failure mode to BUG-0012: `evaluate()` only populates
`metrics['tta_auc']` when the validation set size is an exact multiple of
`tta_group` (default 4). This call site runs **unconditionally every
epoch**, regardless of `select_by`, so any caller of `fit()` with a
validation set not sized as an exact multiple of `tta_group` would hit
`KeyError: 'tta_auc'` inside `DivergenceGuard.update()` — not reachable
through `train.py`'s shipped CLI path (which always builds exact-multiple
val sets), but a live crash risk for any other caller, exactly as
BUG-0012 already documented for its three sibling call sites.

## 4. What the defect was
```python
if guard.update(metrics.get('strict_accuracy', float('-inf')),
                metrics['tta_auc'], metrics['ap']):
```
Three lines above, the same function already reads
`metrics.get('tta_auc', float('-inf'))` (the BUG-0012 fix) and even the
status-line f-string above that uses `metrics.get('tta_auc', float('nan'))`
— this fourth site was the one instance in the function still using plain
`metrics['tta_auc']` indexing.

## 5. Root cause analysis (Five Whys)
1. Why did this call site still crash under the same condition BUG-0012
   supposedly closed? Because it still indexes `metrics['tta_auc']`
   directly instead of using `.get()`.
2. Why wasn't it fixed when BUG-0012 was fixed? Because the original fix
   was applied by locating the call sites that referenced `best_auc`/the
   status-line usage pattern, and this one — feeding
   `DivergenceGuard.update()`, a different consumer three lines later —
   wasn't part of that pattern match.
3. Why wasn't a full-function sweep done instead of a pattern match?
   Because the original bug investigation (BUG-0012) quoted and reasoned
   about two specific lines (697, 704 in the pre-fix line numbering) and
   the fix was scoped to exactly those two lines plus the visibly adjacent
   `select_by=='auc'` branch, not every `metrics['tta_auc']` occurrence in
   the function.
4. Why does that matter? Because `grep -n "tta_auc" model_handler.py`
   before this fix showed 5 occurrences in `fit()`/`evaluate()` combined —
   a mechanical grep sweep of the exact string, not just the specific
   lines quoted in the bug report, would have caught this on the first
   pass.

**Root cause:** the BUG-0012 corrective action fixed the specific lines
named in that bug's root-cause analysis, but not every occurrence of the
same conditional-population/unconditional-consumption pattern within the
same function — the fix targeted the cited symptom lines, not a full
mechanical sweep of the `tta_auc` key's every consumer.

## 6. Corrective action
Fixed directly (trivial: confined to one call expression, no signature/
schema change — no CR required): `guard.update(...)`'s second argument is
now `metrics.get('tta_auc', float('-inf'))`, matching every other
`tta_auc` consumer in `fit()`. Verified via `grep -n "metrics\['tta_auc'\]"
model_handler.py` returning no matches after the fix. **Status: CLOSED.**

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: **matches BUG-0012**
exactly — same root cause (conditional dict population consumed
unconditionally), same function, same key.

**Prior-preventive-action failure analysis:** PA-0010 ("a function that
conditionally populates a dict key must have every downstream consumer
either guard on the same condition or use `.get()` with an explicit
default") was written for BUG-0012 but did not, on its own, prevent this
recurrence, because the corrective action that shipped alongside it fixed
only the call sites the original investigation had named, not every
consumer PA-0010's own wording covers. Classified as **not actually
followed at fix time** — the rule was correctly generalized in wording,
but the accompanying code fix under-applied it within the very function it
was written about.

## 8. Preventive action
**PA-0010 is not reworded** (its wording already correctly targets the
mechanism, not the symptom) — instead, this bug's corrective action
demonstrates the enforcement gap: a rule stated correctly is not
self-applying. **PA-0013** (new, see `PREVENTIVE_ACTIONS.md`): when a bug
fix changes how a dict key is consumed (e.g. `metrics['x']` ->
`metrics.get('x', ...)`), grep the whole file for every other occurrence
of that exact key access pattern before closing the bug, not just the
call sites the investigation happened to quote — extends PA-0010 by
requiring the *verification step* a full sweep needs, since PA-0010 alone
described the target rule but not how to confirm every instance was found.
