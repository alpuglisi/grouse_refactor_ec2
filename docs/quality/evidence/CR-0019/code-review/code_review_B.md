# CR-0019 code review B (independent, adversarial)

- Branch: `cr0019-combined`. Code reviewed at **c599307** (`git diff 140a73e c599307`). Head at end of review: **3cd1ea9**, which adds only `docs/quality/evidence/CR-0019/combined/` (evidence, no code). That evidence was reviewed too.
- Nothing in the worktree or the main tree was edited. All scratch work is under `/tmp/claude-1000/rb/`.

## What was run

1. **Suites.** `python -m unittest tests.test_acceptance_split tests.test_cr0019 tests.test_cr0012` in a `git archive` copy of c599307 (with `git init`): **177 tests OK**.
   - `tests.test_pa0027_lint` in a full-history clone at 3cd1ea9: **11 OK**. It fails with 5 errors in an archive copy only because it needs `git show` of historical commits; that is an environment artefact.
   - `test_shared_constants`, `test_nodata_zero_lint` and `test_cr0017`: OK.
2. **Differential run of pipeline against replay** (`/tmp/claude-1000/rb/diff/diff.py`).
   - Built a synthetic tree with `test_cr0012.build_tree`. Every evaluated-sighting year was replaced by a float drawn from {YEAR_MIN-2, YEAR_MIN-1, YEAR_MIN, YEAR_MIN+1, YEAR_MIN+3}. Every non-null candidate year was redrawn from {YEAR_MIN-1, YEAR_MIN, YEAR_MIN+2, YEAR_MIN+3}. Null candidate years were kept.
   - Ran the real `prepare_training_data` + `generate_negatives`, then `acceptance_split.Replay.run_positives` / `load_candidates` on the same tree.
   - Result: P (key, split, year) is identical in all 3 regions. Count "2" is equal (106/105/87). Pool count "1" is equal (854/857/848). C has no year below YEAR_MIN and no null years.
   - No disagreement was found for float vs int dtype, year == YEAR_MIN, or null candidate years.
   - Non-numeric year strings (object dtype) raise `TypeError` on both sides. Nothing is accepted silently: the replay's broad handler at `acceptance_split.py:984` records it as an R-gate FAIL.
   - Null sighting years raise on both sides, whether or not the row is habitat.
3. **Mutation testing.** Each mutant was built in its own scratch copy with `git init`. Acceptance mutants were run against `TestYearFloorAttacks` + `TestYearFloorUnits`; pipeline mutants against `tests.test_cr0019`.

