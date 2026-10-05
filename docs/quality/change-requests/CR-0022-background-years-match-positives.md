# CR-0022: Background assumed-negatives take the positives' years (BUG-0074)

**Status: APPROVED, 2026-10-05** (v2; reviewers A and B, round 2).
Verdicts and dispositions: `CR-0022-review-log.md`. This document states
only current intent.

## Scope
`train.py --an-background R > 0` draws its random background
assumed-negatives with the same per-year counts as the region's training
positives (scaled by R), each year's points validated on the raster that
year's rows are read from, instead of every point taking one vintage.

## Fixes
- **BUG-0074** (OPEN, latent): `train.sample_background_points` gives
  every background point the latest year of `features[0]` (2024 by
  default, 2025 for some feature orders) while the positives span
  2020–2024. Root cause (BUG-0074 §5): a training-time producer of one
  class assigns the time attribute by its own rule, and no check compares
  the classes on that axis for rows produced at run time.

## Why now
CR-0021 removed the year→label signal from the split files (year-only
AUC 0.5000 in every cell). `--an-background` is the next training
experiment the user wants, and as written it would reintroduce the same
signal in reverse: at R = 1 about 3,800 label-0 rows, all at one vintage —
the vintage `predict.py` maps with. The tracker rule "no run with
`--an-background > 0` until BUG-0074 is fixed" blocks the experiment
until then.

## The change

### 1. Root cause (BUG-0074 §4–5, verified against `main` `652889c`)
`train.py:165-167` and `:220-221`:
```python
    feat = features[0]            # validity is judged on `features[0]` as passed
    path = rd.latest_raster_path(feat)
    year = max(rd.raster_years(feat))
    ...
    out = pd.DataFrame({"longitude": lons, "latitude": lats,
                        "year": int(year), "label": 0.0, "weight": 1.0})
```
One scalar year for the whole frame; `GrousePatchDataset` then reads every
background row from that year's rasters (`dataset.py:122-127`,
`rd.raster_path(feat, yr)` per row year), while each positive is read at
its own year.

### 2. Change

