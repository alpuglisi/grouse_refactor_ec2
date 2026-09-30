# CR-0023: Atomic raster writes in the generators, and the training reader refuses a content-validation fallback outside the year tolerance

**Status: DRAFT v1, 2026-09-30 — awaiting independent review (CLAUDE.md §1.2). Nothing has been implemented.** Review log: `CR-0023-review-log.md`, to be created by the first reviewer.

## Scope
(a) The three raster generators that write final paths directly write a temporary path and `os.replace` it on success; (b) on the training and calibration read path, `raster_path`'s most-recent-valid-year fallback is refused when it lands outside the year tolerance, and `train.filter_by_year_gap` checks the resolved file's year; (c) `standing_checks` fails on a recorded fallback beyond tolerance (BUG-0079; PA-0036).

## Why now
BUG-0079: an interrupted `generate_time_since_disturbance.py` (or TreeMap or road-distance) run leaves truncated files at final paths; `RegionData.raster_path` then substitutes the most recent valid year on the training read path with one warning, and `filter_by_year_gap` (which reads filenames) cannot refuse it. For `tsd` that is future leakage: a 2020 record reads the 2025 disturbance clock. Latent today; reachable by an ordinary interruption.

## The change
### 1. Root cause
As BUG-0079 §5: a fallback designed for the unfiltered analysis scripts sits on the training read path, the year check inspects filenames rather than the resolved file, and non-atomic writers make an invalid file at a training year reachable.

### 2. Writers (normative)
- `generate_time_since_disturbance.py:300-303`: open `outs[y]` at `path + ".tmp"`; in the existing `finally` (`:336`) close every handle; then, on normal completion, `os.replace(tmp, path)` for each year; on an exception, `os.unlink` each `.tmp` and re-raise. `update_tags` unchanged.
- `generate_treemap_features.py:310-313` (`:345` `finally`): the same.
- `generate_road_distance.py:366-367`: `with rasterio.open(out + ".tmp", ...)`, then `os.replace(out + ".tmp", out)`.
- `download_treemap.py:331` (raw intermediate): the same pattern, so a truncated source cannot pass `_source_is_valid` by luck.
No output format, path or tag changes.

### 3. Reader (normative)
- `grouse_data.RegionData.raster_path` gains `on_fallback="warn"` (today's behaviour) or `"raise"`: with `"raise"`, when the resolved year differs from the nearest-year choice and `abs(resolved - year) > tol`, raise `MissingDataError` naming the feature, the requested year, the invalid file and the candidate it would have used.
- `GrousePatchDataset.__init__` gains `max_year_gap=None`; when set, it resolves every (feature, year) with `raster_path(feat, yr, max_year_gap=max_year_gap, on_fallback="raise")`. `train.build_datasets` passes `train_year_gap` (default 2; `-1` disables, as for the filter). `calibrate.py` and `bench_pipeline.py` inherit it through `build_datasets`; `pretrain.py` and `smoke_test_training.py` keep the default (`None`, today's behaviour) and are listed in § Out of scope.
- `train.filter_by_year_gap`: the verdict per year uses the year parsed from `rd.raster_path(f, y)`'s filename (the `PATH_TEMPLATES["raster"]` pattern) instead of `raster_years`, so a substitution is judged by the file actually read.

### 4. Acceptance (amends CR-0013)
`standing_checks`: if the manifest's E11(b) fallback records contain any (feature, year → resolved year) with `abs(gap) > YEAR_MATCH_TOLERANCE`, fail with that list. A test on the harness: a manifest with a 5-year fallback fails; a 1-year fallback passes.

## Impact
- No data changes. A run on a tree with a truncated vintage now stops with a named file instead of training on a substitute.
- `GrousePatchDataset` gains a keyword argument with a backward-compatible default; `raster_path` gains one likewise; no caller changes behaviour unless it opts in (`build_datasets` does).
- Analysis scripts (`analyze_grouse.py`, diagnostics) keep the warning behaviour.
- `predict.py` is unchanged: `latest_raster_path` already skips an invalid file and prints the path it uses; the vintage it resolves is a separate mechanism (PA-0020 Swept?).

## One change per CR (CR-0011 A5)
Writers and reader are two halves of one mechanism (an invalid file at a training year, and a reader that substitutes it); either alone leaves the leakage reachable. The standing check is the acceptance side of the reader change. No data regeneration.

## Risk: LOW
| risk | mitigation |
|---|---|
| A placeholder vintage kept on disk deliberately (CHANGELOG 2026-09-20) now refuses training if a record's nearest year is that placeholder | That is the intended behaviour: the placeholder resolves to a substitute more than `tol` years away only when no valid file is within tolerance, and training should refuse then. The message names the remedy (`download_rev.py --refetch-empty` or `--max-year-gap -1`) |
| `.tmp` files left behind after a crash before the `finally` runs | They are never matched by `raster_years` (`.tif` suffix regex); a note in the generators' docstrings; `document_tree.sh` lists them |
| `os.replace` across filesystems | Same directory as the target; not an issue |

## Test plan
**Validatable here:** none beyond `py_compile` and review (every test needs rasterio).
**Not validatable here (data host):** unit tests with a synthetic 3-year raster set: truncate one file → `GrousePatchDataset(..., max_year_gap=2)` raises naming it; with `max_year_gap=None` it warns as today; `filter_by_year_gap` refuses the same case; the writer tests kill a generator mid-stripe (SIGTERM in a subprocess) and assert no final-path file exists; `standing_checks` harness test (§4).

## Deliverables (in execution order)
- [ ] 1. Pre-approval (A3): the standing-check harness test and the reader unit tests on an unmerged branch.
- [ ] 2. Writer changes (§2) and reader changes (§3); `tests/test_cr0023.py`.
- [ ] 3. Run the tests on the data host; record output under `docs/quality/evidence/CR-0023/`.
- [ ] 4. Confirm `standing_checks` still passes on the live record (no fallback recorded today, expected).
- [ ] 5. Bookkeeping: BUG-0079 → FIXED naming §2/§3; `BUG_LOG.md`; PA-0036 Swept? cell; ARCHITECTURE.md "Empty placeholder vintages" note; CHANGELOG.
- [ ] 6. Close-out.

## Out of scope
- `pretrain.py` and `smoke_test_training.py` opting into the refusal (SSL tiles carry no label; the smoke test is CR-0026's subject).
- `predict.py`'s vintage choice.
- Making `analyze_grouse.py` refuse (analysis; warning is adequate).
