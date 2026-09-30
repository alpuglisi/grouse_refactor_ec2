# CR-0012 implementer findings

The implementer worked from CR-0012 v2.2.1 (text approved at `cec1542`) and
CR-0013's config `docs/quality/acceptance_split.json` at `3230262`, plus
two coordinator notes. The first note said the manifest records measured
constants and environment, omits `op_rule` and uses repo-relative keys.
The second said `inputs` lists every raster that validation opened, and
`hash_spec` is copied from the config word for word.

Under CR-0013 design rule 4, the implementer did not read
`acceptance_split.py`, `tests/test_acceptance_split.py` or
`CR-0013-implementer-findings.md`. The only replay interface used is
`acceptance_split.standing_checks(img_size, jitter, augment)`.

Where the text is silent or two texts conflict, the list below records
the implementer's choice. None of these changes the design.

## Conflicts and risks the coordinator should resolve

1. **County-polygon file listed as a manifest input. This may conflict
   with CR-0013 E11(a).**
   - CR-0012 §2 says the manifest records "the sha256 of every input read
     (including each raster)". Pool step 4 reads
     `data/roads/tl_2023_us_county.zip` through `verify_partition`.
   - CR-0013 E11(a) says a listed input outside S ∪ I passes only if it
     is a digested artifact. As CR-0013 § Artifacts states them, S ∪ I
     does not name the county file. The config does pin its sha256 under
     `paths.county_polygons`.
   - Choice: the file is listed, following CR-0012's text.
   - If the replay's I does not include it, E11(a) fails on the real run.
     The fix is one line (drop the `digest(...)` call in
     `generate_negatives.build`), or a config/CR-0013 note that puts it
     in I.
   - The `negatives` section also lists `block_assignments.csv` and
     `train_/val_positives_R.csv` as inputs, because the draw reads them.
     All three are digested artifacts, so E11(a) allows them.
   - The manifest itself is read, but it is not listed, because it is M
     and is rewritten by the same run.

2. **Positive `x_5070`/`y_5070` are passed through, not recomputed.**
   - Positives step 6 selects the columns by name from the
     `evaluated_sightings_R` rows. So the positive files carry
     `analyze_grouse.py`'s `x_5070`/`y_5070`.
   - Every block id, thin distance and buffer distance in the pipeline is
     recomputed from lon/lat, as the config's `distance`/`block_id` rules
     require.
   - The config says `standing_checks` computes block ids from the files'
     `x_5070`/`y_5070`. If `analyze_grouse.py`'s values differ from a
     fresh pyproj transform by enough to cross a 3 km block edge, the
     standing check and the pipeline could disagree on a positive's
     block.
   - The negatives' and pool's `x_5070`/`y_5070` are recomputed, so this
     concerns positives only.
   - This was not checked on real data (there is no `data/` in the
     worktree). Check it at deliverable 6: recompute the positive
     `x_5070`/`y_5070` from lon/lat and compare.

3. **`verify_partition` reads the county file relative to the working
   directory.** It uses `PATH_TEMPLATES["tiger_county"]` and ignores
   `DataConfig.base_dir`. Both scripts run with root `"."`, so this is
   consistent when they run from the data root. That is also how the
   CR-0012 test plan's order test runs them (from a scratch working
   directory). `run(root)` with root ≠ cwd would digest one file and
   read another. The unit tests patch `verify_partition` for this
   reason.

4. **`hash_spec` depends on the config file at run time.** Following the
   coordinator's note, both scripts copy `hash_spec` from
   `docs/quality/acceptance_split.json` when they run. So the scripts
   need that file, but they read it only as JSON and never import code
   from `docs/`, so the P7 docs-import check stays clean. Constants and
   environment are measured at run time; `op_rule` is omitted.

