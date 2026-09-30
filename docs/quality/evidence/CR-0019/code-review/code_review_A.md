# CR-0019 code review A: implementation on branch `cr0019-combined`

- **Reviewer:** A (independent; did not write either half)
- **Head reviewed:** `c599307e23c9bedbb83d23c4ce3801122f33d328` (`git diff 140a73e cr0019-combined`)
- **Against:** CR-0019 v3 (APPROVED), its review log, PREVENTIVE_ACTIONS.md
- **Method:** read-only. The tests ran in a scratch `git clone` at the head under `/tmp/claude-1000/cr19revA/`. Nothing was written to the worktree, the main tree or `data/`.

## 1. Are the two halves independent?
- The pipeline half is `628083d` + `0a5e14e`. The acceptance half is `65b2469` + `65768a4`. Both branch from `140a73e` (`git merge-base` = `140a73e`), and they touch disjoint files.
- The combine commits `c990a82` and `c599307` are exact copies. Every pipeline file is byte-equal to `0a5e14e` and every acceptance file is byte-equal to `65768a4` (`git diff --quiet`). Nothing was edited in the combine.
- `tests/test_cr0019.py` does not read `acceptance_split.py`. The acceptance tests build their oracles with hashlib, pyproj and scipy directly (`_thin_key`, `_xy`, `_min_dist`), not from the pipeline.

## 2. Do the halves agree on floor semantics?
| rule | pipeline | replay | agree |
|---|---|---|---|
| positives step 2 inclusive `>=` | `prepare_training_data.py:388-389` `df["year"] >= regions.YEAR_MIN` | `acceptance_split.py:1015` `>= self.C["YEAR_MIN"]` | yes |
| floor before window and thin | step 2, before `window_mask` / thin | `run_positives` `:1058`, before `window_filter` | yes |
| null year raises, habitat or not, before the habitat filter | `:383-387` ValueError | `check_years` `:1003-1011` ReplayError, called before `habitat_rows` | yes |
| count "2" is after both conditions | `:390` | `:1059` | yes |
| pool step 1 drops only non-null `< YEAR_MIN`; nulls go on to step 7 | `generate_negatives.py:374-375` (per region, before concat) | `pool_year_floor` `:1017-1022` (after concat) | yes: same rows, same order |
| count "1" is after the floor | `count(1, pool)` after concat | `_count(..., 1)` after `pool_year_floor` | yes |
| constant source | `regions.YEAR_MIN`, read at call time; `measured_constants()["YEAR_MIN"]` goes into both manifest sections | config `constants.YEAR_MIN`. E11(c) checks it equals the manifest; E11(e) checks it equals the `regions.py` literal (parsed) | yes |

- **Real data.** The combined scratch run by the evidence agent (uncommitted, in `.claude/worktrees/cr0019-combined/docs/quality/evidence/CR-0019/combined/`) gives:
  - `acceptance_run1.log`: 20/20 GATEs, E14 and R1-R4 all PASS, so the pipeline and the replay agree row for row on real data;
  - `mc_live_vs_scratch.txt`: MC PASS 42/42;
  - `standing_check_run1.txt`: PASS;
  - `e14_crosscheck_run1.txt`: P and N years are both {2020..2024}, C has no year below 2020;
  - `yeargap_check_run1.txt`: tolerance 2 leaves 12/12 frames unchanged; tolerance 1 refuses 12/12.
- That evidence was not committed when this review finished. Re-check the committed copy.

## 3. Does the implementation match the CR?
Every item in the §2 code table and the §3 acceptance amendments is present:
- `YEAR_MIN` and its comment in `regions.py:64-73`;
- the docstrings for step 2 and pool step 1;
- `get_negatives --years` defaults to `range(YEAR_MIN, …)`;
- `filter_by_year_gap` keeps its name and signature, uses the same verdict and return expression, and raises `SystemExit` naming region, what, count, years, tolerance and the remedy. Its docstring, the `build_datasets` comment and the `--max-year-gap` help are updated;
- the config gains `constants.YEAR_MIN` (an integer) and `regions_py.names.YEAR_MIN`;
- `GATE_SECTION_SHA256` is re-pinned for `constants` and `regions_py` only;
- the E14(a)/(b) predicates are as in the CR table, E14 is in the standing subset with `include_C=False`, and `len(GATE_IDS)` is 20;
- the seven attack rows each carry their fixture-existence asserts, the fixture years are deterministic, the pooled P and N year sets are equal by construction (asserted), and the replay unit tests (inclusive floor, pool null kept at step 1 and dropped at step 7, null sighting raises) are present.

