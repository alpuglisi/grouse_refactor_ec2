# BUG-0076: the stratified draw truncates a non-integer year into a stratum instead of refusing it

> Found in the CR-0021 implementation code review (finding C1,
> 2026-10-03). Never observed on real data (every year is an integer).
> **Status: FIXED** (trivial fix, no CR; `CLAUDE.md` project notes).

## 1. Description
`generate_negatives._strata_of` casts each year with `int()` before
looking up its year stratum, so a non-integer year such as 2020.5 is
silently placed in stratum 2020. CR-0021 §2 B requires every positive and
pool row to map to a stratum "else raise"; the independent replay
(`acceptance_split.stratum_index_of`) refuses such a year, so pipeline
and replay disagree.

## 2. Where encountered
`generate_negatives.py:300-310` (`_strata_of`, called by
`draw_region_split`), as landed in `81cc603`. Reproduced by the reviewer
with a pool row of year 2020.5.

## 3. What it caused to fail
Nothing on today's data. On a pool or positive file with a fractional
year the pipeline would draw without error and write the files; R4 would
then fail with `ReplayError` at acceptance, so no wrong tree could be
accepted, but the defect would surface at the gate instead of at the bad
row, and the pipeline would not be fail-closed as §2 B requires.

## 4. What the defect was
```python
    for y in years:
        if pd.isna(y):
            raise ValueError(f"{what}: a row has no year (CR-0021 draw)")
        try:
            out.append(regions.year_stratum(int(y)))
```

## 5. Root cause analysis (Five Whys)
1. *Why was 2020.5 accepted?* `int(2020.5)` is 2020, which is in a stratum.
2. *Why was `int()` applied before the lookup?* Years arrive as floats
   when a CSV column holds a null; `int()` was used to normalise 2020.0
   to 2020 for the membership test.
3. *Why did that normalisation also accept invalid values?* `int()` is a
   lossy coercion: it maps an invalid value onto a valid one, and the
   validity check (stratum membership) ran on the coerced value, not the
   value as read.
4. *Why was it not caught by tests?* The unit tests fed integer years
   only; no test fed a value that the coercion would change.

**Root cause:** a validity check (stratum membership) was applied to a
value after a lossy coercion, so the coercion decided validity.

## 6. Corrective action
`_strata_of` refuses a year with `float(y) != int(y)` before the lookup
(2020.0 still accepted); test
`tests/test_cr0021.py PipelineStratifiedDraw.test_non_integer_year_raises`
(fails against the old code: no raise). No CR (one function, no behaviour
change beyond the defect). Outputs on today's data unchanged (all years
integers).

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "cast",
"int(", "coerce", "truncat", "astype", "encoder".
**Match:** **BUG-0036 / PA-0006 (scope extension)** — write-side raster
value encoders cast NaN/inf to 0 instead of refusing: the same mechanism
(a lossy coercion turns an invalid value into a valid one before anything
checks it). PA-0028 also lists "integer casts of NaN" among forms its
lint cannot see.
**Prior-preventive-action failure analysis.** PA-0006's extension is
scoped to raster nodata and to "functions converting a physical value to
a stored code"; PA-0028 to validity masks. A stratum lookup on a year is
neither, so the rule did not apply: **too narrow** (domain-scoped to
rasters, where the mechanism is general).

## 8. Preventive action
**PA-0034 (extends PA-0006/BUG-0036 and PA-0028 beyond rasters):** a
validity or membership check runs on the value as read; a coercion that
can change a value (`int()`, `round`, `astype(int)`, clipping) is applied
only after the value is shown to be exactly representable, and an
unrepresentable value is refused.

**Sweep (§3.5), by mechanism:** every `int(...)`/`astype(int)` on a
`year` in git-tracked non-test, non-`legacy/`, non-`docs/`, non-`inv_`/
`res_` `*.py` (grep, 2026-10-03). The P/N/C year columns are now guarded
at acceptance: E15(a) fails any P, N or C year that is in no stratum,
and the replay's `stratum_index_of` refuses non-integers, so a fractional
year in a split file fails the gates before `train.py`'s
`build_datasets` (standing E15) reads it. The casts in `dataset.py`
(`:102`, `:192`, `:266`), `train.py:221,246`, `grouse_data.py:358`,
`generate_negatives.py:233` and `prepare_training_data.py:158` therefore
read only gate-checked integer years for P/N/C; the diagnostic casts
(`diagnose_wetland.py:65-72`, `download_tcc_nlcd.py:277`) read the same
files. No new instance; no new BUG.

## Cross-references
CR-0021 (implementation review C1), BUG-0036, PA-0006, PA-0028, PA-0034.
