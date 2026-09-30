# CR-0009: Retrain once on the rebuilt data, and prove the Errol map is still right

**Status: APPROVED (v5.2), 2026-09-30** — author and both reviewers (round 5); user pre-authorised. The user
pre-authorised the full cycle (review, approval by the author and two
reviewers, implementation) on 2026-09-30; the retrain runs on this machine
(NVIDIA L40S, 46 GB). History, verdicts and dispositions:
`CR-0009-review-log.md`. This document states only current intent.

**Depends on:**
| CR | state (2026-09-30) | what CR-0009 needs from it |
|---|---|---|
| CR-0007 | CLOSED (v9.2) | state partition of `evaluated_sightings_*` |
| CR-0013 | APPROVED; code `3230262` | `acceptance_split.py`, config `docs/quality/acceptance_split.json` |
| CR-0012 | text approved (`cec1542`); implementation waits for this CR's deliverable 2 (its deliverable 0) | rebuilt training point files and a passing `acceptance_record.json` |
| CR-0014 | IMPLEMENTED | `road_dist` at TIGER 2023 |
| CR-0010, CR-0008 | implemented | repaired rasters; validity channels |
| CR-0015 | APPROVED; deliverable 1 implemented | nothing for the retrain (it passes no `--an-background`); deliverable 7b only for BUG-0029's closure |

## Scope
Retrain one checkpoint from scratch on the rebuilt data with the
baselines' recipe, refit its calibration, record the new validation
baseline, and re-measure the user-reported Errol map symptom.

## Why now
The data CRs above are the last planned change to the training set before
BUG-0034's fix. One retrain after them gives one set of numbers on that
footing. It is not the final footing: BUG-0034 (open) will change the
training set again (§ Stated limits).

**The reported symptom is already fixed; this CR checks it stays fixed.**
The user reported that a suitability map around Errol ranked the Maine
side far above New Hampshire. `bf8d31a` fixed it. Measured with the
unmodified checkpoints on the user's box, calibration on
(`INVESTIGATION_REPORT_errol_map.md` § "road_dist no-retrain check"):

| map | ME mean | NH mean | P(ME pixel > NH pixel) | ME ≥0.8 | NH ≥0.8 | ME−NH ≥0.8 |
|---|---|---|---|---|---|---|
| `gap3.pth` before | 0.7949 | 0.6289 | 0.8513 | 67.93 % | 5.05 % | 62.9 pp |
| `gap3.pth` after | 0.6333 | 0.6277 | 0.5400 | 10.24 % | 4.88 % | 5.36 pp |
| `bce.pth` before | 0.6887 | 0.4228 | 0.8235 | 45.68 % | 0.11 % | 45.6 pp |
| `bce.pth` after | 0.4217 | 0.4220 | 0.5089 | 0.18 % | 0.10 % | 0.08 pp |

Both maps used the calibration then in `data/calibration/calibration.json`
(fitted on `gap3.pth`, scale 1.4555, bias −1.4895), as the user's command
did.

The rebuild moves the inputs of every number above: CR-0012 rebuilds the
training point files from CR-0007's partitioned sightings and redraws the
split and negatives; CR-0010/CR-0014 turned uncovered area into nodata.
None of those CRs looks at the map. Closing BUG-0022 without this
re-measurement would do what PA-0016 forbids.

## One change per CR (§1.1 A5)
The deliverables span acceptance design (`symptom_check.py`), a model
artefact (checkpoint + calibration) and bookkeeping. They are kept
together because none lands usefully alone: `symptom_check.py` is this
CR's acceptance instrument, written before approval under §1.1 A3; the
calibration belongs to the checkpoint and is invalid without it; and the
bookkeeping closes bugs on this CR's measurements. No production code or
pipeline data changes here.

