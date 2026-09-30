# CR-0023: Atomic raster writes in the generators, and the training and calibration read path refuses any content-validation fallback

**Status: DRAFT v3, 2026-09-30 — awaiting round-3 bounded re-review (CLAUDE.md §1.2, CR-0011 A2). Round 2: one reviewer APPROVE WITH FOLLOW-UPS, one REVISE (two MAJOR text gaps, no BLOCKING). Nothing has been implemented.** Review log: `CR-0023-review-log.md`.

## Scope
(a) Every raster generator that writes a final path directly writes a temporary path, validates it and `os.replace`s it after the handles are closed (PA-0036(a)); (b) on the training and calibration read path, `raster_path`'s most-recent-valid-year fallback is refused unconditionally, and `train.filter_by_year_gap` judges each year by the file actually resolved (PA-0036(b)) (BUG-0079).

## Why now
BUG-0079: an interrupted `generate_time_since_disturbance.py` (or TreeMap or road-distance) run leaves truncated files at final paths; `RegionData.raster_path` then substitutes the most recent valid year on the training read path with one warning (`grouse_data.py:392-407`), and `filter_by_year_gap` (`train.py:226-265`), which reads filenames, cannot refuse it. For `tsd` that is future leakage: a 2020 record reads the 2025 disturbance clock. Latent today; reachable by an ordinary interruption.

## The change
### 1. Root cause
As BUG-0079 §5: a fallback designed for the unfiltered analysis scripts sits on the training read path, the year check inspects filenames rather than the resolved file, and non-atomic writers make an invalid file at a training year reachable.

