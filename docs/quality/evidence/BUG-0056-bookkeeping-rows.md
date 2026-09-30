# BUG-0056 / BUG-0057 / BUG-0061 / BUG-0062 / PA-0030: rows for the lead to apply

Written 2026-09-30 on branch `worktree-agent-adef8b998228501c0`. Code fix
commit `40dbecf`. The rows are not applied to `BUG_LOG.md`,
`PREVENTIVE_ACTIONS.md` or the tracker, because those files belong to the
lead.
- IDs used: BUG-0056, BUG-0057, BUG-0061, BUG-0062 and PA-0030.
  BUG-0058..0060 are CR-0015's.
- None of the rows below contain a literal `|` inside a cell, so no `\|`
  escaping is needed.

## 1. `docs/quality/bugs/BUG_LOG.md`: new rows
The rows are newest first by ID. Insert them above the current top row,
after placing CR-0015's BUG-0058..0060 by the log's newest-first rule.
Each row is one line.

```
| BUG-0062 | 2026-09-30 | `model_handler.evaluate` and `calibrate.collect_val_logits` infer the 4-rotation TTA grouping from `len % tta_group`: a non-conforming validation set silently drops the TTA metrics (evaluate) or silently returns per-rotation logits that calibration reports as points; a divisible but unrotated set silently averages different points (PA-0030 sweep) | Input contract inferred from a proxy (length) and violated contract resolved to a degraded result, not an error (fail-open; PA-0027 shape on an `if`) | None yet — needs a CR: check the layout from the dataset (`expand_rotations` on every leaf, sequential loader) and raise when `tta_group > 0`; `tta_group=0` stays the opt-out (CR outline in BUG-0062 §6); owner: lead | OPEN (latent; all shipped builders conform) |
| BUG-0061 | 2026-09-30 | `_log_metrics` appends rows to `--metrics-csv` under the header written by the first run; a run with a different key set (e.g. `--dynamic-dropout` toggled) shifts columns silently or makes the file unparseable (PA-0030 sweep; `docs/quality/evidence/BUG-0056/bug0061_repro_output.txt`) | Consumer of a conditional-key producer assumes a fixed key set (the CSV header) and never checks it on append | None yet — recommended: read the existing header and raise `ValueError` naming added/missing keys on mismatch (one function; aborts `fit()` after epoch 1, so owner decides); owner: next change to `model_handler.py` | OPEN |
| BUG-0057 | 2026-09-30 | `smoke_test_training.py` builds validation negatives with `expand_rotations=False`: 50 samples with defaults, so TTA metrics are skipped (exposed BUG-0056); with `--n-val` a multiple of 4, TTA averages 4 different negatives as one point | TTA grouping contract exists only in a docstring and a `train.py` comment; `evaluate()` infers it from length and fails open, so a builder differing from `train.py` got no error | Trivial fix (`40dbecf`, no CR): validation negatives `expand_rotations=True`; smoke test passes all 7 stages on scratch tree B (`docs/quality/evidence/CR-0012-d6/smoke_rerun.txt`); root-cause remediation is BUG-0062 | FIXED |
| BUG-0056 | 2026-09-30 | `fit()` raises `KeyError: 'tuned_tta_accuracy'` at the end of epoch 1 for any validation set not a multiple of 4 (CR-0012 d6 test plan item 7: `smoke_test_training.py` defaults) — third occurrence of BUG-0012 | `evaluate()`'s output key set depends on a runtime condition; PA-0010/PA-0013 checked consumers one key at a time from the key named in the bug, with an unrecorded text search, so a sibling key stored through a loop variable (`metrics[dst]`) was never enumerated and the absent path never run | Trivial fix (`40dbecf`, no CR): status line uses `.get('tuned_tta_accuracy', nan)`; absent-key path re-run passes (`smoke_rerun.txt` run 2); PA-0030 supersedes PA-0010/PA-0013; sweep → BUG-0057, BUG-0061, BUG-0062 | FIXED |
```

## 2. `docs/quality/PREVENTIVE_ACTIONS.md`: new row
Append after PA-0027, or after whatever row is last once PA-0028/0029
land. The row is one line.

```
| PA-0030 | **Supersedes PA-0010 and PA-0013** (widens from the one key named in a bug to the producer's whole optional-key set; adds fail-closed for contract violations, a recorded sweep, and an executed absent path). (a) A producer whose output key set depends on a runtime condition (a store under `if`/`try`/a loop, a store through a variable key such as `d[dst]`, return literals with differing keys, a conditional `.update()`/`**` merge) names its optional keys where it builds them. (b) Every consumer of each optional key, enumerated from the producer's full list and never only from the key named in a bug, reads it with `.get(key, <explicit default>)` or under the producer's own condition; a consumer that assumes a fixed key set (CSV header, `DictWriter` fieldnames, column list) checks the set and raises on mismatch. (c) If a key would be absent because an input broke the producer's contract (layout, grouping, schema), the producer raises instead of omitting it, checking the contract from the input's own metadata, never from a proxy such as a length; `.get` defaults are only for keys that are legitimately optional (an explicit opt-out). (d) A defect of this class closes only after `docs/quality/evidence/BUG-0056/sweep_condkeys.py` and `sweep_returns.py` have been run with output and triage recorded, and after a test or a recorded run has executed the absent-key path through every consumer. Enforcement: the sweep scripts (re-runnable); a lint test needs a CR (tracker). | yes — 2026-09-30 (BUG-0056 §8; `docs/quality/evidence/BUG-0056/sweep_triage.md`): AST sweep of the 67 git-tracked `*.py` minus `inv_*`/`res_*`/`docs/` for conditionally stored keys (incl. loop-variable keys) and differing return literals, every UNGUARDED load read and classified; manual review of every consumer of `fit()`'s metrics dict; every TTA grouping consumer and validation-set builder. Found: BUG-0056 and BUG-0057 (fixed, `40dbecf`), BUG-0061 (`_log_metrics` header, open), BUG-0062 (TTA grouping fails open, open, needs a CR); all other rows not the mechanism | BUG-0056; third occurrence of BUG-0012/BUG-0014 (PA-0010, PA-0013 superseded); swept, BUG-0057, BUG-0061, BUG-0062 |
```

