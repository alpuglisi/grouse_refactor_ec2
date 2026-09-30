# BUG-0082: `diagnose_training.py` section 1 multiplies only positives by 4, but `train.py` rotation-expands both classes, so it reports a 4:1 ratio, an 80 % all-positive baseline and a false "imbalance is severe" verdict on balanced data

> Found by the 2026-09-30 static code review at `3b3e7d1`.
> **Status: FIXED in code (`2c05388`, 2026-09-30, trivial fix, no CR); validation pending on the data host; owner: lead.**

## 1. Description
Section 1 ("what the model actually sees") computes the effective class
composition by multiplying the positive counts by 4 and leaving the
negatives as counted. `train.build_datasets` applies
`expand_rotations=True` to both classes ("symmetric 4x -> 1:1 effective
balance", `train.py:351-352`) for training and validation. On today's
files (4,809 positives and 4,809 negatives pooled, validation prevalence
0.5) the tool prints a 4.0 : 1 training ratio, an "expected train
samples" count short by three times the negatives, an all-positive
validation baseline of 80 % where the true baseline is 50 %, and, since
4 > 3, the "[!] Training imbalance is severe" branch fires
unconditionally.

## 2. Where encountered
- `diagnose_training.py:70-87`.
- Producer of the real rule: `train.py:351-359` (train) and `:388-393`
  (validation), `dataset.py:293-294` (`__len__`), `:445-453` (`labels`).

## 3. What it caused to fail
A user comparing a run's frozen accuracy with the printed all-positive
baseline, or reading the severe-imbalance verdict, is led to a
constant-predictor diagnosis on a balanced set. Diagnostic output only;
no model input.

## 4. What the defect was
`diagnose_training.py:70-87`:
```python
    eff_tr_pos = total_tr_pos * 4   # rotation expansion
    eff_va_pos = total_va_pos * 4
    print(f"\n  AFTER 4x rotation expansion (what the model actually sees):")
    print(f"    train: {eff_tr_pos:,} pos vs {total_tr_neg:,} neg "
          f"-> ratio {eff_tr_pos / max(total_tr_neg, 1):.1f} : 1")
    ...
    maj = eff_va_pos / max(eff_va_pos + total_va_neg, 1) * 100
    print(f"    val accuracy if model just predicts ALL POSITIVE: {maj:.2f}%")
    print(f"    (compare to the frozen accuracy from your run)")
    if eff_tr_pos / max(total_tr_neg, 1) > 3:
        print(f"\n  [!] Training imbalance is severe. This alone explains "
             f"collapsed, frozen predictions. See the fix list the "
             f"assistant provided.")
```

## 5. Root cause analysis (Five Whys)
1. *Why is the ratio wrong?* Only positives are multiplied by 4.
2. *Why?* The diagnostic restates the expansion rule as a literal from
   the original project ("positives keep 4x rotation ... negatives
   don't", `train.py:16-17` header), which `train.py` later changed.
3. *Why did the change not reach it?* The diagnostic derives nothing
   from the producer; it does not call `build_datasets` or read
   `GrousePatchDataset.labels`, so no code path ties it to the rule.
4. *Why was it not caught by BUG-0011's fix?* That fix (CR-0005) covered
   the checkpoint-construction defaults of section 3; PA-0009 speaks of
   construction defaults, not of pipeline facts the diagnostic reports.

**Root cause:** the diagnostic restates a pipeline rule (which classes
are rotation-expanded) as a literal instead of deriving it from the
producer, so a producer change left it wrong with nothing to detect it.

## 6. Corrective action
**None yet.** Trivial fix: build the datasets through
`train.build_datasets` (or `GrousePatchDataset` with the same
`expand_rotations` for both classes) and report `len(ds)` and
`labels.mean()`; delete the literal `* 4` and the `> 3` verdict.
**Implemented 2026-09-30, commit `2c05388` (trivial fix under CLAUDE.md §1: one function, no public signature, file format or schema change).** diagnose_training.py section 1 now expands both classes by the same factor (`EXPANSION = 4`), reports a majority-class baseline and a two-sided ratio check, and prints the assumption it makes (PA-0039). Validation here: `python -m py_compile` only, since this environment has no numpy, torch, rasterio or data tree. To verify: `python diagnose_training.py` on the data host: section 1 shows a 1.00 : 1 ratio and no imbalance warning on the CR-0019 files.
Status: **FIXED (code); validation pending on the data host.** Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for
"diagnose_training", "expansion", "rotation", "ratio", "defaults".

**Matches:** BUG-0011 (same file, section 3 defaults; PA-0009),
BUG-0057 (`smoke_test_training.py` built validation negatives
unexpanded; a sibling misreading of the same rule).

**Prior-preventive-action failure analysis.** PA-0009 requires
diagnostics to construct the model with the training entrypoint's
defaults; it says nothing about other pipeline facts a diagnostic
reports (class composition, expansion). BUG-0057's fix corrected one
builder without a rule. Category: too narrow.

## 8. Preventive action
**PA-0039**: a diagnostic that reports a pipeline fact (class
composition, expansion factor, split sizes, feature list, window size)
derives it by calling the producer (`train.build_datasets`,
`GrousePatchDataset.labels`, `discover_features`) or importing its
constant, never by restating the rule as a literal; a diagnostic that
cannot call the producer prints the assumption it makes next to the
number.

**Sweep (§3.5), literals restating a pipeline rule in diagnostics:**
`diagnose_training.py:70-87` (this, four sites); `smoke_test_training.py`
train negatives `expand_rotations=False` (documented deviation,
BUG-0085 for the geometry side); `diagnose_wetland.py`,
`diagnose_road_bias.py`, `diagnose_water_bias.py`, `inspect_point.py`
(read through `grouse_data`/`dataset`; no restated rule found).

## Cross-references
BUG-0011, BUG-0057, BUG-0083, BUG-0085, PA-0009, PA-0039, PA-0040.
