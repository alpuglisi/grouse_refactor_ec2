# BUG-0061: `_log_metrics` appends rows under a header written by an earlier run with a different key set (PA-0030 sweep)

## 1. Description
`GrouseModelHandler._log_metrics` appends one row per epoch to
`--metrics-csv`. It writes a header only when the file is new. Each row
is written with that run's own sorted key set. `fit()`'s metrics key set
depends on run options:
- `dropout` is present only with `--dynamic-dropout`;
- the TTA keys are present only when the validation set is a multiple of
  4 (see BUG-0056/BUG-0062).

A later run appending to the same file with a different key set writes
rows that do not match the header. If a key is missing, every later
column shifts left and the file still parses, so the damage is silent.
If a key is extra, the file no longer parses.

## 2. Where encountered
- PA-0030 sweep (BUG-0056 §8), 2026-09-30, step 3: a manual review of
  every consumer of `fit()`'s metrics dict.
- The defect: `model_handler.py:1481-1490`.
- Caller: `model_handler.py:1370-1371`. The path comes from
  `train.py --metrics-csv` (`train.py:492-493`, help: "Append per-epoch
  metrics to this CSV."), passed at `train.py:1161`.
- `git blame`: initial commit `29c194a`.

## 3. What it caused to fail
- **Observed in real use:** nothing checked. Whether any existing metrics
  CSV mixes runs is not known.
- **Reproduced:** `docs/quality/evidence/BUG-0056/bug0061_repro.py`,
  output in `bug0061_repro_output.txt`. It calls the real
  `_log_metrics`.
  - **Case A.** Run 1 has `dropout`, run 2 does not. Run 2's row is
    written under the old header: `epoch` lands in the `dropout` column,
    `val_loss` in the `epoch` column, and `val_loss` reads NaN. The file
    parses without error.
  - **Case B.** The reverse. The file has 4 fields in a 3-column file,
    and `pd.read_csv` fails with `ParserError`.
- **How it is reached:** `python train.py --metrics-csv m.csv`, then a
  second run (or a `--resume`) with `--dynamic-dropout` toggled, appending
  to the same `m.csv`. The documented behaviour is "append", so reusing a
  file across runs is expected.
- **Not affected:** within a single `train.py` invocation the key set
  does not change. Ensemble members share the flags.

## 4. What the defect was
`model_handler.py:1481-1490`:
```python
    def _log_metrics(path, metrics):
        import csv
        import os
        keys = sorted(metrics)
        new = not os.path.exists(path)
        with open(path, 'a', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            if new:
                w.writeheader()
            w.writerow({k: metrics[k] for k in keys})
```
The header is written from the first row's keys. Later rows use
`fieldnames=keys` from their own dict and never compare against the
header that is already in the file.

## 5. Root cause analysis (Five Whys)
1. **Why can columns shift?** Each row is laid out by its own key set,
   while the header on disk reflects the key set of the run that created
   the file.
2. **Why do the key sets differ?** `fit()`'s metrics dict is a
   conditional-key producer. Its key set depends on run options and on
   the validation set.
3. **Why does the writer not notice?** It assumes the key set is fixed.
   It checks only whether the file exists, not whether its header
   matches.
4. **Why was that assumption not caught by PA-0010/PA-0013?** Those
   rules concern reading one key by index (`metrics['x']`). A consumer
   that assumes the whole key set (a header) is the same mechanism, but
   it is not a single-key read, so no rule or sweep covered it.

**Root cause:** a consumer of a conditional-key producer assumed a fixed
key set, the one in the CSV header written by the first run, and did not
check it on append.

## 6. Corrective action
**Not fixed in this pass.** The right behaviour on a mismatch is a design
choice with consequences for training runs:
- (a) Raise before writing, which is fail-closed. This aborts `fit()`
  after epoch 1. The checkpoint and resume state are already saved by
  then.
- (b) Write to a new file and print where.
- (c) Check once at `fit()` start instead. That touches a second
  function, so it is no longer trivial.

The recommendation is (a), in `_log_metrics` only:
- read the existing header;
- if it differs from `sorted(metrics)`, raise `ValueError` naming the
  added and missing keys and the file.

That is one function with no signature change. Because it can abort a
training run, it goes to the tracker for the owner's decision rather
than being applied here.

Status: **OPEN** (tracker; owner: next change to `model_handler.py`).

## 7. Recurrence review
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`, for "header",
"CSV", "DictWriter", "column" and "append".
- **Mechanism match: BUG-0012/BUG-0014/BUG-0056** (conditional-key
  producer, consumer assumes the key is present). BUG-0056 §7 holds the
  failure analysis of PA-0010/PA-0013. This finding is one of the reasons
  PA-0030 names "consumers that assume a fixed key set" explicitly.
- **Not a match: BUG-0016 / PA-0014** (a shared mutable output path).
  That is about two scripts writing one file, not a header mismatch.

## 8. Preventive action
**PA-0030** (from BUG-0056), no new PA. Its clause "a consumer that
assumes a fixed key set (CSV header, `DictWriter` fieldnames, column
list) must check the set" covers this bug.
