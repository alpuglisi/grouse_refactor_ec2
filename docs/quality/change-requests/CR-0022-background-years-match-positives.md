# CR-0022: Background assumed-negatives take the positives' years (BUG-0074)

**Status: DRAFT, 2026-10-05** — awaiting independent review.
Verdicts and dispositions: `CR-0022-review-log.md` (created at the first
review). This document states only current intent.

## Scope
`train.py --an-background R > 0` draws its random background
assumed-negatives with the same per-year counts as the region's training
positives (scaled by R), each year's points validated on and read from
that year's rasters, instead of every point taking one vintage.

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
background row from that year's rasters (`dataset.py:122-126`), while each
positive is read at its own year.

### 2. Change

**A. `sample_background_points` gains a required keyword `year`**
(`train.py:121`), in the style of CR-0015's required `region` /
`train_blocks_only` (no behaviour by omission):
- `year=<int>`: validity is judged on `rd.raster_path(features[0], year)`
  — the same resolver `GrousePatchDataset` uses for a row of that year
  (`dataset.py:127`), so a point is validated on the raster it will be
  read from — and every returned row carries `year`.
- `year="latest"`: today's behaviour, unchanged (`latest_raster_path`,
  `max(raster_years)`). Used only by `pretrain.py:194`, whose SSL tiles
  carry no label (BUG-0074 §2: not a class asymmetry); it must now say so
  explicitly.
- Anything else (missing, `None`, a non-integer, a string other than
  `"latest"`) raises `ValueError` before any draw.
- Everything else is unchanged: in-state and training-block constraints,
  nodata rule, determinism per seed, the `acceptance` attrs (gaining
  `"year"`), the `SystemExit` on undersupply.

**B. New helper `background_for_positives(rd, features, pos_years, ratio,
seed, *, region, assignments)`** in `train.py`, used by `build_datasets`
in place of the single call at `train.py:371-374`:
- Year counts: for each distinct year `y` of the region's **training
  positives** (`pos_df["year"]`, after `filter_by_year_gap`, which refuses
  rather than drops, CR-0019), `n_y = round(c_y × ratio)`, Python `round`
  per year. The total is `Σ n_y` (it can differ from
  `round(n_pos × ratio)` for a non-integer ratio; the per-year counts are
  the contract, as in CR-0021 §2 B).
- One `sample_background_points(..., year=y, train_blocks_only=True,
  assignments=...)` call per year with `n_y > 0`, in ascending year order,
  seeded `seed=(seed, region_i, y)` (numpy `default_rng` accepts a
  sequence; independent stream per (run seed, region, year)). Frames are
  concatenated in year order; `attrs["acceptance"]` becomes the list of
  per-year acceptance dicts.
- A positive with a null or non-integral year raises (PA-0034: refuse,
  never coerce); E14/E15 already guarantee integers 2020–2024 in the split
  files, so this is a guard, not a filter.
- **Run-time check (PA-0029, PA-0033):** before returning, the helper
  compares the background frame's year histogram with `{y: n_y}` and
  raises `RuntimeError` on any difference. `build_datasets` prints the
  per-year counts next to the existing "+N random background" line.

**C. Docstrings and help text.** `--an-background` help (`train.py:819`)
states that background years follow the training positives' year
histogram (CR-0022). `sample_background_points`' docstring documents
`year`.

**Before / after** (R = 1, region R with training positives
{2020: a, …, 2024: e}):

| | before | after |
|---|---|---|
| background rows | a+…+e, all year 2024 (or 2025) | a at 2020, …, e at 2024 |
| validity raster | latest `features[0]` | `features[0]` resolved for each row's year |
| year-only AUC, positives vs background | far from 0.5 (one class one vintage) | 0.5 exactly (equal histograms) |
| `pretrain.py` | latest vintage | unchanged (explicit `year="latest"`) |

## Impact
- **Training with `--an-background 0` (the default and every run since
  CR-0009):** no change. `build_datasets` does not call the helper.
- **Training with `--an-background R > 0`:** different background rows
  (years, and therefore locations, since each year's draw is its own
  stream); validation untouched, so metrics stay comparable with
  `--an-background 0` runs of the same split.
- **`pretrain.py`:** identical output (explicit `"latest"`); a test pins
  it.
- **Callers of `sample_background_points`:** `train.build_datasets`
  (via the helper), `pretrain.py:194`, `tests/test_cr0015_sampler.py`
  (≈10 calls) and `tests/cr0015_background_check.py:173-175` (`draw()`,
  which `tests/test_cr0015_real.py:60` uses). Every call gains
  `year="latest"`, today's behaviour; their assertions are unchanged.
  `draw()` passes the same arguments to CR-0015's wrong-sampler
  reimplementations (`tests/cr0015_wrong_samplers.py`, signatures at
  `:48`, `:192-226`), so each gains a `year="latest"` keyword that it
  ignores (they model the latest-vintage sampler); no behaviour change.
