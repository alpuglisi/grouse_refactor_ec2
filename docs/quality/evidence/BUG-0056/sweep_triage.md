# PA-0030 sweep triage (BUG-0056 §8), 2026-09-30

Mechanism swept: a producer whose output key set depends on a runtime
condition, and a consumer that reads a key (or assumes the key set) as if
it were always present.

Scope: git-tracked `*.py` minus `inv_*`, `res_*`, `docs/` (67 files),
tree at `6ab66d7`.

## Method
1. `sweep_condkeys.py` (AST). It lists every string key stored under a
   condition, including keys stored through a loop variable over a
   literal tuple. For each key it lists every plain `X['key']` load in
   the swept files, tagged GUARDED / CO-CONDITIONAL / UNGUARDED.
   Output before the fix: `sweep_condkeys_at_6ab66d7.txt` (60 keys with an
   UNGUARDED load). After the fix: `sweep_condkeys_after_fix.txt` (59 keys).
   The only key that differs is `tuned_tta_accuracy`, which is BUG-0056.
2. `sweep_returns.py` (AST). It lists functions whose `return {...}`
   literals have different key sets (`sweep_returns_output.txt`).
3. Manual review of every consumer of the one producer that is known to
   vary its key set: `fit()`'s per-epoch `metrics` dict (TTA keys depend on
   the validation set; `dropout` depends on `dynamic_dropout`). That
   covers the status line, `selection_score`, `best_*`, the divergence
   guard, TensorBoard, `_log_metrics`, and callers in `train.py`,
   `bench_pipeline.py` and `calibrate.py`. `grep` for `tta_auc|tta_ap|
   tta_accuracy|strict_accuracy|hedged_pct|tuned_accuracy|tuned_tta|
   mean_pos|mean_neg|dropout` over the same scope.
4. Grouping contract (the reason the key goes missing): every consumer
   that groups validation logits by `tta_group`/4
   (`model_handler.evaluate`, `calibrate.collect_val_logits`,
   `diagnose_wetland.score_points`) and every builder of a validation set
   (`expand_rotations=` call sites).

## Findings
| Site | Finding | BUG |
|------|---------|-----|
| `model_handler.py:1339` | `metrics['tuned_tta_accuracy']` read unconditionally; stored only when `_tta_logits` exists (`:1318-1322`, key via loop variable `dst`) | BUG-0056 (fixed) |
| `smoke_test_training.py:90-96` | validation negatives built with `expand_rotations=False` → violates the 4-rotation grouping contract | BUG-0057 (fixed) |
| `model_handler.py:1481-1490` `_log_metrics` | CSV header fixed from the first row ever written; a later run with a different key set (e.g. `--dynamic-dropout` adds `dropout`) appends rows under a stale header → shifted columns or an unparseable file | BUG-0061 (open) |
| `model_handler.py:1888`, `calibrate.py:154` | TTA grouping inferred from `len % tta_group` alone: non-conforming set → TTA silently skipped (evaluate) or per-rotation logits silently returned (calibrate); conforming length but unrotated class → points silently averaged together | BUG-0062 (open, needs CR) |

## UNGUARDED rows classified as not the mechanism
Every UNGUARDED row in `sweep_condkeys_after_fix.txt` was read in context.
Each falls into one of the classes below.
- **Store in a loop over a fixed collection, load in a loop over the same
  collection**, so every key is present:
  - `prepare_training_data.py:375-405` / `:439-441` (`'1'..'6'`, over
    `REGIONS`);
  - `acceptance_split.py:902-908`, `:951`;
  - `generate_negatives.py:362`, `:419-421`;
  - `get_negatives.py:295,328` (`pstate` is initialised with `exhausted`
    at `:273`);
  - `analyze_grouse.py:181-182`, `legacy/audit.py:183-184` (every loaded
    file gets `state`/`year`);
  - test fixtures `tests/test_check_partition.py:219-372`,
    `tests/test_cr0008.py:121`, `tests/test_acceptance_split.py:307-309,
    581, 787`, `tests/test_cr0012.py:539, 581-584`.
- **All branches store the key** (if/elif/else, the else branch raises, or
  both arms assign):
  - `analyze_grouse.py:533-537`, `:786-794` (`evt_phys`/`evt_group`),
    `:811-817` (`spatial_*`, else raises), `:913-978` (`env_zone`, and
    `Used_Pct`/`Classification` read only inside the same branch);
  - `check_partition.py:560-562`;
  - `legacy/audit.py` equivalents.
- **Fill-if-missing or overwrite of a key already present**:
  - `dataset.py:83-99` (`label` validated right after, `weight`, `year`);
  - `grouse_data.py:494,518`;
  - `analyze_grouse.py:197`, `check_partition.py:186` (longitude sign
    flip);
  - `analyze_grouse.py:520` (`fdist` fillna under `'fdist' in bg`);
  - `models.py:912` (`vocab` overwrites the base spec's value);
  - `download_rev.py:459`, `legacy/download_more.py:325` (`results['ok'] +=`
    on a key initialised in the literal).
- **Lazy cache, read right after the store under `not in`/`is None`**:
  - `grouse_data.py:574`, `regions.py:96`, `prepare_training_data.py:100`.
- **try/finally (no except), so an exception propagates and the key is
  never read missing**: `symptom_check.py:985-1011` (`item1..4`,
  `rematch`).
- **Different object that shares a key name** (the heuristic matches by
  name). Examples:
  - `model_handler.py:1111` `state['epoch']` (resume state) vs `metrics`;
  - `model_handler.py:976-1001` `self.hp['lr']`;
  - `acceptance_split.py:2385` `notes['missing']` vs gate result
    `r['missing']`;
  - `acceptance_split.py:848/855` loop-variable stage names vs config
    dicts;
  - `symptom_check.py:279-280` `auc`/`ap`, read only via
    `.get` in production (`:1074-1075`), and in tests on fixtures that have
    both classes;
  - DataFrame columns `split`, `region`, `year`, `longitude` read from
    other frames.
- **Guarded by the key's own condition, which the heuristic did not
  recognise**:
  - `diagnose_road_bias.py:180`, `diagnose_water_bias.py:175`
    (`"positives (trained on)" not in res` → `continue`);
  - `symptom_check.py:158-161` (`value_stats` optional keys read under
    `both`, the same condition as `size > 0`).
- `sweep_returns.py`: `model_handler._loader_extra` (kwargs spread,
  consumer is `DataLoader(**...)`); `symptom_check.value_stats` (see
  above). Neither is the mechanism.

## Not covered (stated limits)
The sweep does not cover:
- keys built at runtime (f-strings);
- `.update()`/`**` merges and `setdefault`;
- keys consumed through `DataFrame(...)`/`to_csv` column sets.

Step 3 covered `fit()`'s metrics by hand for these forms. No other
producer in scope was found to vary its key set by a runtime condition.
