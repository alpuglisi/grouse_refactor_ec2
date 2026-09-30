# CR-0015: Draw assumed-negative background points only in-state, only in training blocks, and without treating 0 as nodata

**Status: PROPOSED (v1) — awaiting review.** Nothing implemented.
History and dispositions: `CR-0015-review-log.md`. This document states
only current intent.

**Split out of CR-0012** by user decision (2026-09-30): the function is
live in two entry points that have nothing to do with the train/val split
files, so it gets its own review.

**Order:** the interim guard (deliverable 1) can land at once. The rest
lands **after CR-0007** (it uses `regions.in_state`) and **after CR-0012**
(it uses the global block grid, `SPLIT_SEED` and `block_assignments.csv`).
Not needed by CR-0009's pinned retrain command, which does not pass
`--an-background`.

## Scope
Change `train.sample_background_points` so the assumed-negative points
used for training lie in the region's own state, in training blocks only,
and are rejected only for true nodata — and make `pretrain.py`'s use of
the same function explicit.

## Why now
`sample_background_points` (`train.py:120-165`) draws uniform row/col
pairs over the region's reference raster. Three defects:
1. **Out of state (BUG-0029 remainder).** The raster covers the region's
   box, which includes neighbouring states and Canada; about 47 % of ME's
   box is outside the state. CR-0012 fixes the positive side; this is the
   assumed-negative side.
2. **Into validation blocks (the BUG-0027 leak, reopened).** Points are
   labelled 0 and added to **training** (`train.py:290-305`), but nothing
   keeps them out of validation blocks — about 20 % land there
   (CR-0012 round-1 reviewer A). No CR-0013 gate can see it: these points
   are drawn in memory, not written to a file.
3. **0 treated as nodata (BUG-0032).** `bad = set(NODATA_SENTINELS) |
   {nodata, 0}` (`:143`) rejects a pixel whose first feature reads `0`.
   The first feature is `evt`, where 0 does not occur today (0.0 % of
   pixels in all three regions), so the defect is latent — but it would
   silently bias sampling for any feature where 0 is a reading (PA-0006).

The path is live: `pretrain.py:179` calls it for every SSL tile, and the
sweep recipes (`sweep/launch.sh`) and Run B use `--an-background 1.0`.

## The change

### 1. `train.sample_background_points(rd, features, n, seed=0, *, region=None, train_blocks_only=False)`
- **Validity:** reject a point only when the first feature's pixel is in
  `NODATA_SENTINELS`, equals the file's declared nodata, or is not
  finite. `0` is no longer rejected (BUG-0032).
- **In-state** (when `region` is given): keep a point only if
  `regions.in_state(lon, lat, region)` (CR-0007).
- **Training blocks** (when `train_blocks_only`): compute the point's
  global block id exactly as CR-0012 §2 does (`x_5070`/`y_5070`,
  `BLOCK_ORIGIN_5070`, `BLOCK_SIZE_M`). Keep it only if the block's split
  is `train`: the split in `block_assignments.csv` if the block is there,
  otherwise CR-0012's rule — `val` iff
  `int(md5(f"{SPLIT_SEED}:{block_id}").hexdigest(), 16) % 10000 < vf × 10000`,
  with `vf` from `block_assignments.csv` as CR-0012 defines it. The rule is
  imported from the module CR-0012 puts it in, not re-typed (PA-0001).
- **Budget:** with ~40–50 % acceptance, raise the oversample to
  `m = max(256, 4 * (n - len(lons)))` per round and up to 80 rounds; the
  `SystemExit` on shortfall stays, with the acceptance rate in its
  message.
- **Determinism:** unchanged — `numpy.random.default_rng(seed)`.

### 2. Call sites
- `train.build_datasets` (AN path, `:296`): passes `region=region,
  train_blocks_only=True`.
