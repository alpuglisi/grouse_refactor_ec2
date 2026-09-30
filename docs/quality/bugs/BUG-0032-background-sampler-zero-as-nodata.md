# BUG-0032: The assumed-negative background sampler treats a first-feature reading of 0 as nodata

> The id was allocated by CR-0007 v7 §7 and deferred without a record.
> CR-0015 deliverable 2 files it (CR-0015 review log, lineage rows
> "BUG-0032 was a deferral…").

## 1. Description
`train.sample_background_points` draws random raster pixels as
assumed-negative background points (and as SSL tiles for
`pretrain.py`). It rejected a draw whose first-feature pixel was in
`NODATA_SENTINELS`, equal to the declared nodata, **or equal to 0**.
`0` is a legitimate reading for several features, e.g. `tcc` (0 %
canopy), `road_dist` (on a road) or `tsd` (disturbed this year). Using
one of these as the first feature would have excluded every such pixel
from the background, with no error.

## 2. Where encountered
- `train.py:144` at `00c0b6f`, inside `sample_background_points`
  (`train.py:121-165`). Its callers are `train.build_datasets`
  (`--an-background > 0`) and `pretrain.py:180`.
- Allocated in the CR-0007 v7 §7 review. It was carried to CR-0015 as a
  review finding, which counts under `CLAUDE.md` §2 even though it was
  never seen running. The L1 lint (`tests/test_nodata_zero_lint.py`)
  flags it as rule (a).

## 3. What it caused to fail
**Latent under the discovered feature order; live with an explicit
`--features`.**
- `features[0]` is the pixel judged. When features are discovered, it is
  `evt`, and `evt == 0` occurs in 0.0000 % of pixels in all three
  regions (CR-0015 review log, reviewer A round 1). So the rejection
  removed nothing.
- `train.py` takes `features = args.features or discover_features(...)`
  (`train.py:914` at `00c0b6f`), and `pretrain.py` does the same. An
  explicit `--features tcc ...` puts a feature with real zeros first.
  The sampler then silently drops every 0-canopy pixel. The assumed
  negatives, and the SSL tiles, would under-represent open land, with no
  warning.
- The comment `# spec order: categorical first` (`:135`) claimed
  `features[0]` is always categorical. That holds only for discovered
  features.

## 4. What the defect was
`train.py:141-150` at `00c0b6f`:
```python
        nodata = src.nodata if src.nodata is not None else -9999
        bad = set(NODATA_SENTINELS) | {nodata, 0}
        ...
            ok = ~np.isin(vals, list(bad)) & np.isfinite(vals)
```

## 5. Root cause analysis (Five Whys)
1. *Why were 0-valued pixels rejected?* `0` was put in the reject set
   next to the sentinels and the declared nodata.
2. *Why was it put there?* The sampler treats 0 as "probably fill".
   LANDFIRE categorical grids have no class 0, and older readers
   (BUG-0008, BUG-0017) collapsed nodata to 0.
3. *Why was that assumption unsafe?* The judged feature is whatever is
   passed first. The code's comment assumed a categorical feature, but
   nothing enforced it, and continuous features such as `tcc`,
   `road_dist` and `tsd` use 0 as a reading.
4. *Why did PA-0006 not stop it?* PA-0006 forbids exactly this overload.
   Its sweeps were each scoped to one file or layer: BUG-0008's to the
   inference path, BUG-0017's to `dataset.py`, BUG-0036's to encoders.
   None read `train.py`'s sampler (§7).
5. *Why could no check catch it?* No mechanical rule looked for a
   literal 0 next to the nodata set, so the rule relied on whoever
   swept to read the right file.

**Root cause:** a validity mask built its reject set from "known fill
values", including a literal `0`, instead of only the declared nodata,
the sentinel set and non-finite values. The rule forbidding that
(PA-0006) had no mechanical enforcement, and each sweep was scoped by
file rather than by mechanism.

## 6. Corrective action
CR-0015 §2, deliverable 6 (commit `2c23d7d`):
```python
            ok = np.isfinite(vals) & ~np.isin(vals, sentinels)
            if declared_nodata is not None:
                ok &= vals != declared_nodata
```
- `sentinels` is `NODATA_SENTINELS`, and 0 is now a reading.
- The `:135` comment now reads "validity is judged on `features[0]` as
  passed".
- Test U3 (`tests/test_cr0015_sampler.py`) checks that a 0 pixel is
  eligible. It also checks that each sentinel, the declared nodata and
  NaN are not eligible.
- L1 (`tests/test_nodata_zero_lint.py`) no longer reports the statement.
  Its pin was removed in the same commit.