5. **`check_partition.py` (CR-0007's closed verifier) was edited.**
   - `P6_NAMES` gains `BLOCK_ORIGIN_5070`, `VAL_FRACTION`, `SPLIT_SEED`
     and `WINDOW_PX`.
   - `tests/test_shared_constants.py` pins them, plus the four new
     `PATH_TEMPLATES` entries. PA-0025 says the pins and names grow with
     each new constant.
   - `P7_GUARDED` was not extended. The two new guards (`clean.py`,
     `legacy/gen_negs.py`) are tested in `tests/test_cr0012.py` with the
     same `guard_first` predicate, plus a run that must exit non-zero
     naming BUG-0031. Adding them to `P7_GUARDED` is a one-line
     follow-up if CR-0007's owner wants P7 to cover them.

## Choices where the text is silent

6. **Identical-coordinate ties in the thin.** The spec orders rows by key,
   then lon, then lat. Rows with identical lon/lat are fully tied: they
   have the same key, and every later one is dropped (d² = 0).
   - The sort is stable over the pooled frame, which is concatenated in
     `REGIONS` order and then file row order. So the kept row among exact
     duplicates is the first by region order, then file order.
   - That choice is order-free across regions, but not within one file.
     `analyze_grouse.py` collapses exact duplicates within a region, so
     within-file ties should not occur.
   - The pool has no such ties, because its 5 dp keys are already unique
     at step 3.
   - If the permuted-input order test ever differs, look here first.

7. **Dedup premise enforced.** Pool step 3 raises if `gbif_id` is null or
   repeated over the pooled rows after step 2. CR-0012 states that both
   hold today. They are what makes "smallest `gbif_id`" order-free.

8. **5 dp key rounding.** The key is pandas `Series.round(5)` (numpy
   rounding), as the config's `dedup.key` says. It is not Python's
   `round()`.
   - The two differ on some values. For example, `43.924905` rounds to
     `43.92491` in numpy and `43.9249` in Python.
   - The unit-test fixture first used Python `round` and caught the
     difference. Every other rounding (the `VAL_FRACTION`, `NEG_RATIO`
     and `NONVEG_MAX_FRAC` counts) is Python `round()` on a Python float,
     as specified.

9. **Per-step counts.**
   - Positives: `"1"` loaded, `"2"` habitat, `"3"` window in bounds,
     `"4"` after the pooled thin, `"5"` rows with a block assigned (equal
     to `"4"`), `"6"` rows written.
   - Pool: `"1"`–`"11"` as the numbered steps. Steps 9–11 equal step 8
     unless a step raises.
   - Every count is the number of rows whose `region` is R.

10. **Constants recorded in the `positives` section.**
    - `manifest_schema` requires one key per config constant in each
      section. So `prepare_training_data.py` also records the
      negatives-only constants, reading them from `generate_negatives`
      through a lazy import.
    - `KEY_DECIMALS` (5) is defined in `generate_negatives.py`, next to
      the other negatives constants. CR-0012 §1 does not list it for
      `regions.py`, and E11(e) does not parse it.

11. **Raster inputs.**
    - `RegionData` gains `rasters_touched`: every path that `raster_path`
      resolved, plus every path that `_is_valid_raster` opened, including
      rejected fallback candidates such as empty `*_2025_*` placeholders.
      Each section lists all of them with their sha256.
    - The test fixture includes an empty `ME_2025_cc.tif`. The test
      asserts that it is listed.

12. **`dirty` flag.** It is computed from `git status --porcelain` in the
    code's repository, not the data root. It is true iff any listed path
    other than an untracked (`??`) one ends in `.py`.

13. **Deleting `acceptance_record.json`.**
    - Only `prepare_training_data.py` deletes it, as CR-0012 assigns. It
      does so before writing any output, then writes the outputs, then
      writes the manifest last (with a `positives` section only).
    - `generate_negatives.py` writes its outputs, then the manifest with
      both sections. It does not delete the record. If a stale record
      remains after a negatives-only rerun, its digests no longer match,
      so `standing_checks` refuses it.

14. **Standing check placement.** `build_datasets` imports
    `acceptance_split` inside the function and calls
    `standing_checks(img_size, jitter, augment)` as its first action,
    before `split_features` and the region loop. Importing `train`
    therefore does not load the replay module.

15. **`split_for_unassigned` keeps its 3-argument signature.** Its `seed`
    parameter now defaults to `SPLIT_SEED`, and the pool always passes
    `SPLIT_SEED`. CR-0013 lists it, and `build_weight`, as normative
    shared functions, so their names and behaviour are unchanged.

16. **Readers and docs (deliverable 4).**
    - `organize_project.py`'s glob now matches `block_assignments*.csv`.
    - These readers were checked and left unchanged:
      - `get_negatives.py:128`: the per-region thinned files still exist.
      - `diagnose_*`, `smoke_test_training.py` and `tune.py`: the added
        `region` column is harmless, and no reference to per-region
        `block_assignments` was found.
    - `ARCHITECTURE.md`, the `grouse_data.py` docstring and both module
      docstrings are updated.
    - `PROJECT_TREE.md` is a generated listing of real file sizes. Regenerate
      it after deliverable 6 (`document_tree.sh`); it was not hand-edited.

17. **Not done here (out of this task's scope):**
    - deliverable 0 (CR-0009 baselines);
    - deliverable 6 (the real-data run, acceptance and the test plan's
      real-data items);
    - deliverable 7 (deleting `block_assignments_{ME,NH,VT}.csv`);
    - deliverable 8 (bookkeeping: the new BUG for
      `generate_negatives.py:153` with its PA-0011 recurrence review,
      BUG-0027/0029 status, and PA-0018's Swept? cell).