- `pretrain.py:179` (SSL tiles): passes `region=region`,
  `train_blocks_only=False`. SSL tiles carry no labels, so drawing them
  in validation blocks leaks no label; keeping them in-state matches the
  records the model is trained and validated on. **This changes the SSL
  tile set** (in-state only, and 0-valued pixels eligible): an existing
  `grouse_ssl_backbone.pth` stays valid but is not reproducible from the
  new code, which is recorded, not hidden.

### 3. Interim guard
Until §1–§2 land, `train.py` exits when `--an-background > 0`, naming this
CR. It is removed by deliverable 5.

## Acceptance
| id | type | check | required |
|---|---|---|---|
| U1 | GATE | Synthetic grid, two states, known blocks: every returned point is in-state | all |
| U2 | GATE | Same grid: with `train_blocks_only`, no point lies in a `val` block (from the file or the md5 rule) | 0 |
| U3 | GATE | A pixel reading `0` is eligible; sentinels, declared nodata and NaN are not | pass |
| U4 | GATE | Exactly `n` points, and the same points for the same seed | pass |
| U5 | GATE | Shortfall raises `SystemExit` with the acceptance rate | pass |
| V1 | GATE | Real data, n = 5,000 per region, AN path: an **independent** re-check (polygon test from the county file, block id recomputed from lon/lat, md5 rule re-typed in the check) finds 0 out-of-state and 0 val-block points | 0 / 0 |
| V2 | OBS | Acceptance rate per region (in-state × train-block) | report |
| L1 | GATE | Lint test: no `*.py` in the tracked, non-evidence set builds a nodata set containing a literal `0` next to `NODATA_SENTINELS` | 0 matches |

V1's re-check lives in `tests/test_background_sample.py` (skipped with a
message if CR-0012's `block_assignments.csv` does not exist yet). L1 is the
mechanical enforcement for PA-0006's reader side (§3.4).

## Impact
- **AN-background training** (`--an-background > 0`): points move
  in-state and out of validation blocks. Every model trained with the AN
  path before this CR learned from out-of-state and validation-block
  assumed negatives; recorded in `CHANGELOG.md`.
- **SSL pretraining:** tiles move in-state (see §2).
- **Not affected:** the default training path (`--an-background 0`),
  CR-0009's pinned retrain, every file CR-0013 gates.

## Risk: LOW
| risk | mitigation |
|---|---|
| Too few accepted points → `SystemExit` | Budget raised; V2 reports the rate |
| Block rule drifts from CR-0012's | Imported, not re-typed; V1 re-types it independently |
| AN path used between CR-0012 and this CR | Interim guard (deliverable 1) |

## Test plan
**Here:** U1–U5, L1, V1–V2 after CR-0012 lands.
**Not here:** model-quality effect of the change (needs an AN-path
retrain; out of scope — CR-0009's retrain does not use it).

## Deliverables (in execution order)
- [ ] 1. Interim guard (§3), with a test; can land before CR-0007/CR-0012.
- [ ] 2. File BUG-0032 (0 treated as nodata in `sample_background_points`)
      with all §2 sections. Recurrence review: PA-0006 (from BUG-0008,
      swept in BUG-0017, extended by BUG-0036) — prior-PA failure
      analysis: the BUG-0017 sweep covered `dataset.py`'s patch path, not
      `train.py`; PA-0006's Swept? cell is updated, and L1 is the new
      mechanical enforcement. `BUG_LOG.md` row.
- [ ] 3. After CR-0007 and CR-0012: §1 and §2; U1–U5, L1.
- [ ] 4. V1–V2 on real data; save to
      `docs/quality/evidence/CR-0015-background.txt`.
- [ ] 5. Remove the interim guard.
- [ ] 6. Close BUG-0029 (the assumed-negative remainder; CR-0012 closed
      the positive side) and BUG-0032; `CHANGELOG.md` note.

## Out of scope
- Whether the AN loss should buffer away from known presences (a
  modelling choice; the docstring's rationale stands).
- Retraining with the AN path.
- The year-gap filter after the split (BUG-0034).
