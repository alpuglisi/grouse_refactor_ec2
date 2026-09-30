# CR-0009: Retrain once on the rebuilt data, and prove the Errol map is still right

**Status: ON HOLD for execution (user decision 2026-09-30: the retrain and
its validation are carried out manually). Document revised to v4 so it is
correct when executed — awaiting review.** History: `CR-0009-review-log.md`.

**Gated on:** CR-0007 (state partition), CR-0012 (global split, pooled
draw), CR-0013 (acceptance gates), CR-0014 (`road_dist`) — all landed with
their acceptance recorded. CR-0010 (raster repair) and CR-0008 (generator
fixes) are already implemented.

## Scope
Retrain once from scratch on the rebuilt data, refit calibration, record
the new validation baseline, and re-measure the user-reported Errol map
symptom.

## Why now
One retrain after all data CRs gives one set of comparable numbers.

**The reported symptom is already fixed; this CR proves it stays fixed.**
The user reported that a suitability map around Errol ranked the Maine
side far above New Hampshire. `bf8d31a` fixed it, measured with the
unmodified checkpoints on the user's exact box:

| map | ME mean | NH mean | P(ME pixel > NH pixel) | ME ≥0.8 | NH ≥0.8 |
|---|---|---|---|---|---|
| `gap3.pth` before | 0.7949 | 0.6289 | 0.8513 | 67.9 % | 5.1 % |
| `gap3.pth` after | 0.6333 | 0.6277 | 0.5400 | 10.24 % | 4.88 % |
| `bce.pth` before | 0.6887 | 0.4228 | 0.8235 | — | — |
| `bce.pth` after | 0.4217 | 0.4220 | 0.5089 | — | — |

The rebuild moves all of it: CR-0007 partitions records by state (NH
positives 2,244 → 1,079); CR-0012 changes the split and negative draw;
CR-0010/CR-0014 turn uncovered area into nodata (ME `road_dist` ≈ 47 %
nodata). None of those CRs looks at the map. Closing BUG-0022 without this
re-measurement would do what PA-0016 forbids.

## The change
1. **Retrain from scratch** with the pinned command:
   ```
   python train.py --regions ME NH VT --seed 42 --missing-mask \
       --save-path grouse_cr0009.pth
   ```
   All other arguments at `train.py` defaults, which are recorded in the
   checkpoint. `--save-path` must be a new file (default
   `grouse_single_best.pth`, `train.py:436`). `--missing-mask` is
   required: without validity channels, `predict.py` and `calibrate.py`
   refuse the repaired rasters (CR-0010/CR-0008).
2. **Refit calibration** (`calibrate.py`) for the new checkpoint;
   `calibration.json`'s `model_path` must name it.
3. **Record the new validation baseline**, stated as not comparable to
   any pre-CR number.
4. **Re-measure the symptom** (§ Symptom acceptance) with
   `symptom_check.py`.

## § Baselines
The comparison baselines are the table above, from
`INVESTIGATION_REPORT_errol_map.md`, measured on `gap3.pth` and `bce.pth`.
Both checkpoints have validity channels, so `predict.py` still runs them
on the repaired rasters. Neither is "the" baseline: their stored configs
are identical yet they give different results, so both are reported.

**What expires:** item 3's point set (the in-box records) changes when
CR-0007/CR-0012 land. Capture it — and any other pre-CR measurement —
**before CR-0012 lands**. There is no escape mode (user decision
2026-09-30).

## § Symptom acceptance
All items run through one committed script, `symptom_check.py`
(replacing the untracked `inv_state_split.py`, `inv_matched_pairs.py`,
`inv_points_auc.py`), on the new checkpoint and the user's box:

```
python predict.py --region NH --model grouse_cr0009.pth --bounds -71.25 44.70 -70.95 44.90
```

| # | type | check | reference (reported beside, not a pass/fail limit) | would indicate |
|---|---|---|---|---|
| 1a | OBS | `P(ME pixel > NH pixel)` | in [0.44, 0.56] | return of the reported symptom (pre-fix 0.82–0.85) |
| 1b | OBS | ME ≥0.8 share − NH ≥0.8 share | ≤ 15 pp | a bimodal Maine side that passes 1a (constructed: 40.1 pp at P = 0.45); accepted baseline 5.36 pp, pre-fix 62.8 pp |
| 2a | OBS | ME−NH `road_dist` on matched-habitat pairs, ME grid, new rasters | \|·\| ≤ 600 m | a `road_dist` regression (pre-fix +4,255 m, post-fix +203 m) |
| 2b | OBS | ME−NH mean probability on those pairs | ≤ +0.20 | model-side reintroduction via `road_dist` |
| 3 | OBS | In-box AUC, all three regions pooled, beside 0.6918 | report | — (41 positives, 11 negatives: no power) |
| 4 | OBS | Whole-ME-region map at stride 8 (~36 min): score distribution, ≥0.8 share and nodata/degraded fraction, separately inside and outside US coverage, per region | report | input to the `predict.py` validity-mask decision |
| 5 | RECORD | BUG-0023's symptom was fixed by `bf8d31a`; this CR verifies it survived the rebuild | stated | the record crediting the wrong change |

