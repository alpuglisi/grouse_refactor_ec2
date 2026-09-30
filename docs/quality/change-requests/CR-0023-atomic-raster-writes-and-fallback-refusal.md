# CR-0023: Atomic raster writes in the generators, and the training and calibration read path refuses any content-validation fallback

**Status: DRAFT v2, 2026-09-30 — awaiting round-2 review (CLAUDE.md §1.2, CR-0011 A2). Nothing has been implemented.** Review log: `CR-0023-review-log.md`.

## Scope
(a) Every raster generator that writes a final path directly writes a temporary path and `os.replace`s it on success (PA-0036(a)); (b) on the training and calibration read path, `raster_path`'s most-recent-valid-year fallback is refused unconditionally, and `train.filter_by_year_gap` judges each year by the file actually resolved (PA-0036(b)) (BUG-0079).

## Why now
BUG-0079: an interrupted `generate_time_since_disturbance.py` (or TreeMap or road-distance) run leaves truncated files at final paths; `RegionData.raster_path` then substitutes the most recent valid year on the training read path with one warning (`grouse_data.py:392-407`), and `filter_by_year_gap` (`train.py:238-256`), which reads filenames, cannot refuse it. For `tsd` that is future leakage: a 2020 record reads the 2025 disturbance clock. Latent today; reachable by an ordinary interruption.

## The change
### 1. Root cause
As BUG-0079 §5: a fallback designed for the unfiltered analysis scripts sits on the training read path, the year check inspects filenames rather than the resolved file, and non-atomic writers make an invalid file at a training year reachable.

### 2. Writers (normative)
Each site opens its output at `path + ".tmp"` and, on normal completion, `os.replace(tmp, path)`; on an exception the `.tmp` files are unlinked and the exception re-raised. Output format, paths and tags are unchanged.
- `generate_time_since_disturbance.py:300-303` (`outs[y]` opened per year); the existing `finally` (`:336-340`) keeps closing every handle; the replace-or-unlink step follows it (`try`/`except`/`else` around the stripe loop).
- `generate_treemap_features.py:310-313`; `finally` at `:359-363`; the same.
- `generate_road_distance.py:366-367`: `with rasterio.open(out + ".tmp", "w", ...)`, then `os.replace`.
- `download_treemap.py:331` (raw intermediate; its validity is judged by `generate_treemap_features._source_is_valid`, `:149`): the same, so a truncated source cannot pass by luck.
- `download_tcc_nlcd.py:467-468`, the no-template branch `shutil.copyfile(merged, out_path)` (the template branch at `:464-465` already copies to `.tmp` and replaces): the same.
A `.tmp` file left by a crash that bypasses the handler (a hard kill) is never matched by `raster_years` (`grouse_data.py:299-306`, `.tif` suffix regex) and is noted in each generator's docstring.