## 3. `docs/quality/PREVENTIVE_ACTIONS.md`: whole-line replacements
These follow the PA-0011 → PA-0027 precedent: the rule text is kept
verbatim after "Original text:", and the Swept? and Source cells are
unchanged.

**Replace line 27 (PA-0010)**
```
| PA-0010 | A function that conditionally populates a dict key must have every downstream consumer either guard on the same condition or use `.get()` with an explicit default — never mix unconditional indexing with conditional population of the same key in the same code path. | yes — found & fixed a missed sibling call site in the same function (BUG-0014) | BUG-0012; confirmed by BUG-0014 |
```
with
```
| PA-0010 | **Superseded by PA-0030** (BUG-0056, 2026-09-30: consumer-side and one key at a time; a sibling key with the same producer condition, stored through a loop variable, recurred in the same function). Original text: A function that conditionally populates a dict key must have every downstream consumer either guard on the same condition or use `.get()` with an explicit default — never mix unconditional indexing with conditional population of the same key in the same code path. | yes — found & fixed a missed sibling call site in the same function (BUG-0014) | BUG-0012; confirmed by BUG-0014 |
```

**Replace line 30 (PA-0013)**
```
| PA-0013 | When a bug fix changes how a dict key is consumed (e.g. `metrics['x']` -> `metrics.get('x', ...)`), grep the whole file for every other occurrence of that exact key access pattern before closing the bug — do not rely on only the call sites the investigation happened to quote. Extends PA-0010 by requiring the verification step a full sweep needs. | yes — repo-wide sweep of the general conditional-population-vs-unconditional-consumption mechanism (not just `tta_auc`) found nothing beyond BUG-0012/BUG-0014's already-fixed instances | BUG-0014 |
```
with
```
| PA-0013 | **Superseded by PA-0030** (BUG-0056, 2026-09-30: scoped to "that exact key", with an unrecorded text search; it missed `metrics['tuned_tta_accuracy']`, present in the same function when its sweep reported "nothing beyond BUG-0012/BUG-0014"). Original text: When a bug fix changes how a dict key is consumed (e.g. `metrics['x']` -> `metrics.get('x', ...)`), grep the whole file for every other occurrence of that exact key access pattern before closing the bug — do not rely on only the call sites the investigation happened to quote. Extends PA-0010 by requiring the verification step a full sweep needs. | yes — repo-wide sweep of the general conditional-population-vs-unconditional-consumption mechanism (not just `tta_auc`) found nothing beyond BUG-0012/BUG-0014's already-fixed instances. **Incorrect** (BUG-0056, 2026-09-30): `model_handler.py:722` (`metrics['tuned_tta_accuracy']`) was present at the time; method and candidates were not recorded | BUG-0014 |
```

## 4. `docs/quality/CR-0007-0008-OPEN-ISSUES.md`: tracker items
Suggested new section:

```
## BUG-0056 bookkeeping / PA-0030 sweep (2026-09-30)
- [ ] **BUG-0062** (needs a CR): `evaluate()` / `calibrate.collect_val_logits()` check the TTA grouping contract from the dataset (every leaf `GrousePatchDataset.expand_rotations`, sequential loader) and raise when `tta_group > 0`; drop `collect_val_logits`' per-rotation fallback. CR outline in BUG-0062 §6 — owner: lead
- [ ] **BUG-0061** decision + trivial fix: `_log_metrics` header mismatch on append → raise `ValueError` (recommended) vs. new file; one function — owner: next change to `model_handler.py`
- [ ] **PA-0030 enforcement** (needs a CR; `CLAUDE.md` §3.4): lint test from `docs/quality/evidence/BUG-0056/sweep_condkeys.py` with an allow-list seeded from `sweep_triage.md` — owner: lead
- [ ] LOW: `fit()` always calls `evaluate()` with the default `tta_group=4` and cannot opt out; decide with BUG-0062's CR whether `fit()` forwards `tta_group` (signature change) — owner: BUG-0062 CR author
- [x] CR-0012 deliverable 6 test plan item 7 (`smoke_test_training.py`) re-run after `40dbecf`: PASS, all 7 stages, scratch tree B (`docs/quality/evidence/CR-0012-d6/smoke_rerun.txt`)
```

## 5. Cross-references
- `docs/quality/evidence/CR-0012-d6/test_plan.txt` item 7: the verdict
  can be updated to "FAIL → PASS after `40dbecf` (BUG-0056, BUG-0057);
  see `smoke_rerun.txt`". That is the lead's file.