**A. `sample_background_points(rd, features, n, seed=0, *, region,
train_blocks_only, year, assignments=None, in_state=None)`**
(`train.py:121`). `year` is keyword-only with **no default**, in the
style of CR-0015's required `region` / `train_blocks_only`:
- Missing `year` → `TypeError` (Python's own, at the call).
- `year` an integer (`numbers.Integral`, `bool` excluded; `np.int64`
  accepted and cast with `int()`): validity is judged on
  `rd.raster_path(features[0], year)` — the resolver `GrousePatchDataset`
  uses for a row of that year (`dataset.py:127`), including its
  nearest-year and empty-placeholder fallbacks — and every row carries
  `year`.
- `year == "latest"`: today's behaviour, byte-identical
  (`latest_raster_path`, `max(raster_years)`). Used only by
  `pretrain.py:194`, whose SSL tiles carry no label (BUG-0074 §2).
- Any other value (`None`, a float including `2020.0`, `True`, any other
  string) → `ValueError`, before any raster is opened.
- `attrs["acceptance"]` gains `"year"`; the undersupply `SystemExit`
  message names the year next to the region. Everything else is
  unchanged (in-state and training-block filters, nodata rule,
  determinism per seed).

**B. New helper `background_for_positives(rd, features, pos_years, ratio,
*, seed, region_i, region, assignments, in_state=None)`** in `train.py`:
- `pos_years`: the region's training positives' years (array-like). Each must be
  non-null and integral (a float such as `2020.0` from a column that held
  a null is accepted and cast; `2020.5` or a null raises `ValueError`,
  PA-0034).
- Per distinct year `y`: `n_y = round(c_y × ratio)` (Python `round`).
  Years with `n_y = 0` are skipped. The total is `Σ n_y`.
- One `sample_background_points(rd, features, n_y, seed=(seed, region_i,
  y), region=region, train_blocks_only=True, year=y,
  assignments=assignments, in_state=in_state)` call per year, in
  ascending year order (numpy `default_rng` accepts the tuple; an
  independent stream per run seed, region and year).
- Frames are concatenated in year order; **after** the concat,
  `attrs["acceptance"]` is set to the list of per-year acceptance dicts.
- **Sampler check:** the helper compares the concatenated frame's year
  histogram with `{y: n_y}` and raises `RuntimeError` on any difference
  (catches a sampler that does not honour `year`).

**C. `build_datasets` (`train.py:365-380`).** When `background_per_pos >
0`, it calls the helper with `pos_df["year"]`, the `seed` and
`region_i` of the loop, and `data.block_assignments`. It then **checks
independently of the helper**: it recomputes `{y: round(c_y × R)}` (zeros
dropped) from `pos_df["year"]`, the frame wrapped as the training
positives, compares it with the background frame's year histogram, and
raises `RuntimeError` on any difference (PA-0021(e), PA-0029). The
existing "+N random background" line prints `Σ n_y` and the per-year
counts.

**D. Text.** `--an-background` help (`train.py:819`) and the sampler's
docstring say that background years follow the training positives'
histogram (CR-0022) and document `year`.

**Before / after** (region with training positives {2020: a, …, 2024: e}):

| | before | after |
|---|---|---|
| background rows at R = 1 | a+…+e, all year 2024 (or 2025) | a at 2020, …, e at 2024 |
| validity raster | latest `features[0]` | `features[0]` resolved for each row's year |
| year-only AUC, positives vs background | far from 0.5 | 0.5 exactly for integer R; per-year counts within ±0.5 row of `c_y × R` otherwise |
| `pretrain.py` | latest vintage | byte-identical (explicit `year="latest"`) |

## Impact
- **Training with `--an-background 0`** (the default and every run since
  CR-0009): no change; the helper is not called.
- **Training with `--an-background R > 0`:** different background rows
  (years, and therefore locations); validation untouched, so metrics stay
  comparable with `--an-background 0` runs on the same split.
- **Other `train.build_datasets` callers** (`calibrate.py`,
  `bench_pipeline.py`, `smoke_test_training.py`) use the default 0:
  unaffected.
- **Callers of `sample_background_points`:** `train.build_datasets`
  (via the helper), `pretrain.py:194` (`year="latest"`),
  `tests/test_cr0015_sampler.py` (11 calls: `:114`, `:196`, `:272`,
  `:287-289`, `:300`, `:315`, `:320`, `:324`, `:329`; each gains
  `year="latest"`, assertions unchanged), and
  `tests/cr0015_background_check.py:173-175` `draw()` (used by
  `tests/test_cr0015_real.py:60,122`; gains `year="latest"`). `draw()`
  passes the same arguments to CR-0015's wrong-sampler reimplementations
  (`tests/cr0015_wrong_samplers.py:48`, `:192-226`, also called directly
  at `tests/test_cr0015_sampler.py:226,238,257`), so each gains a
  `year="latest"` keyword **with that default**, which it ignores (they
  model the latest-vintage sampler).
- **`attrs["acceptance"]`:** a dict per sampler call (now with `"year"`);
  a list of those from the helper. Its one consumer,
  `tests/test_cr0015_real.py:81`, goes through `draw()` and still gets a
  dict.
- **Data, split files, acceptance (`acceptance_split.py`, standing
  checks):** untouched. Nothing under `data/` is written by the change or
  its tests.
- **`predict.py`, `calibrate.py`:** untouched.
- **Patch cache (`dataset._cache_key`):** keyed on each row's year and
  the resolved raster paths, so the new rows get their own entries.

## One change per CR (CR-0011 A5)
One production change (the background producer, its helper and its one
training call site) plus tests and bookkeeping. No data repair, no
acceptance-gate change.

## Risk: LOW
| risk | mitigation |
|---|---|
| A caller silently keeps the one-vintage behaviour | `year` has no default (`TypeError` if omitted); `"latest"` is written out, and only `pretrain.py` uses it |
| The validity raster differs from the read raster | Both use `rd.raster_path(features[0], y)` with the same defaults; U2 compares with `GrousePatchDataset._path_for` on a fixture with a missing year and an empty placeholder vintage |
| The helper is wired to the wrong frame | `build_datasets` recomputes the expected counts from the training positives itself; a test wires the negatives in and must fail |
| Undersupply in one year | Unchanged `SystemExit`, now naming region and year; supply is the whole region raster vs ≤ ~1,000 points per year |
| Different background rows change `--an-background` results vs pre-CR runs | Accepted: no pre-CR `--an-background` result is a baseline (tracker rule since CR-0019) |
| Per-year draws change in-state or training-block filtering | Those filters read only coordinates (`train.py:196-202`), never the raster year; only the validity raster depends on the year (U2). The real-data V1 check (`test_cr0015_real`, `draw()` with `"latest"`) still exercises the filters on real polygons and blocks |

## Test plan
**In this repository (synthetic; no data): `tests/test_cr0022.py`**,
committed before approval (CR-0011 A3) and reviewed with this CR. Its
fixture writes four `evt` rasters through the real `RegionData`
(`DataConfig(base_dir=tmp)`): 2020 valid only in the west half, 2022 only
in the east half, 2023 an empty placeholder (content validation fails,
`raster_path` falls back to 2024), 2024 only in the north half; no 2021
raster (resolves to 2020, tie → earlier). Helper tests inject
`in_state=everywhere` and a synthetic `assignments` frame whose validation
share is 0.
- **U1** histogram: `np.int64` positives {2020: 3, 2022: 5, 2024: 2}, R = 1
  → equal; R = 1.5 → {2020: 4, 2022: 8, 2024: 3}, total 15.
- **U2** through the helper, positives 12 per year 2020–2024: every row is
  valid on `rd.raster_path("evt", y)`, which equals
  `GrousePatchDataset(...)._path_for[("evt", y)]`; 2020 rows lie west,
  2022 rows east.
- **U3** `year`: missing → `TypeError`; `None`, `2020.5`, `2020.0`,
  `True`, `"newest"`, `"2020"` → `ValueError` with `rasterio.open`
  patched to fail; `np.int64(2022)` accepted, `attrs` carries the year.
- **U4** `year="latest"` reproduces the sha256 digests of the
  sampler's frames at `9bb1636` (pinned in the test; four fixtures).
- **U5** determinism: same inputs → equal frames; another seed or region
  index → different; `attrs["acceptance"]` lists one entry per year.
- **U6** positive years: a null or `2020.5` → `ValueError`; `2020.0`
  accepted.
- **U7** a sampler that ignores `year` (always `"latest"`) makes the
  helper raise `RuntimeError`.
- **W1–W3** `build_datasets` with patched acceptance, datasets and
  sampler; training positives {2020: 3, 2022: 2}, other frames other
  years: the sampler is called with exactly (2020, 3) and (2022, 2), in
  training blocks, seeds `(5, 0, y)`; R = 0 makes no call; a helper wired
  to the training negatives' years makes `build_datasets` raise.

All 15 tests fail at `9bb1636` (no `year` keyword, no helper) except W2
(R = 0), and pass against a trial implementation of §2 (not committed).

**Wrong-implementation runs (PA-0021(a)), by a reviewer, not the
author:** (i) helper ignores years (one `"latest"` call) → U1 and U2
fail (via the helper's year check); (ii) per-year `year` on the rows but
validity on the latest raster → U2 fails; (iii) `year="latest"` as the
default → U3 fails; (iv) one `"latest"` draw for `Σ n_y` points with the
`year` column overwritten to match the histogram → U2 fails; (v)
`build_datasets` passing another frame's years → W1 fails (via the
independent `build_datasets` check that W3 exercises). Recorded as
evidence.

**Existing suites** still pass: `test_cr0015_sampler` (calls updated),
`test_cr0015_real` (skips without data), `test_pa0027_lint`,
`test_nodata_zero_lint`, `test_shared_constants`, `test_cr0021`.

**On the EC2 host (real data, writes nothing under `data/`):**
```bash
python train.py --epochs 1 --an-background 1.0 --batch-size 128 \
  --cache-dir '' --save-path /tmp/cr0022_smoke.pth 2>&1 | tee cr0022_smoke.log
```
Pass: each region's printed per-year background counts equal its training
positives' year counts (`acceptance_split` O9's `year_hist.pos`, train
split), no `RuntimeError`, the epoch runs. The log is committed as
evidence.