### 3. Reader (normative)
- `grouse_data.RegionData.raster_path` gains `on_fallback="warn"` (today's behaviour) or `"raise"`. With `"raise"`, when the nearest-year file fails content validation, raise `MissingDataError` naming the feature, the requested year, the invalid file and the candidate the fallback would have used, instead of returning the candidate. The refusal is unconditional (PA-0036(b): any resolution that differs from the nearest-year one is refused on the training path); `max_year_gap` plays no part in it and is not passed by the callers below.
- `GrousePatchDataset.__init__` gains `on_fallback="warn"` and passes it to every `rd.raster_path` call in its path resolution (`dataset.py:122-126`).
- `train.build_datasets` passes `on_fallback="raise"` to all six constructions: `p_tr`, `n_tr` (`train.py:353-362`), `bg_tr` (`:375`), the two validation sets (`:388-393`), and `_score_teacher_probs`'s dataset (`:286`, reached through `soft_labels_for` before `p_tr` is built) through a new `on_fallback` parameter of `_score_teacher_probs`. `calibrate.py` and `bench_pipeline.py` inherit through `build_datasets`; `pretrain.py` and `smoke_test_training.py` build datasets directly and keep the default (§ Out of scope).
- `train.filter_by_year_gap`: for each (feature, year) the verdict uses the year parsed from the filename returned by `rd.raster_path(f, y, on_fallback="raise")` (the `PATH_TEMPLATES["raster"]` pattern) instead of `raster_years`; the refusal therefore fires here first, naming the record class (`what`), when the tolerance check is enabled, and in the dataset when it is disabled (`tolerance < 0` returns at `:240-242`).
- The refusal message names the remedies: fetch the real vintage (`download_rev.py --refetch-empty`) or remove the placeholder from disk so the nearest-year rule resolves to a real neighbour, whose gap `filter_by_year_gap` then judges.
- Patch cache: `_cache_key` (`dataset.py:151-172`) hashes the resolved path and its mtime, and construction raises before any cache lookup, so a cache built under a substitution can never be served to a refusing dataset; once the vintage is repaired the key changes.

### 4. Acceptance
| id | kind | check | how it can fail (PA-0021(a)) |
|---|---|---|---|
| G1 | GATE (unit, `tests/test_cr0023.py`) | on a synthetic 3-year raster set with one file truncated so that `rasterio.open` fails (asserted: `_is_valid_raster` is `False` for it), `GrousePatchDataset(..., on_fallback="raise")` raises `MissingDataError` naming the file; with the default it warns and resolves as today | today's code resolves silently under both |
| G2 | GATE (unit) | `filter_by_year_gap` on the same set raises `SystemExit` naming the record class | today's code passes (filenames only) |
| G3 | GATE (unit) | `build_datasets` with a distillation teacher on the same set raises before scoring (the `_score_teacher_probs` path) | today's code scores on the substitute |
| G4 | GATE (unit, writers) | an exception injected into the stripe loop (`_emit` patched to raise) leaves no final-path file and no `.tmp`; a SIGTERM to a subprocess mid-stripe leaves no final-path file (a `.tmp` may remain) | today's code leaves a final-path file |
| must-change | GATE | on the healthy synthetic set the resolved paths and the dataset's `_cache_key` are identical before and after (no behaviour change without a fallback) | — |
A partial but well-formed file (an interrupted run whose `finally` closed the handle cleanly, unwritten tiles reading as nodata) passes `_is_valid_raster` (`grouse_data.py:308-330`, at least 1 % non-nodata) and is not caught by § 3; only § 2 prevents it. G4 is the check for that case.

## Impact
- No data change. A run on a tree with a truncated or placeholder vintage at a training year now stops with a named file instead of training on a substitute.
- `GrousePatchDataset`, `raster_path`, `filter_by_year_gap` and `_score_teacher_probs` gain a keyword with a backward-compatible default; no caller changes behaviour unless it opts in (`build_datasets` does).
- Analysis scripts keep the warning behaviour; `calibrate.py:343` (`validate=False`) is unaffected.
- `predict.py` is unchanged: `latest_raster_path` already skips an invalid file and prints the path it uses.
- A placeholder vintage kept on disk deliberately (CHANGELOG 2026-09-20) now refuses training for any record whose nearest year it is; that is the intended behaviour, and the message names the remedy.
- Recorded for PA-0036's Swept? cell, not changed here: `train.sample_background_points` (`:166-167`) labels rows with `max(raster_years)` while validity is read from `latest_raster_path`; `--an-background` is forbidden by BUG-0074 and the item is tracked there.

## One change per CR (CR-0011 A5)
Writers (§2) and reader (§3) are both pipeline code and the two clauses of PA-0036 for one BUG. They could land separately; they are kept together because BUG-0079's scenario is closed only by both (writer-only: an invalid file from any other cause is still substituted; reader-only: an interruption still leaves an invalid file, which then refuses training until repaired) and G1 and G4 share one synthetic set. The reviewer's alternative (two CRs) is recorded in the log.

## Risk: LOW
| risk | mitigation |
|---|---|
| A placeholder vintage refuses training | Intended (§ Impact); remedy in the message |
| `.tmp` files after a hard kill | Invisible to `raster_years`; docstring note; overwritten by the next run |
| `os.replace` across filesystems | Same directory as the target |

## Test plan
**Validatable here:** none beyond `py_compile` (every test needs rasterio).
**Not validatable here (data host):** `tests/test_cr0023.py` (§ 4).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0023.py` on an unmerged branch.
- [ ] 2. Writer changes (§2) and reader changes (§3).
- [ ] 3. Run the tests on the data host; record output under `docs/quality/evidence/CR-0023/`.
- [ ] 4. Confirm `standing_checks` and a `build_datasets` call still pass on the live tree (no invalid vintage at a training year today, expected).
- [ ] 5. Bookkeeping: BUG-0079 → FIXED naming §2/§3; `BUG_LOG.md`; PA-0036 Swept? cell (adds `download_tcc_nlcd.py:467-468` and the `sample_background_points` note); ARCHITECTURE.md "Empty placeholder vintages" note; CHANGELOG.
- [ ] 6. Close-out.

## Out of scope
- `pretrain.py` and `smoke_test_training.py` opting into the refusal (SSL tiles carry no label; the smoke test is CR-0026's subject).
- `predict.py`'s vintage choice.
- Making `analyze_grouse.py` refuse (analysis; warning is adequate).
- Recording fallbacks in the manifest or `standing_checks` (v1 §4): no such records exist and the refusal at dataset construction is the standing gate.
- `train.sample_background_points`' year label (BUG-0074).