### 2. Writers (normative)
Sites found by the recorded search (PA-0044) over tracked non-test `*.py` for `rasterio.open(..., "w"`, `shutil.copy`, `shutil.copy2`, `shutil.copyfile` and `open(..., "wb")` whose target is a raster path:
| site | today | change |
|---|---|---|
| `generate_time_since_disturbance.py:300-303` (`outs[y]` opened per year; `finally` `:336-342`) | final path | open at `path + ".tmp"`; see the ordering rule below |
| `generate_treemap_features.py:324-327` (`write_vintage`; `finally` `:359-363`) | final path | the same |
| `generate_treemap_features.py:518-522` (sibling-year fan-out, `shutil.copy2` of the representative year's file to every other year) | final path | copy to `dest + ".tmp"`, validate, `os.replace` |
| `generate_road_distance.py:366-367` (`with rasterio.open(out, "w", ...)`) | final path | `with rasterio.open(out + ".tmp", "w", ...)` inside `try`/`except: unlink; raise`; validate; `os.replace` after the `with` |
| `download_treemap.py:331` (raw intermediate; validity judged by `generate_treemap_features._source_is_valid`, `:149`) | final path | the same |
| `download_tcc_nlcd.py:467-468` (no-template branch `shutil.copyfile(merged, out_path)`; the template branch `:464-465` already copies to `.tmp` and replaces) | final path | copy to `.tmp`, validate, `os.replace` |
| `download_rev.py:416-431` (`copy_topo_baselines`, `shutil.copy(base, dest)` for every non-2020 year; the rest of the file is temp+replace, `:181-186`, `:269`) | final path | copy to `dest + ".tmp"`, validate, `os.replace` |
**Ordering rule (normative for the multi-output writers).** `ok = False`; `try:` the stripe loop; `ok = True`; `finally:` close every output handle and VRT (the existing `finally`). **After** that statement, so that GDAL has written the IFD and tile offsets at close: if not `ok`, unlink every `.tmp` and re-raise; else, for each output, `rasterio.open(tmp)` and check `shape == (height, width)` and read one window (validation), then `os.replace(tmp, path)`. A replace placed inside the `try` (before the close) would publish an incomplete file, the window PA-0036(a) exists to remove. The single-output `with` sites follow the same rule after their `with` block. Output format, paths and tags are unchanged.
A `.tmp` file left by a crash that bypasses the handler (a hard kill) is never matched by `raster_years` (`grouse_data.py:299-306`, `.tif` suffix regex), by `discover_regions` (`:580`), by the acceptance `Rasters.raster_years` (`acceptance_split.py:428`) or by any production raster glob; it is overwritten by the next run and noted in each generator's docstring.
CSV writers found by the same search are out of this CR's raster scope: `analyze_grouse.py:551/877/1099-1100` (CR-0025 makes them atomic), `sightings.py:138` and `predict.py:1105` (tracker items, owner lead).

### 3. Reader (normative)
- `grouse_data.RegionData.resolve_raster(feature, year, *, nearest=True, validate=True, max_year_gap=None, on_fallback="warn")` returns `(path, resolved_year)`; `raster_path` becomes a wrapper returning the path. With `on_fallback="raise"`, when the nearest-year file (the choice `raster_path` makes today: `min(years, key=(abs(y - year), y))`, ties to the earlier year, `:364`) fails content validation, raise `MissingDataError` naming the feature, the requested year, the invalid file and the candidate the fallback would have used, instead of returning the candidate. The refusal is unconditional (PA-0036(b): any resolution that differs from the nearest-year one is refused on the training path); `max_year_gap` plays no part in it and is not passed by the callers below. Any other `on_fallback` value raises `ValueError`.
- `GrousePatchDataset.__init__` gains `on_fallback="warn"` and passes it to every `rd.raster_path` call in its path resolution (`dataset.py:125-127`).
- `train.build_datasets` passes `on_fallback="raise"` to all six constructions: `p_tr`, `n_tr` (`train.py:353-362`), `bg_tr` (`:375`), the two validation sets (`:388-393`), and `_score_teacher_probs`'s dataset (`:286`, reached through `soft_labels_for` before `p_tr` is built) through a new `on_fallback` parameter of `_score_teacher_probs`. `calibrate.py:356` and `bench_pipeline.py:96` inherit through `build_datasets`; `pretrain.py` (whose SSL dataset never calls `raster_path`) and `smoke_test_training.py` (`:84-99`, direct constructions) keep the default (§ Out of scope).
- `train.filter_by_year_gap`: for each (feature, year) the verdict uses `resolved_year` from `rd.resolve_raster(f, y, on_fallback="raise")` instead of `raster_years`; it catches `MissingDataError` and re-raises `SystemExit` carrying `what`, `region` and the original message (its existing remedy text, `:249-255`, is replaced by `resolve_raster`'s), so the refusal fires here first, naming the record class, when the tolerance check is enabled, and in the dataset when it is disabled (`tolerance < 0` returns at `:239-241`). The `if ys` skip at `:243` is kept (a feature with no rasters is unreachable through `discover_features`, `:107-118`, and raises in the dataset otherwise). It gains no keyword. On a healthy tree the verdict is unchanged: the resolved year is the nearest year, whose distance is `min(abs(y - year))`.
- The refusal message names the remedies: fetch the real vintage (`download_rev.py --refetch-empty`, `:441`) or remove the placeholder from disk so the nearest-year rule resolves to a real neighbour, whose gap `filter_by_year_gap` then judges.
- Patch cache: `_cache_key` (`dataset.py:151-172`) hashes the resolved path and its mtime, and construction raises before any cache lookup (`:146`), so a cache built under a substitution can never be served to a refusing dataset; once the vintage is repaired the key changes.
- `--an-background` rows (`train.py:166-167`) go through `GrousePatchDataset(on_fallback="raise")`, so their patch reads are covered; only the sampling read uses latest-valid (BUG-0074, § Out of scope).

### 4. Acceptance
| id | kind | check | how it can fail (PA-0021(a)) |
|---|---|---|---|
| G1 | GATE (unit, `tests/test_cr0023.py`) | on a synthetic 3-year raster set with one file truncated so that `rasterio.open` fails (asserted: `_is_valid_raster` is `False` for it), `GrousePatchDataset(..., on_fallback="raise")` raises `MissingDataError` naming the file; with the default it warns and resolves as today | today's code resolves silently under both |
| G2 | GATE (unit) | `filter_by_year_gap` on the same set raises `SystemExit` naming the record class and carrying the resolver's message | today's code passes (filenames only) |
| G3 | GATE (unit) | `build_datasets(..., train_year_gap=-1, distill_models=[teacher])` with `standing_checks` mocked raises `MissingDataError` from the `_score_teacher_probs` construction (`train.py:286`) before any scoring; with `train_year_gap=2` the same set is refused by `filter_by_year_gap` first | today's code scores on the substitute (and would not be caught by G3 without `-1`, since `filter_by_year_gap` runs first, `:339-350`) |
| G4 | GATE (unit, writers), one row per §2 site | an exception injected after the first write (tsd: `_emit` patched, `:352`; treemap: `treemap_encode` patched; road-distance and `download_treemap`: a `rasterio.open` mock whose `write` raises; tcc/nlcd: `shutil.copyfile` patched; fan-out: `shutil.copy2` patched; topo baselines: `shutil.copy` patched) leaves no final-path file and no `.tmp`; for tsd additionally a SIGTERM to a subprocess mid-stripe leaves no final-path file (a `.tmp` may remain) | today's code leaves a final-path file at every site |
| pin (must not change) | GATE | on the healthy synthetic set, `_path_for` and `_cache_key` are identical between `on_fallback="warn"` and `"raise"` in one run, and `filter_by_year_gap`'s verdicts are identical before and after | over-refusal fails it; G1–G4 are the must-change side (a no-op implementation fails them) |
A partial but well-formed file (an interrupted run whose `finally` closed the handle cleanly, unwritten tiles reading as nodata) passes `_is_valid_raster` (`grouse_data.py:308-330`, at least 1 % non-nodata) and is not caught by § 3; only § 2's ordering rule prevents it. G4 is the check for that case.
`tests/test_cr0019.py:328-332` (`FakeRD`, `raster_years` only) gains `resolve_raster` so its three `filter_by_year_gap` tests (`:338-361`) keep running.

## Impact
- No data change. A run on a tree with a truncated or placeholder vintage at a training year now stops with a named file instead of training on a substitute.
- `GrousePatchDataset`, `resolve_raster`/`raster_path` and `_score_teacher_probs` gain a keyword with a backward-compatible default; `filter_by_year_gap` always refuses; no other caller changes behaviour unless it opts in (`build_datasets` does).
- The pipeline producers keep the fallback deliberately: `prepare_training_data.window_mask` (`:177`) and `generate_negatives.extract_envelope` (`:229`) resolve through `rd.raster_path(feat, yr)` with the default, and the acceptance `Rasters.raster_path` (`acceptance_split.py:479-493`, pinned by `tests/test_acceptance_split.py:2151-2175`) reproduces the same substitution. Under BUG-0079's pre-acceptance scenario the split files are therefore built on the substitute, training then refuses, and after the vintage is repaired R1–R4/E8 fail until the pipeline is re-run: safe, and stated here.
- Analysis scripts keep the warning behaviour; `calibrate.py:343` (`nearest=False`, `validate=False`) unaffected. `nearest=False` with `validate=True` still falls through to the fallback loop (`:361` guards only `year not in years`), for example `generate_road_distance.py:334` (`LAND_EVT_YEAR`); not on the training path, recorded for PA-0036's Swept? cell.
- `predict.py` is unchanged: `latest_raster_path` (`grouse_data.py:413-431`) already skips an invalid file, and `predict.open_aligned_sources` (`:177-180`) prints the basename it uses.
- A placeholder vintage kept on disk deliberately (CHANGELOG `:502`, "Empty placeholder vintages") now refuses training for any record whose nearest year it is; that is the intended behaviour, and the message names the remedy.
- Recorded for PA-0036's Swept? cell, not changed here: `train.sample_background_points` (`:166-167`) labels rows with `max(raster_years)` while validity is read from `latest_raster_path`; `--an-background` is forbidden by BUG-0074 and the item is tracked there.
- `tests/test_pa0027_lint.py:131` pins `_is_valid_raster`'s handler digest; § 3 does not touch it.

## One change per CR (CR-0011 A5)
Writers (§2) and reader (§3) are both pipeline code and the two clauses of PA-0036 for one BUG. They could land separately; they are kept together because BUG-0079's scenario is closed only by both (writer-only: an invalid file from any other cause is still substituted; reader-only: an interruption still leaves an invalid file, which then refuses training until repaired) and G1 and G4 share one synthetic set. The reviewer's alternative (two CRs) is recorded in the log.

## Risk: LOW
| risk | mitigation |
|---|---|
| A placeholder vintage refuses training | Intended (§ Impact); remedy in the message |
| `.tmp` files after a hard kill | Invisible to every raster glob; docstring note; overwritten by the next run |
| `os.replace` across filesystems | Same directory as the target |
| The validation read before replace slows the writers | One window per output; negligible next to the stripe loop |

## Test plan
**Validatable here:** none beyond `py_compile` (every test needs rasterio).
**Not validatable here (data host):** `tests/test_cr0023.py` (§ 4), `tests/test_cr0019.py` after the `FakeRD` change.

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): `tests/test_cr0023.py` and the `FakeRD` change on an unmerged branch.
- [ ] 2. Writer changes (§2) and reader changes (§3).
- [ ] 3. Run the tests on the data host; record output under `docs/quality/evidence/CR-0023/`.
- [ ] 4. Confirm `standing_checks` and a `build_datasets` call still pass on the live tree (no invalid vintage at a training year today, expected).
- [ ] 5. Bookkeeping: BUG-0079 → FIXED naming §2/§3; `BUG_LOG.md`; PA-0036 Swept? cell corrected (adds `generate_treemap_features.py:518-522`, `download_rev.py:416-431`, `download_tcc_nlcd.py:467-468`, the `nearest=False` fall-through and the `sample_background_points` note); tracker items for `sightings.py:138` and `predict.py:1105`; CHANGELOG (the `:502` placeholder entry updated); CHANGELOG entry for this CR.
- [ ] 6. Close-out.

## Out of scope
- `pretrain.py` and `smoke_test_training.py` opting into the refusal (SSL tiles carry no label; the smoke test is CR-0026's subject).
- `predict.py`'s vintage choice.
- Making `analyze_grouse.py`, the pipeline producers or the acceptance `Rasters` refuse (analysis and pre-acceptance; the consequence is stated in § Impact).
- Recording fallbacks in the manifest or `standing_checks` (v1 §4): no such records exist and the refusal at dataset construction is the standing gate.
- `train.sample_background_points`' year label (BUG-0074); the `nearest=False` fall-through outside the training path.
- CSV writers (`analyze_grouse.py`: CR-0025; `sightings.py`, `predict.py`: tracker).
