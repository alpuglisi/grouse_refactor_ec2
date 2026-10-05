# BUG-0074: `train.sample_background_points` gives every assumed-negative background point one vintage (the latest year of `features[0]`), unlike the positives it is trained against (PA-0020 time-axis instance, latent)

> Found by the PA-0020 sweep in CR-0019 deliverable 8, 2026-09-30, at
> `00b0b84` (CR-0019 § Out of scope named it for this sweep).
> **Status: FIXED by CR-0031, 2026-10-05** (code `e18944d`; smoke run
> `docs/quality/evidence/CR-0031/cr0031_smoke.log`). Original status: OPEN
> (latent: opt-in flag, off by default); owner: lead.

## 1. Description
With `train.py --an-background R > 0` (the L_AN-full "assumed negative"
background points, CR-0015), `build_datasets` adds `R × n_pos` random
background locations per region to the training set with label 0. Every
one of them gets the same `year`: the latest raster year of the **first
feature in the list**. Positives carry their own year (2020–2024 after
CR-0019), and each record's year selects its raster vintage. So the
background class is one vintage, the positive class five, and the
vintage identifies most of the background rows. Which vintage it is
depends on the order of `--features`.

## 2. Where encountered
- `train.py:165-167` and `:220-221` (`sample_background_points`), called
  from `build_datasets` at `train.py:371-374` when
  `background_per_pos > 0`.
- `pretrain.py:194` also calls it; the SSL pretraining there uses no label,
  so it is not a class asymmetry (recorded, not an instance).

## 3. What it caused to fail
**Latent: no current model is affected.** `--an-background` defaults to
0.0; CR-0009's retrain used 0.0
(`docs/quality/evidence/CR-0009/retrain/tb_run_args.txt:59`); CR-0019
changed no model. Historical sweep runs used `--an-background 1.0`
(`sweep/r16_combo5.log:1` and siblings, before CR-0012).

If enabled on today's data (measured with `grouse_data.RegionData` and
`train.discover_features`, 2026-09-30, read-only):
- default feature order, `features[0] = evt`, raster years 2022–2024 →
  every background point is year **2024**; positives are 2024 for only
  942 of 4,809 (19.6 %; CR-0019 live OBS O9);
- `--features` with `nlcd`, `road_dist`, `tsd`, `evc`, `fdist`, `ch`, `cc`
  or a TreeMap feature first → year **2025**, a vintage **no positive or
  negative record uses** (the same vintage `predict.py` resolves; see
  PA-0020 Swept?, "separate mechanism"); `tcc` first → 2023.

At `R = 1` the background adds as many label-0 rows as there are
positives, all at one vintage: vintage alone would then predict the label
for those rows, the BUG-0034 mechanism on the time axis.

## 4. What the defect was
`train.py:165-167`:
```python
    feat = features[0]            # validity is judged on `features[0]` as passed
    path = rd.latest_raster_path(feat)
    year = max(rd.raster_years(feat))
```
`train.py:220-221`:
```python
    out = pd.DataFrame({"longitude": lons, "latitude": lats,
                        "year": int(year), "label": 0.0, "weight": 1.0})
```

## 5. Root cause analysis (Five Whys)
1. *Why do all background rows share one vintage?* The function writes
   one scalar `year` for the whole frame.
2. *Why that year?* It is the year of the raster it used to judge
   validity (`features[0]`, latest vintage), chosen for sampling
   convenience.
3. *Why is that a label signal?* Each record's year selects the raster
   vintage it is read from (`dataset.py:122-126`), and the positives it is
   combined with carry their own, different years.