**All symptom items are observations (BUG-0039, user decision
2026-09-30).** The reference values were taken from one or two observed
runs or an 8-pair bootstrap, with no null distribution of retrain-seed
variability, so they cannot be pass/fail limits under PA-0021(c). They
are reported beside the before/after table; a value past its reference
is a finding to investigate (PA-0016), not an automatic rejection.
Promoting any of them to a GATE needs a calibration over ≥ 50 retrain
seeds (a compute decision) and a CR. BUG-0022 is closed on the recorded
values and that investigation, not on a pass/fail.

**Stated limits.**
- A uniform level shift that moves both sides equally is invisible to every item here.
  ME and NH means are reported beside the table above.
- A model trained on a leaking split passes items 1–4. Only CR-0012/0013's
  gates can catch that.
- A model that ignores `road_dist` passes 1 and fails 2.

## § Disk
Measured: 22 GB free. The patch cache was purged by CR-0010 and is purged
again by CR-0014, so the retrain builds a fresh one (~28 GB at the
current record count).
1. **Back up** with checksums: `data/pipeline/` (24 MB),
   `data/negatives/` (27 MB), `data/calibration/` (112 KB), `*.pth*`
   (1.3 GB). Raster backups are CR-0010's (9.46 GB) and CR-0014's.
2. If free space is under 30 GB, delete the CR-0010 raster backup only
   after CR-0010's gates are confirmed (they are), with the user's go-ahead.
3. Retrain; refit calibration; run § Symptom acceptance.

**Rollback:** restore the backed-up trees and `git checkout`. A lower
validation number is never a rollback trigger — it is the expected
consequence of removing the train/val leak (BUG-0027). Rollback is for
a broken pipeline.

## Impact
- Every pre-CR metric (~0.82 AUC, ~0.79 AP, `0.811` best-rank) stops being
  comparable; `CHANGELOG.md` says so.
- The new validation number will be lower, by construction.
- Existing checkpoints stay on disk and still run (`--save-path` is new).
- Training set: ≈ 6,230 pooled positives (ME 3,659 / NH 1,079 / VT 1,492).

## Risk: MEDIUM
| risk | mitigation |
|---|---|
| A lower metric is read as a regression | Stated here and in `CHANGELOG.md` |
| The retrain overwrites a checkpoint | New `--save-path`; `*.pth*` backed up |
| Disk exhaustion | § Disk |
| The symptom regresses unnoticed | § Symptom acceptance 1a, 1b, 2a, 2b |
| NH's halved dataset degrades NH | NH mean (1a/stated limits) and item 3, reported |

## Test plan
**Here, after the retrain:** § Symptom acceptance; the new validation
AUC/AP with CR-0013's gates passing; `smoke_test_training.py`; a
calibration reliability curve.

**Not here:** whether the model is better than the pre-CR one (no
trustworthy pre-CR number, BUG-0027); field accuracy (no independent
ground truth); stability across seeds (one seed).

## Deliverables (in execution order)
- [ ] 1. `symptom_check.py`, unit-tested on a synthetic map (may be
      written before approval, §1.1).
- [ ] 2. Before CR-0012 lands: capture item 3's point set and any other
      pre-CR measurement; record where.
- [ ] 3. Confirm CR-0007, CR-0012, CR-0013 and CR-0014 are landed with
      their acceptance recorded.
- [ ] 4. **User go-ahead for compute.**
- [ ] 5. Backups (§ Disk).
- [ ] 6. Retrain (§ The change 1).
- [ ] 7. Refit calibration; confirm `model_path`.
- [ ] 8. Record the new validation baseline with a not-comparable note.
- [ ] 9. Run § Symptom acceptance; record every number here.
- [ ] 10. Close BUG-0027 and BUG-0029; close BUG-0022 citing § Symptom
      acceptance; update PA-0016's Swept? cell.
- [ ] 11. `CHANGELOG.md`: pre-CR metrics not comparable to post-CR.
- [ ] 12. Remove the `STALE_SEE_CR-0010.txt` markers once new predictions
      and calibration replace the stale ones.

## Out of scope
- Model architecture, loss, hyperparameters, tuning. Data only.
- SSL re-pretraining.
- BUG-0028 (prediction outputs carry no provenance) — which is why the
  checkpoint is recorded by hand.
- `predict.py`'s validity mask (decided after item 4).