- **Data, split files, acceptance (`acceptance_split.py`):** untouched.
  Nothing under `data/` is written.
- **`predict.py`, `calibrate.py`:** untouched.
- **Cache (`dataset._cache_key`):** keyed on each row's year and the
  resolved raster paths, so the new rows get their own cache entries.

## One change per CR (CR-0011 A5)
One production change (the background producer and its single call site)
plus its tests and bookkeeping. No data repair, no acceptance-gate change.

## Risk: LOW
| risk | mitigation |
|---|---|
| A caller silently keeps the one-vintage behaviour | `year` is a required keyword; omission raises; `"latest"` must be written out, and only `pretrain.py` uses it |
| Per-year validity raster differs from the one the row is read from | Both use `rd.raster_path(features[0], y)` with the same defaults; test U2 below pins it |
| Undersupply in a year with few training-block pixels | Unchanged `SystemExit` per call names region and year; supply is the whole region raster (millions of pixels) vs ≤ ~1,000 points per year |
| Different background locations change `--an-background` results vs pre-CR runs | Accepted: no pre-CR `--an-background` result is a baseline (tracker rule since CR-0019); historical sweep runs predate CR-0012 |
| `default_rng((seed, region_i, y))` changes streams vs today | Accepted: determinism per seed is kept and tested; byte-compatibility with the buggy draw is not a goal |

## Test plan
**In this repository (synthetic; no data):** new `tests/test_cr0022.py`,
written with this CR (CR-0011 A3) and reviewed with it:
- **U1** histogram: positives' years {2020: 3, 2022: 5, 2024: 2},
  ratio 1.0 → background year counts equal exactly; ratio 1.5 → per-year
  `round(c_y × 1.5)` = {2020: 4 (round(4.5)=4), 2022: 8 (7.5→8), 2024: 3}
  and total = Σ.
- **U2** validity raster per year: a fake region whose 2020 raster is
  all-nodata in one half and 2024's in the other → every 2020 point lies
  in the 2020-valid half and every 2024 point in the 2024-valid half.
- **U3** required keyword: missing `year`, `year=None`, `year=2020.5`,
  `year="newest"` → `ValueError`/`TypeError` before any raster is opened.
- **U4** `year="latest"` output identical (frame equality, same seed) to
  the pre-CR function on CR-0015's U-fixtures — pins `pretrain.py`
  behaviour.
- **U5** determinism: same seed → identical frame; different seed or
  region index → different.
- **U6** non-integral or null positive year → raises (PA-0034).
- **U7** the run-time check fires: a monkeypatched sampler that returns
  the wrong year for one call makes the helper raise `RuntimeError`
  (PA-0021(a): the check fails on a wrong producer).
- **Wrong-implementation runs (PA-0021(a)), by the reviewer, not the
  author:** (i) helper ignores years (one call, latest) → U1 fails;
  (ii) per-year `year` set on rows but validity still on the latest
  raster → U2 fails; (iii) default `year="latest"` restored → U3 fails.
- Existing suites still pass: `test_cr0015_sampler` (calls updated),
  `test_cr0015_real` (skips without data), `test_pa0027_lint`,
  `test_nodata_zero_lint`, `test_shared_constants`, `test_cr0021`.

**On the EC2 host (real data, read-only):** one smoke run,
`train.py --epochs 1 --an-background 1.0 --save-path /tmp/…` (no
checkpoint over a real one): the printed per-year background counts equal
each region's training positives' year counts; training starts. Then the
user's experiment run is theirs to choose (not a deliverable).

**Not validated here:** model quality with background points (that is
the experiment this CR unblocks, not its acceptance).

## Deliverables
- [ ] 1. This CR and `tests/test_cr0022.py` (pre-approval, CR-0011 A3);
      independent review (two reviewers), dispositions in the review log;
      approval.
- [ ] 2. Code: A, B, C above; callers updated; all suites pass.
- [ ] 3. Reviewer's wrong-implementation runs (Test plan) recorded.
- [ ] 4. EC2 smoke run output committed as evidence.
- [ ] 5. Bookkeeping: BUG-0074 → FIXED with corrective action and
      recurrence re-check; `BUG_LOG.md`; PA-0020 / PA-0033 Swept? cells
      note the run-time producer now matched; tracker: the
      "no `--an-background > 0`" rule lifted; `CHANGELOG.md`.
- [ ] 6. Close-out.

## Out of scope
- Validity on every feature rather than `features[0]` (a background row
  can still hit nodata in another feature, as today; separate item if it
  matters).
- Buffering background points away from presences (deliberately not done;
  CR-0015 §2, L_AN-full's design).
- Matching background points' habitat or wetland mix (the CR-0021 §5
  wetland residual concerns the curated negatives).
- `predict.py`'s latest-vintage rule.
- Choosing R or whether to use `--an-background` at all (an experiment,
  CR-0020's territory).
