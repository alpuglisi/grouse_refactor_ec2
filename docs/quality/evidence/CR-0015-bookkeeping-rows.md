# CR-0015 bookkeeping rows, proposed for the lead to apply

The implementer did not edit `BUG_LOG.md` or `PREVENTIVE_ACTIONS.md`
(handoff §3.4). Apply each row below by exact whole-line insertion or
replacement (rows can contain `\|`, so never use sed on them).

**Placeholder ids.** `BUG-NEW-1`, `BUG-NEW-2` and `BUG-NEW-3` are sweep
findings. Allocate them as BUG-0050 and up, in filing order, after
checking `BUG_LOG.md` for the highest id. Then rename
`docs/quality/bugs/BUG-NEW-n-*.md` and replace every `BUG-NEW-n` in:
- this file;
- BUG-0017, BUG-0032, BUG-0042 and the BUG-NEW docs;
- `docs/quality/change-requests/CR-0015-review-log.md`;
- `docs/quality/evidence/CR-0015-background.txt`.

(`grep -rl BUG-NEW- docs/` finds them.)

## 1. `BUG_LOG.md`: new rows (newest first, above the current top row)

```
| BUG-NEW-3 | 2026-09-30 | Checkpoints carry no split provenance: `--distill-from` teachers, `--init-from` (any GrouseResNet state dict), `--resume` and `calibrate.py --model` accept a checkpoint fitted under another split; 81.0 % of today's val positives were training rows under the pre-CR-0012 split (CR-0015 PA-0029 producer sweep) | Model artefacts that feed training or calibration record no holdout, so the holdout is not enforced on run-time producers of training signal | None yet; owner the lead, via a CR (split digest in checkpoint config, refusal on mismatch; SSL checkpoints exempt). Does not affect CR-0009 as pinned | OPEN |
| BUG-NEW-2 | 2026-09-30 | With `missing_mask=False` (legacy checkpoints, `train.py --no-missing-mask`) `embed` clamps `MISSING_CODE` to row 0 and fills NaN with 0.0; `fdist` 0 is a real code in ~92–96 % of pixels (CR-0015 PA-0006 re-sweep) | Opt-out embedding mode maps nodata onto a legitimate 0; the refusal guard covers only CR-0010-repaired rasters | None yet; owner the lead, via a CR (refuse the flag for training or widen `refuse_legacy_checkpoint_on_repaired`). Residual of BUG-0017 | OPEN |
| BUG-NEW-1 | 2026-09-30 | `predict.py` TensorBoard Edge metric: `torch.nan_to_num` turns continuous nodata into 0 and categorical `MISSING_CODE` counts as a class change, biasing `Edge/pearson_r/*` at coverage edges (CR-0015 PA-0006 re-sweep) | Nodata converted to the legitimate value 0 instead of excluded by a validity mask (PA-0006 mechanism) | None yet; one-function fix (difference only valid pairs); owner the lead (trivial-fix candidate). Diagnostic only | OPEN |
| BUG-0042 | 2026-09-30 | `--an-background` assumed-negative points drawn uniformly over the raster and added to training with label 0: 19.3 / 19.6 / 20.5 % of in-state draws (ME/NH/VT) lay in validation blocks; no file gate sees them | Spatial holdout enforced only on the split files; a run-time producer of training rows was neither constrained nor gated | CR-0015 §2–§3 (deliverable 6, `2c23d7d`): `train_blocks_only` via `regions.to_5070` → `block_ids` → `block_split`; U2 and V1 (0 validation-block points, independent re-check) PASS. PA-0029 (extends PA-0018); sweep found BUG-NEW-3 | FIXED |
| BUG-0032 | 2026-09-30 | `train.sample_background_points` rejected a first-feature reading of 0 as nodata (`set(NODATA_SENTINELS) \| {nodata, 0}`); latent with discovered `evt`, live with explicit `--features tcc …` | Validity mask built from "known fill values" including a literal 0; PA-0006 unenforced and swept by file, not mechanism (4th instance) | CR-0015 §2 (deliverable 6, `2c23d7d`): reject only sentinels, declared nodata and non-finite; U3 PASS; L1 lint (`tests/test_nodata_zero_lint.py`) enforces it. PA-0028 (extends PA-0006); re-sweep found BUG-NEW-1, BUG-NEW-2; BUG-0017 closed | FIXED |
```

The BUG-0032 row contains a literal `|` inside backticks, escaped as
`\|`, as other rows in the log do.

## 2. `BUG_LOG.md`: replacements (exact whole-line)

**BUG-0017.** Old line (line 56 at `00c0b6f`):
```
| BUG-0017 | 2026-09-22 | `dataset.py`'s training patches may conflate nodata sentinels with a legitimate value of 0 (unconfirmed) | Same mechanism as BUG-0008, in the training-data path instead of inference masking — not yet verified against real attribute tables | None — deliberately deferred pending domain confirmation; would need a CR if confirmed (touches cache format) | OPEN, unconfirmed |
```
New line:
```
| BUG-0017 | 2026-09-22 | `dataset.py`'s training patches may conflate nodata sentinels with a legitimate value of 0 (unconfirmed) | Same mechanism as BUG-0008, in the training-data path instead of inference masking; premise confirmed 2026-09-30 (`fdist` 0 is a real code in ~92–96 % of pixels) | Fixed by `51a4ad0` (`nan_to_num(nan=MISSING_CODE)`, cache format v2, validity channels); re-examined by the CR-0015 deliverable 4 re-sweep (doc §9); `missing_mask=False` residual owned by BUG-NEW-2 | CLOSED |
```

**BUG-0029.** Apply this at CR-0015 deliverable 9, which is now, since
deliverable 7b passed. Old line (line 36 at `00c0b6f`):
```
| BUG-0029 | 2026-09-30 | Negatives fetched per state (`stateProvince`), positives clipped by overlapping box: half of NH's positives lie outside NH vs 1 of 2,244 negatives | Two label classes drawn from differently shaped regions; nothing compares their support | Membership: CR-0007 (state partition, implemented); split and draw: CR-0012. PA-0020 (filed) | OPEN — fixed when CR-0012 lands, closed after CR-0009 |
```
New line:
```
| BUG-0029 | 2026-09-30 | Negatives fetched per state (`stateProvince`), positives clipped by overlapping box: half of NH's positives lie outside NH vs 1 of 2,244 negatives | Two label classes drawn from differently shaped regions; nothing compares their support | Membership: CR-0007 (state partition, implemented); split and draw: CR-0012 (landed, deliverable 6 18/18 GATEs); assumed negatives: CR-0015 (in-state draw; V1 0 out-of-state points, deliverable 7b). PA-0020 (filed) | FIXED — closed when CR-0009 closes |
```

## 3. `PREVENTIVE_ACTIONS.md`: new rows (append after PA-0026, or after PA-0027 if CR-0012 d8 files it)

```
| PA-0028 | Extends PA-0006. A validity or nodata mask rejects only the declared nodata, `NODATA_SENTINELS` and non-finite values; any further rejected value (e.g. a literal `0`) needs a reviewed entry in the L1 allowlist (`tests/test_nodata_zero_lint.py`) stating why that value is not a reading. Enforced by L1 over every tracked `.py` (minus top-level `inv_*`/`res_*` and `docs/**`); forms L1 cannot see (a 0 through a variable, `fill_value=0`, `nan_to_num` defaults, integer casts of NaN, `clamp`/`masked_fill` onto a real code) are read by hand on every PA-0006/PA-0028 sweep. | yes — CR-0015 deliverable 4, 2026-09-30, by mechanism: every tracked non-evidence file reading `NODATA_SENTINELS` or a declared nodata (24 production/tool + 7 test files, plus `models.py`, `model_handler.py`, `inspect_point.py`, `diagnose_wetland.py`, `generate_negatives.py`). L1: BUG-0032 fixed; 3 statements allowlisted with justification (`find_tsd_contrast_points.py` NLCD has no 0; `generate_time_since_disturbance.py` VAT 0 Background stays covered; `check_road_dist.py` STATEFP fill 0); the deliberate pre-CR copy in `tests/cr0015_wrong_samplers.py` allowlisted. Manual read: BUG-NEW-1 (`predict.py` Edge metric), BUG-NEW-2 (`missing_mask=False` embed); BUG-0017 closed (fixed by `51a4ad0`); all other `nan_to_num`/boundless/VRT/`fill=0`/int-cast sites checked, not affected. Open: BUG-NEW-1, BUG-NEW-2 (owner the lead) | BUG-0032; swept, BUG-NEW-1, BUG-NEW-2 |
| PA-0029 | Extends PA-0018. Every producer of training rows or training signal — including rows generated in memory at training time, teacher soft labels, and checkpoints used as initial weights or calibrated — is constrained by the holdout (draws only from training blocks, carries no label, or is refused when fitted under another split) and is covered by a gate that reads what it actually produces, not only the split files. | yes — CR-0015 deliverable 2, 2026-09-30: every run-time producer (`train.build_datasets` and its callers `train.py`/`calibrate.py`/`bench_pipeline.py`, `pretrain.py`, `tune.py`, `tune_bins.py`, `smoke_test_training.py`, `diagnose_*`, `dataset.py` expansion/augmentation, `losses.py`, inference scripts). Found: BUG-0042 (fixed by CR-0015; V1 gate) and BUG-NEW-3 (checkpoints without split provenance; open, owner the lead). Not affected: split-file rows (gated by `standing_checks`), rotation/augmentation views, SSL tiles (no label), `clean.py`/`legacy/gen_negs.py` (guarded). Design questions logged to the tracker (D1–D4, owner the lead) | BUG-0042; swept, BUG-NEW-3 |
```

## 4. `PREVENTIVE_ACTIONS.md`: Swept? cell updates (append to the existing cell text)

- **PA-0006.** Append: ` **Re-swept by mechanism, CR-0015 deliverable 4 (2026-09-30):** see PA-0028's cell — BUG-0032 fixed, BUG-0017 closed (fixed by 51a4ad0), BUG-NEW-1 and BUG-NEW-2 filed; extended by PA-0028 (L1 enforcement)`.
  In its Source cell, append `; recurrence BUG-0032`.
- **PA-0018.** Append: ` CR-0015 (2026-09-30): run-time producers of training rows were outside this sweep — BUG-0042 (assumed negatives in validation blocks, fixed by CR-0015) and BUG-NEW-3 (checkpoint provenance, open); extended by PA-0029`.
  In its Source cell, append `; recurrence BUG-0042`.

## 5. Tracker items (`docs/quality/CR-0007-0008-OPEN-ISSUES.md`), owner the lead

- **D1:** validation data drives model selection, the divergence guard,
  `--dynamic-dropout` (`model_handler.py:1306`) and Platt calibration.
  There is no third holdout, so reported validation metrics carry
  selection bias. Decision needed: accept and document, or add a test
  holdout.
- **D2:** `calibrate.cross_fitted_probs` (`calibrate.py:229-239`) uses
  random folds, not block folds, so `ece_cross_fitted` and
  `nll_cross_fitted` are slightly optimistic. Reported numbers only.
- **D3:** training-negative weights (`Selection_Ratio` over every
  sighting, validation included) and the 300 m buffer depend on
  validation positives (`generate_negatives.attach_weights`). No
  CR-0013 gate asks this.
- **D4:** there is no buffer between training and validation blocks.
  The 64 px window is about 1.9 km and the blocks are 3 km, so features
  leak across block edges. Labels do not.
- The `train.py:246` comment "Covers every caller" omits
  `smoke_test_training.py` and `diagnose_training.py`, which build
  datasets without `standing_checks` (no model is kept). Doc fix.
- The `find_tsd_contrast_points.py` docstring (about lines 40-44) says
  `read_window_stack` "zeroes NODATA_SENTINELS to 0". That has been
  stale since `51a4ad0`. Doc fix.
- **V3 status (CR-0015 deliverable 7a):** see
  `CR-0015-review-log.md` § Implementation record. Under the CR's
  literal rule, V3 is demoted to OBS because the md5-0.18 sampler (V1's
  target) is not separated. Decision for the lead: keep OBS, or re-read
  the rule per PA-0021(c) as "the broken sampler V3 exists to catch",
  under which V3 would be a GATE.