## 4. Tests and their power
**Suites at head (scratch clone):** all pass.

| suite | tests | result |
|---|---|---|
| `test_cr0019`, `test_shared_constants`, `test_nodata_zero_lint`, `test_cr0012`, `test_cr0017` | 93 | OK |
| `test_pa0027_lint` (needs full history, so run in the clone) | 11 | OK |
| `test_acceptance_split` | 128 | OK (~100 s) |

**Mutations:** I wrote each one myself. All were killed.

| mutation | killed by |
|---|---|
| pipeline step 2 `>=` changed to `>` | `test_cr0019` (1 failure) |
| pipeline null-year raise removed | `test_cr0019` (2 failures) |
| pool step 1 also drops null years | `test_cr0019` (1 failure) |
| pool step 1 floor removed | `test_cr0019` (2 failures) |
| `filter_by_year_gap` prints instead of raising | `FilterByYearGap` (1 failure) |
| replay `year_floor` `>=` changed to `>` | `TestYearFloorUnits` (4 failures) |
| replay `check_years` call removed | 1 failure |
| E14 removed from the standing subset | 1 failure |
| E14(b) disabled | Units + Attacks (3 failures) |
| replay pool floor drops nulls | 2 failures |

The CR's floor-after-thinning attack is covered twice:
- **Pipeline side:** `test_floor_precedes_thinning` has a control asserting that, with no floor, the pre-floor point wins the thin.
- **Acceptance side:** the `FloorAfterThin` attack row.

## 5. Does the train-time refusal break any legitimate caller?
- **`train.py main`:** default 2. On the post-CR split files nothing is refused (evidence: 12/12 frames unchanged).
- **`calibrate.py:356`** calls `build_datasets` with the default `train_year_gap=2`, whatever tolerance the checkpoint was trained with. That is pre-existing, and after the change it does nothing on the new data.
- **`bench_pipeline.py:96`:** default 2, so no effect.
- **`pretrain.py`** imports only `discover_features`, `sample_background_points` and `WORKERS`. `filter_by_year_gap` is not reached.
- **`smoke_test_training.py`, `diagnose_*`, `tune_bins.py`:** none calls `filter_by_year_gap` or `build_datasets`. They read the split files directly and will see floored positives, as the CR's Impact section says.
- **Sweep scripts** (`sweep/launch2.sh`, `launch3.sh`, `jobs.txt`): all pass `--max-train-year-gap -1`, which disables the check. They train on the same rows as the default, because no split-file year is below `YEAR_MIN`.
- **Values that would refuse:** no caller in the tree passes 0 or 1. A value of 3 or more is looser than 2, so it cannot refuse on data that passes at 2.
- **In-process catchers:** nothing catches `SystemExit` around `build_datasets`. The only `except BaseException` blocks (`prepare_training_data.py:224`, `generate_road_distance.py:159`, `realign_rasters.py:112`) are unrelated atomic-write cleanups.

**Result:** no legitimate caller breaks.

## 6. Is the E14 standing subset safe for every training start?
- **Who calls it:** `standing_checks` runs only from `train.build_datasets`, which serves `train.py`, `calibrate.py` and `bench_pipeline.py`, and from `acceptance_split.py --standing`. `predict.py` does not call it.
- **Pooling:** E14 in the standing subset reads only P and N, pooled over the config's `REGIONS`, so `--regions ME` does not change the verdict. The files it reads are already cached by E0/E1.
- **On main:** nothing changes before the merge.
- **After checkout or merge:** the config sha256 change alone refuses all training until the new record is written (CR § Impact, the accepted refusal window). E14 adds no further refusal on the regenerated files: the combined scratch run gives standing PASS and P and N year sets equal.
- **No false refusal from dtypes:** E14(b) compares float sets, so an int-typed P column against a float-typed N column (for example "2021.0") cannot fail it.

## 7. Config hash and merge timing
- `docs/quality/acceptance_split.json` changes, so its sha256 changes. That is the planned refusal window (deliverable 6). Nothing in the code departs from the CR's order: checkout the branch, run, record, then merge.
- The record's `config_sha256` is a content hash, so it survives the merge.