**Not validated here:** model quality with background points (the
experiment this CR unblocks, not its acceptance).

## Deliverables
- [x] 1. This CR and `tests/test_cr0022.py` (pre-approval, CR-0011 A3);
      two independent reviews, dispositions in the review log; approval.
      — Done: round 1 `9bb1636`, v2 and tests `069f50c`, round 2 APPROVE
      (A) and APPROVE WITH FOLLOW-UPS (B); review log.
- [x] 2. Code: §2 A–D; callers and CR-0015 test fixtures updated; all
      suites pass.
      — Done: `train.py` (sampler `year`, `background_for_positives`,
      independent check in `build_datasets`, help/docstrings),
      `pretrain.py` (`year="latest"`), `tests/test_cr0015_sampler.py`,
      `tests/cr0015_background_check.py`, `tests/cr0015_wrong_samplers.py`.
      All 19 test modules pass (`test_cr0022` 15/15; `test_cr0015_real`
      skips without data).
- [x] 3. Reviewer's wrong-implementation runs (i)–(v) recorded.
      — Done: `docs/quality/evidence/CR-0022/reviewA/wrong_impl_runs.txt`
      (re-runnable with `mutate.py`), at `e18944d`: control 15/15; every
      variant detected; mapping of (i) and (v) corrected (review log I1).
- [ ] 4. EC2 smoke run log committed as evidence.
- [ ] 5. Bookkeeping: BUG-0074 → FIXED (corrective action, recurrence
      re-check); `BUG_LOG.md`; Swept? cells of PA-0020, PA-0029 and
      PA-0033 note that the run-time background producer is now matched
      and checked; tracker: the "no `--an-background > 0`" rule lifted,
      MEDIUM/LOW review follow-ups entered with an owner; `CHANGELOG.md`.
- [ ] 6. Close-out.

## Out of scope
- Validity on every feature rather than `features[0]` (a background row
  can still hit nodata in another feature, as today).
- `year="latest"`'s pre-existing pairing of `latest_raster_path` (skips
  empty vintages) with `max(raster_years)` (does not); unchanged.
- Buffering background points away from presences (deliberately not done;
  CR-0015 §2, L_AN-full's design).
- Matching background points' habitat or wetland mix.
- `predict.py`'s latest-vintage rule.
- Choosing R, or whether to use `--an-background` (an experiment; CR-0020).
