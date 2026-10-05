# CR-0033: split window mask reads a pinned feature list

**Status: IMPLEMENTED, 2026-10-05** (approved with follow-ups, v2). Verdicts and
dispositions: `CR-0033-review-log.md`. This document states only current
intent.

## Scope
`prepare_training_data.window_mask` checks the window against a pinned
list of split rasters equal to the acceptance replay's
`feature_spec_keys`, not the live `models.FEATURE_SPEC`.

## Fixes
BUG-0093 (found in CR-0032 review, A5): the split producer and its
acceptance replay read the window rasters from two different sources,
and nothing ties them.

## Why now
CR-0032 adds four entries to `FEATURE_SPEC`. With today's code that
would, without any split change being intended:
1. make `prepare_training_data.py` / `generate_negatives.py` open
   `mch_*` rasters (`window_mask`, `prepare_training_data.py:174`;
   `generate_negatives.py:481`), raising `MissingDataError` on a host
   where they are not generated yet;
2. once generated, put `mch_*` files into the split manifest's inputs,
   which `acceptance_split.py` (replaying only the 15
   `feature_spec_keys`) rejects as "manifest lists an input outside S and
   I" (`acceptance_split.py:2399`), so the standing checks block training
   on any regenerated split.

## The change
Before (`prepare_training_data.py:161-177`):
```python
    from models import FEATURE_SPEC
    ...
    for feat in FEATURE_SPEC:
```
After:
- module constant in `prepare_training_data.py`, next to the other split
  constants it owns:
  ```python
  # CR-0033: the rasters every split record's window must lie inside.
  # Pinned, not FEATURE_SPEC: adding a model feature must not change the
  # split. Equal to acceptance_split.json "feature_spec_keys" (tested).
  SPLIT_WINDOW_FEATURES = ("evt", "evh", "evc", "sclass", "fdist", "ch",
                           "cc", "tcc", "nlcd", "road_dist", "tsd",
                           "balive", "tpa_live", "qmd", "carbon_dwn")
  ```
- `window_mask` iterates `SPLIT_WINDOW_FEATURES`; its docstring and the
  module docstring step 3 say so.

Today `SPLIT_WINDOW_FEATURES` equals `list(FEATURE_SPEC)` exactly, so the
split output is unchanged.

## Impact
- Split files, manifest, acceptance record: unchanged (same 15 rasters,
  same order). No regeneration.
- `generate_negatives.py` imports `window_mask`; unchanged otherwise.
- Changing the split's raster set later is an explicit edit of the
  constant and of `acceptance_split.json` together (the test fails on
  one without the other).

## One change per CR (CR-0011 A5)
One function and its constant; pipeline code only.

## Risk: LOW
| risk | mitigation |
|---|---|
| The constant drifts from the acceptance config | T1 asserts equality with `acceptance_split.json["feature_spec_keys"]` |

## Test plan (`tests/test_cr0033.py`, pre-approval)
- T1: `SPLIT_WINDOW_FEATURES` equals `feature_spec_keys` (order
  included). Deliberately not tied to `FEATURE_SPEC`: the split must not
  change when a model feature does.
- T2: with an extra feature added to `models.FEATURE_SPEC` and
  `grouse_data.RASTER_FEATURES`, `window_mask` on a synthetic region
  returns the same mask, never opens the extra raster and never records
  it in `rd.rasters_touched` (the manifest's input list); two variants:
  no extra raster on disk, and an extra raster on disk that covers only a
  corner (reading it would change the mask).
- Wrong implementations: today's body fails both T2 variants; a body
  iterating `FEATURE_SPEC` ∩ `available_features()` fails the on-disk
  variant.
- Existing suites pass (`test_acceptance_split`, `test_shared_constants`,
  lints).

## Deliverables
- [x] 1. This CR and `tests/test_cr0033.py`; two independent reviews;
      approval.
- [x] 2. The change; all suites pass.
- [x] 3. BUG-0093, BUG_LOG, PREVENTIVE_ACTIONS (PA-0048, with recurrence
      review and sweep), CHANGELOG, tracker (A33-2); close-out.

## Out of scope
- Moving the constant to `regions.py` so acceptance cross-checks it at
  run time (review A33-2): tracked follow-up.
- Having `acceptance_split.py` read the constant (it deliberately reads
  only its own config and `regions.py`).
- Any change to the split's raster set.