## 8. PA compliance
- **PA-0025 (a constant's literal lives only in `regions.py`):** the `2020` literal as the floor appears only in `regions.py:73`.
  - `get_negatives` imports `YEAR_MIN`, and an AST test proves there is no literal in its `--years` default.
  - The acceptance config's `2020` is the independent config value the CR requires, and E11(e) cross-checks it against the `regions.py` literal.
  - `test_shared_constants` pins `YEAR_MIN`.
  - Year literals in other files (`download_rev.py`, the TreeMap vintages) are raster vintages, not the floor.
- **PA-0027 (no broad handlers that fail open):** the diff adds no handler. The PA-0027 lint passes.
- **PA-0020 (both classes selected on the same support):** both classes are now selected by one constant, and E14 is the build-time support comparison on the time axis. The residual distribution difference within 2020-2024 is out of scope (CR §5).
- **PA-0021(a) (attacks cannot pass vacuously):** every attack row asserts that its fixture rows exist. §4 above records a reviewer's mutation runs.
- **PA-0030 (optional dict keys):** `YEAR_MIN` is unconditionally present in `measured_constants()` and in the config, so no key is optional.
- **PA-0031 (`except ... as` names read outside the clause):** the diff adds no `except ... as`.

## 9. Findings
| id | severity | file:line | finding and concrete scenario | fix |
|---|---|---|---|---|
| A-1 | LOW (tracker item B12) | `train.py:256` | The refusal raises a bare `SystemExit` from a library function. The CLI behaviour is correct: the message goes to stderr and the process exits 1. It is also fail-closed: an `except Exception` wrapper cannot swallow it. Two drawbacks: a programmatic caller or test cannot tell a year-gap refusal from any other `SystemExit` without matching the message text, and `BaseException` cleanup handlers see it as an ordinary exit. | **Recommend** `class YearGapRefused(SystemExit)` in `train.py`, raised with the same message. This keeps the exit semantics and the PA-0027 fail-closed property, and `FilterByYearGap` can then `assertRaises(train.YearGapRefused)`. It is optional and can be done in the CR-0020 train-side work. Close B12 in the tracker either way. |
| A-2 | LOW | `acceptance_split.py:1017-1022` (`pool_year_floor`) | If a `gbif_negatives_R.csv` lacks a `year` column, the pipeline raises a clear ValueError (`generate_negatives.py:372`), but the replay raises a raw `KeyError: 'year'`. That error is still recorded by the handler at `:984` and reported as an R-gate FAIL, so the result is fail-closed and no wrong acceptance is possible. Only the diagnosis is poorer. | In `load_candidates`, raise `ReplayError(f"{rpath(...)}: no 'year' column")` per region, mirroring `check_years`. |
| A-3 | LOW | Test plan, deliverable 4 | The CR asks that "`build_datasets` (via `bench_pipeline.py` or a direct call) drops 0 at tol 2 and refuses at tol 1". The evidence calls `filter_by_year_gap` directly, with the features from `discover_features`. That is equivalent, because `build_datasets` makes exactly those four calls, but it is not the literal item. It was not possible in the pipeline-only run (there was no record yet). The combined scratch tree now has a record. | Optionally have the evidence agent call `train.build_datasets(..., train_year_gap=2)` and `=1` on the combined scratch tree and record the result, or record in RUN.txt why the direct call is sufficient. |
| A-4 | INFO | `train.py:239-241` docstring | "returns the frame unchanged" is literally `df[keep].reset_index(drop=True)`: content-equal, but a new object with a reset index. The CR mandates the same return expression, and every caller already reads split files with a default index. | None. |
| A-5 | INFO | `calibrate.py:356` | Calibration always checks at tolerance 2, whatever the checkpoint's `--max-year-gap`. This is pre-existing, not introduced here, and a no-op on post-CR data. | None (it could be noted for CR-0020). |

There are no BLOCKING, MAJOR or MEDIUM findings.

## 10. Verdict
**APPROVE WITH FOLLOW-UPS.** A-1 to A-3 are LOW and go to the tracker.

- The implementation matches CR-0019 v3 exactly.
- The two independently written halves agree on every floor rule, confirmed by exact R1-R4 on real data in the combined scratch run.
- The tests are powerful: all 10 mutations were killed.
- No legitimate caller breaks.
- The E14 standing subset is safe.
- No PA is violated.

**B12 recommendation:** adopt a named `SystemExit` subclass (A-1), either now or as a tracked follow-up. The bare `SystemExit` is acceptable for approval.