## The change
### 1. Retrain — the baselines' recipe, 10 epochs (user decision)
```
python train.py --epochs 10 --loss an_full --an-pos-weight 1.0 \
    --embed-dropout 0.1 --dropout 0.4 \
    --dynamic-dropout --dynamic-dropout-step 0.05 --dynamic-dropout-max 0.9 \
    --weight-decay 1e-3 --seed 0 --save-path grouse_cr0009.pth \
    --metrics-csv docs/quality/evidence/CR-0009/retrain/metrics.csv \
    --tensorboard
```
- **Recipe source.** `bce.pth` and `gap3.pth` were trained with
  (`~/.bash_history`, the last `bce.pth` and `gap3.pth` lines):
  - shared: `--loss an_full --embed-dropout 0.1 --dropout 0.4
    --dynamic-dropout --dynamic-dropout-step 0.05 --dynamic-dropout-max
    0.9 --weight-decay 1e-3 --compile`, seed default 0,
    `an_pos_weight` auto = 1.0 (stratified batching);
  - `bce.pth`: `--epochs 50`, year gap default 2;
  - `gap3.pth`: `--epochs 12 --max-year-gap 3`.
- **Epochs: 10, by user decision (2026-09-30)** — not 50. Consequence:
  the comparison is recipe-matched on loss and regularisation but not on
  training length or year gap. `gap3.pth` (12 epochs) is the nearer
  baseline on length; `bce.pth` is the nearer on year gap. Both are
  reported (§ Baselines).
- `--an-pos-weight 1.0` is pinned explicitly so it does not depend on the
  auto rule; it equals what both baselines resolved.
- `--seed 0` equals the baselines' default. One seed only (§ Stated
  limits).