4. *Why was it not caught?* The background rows are produced at training
   time, not in a split file, so no CR-0013 gate (and not E14) sees them
   (PA-0029's run-time producer); PA-0020's earlier sweeps looked at
   acquisition queries, not at training-time producers of label-0 rows.

**Root cause:** a training-time producer of one class assigns the time
attribute (year → vintage) by its own rule, independent of the epoch
distribution of the class it is trained against, and no build-time check
compares the classes on that axis for rows produced at run time.

## 6. Corrective action
**CR-0031** (approved 2026-10-05 by two independent reviewers; code
`e18944d`):
- `sample_background_points` takes a **required** keyword `year`: an
  integer validates draws on `rd.raster_path(features[0], year)` — the
  raster `GrousePatchDataset` reads a row of that year from, nearest-year
  and empty-placeholder fallbacks included — and stamps every row with
  that year; `"latest"` keeps the old single vintage for `pretrain.py`
  only (its SSL tiles carry no label); anything else raises.
- New `background_for_positives` draws, per distinct training-positive
  year `y`, `round(c_y × R)` points (seed `(seed, region_i, y)`), and
  checks the result's year histogram.
- `build_datasets` recomputes the expected counts from the training
  positives itself and raises on any difference (a run-time gate for this
  run-time producer, PA-0029).
- Tests: `tests/test_cr0031.py` (15, synthetic rasters with a missing year
  and an empty placeholder vintage); reviewer-built wrong implementations
  each caught (`docs/quality/evidence/CR-0031/reviewA/wrong_impl_runs.txt`).
- On real data (EC2, `--an-background 1.0`): every region's background
  year counts equal its training positives' (ME 469/588/648/282/304,
  NH 97/118/137/118/164, VT 163/147/170/174/268 for 2020–2024).
This addresses the root cause: the producer no longer assigns the time
attribute by its own rule, and a run-time check compares the classes on
that axis.

Candidate fix as first written (kept for the record): Candidate fix: draw each background point's year from the
region's training positives' year distribution (or from the negatives'
after BUG-0073's fix), with a test that the background year histogram
matches it; and judge validity on that year's raster. That changes
`sample_background_points`' output schema semantics and the training set
for `--an-background > 0`, so it needs a CR. Until then: **no run with
`--an-background > 0`** (tracker item; CR-0020 must not use it unless it
fixes this first).

Status: **OPEN** (latent). Owner: lead.

## 7. Recurrence review (`CLAUDE.md` §4)
**Searched:** `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md` for "background",
"vintage", "year", "an-background", "assumed negative", "latest".

**Matches:**
- **BUG-0034 / PA-0020** — same mechanism (per-class time-axis selection
  makes vintage predict the label). BUG-0034 was the acquisition floor;
  this is a training-time producer. Not a duplicate.
- **BUG-0073** — same axis, per-class year-assignment rule; different
  producer (split-file dedup/collapse rules vs a run-time sampler).
- **BUG-0042 / BUG-0029** — earlier fixes to the same function
  (training-block and in-state constraints: the spatial axis), which did
  not look at its time attribute.
- **PA-0029** — rows produced at run time are not covered by the file
  gates; this is such a producer.

**Prior-preventive-action failure analysis.**
- **PA-0020** covers it: clause (i) "must use the same … epoch … as
  everything its output will be combined with". It was **not followed**
  when BUG-0029/BUG-0042 changed this function (their fixes were scoped to
  the spatial axis), and PA-0020's earlier sweeps (CR-0007 deliverable 6)
  enumerated acquisition queries, not training-time producers of rows.
  Category: sweep scope too narrow (by producer type), not a gap in the
  rule text.

**Re-checked at the fix (CR-0031, 2026-10-05):** `BUG_LOG.md` rows since
filing (BUG-0076, BUG-0077) and `PREVENTIVE_ACTIONS.md` PA-0033..PA-0035:
PA-0033 (BUG-0073, extends PA-0020) now names this instance in its Swept?
cell; no new prior instance of this mechanism. Analysis above stands.

## 8. Preventive action
**No new rule.** PA-0020 covers it, and PA-0033 (written after this BUG,
for BUG-0073) now requires the per-cell distribution comparison it lacked;
CR-0031 implements that comparison for this producer. The Swept? cells of
PA-0020, PA-0029 and PA-0033 record the fix.

As first written: **No new rule; PA-0020 covers it.** The PA-0020 Swept? cell now names
training-time producers of labelled rows (`sample_background_points`) as
part of the sweep scope and this BUG as the owner of the finding. If
BUG-0073's fix CR extends PA-0020 to per-class attribute-assignment rules,
this instance is cited there.

## Cross-references
CR-0019 deliverable 8 and § Out of scope; CR-0031 (fix); BUG-0034;
BUG-0073; PA-0020; PA-0029; PA-0033.