This addresses the root cause in two parts. The mask now rejects only
nodata. L1 enforces the rule mechanically across the whole tracked
tree, not just this file.

Status: **FIXED** (CR-0015 deliverable 6). It closes at CR-0015
deliverable 9.

## 7. Recurrence review (`CLAUDE.md` §4)
I searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "nodata", "0",
"sentinel" and PA-0006. The same mechanism appears three times before
this:
- **BUG-0008** (`predict.py`, CLOSED). The mask was
  `ref_band[cy, cx] == 0 and ref_nodata != 0`. PA-0006 was created from
  it.
- **BUG-0017** (`dataset.py`, `nan_to_num(nan=0.0)`), OPEN and
  unconfirmed when CR-0015 was written. The CR-0015 deliverable 4
  re-sweep finds it fixed by `51a4ad0`, which introduced `MISSING_CODE`.
  See that bug's doc.
- **BUG-0036** (value encoders cast NaN to 0). PA-0006's scope was
  extended from it.

**This is a recurrence (the fourth instance of PA-0006's mechanism).**

**Prior-preventive-action failure analysis (PA-0006).** The category is
**too narrow and not enforced-verifiable**.
- *Too narrow:* each PA-0006 sweep was scoped by file or layer, not by
  mechanism:
  - BUG-0008's covered the inference path;
  - BUG-0017's covered `dataset.py`'s patch path;
  - BUG-0036's covered write-side encoders.

  The mechanism is a validity mask that admits a literal 0 next to the
  nodata set, in any file. `train.py`'s sampler was in none of those
  scopes.
- *Not enforced-verifiable:* nothing checked the rule mechanically, so
  each sweep found only what its chosen files contained.

## 8. Preventive action
**PA-0028, extends PA-0006.** A validity or nodata mask rejects only the
declared nodata, `NODATA_SENTINELS` and non-finite values. Anything more,
such as a literal `0`, needs an L1 allowlist entry justifying it.
- **Mechanical enforcement (§3.4):** `tests/test_nodata_zero_lint.py`
  (L1) parses every tracked `.py` file, excluding top-level
  `inv_*`/`res_*` and `docs/**`. It fails on any unallowlisted literal-0
  comparison or display next to a nodata-bearing name.
- **Out of L1's reach:** a 0 reached through a variable, a
  `fill_value=0` read, `nan_to_num`, or an integer cast of NaN. A manual
  sweep covers these on each PA-0006/PA-0028 pass.

The row text for `PREVENTIVE_ACTIONS.md` is in
`docs/quality/evidence/CR-0015-bookkeeping-rows.md`.

**Sweep (§3.5), CR-0015 deliverable 4, 2026-09-30, scoped by mechanism.**
- **Scope:** every tracked non-evidence `.py` file that reads
  `NODATA_SENTINELS` or a raster's declared nodata. That is 24 production
  and tool files and 7 test files, plus `models.py`, `model_handler.py`,
  `inspect_point.py`, `diagnose_wetland.py` and `generate_negatives.py`,
  which handle nodata without matching the grep.
- **L1 matches:**
  - `train.py`: this bug, fixed.
  - Three NOT-A-DEFECT, each now an allowlist entry with its
    justification:
    - `find_tsd_contrast_points.py`: NLCD has no class 0;
    - `generate_time_since_disturbance.py`: VAT class 0 "Background"
      stays in coverage, and the statement is a disturbance predicate;
    - `check_road_dist.py`: 0 means "no US county" in a rasterised
      STATEFP.
- **Manual read, two findings:**
  - `predict.py`'s `Edge` contrast metric turns nodata into 0 through
    `torch.nan_to_num` → **BUG-NEW-1**.
  - `GrouseResNet.embed` with `missing_mask=False` sends
    `MISSING_CODE` to the embedding row of class 0 and NaN to 0.0. For
    `fdist`, 0 is a real code in about 92–96 % of in-coverage pixels
    → **BUG-NEW-2**.
- **Checked and not affected:** every other `nan_to_num` (all use
  `nan=MISSING_CODE`), every boundless or WarpedVRT fill (every source
  declares a sentinel), `generate_treemap_features.py:300` (fill 0 is
  unreachable, and anything outside the source is masked to -9999), the
  `fill=0` rasterisations (coverage or zone masks, not readings), and
  the int casts after NaN rows are dropped.
- **BUG-0017:** FIXED by `51a4ad0` (see its doc).

(The BUG-NEW-n ids are placeholders; the lead assigns the real ids.)