| mutant | result (killing test) |
|---|---|
| A1 replay step 2 `>` instead of `>=` | killed (off_by_one, reference_year_sets, ...) |
| A2 replay pool floor also drops null years | killed (pool_step1_drops_below_floor_keeps_null, count_and_step7) |
| A3 replay pool floor moved after dedup | killed (count_and_step7) |
| A4 E14(a) bound lowered to `< ymin-1` | killed (no_floor, train_split_only, e14a_*) |
| A5 E14(a) integral check removed | killed (e14a_positives) |
| A6 E14(a) null P/N allowed | killed (e14a_positives) |
| A7 E14(a) C check removed | killed (no_pool_floor, e14a_pool) |
| A8 E14(b) compares only min year | killed (positives_later_than_every_negative, upper_end_divergence) |
| A9 E14(b) disabled | killed |
| **A10 E14(b) weakened to `P ⊆ N`** | **SURVIVED**. Also survives the full `test_acceptance_split` + `test_cr0012` + `test_cr0019` run (finding F1) |
| A11 E14(b) per (region, year) instead of pooled | killed (the fixture's per-region sets differ, so the reference must PASS only when pooled) |
| A12 null-year check on habitat rows only | killed (null_year_sighting_raises uses a non-habitat row) |
| A13 null-year check removed | killed |
| A14 E14 removed from `standing_checks` | killed |
| A15 E14 reads P in place of N | killed |
| P1 pipeline step 2 `>` | killed (floor_drops_below_keeps_equal) |
| P2 pipeline floor after thinning | killed (floor_precedes_thinning, floor_drops_below_keeps_equal) |
| P3 pipeline pool floor drops null years | killed |
| P4 refusal replaced by drop (print) | killed (refuses_when_any_row_would_be_excluded) |
| P5 null check on habitat rows only | killed (null_year_raises_habitat_or_not, nonveg=True) |
| P6 pipeline pool floor removed | killed |
| P7 pool floor as literal 2020, not `regions.YEAR_MIN` at call time | killed (YearMinAboveLowestCandidate) |
| P8 pool floor `<=` | killed |
| P9 refusal only for train sets | killed |

4. **Attack-row preconditions (PA-0021(a)).** Each of the seven attack rows in CR §3 has a test that first establishes its fixture rows independently of the gate: pandas on the files, pyproj/cKDTree for distances, and hashlib for the thin key (`_thin_key`).
   - **Floor after thinning:** the precondition is checked on the BASE tree, and the attack's loss of the partner is checked separately.
   - **Source-level floor:** the candidate is within BUF of a pre-floor sighting only, is absent from the base C, and is present in the attack's N.
   - **Train split only:** a pre-floor positive exists in a val block, confirmed against B.
   - **Positives later than every negative:** R1 PASS is asserted, so the pipeline is right and the inputs are wrong.
   - **Correct tree:** P years == N years == FIX_YEARS is asserted.
   - Every precondition is real and does not depend on `gate_E14` or the R gates.
5. **Evidence reproducibility.**
   - `acceptance_prefix.py`, re-run read-only (run_gates only) with WT = `git archive 65b2469` and data root = live: the body is **identical** to the committed `acceptance_prefix.txt` apart from the runtime line. `acceptance_split.py` sha256 is `3376f0aa…` at 65b2469, 65768a4 and c599307.
   - `scratch/`: the current `/tmp/claude-1000/cr0019-scratch` matches `scratch_run2.sha256` (40/40).
   - `combined/`: the scratch tree matches `scratch_run2.sha256` (41/41).
     - `scratch_after_gen1.sha256` equals `../scratch/scratch_run1.sha256` except `split_manifest.json`, as RUN.txt states (commit field).
     - `e14_crosscheck.py`, `standing_check.py` and `yeargap_check.py` re-run read-only give output identical to the committed `*_run2.txt` / `yeargap_check.txt`.
   - I did not re-run the generators or the full acceptance run, to keep CPU light. I did not write to the other agent's scratch record.
6. **PA checks.**
   - **PA-0027:** no new broad handler in production code, tests or evidence. `yeargap_check.py:34` catches `SystemExit` narrowly, counts it as a refusal, and asserts on the count.
   - **PA-0031:** the `e` in `except SystemExit as e` is read only inside the clause. The sweep `sweep_except_name.py` reports 2 hits, both in `gate_E13` (`acceptance_split.py:1851,1857`). They were already present at 140a73e (`:1820,1826`), so they are not from CR-0019 (see F5).
   - **PA-0030:** see F3.
   - **PA-0025:** the only new year literal is `regions.py` `YEAR_MIN = 2020`, pinned in `test_shared_constants`. `get_negatives --years` uses the constant (AST-tested).

## Findings

**F1: MEDIUM. Half of E14(b) is unmeasured (PA-0021(a)).**
- Location: `tests/test_acceptance_split.py:1836` (`test_e14b_upper_end_divergence`) and the gate at `acceptance_split.py:1923`.
- The gate itself is correct (set equality). But every E14(b) test and attack has a year that is only in P; none has a year that is only in N. Mutant A10 (`not years["P"] <= years["N"]`) passes all 177 + 11 tests.
- Failure scenario:
  1. A later edit "relaxes" E14(b) to "every positive year has negatives", and the suite stays green.
  2. Negatives are then re-acquired with `--years` through 2026 while positives stop at 2024.
  3. N gains 2025–2026 rows that no positive shares, so year predicts the label again (the BUG-0034 mechanism, mirrored), and acceptance passes.
- Fix: add the mirror test. Give N a year not in P (for example, relabel P's top year to top-1 in every region, or add one N row at FIX_YEARS[-1]+1). Assert FAIL with `only in N {…}`, and assert that (a) still holds.

**F2: LOW. Operator message left out of the refusal sweep.**
- Location: `download_tcc_nlcd.py:291-295`.
- It still says "train.py will EXCLUDE these records unless --max-train-year-gap loosens it". After CR-0019, train.py *refuses* (SystemExit) and excludes nothing.
- Failure scenario: an operator adds a raster product, reads the warning, expects silent exclusion, and instead meets a refusal. Nothing wrong is produced, so this is misleading text only.
- `grouse_model_results_summary.md:61` has the same stale description.
- Fix: reword both ("train.py refuses …; see regions.YEAR_MIN"). Include them in deliverable 7's doc updates.

**F3: LOW. PA-0030(a) and (d) on `gate_E14`'s `years` dict.**
- Location: `acceptance_split.py:1881-1923`.
- The keys "P" and "N" are stored conditionally: a class file can be missing, or can lack a `year` column. The consumer is guarded (`"P" in years and "N" in years`), and both absence paths fail closed (a missing entry, or a problem "no 'year' column"), so no wrong PASS is possible.
- Still, the producer does not name its optional keys. The absent path through a class file with no `year` column is not executed by any test.
- Fix: add a one-line comment naming the optional keys. Add a unit test that drops `year` from one N file and asserts FAIL with "N: no 'year' column".

**F4: LOW. Replay error type differs from the CR §3 wording.**
- Location: `acceptance_split.py:1017-1022` (`pool_year_floor`) and `load_candidates`.
- If a candidate file has no `year` column, the pipeline raises `ValueError(f"{path}: no 'year' column")`. The replay raises a bare `KeyError: 'year'`, where CR §3 says "the replay raises ReplayError where the pipeline raises".
- The outcome is identical: the broad handler at `:984` records it and R1–R4 FAIL. Only the message is worse.
- Fix: check the column in `load_candidates` and raise `ReplayError(f"{rpath(...)} has no 'year' column")`, mirroring `check_years`.

**F5: LOW (pre-existing, not introduced by CR-0019; for the tracker).**
- Location: `acceptance_split.py:1851,1857` (`gate_E13`).
- The PA-0031 sweep, whose rule text says "0 hits required", reports 2 hits here. Both are false positives: `except MissingInput as e:` returns, and `e` is rebound by `e = domain_edge_within(...)` afterwards.
- They date from CR-0017 (present at 140a73e).
- Fix (tracker, owner lead): rename the later variable, or teach the sweep about rebinding. Record it alongside the existing PA-0031 lint follow-up (`CR-0007-0008-OPEN-ISSUES.md:215`).

**F6: LOW (evidence text).**
- Location: `docs/quality/evidence/CR-0019/combined/standing_check.py:1-4` and `RUN.txt` step 7.
- Both say "train.py defaults (img_size 64, jitter 0, no augment)". train.py's default is `--augment` on.
- The check is equivalent, because the default jitter is 0, so pad = 0 either way. Only the wording is wrong.
- Fix: say "augment on, jitter 0 (pad 0)", or pass `augment=True`.

No BLOCKING or MAJOR findings. The pipeline and the replay agree on every edge case tried. Every mutation of either half that the CR's attack table or test plan names is killed. The refusal is exact and tested. The evidence reproduces from committed scripts.

## Verdict

**APPROVE WITH FOLLOW-UPS.**
- F1 (MEDIUM) should be added before the live run, since it is a single test.
- F2–F6 (LOW) go to the review log and the tracker.