- `--compile` is omitted: it changes execution speed, not the recipe.
- `--metrics-csv` and `--tensorboard` are output-only apart from the RNG
  stream (`--tensorboard` draws one validation batch at
  `model_handler.py:836-840`, which advances torch's global RNG); `bce.pth`
  was run with both. TensorBoard's `run/command` and `run/args` texts
  (under `runs/<timestamp>_grouse_cr0009/`) are the source of the recorded
  argv and `vars(args)`; they are extracted and copied into the evidence
  directory (no code change).
- **Before the run:** `mkdir -p docs/quality/evidence/CR-0009/retrain`
  (`_log_metrics` appends without creating directories), and
  `metrics.csv` must not exist (append mode would mix two runs).
- Everything else is at `train.py` defaults, including `--missing-mask`
  (default on), `--max-year-gap 2`, `--regions` (all three) and
  `--save-path` (default `grouse_single_best.pth`, `train.py:437`, which
  this command avoids).
- **Recorded in `docs/quality/evidence/CR-0009/retrain/`:** the exact
  argv; full `vars(args)` as JSON; `git rev-parse HEAD` and
  `git status --porcelain`; the sha256 of `grouse_cr0009.pth`; the train
  log; and, from CR-0013, the sha256 of `data/pipeline/acceptance_record.json`
  and the config sha256 it records (must equal the sha256 of
  `docs/quality/acceptance_split.json` at the retrain's commit).
- Runtime is not a gate; expect roughly a fifth of a 50-epoch run, plus
  the patch-cache build.

### 2. Refit calibration
```
python calibrate.py --model grouse_cr0009.pth
```
`calibrate.py` builds its validation set with `build_datasets`'
`train_year_gap=2` (fixed; `calibrate.py:356`, `train.py:241`), which
matches this retrain's year gap. `calibration.json`'s `model_path` must
be the absolute path of `grouse_cr0009.pth`. The output files are
copied to `docs/quality/evidence/CR-0009/calibration/`.

### 3. New validation baseline
From the retrain's log and metrics CSV: validation AUC and AP of the
selected epoch; from `calibrate.py`: ECE, MCE and the reliability curve.
Stated as not comparable to any pre-CR number (§ Impact).

### 4. Symptom re-measurement
§ Symptom acceptance, with `symptom_check.py`.

## § Baselines
Two checkpoints, `gap3.pth` and `bce.pth`, both with validity channels,
both runnable on the repaired rasters. Neither is "the" baseline: they
differ in epochs and year gap (§ The change 1), which explains their
different results.

**What depends on what.** Items 1, 2 and 4 depend only on rasters,
checkpoints and a calibration file; CR-0012 changes none of them, so
their baseline values can be measured at any time. Item 3 depends on the
training point files, which CR-0012 rebuilds; its point sets must be
captured before CR-0012's deliverable 6.

**Deliverable 2 (baseline capture) runs before approval.** This extends
§1.1 A3 (which covers gate code, not running it) by **lead-author decision
under the user's standing authorisation (2026-09-30)**: the capture is a
read-only measurement; maps are scored in-process (`symptom_check.py
--reproduce`), never with the `predict.py` CLI, and nothing under `data/`
is written; it writes only under
`docs/quality/evidence/CR-0009/baseline/`, with a `SHA256SUMS` file,
re-verified with `sha256sum -c` and committed. It is CR-0012's
deliverable 0. It captures exactly:
1. **Item 3 point sets**, from two snapshots:
   - **S0**, pre-CR-0007: `/home/ec2-user/grouse_backup/CR-0007/`
     (`pipeline/thinned_positives_R.csv`, `negatives/negatives_R.csv`),
     verified first against `docs/quality/evidence/CR-0007-backup-manifest.txt`;
   - **S1**, current (post-CR-0007, pre-CR-0012): the same files under
     `data/`.

   Each in-box record (box of § Symptom acceptance) is written with
   lon, lat, label, `split`, source region file and TIGER side. At
   `0019d4e` these point files are byte-identical in S0 and S1 (CR-0007
   regenerated only `evaluated_sightings`, `envelope_metrics` and
   `nonveg_flagged`); the capture records both sha256 sets so this is
   evidenced, not assumed.
2. **Scores at those points** for `gap3.pth` and `bce.pth` with the
   current `calibration.json` (copied into the evidence directory first,
   since deliverable 7 overwrites it): AUC and AP by split × side, NH
   side, and all points (item 3's definitions).
3. **The reproduction run** of `symptom_check.py` (§ symptom_check.py,
   R) for both checkpoints, which also records the items 1, 2 and 4
   baseline values on the current rasters.
4. The frozen pairs file and the sha256 of every input read (checkpoints,
   calibration copy, county file, point files, rasters in the box).

After the retrain, item 3 uses the new split's points, reported beside
the captured S0/S1 values.

## § Symptom acceptance
All items run through one committed script, `symptom_check.py`, on the
new checkpoint and its new calibration. Maps:
```
python predict.py --region NH --model grouse_cr0009.pth --bounds -71.25 44.70 -70.95 44.90
python predict.py --region ME --model grouse_cr0009.pth --stride 8
```
The first is the user's command (stride 4, default calibration path) and
serves items 1 and 3. The second is item 4 (~36 min).

**All rows are observations (BUG-0039, user decision 2026-09-30).** No
row has a null distribution of retrain-seed variability, so none can be a
pass/fail limit under PA-0021(c). A value beyond its reference is a
finding to investigate (PA-0016), not a rejection. Promoting a row to a
GATE needs ≥ 50 retrain seeds (a compute decision) and a CR. BUG-0022 is
closed on the recorded values and that investigation.

| # | type | statistic | investigate if | pre-fix / post-fix (§ Why now) | would indicate |
|---|---|---|---|---|---|
| 1a | OBS | `P(ME pixel > NH pixel)` (Mann–Whitney U / n_ME·n_NH) | outside [0.44, 0.56] | 0.8513, 0.8235 / 0.5400, 0.5089 | return of the reported symptom |
| 1b | OBS | ME ≥0.8 share − NH ≥0.8 share, pp | > 15 pp | 62.9, 45.6 / 5.36, 0.08 | a bimodal Maine side that 1a misses (a hypothetical ME 45.0 % / NH 4.9 % = 40.1 pp, constructed in review) |
| 2a | OBS | mean ME−NH `road_dist` (m) over the frozen pairs, NH grid, current rasters | \|·\| > 600 m | +4,255 / +202.75 | a `road_dist` raster regression (raster-only; § Stated limits) |
| 2b | OBS | mean ME−NH calibrated probability over the frozen pairs | > +0.20 | +0.3484 / +0.1078 (`bce.pth`) | model-side reintroduction via `road_dist` |
| 3 | OBS | AUC and AP of the item-1 map at in-box records, by split × side; NH side; all points | report | NH side 0.6918 (41 pos / 11 neg) / 0.6918; all points 0.7570 / 0.7273 (55 pos / 11 neg) (`bce.pth`) | — (no power; see fields) |
| 4 | OBS | whole-ME-region map: score quantiles, ≥0.8 share, NaN fraction, degraded fraction | report | — | input to the `predict.py` validity-mask decision |
| 5 | OBS | the 1a/1b/2a/2b values beside `bf8d31a`'s before/after, in BUG-0022 and BUG-0023 | stated | — | BUG-0023's fix credited to the wrong change |

**PA-0021(f) fields.**
| # | class | subset | null population |
|---|---|---|---|
| 1a | calibrated pixel scores of one stride-4 map (rank statistic, so calibration-invariant) | finite pixels in the box, ME vs NH side by TIGER 2023 county (other/none excluded); counts reported | none: two post-fix values from two recipes, not a seed null |
| 1b | same map, thresholded at 0.8 (depends on calibration) | as 1a | none, as 1a |
| 2a | `road_dist` raster values at pair centres (model-independent) | the 8 frozen pairs, NH region grid | none needed for a deterministic raster read; the value changes only if a raster changes |
| 2b | calibrated probability of a single 64×64 window at each pair centre, D4 TTA (as `inv_matched_pairs.py`) | the 8 frozen pairs | none for retrain seeds; an 8-pair bootstrap is reported as pair-sampling spread only (95 % interval of the mean), not as a false-fail rate |
| 3 | map value sampled at each record | in-box records; post-retrain: union of the three region files (each record in one region after CR-0012; a duplicate (lon, lat, label) is refused); captured: S0/S1 (reference set = NH region files, 55/11; pooling S0's regions double-counts, 97/16, and is not used) | none; 11 negatives, mostly training points |
| 4 | calibrated pixel scores, stride 8 | ME region grid, split into ME side, NH side and outside US counties (Canada, water) | none (descriptive) |
| 5 | — (not distributional) | — | — |

**Stated limits.**
- A uniform level shift that moves both sides equally is invisible to 1a,
  1b and 2b. ME and NH means are reported beside § Why now's table.
- A model trained on a leaking split passes every row. Only CR-0012/0013's
  gates (`acceptance_record.json`) catch that.
- **2a is a raster property.** It is identical for every checkpoint, so it
  cannot see anything the retrain does; it sees a `road_dist` raster that
  changed since CR-0014. CR-0009 changes no raster, so 2a is expected to
  equal its captured value exactly.
- **A model that ignores `road_dist` gives 2b ≈ 0** and sits inside every
  reference; nothing here tells it from a correct model.
- One seed: a value beyond a reference may be seed noise (no null).
- Different training length and year gap from both baselines (§ The
  change 1): a difference from a baseline confounds data with length.
- **BUG-0034 (open):** the year-gap filter drops about 23.6 % of positives
  and 0 % of negatives, so raster vintage partly predicts the label. This
  retrain inherits it, and `gap3.pth` (year gap 3) had a different drop.
  Its fix will change the training set and require another baseline.
- Item 3: most in-box records are training points, so its AUC measures
  fit more than generalisation; hence by split.

## § symptom_check.py
Committed with unit tests before approval (§1.1 A3). Replaces the
untracked `inv_state_split.py`, `inv_matched_pairs.py`,
`inv_points_auc.py`, whose methods it keeps except where stated.

- **Inputs are explicit:** `--model`, `--calibration` (a file path; the
  reproduction passes the evidence copy, the post-retrain run the new
  `calibration.json`), `--map`, `--out`, optional `--region-map`,
  `--points` (a captured point-set CSV). It writes only under `--out`.
- **Side assignment:** TIGER 2023 counties
  (`data/roads/tl_2023_us_county.zip`, sha256 recorded); STATEFP 23 = ME,
  33 = NH, 50 = VT. Pixels: rasterized on the map grid (pixel-centre
  rule). Points: `within` join, first match kept. The region files'
  `state` column is not used.
- **Nodata:** NaN/nodata map pixels and points on them are excluded and
  counted per side.
- **Calibration:** every probability row names the calibration file and
  its `model_path`; the script warns if `model_path` differs from
  `--model` (the reproduction's `bce.pth` run expects this warning).
- **Map provenance (BUG-0028):** each map is copied into `--out` and its
  sha256 recorded before it is read, or it is scored in-process through
  `predict.py`'s own functions. Either way a spot check re-scores ≥ 20
  map cells with `--model` and `--calibration` and refuses (exit 2) if any
  differs by more than 1e-3 (fp16 autocast jitter measured up to 8.6e-5; another model differs by ~0.43) — an input guard, not an acceptance row.
- **Frozen pairs:** the 8 pairs of `inv_matched_pairs.csv` (copied to the
  evidence directory with sha256), mapped to NH-grid cells by lon/lat. The
  script also re-runs `inv_matched_pairs.py`'s matching on the current NH
  rasters — identical evt/evh/evc/sclass/nlcd, |Δch| ≤ 2 m, |Δcc| ≤ 5 %,
  |Δtcc| ≤ 5 %, full 64×64 window, no missing key value, NPAIRS 8, SEED 0,
  ME candidates in `rng.permutation` order, first NH match — and reports
  whether it selects the same 8 cells. Items 2a/2b always use the frozen
  pairs.
- **Output:** a report and `results.json`; every row carries its type,
  the three PA-0021(f) fields, the reference, the calibration source and
  the counts per subset. Exit 0 whatever the numbers (OBS); exit 2 on a
  missing input or a failed guard.
- **Unit tests** (synthetic, no real data): a map with a known P and known
  ≥0.8 shares, including a constructed bimodal Maine side where 1a is in
  band and 1b is not; side assignment on a synthetic two-polygon county
  file; nodata exclusion counts; frozen-pair lookup and the pair means;
  AUC by split × side on a known point set; the duplicate-record refusal;
  the provenance guard refusing a map made by another model; the PA-0021(f)
  fields present on every row.
- **R — real-data reproduction (GATE on the instrument, exact).** On the
  current rasters, with the evidence copy of the current calibration:
  - `gap3.pth`: 1a 0.5400, 1b 5.36 pp, ME/NH means 0.6333/0.6277;
  - `bce.pth`: 1a 0.5089, means 0.4217/0.4220; 2b +0.1078 with per-pair
    values as in the report; item 3 on S1's NH region files: all points
    0.7273, NH side 0.6918;
  - 2a: +202.75 m with per-pair values [−549, −185, 490, 1154, 203, −155,
    835, −171].

  Each must equal the reference at its printed precision. Basis for
  expecting equality: the NH-box inputs are unchanged by CR-0010/CR-0014
  (reviewer A, round 4 M3). A mismatch stops the CR: the first check is
  whether a box input changed (against the CR-0010/CR-0014 backups), and
  the result goes to the review log (PA-0016).

## § Disk
Measured: 21 GB free (2026-09-30). The patch cache (`data/cache`, now
empty) is rebuilt for the retrain: ≈ 1.5–2 GB. No raster backup is
deleted.

**Backups** to `/home/ec2-user/grouse_backup/CR-0009/`, with a sha256
manifest in `docs/quality/evidence/CR-0009/`, before anything is
overwritten: `data/predictions/` (468 KB), `data/calibration/` (112 KB),
`*.pth*` (1.3 GB). CR-0009 writes no pipeline or negatives file.

**Rollback:** restore the two backed-up directories; the new checkpoint
is a new file. A lower validation number is never a rollback trigger (it
is the expected result of removing the train/val leak, BUG-0027).

## § Stale markers
`STALE_SEE_CR-0010.txt` in a directory is removed only when every other
file in it has been regenerated from `grouse_cr0009.pth` or deleted.
| directory | files | regenerated by | marker |
|---|---|---|---|
| `data/calibration/` | `calibration.json`, `reliability.csv`, `reliability.png` | § The change 2 | removed |
| `data/predictions/` | `NH_custom_suitability.{tif,kmz}` | item 1's `predict.py` run | removed only if the next two rows are done |
| | `ME_custom_suitability.{tif,kmz}` (stride 16), `VT_custom_suitability.{tif,kmz}` (stride 8) | `predict.py --region R --bounds <the existing file's lon/lat extent> --stride <its stride>`, seconds to a minute each. The original request bounds are unknown (BUG-0028), so the extent may differ from the original by the window padding; recorded | |
| | `ME_suitability.{tif,kmz}` (new) | item 4 | |
| `data/maps/` | `grouse_diagnostic_map_{ME,NH,VT}.png`, `map_data/cb_2023_us_state_20m.zip` | not by CR-0009 (sightings diagnostics from `analyze_grouse.py`, and an input download; not model outputs) | stays; ownership in the open-issues tracker |

## Impact
- Every pre-CR metric (~0.82 AUC, ~0.79 AP, `0.811` best-rank) stops being
  comparable; `CHANGELOG.md` says so, and says BUG-0034 will move the
  footing again.
- The new validation number will be lower, by construction.
- Existing checkpoints stay on disk and still run.
- Training set: the counts CR-0012 records at its deliverable 6 (expected
  6,232 positives, CR-0012 § Impact); recorded in the evidence directory.

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A lower metric is read as a regression | § Impact and `CHANGELOG.md` |
| The retrain overwrites a checkpoint | New `--save-path`; `*.pth*` backed up |
| Calibration or maps overwritten without a copy | § Disk backups; evidence copies |
| Recipe confounded with data | Recipe pinned to the baselines' (§ The change 1); remaining difference (epochs, seed) stated |
| The symptom regresses unnoticed | § Symptom acceptance 1a, 1b, 2b |
| The instrument measures something else | R reproduces the published numbers first |
| NH's halved dataset degrades NH | NH mean and item 3, reported |

## Test plan
**Here, before approval:** `symptom_check.py` unit tests; R on the
current rasters (deliverable 2).
**Here, after the retrain:** CR-0012's standing checks pass inside
`train.py` (it refuses otherwise); § Symptom acceptance;
`smoke_test_training.py`; the calibration reliability curve.
**Not here:** whether the model is better than the pre-CR one (no
trustworthy pre-CR number, BUG-0027); field accuracy (no independent
ground truth); stability across seeds (one seed); the effect of 10 vs 50
epochs.

## Deliverables (in execution order)
- [x] 1. `symptom_check.py` and `tests/test_symptom_check.py`, committed
      before approval (§1.1 A3).
- [x] 2. Baseline capture (§ Baselines), before approval; `SHA256SUMS`
      verified and committed. R passes against the evidence copies; S0 = S1 byte-identical (`docs/quality/evidence/CR-0009/baseline/`).
- [x] 3. Round-5 review; approval by the author and both reviewers.
- [ ] 4. Confirm CR-0012 deliverable 6 passed, with `acceptance_record.json`
      written; CR-0014 landed.
- [x] 5. Backups (§ Disk): 23 files, 1.3 GB, verified; manifest `docs/quality/evidence/CR-0009/backup_SHA256SUMS`.
- [ ] 6. Retrain (§ The change 1); record the evidence it lists.
- [ ] 7. Refit calibration; confirm `model_path`.
- [ ] 8. Record the new validation baseline, with the not-comparable
      note and BUG-0034.
- [ ] 9. Maps (§ Symptom acceptance, § Stale markers); run
      `symptom_check.py`; record every number in the evidence directory
      and summarise it in BUG-0022.
- [ ] 10. Bookkeeping:
      - BUG-0022: close, citing item 1–5 results and the investigation.
      - BUG-0023: add item 5's record.
      - BUG-0027: close (CR-0012 deliverable 8: "closing after CR-0009").
      - BUG-0029: record "CR-0009 closed". It becomes CLOSED only if
        CR-0015 deliverable 7b has passed (CR-0015 deliverable 9's rule);
        otherwise its status is unchanged.
      - BUG-0039: close; corrective action = v5 § Symptom acceptance
        (OBS with PA-0021(f) fields). Update PA-0021's Swept? cell entry
        for BUG-0039 to "resolved by CR-0009 v5 (demoted to OBS)".
      - PA-0016's Swept? cell: append "CR-0009: BUG-0022 closed on a
        re-measurement after the rebuild (`docs/quality/evidence/CR-0009/`);
        no new instance".
      - `BUG_LOG.md` rows for each status change.
- [ ] 11. `CHANGELOG.md`: pre-CR metrics not comparable; BUG-0034 note.
- [ ] 12. Remove stale markers per § Stale markers.

## Out of scope
- Model architecture, loss, hyperparameters and tuning beyond pinning the
  baselines' recipe; the 10-epoch choice is the user's.
- SSL re-pretraining.
- BUG-0034's fix.
- BUG-0028 (prediction outputs carry no provenance) — which is why maps
  are hashed by hand.
- `predict.py`'s validity mask (decided after item 4).
- Whole-region maps other than ME; `data/maps/`.
